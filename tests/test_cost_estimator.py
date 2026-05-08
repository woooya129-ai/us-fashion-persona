"""src/cost_estimator.py 테스트.

PM v3 §10.3 (token 추정), §10.4 (비용 계산) 검증.
"""

import pytest

from src.cost_estimator import (
    DEFAULT_CONCURRENCY,
    DEFAULT_LATENCY_HIGH_SEC,
    DEFAULT_LATENCY_LOW_SEC,
    CostEstimate,
    TokenEstimate,
    count_tokens_approx,
    estimate_cost,
    estimate_tokens,
)

pytestmark = pytest.mark.no_network


class TestCountTokensApprox:
    def test_empty_returns_zero(self):
        assert count_tokens_approx("") == 0

    def test_none_returns_zero(self):
        assert count_tokens_approx(None) == 0

    def test_short_text_min_one(self):
        assert count_tokens_approx("a") >= 1

    def test_korean_text_approx(self):
        assert count_tokens_approx("한국어 테스트 50자 가량의 임의 텍스트") > 0

    def test_longer_text_more_tokens(self):
        short = count_tokens_approx("hi")
        long = count_tokens_approx("hi" * 100)
        assert long > short


class TestEstimateTokens:
    def test_per_call_input_tokens_sum(self):
        result = estimate_tokens(
            system_prompt_tokens=100,
            persona_tokens=200,
            concept_tokens=150,
            economic_context_tokens=50,
            schema_instruction_tokens=80,
            expected_output_tokens_per_persona=325,
            new_call_count=10,
            cached_count=5,
        )
        assert result.per_call_input_tokens == 580
        assert result.per_call_output_tokens == 325
        assert result.new_call_count == 10
        assert result.cached_count == 5

    def test_estimated_total_input_tokens(self):
        result = estimate_tokens(100, 200, 150, 50, 80, 325, 10, 5)
        assert result.estimated_input_tokens_total == 5800

    def test_estimated_total_output_tokens(self):
        result = estimate_tokens(100, 200, 150, 50, 80, 325, 10, 5)
        assert result.estimated_output_tokens_total == 3250

    def test_cached_count_does_not_affect_total(self):
        a = estimate_tokens(100, 200, 150, 50, 80, 325, 10, 0)
        b = estimate_tokens(100, 200, 150, 50, 80, 325, 10, 100)
        assert a.estimated_input_tokens_total == b.estimated_input_tokens_total
        assert a.estimated_output_tokens_total == b.estimated_output_tokens_total

    def test_zero_new_calls(self):
        result = estimate_tokens(100, 200, 150, 50, 80, 325, 0, 5)
        assert result.estimated_input_tokens_total == 0
        assert result.estimated_output_tokens_total == 0

    def test_negative_input_raises(self):
        with pytest.raises(ValueError):
            estimate_tokens(-1, 0, 0, 0, 0, 0, 0, 0)


class TestEstimateCost:
    def _basic_estimate(self) -> TokenEstimate:
        return estimate_tokens(100, 200, 150, 50, 80, 325, 10, 0)

    def test_cost_calculation(self):
        token_est = self._basic_estimate()
        result = estimate_cost(token_est, 0.15, 0.60)
        # input = 5800 / 1M * 0.15 = 0.00087
        # output = 3250 / 1M * 0.60 = 0.00195
        # low = 0.00282
        assert result.estimated_cost_usd_low == pytest.approx(0.00282)
        assert result.estimated_cost_usd_high == pytest.approx(0.00282 * 1.5)

    def test_time_estimate(self):
        token_est = self._basic_estimate()
        result = estimate_cost(
            token_est,
            0.15,
            0.60,
            concurrency=5,
            average_latency_seconds_low=5,
            average_latency_seconds_high=20,
        )
        # 10 calls / 5 concurrency = 2 batches. low: 2*5=10s, high: 2*20=40s
        assert result.estimated_time_min_low == pytest.approx(10 / 60)
        assert result.estimated_time_min_high == pytest.approx(40 / 60)

    def test_returns_cost_estimate(self):
        result = estimate_cost(self._basic_estimate(), 0.15, 0.60)
        assert isinstance(result, CostEstimate)

    def test_negative_input_price_raises(self):
        with pytest.raises(ValueError):
            estimate_cost(self._basic_estimate(), -0.1, 0.60)

    def test_negative_output_price_raises(self):
        with pytest.raises(ValueError):
            estimate_cost(self._basic_estimate(), 0.15, -0.6)

    def test_zero_concurrency_raises(self):
        with pytest.raises(ValueError):
            estimate_cost(self._basic_estimate(), 0.15, 0.60, concurrency=0)

    def test_negative_concurrency_raises(self):
        with pytest.raises(ValueError):
            estimate_cost(self._basic_estimate(), 0.15, 0.60, concurrency=-5)

    def test_latency_low_greater_than_high_raises(self):
        with pytest.raises(ValueError):
            estimate_cost(
                self._basic_estimate(),
                0.15,
                0.60,
                average_latency_seconds_low=30,
                average_latency_seconds_high=10,
            )

    def test_default_concurrency_is_5(self):
        assert DEFAULT_CONCURRENCY == 5

    def test_default_latency_range(self):
        assert DEFAULT_LATENCY_LOW_SEC == 5
        assert DEFAULT_LATENCY_HIGH_SEC == 20
