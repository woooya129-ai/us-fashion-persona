# SPDX-License-Identifier: AGPL-3.0-only
"""hash 생성 (concept / price_context / cache_key).

lock-in v1.2 §5.3.1 canonical input 정의 정확 구현.
DISCUSS-001 옵션 A: cache_key 에 provider 포함.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

# 공백: ASCII space/tab + non-breaking space (U+00A0) + ideographic space (U+3000)
_WHITESPACE_RE = re.compile(r"[ \t 　]+")
# 보이지 않는 문자: zero-width 계열, bidi marks, word joiner, BOM
_INVISIBLE_RE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


def _serialize_canonical(payload: dict[str, Any]) -> str:
    """key 정렬 JSON, ensure_ascii=False, separators=(',', ':')."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_concept_text(raw: str) -> str:
    """PM v3 §12.3 정규화.

    - Unicode NFC 정규화
    - 보이지 않는 문자 제거 (zero-width, bidi marks, BOM)
    - 줄바꿈 통일 (\\r\\n / \\r → \\n)
    - 연속 공백 (스페이스/탭/non-breaking space/ideographic space) → 1개 스페이스
    - 앞뒤 공백 제거
    """
    if raw is None:
        return ""
    text = unicodedata.normalize("NFC", str(raw))
    text = _INVISIBLE_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def compute_concept_hash(concept_text: str, category: str, price_usd_cents: int) -> str:
    """lock-in §5.3.1 concept_hash.

    M2 해소 (current-update-review 2026-05-01): 이름은 'concept_hash' 지만
    payload 는 (concept_text + category + price_usd_cents) 3개 입력의 합쳐진 hash 다.
    이는 cache 안정성 목적 — concept text 만 같아도 카테고리/가격이 다르면
    별개 컨셉으로 취급. lock-in §5.3.1 명세 그대로.
    """
    payload = {
        "concept_text": normalize_concept_text(concept_text),
        "category": category,
        "price_usd_cents": int(price_usd_cents),
    }
    return _sha256_hex(_serialize_canonical(payload))


def compute_price_context_hash(
    source: str,
    period: str,
    denominator_usd_cents: int,
    price_context_version: str,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """lock-in §5.3.1 price_context_hash."""
    payload = {
        "source": source,
        "period": period,
        "denominator_usd_cents": int(denominator_usd_cents),
        "price_context_version": price_context_version,
    }
    if extra_context is not None:
        payload["extra_context"] = extra_context
    return _sha256_hex(_serialize_canonical(payload))


def compute_cache_key(
    persona_id: str,
    provider: str,
    concept_hash: str,
    price_context_hash: str,
    model_name: str,
    temperature: float,
    prompt_version: str,
    schema_version: str,
    api_base_url: str | None = None,
    provider_model_id: str | None = None,
) -> str:
    """lock-in §5.3.1 cache_key.

    Provider endpoint and provider model id are included so OpenAI-compatible
    providers cannot collide when they share a UI alias or model name.
    """
    payload = {
        "persona_id": persona_id,
        "provider": provider,
        "api_base_url": api_base_url or "",
        "concept_hash": concept_hash,
        "price_context_hash": price_context_hash,
        "model_name": model_name,
        "provider_model_id": provider_model_id or model_name,
        "temperature": float(temperature),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
    }
    return _sha256_hex(_serialize_canonical(payload))


def compute_legacy_cache_key_v1(
    persona_id: str,
    provider: str,
    concept_hash: str,
    price_context_hash: str,
    model_name: str,
    temperature: float,
    prompt_version: str,
    schema_version: str,
) -> str:
    """Pre-provider-endpoint cache key kept for one-read fallback compatibility."""
    payload = {
        "persona_id": persona_id,
        "provider": provider,
        "concept_hash": concept_hash,
        "price_context_hash": price_context_hash,
        "model_name": model_name,
        "temperature": float(temperature),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
    }
    return _sha256_hex(_serialize_canonical(payload))
