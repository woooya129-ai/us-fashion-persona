# SPDX-License-Identifier: AGPL-3.0-only
"""Worker thread for the job/run lifecycle.

The worker owns job state transitions and run_results persistence. It can run
either the legacy synchronous evaluator or the app's async evaluator through
src.async_runner so the real app path uses bounded concurrency.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.async_runner import RunnerConfig, run_evaluations
from src.job_manager import (
    JobStatus,
    RunMeta,
    complete_job,
    create_run,
    is_cancel_requested,
    save_result,
    start_job,
)

logger = logging.getLogger(__name__)

EvaluatorResult = dict[str, Any]
Evaluator = Callable[[dict], EvaluatorResult]
AsyncEvaluator = Callable[[dict], Coroutine[Any, Any, EvaluatorResult]]

_PAYLOAD_REQUIRED_KEYS: tuple[str, ...] = ("persona_id",)


@dataclass(frozen=True)
class WorkerInput:
    """All inputs the worker needs to run a job to completion."""

    db_path: Path
    job_id: str
    run_meta: RunMeta
    persona_payloads: list[dict]
    evaluator: Evaluator | None = None
    evaluator_async: AsyncEvaluator | None = None
    concurrency: int = 5
    max_concurrency: int = 10


def _coerce_evaluator_result(result: Any) -> EvaluatorResult:
    """Validate the evaluator's return shape; raise TypeError if it is wrong."""
    if not isinstance(result, dict):
        raise TypeError(f"evaluator must return a dict, got {type(result).__name__}")
    if "status" not in result:
        raise TypeError("evaluator result missing required key 'status'")
    return result


def _validate_payload(payload: dict) -> None:
    for key in _PAYLOAD_REQUIRED_KEYS:
        if key not in payload:
            raise KeyError(f"persona payload missing required key: {key!r}")


def _result_cache_key(_payload: dict, result: EvaluatorResult) -> str | None:
    """Return a cache FK only when a cache row should exist."""
    explicit = result.get("cache_key")
    if explicit is not None:
        return str(explicit)
    return None


def _save_result_from_evaluator_result(
    *,
    db_path: Path,
    run_id: str,
    payload: dict,
    raw_result: Any,
) -> None:
    _validate_payload(payload)
    result = _coerce_evaluator_result(raw_result)
    save_result(
        db_path=db_path,
        run_id=run_id,
        persona_id=payload["persona_id"],
        cache_key=_result_cache_key(payload, result),
        status=result["status"],  # type: ignore[arg-type]
        error_type=result.get("error_type"),
        response_json=result.get("response_json"),
        latency_ms=result.get("latency_ms"),
    )


def _run_async_evaluations_for_worker(input_: WorkerInput) -> bool:
    """Run the async evaluator through the shared concurrency runner."""
    if input_.evaluator_async is None:
        raise TypeError("WorkerInput requires evaluator or evaluator_async")

    db_path = input_.db_path
    job_id = input_.job_id
    run_id = input_.run_meta.run_id
    errors: list[BaseException] = []
    cancel_observed = False

    for payload in input_.persona_payloads:
        _validate_payload(payload)

    def cancel_check() -> bool:
        nonlocal cancel_observed
        requested = is_cancel_requested(db_path, job_id)
        if requested:
            cancel_observed = True
        return requested

    def on_result(payload: dict, result: dict) -> None:
        try:
            _save_result_from_evaluator_result(
                db_path=db_path,
                run_id=run_id,
                payload=payload,
                raw_result=result,
            )
        except BaseException as exc:
            errors.append(exc)
            raise

    asyncio.run(
        run_evaluations(
            payloads=input_.persona_payloads,
            evaluator_async=input_.evaluator_async,
            config=RunnerConfig(
                concurrency=input_.concurrency,
                max_concurrency=input_.max_concurrency,
                cancel_check=cancel_check,
            ),
            on_result=on_result,
        )
    )
    if errors:
        raise errors[0]
    return cancel_observed


def run_worker(input_: WorkerInput) -> None:
    """Execute the full lifecycle for one job.

    Per-persona evaluator exceptions become api_failed rows. Contract failures
    such as malformed payloads, unknown statuses, or DB write failures mark the
    job failed and re-raise the original exception.
    """
    db_path = input_.db_path
    job_id = input_.job_id

    start_job(db_path, job_id)
    started = True
    terminal_written = False

    try:
        create_run(db_path, input_.run_meta)

        if input_.evaluator_async is not None:
            cancelled = _run_async_evaluations_for_worker(input_)
        else:
            if input_.evaluator is None:
                raise TypeError("WorkerInput requires evaluator or evaluator_async")
            cancelled = False
            for payload in input_.persona_payloads:
                _validate_payload(payload)

                if is_cancel_requested(db_path, job_id):
                    cancelled = True
                    break

                try:
                    raw_result = input_.evaluator(payload)
                except Exception as exc:
                    raw_result = {
                        "status": "api_failed",
                        "error_type": type(exc).__name__,
                        "response_json": None,
                        "latency_ms": None,
                    }

                _save_result_from_evaluator_result(
                    db_path=db_path,
                    run_id=input_.run_meta.run_id,
                    payload=payload,
                    raw_result=raw_result,
                )

        final_status: JobStatus = "cancelled" if cancelled else "completed"
        complete_job(db_path, job_id, final_status)
        terminal_written = True
    except BaseException:
        if started and not terminal_written:
            with suppress(Exception):
                complete_job(db_path, job_id, "failed")
            logger.warning(
                "worker lifecycle failed; job closed as 'failed' (job_id=%s)",
                job_id,
            )
        raise


def start_worker_thread(input_: WorkerInput) -> threading.Thread:
    """Start a non-daemon thread running run_worker(input_) and return it."""
    thread = threading.Thread(
        target=run_worker,
        args=(input_,),
        name=f"ws-job-worker-{input_.job_id[:8]}",
        daemon=False,
    )
    thread.start()
    return thread
