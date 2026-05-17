from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.no_network

DOC_PATHS = (
    Path("README.md"),
    Path("README-KOR.md"),
    Path("docs/INSTALL.md"),
    Path("docs/INSTALL-KOR.md"),
    Path("docs/install/INSTALL-ENG.md"),
    Path("docs/install/INSTALL.md"),
)


def _doc_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_docs_do_not_limit_api_keys_to_three_providers():
    text = _doc_text()
    blocked = (
        "OpenAI, Anthropic, Gemini",
        "OpenAI, Anthropic, or Gemini",
        "OpenAI / Anthropic / Google Gemini",
        "selected OpenAI, Anthropic, or Gemini API server",
    )
    for phrase in blocked:
        assert phrase not in text


def test_docs_state_local_runtime_and_external_transfer_scope():
    readme = _read("README.md")
    readme_kr = _read("README-KOR.md")
    install = _read("docs/INSTALL.md")

    assert "SQLite cache" in readme
    assert "run locally on the user's machine" in readme
    assert "selected provider API server" in readme
    assert "The app does not save API keys" in readme
    assert "사용자 PC에서 로컬로 실행" in readme_kr
    assert "LLM provider API key" in install


def test_docs_state_config_based_endpoint_allowlist_risk():
    text = _doc_text()
    assert "config/pricing_config.yaml" in text
    assert "api_base_url" in text
    assert "allowed host set" in text or "허용 host set" in text


def test_docs_state_public_deployments_require_user_provider_key():
    text = _doc_text()

    assert "UFPS_REQUIRE_USER_PROVIDER_KEY=1" in text
    assert "shared owner LLM keys are not used" in text
    assert "owner-side provider key fallback" in text


def test_hf_space_frontmatter_is_configured():
    readme = _read("README.md")
    assert readme.startswith("---\n")
    frontmatter = yaml.safe_load(readme.split("---", 2)[1])

    assert frontmatter["title"] == "US Fashion Persona"
    assert frontmatter["sdk"] == "docker"
    assert frontmatter["app_port"] == 7860
    assert "app_file" not in frontmatter
    assert "sdk_version" not in frontmatter
    assert "nvidia/Nemotron-Personas-USA" in frontmatter["datasets"]


def test_hf_space_dockerfile_runs_streamlit_on_declared_port():
    dockerfile = _read("Dockerfile")

    assert "FROM python:3.11-slim" in dockerfile
    assert "pip install -r requirements.txt" in dockerfile
    assert '"streamlit", "run", "src/app.py"' in dockerfile
    assert '"--server.address=0.0.0.0"' in dockerfile
    assert '"--server.port=7860"' in dockerfile
    assert "EXPOSE 7860" in dockerfile


def test_project_version_matches_docs_and_pyproject():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    version = pyproject["project"]["version"]

    assert f"version-{version}" in _read("README.md")
    assert f"version-{version}" in _read("README-KOR.md")
    assert f"version: {version}" in _read("CITATION.cff")
