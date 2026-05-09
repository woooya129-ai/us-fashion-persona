# SPDX-License-Identifier: AGPL-3.0-only
"""Async runner for parallel LLM evaluations + cache integration.

PM v3 §11.4, §11.5:
  - asyncio.Semaphore limits concurrent LLM calls (default 5, max 10).
  - Partial results are saved immediately via on_result callback.
  - cancel_check() halts new task creation; existing tasks run to completion
    (PM v3 §11.7).
  - on_result exception in one payload does not affect other payloads.

WS-JOB integration:
  - WS-JOB worker (src/worker.py) calls run_evaluations from inside its
    own thread + event loop. The worker passes evaluator_async (which is
    typically a cached evaluator wrapping the LLM client) and on_result
    (which writes to run_results via job_manager.save_result).

Cache integration:
  - make_cached_evaluator() returns an async evaluator that consults a
    cache_lookup callable BEFORE awaiting the underlying LLM evaluator.
  - On cache hit: returns status="cached" and never invokes the LLM
    evaluator (verified by test).
  - On cache miss: awaits the LLM evaluator and stores the result via
    cache_store.
  - cache_lookup / cache_store are injected callables; this module does
    not touch sqlite directly.

No subprocess, eval, exec, or pickle.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerConfig:
    """Configuration for run_evaluations.

    Attributes:
        concurrency: Number of concurrent LLM calls (default 5,
            PM v3 §11.5).
        max_concurrency: Hard cap; concurrency > max_concurrency raises
            ValueError before any task starts.
        cancel_check: Optional callable returning True when cancellation
            is requested. When True, no new tasks are scheduled; tasks
            already started run to completion.
    """

    concurrency: int = 5
    max_concurrency: int = 10
    cancel_check: Callable[[], bool] | None = None


async def run_evaluations(
    payloads: list[dict],
    evaluator_async: Callable[[dict], Coroutine[Any, Any, dict]],
    config: RunnerConfig,
    on_result: Callable[[dict, dict], None],
) -> None:
    """Run async LLM evaluations with concurrency control.

    For each payload:
      - Acquires a semaphore slot.
      - Calls evaluator_async(payload).
      - Calls on_result(payload, result) immediately after each evaluation
        so the callback retains payload context (persona_id, cache_key, etc.)
        needed to persist the result via WS-JOB save_result().
      - If evaluator_async raises, a synthetic api_failed result is built
        from the exception type so on_result still fires.
      - If on_result raises, the exception is logged (type-only — no
        provider raw / payload body) and other payloads continue
        (exception isolation per payload).
      - cancel_check() checked before scheduling each new task. When True,
        scheduling stops; already-scheduled tasks run to completion.

    Args:
        payloads: List of evaluation payload dicts (one per persona).
        evaluator_async: Async callable taking a payload dict and returning
            a result dict with keys: status, error_type, response_json,
            latency_ms (the WS-JOB evaluator contract).
        config: RunnerConfig controlling concurrency and cancellation.
        on_result: Synchronous callback invoked immediately after each
            result with (payload, result). Typically saves the result to
            the database via WS-JOB save_result(persona_id=payload[...],
            cache_key=payload.get("cache_key"), ...).

    Raises:
        ValueError: If concurrency is non-positive or exceeds max_concurrency.

    Implementation note:
        on_result signature is (payload, result). Earlier draft passed only
        result, which lost the persona_id/cache_key context required by
        WS-JOB save_result.
    """
    if config.max_concurrency <= 0:
        raise ValueError(f"max_concurrency must be positive, got {config.max_concurrency}")
    if config.concurrency <= 0:
        raise ValueError(f"concurrency must be positive, got {config.concurrency}")
    if config.concurrency > config.max_concurrency:
        raise ValueError(
            f"concurrency={config.concurrency} exceeds max_concurrency={config.max_concurrency}"
        )

    semaphore = asyncio.Semaphore(config.concurrency)

    async def _run_one(payload: dict) -> None:
        async with semaphore:
            # Re-check cancel AFTER acquiring the slot. All tasks are
            # create_task'd up front, so the for-loop check above only
            # filters tasks not yet scheduled. PM v3 §11.7: "이미 진행 중인
            # 호출은 완료 또는 timeout까지 대기" — a task that hasn't
            # acquired its semaphore slot yet is NOT yet "in progress",
            # so we skip it without firing evaluator/on_result.
            if config.cancel_check is not None and config.cancel_check():
                return
            try:
                result = await evaluator_async(payload)
            except Exception as exc:  # noqa: BLE001 — synthesize api_failed
                # Type-only safe log.
                # provider raw error / payload body must not enter logs;
                # Runtime data policy forbids storing raw LLM responses.
                logger.warning(
                    "evaluator_async failed; converted to api_failed: %s",
                    type(exc).__name__,
                )
                result = {
                    "status": "api_failed",
                    "error_type": type(exc).__name__,
                    "response_json": None,
                    "latency_ms": None,
                }
            try:
                on_result(payload, result)
            except Exception as exc:
                # Type-only safe log — payload may contain user concept
                # text indirectly.
                logger.warning(
                    "on_result callback raised; continuing: %s",
                    type(exc).__name__,
                )

    tasks: list[asyncio.Task] = []
    for payload in payloads:
        if config.cancel_check is not None and config.cancel_check():
            logger.info("cancel_check() returned True; stopping new task creation.")
            break
        tasks.append(asyncio.create_task(_run_one(payload)))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def make_sync_evaluator_for_worker(
    evaluator_async: Callable[[dict], Coroutine[Any, Any, dict]],
) -> Callable[[dict], dict]:
    """Wrap an async evaluator as a synchronous callable for WS-JOB.

    For single-call use from a non-async context (e.g. WS-JOB worker
    thread). For parallel execution, the worker should call
    run_evaluations directly.

    The returned callable creates a fresh event loop per call via
    asyncio.run, so it MUST NOT be invoked from within an already-running
    event loop.

    Args:
        evaluator_async: Async callable with signature (dict) -> dict.

    Returns:
        Synchronous callable with the same input/output signature.
    """

    def _sync_eval(payload: dict) -> dict:
        return asyncio.run(evaluator_async(payload))

    return _sync_eval


# ---------------------------------------------------------------------------
# Cache-integrated evaluator factory
# ---------------------------------------------------------------------------


def make_cached_evaluator(
    llm_evaluator_async: Callable[[dict], Coroutine[Any, Any, dict]],
    cache_lookup: Callable[[str], str | None],
    cache_store: Callable[[str, dict], None],
    cache_key_of: Callable[[dict], str],
) -> Callable[[dict], Coroutine[Any, Any, dict]]:
    """Return an async evaluator that consults the cache before calling the LLM.

    Contract:
      - On cache hit: returns {"status": "cached", "error_type": None,
        "response_json": <cached_json>, "latency_ms": 0} and DOES NOT
        await llm_evaluator_async (verified by test).
      - On cache miss: awaits llm_evaluator_async(payload). When the
        underlying result is success, cache_store(cache_key, result) is
        called to persist it. Other statuses (api_failed, parse_failed,
        cancelled) are NOT cached.
      - cache_lookup / cache_store / cache_key_of are caller-injected so
        this module does not touch sqlite. The caller (e.g. WS-APP wiring)
        bridges to src/db.py and src/cache.py.

    Args:
        llm_evaluator_async: Async callable producing a result dict for a
            single payload (keys: status, error_type, response_json,
            latency_ms). Must not be invoked when the cache hits.
        cache_lookup: Callable(cache_key) -> response_json string or None.
            Receives only the cache_key — never the full payload.
        cache_store: Callable(cache_key, result_dict) -> None. Called only
            for status="success" results.
        cache_key_of: Callable(payload) -> cache_key string. The caller
            decides which payload fields participate in the key (typically
            via src.cache.compute_cache_key over persona/provider/etc.).

    Returns:
        Async callable matching the WS-JOB evaluator signature.
    """

    async def _evaluator(payload: dict) -> dict:
        cache_key = cache_key_of(payload)
        cached_json = cache_lookup(cache_key)
        if cached_json is not None:
            # CRITICAL: do NOT await the LLM evaluator on cache hit
            # (runtime cache policy).
            return {
                "status": "cached",
                "error_type": None,
                "response_json": cached_json,
                "latency_ms": 0,
            }
        result = await llm_evaluator_async(payload)
        if result.get("status") == "success" and result.get("response_json"):
            try:
                cache_store(cache_key, result)
            except Exception as exc:
                # Cache store failure must not break the evaluation.
                # Type-only safe log.
                logger.warning(
                    "cache_store failed; continuing without cache: %s",
                    type(exc).__name__,
                )
        return result

    return _evaluator
