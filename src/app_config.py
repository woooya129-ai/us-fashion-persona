# SPDX-License-Identifier: AGPL-3.0-only
"""Shared app constants for Streamlit wiring, UI, and orchestration."""

from __future__ import annotations

from typing import Any

PRODUCT_CARD_EMPTY_PLACEHOLDER = "미입력"
PRODUCT_CARD_FIELD_ORDER: tuple[str, ...] = (
    "category",
    "price",
    "fit",
    "material",
    "color",
    "season",
    "occasion",
    "style_tone",
    "target_hypothesis",
    "description",
)
PRODUCT_CARD_FIELD_LABELS_KR: dict[str, str] = {
    "category": "카테고리",
    "price": "가격",
    "fit": "핏",
    "material": "소재",
    "color": "컬러",
    "season": "시즌",
    "occasion": "착용 상황",
    "style_tone": "스타일 톤",
    "target_hypothesis": "타깃 가설",
    "description": "브랜드 메시지/제품 설명",
}

APP_VERSION = "0.5.3"
DEFAULT_PRICE_CONTEXT_VERSION = "us_official_bls_2024_census_hinc02_2024_scf_2022_segments_v1"
DEFAULT_UI_LANGUAGE = "EN"
DEFAULT_TEMPERATURE = 0.3
MAX_SAMPLE_SIZE = 1000
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ESTIMATE_SYSTEM_PROMPT_TOKENS = 400
ESTIMATE_PERSONA_TOKENS = 350
ESTIMATE_SIDEBAR_CONCEPT_TOKENS = 160
ESTIMATE_ECONOMIC_CONTEXT_TOKENS = 140
ESTIMATE_SCHEMA_INSTRUCTION_TOKENS = 120
ESTIMATE_OUTPUT_TOKENS_PER_PERSONA = 325
MAX_OUTPUT_TOKENS_PER_PERSONA = 600
RUN_MODE_PRESETS: dict[str, dict[str, Any]] = {
    "quick": {"sample_size": 10, "temperature": 0.2},
    "balanced": {"sample_size": 30, "temperature": 0.3},
    "deep": {"sample_size": 60, "temperature": 0.3},
    "max": {"sample_size": 1000, "temperature": 0.3},
}
US_STATE_OPTIONS: tuple[str, ...] = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "PR",
)
OCCUPATION_KEYWORD_OPTIONS: tuple[str, ...] = (
    "사무",
    "전문",
    "관리",
    "서비스",
    "판매",
    "자영",
    "학생",
    "주부",
    "교육",
    "의료",
    "기술",
    "생산",
    "운전",
    "농림어업",
    "예술",
)
BEGINNER_MODEL_PRIORITY: tuple[str, ...] = (
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.3-chat-latest",
    "gpt-4o-mini",
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "gemini-flash",
    "gpt-4o",
)
