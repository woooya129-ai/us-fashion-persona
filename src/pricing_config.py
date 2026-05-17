# SPDX-License-Identifier: AGPL-3.0-only
"""pricing_config.yaml 로딩.

PM v3 §10.4. yaml.safe_load 만 사용 (Hard Rule §17 unsafe deserialization 금지).
가격 단가는 코드 하드코딩 금지 — 모든 값은 YAML 파일에서 로딩.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


@dataclass(frozen=True)
class ModelPricing:
    model_name: str
    provider: str
    input_per_million_usd: float | None
    output_per_million_usd: float | None
    provider_model_id: str | None = None
    api_base_url: str | None = None
    auth_header: str | None = None
    api_key_env: str | None = None
    supports_json_object: bool = False
    supports_json_schema: bool = False
    supports_tool_use: bool = False
    reference_only: bool = False
    verified: bool = True
    source_url: str | None = None
    checked_at: str | None = None

    @property
    def has_pricing(self) -> bool:
        return self.input_per_million_usd is not None and self.output_per_million_usd is not None


_REQUIRED_KEYS: tuple[str, ...] = ("provider",)

_PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "openai": {
        "api_base_url": "https://api.openai.com/v1",
        "auth_header": "Authorization",
        "api_key_env": "OPENAI_API_KEY",
        "supports_json_object": True,
        "supports_json_schema": True,
        "supports_tool_use": True,
    },
    "anthropic": {
        "api_base_url": "https://api.anthropic.com/v1",
        "auth_header": "x-api-key",
        "api_key_env": "ANTHROPIC_API_KEY",
        "supports_json_object": False,
        "supports_json_schema": False,
        "supports_tool_use": True,
    },
    "google": {
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "auth_header": "x-goog-api-key",
        "api_key_env": "GOOGLE_API_KEY",
        "supports_json_object": True,
        "supports_json_schema": True,
        "supports_tool_use": False,
    },
    "openai_compatible": {
        "auth_header": "Authorization",
        "supports_json_object": True,
        "supports_json_schema": False,
        "supports_tool_use": False,
    },
}

_ALLOWED_AUTH_HEADERS: frozenset[str] = frozenset({"Authorization", "x-api-key", "x-goog-api-key"})


def _optional_str(entry: dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = entry.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be non-empty str")
    return value


def _optional_bool(entry: dict[str, Any], key: str, default: bool = False) -> bool:
    value = entry.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be bool")
    return value


def _validate_api_base_url(model_name: str, api_base_url: str | None) -> None:
    if api_base_url is None:
        return
    parsed = urlparse(api_base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"model '{model_name}' api_base_url must be an https URL")


def _validate_source_url(model_name: str, source_url: str | None) -> None:
    if source_url is None:
        return
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"model '{model_name}' source_url must be a URL")


def _validate_checked_at(model_name: str, checked_at: str | None) -> None:
    if checked_at is None:
        return
    try:
        date.fromisoformat(checked_at)
    except ValueError as exc:
        raise ValueError(f"model '{model_name}' checked_at must be YYYY-MM-DD") from exc


def _parse_price(model_name: str, entry: dict[str, Any], key: str) -> float | None:
    raw = entry.get(key)
    if raw is None:
        return None
    try:
        price = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"model '{model_name}' price must be numeric: {exc}") from exc
    if price < 0:
        raise ValueError(f"model '{model_name}' price must be non-negative")
    return price


def _validate_model_entry(model_name: str, entry: Any) -> ModelPricing:
    if not isinstance(entry, dict):
        raise ValueError(f"model '{model_name}' entry must be dict, got {type(entry).__name__}")

    for key in _REQUIRED_KEYS:
        if key not in entry:
            raise ValueError(f"model '{model_name}' missing required key: {key}")

    provider = entry["provider"]
    if not isinstance(provider, str) or not provider:
        raise ValueError(f"model '{model_name}' provider must be non-empty str")

    defaults = _PROVIDER_DEFAULTS.get(provider, {})
    merged = {**defaults, **entry}

    input_price = _parse_price(model_name, merged, "input_per_million_usd")
    output_price = _parse_price(model_name, merged, "output_per_million_usd")
    reference_only = _optional_bool(merged, "reference_only", False)
    if (input_price is None or output_price is None) and not reference_only:
        raise ValueError(
            f"model '{model_name}' missing price; set reference_only: true if pricing is unset"
        )

    api_base_url = _optional_str(merged, "api_base_url")
    _validate_api_base_url(model_name, api_base_url)
    auth_header = _optional_str(merged, "auth_header")
    if auth_header is not None and auth_header not in _ALLOWED_AUTH_HEADERS:
        raise ValueError(f"model '{model_name}' unsupported auth_header: {auth_header}")
    source_url = _optional_str(merged, "source_url")
    _validate_source_url(model_name, source_url)
    checked_at = _optional_str(merged, "checked_at")
    _validate_checked_at(model_name, checked_at)

    return ModelPricing(
        model_name=model_name,
        provider=provider,
        input_per_million_usd=input_price,
        output_per_million_usd=output_price,
        provider_model_id=_optional_str(merged, "provider_model_id"),
        api_base_url=api_base_url,
        auth_header=auth_header,
        api_key_env=_optional_str(merged, "api_key_env"),
        supports_json_object=_optional_bool(merged, "supports_json_object", False),
        supports_json_schema=_optional_bool(merged, "supports_json_schema", False),
        supports_tool_use=_optional_bool(merged, "supports_tool_use", False),
        reference_only=reference_only,
        verified=_optional_bool(merged, "verified", True),
        source_url=source_url,
        checked_at=checked_at,
    )


def load_pricing_config(yaml_path: Path) -> dict[str, ModelPricing]:
    """YAML → {model_name: ModelPricing}.

    yaml.safe_load 만 사용. Loader=Loader 절대 사용 금지.
    누락 키 / 음수 / 잘못된 타입 → ValueError.
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"pricing config not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"pricing config root must be dict, got {type(raw).__name__}")

    models_section = raw.get("models")
    if not isinstance(models_section, dict):
        raise ValueError("pricing config must have 'models' dict at root")

    result: dict[str, ModelPricing] = {}
    for model_name, entry in models_section.items():
        if not isinstance(model_name, str) or not model_name:
            raise ValueError(f"model name must be non-empty str, got {model_name!r}")
        # _meta 같은 reserved 키는 dict 아니면 무시 (I4 메타 섹션 호환).
        if model_name.startswith("_"):
            continue
        result[model_name] = _validate_model_entry(model_name, entry)

    if not result:
        raise ValueError("pricing config 'models' must not be empty")

    from src.llm_client import register_allowed_api_base_urls

    register_allowed_api_base_urls(pricing.api_base_url for pricing in result.values())

    return result


def get_model_pricing(config: dict[str, ModelPricing], model_name: str) -> ModelPricing:
    """모델명 lookup. 없으면 KeyError."""
    if model_name not in config:
        raise KeyError(f"model '{model_name}' not in pricing config")
    return config[model_name]
