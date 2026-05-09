"""Tests for src/worker.py — WS-JOB worker thread.

All tests use tmp_path SQLite + the sync fake evaluator. No real LLM,
no network, no async. Marked no_network.
"""

from __future__ import annotations

import asyncio
import re
import threading
import uuid
from pathlib import Path

import pytest

from src.db import get_connection, init_db
from src.job_manager import (
    RunMeta,
    create_job,
    load_job,
    request_cancel,
)
from src.worker import WorkerInput, run_worker, start_worker_thread
from tests.fixtures.fake_evaluator import (
    make_blocking_fake_evaluator,
    make_fake_evaluator,
)

pytestmark = pytest.mark.no_network

# Generous join timeout so Windows runners don't flake.
_THREAD_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _run_meta(job_id: str) -> RunMeta:
    return RunMeta(
        run_id=str(uuid.uuid4()),
        job_id=job_id,
        dataset_name="test-dataset",
        dataset_revision="abc123",
        sample_size=5,
        sampling_seed=42,
        provider="openai",
        model_name="gpt-4o-mini",
        temperature=0.3,
        prompt_version="concept_eval_ko_v0_3",
        schema_version="eval_v0_1",
        price_context_version="bls_2024_apparel_services_annual_v1",
        concept_hash="deadbeef",
        price_context_hash="cafebabe",
    )


def _payloads(persona_ids: list[str]) -> list[dict]:
    return [{"persona_id": pid, "cache_key": None} for pid in persona_ids]


def _worker_input(
    db: Path,
    job_id: str,
    persona_ids: list[str],
    evaluator,
) -> WorkerInput:
    return WorkerInput(
        db_path=db,
        job_id=job_id,
        run_meta=_run_meta(job_id),
        persona_payloads=_payloads(persona_ids),
        evaluator=evaluator,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_run_worker_all_success(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p001", "p002", "p003", "p004", "p005"]
    scenarios = {
        pid: {
            "status": "success",
            "error_type": None,
            "response_json": '{"ok":1}',
            "latency_ms": 50,
        }
        for pid in personas
    }
    evaluator = make_fake_evaluator(scenarios)
    job_id = create_job(db, total_count=len(personas))
    run_worker(_worker_input(db, job_id, personas, evaluator))

    record = load_job(db, job_id)
    assert record.status == "completed"
    assert record.success_count == 5
    assert record.cached_count == 0
    assert record.failed_count == 0
    assert record.started_at is not None
    assert record.completed_at is not None


def test_run_worker_mixed_cached_and_success(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p_cached", "p_live"]
    scenarios = {
        "p_cached": {
            "status": "cached",
            "error_type": None,
            "response_json": '{"c":1}',
            "latency_ms": 5,
        },
        "p_live": {
            "status": "success",
            "error_type": None,
            "response_json": '{"s":1}',
            "latency_ms": 50,
        },
    }
    evaluator = make_fake_evaluator(scenarios)
    job_id = create_job(db, total_count=2)
    run_worker(_worker_input(db, job_id, personas, evaluator))

    record = load_job(db, job_id)
    assert record.cached_count == 1
    assert record.success_count == 1
    assert record.status == "completed"


def test_run_worker_persists_explicit_cache_key_when_cache_row_exists(tmp_path: Path) -> None:
    db = _db(tmp_path)
    cache_key = "c" * 64
    with get_connection(db) as conn:
        conn.execute(
            "INSERT INTO llm_cache ("
            "cache_key, persona_id, concept_hash, price_context_hash, provider, "
            "model_name, temperature, prompt_version, schema_version, "
            "price_context_version, response_json, raw_response_path, "
            "input_tokens_actual, output_tokens_actual, cost_actual_usd, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cache_key,
                "p001",
                "c" * 64,
                "p" * 64,
                "openai",
                "gpt-4o-mini",
                0.3,
                "concept_eval_ko_v0_3",
                "eval_v0_1",
                "bls_2024_apparel_services_annual_v1",
                '{"ok":1}',
                None,
                None,
                None,
                None,
                "2026-05-07T00:00:00.000000Z",
            ),
        )
        conn.commit()

    def evaluator(_payload: dict) -> dict:
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"ok":1}',
            "latency_ms": 1,
            "cache_key": cache_key,
        }

    job_id = create_job(db, total_count=1)
    run_worker(
        WorkerInput(
            db_path=db,
            job_id=job_id,
            run_meta=_run_meta(job_id),
            persona_payloads=[{"persona_id": "p001", "_cache_key": cache_key}],
            evaluator=evaluator,
        )
    )

    with get_connection(db) as conn:
        row = conn.execute("SELECT cache_key FROM run_results WHERE persona_id = 'p001'").fetchone()

    assert row[0] == cache_key


@pytest.mark.parametrize("payload_key", ["_cache_key", "cache_key"])
def test_run_worker_does_not_promote_payload_cache_key_without_explicit_result(
    tmp_path: Path,
    payload_key: str,
) -> None:
    db = _db(tmp_path)
    cache_key = "m" * 64

    def evaluator(_payload: dict) -> dict:
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"ok":1}',
            "latency_ms": 1,
        }

    job_id = create_job(db, total_count=1)
    run_worker(
        WorkerInput(
            db_path=db,
            job_id=job_id,
            run_meta=_run_meta(job_id),
            persona_payloads=[{"persona_id": "p001", payload_key: cache_key}],
            evaluator=evaluator,
        )
    )

    with get_connection(db) as conn:
        row = conn.execute(
            "SELECT status, cache_key FROM run_results WHERE persona_id = 'p001'"
        ).fetchone()

    record = load_job(db, job_id)
    assert record.status == "completed"
    assert record.success_count == 1
    assert row == ("success", None)


def test_run_worker_async_evaluator_uses_configured_concurrency(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p001", "p002", "p003", "p004"]
    active = 0
    peak = 0
    lock = threading.Lock()

    async def evaluator(_payload: dict) -> dict:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        with lock:
            active -= 1
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"ok":1}',
            "latency_ms": 1,
        }

    job_id = create_job(db, total_count=len(personas))
    run_worker(
        WorkerInput(
            db_path=db,
            job_id=job_id,
            run_meta=_run_meta(job_id),
            persona_payloads=[{"persona_id": pid} for pid in personas],
            evaluator_async=evaluator,
            concurrency=2,
        )
    )

    record = load_job(db, job_id)
    assert record.status == "completed"
    assert record.success_count == 4
    assert peak == 2


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_run_worker_evaluator_exception_becomes_api_failed(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p_boom", "p_ok"]
    scenarios = {
        "p_boom": {"raise": True, "exc_type": RuntimeError, "message": "boom"},
        "p_ok": {
            "status": "success",
            "error_type": None,
            "response_json": '{"ok":1}',
            "latency_ms": 10,
        },
    }
    evaluator = make_fake_evaluator(scenarios)
    job_id = create_job(db, total_count=2)
    run_worker(_worker_input(db, job_id, personas, evaluator))

    record = load_job(db, job_id)
    assert record.failed_count == 1
    assert record.success_count == 1
    # 설계상: per-persona 실패는 job 최종 status 를 failed 로 올리지 않는다.
    assert record.status == "completed"


def test_run_worker_parse_failed_increments_failed_count(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p001"]
    scenarios = {
        "p001": {
            "status": "parse_failed",
            "error_type": "JSONDecodeError",
            "response_json": None,
            "latency_ms": 20,
        },
    }
    evaluator = make_fake_evaluator(scenarios)
    job_id = create_job(db, total_count=1)
    run_worker(_worker_input(db, job_id, personas, evaluator))

    record = load_job(db, job_id)
    assert record.failed_count == 1
    assert record.status == "completed"


def test_run_worker_continues_after_evaluator_exception(tmp_path: Path) -> None:
    """A mid-list exception must not abort the worker — others must still run."""
    db = _db(tmp_path)
    personas = ["p_a", "p_boom", "p_c"]
    scenarios = {
        "p_a": {
            "status": "success",
            "error_type": None,
            "response_json": None,
            "latency_ms": 5,
        },
        "p_boom": {"raise": True, "exc_type": ValueError, "message": "x"},
        "p_c": {
            "status": "success",
            "error_type": None,
            "response_json": None,
            "latency_ms": 5,
        },
    }
    evaluator = make_fake_evaluator(scenarios)
    job_id = create_job(db, total_count=3)
    run_worker(_worker_input(db, job_id, personas, evaluator))

    record = load_job(db, job_id)
    assert record.success_count == 2
    assert record.failed_count == 1
    assert record.status == "completed"


# ---------------------------------------------------------------------------
# Cancel scenarios — partial-result preservation
# ---------------------------------------------------------------------------


def test_run_worker_cancel_during_processing_saves_partial_results(
    tmp_path: Path,
) -> None:
    """Block inside p001's evaluator, request_cancel from another thread,
    then release. p001's result must persist; p002/p003 must not run.
    """
    db = _db(tmp_path)
    personas = ["p001", "p002", "p003"]
    started = threading.Event()
    proceed = threading.Event()

    scenarios = {
        pid: {
            "status": "success",
            "error_type": None,
            "response_json": None,
            "latency_ms": 5,
        }
        for pid in personas
    }
    evaluator = make_blocking_fake_evaluator(
        scenarios=scenarios,
        started_event=started,
        proceed_event=proceed,
        trigger_persona_id="p001",
    )
    job_id = create_job(db, total_count=3)

    def _run() -> None:
        run_worker(_worker_input(db, job_id, personas, evaluator))

    t = threading.Thread(target=_run, daemon=False)
    t.start()
    assert started.wait(timeout=_THREAD_TIMEOUT), "evaluator never started"
    request_cancel(db, job_id)
    proceed.set()
    t.join(timeout=_THREAD_TIMEOUT)
    assert not t.is_alive(), "worker thread did not finish in time"

    record = load_job(db, job_id)
    assert record.status == "cancelled"
    # p001 was already in flight when cancel arrived — its result IS saved.
    assert record.success_count == 1
    # p002, p003 are NOT processed — total processed must be < total_count.
    processed = record.success_count + record.failed_count + record.cached_count
    assert processed == 1
    assert processed < record.total_count


def test_run_worker_cancel_before_start_yields_cancelled_status(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    personas = ["p001", "p002"]
    scenarios = {
        pid: {
            "status": "success",
            "error_type": None,
            "response_json": None,
            "latency_ms": 5,
        }
        for pid in personas
    }
    evaluator = make_fake_evaluator(scenarios)
    job_id = create_job(db, total_count=2)
    request_cancel(db, job_id)

    run_worker(_worker_input(db, job_id, personas, evaluator))

    record = load_job(db, job_id)
    assert record.status == "cancelled"
    # No persona ever executed.
    assert record.success_count == 0
    assert record.failed_count == 0
    assert record.cached_count == 0


# ---------------------------------------------------------------------------
# start_worker_thread
# ---------------------------------------------------------------------------


def test_start_worker_thread_returns_thread_object(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p001"]
    evaluator = make_fake_evaluator(
        {
            "p001": {
                "status": "success",
                "error_type": None,
                "response_json": None,
                "latency_ms": 1,
            }
        }
    )
    job_id = create_job(db, total_count=1)
    t = start_worker_thread(_worker_input(db, job_id, personas, evaluator))
    assert isinstance(t, threading.Thread)
    t.join(timeout=_THREAD_TIMEOUT)
    assert not t.is_alive()


def test_start_worker_thread_is_not_daemon(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p001"]
    evaluator = make_fake_evaluator(
        {
            "p001": {
                "status": "success",
                "error_type": None,
                "response_json": None,
                "latency_ms": 1,
            }
        }
    )
    job_id = create_job(db, total_count=1)
    t = start_worker_thread(_worker_input(db, job_id, personas, evaluator))
    assert t.daemon is False
    t.join(timeout=_THREAD_TIMEOUT)


def test_start_worker_thread_completes_job_after_join(tmp_path: Path) -> None:
    db = _db(tmp_path)
    personas = ["p001", "p002"]
    evaluator = make_fake_evaluator(
        {
            "p001": {
                "status": "success",
                "error_type": None,
                "response_json": None,
                "latency_ms": 1,
            },
            "p002": {
                "status": "cached",
                "error_type": None,
                "response_json": None,
                "latency_ms": 1,
            },
        }
    )
    job_id = create_job(db, total_count=2)
    t = start_worker_thread(_worker_input(db, job_id, personas, evaluator))
    t.join(timeout=_THREAD_TIMEOUT)

    record = load_job(db, job_id)
    assert record.status == "completed"
    assert record.success_count == 1
    assert record.cached_count == 1


# ---------------------------------------------------------------------------
# Defensive checks on payload / evaluator-result shape
# ---------------------------------------------------------------------------


def test_run_worker_rejects_payload_missing_persona_id(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    bad = WorkerInput(
        db_path=db,
        job_id=job_id,
        run_meta=_run_meta(job_id),
        persona_payloads=[{"cache_key": None}],  # no persona_id
        evaluator=make_fake_evaluator({}),
    )
    with pytest.raises(KeyError, match="persona_id"):
        run_worker(bad)


def test_run_worker_rejects_evaluator_returning_non_dict(tmp_path: Path) -> None:
    """Malformed evaluator output is a lifecycle contract failure."""
    db = _db(tmp_path)
    personas = ["p001"]

    def bad_evaluator(_payload: dict) -> dict:
        return "not-a-dict"  # type: ignore[return-value]

    job_id = create_job(db, total_count=1)
    with pytest.raises(TypeError, match="evaluator must return a dict"):
        run_worker(_worker_input(db, job_id, personas, bad_evaluator))

    record = load_job(db, job_id)
    assert record.status == "failed"
    assert record.completed_at is not None


def test_run_worker_rejects_evaluator_result_missing_status(
    tmp_path: Path,
) -> None:
    """Missing status is a lifecycle contract failure, not api_failed."""
    db = _db(tmp_path)
    personas = ["p001"]

    def bad_evaluator(_payload: dict) -> dict:
        return {"error_type": None, "response_json": None, "latency_ms": 10}

    job_id = create_job(db, total_count=1)
    with pytest.raises(TypeError, match="missing required key 'status'"):
        run_worker(_worker_input(db, job_id, personas, bad_evaluator))

    record = load_job(db, job_id)
    assert record.status == "failed"
    assert record.completed_at is not None


# ---------------------------------------------------------------------------
# Lifecycle finalization (payload / evaluator contract edge cases)
#
# A job that has been started MUST always reach a terminal state. Per-persona
# evaluator failures stay 'api_failed' inside completed/cancelled jobs, but
# lifecycle-level failures (malformed payload contract, malformed evaluator
# output, unknown status, save_result raising for FK/contract reasons) must
# close the job as 'failed' AND re-raise the original exception so the
# calling thread / test can observe it.
# ---------------------------------------------------------------------------


def test_run_worker_payload_missing_persona_id_marks_job_failed(
    tmp_path: Path,
) -> None:
    """Missing persona_id in payload: job must close as failed."""
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    bad = WorkerInput(
        db_path=db,
        job_id=job_id,
        run_meta=_run_meta(job_id),
        persona_payloads=[{"cache_key": None}],  # no persona_id
        evaluator=make_fake_evaluator({}),
    )
    with pytest.raises(KeyError, match="persona_id"):
        run_worker(bad)

    # Even though the original exception propagates, the job must NOT be
    # left stuck in 'running'. WS-APP polling depends on this terminal state.
    record = load_job(db, job_id)
    assert record.status == "failed"
    assert record.completed_at is not None


def test_run_worker_invalid_evaluator_status_marks_job_failed(
    tmp_path: Path,
) -> None:
    """Unknown ResultStatus from evaluator: lifecycle failure, job must be 'failed'."""
    db = _db(tmp_path)
    personas = ["p001"]

    def evaluator_with_bad_status(_payload: dict) -> dict:
        return {
            "status": "bogus_status",  # not in ResultStatus literal
            "error_type": None,
            "response_json": None,
            "latency_ms": 10,
        }

    job_id = create_job(db, total_count=1)
    with pytest.raises(ValueError, match="status"):
        run_worker(_worker_input(db, job_id, personas, evaluator_with_bad_status))

    record = load_job(db, job_id)
    assert record.status == "failed"
    assert record.completed_at is not None


def test_run_worker_save_result_failure_marks_job_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If save_result raises for a non-per-persona reason, job must still close as 'failed'."""
    db = _db(tmp_path)
    personas = ["p001"]

    def good_evaluator(_payload: dict) -> dict:
        return {
            "status": "success",
            "error_type": None,
            "response_json": '{"persona_id": "p001"}',
            "latency_ms": 10,
        }

    # Patch save_result on the worker module's bound reference so that the
    # first call raises a synthetic IntegrityError simulating a DB-level
    # lifecycle failure (e.g. FK breakage that the worker can't recover from).
    import sqlite3

    import src.worker as worker_module

    def exploding_save_result(**_kwargs: object) -> None:
        raise sqlite3.IntegrityError("simulated FK violation")

    monkeypatch.setattr(worker_module, "save_result", exploding_save_result)

    job_id = create_job(db, total_count=1)
    with pytest.raises(sqlite3.IntegrityError, match="simulated FK violation"):
        run_worker(_worker_input(db, job_id, personas, good_evaluator))

    record = load_job(db, job_id)
    assert record.status == "failed"
    assert record.completed_at is not None


# ---------------------------------------------------------------------------
# Source-level guards — no streamlit / asyncio.run / subprocess / etc.
# ---------------------------------------------------------------------------


def _read_source(name: str) -> str:
    src = Path(__file__).parent.parent / "src" / name
    return src.read_text(encoding="utf-8")


def test_worker_does_not_import_streamlit() -> None:
    """Streamlit must never be imported from worker — any st.* call inside a
    worker thread is a PM v3 §11.2 violation. We check IMPORT statements only;
    the word may legitimately appear in docstrings explaining this rule.
    """
    source = _read_source("worker.py")
    assert "import streamlit" not in source
    assert "from streamlit" not in source
    # Catch `import streamlit as st` style and bare `st.` calls.
    assert re.search(r"^\s*import streamlit\b", source, re.MULTILINE) is None
    assert re.search(r"\bst\.[a-zA-Z_]", source) is None


def test_worker_uses_async_runner_without_defining_async_functions() -> None:
    """Worker may bridge to async_runner, but async task logic stays there."""
    source = _read_source("worker.py")
    assert "async def" not in source
    assert "run_evaluations" in source


def test_worker_does_not_use_subprocess_eval_exec_pickle() -> None:
    source = _read_source("worker.py")
    assert "subprocess" not in source
    assert "pickle" not in source
    assert "eval(" not in source
    assert " exec(" not in source
    assert "\nexec(" not in source


def test_worker_only_parameterized_sql_via_job_manager() -> None:
    """worker.py must not contain raw SQL — all DB writes go through
    src.job_manager which is itself parameterized."""
    source = _read_source("worker.py")
    sql_keywords = re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|BEGIN|COMMIT|ROLLBACK)\b",
        re.IGNORECASE,
    )
    # Allow SQL words inside docstrings/comments? Be strict — worker shouldn't
    # contain them at all. If we ever need to, route through job_manager.
    matches = sql_keywords.findall(source)
    assert matches == [], f"worker.py contains raw SQL keywords: {matches!r}"
