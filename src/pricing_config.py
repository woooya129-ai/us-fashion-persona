# SPDX-License-Identifier: AGPL-3.0-only
"""pricing_config.yaml 로딩.

PM v3 §10.4. yaml.safe_load 만 사용 (Hard Rule §17 unsafe deserialization 금지).
가격 단가는 코드 하드코딩 금지 — 모든 값은 YAML 파일에서 로딩.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelPricing:
    model_name: str
    provider: str
    input_per_million_usd: float
    output_per_million_usd: float
    # I4 해소 (current-update-review 2026-05-01): 출처/확인일/공급자 모델 id 메타.
    # 기존 yaml 호환을 위해 모두 optional. 신규 작성 시 권장.
    provider_model_id: str | None = None
    source_url: str | None = None
    checked_at: str | None = None


_REQUIRED_KEYS: tuple[str, ...] = (
    "provider",
    "input_per_million_usd",
    "output_per_million_usd",
)


def _validate_model_entry(model_name: str, entry: Any) -> ModelPricing:
    if not isinstance(entry, dict):
        raise ValueError(f"model '{model_name}' entry must be dict, got {type(entry).__name__}")

    for key in _REQUIRED_KEYS:
        if key not in entry:
            raise ValueError(f"model '{model_name}' missing required key: {key}")

    provider = entry["provider"]
    if not isinstance(provider, str) or not provider:
        raise ValueError(f"model '{model_name}' provider must be non-empty str")

    try:
        input_price = float(entry["input_per_million_usd"])
        output_price = float(entry["output_per_million_usd"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"model '{model_name}' price must be numeric: {exc}") from exc

    if input_price < 0 or output_price < 0:
        raise ValueError(
            f"model '{model_name}' price must be non-negative "
            f"(input={input_price}, output={output_price})"
        )

    return ModelPricing(
        model_name=model_name,
        provider=provider,
        input_per_million_usd=input_price,
        output_per_million_usd=output_price,
        provider_model_id=entry.get("provider_model_id"),
        source_url=entry.get("source_url"),
        checked_at=entry.get("checked_at"),
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

    return result


def get_model_pricing(config: dict[str, ModelPricing], model_name: str) -> ModelPricing:
    """모델명 lookup. 없으면 KeyError."""
    if model_name not in config:
        raise KeyError(f"model '{model_name}' not in pricing config")
    return config[model_name]
