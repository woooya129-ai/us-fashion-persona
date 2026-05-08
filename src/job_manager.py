# SPDX-License-Identifier: AGPL-3.0-only
"""Job/Run lifecycle DB operations for WS-JOB.

Implements lock-in v1.2 §5.1 (jobs), §5.2 (runs), §5.4 (run_results).

Design rules (job lifecycle contract):
- All SQL is parameterized — no string concat / f-string SQL.
- save_result + counter increment must run inside the **same transaction**
  on the **same connection** so a mid-flight failure rolls both back.
- jobs counter mapping (frozen contract — tested by test_job_manager.py):
      cached       -> cached_count++
      success      -> success_count++
      api_failed   -> failed_count++
      parse_failed -> failed_count++
      cancelled    -> no counter changes
- Timestamps are ISO 8601 UTC with explicit 'Z' suffix.
- This module never touches Streamlit, asyncio, or any LLM provider.
- Only concept_hash / persona_id / response_json (validated EvaluationResult JSON
  passed in by caller) are persisted; raw user concept text and raw provider
responses are out of scope (caller responsibility per runtime data policy).
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from src.db import CONNECTION_LEVEL_PRAGMAS

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# JobStatus semantics (frozen contract — referenced by WS-APP UI).
# Job status contract:
#   queued    = created, worker has not yet started
#   running   = start_job called, worker iterating payloads
#   completed = worker lifecycle finished normally; per-persona failures
#               (api_failed / parse_failed) DO NOT promote to 'failed'
#   cancelled = cancel was honoured cleanly; partial results saved
#   failed    = worker lifecycle itself broke (malformed payload contract,
#               save_result raising for non-per-persona reasons, evaluator
#               returning unknown status, etc.). Per-persona failures alone
#               never reach this state.
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ResultStatus = Literal["cached", "success", "api_failed", "parse_failed", "cancelled"]

_FINAL_JOB_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})
_TERMINAL_JOB_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})

# ResultStatus -> jobs counter column name (None means "no counter increment").
# Public so tests can assert the contract directly.
_STATUS_TO_COUNTER: dict[str, str | None] = {
    "cached": "cached_count",
    "success": "success_count",
    "api_failed": "failed_count",
    "parse_failed": "failed_count",
    "cancelled": None,
}

# Pre-built parameterized UPDATE statements per status. Column names are NOT
# composed at runtime, which keeps bandit B608 quiet and removes any
# dynamic-SQL surface.
_STATUS_TO_INCREMENT_SQL: dict[str, str] = {
    "cached": "UPDATE jobs SET cached_count = cached_count + 1 WHERE job_id = ?",
    "success": "UPDATE jobs SET success_count = success_count + 1 WHERE job_id = ?",
    "api_failed": "UPDATE jobs SET failed_count = failed_count + 1 WHERE job_id = ?",
    "parse_failed": "UPDATE jobs SET failed_count = failed_count + 1 WHERE job_id = ?",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    status: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    cancel_requested: bool
    total_count: int
    cached_count: int
    success_count: int
    failed_count: int


@dataclass(frozen=True)
class RunMeta:
    """All fields required by lock-in §5.2 (PM v3 §13.2 mandatory metadata)."""

    run_id: str
    job_id: str
    dataset_name: str
    dataset_revision: str
    sample_size: int
    sampling_seed: int
    provider: str
    model_name: str
    temperature: float
    prompt_version: str
    schema_version: str
    price_context_version: str
    concept_hash: str
    price_context_hash: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso8601_z() -> str:
    """ISO 8601 UTC string with 'Z' suffix and microsecond precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@contextmanager
def _write_transaction(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a single connection, BEGIN IMMEDIATE, COMMIT on success, ROLLBACK on error.

    Why BEGIN IMMEDIATE rather than relying on Python's deferred auto-BEGIN:
      - Acquires the SQLite write lock up front so concurrent writers fail-fast
        on the busy_timeout boundary instead of mid-transaction.
      - Makes the rollback path deterministic — every statement inside this
        block is part of the explicit transaction.
      - Matches the task-instructions wording ("BEGIN ... COMMIT").

    PRAGMAs from src.db.CONNECTION_LEVEL_PRAGMAS are re-applied per connection
    (foreign_keys, busy_timeout) — SQLite scopes those per-connection.
    """
    # isolation_level=None disables Python's implicit BEGIN so the explicit
    # BEGIN IMMEDIATE below is the only transaction marker.
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        for pragma in CONNECTION_LEVEL_PRAGMAS:
            conn.execute(pragma)
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            # Roll back any partial work, then propagate the original exception.
            # The connection may already be broken — suppress is intentional.
            with suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


def create_job(db_path: Path, total_count: int) -> str:
    """Create a new job in 'queued' state. Returns the new UUID v4 job_id."""
    job_id = str(uuid.uuid4())
    created_at = _utc_now_iso8601_z()
    with _write_transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, status, created_at, total_count) VALUES (?, ?, ?, ?)",
            (job_id, "queued", created_at, int(total_count)),
        )
    return job_id


def start_job(db_path: Path, job_id: str) -> None:
    """Transition queued -> running and stamp started_at.

    Raises:
        KeyError: job_id not found.
        ValueError: current status is not 'queued'.
    """
    started_at = _utc_now_iso8601_z()
    with _write_transaction(db_path) as conn:
        row = conn.execute(
            "SELECT status FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        if row[0] != "queued":
            raise ValueError(f"start_job requires status=queued, got status={row[0]!r}")
        conn.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE job_id = ?",
            (started_at, job_id),
        )


def complete_job(db_path: Path, job_id: str, final_status: JobStatus) -> None:
    """Transition running -> completed/failed/cancelled and stamp completed_at.

    Raises:
        KeyError: job_id not found.
        ValueError: current status is not 'running', or final_status is invalid.
    """
    if final_status not in _FINAL_JOB_STATUSES:
        raise ValueError(
            f"complete_job final_status must be one of "
            f"{sorted(_FINAL_JOB_STATUSES)}, got {final_status!r}"
        )
    completed_at = _utc_now_iso8601_z()
    with _write_transaction(db_path) as conn:
        row = conn.execute(
            "SELECT status FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        if row[0] != "running":
            raise ValueError(f"complete_job requires status=running, got status={row[0]!r}")
        conn.execute(
            "UPDATE jobs SET status = ?, completed_at = ? WHERE job_id = ?",
            (final_status, completed_at, job_id),
        )


def request_cancel(db_path: Path, job_id: str) -> None:
    """Set cancel_requested=1 if the job is queued or running.

    No-op for terminal statuses (completed/failed/cancelled).
    Raises KeyError if job_id is unknown.
    """
    with _write_transaction(db_path) as conn:
        row = conn.execute(
            "SELECT status FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        if row[0] in _TERMINAL_JOB_STATUSES:
            return
        conn.execute(
            "UPDATE jobs SET cancel_requested = 1 WHERE job_id = ?",
            (job_id,),
        )


def is_cancel_requested(db_path: Path, job_id: str) -> bool:
    """Return True iff cancel_requested=1. Raises KeyError if job_id is unknown.

    Read-only — opens its own short connection and does NOT take a write lock.
    """
    conn = sqlite3.connect(db_path)
    try:
        for pragma in CONNECTION_LEVEL_PRAGMAS:
            conn.execute(pragma)
        row = conn.execute(
            "SELECT cancel_requested FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyError(job_id)
    return bool(row[0])


def load_job(db_path: Path, job_id: str) -> JobRecord:
    """Read a JobRecord. Raises KeyError if job_id is unknown."""
    conn = sqlite3.connect(db_path)
    try:
        for pragma in CONNECTION_LEVEL_PRAGMAS:
            conn.execute(pragma)
        row = conn.execute(
            "SELECT job_id, status, created_at, started_at, completed_at, "
            "cancel_requested, total_count, cached_count, success_count, "
            "failed_count "
            "FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyError(job_id)
    return JobRecord(
        job_id=row[0],
        status=row[1],
        created_at=row[2],
        started_at=row[3],
        completed_at=row[4],
        cancel_requested=bool(row[5]),
        total_count=row[6],
        cached_count=row[7],
        success_count=row[8],
        failed_count=row[9],
    )


def load_job_stats(db_path: Path, job_id: str) -> JobRecord:
    """Alias for load_job — exposed under the name UI polling code uses."""
    return load_job(db_path, job_id)


# ---------------------------------------------------------------------------
# Run CRUD
# ---------------------------------------------------------------------------


def create_run(db_path: Path, meta: RunMeta) -> None:
    """Insert a runs row carrying every mandatory metadata column (lock-in §5.2).

    Raises sqlite3.IntegrityError if meta.job_id has no matching jobs row.
    """
    with _write_transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO runs ("
            "  run_id, job_id, created_at, dataset_name, dataset_revision, "
            "  sample_size, sampling_seed, provider, model_name, temperature, "
            "  prompt_version, schema_version, price_context_version, "
            "  concept_hash, price_context_hash"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                meta.run_id,
                meta.job_id,
                _utc_now_iso8601_z(),
                meta.dataset_name,
                meta.dataset_revision,
                int(meta.sample_size),
                int(meta.sampling_seed),
                meta.provider,
                meta.model_name,
                float(meta.temperature),
                meta.prompt_version,
                meta.schema_version,
                meta.price_context_version,
                meta.concept_hash,
                meta.price_context_hash,
            ),
        )


# ---------------------------------------------------------------------------
# Result + counter (single transaction)
# ---------------------------------------------------------------------------


def _increment_counter_in_conn(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
) -> None:
    """Bump the right jobs counter for ``status`` on the SAME connection.

    Looks up a frozen ``status -> SQL`` map; never composes SQL at runtime.
    Status 'cancelled' is a no-op by design (contract).
    Status outside the contract raises ValueError to fail loudly.
    """
    if status not in _STATUS_TO_COUNTER:
        raise ValueError(f"Unknown ResultStatus: {status!r}")
    sql = _STATUS_TO_INCREMENT_SQL.get(status)
    if sql is None:
        return  # 'cancelled' contributes to no counter.
    conn.execute(sql, (job_id,))


def save_result(
    db_path: Path,
    run_id: str,
    persona_id: str,
    cache_key: str | None,
    status: ResultStatus,
    error_type: str | None,
    response_json: str | None,
    latency_ms: int | None,
) -> None:
    """Persist one run_results row AND bump the matching jobs counter.

    Both writes share a single connection inside an explicit
    ``BEGIN IMMEDIATE ... COMMIT`` block. If either write raises, both are
    rolled back (transaction boundary requirement).

    PK is (run_id, persona_id) — duplicate inserts raise sqlite3.IntegrityError;
    the caller (worker.run_worker) is responsible for not retrying the same
    (run_id, persona_id).

    Raises:
        sqlite3.IntegrityError: PK duplicate, or FK on run_id / cache_key fails.
        ValueError: status is not a known ResultStatus.
    """
    if status not in _STATUS_TO_COUNTER:
        raise ValueError(f"Unknown ResultStatus: {status!r}")
    with _write_transaction(db_path) as conn:
        # Resolve job_id from the run row. Raise IntegrityError if FK is bad,
        # because PRAGMA foreign_keys=ON gives us the constraint check on the
        # later INSERT regardless, but we still need job_id to bump counters.
        row = conn.execute(
            "SELECT job_id FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise sqlite3.IntegrityError(
                f"FOREIGN KEY constraint failed: run_id={run_id!r} not in runs"
            )
        job_id: str = row[0]

        conn.execute(
            "INSERT INTO run_results "
            "(run_id, persona_id, cache_key, status, error_type, response_json, "
            "latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                persona_id,
                cache_key,
                status,
                error_type,
                response_json,
                None if latency_ms is None else int(latency_ms),
            ),
        )
        _increment_counter_in_conn(conn, job_id, status)


def increment_job_counters(
    db_path: Path,
    job_id: str,
    cached_delta: int = 0,
    success_delta: int = 0,
    failed_delta: int = 0,
) -> None:
    """Direct counter bump. Internal-by-default; exposed for tests.

    All three deltas are applied in a single transaction so a partial bump
    is impossible. Use save_result() for the normal path.
    """
    with _write_transaction(db_path) as conn:
        if cached_delta:
            conn.execute(
                "UPDATE jobs SET cached_count = cached_count + ? WHERE job_id = ?",
                (int(cached_delta), job_id),
            )
        if success_delta:
            conn.execute(
                "UPDATE jobs SET success_count = success_count + ? WHERE job_id = ?",
                (int(success_delta), job_id),
            )
        if failed_delta:
            conn.execute(
                "UPDATE jobs SET failed_count = failed_count + ? WHERE job_id = ?",
                (int(failed_delta), job_id),
            )
