# SPDX-License-Identifier: AGPL-3.0-only
"""API key / HF token 로딩.

Runtime credential policy:
- 실제 키는 ~/secrets/us-fashion/.env (프로젝트 root 밖)
- 코드에 키 직접 작성 금지
- print/log 에 키 출력 금지 (일부라도)
- 에러 메시지에 키 노출 금지
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv 미설치 환경에서도 모듈 import 가능
    load_dotenv = None  # type: ignore[assignment]


SECRETS_ENV_PATH: Path = Path.home() / "secrets" / "us-fashion" / ".env"

# 아래 상수는 환경변수 *이름* 이며 실제 자격증명 값이 아니다.
# bandit B105 hardcoded_password_string false-positive 회피.
OPENAI_KEY_VAR = "OPENAI_API_KEY"  # nosec B105
ANTHROPIC_KEY_VAR = "ANTHROPIC_API_KEY"  # nosec B105
GOOGLE_KEY_VAR = "GOOGLE_API_KEY"  # nosec B105
HF_TOKEN_VAR = "HF_TOKEN"  # nosec B105


@dataclass(frozen=True)
class LoadedSecretsStatus:
    """자격증명 보유 여부만 노출. 실제 값은 절대 포함하지 않음."""

    openai_present: bool
    anthropic_present: bool
    hf_token_present: bool
    env_path: Path
    env_path_exists: bool
    google_present: bool = False


def load_secrets_from_env_path(env_path: Path = SECRETS_ENV_PATH) -> LoadedSecretsStatus:
    """~/secrets/us-fashion/.env → os.environ 로딩 + 보유 상태 반환.

    값 자체는 반환 또는 출력 금지. 호출자는 os.environ.get() 으로 직접 조회.
    파일 없어도 예외 발생 안 함 (사용자가 .env 작성 안 했을 수 있음 — UI 에서 안내).
    """
    env_path = Path(env_path)
    exists = env_path.is_file()

    if exists and load_dotenv is not None:
        load_dotenv(env_path, override=False)

    return LoadedSecretsStatus(
        openai_present=bool(os.environ.get(OPENAI_KEY_VAR)),
        anthropic_present=bool(os.environ.get(ANTHROPIC_KEY_VAR)),
        hf_token_present=bool(os.environ.get(HF_TOKEN_VAR)),
        env_path=env_path,
        env_path_exists=exists,
        google_present=bool(os.environ.get(GOOGLE_KEY_VAR)),
    )


def get_provider_key(provider: str) -> str | None:
    """provider 이름 → 환경변수 값. 값 자체는 호출 시점에만 사용, 저장/출력 금지."""
    mapping = {
        "openai": OPENAI_KEY_VAR,
        "anthropic": ANTHROPIC_KEY_VAR,
        "google": GOOGLE_KEY_VAR,
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
    """로그 출력용 redaction. keep > 0 이어도 최대 0자 (Hard Rule §2: 일부라도 출력 금지).

    None / 빈 문자열 → [ABSENT] (load_secrets 의 absent 의미와 동일).
    그 외 → [REDACTED]. keep 인자는 호출자 의도 명확화 용도.
    """
    if not secret:
        return "[ABSENT]"
    return "[REDACTED]"
