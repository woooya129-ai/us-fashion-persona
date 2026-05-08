# SPDX-License-Identifier: AGPL-3.0-only
"""HF dataset / local CSV and Parquet loading."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any, Literal

from src.persona_normalizer import Persona, normalize_persona
from src.secrets_loader import HF_TOKEN_VAR

_DATASET_ID_RE = re.compile(r"^(?!.*\.\.)[\w\-./]+$")

DEFAULT_HF_DATASET_ID = "nvidia/Nemotron-Personas-USA"
DEFAULT_HF_REVISION = "5b4cd35ab46490c1da1bd2b5a2324d6f871be180"
DEFAULT_SPLIT = "train"

ALLOWED_LOCAL_EXTENSIONS: tuple[str, ...] = (".csv", ".parquet")
MAX_LOCAL_FILE_BYTES: int = 500 * 1024 * 1024

DEFAULT_ALLOWED_ROOTS: tuple[Path, ...] = (Path("data").resolve(),)

EXPECTED_COLUMNS: tuple[str, ...] = (
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


class DatasetAccessError(RuntimeError):
    """Unified access/schema/path error with a UI-safe message."""

    def __init__(
        self,
        user_message: str,
        error_type: Literal[
            "unauthorized",
            "forbidden",
            "gated",
            "not_found",
            "network",
            "interrupted",
            "schema_mismatch",
            "invalid_path",
        ] = "network",
        missing_columns: list[str] | None = None,
    ) -> None:
        super().__init__(user_message)
        self.error_type = error_type
        self.user_message = user_message
        self.missing_columns = missing_columns


class DatasetSchemaError(ValueError):
    """Required dataset columns are missing."""


@dataclass(frozen=True)
class LoadedDataset:
    """Loaded dataset metadata. Raw rows are returned as an iterator."""

    source: str
    dataset_revision: str
    total_rows: int


def validate_columns(columns: list[str]) -> None:
    """Verify that all required columns are present."""
    missing = [c for c in EXPECTED_COLUMNS if c not in columns]
    if missing:
        suffix = "..." if len(missing) > 5 else ""
        raise DatasetSchemaError(
            f"missing required columns ({len(missing)}): {missing[:5]}{suffix}"
        )


def validate_local_path(
    file_path: Path,
    allowed_roots: tuple[Path, ...] | None = None,
) -> None:
    """Validate local dataset path, extension, root, and file size."""
    file_path = Path(file_path).resolve()
    roots = tuple(Path(r).resolve() for r in (allowed_roots or DEFAULT_ALLOWED_ROOTS))

    if not file_path.is_file():
        raise FileNotFoundError(f"file not found: {file_path}")

    if not any(_is_relative_to(file_path, root) for root in roots):
        raise ValueError(
            f"file path outside allowed roots: {file_path} (allowed: {[str(r) for r in roots]})"
        )

    suffix = file_path.suffix.lower()
    if suffix not in ALLOWED_LOCAL_EXTENSIONS:
        raise ValueError(f"unsupported extension: {suffix} (allowed: {ALLOWED_LOCAL_EXTENSIONS})")
    size = file_path.stat().st_size
    if size > MAX_LOCAL_FILE_BYTES:
        raise ValueError(f"file too large: {size} bytes > {MAX_LOCAL_FILE_BYTES}")


def _is_relative_to(path: Path, base: Path) -> bool:
    """Python 3.9 compatible Path.is_relative_to."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def normalize_rows_to_personas(
    rows: Iterator[dict[str, Any]],
) -> Iterator[Persona]:
    """Convert raw rows to Persona objects, skipping invalid rows."""
    for idx, row in enumerate(rows):
        persona = normalize_persona(row, idx)
        if persona is not None:
            yield persona


def _validate_dataset_id(dataset_id: str) -> None:
    """Allow only the pinned default Hugging Face dataset id."""
    if not _DATASET_ID_RE.match(dataset_id):
        raise DatasetAccessError(
            "Invalid dataset_id format. Use letters, numbers, hyphen, underscore, slash, or dot.",
            error_type="invalid_path",
        )
    if dataset_id != DEFAULT_HF_DATASET_ID:
        raise DatasetAccessError(
            f"This app only allows the Hugging Face dataset {DEFAULT_HF_DATASET_ID}.",
            error_type="invalid_path",
        )


def _validate_hf_revision(revision: str | None) -> str:
    """Return the pinned HF revision and reject runtime overrides."""
    if revision in (None, "", DEFAULT_HF_REVISION):
        return DEFAULT_HF_REVISION
    raise DatasetAccessError(
        f"This app only allows the pinned Hugging Face revision {DEFAULT_HF_REVISION}.",
        error_type="invalid_path",
    )


def load_huggingface_dataset(
    dataset_id: str = DEFAULT_HF_DATASET_ID,
    split: str = DEFAULT_SPLIT,
    streaming: bool = True,
    revision: str | None = None,
) -> tuple[LoadedDataset, Iterator[dict[str, Any]]]:
    """Load the pinned USA persona dataset from Hugging Face."""
    _validate_dataset_id(dataset_id)
    effective_revision = _validate_hf_revision(revision)

    try:
        from datasets import load_dataset  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DatasetAccessError(
            "datasets package is not installed. Run uv add datasets.",
            error_type="network",
        ) from exc

    token = os.environ.get(HF_TOKEN_VAR) or None

    try:
        ds = load_dataset(
            dataset_id,
            split=split,
            streaming=streaming,
            token=token,
            revision=effective_revision,
        )
    except Exception as exc:
        exc_type_name = type(exc).__name__
        exc_msg_lower = str(exc).lower()

        if exc_type_name == "GatedRepoError":
            raise DatasetAccessError(
                "This Hugging Face dataset requires access approval. "
                "Request access on the dataset page and try again.",
                error_type="gated",
            ) from exc

        if "401" in exc_msg_lower or "unauthorized" in exc_msg_lower:
            raise DatasetAccessError(
                "Hugging Face token is invalid. Check HF_TOKEN in ~/secrets/us-fashion/.env.",
                error_type="unauthorized",
            ) from exc

        if exc_type_name in ("DatasetNotFoundError", "RepositoryNotFoundError"):
            raise DatasetAccessError(
                "Dataset was not found. Check dataset_id.",
                error_type="not_found",
            ) from exc

        if "403" in exc_msg_lower or "forbidden" in exc_msg_lower or "permission" in exc_msg_lower:
            raise DatasetAccessError(
                "You do not have permission to access this Hugging Face dataset.",
                error_type="forbidden",
            ) from exc

        if isinstance(exc, ConnectionError | TimeoutError) or any(
            k in exc_msg_lower for k in ("connection", "timeout", "network", "unreachable")
        ):
            raise DatasetAccessError(
                "Dataset download failed. Check network status and try again.",
                error_type="network",
            ) from exc

        raise DatasetAccessError(
            "Dataset download failed. Check network status and try again.",
            error_type="network",
        ) from exc

    columns = list(ds.column_names) if hasattr(ds, "column_names") and ds.column_names else []
    if columns:
        try:
            validate_columns(columns)
        except DatasetSchemaError as exc:
            missing = [c for c in EXPECTED_COLUMNS if c not in columns]
            raise DatasetAccessError(
                f"Missing required columns: {missing[:5]}{'...' if len(missing) > 5 else ''}",
                error_type="schema_mismatch",
                missing_columns=missing,
            ) from exc

    total = -1
    if not streaming and hasattr(ds, "__len__"):
        total = len(ds)

    return (
        LoadedDataset(
            source=f"huggingface:{dataset_id}",
            dataset_revision=f"pinned:{effective_revision}",
            total_rows=total,
        ),
        iter(ds),
    )


def load_local_file(file_path: Path) -> tuple[LoadedDataset, Iterator[dict[str, Any]]]:
    """Load a local CSV or Parquet file."""
    try:
        validate_local_path(file_path)
    except FileNotFoundError as exc:
        raise DatasetAccessError(
            f"File not found: {Path(file_path).name}",
            error_type="invalid_path",
        ) from exc
    except ValueError as exc:
        raise DatasetAccessError(
            str(exc),
            error_type="invalid_path",
        ) from exc

    file_path = Path(file_path)

    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DatasetAccessError(
            "pandas package is not installed. Run uv add pandas.",
            error_type="network",
        ) from exc

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path, dtype={"zipcode": "string"})
    elif suffix == ".parquet":
        df = pd.read_parquet(file_path)
        if "zipcode" in df.columns and pd.api.types.is_numeric_dtype(df["zipcode"].dtype):
            raise DatasetAccessError(
                "Parquet zipcode column must be stored as text, not numeric. "
                "Numeric zipcodes can lose leading zeros before load.",
                error_type="schema_mismatch",
            )
    else:
        raise DatasetAccessError(
            f"Unsupported file format: {suffix}",
            error_type="invalid_path",
        )
    if "zipcode" in df.columns:
        df["zipcode"] = df["zipcode"].astype("string")

    try:
        validate_columns(list(df.columns))
    except DatasetSchemaError as exc:
        missing = [c for c in EXPECTED_COLUMNS if c not in list(df.columns)]
        raise DatasetAccessError(
            f"Missing required columns: {missing[:5]}{'...' if len(missing) > 5 else ''}",
            error_type="schema_mismatch",
            missing_columns=missing,
        ) from exc

    from datetime import datetime

    loaded_at = datetime.now(UTC).isoformat()
    rows = (row.to_dict() for _, row in df.iterrows())

    return (
        LoadedDataset(
            source=f"local:{file_path.name}",
            dataset_revision=f"loaded_at:{loaded_at}",
            total_rows=len(df),
        ),
        rows,
    )
