import math

import pytest

from src.economic_context import price_burden_label, price_burden_ratio

pytestmark = pytest.mark.no_network


@pytest.mark.parametrize(
    "price,expected_ratio,expected_label",
    [
        (100_000, pytest.approx(100_000 / 200_100), "low"),
        (100_050, pytest.approx(0.5), "low"),
        (100_051, pytest.approx(100_051 / 200_100), "medium"),
        (200_100, pytest.approx(1.0), "medium"),
        (240_120, pytest.approx(1.2), "medium"),
        (240_121, pytest.approx(240_121 / 200_100), "high"),
        (300_000, pytest.approx(300_000 / 200_100), "high"),
        (400_200, pytest.approx(2.0), "high"),
        (400_201, pytest.approx(400_201 / 200_100), "very_high"),
        (500_000, pytest.approx(500_000 / 200_100), "very_high"),
    ],
)
def test_price_burden(price, expected_ratio, expected_label):
    ratio = price_burden_ratio(price)
    assert ratio == expected_ratio
    assert price_burden_label(ratio) == expected_label


def test_price_burden_zero_raises():
    with pytest.raises(ValueError):
        price_burden_ratio(0)


def test_price_burden_negative_raises():
    with pytest.raises(ValueError):
        price_burden_ratio(-1)


def test_price_burden_label_zero_raises():
    with pytest.raises(ValueError):
        price_burden_label(0.0)


def test_price_burden_label_negative_raises():
    with pytest.raises(ValueError):
        price_burden_label(-0.1)


def test_price_burden_label_nan_raises():
    with pytest.raises(ValueError):
        price_burden_label(math.nan)


def test_price_burden_label_inf_raises():
    with pytest.raises(ValueError):
        price_burden_label(math.inf)
