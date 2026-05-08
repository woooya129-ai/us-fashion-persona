# SPDX-License-Identifier: AGPL-3.0-only
"""Worker thread for the job/run lifecycle (WS-JOB).

This module contains ZERO LLM, network, async, or Streamlit code. The
``evaluator`` callable is **injected**: WS-PROMPT-LLM will provide a sync
adapter wrapping its async runner.

Worker contract:
    1. start_job
    2. create_run
    3. for each persona payload:
         - if cancel_requested -> stop iterating (cooperative cancellation)
         - call evaluator(payload) and translate any exception to api_failed
         - persist via save_result (transactional with the counter bump)
    4. complete_job:
         - cancelled  -> cancel was observed before/during iteration
         - completed  -> all payloads handled, lifecycle finished cleanly
                         (per-persona failures DO NOT promote to 'failed';
                         UI judges from the result rows)
         - failed     -> worker lifecycle itself broke (e.g. malformed
                         payload contract, save_result raising for a non-
                         per-persona reason, evaluator returning an unknown
                         status). The job MUST always reach a terminal
                         state.

JobStatus semantics (frozen contract — referenced by WS-APP UI):
    completed = worker lifecycle finished normally
    cancelled = cancel was honoured cleanly
    failed    = worker lifecycle itself broke; the original exception is
                re-raised after the DB is closed out, so the calling thread
                / test can observe the cause.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

# evaluator return-type is a small dict with these keys.
# WS-PROMPT-LLM's make_sync_evaluator_for_worker MUST emit this shape.
EvaluatorResult = dict[str, Any]
Evaluator = Callable[[dict], EvaluatorResult]

# Required keys in payload that worker reads directly.
_PAYLOAD_REQUIRED_KEYS: tuple[str, ...] = ("persona_id",)


@dataclass(frozen=True)
class WorkerInput:
    """All inputs the worker needs to run a job to completion.

    evaluator(payload) -> dict with keys:
        - "status":        ResultStatus literal
        - "error_type":    str | None
        - "response_json": str | None
        - "latency_ms":    int | None

    The worker treats the evaluator as a black box and trusts the contract.
    Any exception raised by the evaluator call is converted to an api_failed
    row. Malformed return values are lifecycle contract failures.
    """

    db_path: Path
    job_id: str
    run_meta: RunMeta
    persona_payloads: list[dict]
    evaluator: Evaluator


def _coerce_evaluator_result(result: Any) -> EvaluatorResult:
    """Validate the evaluator's return shape; raise TypeError if it's wrong.

    Defensive — the WS-PROMPT-LLM contract is documented but bugs happen,
    and a malformed evaluator must not silently corrupt the DB.
    """
    if not isinstance(result, dict):
        raise TypeError(f"evaluator must return a dict, got {type(result).__name__}")
    if "status" not in result:
        raise TypeError("evaluator result missing required key 'status'")
    return result


def run_worker(input_: WorkerInput) -> None:
    """Execute the full lifecycle for one job.

    Cooperative cancellation:
        cancel_requested is checked BEFORE each new evaluator call. The
        in-flight call is allowed to complete and its result is persisted.
        This matches PM v3 §11.7 ("partial results are saved").

    Lifecycle finalization:
        Once start_job succeeds, the job MUST reach a terminal state. Any
        unhandled exception in the lifecycle (malformed payload, save_result
        raising, create_run raising, etc.) is caught, the job is closed out
        as 'failed', and the original exception is re-raised so the calling
        thread / test can observe it.

        Per-persona evaluator failures stay 'api_failed' (not 'failed') —
        that distinction is by design and tested separately.
    """
    db_path = input_.db_path
    job_id = input_.job_id
    run_id = input_.run_meta.run_id

    start_job(db_path, job_id)
    started = True

    terminal_written = False
    try:
        create_run(db_path, input_.run_meta)

        cancelled = False
        for payload in input_.persona_payloads:
            # Defensive read — keeps the error message helpful if the caller
            # (e.g. WS-APP) builds a malformed payload list.
            for key in _PAYLOAD_REQUIRED_KEYS:
                if key not in payload:
                    raise KeyError(f"persona payload missing required key: {key!r}")

            if is_cancel_requested(db_path, job_id):
                cancelled = True
                break

            persona_id: str = payload["persona_id"]
            cache_key: str | None = payload.get("cache_key")

            status: str
            error_type: str | None
            response_json: str | None
            latency_ms: int | None

            try:
                raw_result = input_.evaluator(payload)
            except Exception as exc:
                # Broad catch is intentional — any evaluator failure becomes
                # api_failed. We deliberately do NOT log the exception message
                # because evaluator (LLM client) errors may carry redacted-
                # but-still-sensitive provider text. error_type is the class
                # name only, which is safe per runtime data policy.
                status = "api_failed"
                error_type = type(exc).__name__
                response_json = None
                latency_ms = None
            else:
                # Return-shape violations are not per-persona API failures.
                # They mean the WS-PROMPT adapter broke the worker contract,
                # so the outer lifecycle handler must mark the job failed and
                # re-raise the original TypeError.
                result = _coerce_evaluator_result(raw_result)
                status = result["status"]
                error_type = result.get("error_type")
                response_json = result.get("response_json")
                latency_ms = result.get("latency_ms")

            save_result(
                db_path=db_path,
                run_id=run_id,
                persona_id=persona_id,
                cache_key=cache_key,
                status=status,  # type: ignore[arg-type]
                error_type=error_type,
                response_json=response_json,
                latency_ms=latency_ms,
            )

        final_status: JobStatus = "cancelled" if cancelled else "completed"
        complete_job(db_path, job_id, final_status)
        terminal_written = True
    except BaseException:
        # Lifecycle failure: the job must NOT stay in 'running'. Try to
        # close it out as 'failed' on a best-effort basis (the DB might be
        # locked / unreachable; we suppress secondary errors so the
        # original exception propagates intact).
        if started and not terminal_written:
            with suppress(Exception):
                complete_job(db_path, job_id, "failed")
            # Intentionally NOT logging the exception body here — provider
            # raw error / payload content may be sensitive.
            # The exception class is enough for operator observability.
            logger.warning(
                "worker lifecycle failed; job closed as 'failed' (job_id=%s)",
                job_id,
            )
        raise


def start_worker_thread(input_: WorkerInput) -> threading.Thread:
    """Start a non-daemon thread running run_worker(input_) and return it.

    The caller (UI / test) is responsible for joining the thread. We use
    daemon=False so the worker is allowed to flush partial results even
    if the parent process exits cleanly.
    """
    thread = threading.Thread(
        target=run_worker,
        args=(input_,),
        name=f"ws-job-worker-{input_.job_id[:8]}",
        daemon=False,
    )
    thread.start()
    return thread
