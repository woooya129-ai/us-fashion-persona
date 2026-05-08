#!/bin/bash
# 환경 격리가 올바른지 검증
# Public-safe runtime check: credentials must stay outside the repo root.

set -e

echo "환경 격리 검증..."

# 1. .env가 프로젝트 root에 없어야 함
if [ -f "./.env" ]; then
    echo "DANGER: 프로젝트 root에 .env 파일 발견"
    echo "조치: ~/secrets/us-fashion/.env로 이동"
    exit 1
fi

# 2. ~/secrets에 .env가 있어야 함
if [ ! -f "$HOME/secrets/us-fashion/.env" ]; then
    echo "WARN: ~/secrets/us-fashion/.env가 없습니다"
    echo "조치: 로컬 환경 파일을 만들거나 maintainer에게 설정 문의"
fi

# 3. .env 권한 확인 (Unix 환경)
if [ -f "$HOME/secrets/us-fashion/.env" ]; then
    if command -v stat &> /dev/null; then
        perms=$(stat -f "%A" "$HOME/secrets/us-fashion/.env" 2>/dev/null || stat -c "%a" "$HOME/secrets/us-fashion/.env" 2>/dev/null || echo "unknown")
        if [ "$perms" != "600" ] && [ "$perms" != "unknown" ]; then
            echo "WARN: ~/secrets/us-fashion/.env 권한이 600이 아닙니다 (현재: $perms)"
            echo "조치: chmod 600 ~/secrets/us-fashion/.env"
        fi
    fi
fi

# 4. .gitignore 존재 확인
if [ ! -f "./.gitignore" ]; then
    echo "DANGER: .gitignore가 없습니다"
    exit 1
fi

# 5. pre-commit hook 존재 확인 (uv run pre-commit install 후 생성됨)
if [ ! -f "./.git/hooks/pre-commit" ]; then
    echo "WARN: pre-commit hook이 없습니다"
    echo "조치: uv run pre-commit install"
fi

# 6. 위험 파일 패턴 확인
DANGER_FILES=$(find . \( -name "*.db" -o -name "*.sqlite" -o -name "*.parquet" -o -name "*.pkl" \) -not -path "./.git/*" -not -path "./.venv/*" 2>/dev/null || true)
if [ -n "$DANGER_FILES" ]; then
    echo "WARN: 데이터/캐시 파일 발견 (commit 전 .gitignore 확인)"
    echo "$DANGER_FILES"
fi

echo "PASS: 환경 격리 검증 통과"
