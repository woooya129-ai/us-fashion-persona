# SPDX-License-Identifier: AGPL-3.0-only
"""httpx-based LLM provider adapters.

Security contract:
- API keys are never stored in exception objects, log messages, repr, or str.
- Provider raw error bodies are never forwarded to the user.
- Requests are limited to known provider hosts.
- No subprocess, eval, exec, or pickle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from src.result_parser import EvaluationResult
from src.result_parser import validate_evaluation_payload as _validate_eval

logger = logging.getLogger(__name__)

Provider = Literal["openai", "anthropic", "google", "openai_compatible"]
AuthHeader = Literal["Authorization", "x-api-key", "x-goog-api-key"]

# Configured provider hosts. Custom arbitrary endpoints are intentionally not
# accepted; add hosts through config/code review before enabling a provider.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "api.deepseek.com",
        "dashscope-intl.aliyuncs.com",
        "dashscope-us.aliyuncs.com",
        "dashscope.aliyuncs.com",
        "cn-hongkong.dashscope.aliyuncs.com",
    }
)
_CONFIG_ALLOWED_HOSTS: set[str] = set()

EVALUATION_RESULT_KEYS: frozenset[str] = frozenset(
    {
        "persona_id",
        "sentiment",
        "interest_score",
        "price_burden",
        "main_reasons",
        "main_concerns",
        "confidence_note",
    }
)

EVALUATION_RESULT_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "persona_id": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "interest_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "price_burden": {
            "type": "string",
            "enum": ["low", "medium", "high", "very_high", "unknown"],
        },
        "main_reasons": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "main_concerns": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "confidence_note": {"type": "string", "maxLength": 300},
    },
    "required": sorted(EVALUATION_RESULT_KEYS),
    "additionalProperties": False,
}
GOOGLE_EVALUATION_RESULT_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "persona_id": {"type": "STRING"},
        "sentiment": {"type": "STRING", "enum": ["positive", "neutral", "negative"]},
        "interest_score": {"type": "INTEGER"},
        "price_burden": {
            "type": "STRING",
            "enum": ["low", "medium", "high", "very_high", "unknown"],
        },
        "main_reasons": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "main_concerns": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "confidence_note": {"type": "STRING"},
    },
    "required": sorted(EVALUATION_RESULT_KEYS),
    "propertyOrdering": [
        "persona_id",
        "sentiment",
        "interest_score",
        "price_burden",
        "main_reasons",
        "main_concerns",
        "confidence_note",
    ],
}

_BASE_BACKOFF_SECONDS: float = 1.0
_MAX_BACKOFF_SECONDS: float = 60.0

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.IGNORECASE)


def _validate_host(url: str) -> None:
    """Raise ValueError if URL host is not in the configured allowlist."""
    hostname = urlparse(url).hostname or ""
    allowed_hosts = get_allowed_hosts()
    if hostname not in allowed_hosts:
        raise ValueError(
            f"Domain '{hostname}' is not in the allowlist {sorted(allowed_hosts)}. "
            "Refusing to send request."
        )


def get_allowed_hosts() -> frozenset[str]:
    """Return built-in plus pricing-config-registered LLM API hosts."""
    return ALLOWED_HOSTS.union(_CONFIG_ALLOWED_HOSTS)


def register_allowed_api_base_urls(api_base_urls: Iterable[str | None]) -> None:
    """Register hosts from reviewed config entries as allowed LLM API targets."""
    for api_base_url in api_base_urls:
        if not api_base_url:
            continue
        parsed = urlparse(api_base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("LLM API base URL must use https.")
        _CONFIG_ALLOWED_HOSTS.add(parsed.hostname)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _validated_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise ValueError("LLM API base URL must use https.")
    _validate_host(base_url)
    return base_url.rstrip("/")


@dataclass(frozen=True)
class LLMRequest:
    """Parameters for a single LLM call.

    api_key is intentionally excluded from repr/str.
    """

    provider: Provider
    model_name: str
    api_key: str
    system: str
    developer: str | None
    user: str
    temperature: float
    max_output_tokens: int = 1200
    timeout_seconds: float = 60.0
    api_base_url: str | None = None
    auth_header: AuthHeader | str | None = None
    supports_json_object: bool = True
    supports_json_schema: bool = False
    supports_tool_use: bool = False

    def __repr__(self) -> str:
        return (
            f"LLMRequest(provider={self.provider!r}, model_name={self.model_name!r}, "
            f"api_base_url={self.api_base_url!r}, api_key=[REDACTED], "
            f"temperature={self.temperature!r})"
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
    "bad_request",
    "server_error",
    "structured_failed",
]


class LLMClientError(Exception):
    """Provider-agnostic LLM client error.

    Only safe fields are stored. API keys and raw provider bodies must not be
    passed into this exception.
    """

    def __init__(
        self,
        error_type: _ErrorType,
        user_message: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(error_type, user_message)
        self.error_type = error_type
        self.user_message = user_message
        self.retry_after_seconds = retry_after_seconds

    def __repr__(self) -> str:
        return f"LLMClientError(error_type={self.error_type!r}, user_message={self.user_message!r})"

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.user_message}"


def _safe_retry_after(headers: httpx.Headers) -> float | None:
    for header in ("retry-after", "x-ratelimit-reset-requests"):
        val = headers.get(header)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


_CONTEXT_LENGTH_PATTERNS: tuple[str, ...] = (
    "context_length",
    "context length",
    "context window",
    "maximum context",
    "too many tokens",
    "token limit",
    "prompt is too long",
    "input is too long",
)


def _is_context_length_error(resp: httpx.Response) -> bool:
    return any(pattern in resp.text.lower() for pattern in _CONTEXT_LENGTH_PATTERNS)


def _is_api_key_error(resp: httpx.Response) -> bool:
    text = resp.text.lower()
    return (
        "api key" in text
        or "apikey" in text
        or "authentication" in text
        or "unauthorized" in text
        or "permission" in text
    )


def _provider_error(provider_name: str, error_type: _ErrorType) -> str:
    messages = {
        "api_key_invalid": f"{provider_name} API key is invalid or unauthorized.",
        "rate_limit": f"{provider_name} rate limit was reached. Try again later.",
        "timeout": f"{provider_name} request timed out. Try again later.",
        "network": f"{provider_name} network request failed. Check your connection.",
        "context_length": "Input is too long. Reduce persona/context text and try again.",
        "bad_request": f"{provider_name} API request is invalid. Check model id and parameters.",
        "server_error": f"{provider_name} API server error. Try again later.",
        "structured_failed": "Structured output failed.",
    }
    return messages[error_type]


def _bad_request_error(provider_name: str) -> LLMClientError:
    return LLMClientError("bad_request", _provider_error(provider_name, "bad_request"))


def _handle_common_http_error(
    resp: httpx.Response,
    provider_name: str,
    *,
    auth_status_codes: tuple[int, ...] = (401, 403),
) -> None:
    if resp.status_code in auth_status_codes or (
        resp.status_code == 400 and _is_api_key_error(resp)
    ):
        raise LLMClientError(
            "api_key_invalid",
            _provider_error(provider_name, "api_key_invalid"),
        )
    if resp.status_code == 429:
        raise LLMClientError(
            "rate_limit",
            _provider_error(provider_name, "rate_limit"),
            retry_after_seconds=_safe_retry_after(resp.headers),
        )
    if resp.status_code == 400:
        if _is_context_length_error(resp):
            raise LLMClientError(
                "context_length",
                _provider_error(provider_name, "context_length"),
            )
        raise _bad_request_error(provider_name)
    if resp.status_code == 404:
        raise _bad_request_error(provider_name)
    if resp.status_code >= 500:
        raise LLMClientError("server_error", _provider_error(provider_name, "server_error"))
    if resp.status_code != 200:
        raise LLMClientError("server_error", _provider_error(provider_name, "server_error"))


def _build_openai_messages(req: LLMRequest) -> list[dict]:
    system_content = req.system
    if req.developer:
        system_content = f"{req.developer}\n\n{req.system}"
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": req.user},
    ]


def _json_schema_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "evaluation_result",
            "schema": EVALUATION_RESULT_RESPONSE_SCHEMA,
            "strict": True,
        },
    }


def _json_object_response_format() -> dict:
    return {"type": "json_object"}


def _usage_int(usage: dict, *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


class LLMProviderAdapter:
    provider: Provider
    provider_name: str
    default_api_base_url: str
    default_auth_header: AuthHeader

    def api_base_url(self, req: LLMRequest) -> str:
        return _validated_base_url(req.api_base_url or self.default_api_base_url)

    def auth_header(self, req: LLMRequest) -> str:
        return str(req.auth_header or self.default_auth_header)

    def request_url(self, req: LLMRequest) -> str:
        raise NotImplementedError

    def request_headers(self, req: LLMRequest) -> dict[str, str]:
        header_name = self.auth_header(req)
        auth_value = f"Bearer {req.api_key}" if header_name == "Authorization" else req.api_key
        return {
            header_name: auth_value,
            "Content-Type": "application/json",
        }

    def request_payload(self, req: LLMRequest) -> dict:
        raise NotImplementedError

    def parse_response(self, resp: httpx.Response) -> LLMRawResponse:
        raise NotImplementedError

    def structured_output_requested(self, req: LLMRequest) -> bool:
        return False

    async def call(self, req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
        url = self.request_url(req)
        _validate_host(url)
        try:
            resp = await client.post(
                url,
                headers=self.request_headers(req),
                json=self.request_payload(req),
                timeout=req.timeout_seconds,
            )
        except httpx.TimeoutException:
            raise LLMClientError(
                "timeout",
                _provider_error(self.provider_name, "timeout"),
            ) from None
        except httpx.RequestError:
            raise LLMClientError(
                "network",
                _provider_error(self.provider_name, "network"),
            ) from None

        raw = self.parse_response(resp)
        if self.structured_output_requested(req):
            return replace(raw, used_structured_output=True)
        return raw


class OpenAIAdapter(LLMProviderAdapter):
    provider: Provider = "openai"
    provider_name = "OpenAI"
    default_api_base_url = "https://api.openai.com/v1"
    default_auth_header: AuthHeader = "Authorization"

    def request_url(self, req: LLMRequest) -> str:
        return _join_url(self.api_base_url(req), "chat/completions")

    def request_payload(self, req: LLMRequest) -> dict:
        payload: dict = {
            "model": req.model_name,
            "messages": _build_openai_messages(req),
            "temperature": req.temperature,
            "max_tokens": req.max_output_tokens,
        }
        if req.supports_json_schema:
            payload["response_format"] = _json_schema_response_format()
        elif req.supports_json_object:
            payload["response_format"] = _json_object_response_format()
        return payload

    def structured_output_requested(self, req: LLMRequest) -> bool:
        return req.supports_json_object or req.supports_json_schema

    def parse_response(self, resp: httpx.Response) -> LLMRawResponse:
        _handle_common_http_error(resp, self.provider_name)
        try:
            body = resp.json()
            choice = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMClientError(
                "server_error",
                _provider_error(self.provider_name, "server_error"),
            ) from exc

        return LLMRawResponse(
            text=choice or "",
            input_tokens_actual=_usage_int(usage, "prompt_tokens", "input_tokens"),
            output_tokens_actual=_usage_int(usage, "completion_tokens", "output_tokens"),
            used_structured_output=False,
        )


class OpenAICompatibleAdapter(OpenAIAdapter):
    provider: Provider = "openai_compatible"
    provider_name = "OpenAI-compatible provider"
    default_api_base_url = ""

    def api_base_url(self, req: LLMRequest) -> str:
        if not req.api_base_url:
            raise ValueError("openai_compatible provider requires api_base_url from config.")
        return _validated_base_url(req.api_base_url)

    def request_payload(self, req: LLMRequest) -> dict:
        payload = super().request_payload(req)
        if req.supports_json_object:
            payload["response_format"] = _json_object_response_format()
        return payload


class AnthropicAdapter(LLMProviderAdapter):
    provider: Provider = "anthropic"
    provider_name = "Anthropic"
    default_api_base_url = "https://api.anthropic.com/v1"
    default_auth_header: AuthHeader = "x-api-key"

    def request_headers(self, req: LLMRequest) -> dict[str, str]:
        headers = super().request_headers(req)
        headers["anthropic-version"] = "2023-06-01"
        return headers

    def request_url(self, req: LLMRequest) -> str:
        return _join_url(self.api_base_url(req), "messages")

    def request_payload(self, req: LLMRequest) -> dict:
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
        if req.supports_tool_use:
            payload["tools"] = [
                {
                    "name": "evaluation_result",
                    "description": "Return only the structured evaluation result.",
                    "input_schema": EVALUATION_RESULT_RESPONSE_SCHEMA,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": "evaluation_result"}
        return payload

    def parse_response(self, resp: httpx.Response) -> LLMRawResponse:
        _handle_common_http_error(resp, self.provider_name)
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
        except (KeyError, ValueError, TypeError) as exc:
            raise LLMClientError(
                "server_error",
                _provider_error(self.provider_name, "server_error"),
            ) from exc

        return LLMRawResponse(
            text=text,
            input_tokens_actual=usage.get("input_tokens"),
            output_tokens_actual=usage.get("output_tokens"),
            used_structured_output=used_structured,
        )


class GoogleAdapter(LLMProviderAdapter):
    provider: Provider = "google"
    provider_name = "Google Gemini"
    default_api_base_url = "https://generativelanguage.googleapis.com/v1beta"
    default_auth_header: AuthHeader = "x-goog-api-key"

    def request_url(self, req: LLMRequest) -> str:
        return _join_url(self.api_base_url(req), f"models/{req.model_name}:generateContent")

    def request_payload(self, req: LLMRequest) -> dict:
        system_parts: list[dict] = [{"text": req.system}]
        if req.developer:
            system_parts.append({"text": req.developer})

        generation_config: dict = {
            "temperature": req.temperature,
            "maxOutputTokens": req.max_output_tokens,
        }
        if req.supports_json_object or req.supports_json_schema:
            generation_config["responseMimeType"] = "application/json"
        if req.supports_json_schema:
            generation_config["responseJsonSchema"] = EVALUATION_RESULT_RESPONSE_SCHEMA

        return {
            "system_instruction": {"parts": system_parts},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": req.user}],
                }
            ],
            "generationConfig": generation_config,
        }

    def structured_output_requested(self, req: LLMRequest) -> bool:
        return req.supports_json_object or req.supports_json_schema

    def parse_response(self, resp: httpx.Response) -> LLMRawResponse:
        _handle_common_http_error(resp, self.provider_name)
        try:
            body = resp.json()
            candidate = body["candidates"][0]
            text = candidate["content"]["parts"][0]["text"]
            usage = body.get("usageMetadata", {})
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMClientError(
                "server_error",
                _provider_error(self.provider_name, "server_error"),
            ) from exc

        return LLMRawResponse(
            text=text or "",
            input_tokens_actual=usage.get("promptTokenCount"),
            output_tokens_actual=usage.get("candidatesTokenCount"),
            used_structured_output=False,
        )


PROVIDER_REGISTRY: dict[Provider, LLMProviderAdapter] = {
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "google": GoogleAdapter(),
    "openai_compatible": OpenAICompatibleAdapter(),
}


async def call_openai(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    return await PROVIDER_REGISTRY["openai"].call(req, client)


async def call_anthropic(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    return await PROVIDER_REGISTRY["anthropic"].call(req, client)


async def call_google(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    return await PROVIDER_REGISTRY["google"].call(req, client)


async def call_openai_compatible(req: LLMRequest, client: httpx.AsyncClient) -> LLMRawResponse:
    return await PROVIDER_REGISTRY["openai_compatible"].call(req, client)


def _extract_json_fences(text: str) -> list[str]:
    return [m.group(1).strip() for m in _JSON_FENCE_RE.finditer(text)]


def _extract_json_objects(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for idx, char in enumerate(text):
        if start is None:
            if char == "{":
                start = idx
                depth = 1
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidates.append(text[start : idx + 1])
                start = None

    return candidates


def _coerce_json_object(obj: object, depth: int = 0) -> dict | None:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str) and depth < 2:
        return _load_json_object(obj, depth + 1)
    if isinstance(obj, list):
        first_dict: dict | None = None
        for item in obj:
            coerced = _coerce_json_object(item, depth + 1)
            if coerced is None:
                continue
            if first_dict is None:
                first_dict = coerced
            if EVALUATION_RESULT_KEYS.intersection(coerced):
                return coerced
        return first_dict
    return None


def _load_json_object(text: str, depth: int = 0) -> dict | None:
    try:
        obj = json.loads(text.strip().lstrip("\ufeff"))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return _coerce_json_object(obj, depth)


def _try_parse_json(text: str) -> dict | None:
    candidates = [text, *_extract_json_fences(text), *_extract_json_objects(text)]
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        parsed = _load_json_object(normalized)
        if parsed is not None:
            return parsed
    return None


def parse_evaluation_result(
    raw: LLMRawResponse,
    expected_persona_id: str,
) -> tuple[Literal["success", "parse_failed"], dict | None, str | None]:
    """Parse and validate provider output into EvaluationResult-compatible dict."""
    text = raw.text.strip() if raw.text else ""
    parsed = _try_parse_json(text)

    if parsed is None:
        return "parse_failed", None, "JSON parse failed"

    if parsed.get("persona_id") != expected_persona_id:
        logger.warning("LLM returned persona_id mismatch; replacing with expected value.")
        parsed = dict(parsed)
        parsed["persona_id"] = expected_persona_id

    try:
        result: EvaluationResult = _validate_eval(parsed)
    except ValidationError:
        logger.warning(
            "LLM response schema validation failed.",
            extra={"reason": "schema_validation"},
        )
        return "parse_failed", None, "schema validation failed"

    return "success", result.model_dump(), None


def _get_provider_fn(provider: Provider):
    if provider == "openai":
        return call_openai
    if provider == "anthropic":
        return call_anthropic
    if provider == "google":
        return call_google
    if provider == "openai_compatible":
        return call_openai_compatible
    raise ValueError(f"Unknown provider: {provider!r}")


def _clone_with_temperature(req: LLMRequest, temperature: float) -> LLMRequest:
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
        api_base_url=req.api_base_url,
        auth_header=req.auth_header,
        supports_json_object=req.supports_json_object,
        supports_json_schema=req.supports_json_schema,
        supports_tool_use=req.supports_tool_use,
    )


async def call_with_retry(
    req: LLMRequest,
    client: httpx.AsyncClient,
    max_retries: int = 2,
) -> LLMRawResponse:
    """Call the selected provider with backoff and low-temperature retry."""
    provider_fn = _get_provider_fn(req.provider)
    last_error: LLMClientError | None = None
    current_req = req

    for attempt in range(max_retries + 1):
        if attempt > 0 and last_error is not None:
            if last_error.error_type == "structured_failed":
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
            if exc.error_type in ("api_key_invalid", "context_length", "bad_request"):
                raise
            if attempt == max_retries:
                raise

    assert last_error is not None  # noqa: S101
    raise last_error
