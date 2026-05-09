# SPDX-License-Identifier: AGPL-3.0-only
"""Official U.S. household context for price-burden prompts and reports."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
US_CONTEXT_SNAPSHOT_PATH = REPO_ROOT / "data" / "public" / "us_household_context.csv"

DEFAULT_REFERENCE_SEGMENT_ID = "national_all"
DEFAULT_REFERENCE_SEGMENT_LABEL = "U.S. national baseline"

BLS_2024_ANNUAL_APPAREL_SERVICES_USD: int = 2_001
BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS: int = 200_100
BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD: int = 104_207
CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD: int = 83_730
FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD: int = 192_900
FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD: int = 1_063_700

OFFICIAL_US_CONTEXT_SOURCES: tuple[str, ...] = (
    "BLS Consumer Expenditure Surveys 2024",
    "U.S. Census CPS ASEC 2024 HINC-02",
    "Federal Reserve Survey of Consumer Finances 2022",
)

MetricKey = Literal[
    "annual_apparel_services_spend_usd",
    "average_income_before_taxes_usd",
    "median_household_income_usd",
    "median_family_net_worth_usd",
    "mean_family_net_worth_usd",
]

REFERENCE_METRIC_LABELS: dict[str, str] = {
    "annual_apparel_services_spend_usd": (
        "BLS Consumer Expenditure Survey 2024 annual Apparel and services"
    ),
    "average_income_before_taxes_usd": (
        "BLS Consumer Expenditure Survey 2024 average income before taxes"
    ),
    "median_household_income_usd": "Census CPS ASEC 2024 median household income",
    "median_family_net_worth_usd": "Federal Reserve SCF 2022 median family net worth",
    "mean_family_net_worth_usd": "Federal Reserve SCF 2022 mean family net worth",
}


@dataclass(frozen=True)
class UsMetric:
    segment_id: str
    segment_label: str
    metric: str
    period: str
    value_usd: int
    source_name: str
    source_url: str
    note: str = ""


def _validate_price(product_price_usd_cents: int) -> None:
    if product_price_usd_cents <= 0:
        raise ValueError(f"product_price_usd_cents must be positive, got {product_price_usd_cents}")


def price_burden_ratio(
    product_price_usd_cents: int,
    denominator_usd_cents: int | None = None,
) -> float:
    """ratio = product_price_usd_cents / annual apparel-services denominator."""
    _validate_price(product_price_usd_cents)
    denominator = int(denominator_usd_cents or BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS)
    if denominator <= 0:
        raise ValueError(f"denominator_usd_cents must be positive, got {denominator}")
    return product_price_usd_cents / denominator


def _price_usd(product_price_usd_cents: int) -> float:
    _validate_price(product_price_usd_cents)
    return product_price_usd_cents / 100


def income_ratio(
    product_price_usd_cents: int,
    median_household_income_usd: int | None = None,
) -> float:
    """Product price divided by Census median household income."""
    denominator = int(median_household_income_usd or CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD)
    if denominator <= 0:
        raise ValueError(f"median_household_income_usd must be positive, got {denominator}")
    return _price_usd(product_price_usd_cents) / denominator


def bls_income_ratio(
    product_price_usd_cents: int,
    average_income_before_taxes_usd: int | None = None,
) -> float:
    """Product price divided by BLS CE average income before taxes."""
    denominator = int(average_income_before_taxes_usd or BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD)
    if denominator <= 0:
        raise ValueError(f"average_income_before_taxes_usd must be positive, got {denominator}")
    return _price_usd(product_price_usd_cents) / denominator


def net_worth_ratio(
    product_price_usd_cents: int,
    median_family_net_worth_usd: int | None = None,
) -> float:
    """Product price divided by Fed SCF median family net worth."""
    denominator = int(median_family_net_worth_usd or FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD)
    if denominator <= 0:
        raise ValueError(f"median_family_net_worth_usd must be positive, got {denominator}")
    return _price_usd(product_price_usd_cents) / denominator


def load_us_context_snapshot(path: Path = US_CONTEXT_SNAPSHOT_PATH) -> list[UsMetric]:
    """Load committed official U.S. context snapshot."""
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [
            UsMetric(
                segment_id=str(row["segment_id"]),
                segment_label=str(row["segment_label"]),
                metric=str(row["metric"]),
                period=str(row["period"]),
                value_usd=int(float(row["value_usd"])),
                source_name=str(row["source_name"]),
                source_url=str(row["source_url"]),
                note=str(row.get("note", "")),
            )
            for row in reader
        ]


def us_context_segment_options(metrics: list[UsMetric] | None = None) -> dict[str, str]:
    """Return segment_id to segment_label options in snapshot order."""
    metrics = metrics if metrics is not None else load_us_context_snapshot()
    options: dict[str, str] = {}
    for row in metrics:
        options.setdefault(row.segment_id, row.segment_label)
    return options


def _selected_metrics(metrics: list[UsMetric], segment_id: str) -> tuple[list[UsMetric], str, str]:
    options = us_context_segment_options(metrics)
    selected_segment = segment_id if segment_id in options else DEFAULT_REFERENCE_SEGMENT_ID

    national = [row for row in metrics if row.segment_id == DEFAULT_REFERENCE_SEGMENT_ID]
    selected = [row for row in metrics if row.segment_id == selected_segment]

    by_metric: dict[str, UsMetric] = {row.metric: row for row in national}
    for row in selected:
        by_metric[row.metric] = row

    metric_order = list(REFERENCE_METRIC_LABELS)
    ordered = sorted(
        by_metric.values(),
        key=lambda row: (
            metric_order.index(row.metric)
            if row.metric in REFERENCE_METRIC_LABELS
            else len(metric_order)
        ),
    )
    return ordered, selected_segment, options.get(selected_segment, DEFAULT_REFERENCE_SEGMENT_LABEL)


def _metric_value(rows: list[UsMetric], metric: str) -> int | None:
    for row in rows:
        if row.metric == metric:
            return row.value_usd
    return None


def _period_summary(rows: list[UsMetric]) -> str:
    periods = sorted({row.period for row in rows})
    return ", ".join(periods)


def _hash_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _context_digest(rows: list[UsMetric], segment_id: str) -> str:
    return _hash_payload(
        {
            "segment_id": segment_id,
            "rows": [
                {
                    "metric": row.metric,
                    "period": row.period,
                    "value_usd": row.value_usd,
                    "source_name": row.source_name,
                }
                for row in rows
            ],
        }
    )


def build_price_context(
    product_price_usd_cents: int,
    *,
    reference_segment_id: str = DEFAULT_REFERENCE_SEGMENT_ID,
    snapshot_path: Path = US_CONTEXT_SNAPSHOT_PATH,
) -> dict[str, Any]:
    """Build compact context used by UI, prompt, cache hash, and report."""
    snapshot_metrics = load_us_context_snapshot(snapshot_path)
    warnings: list[str] = []
    options = us_context_segment_options(snapshot_metrics)
    if reference_segment_id not in options:
        warnings.append(
            f"Unknown U.S. reference segment '{reference_segment_id}', using national baseline."
        )

    selected_rows, selected_segment, segment_label = _selected_metrics(
        snapshot_metrics,
        reference_segment_id,
    )
    apparel_services = (
        _metric_value(selected_rows, "annual_apparel_services_spend_usd")
        or BLS_2024_ANNUAL_APPAREL_SERVICES_USD
    )
    average_income = (
        _metric_value(selected_rows, "average_income_before_taxes_usd")
        or BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD
    )
    median_income = (
        _metric_value(selected_rows, "median_household_income_usd")
        or CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD
    )
    median_net_worth = (
        _metric_value(selected_rows, "median_family_net_worth_usd")
        or FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD
    )
    mean_net_worth = (
        _metric_value(selected_rows, "mean_family_net_worth_usd")
        or FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD
    )

    denominator = int(apparel_services) * 100
    ratio = price_burden_ratio(product_price_usd_cents, denominator)
    metrics = {row.metric: row.value_usd for row in selected_rows}
    source_names = sorted({row.source_name for row in selected_rows})
    source_urls = sorted({row.source_url for row in selected_rows if row.source_url})
    context_digest = _context_digest(selected_rows, selected_segment)

    return {
        "source": "us_official",
        "source_mode": "snapshot",
        "source_name": "; ".join(source_names),
        "source_urls": source_urls,
        "reference_segment_id": selected_segment,
        "reference_segment_label": segment_label,
        "period": _period_summary(selected_rows),
        "denominator_usd_cents": denominator,
        "price_burden_ratio": ratio,
        "price_burden_label": price_burden_label(ratio),
        "income_ratio": income_ratio(product_price_usd_cents, median_income),
        "bls_income_ratio": bls_income_ratio(product_price_usd_cents, average_income),
        "net_worth_ratio": net_worth_ratio(product_price_usd_cents, median_net_worth),
        "apparel_services_annual_usd": apparel_services,
        "bls_average_income_before_taxes_usd": average_income,
        "census_median_household_income_usd": median_income,
        "fed_scf_median_family_net_worth_usd": median_net_worth,
        "fed_scf_mean_family_net_worth_usd": mean_net_worth,
        "sources": OFFICIAL_US_CONTEXT_SOURCES,
        "metrics": metrics,
        "metric_rows": [
            {
                "metric": row.metric,
                "label": REFERENCE_METRIC_LABELS.get(row.metric, row.metric),
                "period": row.period,
                "value_usd": row.value_usd,
                "source_name": row.source_name,
                "source_url": row.source_url,
                "note": row.note,
            }
            for row in selected_rows
        ],
        "warnings": tuple(warnings),
        "context_digest": context_digest,
    }


def economic_baseline_hash_payload(price_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stable official baseline payload for price_context_hash."""
    if price_context is not None:
        return {
            "source_set": "bls_ce_2024+census_cps_asec_2024_hinc02+fed_scf_2022",
            "source_mode": price_context.get("source_mode", "snapshot"),
            "reference_segment_id": price_context.get("reference_segment_id"),
            "reference_segment_label": price_context.get("reference_segment_label"),
            "period": price_context.get("period"),
            "denominator_usd_cents": price_context.get("denominator_usd_cents"),
            "context_digest": price_context.get("context_digest"),
            "metrics": price_context.get("metrics", {}),
        }

    return {
        "bls_2024_apparel_services_usd": BLS_2024_ANNUAL_APPAREL_SERVICES_USD,
        "bls_2024_average_income_before_taxes_usd": BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD,
        "census_2024_median_household_income_usd": CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD,
        "fed_scf_2022_median_family_net_worth_usd": FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD,
        "fed_scf_2022_mean_family_net_worth_usd": FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD,
        "source_set": "bls_ce_2024+census_cps_asec_2024+fed_scf_2022",
    }


def price_burden_label(ratio: float) -> Literal["low", "medium", "high", "very_high"]:
    """Classify product price relative to annual apparel-services spending."""
    import math

    if not isinstance(ratio, int | float) or math.isnan(ratio) or math.isinf(ratio):
        raise ValueError(f"ratio must be finite number, got {ratio!r}")
    if ratio <= 0:
        raise ValueError(f"ratio must be positive, got {ratio}")
    if ratio <= 0.5:
        return "low"
    if ratio <= 1.2:
        return "medium"
    if ratio <= 2.0:
        return "high"
    return "very_high"
