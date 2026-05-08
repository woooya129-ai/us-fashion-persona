# SPDX-License-Identifier: AGPL-3.0-only
"""Token + 비용 추정.

PM v3 §10.3 (token 추정), §10.4 (비용 계산).
실제 tokenizer 미사용 — provider 의존성 회피. v0.2 이후 tiktoken 등 도입 검토.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_OUTPUT_TOKENS_PER_PERSONA: int = 325  # PM v3 §10.3 권장 250-400 중간값
DEFAULT_CONCURRENCY: int = 5  # PM v3 §11.5
DEFAULT_LATENCY_LOW_SEC: int = 5  # PM v3 §10.3
DEFAULT_LATENCY_HIGH_SEC: int = 20


@dataclass(frozen=True)
class TokenEstimate:
    per_call_input_tokens: int
    per_call_output_tokens: int
    new_call_count: int
    cached_count: int

    @property
    def estimated_input_tokens_total(self) -> int:
        return self.per_call_input_tokens * self.new_call_count

    @property
    def estimated_output_tokens_total(self) -> int:
        return self.per_call_output_tokens * self.new_call_count


@dataclass(frozen=True)
class CostEstimate:
    estimated_input_tokens_total: int
    estimated_output_tokens_total: int
    estimated_cost_usd_low: float
    estimated_cost_usd_high: float
    estimated_time_min_low: float
    estimated_time_min_high: float


def count_tokens_approx(text: str) -> int:
    """간단 추정: 한국어/영어 혼합 텍스트 ≈ len(text) / 2 (보수적 상한).

    실제 tokenizer 미사용 — provider 의존성 회피.
    빈 문자열 → 0. 비어있지 않으면 최소 1 보장.
    """
    if not text:
        return 0
    return max(1, len(text) // 2)


def estimate_tokens(
    system_prompt_tokens: int,
    persona_tokens: int,
    concept_tokens: int,
    economic_context_tokens: int,
    schema_instruction_tokens: int,
    expected_output_tokens_per_persona: int,
    new_call_count: int,
    cached_count: int,
) -> TokenEstimate:
    """PM v3 §10.3 token 추정.

    per_call_input_tokens = 5개 부분 합산.
    음수 입력 → ValueError.
    """
    parts = (
        system_prompt_tokens,
        persona_tokens,
        concept_tokens,
        economic_context_tokens,
        schema_instruction_tokens,
        expected_output_tokens_per_persona,
        new_call_count,
        cached_count,
    )
    if any(p < 0 for p in parts):
        raise ValueError(f"all token / count inputs must be non-negative, got {parts}")

    per_call_input = (
        system_prompt_tokens
        + persona_tokens
        + concept_tokens
        + economic_context_tokens
        + schema_instruction_tokens
    )
    return TokenEstimate(
        per_call_input_tokens=per_call_input,
        per_call_output_tokens=expected_output_tokens_per_persona,
        new_call_count=new_call_count,
        cached_count=cached_count,
    )


def estimate_cost(
    token_estimate: TokenEstimate,
    model_input_price_per_million_usd: float,
    model_output_price_per_million_usd: float,
    concurrency: int = DEFAULT_CONCURRENCY,
    average_latency_seconds_low: int = DEFAULT_LATENCY_LOW_SEC,
    average_latency_seconds_high: int = DEFAULT_LATENCY_HIGH_SEC,
) -> CostEstimate:
    """PM v3 §10.4 비용 계산 + 시간 범위 추정.

    음수 단가 / 0 이하 concurrency / 음수 latency → ValueError.
    """
    if model_input_price_per_million_usd < 0 or model_output_price_per_million_usd < 0:
        raise ValueError("model price per million must be non-negative")
    if concurrency <= 0:
        raise ValueError(f"concurrency must be positive, got {concurrency}")
    if average_latency_seconds_low < 0 or average_latency_seconds_high < 0:
        raise ValueError("latency seconds must be non-negative")
    if average_latency_seconds_low > average_latency_seconds_high:
        raise ValueError("latency low must be <= high")

    input_total = token_estimate.estimated_input_tokens_total
    output_total = token_estimate.estimated_output_tokens_total

    cost_low = (
        input_total / 1_000_000 * model_input_price_per_million_usd
        + output_total / 1_000_000 * model_output_price_per_million_usd
    )
    cost_high = cost_low * 1.5  # 출력 토큰 상한 보정

    new_call_count = token_estimate.new_call_count
    time_sec_low = (new_call_count * average_latency_seconds_low) / concurrency
    time_sec_high = (new_call_count * average_latency_seconds_high) / concurrency

    return CostEstimate(
        estimated_input_tokens_total=input_total,
        estimated_output_tokens_total=output_total,
        estimated_cost_usd_low=cost_low,
        estimated_cost_usd_high=cost_high,
        estimated_time_min_low=time_sec_low / 60,
        estimated_time_min_high=time_sec_high / 60,
    )
