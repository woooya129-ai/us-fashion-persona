"""Tests for src/job_manager.py — WS-JOB job/run lifecycle DB operations.

All tests use tmp_path SQLite — never the real cache.db.
No network, no real LLM, marked no_network.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import pytest

from src.db import get_connection, init_db
from src.job_manager import (
    _STATUS_TO_COUNTER,
    JobRecord,
    RunMeta,
    complete_job,
    create_job,
    create_run,
    increment_job_counters,
    is_cancel_requested,
    load_job,
    load_job_stats,
    request_cancel,
    save_result,
    start_job,
)

pytestmark = pytest.mark.no_network

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_ISO8601_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _run_meta(job_id: str, run_id: str | None = None) -> RunMeta:
    return RunMeta(
        run_id=run_id or str(uuid.uuid4()),
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
        dataset_split="train",
        matched_count_before_sample=42,
        sampling_strategy="filter_then_seeded_reservoir",
        filter_summary="no filters",
    )


def _setup_run(db: Path) -> tuple[str, str]:
    """Create job + start + create_run; return (job_id, run_id)."""
    job_id = create_job(db, total_count=10)
    start_job(db, job_id)
    meta = _run_meta(job_id)
    create_run(db, meta)
    return job_id, meta.run_id


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


def test_create_job_returns_uuid_v4(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=10)
    assert _UUID4_RE.match(job_id), f"not a UUID v4: {job_id!r}"


def test_create_job_status_queued(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=3)
    record = load_job(db, job_id)
    assert record.status == "queued"


def test_create_job_total_count_stored(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=99)
    record = load_job(db, job_id)
    assert record.total_count == 99


def test_create_job_created_at_is_iso8601_utc_z(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    record = load_job(db, job_id)
    assert _ISO8601_Z_RE.match(record.created_at), f"bad timestamp: {record.created_at!r}"


def test_create_job_initial_counters_are_zero(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=5)
    record = load_job(db, job_id)
    assert record.cached_count == 0
    assert record.success_count == 0
    assert record.failed_count == 0
    assert record.cancel_requested is False
    assert record.started_at is None
    assert record.completed_at is None


# ---------------------------------------------------------------------------
# start_job
# ---------------------------------------------------------------------------


def test_start_job_queued_to_running(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    assert load_job(db, job_id).status == "running"


def test_start_job_records_started_at(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    record = load_job(db, job_id)
    assert record.started_at is not None
    assert _ISO8601_Z_RE.match(record.started_at)


def test_start_job_raises_value_error_if_not_queued(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    with pytest.raises(ValueError, match="queued"):
        start_job(db, job_id)


def test_start_job_raises_key_error_for_unknown_id(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with pytest.raises(KeyError):
        start_job(db, "nonexistent-job")


# ---------------------------------------------------------------------------
# complete_job
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("final_status", ["completed", "failed", "cancelled"])
def test_complete_job_running_to_each_final_status(tmp_path: Path, final_status: str) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    complete_job(db, job_id, final_status)  # type: ignore[arg-type]
    assert load_job(db, job_id).status == final_status


def test_complete_job_records_completed_at(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    complete_job(db, job_id, "completed")
    record = load_job(db, job_id)
    assert record.completed_at is not None
    assert _ISO8601_Z_RE.match(record.completed_at)


def test_complete_job_raises_value_error_if_not_running(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    with pytest.raises(ValueError, match="running"):
        complete_job(db, job_id, "completed")


def test_complete_job_raises_value_error_on_invalid_final_status(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    with pytest.raises(ValueError):
        complete_job(db, job_id, "queued")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        complete_job(db, job_id, "running")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# request_cancel / is_cancel_requested
# ---------------------------------------------------------------------------


def test_request_cancel_sets_flag_on_queued(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    request_cancel(db, job_id)
    assert is_cancel_requested(db, job_id) is True


def test_request_cancel_sets_flag_on_running(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    request_cancel(db, job_id)
    assert is_cancel_requested(db, job_id) is True


@pytest.mark.parametrize("final_status", ["completed", "failed", "cancelled"])
def test_request_cancel_is_noop_on_terminal_status(tmp_path: Path, final_status: str) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    start_job(db, job_id)
    complete_job(db, job_id, final_status)  # type: ignore[arg-type]
    request_cancel(db, job_id)  # must not raise
    assert is_cancel_requested(db, job_id) is False


def test_request_cancel_raises_key_error_for_unknown_job(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with pytest.raises(KeyError):
        request_cancel(db, "nonexistent-job")


def test_is_cancel_requested_false_by_default(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    assert is_cancel_requested(db, job_id) is False


def test_is_cancel_requested_raises_key_error_for_unknown(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with pytest.raises(KeyError):
        is_cancel_requested(db, "nonexistent-job")


# ---------------------------------------------------------------------------
# load_job / load_job_stats
# ---------------------------------------------------------------------------


def test_load_job_raises_key_error_when_missing(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with pytest.raises(KeyError):
        load_job(db, "nonexistent-job")


def test_load_job_stats_is_alias_of_load_job(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=7)
    assert load_job(db, job_id) == load_job_stats(db, job_id)


def test_load_job_returns_job_record_dataclass(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    record = load_job(db, job_id)
    assert isinstance(record, JobRecord)


# ---------------------------------------------------------------------------
# create_run
# ---------------------------------------------------------------------------


def test_create_run_inserts_all_lockin_columns(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    meta = _run_meta(job_id)
    create_run(db, meta)

    with get_connection(db) as conn:
        row = conn.execute(
            "SELECT run_id, job_id, dataset_name, dataset_revision, "
            "sample_size, sampling_seed, provider, model_name, temperature, "
            "prompt_version, schema_version, price_context_version, "
            "concept_hash, price_context_hash, created_at, dataset_split, "
            "matched_count_before_sample, sampling_strategy, filter_summary "
            "FROM runs WHERE run_id = ?",
            (meta.run_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == meta.run_id
    assert row[1] == meta.job_id
    assert row[2] == meta.dataset_name
    assert row[3] == meta.dataset_revision
    assert row[4] == meta.sample_size
    assert row[5] == meta.sampling_seed
    assert row[6] == meta.provider
    assert row[7] == meta.model_name
    assert row[8] == pytest.approx(meta.temperature)
    assert row[9] == meta.prompt_version
    assert row[10] == meta.schema_version
    assert row[11] == meta.price_context_version
    assert row[12] == meta.concept_hash
    assert row[13] == meta.price_context_hash
    assert _ISO8601_Z_RE.match(row[14])
    assert row[15] == meta.dataset_split
    assert row[16] == meta.matched_count_before_sample
    assert row[17] == meta.sampling_strategy
    assert row[18] == meta.filter_summary


def test_create_run_raises_integrity_error_on_bad_job_fk(tmp_path: Path) -> None:
    db = _db(tmp_path)
    meta = _run_meta("no-such-job")
    with pytest.raises(sqlite3.IntegrityError):
        create_run(db, meta)


# ---------------------------------------------------------------------------
# save_result — counter mapping per ResultStatus
# ---------------------------------------------------------------------------


def test_save_result_cached_increments_cached_count(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    save_result(db, run_id, "p001", None, "cached", None, '{"x":1}', 10)
    record = load_job(db, job_id)
    assert record.cached_count == 1
    assert record.success_count == 0
    assert record.failed_count == 0


def test_save_result_success_increments_success_count(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    save_result(db, run_id, "p001", None, "success", None, '{"y":2}', 50)
    record = load_job(db, job_id)
    assert record.success_count == 1
    assert record.cached_count == 0
    assert record.failed_count == 0


def test_save_result_api_failed_increments_failed_count(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    save_result(db, run_id, "p001", None, "api_failed", "TimeoutError", None, None)
    record = load_job(db, job_id)
    assert record.failed_count == 1
    assert record.success_count == 0
    assert record.cached_count == 0


def test_save_result_parse_failed_increments_failed_count(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    save_result(db, run_id, "p001", None, "parse_failed", "JSONDecodeError", None, None)
    record = load_job(db, job_id)
    assert record.failed_count == 1
    assert record.success_count == 0
    assert record.cached_count == 0


def test_save_result_cancelled_does_not_increment_any_counter(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    save_result(db, run_id, "p001", None, "cancelled", None, None, None)
    record = load_job(db, job_id)
    assert record.cached_count == 0
    assert record.success_count == 0
    assert record.failed_count == 0


def test_save_result_raises_value_error_on_unknown_status(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _, run_id = _setup_run(db)
    with pytest.raises(ValueError, match="ResultStatus"):
        save_result(
            db,
            run_id,
            "p001",
            None,
            "totally_invalid",
            None,
            None,
            None,  # type: ignore[arg-type]
        )


def test_save_result_pk_duplicate_raises_integrity_error(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _, run_id = _setup_run(db)
    save_result(db, run_id, "p001", None, "success", None, None, None)
    with pytest.raises(sqlite3.IntegrityError):
        save_result(db, run_id, "p001", None, "success", None, None, None)


def test_save_result_bad_run_id_fk_raises_integrity_error(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        save_result(db, "no-such-run", "p001", None, "success", None, None, None)


def test_save_result_bad_cache_key_fk_raises_integrity_error(
    tmp_path: Path,
) -> None:
    """run_results.cache_key references llm_cache.cache_key."""
    db = _db(tmp_path)
    _, run_id = _setup_run(db)
    with pytest.raises(sqlite3.IntegrityError):
        save_result(db, run_id, "p001", "no-such-cache-key", "cached", None, '{"x":1}', 5)


def test_save_result_persists_all_columns(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _, run_id = _setup_run(db)
    save_result(db, run_id, "p042", None, "success", None, '{"sentiment":"positive"}', 123)
    with get_connection(db) as conn:
        row = conn.execute(
            "SELECT run_id, persona_id, cache_key, status, error_type, "
            "response_json, latency_ms FROM run_results WHERE run_id = ? "
            "AND persona_id = ?",
            (run_id, "p042"),
        ).fetchone()
    assert row == (
        run_id,
        "p042",
        None,
        "success",
        None,
        '{"sentiment":"positive"}',
        123,
    )


# ---------------------------------------------------------------------------
# save_result — transaction rollback (transaction boundary)
# ---------------------------------------------------------------------------


def test_save_result_rolls_back_when_counter_update_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the counter UPDATE raises after the INSERT, BOTH must be rolled back.

    Forces a failure inside _increment_counter_in_conn AFTER the run_results
    INSERT has been issued. Verifies via a fresh connection that:
        - run_results has no row for this (run_id, persona_id)
        - jobs counters are still 0
    """
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)

    import src.job_manager as jm

    def boom(conn, job_id, status):  # noqa: ARG001
        raise RuntimeError("simulated counter failure")

    monkeypatch.setattr(jm, "_increment_counter_in_conn", boom)

    with pytest.raises(RuntimeError, match="simulated counter failure"):
        save_result(db, run_id, "p_rollback", None, "success", None, "{}", 1)

    # New connection — verify rollback was committed nowhere.
    with get_connection(db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM run_results WHERE run_id = ? AND persona_id = ?",
            (run_id, "p_rollback"),
        ).fetchone()
        assert row[0] == 0, "run_results row was NOT rolled back"

    record = load_job(db, job_id)
    assert record.success_count == 0
    assert record.cached_count == 0
    assert record.failed_count == 0


def test_save_result_rolls_back_on_pk_collision_no_phantom_counter(
    tmp_path: Path,
) -> None:
    """A duplicate-PK INSERT must not leave the counter incremented twice."""
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    save_result(db, run_id, "p_dup", None, "success", None, '{"a":1}', 5)
    record_after_first = load_job(db, job_id)
    assert record_after_first.success_count == 1

    with pytest.raises(sqlite3.IntegrityError):
        save_result(db, run_id, "p_dup", None, "success", None, '{"a":2}', 6)

    record_after_dup = load_job(db, job_id)
    # Counter must still be exactly 1 — duplicate insert was rolled back.
    assert record_after_dup.success_count == 1


# ---------------------------------------------------------------------------
# increment_job_counters (public for tests)
# ---------------------------------------------------------------------------


def test_increment_job_counters_applies_all_three_deltas(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=10)
    increment_job_counters(db, job_id, cached_delta=2, success_delta=3, failed_delta=1)
    record = load_job(db, job_id)
    assert record.cached_count == 2
    assert record.success_count == 3
    assert record.failed_count == 1


def test_increment_job_counters_zero_deltas_is_noop(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = create_job(db, total_count=1)
    increment_job_counters(db, job_id)
    record = load_job(db, job_id)
    assert record.cached_count == 0
    assert record.success_count == 0
    assert record.failed_count == 0


# ---------------------------------------------------------------------------
# Counter mapping contract (frozen)
# ---------------------------------------------------------------------------


def test_status_to_counter_mapping_contract() -> None:
    """ResultStatus -> counter mapping is the single source of truth."""
    assert _STATUS_TO_COUNTER == {
        "cached": "cached_count",
        "success": "success_count",
        "api_failed": "failed_count",
        "parse_failed": "failed_count",
        "cancelled": None,
    }


# ---------------------------------------------------------------------------
# DB concurrency — best-effort given Python sqlite3 + WAL
# ---------------------------------------------------------------------------


def test_concurrent_save_result_preserves_counters(tmp_path: Path) -> None:
    """Two threads concurrently insert different (run_id, persona_id) rows.

    With WAL + busy_timeout=5000 this must NOT lose a counter increment and
    must NOT raise SQLITE_BUSY (the busy_timeout absorbs the contention).
    """
    db = _db(tmp_path)
    job_id, run_id = _setup_run(db)
    n_per_thread = 10
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def worker(prefix: str) -> None:
        try:
            barrier.wait(timeout=5.0)
            for i in range(n_per_thread):
                save_result(
                    db,
                    run_id,
                    f"{prefix}_{i:03d}",
                    None,
                    "success",
                    None,
                    None,
                    1,
                )
        except Exception as exc:  # capture, do not crash the test runner
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=("a",), daemon=False)
    t2 = threading.Thread(target=worker, args=("b",), daemon=False)
    t1.start()
    t2.start()
    t1.join(timeout=30.0)
    t2.join(timeout=30.0)

    assert not t1.is_alive() and not t2.is_alive(), "thread timed out"
    assert errors == [], f"concurrent save_result failed: {errors!r}"

    record = load_job(db, job_id)
    assert record.success_count == 2 * n_per_thread, (
        f"counter lost rows: got {record.success_count}, expected {2 * n_per_thread}"
    )

    # Sanity: every row landed.
    with get_connection(db) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM run_results WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
    assert total == 2 * n_per_thread


def test_concurrent_writers_dont_deadlock(tmp_path: Path) -> None:
    """A second writer arriving while the first holds the write lock must
    eventually proceed (busy_timeout absorbs the wait), not deadlock."""
    db = _db(tmp_path)
    job_id = create_job(db, total_count=2)
    finished = threading.Event()

    def slow_writer() -> None:
        # increment one counter at a time to force two write transactions
        increment_job_counters(db, job_id, cached_delta=1)
        time.sleep(0.05)
        increment_job_counters(db, job_id, success_delta=1)
        finished.set()

    def fast_writer() -> None:
        increment_job_counters(db, job_id, failed_delta=1)

    t1 = threading.Thread(target=slow_writer, daemon=False)
    t2 = threading.Thread(target=fast_writer, daemon=False)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert finished.is_set(), "slow writer never finished"
    record = load_job(db, job_id)
    assert record.cached_count == 1
    assert record.success_count == 1
    assert record.failed_count == 1


# ---------------------------------------------------------------------------
# Source-level guards — parameterized SQL only, no streamlit/asyncio.run
# ---------------------------------------------------------------------------


def _read_source(name: str) -> str:
    src = Path(__file__).parent.parent / "src" / name
    return src.read_text(encoding="utf-8")


def test_job_manager_uses_only_parameterized_sql() -> None:
    source = _read_source("job_manager.py")
    # All SQL strings must be plain literals or .format()-free constants.
    # f-string SQL is a strict no.
    forbidden_patterns = [
        re.compile(r'f"[^"\n]*\bFROM\b', re.IGNORECASE),
        re.compile(r"f'[^'\n]*\bFROM\b", re.IGNORECASE),
        re.compile(r'f"[^"\n]*\bINSERT\b', re.IGNORECASE),
        re.compile(r"f'[^'\n]*\bINSERT\b", re.IGNORECASE),
        re.compile(r'f"[^"\n]*\bUPDATE\b', re.IGNORECASE),
        re.compile(r"f'[^'\n]*\bUPDATE\b", re.IGNORECASE),
        re.compile(r"%s.*FROM", re.IGNORECASE),
        re.compile(r"\.format\([^)]*\)\.execute", re.IGNORECASE),
    ]
    for pat in forbidden_patterns:
        match = pat.search(source)
        assert match is None, (
            f"forbidden dynamic-SQL pattern {pat.pattern!r} matched: "
            f"{match.group(0) if match else ''!r}"
        )


def test_job_manager_does_not_import_streamlit() -> None:
    """Check IMPORT statements only; the word may legitimately appear in
    docstrings explaining the no-streamlit rule (PM v3 §11.2)."""
    source = _read_source("job_manager.py")
    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert re.search(r"^\s*import streamlit\b", source, re.MULTILINE) is None
    assert re.search(r"\bst\.[a-zA-Z_]", source) is None


def test_job_manager_does_not_use_asyncio_run() -> None:
    source = _read_source("job_manager.py")
    assert "asyncio.run" not in source
    assert "import asyncio" not in source


def test_job_manager_has_no_subprocess_eval_exec_pickle() -> None:
    source = _read_source("job_manager.py")
    assert "subprocess" not in source
    assert "pickle" not in source
    # eval(/exec( as function calls — the words appear in 'execute' so
    # we look for the call form specifically.
    assert "eval(" not in source
    assert " exec(" not in source
    assert "\nexec(" not in source
