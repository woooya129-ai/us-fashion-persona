# SPDX-License-Identifier: AGPL-3.0-only
"""SQLite DB 초기화 + DDL + PRAGMA 적용.

lock-in v1.2 §5.1-§5.5 구현.
모든 SQL 은 parameterized query 사용 (string concat / format 금지).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DDL_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id            TEXT PRIMARY KEY,
    status            TEXT NOT NULL CHECK (status IN
                          ('queued','running','completed','failed','cancelled')),
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    completed_at      TEXT,
    cancel_requested  INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
    total_count       INTEGER NOT NULL DEFAULT 0,
    cached_count      INTEGER NOT NULL DEFAULT 0,
    success_count     INTEGER NOT NULL DEFAULT 0,
    failed_count      INTEGER NOT NULL DEFAULT 0
)
"""

DDL_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    run_id                  TEXT PRIMARY KEY,
    job_id                  TEXT NOT NULL REFERENCES jobs(job_id),
    created_at              TEXT NOT NULL,
    dataset_name            TEXT NOT NULL,
    dataset_revision        TEXT NOT NULL,
    sample_size             INTEGER NOT NULL,
    sampling_seed           INTEGER NOT NULL,
    provider                TEXT NOT NULL,
    model_name              TEXT NOT NULL,
    temperature             REAL NOT NULL,
    prompt_version          TEXT NOT NULL,
    schema_version          TEXT NOT NULL,
    price_context_version   TEXT NOT NULL,
    concept_hash            TEXT NOT NULL,
    price_context_hash      TEXT NOT NULL
)
"""

DDL_LLM_CACHE = """
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key             TEXT PRIMARY KEY,
    persona_id            TEXT NOT NULL,
    concept_hash          TEXT NOT NULL,
    price_context_hash    TEXT NOT NULL,
    provider              TEXT NOT NULL,
    model_name            TEXT NOT NULL,
    temperature           REAL NOT NULL,
    prompt_version        TEXT NOT NULL,
    schema_version        TEXT NOT NULL,
    price_context_version TEXT NOT NULL,
    response_json         TEXT NOT NULL,
    raw_response_path     TEXT,
    input_tokens_actual   INTEGER,
    output_tokens_actual  INTEGER,
    cost_actual_usd       REAL,
    created_at            TEXT NOT NULL
)
"""

DDL_RUN_RESULTS = """
CREATE TABLE IF NOT EXISTS run_results (
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    persona_id      TEXT NOT NULL,
    cache_key       TEXT REFERENCES llm_cache(cache_key),
    status          TEXT NOT NULL CHECK (status IN
                        ('cached','success','api_failed','parse_failed','cancelled')),
    error_type      TEXT,
    response_json   TEXT,
    latency_ms      INTEGER,
    PRIMARY KEY (run_id, persona_id)
)
"""

ALL_DDL: list[str] = [DDL_JOBS, DDL_RUNS, DDL_LLM_CACHE, DDL_RUN_RESULTS]

ALL_INDICES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_runs_job_id ON runs(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_runs_concept_hash ON runs(concept_hash)",
    "CREATE INDEX IF NOT EXISTS idx_cache_persona ON llm_cache(persona_id)",
    "CREATE INDEX IF NOT EXISTS idx_cache_concept ON llm_cache(concept_hash)",
    "CREATE INDEX IF NOT EXISTS idx_results_status ON run_results(status)",
    "CREATE INDEX IF NOT EXISTS idx_results_cache_key ON run_results(cache_key)",
]

DB_LEVEL_PRAGMAS: list[str] = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
]

CONNECTION_LEVEL_PRAGMAS: list[str] = [
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 5000",
]


def init_db(db_path: Path) -> None:
    """앱 시작 시 1회 호출. 부모 디렉토리 자동 생성, DDL + 인덱스 + db-level PRAGMA 적용."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        for pragma in DB_LEVEL_PRAGMAS:
            conn.execute(pragma)
        for pragma in CONNECTION_LEVEL_PRAGMAS:
            conn.execute(pragma)
        for ddl in ALL_DDL:
            conn.execute(ddl)
        for index_sql in ALL_INDICES:
            conn.execute(index_sql)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """connection-scoped PRAGMA 매번 적용. with 블록 내에서 사용."""
    conn = sqlite3.connect(db_path)
    try:
        for pragma in CONNECTION_LEVEL_PRAGMAS:
            conn.execute(pragma)
        yield conn
    finally:
        conn.close()
