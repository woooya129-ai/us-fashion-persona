# SPDX-License-Identifier: AGPL-3.0-only
"""API key and HF token loading.

Runtime credential policy:
- Real keys live outside the repository, normally in ~/secrets/us-fashion/.env.
- Keys are never printed, logged, or returned by status helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional at import time.
    load_dotenv = None  # type: ignore[assignment]


SECRETS_ENV_PATH: Path = Path.home() / "secrets" / "us-fashion" / ".env"

# Environment variable names only. These constants are not credential values.
OPENAI_KEY_VAR = "OPENAI_API_KEY"
ANTHROPIC_KEY_VAR = "ANTHROPIC_API_KEY"
GOOGLE_KEY_VAR = "GOOGLE_API_KEY"
GROQ_KEY_VAR = "GROQ_API_KEY"
DEEPSEEK_KEY_VAR = "DEEPSEEK_API_KEY"
QWEN_KEY_VAR = "QWEN_API_KEY"
HF_TOKEN_VAR = "HF_TOKEN"
REQUIRE_USER_PROVIDER_KEY_VAR = "UFPS_REQUIRE_USER_PROVIDER_KEY"

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LoadedSecretsStatus:
    """Presence-only credential status. Actual values are never included."""

    openai_present: bool
    anthropic_present: bool
    hf_token_present: bool
    env_path: Path
    env_path_exists: bool
    google_present: bool = False
    groq_present: bool = False
    deepseek_present: bool = False
    qwen_present: bool = False


def require_user_provider_key() -> bool:
    """Return True when shared provider env-key fallback is disabled."""
    return os.environ.get(REQUIRE_USER_PROVIDER_KEY_VAR, "").strip().lower() in _TRUE_VALUES


def provider_env_fallback_allowed() -> bool:
    """Return whether LLM provider keys may be read from process env."""
    return not require_user_provider_key()


def load_secrets_from_env_path(env_path: Path = SECRETS_ENV_PATH) -> LoadedSecretsStatus:
    """Load external .env into os.environ and return presence-only status."""
    env_path = Path(env_path)
    exists = env_path.is_file()

    if exists and load_dotenv is not None:
        load_dotenv(env_path, override=False)

    provider_env_allowed = provider_env_fallback_allowed()

    return LoadedSecretsStatus(
        openai_present=provider_env_allowed and bool(os.environ.get(OPENAI_KEY_VAR)),
        anthropic_present=provider_env_allowed and bool(os.environ.get(ANTHROPIC_KEY_VAR)),
        hf_token_present=bool(os.environ.get(HF_TOKEN_VAR)),
        env_path=env_path,
        env_path_exists=exists,
        google_present=provider_env_allowed and bool(os.environ.get(GOOGLE_KEY_VAR)),
        groq_present=provider_env_allowed and bool(os.environ.get(GROQ_KEY_VAR)),
        deepseek_present=provider_env_allowed and bool(os.environ.get(DEEPSEEK_KEY_VAR)),
        qwen_present=provider_env_allowed and bool(os.environ.get(QWEN_KEY_VAR)),
    )


def get_provider_key(
    provider: str,
    api_key_env: str | None = None,
    *,
    allow_env_fallback: bool | None = None,
) -> str | None:
    """Return the provider key from env, without storing or logging it."""
    if allow_env_fallback is None:
        allow_env_fallback = provider_env_fallback_allowed()

    if not allow_env_fallback:
        return None

    if api_key_env:
        val = os.environ.get(api_key_env)
        return val if val else None

    mapping = {
        "openai": OPENAI_KEY_VAR,
        "anthropic": ANTHROPIC_KEY_VAR,
        "google": GOOGLE_KEY_VAR,
        "groq": GROQ_KEY_VAR,
        "deepseek": DEEPSEEK_KEY_VAR,
        "qwen": QWEN_KEY_VAR,
    }
    var = mapping.get(provider.lower())
    if var is None:
        raise ValueError(f"unknown provider: {provider}")
    val = os.environ.get(var)
    return val if val else None


def get_hf_token() -> str | None:
    val = os.environ.get(HF_TOKEN_VAR)
    return val if val else None


def redact_for_log(secret: str | None, keep: int = 0) -> str:
    """Redact secrets for logging. No partial key is ever exposed."""
    if not secret:
        return "[ABSENT]"
    return "[REDACTED]"
