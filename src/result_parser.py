# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    persona_id: str
    sentiment: Literal["positive", "neutral", "negative"]
    interest_score: int = Field(ge=1, le=10)
    price_burden: Literal["low", "medium", "high", "very_high", "unknown"]
    main_reasons: list[str] = Field(min_length=0, max_length=5)
    main_concerns: list[str] = Field(min_length=0, max_length=5)
    confidence_note: str = Field(max_length=300)

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }


def validate_evaluation_payload(data: dict[str, Any]) -> EvaluationResult:
    """dict → EvaluationResult. 검증 실패 시 ValidationError."""
    return EvaluationResult.model_validate(data)


def parse_evaluation_result(data: dict[str, Any]) -> EvaluationResult:
    """Backward-compatible alias for validate_evaluation_payload."""
    return validate_evaluation_payload(data)
