# SPDX-License-Identifier: AGPL-3.0-only
from typing import Literal

BLS_2024_ANNUAL_APPAREL_SERVICES_USD: int = 2_001
BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS: int = 200_100


def price_burden_ratio(product_price_usd_cents: int) -> float:
    """ratio = product_price_usd_cents / 200_100. 0 또는 음수 → ValueError."""
    if product_price_usd_cents <= 0:
        raise ValueError(f"product_price_usd_cents must be positive, got {product_price_usd_cents}")
    return product_price_usd_cents / BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS


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
