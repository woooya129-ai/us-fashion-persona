"""src/pricing_config.py 테스트.

yaml.safe_load 만 사용 (Hard Rule §17 unsafe deserialization 금지).
"""

from pathlib import Path

import pytest

from src.pricing_config import ModelPricing, get_model_pricing, load_pricing_config

pytestmark = pytest.mark.no_network


SAMPLE_YAML = Path(__file__).parent / "fixtures" / "sample_pricing.yaml"


class TestLoadPricingConfig:
    def test_load_sample(self):
        config = load_pricing_config(SAMPLE_YAML)
        assert "gpt-4o-mini" in config
        assert "claude-sonnet-4-6" in config

    def test_load_sample_returns_model_pricing(self):
        config = load_pricing_config(SAMPLE_YAML)
        entry = config["gpt-4o-mini"]
        assert isinstance(entry, ModelPricing)
        assert entry.provider == "openai"
        assert entry.input_per_million_usd == 0.15
        assert entry.output_per_million_usd == 0.60

    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_pricing_config(tmp_path / "nonexistent.yaml")

    def test_root_not_dict_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_pricing_config(path)

    def test_missing_models_section_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("other_key: value\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_pricing_config(path)

    def test_empty_models_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("models: {}\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_pricing_config(path)

    def test_missing_provider_key_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "models:\n  m1:\n    input_per_million_usd: 1.0\n    output_per_million_usd: 2.0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="provider"):
            load_pricing_config(path)

    def test_negative_input_price_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "models:\n  m1:\n    provider: x\n"
            "    input_per_million_usd: -1.0\n    output_per_million_usd: 2.0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="non-negative"):
            load_pricing_config(path)

    def test_negative_output_price_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "models:\n  m1:\n    provider: x\n"
            "    input_per_million_usd: 1.0\n    output_per_million_usd: -2.0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="non-negative"):
            load_pricing_config(path)

    def test_non_numeric_price_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "models:\n  m1:\n    provider: x\n"
            "    input_per_million_usd: free\n    output_per_million_usd: 2.0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            load_pricing_config(path)

    def test_empty_provider_raises(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "models:\n  m1:\n    provider: ''\n"
            "    input_per_million_usd: 1.0\n    output_per_million_usd: 2.0\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="provider"):
            load_pricing_config(path)


class TestGetModelPricing:
    def test_lookup_existing(self):
        config = load_pricing_config(SAMPLE_YAML)
        pricing = get_model_pricing(config, "gpt-4o-mini")
        assert pricing.model_name == "gpt-4o-mini"

    def test_lookup_missing_raises_keyerror(self):
        config = load_pricing_config(SAMPLE_YAML)
        with pytest.raises(KeyError):
            get_model_pricing(config, "nonexistent-model")


class TestProductionConfigShape:
    def test_production_config_loads(self):
        production_path = Path(__file__).parent.parent / "config" / "pricing_config.yaml"
        config = load_pricing_config(production_path)
        assert len(config) >= 1
        assert "gpt-5.2" in config
        assert "gpt-5.2-pro" in config
        assert "gpt-5-mini" in config
        assert "gpt-5-nano" in config
        assert "claude-opus-4-7" in config
        assert "claude-sonnet-4-6" in config
        assert "claude-haiku-4-5" in config
        assert "gemini-3.1-flash-lite" in config
        assert "gemini-3.1-pro-preview" in config
        assert "gemini-3-flash-preview" in config
        assert "gemini-2.5-flash-lite" in config
        assert "groq-qwen-qwq" in config
        assert "deepseek-chat" in config
        assert "qwen3.6-plus" in config
        for _model_name, pricing in config.items():
            assert isinstance(pricing, ModelPricing)
            if pricing.has_pricing:
                assert pricing.input_per_million_usd is not None
                assert pricing.output_per_million_usd is not None
                assert pricing.input_per_million_usd >= 0
                assert pricing.output_per_million_usd >= 0
            else:
                assert pricing.reference_only is True
            assert pricing.provider

    def test_production_config_meta_section_ignored(self):
        """I4 해소 검증: _meta reserved 키 무시."""
        production_path = Path(__file__).parent.parent / "config" / "pricing_config.yaml"
        config = load_pricing_config(production_path)
        assert "_meta" not in config

    def test_production_config_has_provider_metadata(self):
        """I4 해소 검증: 신규 메타 필드 (provider_model_id / source_url / checked_at)."""
        production_path = Path(__file__).parent.parent / "config" / "pricing_config.yaml"
        config = load_pricing_config(production_path)
        for _model_name, pricing in config.items():
            assert pricing.provider_model_id, f"{_model_name} missing provider_model_id"
            assert pricing.api_base_url and pricing.api_base_url.startswith("https://")
            assert pricing.auth_header
            assert pricing.api_key_env
            assert isinstance(pricing.supports_json_object, bool)
            assert isinstance(pricing.supports_json_schema, bool)
            assert isinstance(pricing.supports_tool_use, bool)
            assert isinstance(pricing.verified, bool)
            assert pricing.source_url and pricing.source_url.startswith("https://")
            assert pricing.checked_at  # ISO date string

    def test_reference_only_models_can_omit_prices(self):
        production_path = Path(__file__).parent.parent / "config" / "pricing_config.yaml"
        config = load_pricing_config(production_path)
        for alias in ("groq-qwen-qwq", "deepseek-chat", "qwen3.6-plus"):
            pricing = config[alias]
            assert pricing.provider == "openai_compatible"
            assert pricing.input_per_million_usd is None
            assert pricing.output_per_million_usd is None
            assert pricing.reference_only is True
            assert pricing.verified is False


class TestModelPricingOptionalMeta:
    def test_optional_meta_default_none(self, tmp_path: Path):
        """기존 yaml (메타 없는) 호환."""
        path = tmp_path / "minimal.yaml"
        path.write_text(
            "models:\n  m1:\n    provider: test\n"
            "    input_per_million_usd: 1.0\n    output_per_million_usd: 2.0\n",
            encoding="utf-8",
        )
        config = load_pricing_config(path)
        assert config["m1"].provider_model_id is None
        assert config["m1"].source_url is None
        assert config["m1"].checked_at is None
