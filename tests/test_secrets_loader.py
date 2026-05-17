"""Tests for secret loading without exposing real values."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.secrets_loader import (
    ANTHROPIC_KEY_VAR,
    DEEPSEEK_KEY_VAR,
    GOOGLE_KEY_VAR,
    GROQ_KEY_VAR,
    HF_TOKEN_VAR,
    OPENAI_KEY_VAR,
    QWEN_KEY_VAR,
    REQUIRE_USER_PROVIDER_KEY_VAR,
    LoadedSecretsStatus,
    get_hf_token,
    get_provider_key,
    load_secrets_from_env_path,
    provider_env_fallback_allowed,
    redact_for_log,
    require_user_provider_key,
)

pytestmark = pytest.mark.no_network


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch):
    """Keep credential-related environment variables isolated per test."""
    for var in (
        OPENAI_KEY_VAR,
        ANTHROPIC_KEY_VAR,
        GOOGLE_KEY_VAR,
        GROQ_KEY_VAR,
        DEEPSEEK_KEY_VAR,
        QWEN_KEY_VAR,
        HF_TOKEN_VAR,
        REQUIRE_USER_PROVIDER_KEY_VAR,
    ):
        monkeypatch.delenv(var, raising=False)
    yield


class TestLoadSecretsFromEnvPath:
    def test_missing_env_file_no_exception(self, tmp_path: Path):
        env_path = tmp_path / "nonexistent.env"
        status = load_secrets_from_env_path(env_path)
        assert isinstance(status, LoadedSecretsStatus)
        assert status.env_path_exists is False
        assert status.openai_present is False
        assert status.anthropic_present is False
        assert status.google_present is False
        assert status.groq_present is False
        assert status.deepseek_present is False
        assert status.qwen_present is False
        assert status.hf_token_present is False

    def test_env_present_after_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(OPENAI_KEY_VAR, "fake-openai-key-for-test")
        env_path = tmp_path / "fake.env"
        env_path.write_text("# placeholder\n", encoding="utf-8")
        status = load_secrets_from_env_path(env_path)
        assert status.openai_present is True
        assert status.env_path_exists is True

    def test_required_user_provider_key_hides_provider_env_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(REQUIRE_USER_PROVIDER_KEY_VAR, "1")
        monkeypatch.setenv(OPENAI_KEY_VAR, "fake-openai-key-for-test")
        monkeypatch.setenv(HF_TOKEN_VAR, "fake-hf-token")
        env_path = tmp_path / "fake.env"
        env_path.write_text("# placeholder\n", encoding="utf-8")

        status = load_secrets_from_env_path(env_path)

        assert status.openai_present is False
        assert status.hf_token_present is True

    def test_returned_status_does_not_contain_actual_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake = "fake-openai-key-12345-abc"
        monkeypatch.setenv(OPENAI_KEY_VAR, fake)
        env_path = tmp_path / "fake.env"
        status = load_secrets_from_env_path(env_path)
        for value in (str(status), repr(status)):
            assert fake not in value
            assert fake[:8] not in value


class TestGetProviderKey:
    def test_openai_present(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(OPENAI_KEY_VAR, "fake-openai")
        assert get_provider_key("openai") == "fake-openai"

    def test_openai_case_insensitive(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(OPENAI_KEY_VAR, "fake-openai")
        assert get_provider_key("OpenAI") == "fake-openai"

    def test_anthropic_present(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(ANTHROPIC_KEY_VAR, "fake-anthropic")
        assert get_provider_key("anthropic") == "fake-anthropic"

    def test_google_present(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(GOOGLE_KEY_VAR, "fake-google")
        assert get_provider_key("google") == "fake-google"

    def test_explicit_api_key_env_takes_precedence(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(GROQ_KEY_VAR, "fake-groq")
        assert get_provider_key("openai_compatible", api_key_env=GROQ_KEY_VAR) == "fake-groq"

    def test_required_user_provider_key_blocks_provider_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REQUIRE_USER_PROVIDER_KEY_VAR, "true")
        monkeypatch.setenv(OPENAI_KEY_VAR, "fake-openai")

        assert require_user_provider_key() is True
        assert provider_env_fallback_allowed() is False
        assert get_provider_key("openai") is None

    def test_required_user_provider_key_blocks_explicit_provider_env(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(REQUIRE_USER_PROVIDER_KEY_VAR, "1")
        monkeypatch.setenv(GROQ_KEY_VAR, "fake-groq")

        assert get_provider_key("openai_compatible", api_key_env=GROQ_KEY_VAR) is None

    def test_allow_env_fallback_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REQUIRE_USER_PROVIDER_KEY_VAR, "1")
        monkeypatch.setenv(OPENAI_KEY_VAR, "fake-openai")

        assert get_provider_key("openai", allow_env_fallback=True) == "fake-openai"

    def test_missing_returns_none(self):
        assert get_provider_key("openai") is None

    def test_empty_string_returns_none(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(OPENAI_KEY_VAR, "")
        assert get_provider_key("openai") is None

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="unknown provider"):
            get_provider_key("nonexistent-provider")


class TestGetHfToken:
    def test_present(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(HF_TOKEN_VAR, "fake-hf-token")
        assert get_hf_token() == "fake-hf-token"

    def test_missing(self):
        assert get_hf_token() is None


class TestRedactForLog:
    def test_none_returns_absent(self):
        assert redact_for_log(None) == "[ABSENT]"

    def test_secret_returns_redacted(self):
        assert redact_for_log("sk-fake-key-12345") == "[REDACTED]"

    def test_keep_argument_does_not_leak(self):
        secret = "sk-fake-key-12345"
        redacted = redact_for_log(secret, keep=4)
        assert secret not in redacted
        assert secret[:4] not in redacted
        assert secret[-4:] not in redacted
        assert redacted == "[REDACTED]"

    def test_empty_returns_absent(self):
        assert redact_for_log("") == "[ABSENT]"
