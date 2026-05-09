"""src/cache.py 테스트.

lock-in v1.2 §5.3.1 canonical input + DISCUSS-001 옵션 A (cache_key 에 provider 포함) 검증.
"""

import pytest

from src.cache import (
    compute_cache_key,
    compute_concept_hash,
    compute_price_context_hash,
    normalize_concept_text,
)

pytestmark = pytest.mark.no_network


class TestNormalizeConceptText:
    def test_strip_whitespace(self):
        assert normalize_concept_text("  hello  ") == "hello"

    def test_collapse_consecutive_spaces(self):
        assert normalize_concept_text("a    b") == "a b"

    def test_collapse_mixed_whitespace(self):
        assert normalize_concept_text("a\t\tb") == "a b"

    def test_normalize_crlf(self):
        assert normalize_concept_text("a\r\nb") == "a\nb"

    def test_normalize_cr(self):
        assert normalize_concept_text("a\rb") == "a\nb"

    def test_remove_zero_width_space(self):
        assert normalize_concept_text("a​b") == "ab"

    def test_remove_bom(self):
        assert normalize_concept_text("﻿hello") == "hello"

    def test_collapse_nbsp(self):
        assert normalize_concept_text("a  b") == "a b"

    def test_empty_string(self):
        assert normalize_concept_text("") == ""

    def test_none_returns_empty(self):
        assert normalize_concept_text(None) == ""

    def test_keep_newline(self):
        assert normalize_concept_text("a\nb") == "a\nb"


class TestComputeConceptHash:
    def test_deterministic(self):
        h1 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 159_000)
        h2 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 159_000)
        assert h1 == h2

    def test_normalization_invariance(self):
        h1 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 159_000)
        h2 = compute_concept_hash("  미니멀  데일리룩  ", "여성 의류", 159_000)
        assert h1 == h2

    def test_different_concept(self):
        h1 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 159_000)
        h2 = compute_concept_hash("스트릿 캐주얼", "여성 의류", 159_000)
        assert h1 != h2

    def test_different_category(self):
        h1 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 159_000)
        h2 = compute_concept_hash("미니멀 데일리룩", "남성 의류", 159_000)
        assert h1 != h2

    def test_different_price(self):
        h1 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 159_000)
        h2 = compute_concept_hash("미니멀 데일리룩", "여성 의류", 199_000)
        assert h1 != h2

    def test_returns_64_hex_chars(self):
        h = compute_concept_hash("test", "category", 10_000)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestComputePriceContextHash:
    def test_deterministic(self):
        h1 = compute_price_context_hash(
            "bls",
            "2024_annual",
            200_100,
            "bls_2024_apparel_services_annual_v1",
        )
        h2 = compute_price_context_hash(
            "bls",
            "2024_annual",
            200_100,
            "bls_2024_apparel_services_annual_v1",
        )
        assert h1 == h2

    def test_different_source(self):
        h1 = compute_price_context_hash("bls", "2024_annual", 200_100, "v1")
        h2 = compute_price_context_hash("other", "2024_annual", 200_100, "v1")
        assert h1 != h2

    def test_different_period(self):
        h1 = compute_price_context_hash("bls", "2024_annual", 200_100, "v1")
        h2 = compute_price_context_hash("bls", "2024_q4", 200_100, "v1")
        assert h1 != h2

    def test_different_denominator(self):
        h1 = compute_price_context_hash("bls", "2024_annual", 200_100, "v1")
        h2 = compute_price_context_hash("bls", "2024_annual", 200_101, "v1")
        assert h1 != h2

    def test_different_version(self):
        h1 = compute_price_context_hash("bls", "2024_annual", 200_100, "v1")
        h2 = compute_price_context_hash("bls", "2024_annual", 200_100, "v2")
        assert h1 != h2

    def test_different_extra_context(self):
        h1 = compute_price_context_hash(
            "bls_census_federal_reserve",
            "bls_2024+census_2024+scf_2022",
            200_100,
            "v1",
            extra_context={"census_2024_median_household_income_usd": 83_730},
        )
        h2 = compute_price_context_hash(
            "bls_census_federal_reserve",
            "bls_2024+census_2024+scf_2022",
            200_100,
            "v1",
            extra_context={"census_2024_median_household_income_usd": 84_000},
        )
        assert h1 != h2


class TestComputeCacheKey:
    BASE_ARGS = {
        "persona_id": "mock-001",
        "provider": "openai",
        "concept_hash": "a" * 64,
        "price_context_hash": "b" * 64,
        "model_name": "gpt-4o-mini",
        "temperature": 0.3,
        "prompt_version": "concept_eval_ko_v0_3",
        "schema_version": "eval_v0_1",
    }

    def test_deterministic(self):
        h1 = compute_cache_key(**self.BASE_ARGS)
        h2 = compute_cache_key(**self.BASE_ARGS)
        assert h1 == h2

    def test_provider_inclusion_changes_key(self):
        """DISCUSS-001 옵션 A 핵심 검증: provider 만 다르면 다른 cache_key."""
        h1 = compute_cache_key(**{**self.BASE_ARGS, "provider": "openai"})
        h2 = compute_cache_key(**{**self.BASE_ARGS, "provider": "anthropic"})
        assert h1 != h2

    def test_temperature_float_precision(self):
        """0.3 vs 0.30 동일 처리."""
        h1 = compute_cache_key(**{**self.BASE_ARGS, "temperature": 0.3})
        h2 = compute_cache_key(**{**self.BASE_ARGS, "temperature": 0.30})
        assert h1 == h2

    def test_different_persona(self):
        h1 = compute_cache_key(**self.BASE_ARGS)
        h2 = compute_cache_key(**{**self.BASE_ARGS, "persona_id": "mock-002"})
        assert h1 != h2

    def test_different_model_name(self):
        h1 = compute_cache_key(**self.BASE_ARGS)
        h2 = compute_cache_key(**{**self.BASE_ARGS, "model_name": "gpt-4o"})
        assert h1 != h2

    def test_different_temperature(self):
        h1 = compute_cache_key(**self.BASE_ARGS)
        h2 = compute_cache_key(**{**self.BASE_ARGS, "temperature": 0.7})
        assert h1 != h2

    def test_different_prompt_version(self):
        h1 = compute_cache_key(**self.BASE_ARGS)
        h2 = compute_cache_key(**{**self.BASE_ARGS, "prompt_version": "concept_eval_ko_v0_2"})
        assert h1 != h2

    def test_different_schema_version(self):
        h1 = compute_cache_key(**self.BASE_ARGS)
        h2 = compute_cache_key(**{**self.BASE_ARGS, "schema_version": "eval_v0_2"})
        assert h1 != h2

    def test_returns_64_hex_chars(self):
        h = compute_cache_key(**self.BASE_ARGS)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
