# SPDX-License-Identifier: AGPL-3.0-only
"""Thin httpx-based LLM clients for OpenAI, Anthropic, and Google Gemini.

Security contract (runtime data policy):
- API keys are NEVER stored in exception objects, log messages, repr, or str.
- Google ?key= URL parameter is NEVER included in error messages or logs.
- provider raw error bodies are NEVER forwarded to the user; only the
  bilingual user_message attached to LLMClientError is exposed.
- All requests go to ALLOWED_HOSTS only; any other target raises ValueError
  before issuing any HTTP call.
- No subprocess, eval, exec, or pickle.
- No real network calls in tests — use respx mocks.

PM v3 §16.2 four-step JSON parsing fallback:
  1. structured output / tool use first (used_structured_output flag)
  2. on structured failure → call_with_retry retries once with temperature=0.1
  3. on plain text → parse_evaluation_result extracts ```json ... ``` fences
  4. on all-fail → parse_failed status returned with a PII-free short summary

lock-in v1.2 §2.1: temperature default 0.3.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import httpx

from src.result_parser import (
    EvaluationResult,
)
from src.result_parser import (
    parse_evaluation_result as _validate_eval,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain allowlist — security policy hard rule
# ---------------------------------------------------------------------------
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
    }
)

Provider = Literal["openai", "anthropic", "google"]

# Retry timing constants (overridable via monkeypatch in tests).
_BASE_BACKOFF_SECONDS: float = 1.0
_MAX_BACKOFF_SECONDS: float = 60.0

# JSON fence extraction (matches ```json ... ``` and ``` ... ``` blocks).
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n```", re.IGNORECASE)


def _validate_host(url: str) -> None:
    """Raise ValueError if URL host is not in ALLOWED_HOSTS.

    The URL itself (which may contain ?key=...) is NOT included in the
    error message — only the parsed hostname.
    """
    hostname = urlparse(url).hostname or ""
    if hostname not in ALLOWED_HOSTS:
        raise ValueError(
            f"Domain '{hostname}' is not in the allowlist {sorted(ALLOWED_HOSTS)}. "
            "Refusing to send request."
        )


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMRequest:
    """Parameters for a single LLM call.

    api_key is intentionally excluded from __repr__ / __str__ to prevent
    accidental key leakage in logs or exception tracebacks. The dataclass
    decorator runs first; the methods below override the synthesised repr.
    """

    provider: Provider
    model_name: str
    api_key: str
    system: str
    developer: str | None
    user: str
    temperature: float
    max_output_tokens: int = 600
    timeout_seconds: float = 60.0

    def __repr__(self) -> str:
        return (
            f"LLMRequest(provider={self.provider!r}, model_name={self.model_name!r}, "
            f"api_key=[REDACTED], temperature={self.temperature!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class LLMRawResponse:
    """Raw text output from an LLM provider call."""

    text: str
    input_tokens_actual: int | None
    output_tokens_actual: int | None
    used_structured_output: bool


_ErrorType = Literal[
    "api_key_invalid",
    "rate_limit",
    "timeout",
    "network",
    "context_length",
    "server_error",
    "structured_failed",
]


class LLMClientError(Exception):
    """Provider-agnostic LLM client error.

    Design: api_key is NEVER passed to or stored in this exception.
    Only error_type and user_message are stored (and retry_after_seconds
    when applicable). repr/str emit only safe fields.
    """

    def __init__(
        self,
        error_type: _ErrorType,
        user_message: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        # Only safe args end up in self.args / repr.
        super().__init__(error_type, user_message)
        self.error_type = error_type
        self.user_message = user_message
        self.retry_after_seconds = retry_after_seconds

    def __repr__(self) -> str:
        return f"LLMClientError(error_type={self.error_type!r}, user_message={self.user_message!r})"

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.user_message}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_retry_after(headers: httpx.Headers) -> float | None:
    """Extract retry-after seconds from response headers, or None."""
    for header in ("retry-after", "x-ratelimit-reset-requests"):
        val = headers.get(header)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def _extract_json_fence(text: str) -> str | None:
    """Extract JSON from a ```json ... ``` or ``` ... ``` fence.

    Returns the inner content stripped, or None if no fence is found.
    """
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def _try_parse_json(text: str) -> dict | None:
    """Attempt JSON parse; return dict or None on failure (also None on non-dict)."""
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(obj, dict):
        return obj
    return None


def _build_openai_messages(req: LLMRequest) -> list[dict]:
    """Construct messages for OpenAI chat completion.

    Developer text, when present, is prepended to the system message for
    cross-version compatibility. We do not inject a separate 'developer'
    role to keep the surface area small for v0.1.
    """
    system_content = req.system
    if req.developer:
        system_content = f"{req.developer}\n\n{req.system}"
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": req.user},
    ]


# ---------------------------------------------------------------------------
# Provider call functions
# ---------------------------------------------------------------------------


async def call_openai(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    """Call OpenAI chat completions API.

    Uses response_format=json_object so the model is steered toward valid
    JSON. Authorization header is NEVER logged.
    """
    url = "https://api.openai.com/v1/chat/completions"
    _validate_host(url)

    headers = {
        "Authorization": f"Bearer {req.api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": req.model_name,
        "messages": _build_openai_messages(req),
        "temperature": req.temperature,
        "max_tokens": req.max_output_tokens,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=req.timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise LLMClientError(
            "timeout",
            "요청 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
        ) from exc
    except httpx.ConnectError as exc:
        raise LLMClientError(
            "network",
            "네트워크 연결에 실패했습니다. 인터넷 연결을 확인하세요.",
        ) from exc
    except httpx.RequestError as exc:
        raise LLMClientError(
            "network",
            "네트워크 요청 중 오류가 발생했습니다.",
        ) from exc

    return _handle_openai_response(resp)


def _handle_openai_response(resp: httpx.Response) -> LLMRawResponse:
    """Parse OpenAI HTTP response into LLMRawResponse or raise LLMClientError.

    Provider raw error bodies are not propagated to the user.
    """
    if resp.status_code == 401:
        raise LLMClientError(
            "api_key_invalid",
            "API 키가 유효하지 않습니다. OpenAI API 키를 확인하세요.",
        )
    if resp.status_code == 429:
        retry_after = _safe_retry_after(resp.headers)
        raise LLMClientError(
            "rate_limit",
            "요청 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
            retry_after_seconds=retry_after,
        )
    if resp.status_code == 400:
        raise LLMClientError(
            "context_length",
            "입력이 너무 깁니다. 컨셉 또는 페르소나 텍스트를 줄여주세요.",
        )
    if resp.status_code >= 500:
        raise LLMClientError(
            "server_error",
            "OpenAI 서버 오류가 발생했습니다. 잠시 후 다시 시도하세요.",
        )
    if resp.status_code != 200:
        raise LLMClientError(
            "server_error",
            f"OpenAI API 오류 (HTTP {resp.status_code}). 잠시 후 다시 시도하세요.",
        )

    try:
        body = resp.json()
        choice = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMClientError(
            "server_error",
            "OpenAI 응답 파싱에 실패했습니다.",
        ) from exc

    return LLMRawResponse(
        text=choice or "",
        input_tokens_actual=usage.get("prompt_tokens"),
        output_tokens_actual=usage.get("completion_tokens"),
        used_structured_output=True,
    )


async def call_anthropic(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    """Call Anthropic Messages API.

    x-api-key header is NEVER logged. Developer text becomes a second
    system block when present.
    """
    url = "https://api.anthropic.com/v1/messages"
    _validate_host(url)

    headers = {
        "x-api-key": req.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    system_blocks: list[dict] = [{"type": "text", "text": req.system}]
    if req.developer:
        system_blocks.append({"type": "text", "text": req.developer})

    payload: dict = {
        "model": req.model_name,
        "max_tokens": req.max_output_tokens,
        "temperature": req.temperature,
        "system": system_blocks,
        "messages": [{"role": "user", "content": req.user}],
    }

    try:
        resp = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=req.timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise LLMClientError(
            "timeout",
            "요청 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
        ) from exc
    except httpx.ConnectError as exc:
        raise LLMClientError(
            "network",
            "네트워크 연결에 실패했습니다. 인터넷 연결을 확인하세요.",
        ) from exc
    except httpx.RequestError as exc:
        raise LLMClientError(
            "network",
            "네트워크 요청 중 오류가 발생했습니다.",
        ) from exc

    return _handle_anthropic_response(resp)


def _handle_anthropic_response(resp: httpx.Response) -> LLMRawResponse:
    """Parse Anthropic HTTP response into LLMRawResponse or raise LLMClientError."""
    if resp.status_code == 401:
        raise LLMClientError(
            "api_key_invalid",
            "API 키가 유효하지 않습니다. Anthropic API 키를 확인하세요.",
        )
    if resp.status_code == 429:
        retry_after = _safe_retry_after(resp.headers)
        raise LLMClientError(
            "rate_limit",
            "요청 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
            retry_after_seconds=retry_after,
        )
    if resp.status_code == 400:
        raise LLMClientError(
            "context_length",
            "입력이 너무 깁니다. 컨셉 또는 페르소나 텍스트를 줄여주세요.",
        )
    if resp.status_code >= 500:
        raise LLMClientError(
            "server_error",
            "Anthropic 서버 오류가 발생했습니다. 잠시 후 다시 시도하세요.",
        )
    if resp.status_code != 200:
        raise LLMClientError(
            "server_error",
            f"Anthropic API 오류 (HTTP {resp.status_code}). 잠시 후 다시 시도하세요.",
        )

    try:
        body = resp.json()
        content_blocks = body.get("content", [])
        text = ""
        used_structured = False
        for block in content_blocks:
            if block.get("type") == "tool_use":
                text = json.dumps(block.get("input", {}), ensure_ascii=False)
                used_structured = True
                break
            if block.get("type") == "text":
                text = block.get("text", "")
        usage = body.get("usage", {})
    except (KeyError, ValueError) as exc:
        raise LLMClientError(
            "server_error",
            "Anthropic 응답 파싱에 실패했습니다.",
        ) from exc

    return LLMRawResponse(
        text=text,
        input_tokens_actual=usage.get("input_tokens"),
        output_tokens_actual=usage.get("output_tokens"),
        used_structured_output=used_structured,
    )


async def call_google(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    """Call Google Gemini generateContent API.

    The api_key travels in the URL query parameter per Google's API design.
    The full URL (with ?key=...) MUST NOT appear in any log or error
    message. Errors include only the host and HTTP status code.
    """
    base_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{req.model_name}:generateContent"
    )
    # Validate the host BEFORE appending the key.
    _validate_host(base_url)

    url_with_key = f"{base_url}?key={req.api_key}"

    system_parts: list[dict] = [{"text": req.system}]
    if req.developer:
        system_parts.append({"text": req.developer})

    payload: dict = {
        "system_instruction": {"parts": system_parts},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": req.user}],
            }
        ],
        "generationConfig": {
            "temperature": req.temperature,
            "maxOutputTokens": req.max_output_tokens,
            "responseMimeType": "application/json",
        },
    }

    try:
        resp = await client.post(
            url_with_key,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=req.timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise LLMClientError(
            "timeout",
            "요청 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
        ) from exc
    except httpx.ConnectError as exc:
        raise LLMClientError(
            "network",
            "네트워크 연결에 실패했습니다. 인터넷 연결을 확인하세요.",
        ) from exc
    except httpx.RequestError as exc:
        # Explicitly avoid forwarding any URL or args (key leakage).
        raise LLMClientError(
            "network",
            "네트워크 요청 중 오류가 발생했습니다.",
        ) from exc

    return _handle_google_response(resp)


def _handle_google_response(resp: httpx.Response) -> LLMRawResponse:
    """Parse Google Gemini HTTP response.

    Never include the response URL (which contains the api_key) in errors.
    """
    if resp.status_code in (400, 401, 403):
        raise LLMClientError(
            "api_key_invalid",
            "API 키가 유효하지 않습니다. Google AI API 키를 확인하세요.",
        )
    if resp.status_code == 429:
        retry_after = _safe_retry_after(resp.headers)
        raise LLMClientError(
            "rate_limit",
            "요청 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
            retry_after_seconds=retry_after,
        )
    if resp.status_code >= 500:
        raise LLMClientError(
            "server_error",
            "Google AI 서버 오류가 발생했습니다. 잠시 후 다시 시도하세요.",
        )
    if resp.status_code != 200:
        raise LLMClientError(
            "server_error",
            f"Google AI API 오류 (HTTP {resp.status_code}). 잠시 후 다시 시도하세요.",
        )

    try:
        body = resp.json()
        candidate = body["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]
        usage = body.get("usageMetadata", {})
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMClientError(
            "server_error",
            "Google AI 응답 파싱에 실패했습니다.",
        ) from exc

    return LLMRawResponse(
        text=text or "",
        input_tokens_actual=usage.get("promptTokenCount"),
        output_tokens_actual=usage.get("candidatesTokenCount"),
        used_structured_output=False,
    )


# ---------------------------------------------------------------------------
# Parse / validate LLM output (PM v3 §16.2 step 1, 3, 4)
# ---------------------------------------------------------------------------


def parse_evaluation_result(
    raw: LLMRawResponse,
    expected_persona_id: str,
) -> tuple[Literal["success", "parse_failed"], dict | None, str | None]:
    """PM v3 §16.2 fallback parse (steps 1, 3, 4).

    Step 2 (temperature retry) is owned by call_with_retry; this function
    handles structured output / fence extraction / final parse_failed.

    Steps:
      1. Direct JSON parse of raw.text
      3. Extract ```json ... ``` fence and parse
      4. Pydantic validation via src.result_parser; on any failure return
         parse_failed with a short PII-free summary.

    persona_id mismatch (LLM outputs a different ID): silently replaced
    with expected_persona_id and a warning is logged.

    Args:
        raw: LLMRawResponse from a provider call.
        expected_persona_id: The persona_id the response should contain.

    Returns:
        ('success', validated_dict, None) on success.
        ('parse_failed', None, short_error_summary) on failure.
        short_error_summary never contains PII or raw LLM text.
    """
    text = raw.text.strip() if raw.text else ""

    # Step 1: direct JSON parse.
    parsed = _try_parse_json(text)

    # Step 3: markdown fence extraction.
    if parsed is None:
        fenced = _extract_json_fence(text)
        if fenced:
            parsed = _try_parse_json(fenced)

    if parsed is None:
        return "parse_failed", None, "JSON 파싱 실패"

    # Persona ID alignment (silent fix-up — LLM sometimes echoes the wrong ID).
    if parsed.get("persona_id") != expected_persona_id:
        logger.warning("LLM returned persona_id mismatch; replacing with expected value.")
        parsed = dict(parsed)
        parsed["persona_id"] = expected_persona_id

    try:
        result: EvaluationResult = _validate_eval(parsed)
    except Exception:
        return "parse_failed", None, "스키마 검증 실패"

    return "success", result.model_dump(), None


# ---------------------------------------------------------------------------
# Retry wrapper (PM v3 §11.5, §16.2 step 2)
# ---------------------------------------------------------------------------


def _get_provider_fn(provider: Provider):
    """Return the async provider call function for a given provider."""
    if provider == "openai":
        return call_openai
    if provider == "anthropic":
        return call_anthropic
    if provider == "google":
        return call_google
    raise ValueError(f"Unknown provider: {provider!r}")


def _clone_with_temperature(req: LLMRequest, temperature: float) -> LLMRequest:
    """Return a new LLMRequest with a different temperature (frozen dataclass)."""
    return LLMRequest(
        provider=req.provider,
        model_name=req.model_name,
        api_key=req.api_key,
        system=req.system,
        developer=req.developer,
        user=req.user,
        temperature=temperature,
        max_output_tokens=req.max_output_tokens,
        timeout_seconds=req.timeout_seconds,
    )


async def call_with_retry(
    req: LLMRequest,
    client: httpx.AsyncClient,
    max_retries: int = 2,
) -> LLMRawResponse:
    """Call the appropriate provider with exponential backoff retry.

    Behaviour:
      - api_key_invalid / context_length: non-retryable, raise immediately.
      - rate_limit: respect retry_after_seconds when present, else exponential
        backoff with cap _MAX_BACKOFF_SECONDS.
      - structured_failed (PM v3 §16.2 step 2): retry once with
        temperature=0.1.
      - other errors: exponential backoff up to max_retries.

    Args:
        req: The LLM request parameters.
        client: An httpx.AsyncClient (caller manages lifecycle).
        max_retries: Maximum number of retry attempts after the first call
            (default 2 → up to 3 total attempts).

    Returns:
        LLMRawResponse on success.

    Raises:
        LLMClientError: After all retries are exhausted, or for non-retryable errors.
    """
    provider_fn = _get_provider_fn(req.provider)
    last_error: LLMClientError | None = None
    current_req = req

    for attempt in range(max_retries + 1):
        if attempt > 0 and last_error is not None:
            if last_error.error_type == "structured_failed":
                # PM v3 §16.2 step 2: temperature retry.
                current_req = _clone_with_temperature(req, 0.1)
            elif last_error.error_type == "rate_limit":
                wait = (
                    last_error.retry_after_seconds
                    if last_error.retry_after_seconds is not None
                    else min(
                        _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                        _MAX_BACKOFF_SECONDS,
                    )
                )
                await asyncio.sleep(wait)
            else:
                wait = min(
                    _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                    _MAX_BACKOFF_SECONDS,
                )
                await asyncio.sleep(wait)

        try:
            return await provider_fn(current_req, client)
        except LLMClientError as exc:
            last_error = exc
            if exc.error_type in ("api_key_invalid", "context_length"):
                # Non-retryable.
                raise
            if attempt == max_retries:
                raise
            # else continue loop

    # Defensive — loop above always returns or raises.
    assert last_error is not None  # noqa: S101 — internal invariant
    raise last_error
