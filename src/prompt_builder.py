# SPDX-License-Identifier: AGPL-3.0-only
"""Prompt builder for concept_eval_ko (v0.2 / v0.3).

lock-in v1.2 §2.1 / public beta v3 prompt rubric:
  prompt_version is derived from the loaded prompt template (allowlist below).
    - "concept_eval_ko_v0_2" — US fashion pre-screening rubric (7 risk signals).
    - "concept_eval_ko_v0_3" — balanced synthetic persona reaction evaluator.
  schema_version stays "eval_v0_1" — EvaluationResult schema is unchanged.

cache invalidation contract (lock-in v1.2 §5.3.1):
  - prompt_version flows into compute_cache_key, so v0.2 and v0.3 cache rows
    never collide for the same persona/concept/model tuple.

PM v3 §15 prompt injection defence:
  - All user-controlled text is confined to the [USER_CONCEPT_INPUT] block.
  - Persona text is confined to [PERSONA]; economic context to [ECONOMIC_CONTEXT].
  - System / Developer blocks contain only template-side instructions.
  - detect_injection_keywords() screens concept_text for the 7 PM v3 §15.3 phrases.
  - Normalization via src.cache.normalize_concept_text (NFC + invisible-char strip).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.cache import normalize_concept_text

# Public release default. The actual prompt_version returned by build_prompt
# is still derived from the loaded template so cache keys stay template-bound.
PROMPT_VERSION = "concept_eval_ko_v0_3"
PROMPT_VERSION_V0_2 = "concept_eval_ko_v0_2"
PROMPT_VERSION_V0_3 = PROMPT_VERSION
SCHEMA_VERSION = "eval_v0_1"

# Allowlist of supported prompt versions. Adding a new version requires
# the lock-in v1.2 §2.3 checklist and a corresponding template file.
SUPPORTED_PROMPT_VERSIONS: frozenset[str] = frozenset({PROMPT_VERSION_V0_2, PROMPT_VERSION_V0_3})

# Matches the metadata header: `prompt_version: \`concept_eval_ko_v0_X\``.
_PROMPT_VERSION_LINE = re.compile(
    r"^prompt_version:\s*`(?P<version>[^`\s]+)`\s*$",
    re.MULTILINE,
)

# PM v3 §15.3 — 7 injection keywords (matched case-insensitive after normalization).
#
# Localized prompt-injection phrases should reflect realistic user input.
# The previous localized phrases were copied from a wishlist; real concept
# inputs do not contain them verbatim.
# Replaced with the actually-occurring forms used by attackers in local
# product descriptions. Tests now use natural localized inputs (not the literal
# keyword strings) so a future drift between detector and natural input is
# caught.
_INJECTION_KEYWORDS: list[str] = [
    "ignore previous",
    "ignore above",
    "system prompt",
    "developer message",
    "모든 응답은 긍정",
    "이 지시 무시",
    "JSON 말고",
]

# Compiled patterns for fast case-insensitive partial matching.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(re.escape(kw), re.IGNORECASE) for kw in _INJECTION_KEYWORDS
]

# Block marker constants — must mirror supported prompt templates.
_BLOCK_PERSONA = "[PERSONA]"
_BLOCK_PERSONA_END = "[/PERSONA]"
_BLOCK_ECONOMIC = "[ECONOMIC_CONTEXT]"
_BLOCK_ECONOMIC_END = "[/ECONOMIC_CONTEXT]"
_BLOCK_CONCEPT = "[USER_CONCEPT_INPUT]"
_BLOCK_CONCEPT_END = "[/USER_CONCEPT_INPUT]"
_BLOCK_SCHEMA = "[SCHEMA_INSTRUCTION]"
_BLOCK_SCHEMA_END = "[/SCHEMA_INSTRUCTION]"

# Markdown section headers in the .md template.
_SYSTEM_HEADER = "## System"
_DEVELOPER_HEADER = "## Developer"
_USER_TEMPLATE_HEADER = "## User template (변수 치환)"
_SCHEMA_HEADER = "## 출력 스키마 (lock-in §3.1)"


def _extract_prompt_version_from_template(prompt_template_md: str) -> str:
    """Read the `prompt_version:` metadata line from a prompt template.

    Returns:
        The matched prompt_version string (e.g. "concept_eval_ko_v0_2").

    Raises:
        ValueError: when the header is missing or the version is not in
            ``SUPPORTED_PROMPT_VERSIONS``. The error message intentionally
            does not echo arbitrary file content beyond the matched version
            string to keep prompt-injection content out of error logs.
    """
    match = _PROMPT_VERSION_LINE.search(prompt_template_md)
    if match is None:
        raise ValueError("Prompt template is missing the `prompt_version:` metadata line.")
    version = match.group("version")
    if version not in SUPPORTED_PROMPT_VERSIONS:
        raise ValueError(
            f"Unsupported prompt_version '{version}'. "
            f"Supported: {sorted(SUPPORTED_PROMPT_VERSIONS)}."
        )
    return version


def _extract_section(md: str, start_header: str, end_header: str | None) -> str:
    """Extract the body between two markdown headers (exclusive of headers).

    Returns stripped section text. If end_header is None, takes everything
    after start_header. Returns empty string if start_header is missing.
    """
    start_idx = md.find(start_header)
    if start_idx == -1:
        return ""
    content_start = md.find("\n", start_idx)
    if content_start == -1:
        return ""
    content_start += 1  # skip newline after header line

    if end_header is not None:
        end_idx = md.find(end_header, content_start)
        section = md[content_start:] if end_idx == -1 else md[content_start:end_idx]
    else:
        section = md[content_start:]

    return section.strip()


@dataclass(frozen=True)
class PromptParts:
    """Assembled prompt blocks for a single LLM call.

    Attributes:
        system: System-role instruction block.
        developer: Developer-role context block. None when the template
            does not provide a Developer section; in that case callers
            should prepend the value to system if the provider supports it.
        user: User-role message containing [PERSONA], [ECONOMIC_CONTEXT],
            [USER_CONCEPT_INPUT], and [SCHEMA_INSTRUCTION] blocks.
        prompt_version: Lock-in identifier derived from the loaded template
            metadata. Must be a member of ``SUPPORTED_PROMPT_VERSIONS``
            (currently "concept_eval_ko_v0_2" or "concept_eval_ko_v0_3").
        schema_version: Lock-in identifier — always "eval_v0_1".
    """

    system: str
    developer: str | None
    user: str
    prompt_version: str
    schema_version: str


def build_prompt(
    persona_id: str,
    persona_summary: str,
    persona_attributes_text: str,
    economic_context_text: str,
    category: str,
    concept_text: str,
    price_usd_cents: int,
    prompt_template_md: str,
) -> PromptParts:
    """Build PromptParts from normalised persona + concept inputs.

    Security contract (PM v3 §15):
      - concept_text appears ONLY inside [USER_CONCEPT_INPUT] ... [/USER_CONCEPT_INPUT].
      - persona_summary / persona_attributes_text appear ONLY inside [PERSONA].
      - economic_context_text appears ONLY inside [ECONOMIC_CONTEXT].
      - No user-controlled text leaks into the system or developer blocks.
      - Callers should call detect_injection_keywords(concept_text) first
        and warn the user if the result is non-empty.

    The function does not do any string formatting on the full template; it
    extracts the System/Developer sections verbatim and assembles the user
    block from typed parameters. This eliminates accidental {} substitution
    in any block.

    Args:
        persona_id: Persona identifier (e.g. UUID string).
        persona_summary: Free-text self-description from the persona.
        persona_attributes_text: Pre-formatted attributes string (e.g.
            "32세 / 서울 강남구 / 사무직 / 1인가구").
        economic_context_text: Pre-formatted price burden description from
            PM v3 §9.5.
        category: Fashion product category (e.g. "상의", "아우터").
        concept_text: User-supplied concept description — UNTRUSTED INPUT.
        price_usd_cents: Product price in US cents.
        prompt_template_md: Full contents of a supported prompt template
            (currently prompts/concept_eval_ko_v0_2.md or
            prompts/concept_eval_ko_v0_3.md). The returned prompt_version is
            derived from the template's metadata header so cache keys are
            isolated across versions.

    Returns:
        PromptParts with system, developer, user, prompt_version, schema_version.

    Raises:
        ValueError: when the template's prompt_version header is missing or
            references a version not in ``SUPPORTED_PROMPT_VERSIONS``.
    """
    prompt_version = _extract_prompt_version_from_template(prompt_template_md)
    system_text = _extract_section(prompt_template_md, _SYSTEM_HEADER, _DEVELOPER_HEADER)
    developer_text = _extract_section(prompt_template_md, _DEVELOPER_HEADER, _USER_TEMPLATE_HEADER)
    price_usd = price_usd_cents / 100

    user_lines: list[str] = [
        _BLOCK_PERSONA,
        f"- persona_id: {persona_id}",
        f"- 기본 정보: {persona_attributes_text}",
        f"- 자기 소개: {persona_summary}",
        _BLOCK_PERSONA_END,
        "",
        _BLOCK_ECONOMIC,
        economic_context_text,
        _BLOCK_ECONOMIC_END,
        "",
        _BLOCK_CONCEPT,
        f"카테고리: {category}",
        f"제품 가격: ${price_usd:,.2f} USD",
        f"컨셉: {concept_text}",
        _BLOCK_CONCEPT_END,
        "",
        _BLOCK_SCHEMA,
        "위 페르소나 입장에서 [USER_CONCEPT_INPUT] 의 패션 컨셉을 평가하세요.",
        "취향 적합성, 관심 이유, 망설임 요인, 리스크 신호를 균형 있게 보세요.",
        "출력은 아래 EvaluationResult JSON 형식만 허용됩니다. 다른 어떤 텍스트도 금지.",
        "",
        "{",
        f'  "persona_id": "{persona_id}",',
        '  "sentiment": "positive | neutral | negative",',
        '  "interest_score": 1부터 10까지 정수,',
        '  "price_burden": "low | medium | high | very_high | unknown",',
        '  "main_reasons": ["긍정/관심 이유 0개부터 5개까지"],',
        '  "main_concerns": ["망설임/거부/리스크 신호 0개부터 5개까지"],',
        '  "confidence_note": "응답 해석 시 주의점 300자 이내"',
        "}",
        _BLOCK_SCHEMA_END,
    ]
    user_text = "\n".join(user_lines)

    return PromptParts(
        system=system_text,
        developer=developer_text if developer_text else None,
        user=user_text,
        prompt_version=prompt_version,
        schema_version=SCHEMA_VERSION,
    )


def detect_injection_keywords(concept_text: str) -> list[str]:
    """Detect PM v3 §15.3 prompt injection keywords in concept_text.

    Normalisation (NFC + invisible-char strip via src.cache.normalize_concept_text)
    is applied before matching. Matching is case-insensitive partial-match.

    Args:
        concept_text: User-supplied concept description.

    Returns:
        List of matched keywords (subset of the seven canonical phrases).
        Empty list means no threats were detected. The UI layer should warn
        the user when the list is non-empty (PM v3 §15.3).
    """
    if not concept_text:
        return []
    normalized = normalize_concept_text(concept_text)
    matched: list[str] = []
    for keyword, pattern in zip(_INJECTION_KEYWORDS, _INJECTION_PATTERNS, strict=True):
        if pattern.search(normalized):
            matched.append(keyword)
    return matched
