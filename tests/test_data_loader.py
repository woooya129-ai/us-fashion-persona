"""src/data_loader.py tests.

No real Hugging Face calls or real data file reads beyond synthetic fixtures.
"""

import sys
from pathlib import Path

import pytest

from src.data_loader import (
    ALLOWED_LOCAL_EXTENSIONS,
    DEFAULT_HF_DATASET_ID,
    DEFAULT_HF_REVISION,
    EXPECTED_COLUMNS,
    MAX_LOCAL_FILE_BYTES,
    DatasetAccessError,
    DatasetSchemaError,
    normalize_rows_to_personas,
    validate_columns,
    validate_local_path,
)
from tests.fixtures.mock_hf_rows import MOCK_HF_ROWS
from tests.fixtures.mock_personas import ALL_MOCK_PERSONAS

pytestmark = pytest.mark.no_network


class TestValidateColumns:
    def test_all_present(self):
        validate_columns(list(EXPECTED_COLUMNS))

    def test_extra_columns_ok(self):
        validate_columns(list(EXPECTED_COLUMNS) + ["bonus", "extra"])

    def test_missing_one_raises(self):
        cols = [c for c in EXPECTED_COLUMNS if c != "persona"]
        with pytest.raises(DatasetSchemaError):
            validate_columns(cols)

    def test_missing_uuid_raises(self):
        cols = [c for c in EXPECTED_COLUMNS if c != "uuid"]
        with pytest.raises(DatasetSchemaError):
            validate_columns(cols)

    def test_empty_columns_raises(self):
        with pytest.raises(DatasetSchemaError):
            validate_columns([])

    def test_count_is_23(self):
        assert len(EXPECTED_COLUMNS) == 23

    def test_expected_columns_match_usa_contract(self):
        assert EXPECTED_COLUMNS == (
            "uuid",
            "professional_persona",
            "sports_persona",
            "arts_persona",
            "travel_persona",
            "culinary_persona",
            "persona",
            "cultural_background",
            "skills_and_expertise",
            "skills_and_expertise_list",
            "hobbies_and_interests",
            "hobbies_and_interests_list",
            "career_goals_and_ambitions",
            "sex",
            "age",
            "marital_status",
            "education_level",
            "bachelors_field",
            "occupation",
            "city",
            "state",
            "zipcode",
            "country",
        )


class TestValidateLocalPath:
    def test_csv_extension_ok(self, tmp_path: Path):
        p = tmp_path / "data.csv"
        p.write_text("a,b,c\n", encoding="utf-8")
        validate_local_path(p, allowed_roots=(tmp_path,))

    def test_parquet_extension_ok(self, tmp_path: Path):
        p = tmp_path / "data.parquet"
        p.write_bytes(b"PAR1")
        validate_local_path(p, allowed_roots=(tmp_path,))

    def test_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            validate_local_path(tmp_path / "missing.csv", allowed_roots=(tmp_path,))

    def test_disallowed_extension_raises(self, tmp_path: Path):
        p = tmp_path / "data.json"
        p.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported extension"):
            validate_local_path(p, allowed_roots=(tmp_path,))

    def test_pickle_extension_raises(self, tmp_path: Path):
        p = tmp_path / "data.pkl"
        p.write_bytes(b"x")
        with pytest.raises(ValueError, match="unsupported"):
            validate_local_path(p, allowed_roots=(tmp_path,))

    def test_oversize_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        import stat as stat_module

        p = tmp_path / "data.csv"
        p.write_text("a\n", encoding="utf-8")
        p_resolved = p.resolve()
        original_stat = Path.stat

        class FakeStat:
            st_size = MAX_LOCAL_FILE_BYTES + 1
            st_mode = stat_module.S_IFREG | 0o644

        def fake_stat(self, *args, **kwargs):
            if self == p_resolved:
                return FakeStat()
            return original_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", fake_stat)
        with pytest.raises(ValueError, match="too large"):
            validate_local_path(p, allowed_roots=(tmp_path,))

    def test_outside_allowed_roots_rejected(self, tmp_path: Path):
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "data.csv"
        outside_file.write_text("a\n", encoding="utf-8")

        allowed = tmp_path / "allowed"
        allowed.mkdir()

        with pytest.raises(ValueError, match="outside allowed roots"):
            validate_local_path(outside_file, allowed_roots=(allowed,))

    def test_path_traversal_rejected(self, tmp_path: Path):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        sibling = tmp_path / "sibling.csv"
        sibling.write_text("a\n", encoding="utf-8")

        traversal = allowed / ".." / "sibling.csv"
        with pytest.raises(ValueError, match="outside allowed roots"):
            validate_local_path(traversal, allowed_roots=(allowed,))

    def test_default_allowed_roots_uses_data_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        outside = tmp_path / "x.csv"
        outside.write_text("a\n", encoding="utf-8")
        with pytest.raises(ValueError, match="outside allowed roots"):
            validate_local_path(outside)


class TestNormalizeRowsToPersonas:
    def test_all_mock_personas_yield(self):
        personas = list(normalize_rows_to_personas(iter(ALL_MOCK_PERSONAS)))
        assert len(personas) == len(ALL_MOCK_PERSONAS)

    def test_invalid_rows_skipped(self):
        rows = [
            ALL_MOCK_PERSONAS[0],
            {"uuid": "", "age": 1, "sex": "F", "persona": "x"},
            ALL_MOCK_PERSONAS[1],
        ]
        personas = list(normalize_rows_to_personas(iter(rows)))
        assert len(personas) == 2

    def test_source_row_id_assigned(self):
        rows = list(ALL_MOCK_PERSONAS)
        personas = list(normalize_rows_to_personas(iter(rows)))
        assert [p.source_row_id for p in personas] == list(range(len(rows)))


class TestModuleConstants:
    def test_default_dataset_contract(self):
        assert DEFAULT_HF_DATASET_ID == "nvidia/Nemotron-Personas-USA"
        assert DEFAULT_HF_REVISION == "5b4cd35ab46490c1da1bd2b5a2324d6f871be180"

    def test_allowed_extensions(self):
        assert ".csv" in ALLOWED_LOCAL_EXTENSIONS
        assert ".parquet" in ALLOWED_LOCAL_EXTENSIONS
        assert ".pkl" not in ALLOWED_LOCAL_EXTENSIONS
        assert ".json" not in ALLOWED_LOCAL_EXTENSIONS

    def test_max_file_bytes_reasonable(self):
        assert 100 * 1024 * 1024 <= MAX_LOCAL_FILE_BYTES <= 1024 * 1024 * 1024


class TestDatasetAccessError:
    def test_default_error_type_is_network(self):
        err = DatasetAccessError("test error")
        assert err.error_type == "network"
        assert err.user_message == "test error"
        assert err.missing_columns is None

    def test_all_eight_error_types_accepted(self):
        types = [
            "unauthorized",
            "forbidden",
            "gated",
            "not_found",
            "network",
            "interrupted",
            "schema_mismatch",
            "invalid_path",
        ]
        for etype in types:
            err = DatasetAccessError("message", error_type=etype)  # type: ignore[arg-type]
            assert err.error_type == etype

    def test_missing_columns_set_for_schema_mismatch(self):
        err = DatasetAccessError(
            "missing columns",
            error_type="schema_mismatch",
            missing_columns=["uuid", "age"],
        )
        assert err.missing_columns == ["uuid", "age"]

    def test_is_runtime_error_subclass(self):
        err = DatasetAccessError("error")
        assert isinstance(err, RuntimeError)

    def test_str_is_user_message(self):
        err = DatasetAccessError("safe user message")
        assert "safe user message" in str(err)


def _make_fake_dataset(rows: list[dict], column_names: list[str] | None = None):
    """Fake iterable object returned by datasets.load_dataset."""

    class FakeDS:
        def __init__(self) -> None:
            self.column_names = column_names or (list(rows[0].keys()) if rows else [])

        def __iter__(self):
            return iter(rows)

        def __len__(self):
            return len(rows)

    return FakeDS()


class TestLoadHuggingfaceDataset:
    def _patch_load_dataset(self, monkeypatch, fake_fn):
        class FakeDatasets:
            @staticmethod
            def load_dataset(*args, **kwargs):
                return fake_fn(*args, **kwargs)

        monkeypatch.setitem(sys.modules, "datasets", FakeDatasets)

    def test_happy_path_returns_loaded_dataset_with_default_revision(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        seen = {}

        def fake_load(*args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return _make_fake_dataset(MOCK_HF_ROWS)

        self._patch_load_dataset(monkeypatch, fake_load)

        meta, rows_iter = load_huggingface_dataset()
        assert meta.source == "huggingface:nvidia/Nemotron-Personas-USA"
        assert meta.dataset_revision == f"pinned:{DEFAULT_HF_REVISION}"
        assert seen["args"][0] == "nvidia/Nemotron-Personas-USA"
        assert seen["kwargs"]["revision"] == DEFAULT_HF_REVISION
        assert list(rows_iter)[:1] == MOCK_HF_ROWS[:1]

    def test_default_revision_can_be_passed_explicitly(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        seen = {}

        def fake_load(*args, **kwargs):
            seen["kwargs"] = kwargs
            return _make_fake_dataset(MOCK_HF_ROWS)

        self._patch_load_dataset(monkeypatch, fake_load)

        meta, _ = load_huggingface_dataset(DEFAULT_HF_DATASET_ID, revision=DEFAULT_HF_REVISION)
        assert meta.dataset_revision == f"pinned:{DEFAULT_HF_REVISION}"
        assert seen["kwargs"]["revision"] == DEFAULT_HF_REVISION

    def test_non_default_revision_is_rejected(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset(DEFAULT_HF_DATASET_ID, revision="abc123")

        assert exc_info.value.error_type == "invalid_path"
        assert DEFAULT_HF_REVISION in exc_info.value.user_message

    def test_gated_repo_error_maps_to_gated(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        class GatedRepoError(Exception):
            pass

        def fake_load(*args, **kwargs):
            raise GatedRepoError("gated")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "gated"
        assert "requires access" in exc_info.value.user_message

    def test_dataset_not_found_maps_to_not_found(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        class DatasetNotFoundError(Exception):
            pass

        def fake_load(*args, **kwargs):
            raise DatasetNotFoundError("not found")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "not_found"
        assert "not found" in exc_info.value.user_message

    def test_repository_not_found_maps_to_not_found(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        class RepositoryNotFoundError(Exception):
            pass

        def fake_load(*args, **kwargs):
            raise RepositoryNotFoundError("repo not found")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "not_found"

    def test_repository_not_found_with_401_maps_to_unauthorized(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        class RepositoryNotFoundError(Exception):
            pass

        def fake_load(*args, **kwargs):
            raise RepositoryNotFoundError("401 Client Error: Unauthorized")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "unauthorized"
        assert "token" in exc_info.value.user_message

    def test_401_string_maps_to_unauthorized(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        def fake_load(*args, **kwargs):
            raise RuntimeError("HTTP Error 401: unauthorized token")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "unauthorized"
        assert "token" in exc_info.value.user_message

    def test_403_string_maps_to_forbidden(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        def fake_load(*args, **kwargs):
            raise RuntimeError("HTTP Error 403 forbidden")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "forbidden"
        assert "permission" in exc_info.value.user_message

    def test_connection_error_maps_to_network(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        def fake_load(*args, **kwargs):
            raise ConnectionError("connection refused")

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "network"
        assert "download failed" in exc_info.value.user_message

    def test_22_columns_raises_schema_mismatch(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        partial_cols = [c for c in EXPECTED_COLUMNS if c != "uuid"]
        short_rows = [{c: "x" for c in partial_cols}]

        def fake_load(*args, **kwargs):
            return _make_fake_dataset(short_rows, column_names=partial_cols)

        self._patch_load_dataset(monkeypatch, fake_load)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()
        assert exc_info.value.error_type == "schema_mismatch"
        assert exc_info.value.missing_columns is not None
        assert "uuid" in exc_info.value.missing_columns

    def test_invalid_dataset_id_raises_invalid_path(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset("../etc/passwd")
        assert exc_info.value.error_type == "invalid_path"

    def test_dataset_id_with_special_chars_raises(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset("nvidia/data;rm -rf /")
        assert exc_info.value.error_type == "invalid_path"

    def test_non_default_hf_dataset_is_rejected(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset("otherorg/other-dataset")
        assert exc_info.value.error_type == "invalid_path"
        assert "nvidia/Nemotron-Personas-USA" in exc_info.value.user_message

    def test_hf_token_not_leaked_in_error(self, monkeypatch):
        from src.data_loader import load_huggingface_dataset

        fake_token = "hf_FAKE_TOKEN_FOR_TESTING_ONLY_AAABBB"

        def fake_load(*args, **kwargs):
            raise RuntimeError("Some error without token info")

        self._patch_load_dataset(monkeypatch, fake_load)
        monkeypatch.setenv("HF_TOKEN", fake_token)

        with pytest.raises(DatasetAccessError) as exc_info:
            load_huggingface_dataset()

        assert fake_token not in exc_info.value.user_message
        assert fake_token not in str(exc_info.value)


class TestLoadLocalFileErrors:
    def test_nonexistent_file_raises_invalid_path(self, tmp_path: Path, monkeypatch):
        from src.data_loader import load_local_file

        monkeypatch.chdir(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with pytest.raises(DatasetAccessError) as exc_info:
            load_local_file(data_dir / "missing.csv")
        assert exc_info.value.error_type == "invalid_path"

    def test_wrong_extension_raises_invalid_path(self, tmp_path: Path):
        from src.data_loader import load_local_file

        p = tmp_path / "data.txt"
        p.write_text("hello\n", encoding="utf-8")

        with pytest.raises(DatasetAccessError) as exc_info:
            load_local_file(p)
        assert exc_info.value.error_type == "invalid_path"

    def test_path_traversal_raises_invalid_path(self, tmp_path: Path, monkeypatch):
        from src.data_loader import load_local_file

        monkeypatch.chdir(tmp_path)
        allowed = tmp_path / "data"
        allowed.mkdir()
        sibling = tmp_path / "secret.csv"
        sibling.write_text("a\n", encoding="utf-8")

        with pytest.raises(DatasetAccessError) as exc_info:
            load_local_file(allowed / ".." / "secret.csv")
        assert exc_info.value.error_type == "invalid_path"

    def test_missing_columns_raises_schema_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        pytest.importorskip("pandas")

        import src.data_loader as dl_module

        monkeypatch.setattr(dl_module, "DEFAULT_ALLOWED_ROOTS", (tmp_path,))

        p = tmp_path / "bad.csv"
        p.write_text("col_a,col_b\nval1,val2\n", encoding="utf-8")

        from src.data_loader import load_local_file

        with pytest.raises(DatasetAccessError) as exc_info:
            load_local_file(p)
        assert exc_info.value.error_type == "schema_mismatch"
        assert exc_info.value.missing_columns is not None
        assert len(exc_info.value.missing_columns) > 0

    def test_mock_csv_fixture_loads_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        pytest.importorskip("pandas")

        import shutil

        import src.data_loader as dl_module

        fixture_csv = Path(__file__).parent / "fixtures" / "mock_local_csv.csv"
        dest = tmp_path / "mock_local_csv.csv"
        shutil.copy(fixture_csv, dest)

        monkeypatch.setattr(dl_module, "DEFAULT_ALLOWED_ROOTS", (tmp_path,))

        from src.data_loader import load_local_file

        meta, rows_iter = load_local_file(dest)
        rows = list(rows_iter)
        assert meta.source == "local:mock_local_csv.csv"
        assert len(rows) == 5
        assert str(rows[0]["zipcode"]) == "27601"
        assert isinstance(rows[0]["zipcode"], str)

    def test_csv_zipcode_preserves_leading_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        pytest.importorskip("pandas")

        import pandas as pd

        import src.data_loader as dl_module

        csv_path = tmp_path / "zipcodes.csv"
        row = {column: "" for column in EXPECTED_COLUMNS}
        row.update(
            {
                "uuid": "z-1",
                "persona": "persona",
                "age": 30,
                "sex": "F",
                "city": "Princeton",
                "state": "NJ",
                "zipcode": "08540",
                "country": "United States",
            }
        )
        pd.DataFrame([row]).to_csv(csv_path, index=False)
        monkeypatch.setattr(dl_module, "DEFAULT_ALLOWED_ROOTS", (tmp_path,))

        from src.data_loader import load_local_file

        _, rows_iter = load_local_file(csv_path)
        rows = list(rows_iter)
        assert rows[0]["zipcode"] == "08540"
        assert isinstance(rows[0]["zipcode"], str)

    def test_mock_parquet_fixture_loads_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        from tests.fixtures.mock_local_parquet import write_mock_parquet

        parquet_path = write_mock_parquet(tmp_path)

        import src.data_loader as dl_module

        monkeypatch.setattr(dl_module, "DEFAULT_ALLOWED_ROOTS", (tmp_path,))

        from src.data_loader import load_local_file

        meta, rows_iter = load_local_file(parquet_path)
        rows = list(rows_iter)
        assert meta.source == "local:mock_data.parquet"
        assert len(rows) == 5
        assert isinstance(rows[0]["zipcode"], str)

    def test_parquet_zipcode_preserves_leading_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        import pandas as pd

        import src.data_loader as dl_module

        parquet_path = tmp_path / "zipcodes.parquet"
        row = {column: "" for column in EXPECTED_COLUMNS}
        row.update(
            {
                "uuid": "z-1",
                "persona": "persona",
                "age": 30,
                "sex": "F",
                "city": "Princeton",
                "state": "NJ",
                "zipcode": "08540",
                "country": "United States",
            }
        )
        pd.DataFrame([row]).to_parquet(parquet_path, index=False)
        monkeypatch.setattr(dl_module, "DEFAULT_ALLOWED_ROOTS", (tmp_path,))

        from src.data_loader import load_local_file

        _, rows_iter = load_local_file(parquet_path)
        rows = list(rows_iter)
        assert rows[0]["zipcode"] == "08540"
        assert isinstance(rows[0]["zipcode"], str)

    def test_parquet_numeric_zipcode_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        import pandas as pd

        import src.data_loader as dl_module

        parquet_path = tmp_path / "numeric-zipcodes.parquet"
        row = {column: "" for column in EXPECTED_COLUMNS}
        row.update(
            {
                "uuid": "z-1",
                "persona": "persona",
                "age": 30,
                "sex": "F",
                "city": "Princeton",
                "state": "NJ",
                "zipcode": 8540,
                "country": "United States",
            }
        )
        pd.DataFrame([row]).to_parquet(parquet_path, index=False)
        monkeypatch.setattr(dl_module, "DEFAULT_ALLOWED_ROOTS", (tmp_path,))

        from src.data_loader import load_local_file

        with pytest.raises(DatasetAccessError) as exc_info:
            load_local_file(parquet_path)

        assert exc_info.value.error_type == "schema_mismatch"
        assert "zipcode column must be stored as text" in exc_info.value.user_message
