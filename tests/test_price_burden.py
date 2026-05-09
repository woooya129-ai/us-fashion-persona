import math

import pytest

from src import economic_context as econ
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


def test_official_us_income_and_asset_ratios():
    price = 20_010

    assert econ.income_ratio(price) == pytest.approx(200.10 / 83_730)
    assert econ.bls_income_ratio(price) == pytest.approx(200.10 / 104_207)
    assert econ.net_worth_ratio(price) == pytest.approx(200.10 / 192_900)


def test_economic_baseline_hash_payload_includes_income_and_assets():
    payload = econ.economic_baseline_hash_payload()

    assert payload["bls_2024_apparel_services_usd"] == 2_001
    assert payload["bls_2024_average_income_before_taxes_usd"] == 104_207
    assert payload["census_2024_median_household_income_usd"] == 83_730
    assert payload["fed_scf_2022_median_family_net_worth_usd"] == 192_900
    assert payload["fed_scf_2022_mean_family_net_worth_usd"] == 1_063_700


def test_us_context_segment_options_include_age_segments():
    options = econ.us_context_segment_options()

    assert options["national_all"] == "U.S. national baseline"
    assert options["age_25_34"] == "Age 25 to 34"
    assert options["age_75_plus"] == "Age 75 or over"


def test_build_price_context_uses_selected_age_segment_snapshot():
    context = econ.build_price_context(20_010, reference_segment_id="age_35_44")

    assert context["reference_segment_id"] == "age_35_44"
    assert context["reference_segment_label"] == "Age 35 to 44"
    assert context["apparel_services_annual_usd"] == 2_649
    assert context["bls_average_income_before_taxes_usd"] == 128_285
    assert context["census_median_household_income_usd"] == 106_100
    assert context["fed_scf_median_family_net_worth_usd"] == 135_600
    assert context["fed_scf_mean_family_net_worth_usd"] == 549_600
    assert context["price_burden_ratio"] == pytest.approx(20_010 / 264_900)
    assert context["income_ratio"] == pytest.approx(200.10 / 106_100)
    assert len(context["metric_rows"]) == 5


def test_context_hash_payload_includes_selected_segment_digest():
    context = econ.build_price_context(20_010, reference_segment_id="age_45_54")
    payload = econ.economic_baseline_hash_payload(context)

    assert payload["reference_segment_id"] == "age_45_54"
    assert payload["denominator_usd_cents"] == 254_700
    assert payload["metrics"]["median_household_income_usd"] == 116_800
    assert payload["context_digest"] == context["context_digest"]
