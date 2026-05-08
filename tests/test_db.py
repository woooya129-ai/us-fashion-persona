"""src/db.py 테스트.

lock-in v1.2 §5.1-§5.5 정합성 검증.
모든 DB 파일은 tmp_path 사용 (실제 cache.db 영향 없음).
"""

import sqlite3
from pathlib import Path

import pytest

from src.db import (
    ALL_DDL,
    ALL_INDICES,
    CONNECTION_LEVEL_PRAGMAS,
    DB_LEVEL_PRAGMAS,
    get_connection,
    init_db,
)

pytestmark = pytest.mark.no_network


EXPECTED_TABLES = {"jobs", "runs", "llm_cache", "run_results"}
EXPECTED_INDICES = {
    "idx_jobs_status",
    "idx_jobs_created_at",
    "idx_runs_job_id",
    "idx_runs_concept_hash",
    "idx_cache_persona",
    "idx_cache_concept",
    "idx_results_status",
    "idx_results_cache_key",
}


class TestInitDb:
    def test_creates_db_file(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path):
        db_path = tmp_path / "nested" / "dir" / "test.db"
        init_db(db_path)
        assert db_path.exists()

    def test_creates_all_four_tables(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        actual = {r[0] for r in rows}
        assert EXPECTED_TABLES.issubset(actual)

    def test_creates_all_indices(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        actual = {r[0] for r in rows}
        assert EXPECTED_INDICES.issubset(actual)

    def test_idempotent_re_init(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
        assert count >= len(EXPECTED_TABLES)

    def test_journal_mode_wal(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_runs_table_has_v12_columns(self, tmp_path: Path):
        """v1.2 추가 컬럼 (provider, price_context_version, dataset_revision) 존재."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
        assert {"provider", "price_context_version", "dataset_revision"}.issubset(cols)

    def test_llm_cache_has_v12_columns(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(llm_cache)").fetchall()}
        assert {"provider", "price_context_version"}.issubset(cols)


class TestGetConnection:
    def test_foreign_keys_on(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with get_connection(db_path) as conn:
            value = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert value == 1

    def test_busy_timeout_5000(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with get_connection(db_path) as conn:
            value = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert value == 5000

    def test_connection_closed_after_with(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with get_connection(db_path) as conn:
            pass
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_foreign_key_constraint_runs_to_jobs(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with (
            get_connection(db_path) as conn,
            pytest.raises(sqlite3.IntegrityError),
        ):
            conn.execute(
                "INSERT INTO runs (run_id, job_id, created_at, dataset_name, "
                "dataset_revision, sample_size, sampling_seed, provider, model_name, "
                "temperature, prompt_version, schema_version, price_context_version, "
                "concept_hash, price_context_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "run-1",
                    "nonexistent-job",
                    "2026-04-30",
                    "test_dataset",
                    "rev-1",
                    10,
                    42,
                    "openai",
                    "gpt-4o-mini",
                    0.3,
                    "concept_eval_ko_v0_3",
                    "eval_v0_1",
                    "bls_2024_apparel_services_annual_v1",
                    "concept_hash_1",
                    "price_hash_1",
                ),
            )
            conn.commit()


class TestModuleConstants:
    def test_all_ddl_count(self):
        assert len(ALL_DDL) == 4

    def test_all_indices_count(self):
        assert len(ALL_INDICES) >= 8

    def test_db_level_pragmas_include_wal(self):
        joined = " ".join(DB_LEVEL_PRAGMAS).lower()
        assert "wal" in joined
        assert "synchronous" in joined

    def test_connection_level_pragmas_include_foreign_keys(self):
        joined = " ".join(CONNECTION_LEVEL_PRAGMAS).lower()
        assert "foreign_keys" in joined
        assert "busy_timeout" in joined
