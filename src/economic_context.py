# SPDX-License-Identifier: AGPL-3.0-only
from typing import Literal

BLS_2024_ANNUAL_APPAREL_SERVICES_USD: int = 2_001
BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS: int = 200_100
BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD: int = 104_207
CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD: int = 83_730
FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD: int = 192_900
FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD: int = 1_063_700

OFFICIAL_US_CONTEXT_SOURCES: tuple[str, ...] = (
    "BLS Consumer Expenditure Survey 2024",
    "U.S. Census CPS ASEC 2024 income release",
    "Federal Reserve Survey of Consumer Finances 2022",
)


def price_burden_ratio(product_price_usd_cents: int) -> float:
    """ratio = product_price_usd_cents / 200_100. 0 또는 음수 → ValueError."""
    if product_price_usd_cents <= 0:
        raise ValueError(f"product_price_usd_cents must be positive, got {product_price_usd_cents}")
    return product_price_usd_cents / BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS


def _price_usd(product_price_usd_cents: int) -> float:
    if product_price_usd_cents <= 0:
        raise ValueError(f"product_price_usd_cents must be positive, got {product_price_usd_cents}")
    return product_price_usd_cents / 100


def income_ratio(product_price_usd_cents: int) -> float:
    """Product price divided by Census 2024 median household income."""
    return _price_usd(product_price_usd_cents) / CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD


def bls_income_ratio(product_price_usd_cents: int) -> float:
    """Product price divided by BLS CE 2024 average income before taxes."""
    return _price_usd(product_price_usd_cents) / BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD


def net_worth_ratio(product_price_usd_cents: int) -> float:
    """Product price divided by Fed SCF 2022 median family net worth."""
    return _price_usd(product_price_usd_cents) / FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD


def economic_baseline_hash_payload() -> dict[str, int | str]:
    """Stable official baseline payload for price_context_hash."""
    return {
        "bls_2024_apparel_services_usd": BLS_2024_ANNUAL_APPAREL_SERVICES_USD,
        "bls_2024_average_income_before_taxes_usd": BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD,
        "census_2024_median_household_income_usd": CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD,
        "fed_scf_2022_median_family_net_worth_usd": FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD,
        "fed_scf_2022_mean_family_net_worth_usd": FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD,
        "source_set": "bls_ce_2024+census_cps_asec_2024+fed_scf_2022",
    }


def price_burden_label(ratio: float) -> Literal["low", "medium", "high", "very_high"]:
    """경계는 '이하'가 낮은 라벨에 포함 (lock-in §4.5).

    ratio <= 0.5        → low
    0.5 < ratio <= 1.2  → medium
    1.2 < ratio <= 2.0  → high
    ratio > 2.0         → very_high

    M1 해소 (current-update-review 2026-05-01): ratio <= 0 또는 NaN/Inf → ValueError.
    price_burden_ratio() 가 이미 음수/0 을 거르지만, 단독 호출 보호.
    """
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
