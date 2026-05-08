"""Parquet fixture helper."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.mock_hf_rows import MOCK_HF_ROWS


def write_mock_parquet(
    tmp_path: Path,
    filename: str = "mock_data.parquet",
) -> Path:
    """Write five synthetic USA rows to a parquet file and return its path."""
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError("pandas is not installed. Run uv add pandas.") from exc

    try:
        import pyarrow  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:
        raise ImportError("pyarrow is not installed. Run uv add pyarrow.") from exc

    df = pd.DataFrame(MOCK_HF_ROWS[:5])
    out_path = tmp_path / filename
    df.to_parquet(out_path, index=False)
    return out_path
