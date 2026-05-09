# SPDX-License-Identifier: AGPL-3.0-only
"""UI asset paths, links, and small data-URI helpers."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from urllib.parse import quote

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
FABRIC_PATH: Path = REPO_ROOT / "design" / "hero-skyblue-fabric.png"
DIRECTION_BG_PATH: Path = REPO_ROOT / "design" / "direction-bg.png"
HF_DATASET_URL = "https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA"
PUBLIC_GITHUB_REPO_URL = "https://github.com/woooya129-ai/us-fashion-persona"
PUBLIC_GITHUB_LICENSE_URL = f"{PUBLIC_GITHUB_REPO_URL}/blob/main/LICENSE"

logger = logging.getLogger(__name__)
_MISSING_IMAGE_ASSET_LOGGED: set[Path] = set()

# GitHub Octicons "mark-github" (16x16), same path as docs/docs.html.
GITHUB_MARK_PATH = (
    "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59"
    ".4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37"
    "-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15"
    "-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21"
    " 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2"
    "-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2"
    "-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18"
    " 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04"
    " 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56"
    ".82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25"
    ".54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15"
    ".46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
)
GITHUB_MARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    f'<path fill="black" fill-rule="evenodd" d="{GITHUB_MARK_PATH}"/></svg>'
)
GITHUB_MARK_MASK_URI = f"data:image/svg+xml,{quote(GITHUB_MARK_SVG, safe='')}"
GITHUB_PILL_ICON_HTML = '<span class="kfps-pill-github" aria-hidden="true"></span>'


def _docs_static_base_url() -> str:
    """Base URL serving repo `/docs/` on the same machine (override with env)."""
    return os.environ.get("UFPS_STATIC_DOCS_BASE", "http://127.0.0.1:8510").rstrip("/")


def docs_page_url() -> str:
    return f"{_docs_static_base_url()}/docs/docs.html"


@st.cache_data(show_spinner=False)
def _image_data_uri(path: Path) -> str:
    if not path.exists():
        if path not in _MISSING_IMAGE_ASSET_LOGGED:
            logger.info(
                "Optional design asset not found; using fallback UI background: %s",
                path.relative_to(REPO_ROOT),
            )
            _MISSING_IMAGE_ASSET_LOGGED.add(path)
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
