"""Tests for src/async_runner.py.

Verifies:
  - Semaphore-based concurrency control (PM v3 §11.5)
  - Cancellation halts new tasks while existing tasks complete (§11.7)
  - on_result exception isolation
  - make_sync_evaluator_for_worker sync interface
  - concurrency > max_concurrency → ValueError
  - make_cached_evaluator: cache hit → llm_evaluator NOT awaited (cache integration)

No real LLM calls or network activity. Async tests wrap their bodies in
asyncio.run to avoid a pytest-asyncio dependency.
"""

from __future__ import annotations

import asyncio

import pytest

from src.async_runner import (
    RunnerConfig,
    make_cached_evaluator,
    make_sync_evaluator_for_worker,
    run_evaluations,
)

pytestmark = pytest.mark.no_network


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_payloads(n: int) -> list[dict]:
    return [{"persona_id": f"p{i:03d}", "index": i} for i in range(n)]


async def _fast_evaluator(payload: dict) -> dict:
    await asyncio.sleep(0)
    return {
        "status": "success",
        "error_type": None,
        "response_json": f'{{"persona_id": "{payload["persona_id"]}"}}',
        "latency_ms": 1,
    }


async def _slow_evaluator(payload: dict) -> dict:
    await asyncio.sleep(0.05)
    return {
        "status": "success",
        "error_type": None,
        "response_json": f'{{"persona_id": "{payload["persona_id"]}"}}',
        "latency_ms": 50,
    }


async def _failing_evaluator(payload: dict) -> dict:
    raise RuntimeError("Simulated evaluator failure")


# ---------------------------------------------------------------------------
# run_evaluations — basic
# ---------------------------------------------------------------------------


def test_run_evaluations_all_results_collected():
    results: list[dict] = []

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(5),
            evaluator_async=_fast_evaluator,
            config=RunnerConfig(concurrency=5),
            on_result=lambda _payload, result: results.append(result),
        )

    _run(_inner())
    assert len(results) == 5
    assert all(r["status"] == "success" for r in results)


def test_run_evaluations_empty_payloads():
    results: list[dict] = []

    async def _inner():
        await run_evaluations(
            payloads=[],
            evaluator_async=_fast_evaluator,
            config=RunnerConfig(),
            on_result=lambda _payload, result: results.append(result),
        )

    _run(_inner())
    assert results == []


def test_run_evaluations_single_payload():
    results: list[dict] = []

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(1),
            evaluator_async=_fast_evaluator,
            config=RunnerConfig(),
            on_result=lambda _payload, result: results.append(result),
        )

    _run(_inner())
    assert len(results) == 1


# ---------------------------------------------------------------------------
# run_evaluations — concurrency control
# ---------------------------------------------------------------------------


def test_run_evaluations_concurrency_limit_obeyed():
    """With concurrency=2 and 4 slow tasks, peak concurrent executions is 2."""
    active: list[int] = []
    peak: list[int] = [0]

    async def counting_evaluator(payload: dict) -> dict:
        active.append(1)
        peak[0] = max(peak[0], len(active))
        await asyncio.sleep(0.05)
        active.pop()
        return {
            "status": "success",
            "error_type": None,
            "response_json": None,
            "latency_ms": 50,
        }

    results: list[dict] = []

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(4),
            evaluator_async=counting_evaluator,
            config=RunnerConfig(concurrency=2),
            on_result=lambda _payload, result: results.append(result),
        )

    _run(_inner())
    assert len(results) == 4
    assert peak[0] <= 2


# ---------------------------------------------------------------------------
# run_evaluations — cancellation
# ---------------------------------------------------------------------------


def test_run_evaluations_cancel_stops_new_tasks():
    """cancel_check returning True halts new task creation; existing tasks finish."""
    started: list[str] = []
    cancel_after = 2

    async def tracking_evaluator(payload: dict) -> dict:
        started.append(payload["persona_id"])
        await asyncio.sleep(0.01)
        return {
            "status": "success",
            "error_type": None,
            "response_json": None,
            "latency_ms": 10,
        }

    results: list[dict] = []

    def cancel_check() -> bool:
        return len(started) >= cancel_after

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(10),
            evaluator_async=tracking_evaluator,
            config=RunnerConfig(concurrency=1, cancel_check=cancel_check),
            on_result=lambda _payload, result: results.append(result),
        )

    _run(_inner())
    # With concurrency=1 and cancel after 2 started, far fewer than 10 results.
    assert len(results) < 10


# ---------------------------------------------------------------------------
# run_evaluations — exception isolation
# ---------------------------------------------------------------------------


def test_on_result_exception_doesnt_stop_other_tasks():
    call_count = {"n": 0}

    def flaky_on_result(payload: dict, result: dict) -> None:
        call_count["n"] += 1
        # Payload context lets us check per-persona without
        # fishing inside the result body.
        if payload.get("persona_id") == "p002":
            raise RuntimeError("on_result failure simulation")

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(5),
            evaluator_async=_fast_evaluator,
            config=RunnerConfig(concurrency=3),
            on_result=flaky_on_result,
        )

    _run(_inner())
    assert call_count["n"] == 5


def test_evaluator_failure_synthesizes_api_failed():
    results: list[dict] = []

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(3),
            evaluator_async=_failing_evaluator,
            config=RunnerConfig(),
            on_result=lambda _payload, result: results.append(result),
        )

    _run(_inner())
    assert len(results) == 3
    for r in results:
        assert r["status"] == "api_failed"
        assert r["error_type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# run_evaluations — concurrency cap enforcement
# ---------------------------------------------------------------------------


def test_run_evaluations_concurrency_exceeds_max_raises():
    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(1),
            evaluator_async=_fast_evaluator,
            config=RunnerConfig(concurrency=11, max_concurrency=10),
            on_result=lambda _p, _r: None,
        )

    with pytest.raises(ValueError, match="max_concurrency"):
        _run(_inner())


# ---------------------------------------------------------------------------
# on_result payload context
#
# WS-JOB save_result(persona_id=..., cache_key=..., ...) requires the payload
# context, not just the evaluator result body. These tests pin the contract.
# ---------------------------------------------------------------------------


def test_run_evaluations_on_result_receives_payload_context():
    """on_result must be called with (payload, result), not just (result)."""
    captured: list[tuple[dict, dict]] = []

    def capture(payload: dict, result: dict) -> None:
        captured.append((payload, result))

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(3),
            evaluator_async=_fast_evaluator,
            config=RunnerConfig(concurrency=2),
            on_result=capture,
        )

    _run(_inner())
    assert len(captured) == 3
    seen_personas = {payload["persona_id"] for payload, _ in captured}
    assert seen_personas == {"p000", "p001", "p002"}
    # Each callback gets exactly the payload dict that was processed.
    for payload, result in captured:
        assert "persona_id" in payload
        assert result["status"] == "success"


def test_run_evaluations_api_failed_result_keeps_persona_id_context():
    """When evaluator raises, the synthetic api_failed result still arrives
    paired with the original payload so save_result can be called.
    """
    captured: list[tuple[str, str]] = []

    def capture(payload: dict, result: dict) -> None:
        captured.append((payload["persona_id"], result["status"]))

    async def _inner():
        await run_evaluations(
            payloads=_make_payloads(3),
            evaluator_async=_failing_evaluator,
            config=RunnerConfig(concurrency=2),
            on_result=capture,
        )

    _run(_inner())
    assert len(captured) == 3
    persona_ids = {pid for pid, _ in captured}
    assert persona_ids == {"p000", "p001", "p002"}
    assert all(status == "api_failed" for _, status in captured)


def test_cached_evaluator_cache_hit_result_can_be_saved_by_job_contract():
    """End-to-end: make_cached_evaluator hit + run_evaluations callback can
    extract everything WS-JOB save_result needs (persona_id, cache_key,
    status, response_json).
    """
    saved: list[dict] = []

    async def llm_eval(payload: dict) -> dict:
        raise AssertionError("LLM must not be called on cache hit")

    def cache_lookup(_key: str) -> str | None:
        return '{"persona_id": "p000", "from_cache": true}'

    def cache_store(_key: str, _result: dict) -> None:
        pass

    def cache_key_of(payload: dict) -> str:
        return f"key:{payload['persona_id']}"

    cached_eval = make_cached_evaluator(llm_eval, cache_lookup, cache_store, cache_key_of)

    def save_like_ws_job(payload: dict, result: dict) -> None:
        saved.append(
            {
                "persona_id": payload["persona_id"],
                "cache_key": payload.get("cache_key"),
                "status": result["status"],
                "response_json": result["response_json"],
            }
        )

    async def _inner():
        await run_evaluations(
            payloads=[
                {"persona_id": "p000", "cache_key": "ck-000", "index": 0},
                {"persona_id": "p001", "cache_key": "ck-001", "index": 1},
            ],
            evaluator_async=cached_eval,
            config=RunnerConfig(concurrency=2),
            on_result=save_like_ws_job,
        )

    _run(_inner())
    assert len(saved) == 2
    for row in saved:
        assert row["status"] == "cached"
        assert row["persona_id"] in {"p000", "p001"}
        assert row["cache_key"] in {"ck-000", "ck-001"}
        assert row["response_json"] is not None


# ---------------------------------------------------------------------------
# make_sync_evaluator_for_worker
# ---------------------------------------------------------------------------


def test_make_sync_evaluator_returns_callable():
    sync_eval = make_sync_evaluator_for_worker(_fast_evaluator)
    assert callable(sync_eval)


def test_make_sync_evaluator_returns_correct_result():
    sync_eval = make_sync_evaluator_for_worker(_fast_evaluator)
    payload = {"persona_id": "test-sync-001", "index": 0}
    result = sync_eval(payload)
    assert result["status"] == "success"
    assert result["error_type"] is None


def test_make_sync_evaluator_handles_multiple_calls():
    sync_eval = make_sync_evaluator_for_worker(_fast_evaluator)
    for i in range(3):
        payload = {"persona_id": f"p{i:03d}", "index": i}
        result = sync_eval(payload)
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# make_cached_evaluator cache integration
#   cache hit → llm_evaluator MUST NOT be awaited (call_count == 0)
#   cache miss → llm_evaluator awaited, success → cache_store called
# ---------------------------------------------------------------------------


def test_cached_evaluator_cache_hit_skips_llm():
    """Cache hit returns status=cached and never awaits the LLM evaluator."""
    llm_call_count = {"n": 0}

    async def llm_eval(payload: dict) -> dict:
        llm_call_count["n"] += 1
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"persona_id": "p001"}',
            "latency_ms": 100,
        }

    def cache_lookup(key: str) -> str | None:
        return '{"persona_id": "p001", "from_cache": true}'

    def cache_store(key: str, result: dict) -> None:
        raise AssertionError("cache_store must not be called on cache hit")

    def cache_key_of(payload: dict) -> str:
        return f"key:{payload['persona_id']}"

    cached_eval = make_cached_evaluator(llm_eval, cache_lookup, cache_store, cache_key_of)

    async def _inner():
        return await cached_eval({"persona_id": "p001"})

    result = _run(_inner())
    assert result["status"] == "cached"
    assert result["response_json"] == '{"persona_id": "p001", "from_cache": true}'
    assert result["latency_ms"] == 0
    assert llm_call_count["n"] == 0  # CRITICAL — no LLM call on cache hit


def test_cached_evaluator_cache_miss_calls_llm_then_stores():
    """Cache miss awaits the LLM evaluator and stores success results."""
    llm_call_count = {"n": 0}
    stored: list[tuple[str, dict]] = []

    async def llm_eval(payload: dict) -> dict:
        llm_call_count["n"] += 1
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"persona_id": "p002"}',
            "latency_ms": 100,
        }

    def cache_lookup(key: str) -> str | None:
        return None  # miss

    def cache_store(key: str, result: dict) -> None:
        stored.append((key, result))

    def cache_key_of(payload: dict) -> str:
        return f"key:{payload['persona_id']}"

    cached_eval = make_cached_evaluator(llm_eval, cache_lookup, cache_store, cache_key_of)

    async def _inner():
        return await cached_eval({"persona_id": "p002"})

    result = _run(_inner())
    assert result["status"] == "success"
    assert llm_call_count["n"] == 1
    assert len(stored) == 1
    assert stored[0][0] == "key:p002"
    assert stored[0][1]["status"] == "success"


def test_cached_evaluator_does_not_store_failed_results():
    """status != success must NOT be cached."""
    stored: list[tuple[str, dict]] = []

    async def llm_eval_fail(payload: dict) -> dict:
        return {
            "status": "api_failed",
            "error_type": "ConnectionError",
            "response_json": None,
            "latency_ms": None,
        }

    cached_eval = make_cached_evaluator(
        llm_eval_fail,
        cache_lookup=lambda k: None,
        cache_store=lambda k, r: stored.append((k, r)),
        cache_key_of=lambda p: f"k:{p['persona_id']}",
    )

    async def _inner():
        return await cached_eval({"persona_id": "p003"})

    result = _run(_inner())
    assert result["status"] == "api_failed"
    assert stored == []


def test_cached_evaluator_does_not_store_parse_failed():
    stored: list[tuple[str, dict]] = []

    async def llm_eval_parse_fail(payload: dict) -> dict:
        return {
            "status": "parse_failed",
            "error_type": None,
            "response_json": None,
            "latency_ms": 100,
        }

    cached_eval = make_cached_evaluator(
        llm_eval_parse_fail,
        cache_lookup=lambda k: None,
        cache_store=lambda k, r: stored.append((k, r)),
        cache_key_of=lambda p: f"k:{p['persona_id']}",
    )

    async def _inner():
        return await cached_eval({"persona_id": "p004"})

    _run(_inner())
    assert stored == []


def test_cached_evaluator_cache_store_failure_swallowed():
    """A cache_store error must not break the evaluation."""

    async def llm_eval_ok(payload: dict) -> dict:
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"x": 1}',
            "latency_ms": 1,
        }

    def cache_store_raises(key: str, result: dict) -> None:
        raise RuntimeError("disk full")

    cached_eval = make_cached_evaluator(
        llm_eval_ok,
        cache_lookup=lambda k: None,
        cache_store=cache_store_raises,
        cache_key_of=lambda p: "k:1",
    )

    async def _inner():
        return await cached_eval({"persona_id": "p005"})

    # No exception should escape.
    result = _run(_inner())
    assert result["status"] == "success"
