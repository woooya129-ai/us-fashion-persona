# SPDX-License-Identifier: AGPL-3.0-only
"""Streamlit entry point for the local screener UI.

The app is a thin orchestration layer. Core work stays in the existing
modules: data loading, persona filtering, prompt construction, LLM calls,
worker lifecycle, aggregation, and report rendering.
"""

# ruff: noqa: E402

from __future__ import annotations

import base64
import csv
import html
import io
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx
import streamlit as st
import streamlit.components.v1 as components

from src.aggregator import QualityCounts, aggregate
from src.async_runner import make_sync_evaluator_for_worker
from src.cache import (
    compute_cache_key,
    compute_concept_hash,
    compute_price_context_hash,
    normalize_concept_text,
)
from src.cost_estimator import (
    DEFAULT_CONCURRENCY,
    count_tokens_approx,
    estimate_cost,
    estimate_tokens,
)
from src.data_loader import (
    DEFAULT_HF_DATASET_ID,
    DEFAULT_HF_REVISION,
    DEFAULT_SPLIT,
    DatasetAccessError,
    LoadedDataset,
    load_huggingface_dataset,
    load_local_file,
    validate_local_path,
)
from src.db import get_connection, init_db
from src.economic_context import (
    BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS,
    BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD,
    CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD,
    FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD,
    FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD,
    OFFICIAL_US_CONTEXT_SOURCES,
    bls_income_ratio,
    economic_baseline_hash_payload,
    income_ratio,
    net_worth_ratio,
    price_burden_label,
    price_burden_ratio,
)
from src.job_manager import (
    RunMeta,
    create_job,
    load_job_stats,
    request_cancel,
)
from src.llm_client import (
    LLMClientError,
    LLMRequest,
    Provider,
    call_with_retry,
)
from src.llm_client import (
    parse_evaluation_result as parse_llm_evaluation_result,
)
from src.orchestrator import _load_and_sample as _orchestrator_load_and_sample
from src.persona_filter import (
    PersonaFilter,
    filter_summary,
)
from src.persona_normalizer import Persona
from src.pricing_config import ModelPricing, get_model_pricing, load_pricing_config
from src.prompt_builder import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    build_prompt,
    detect_injection_keywords,
)
from src.report_writer import render_csv, render_markdown, required_footer_text
from src.result_parser import EvaluationResult, parse_evaluation_result
from src.secrets_loader import get_provider_key, load_secrets_from_env_path
from src.worker import WorkerInput, start_worker_thread

APP_VERSION = "0.5.3"
DB_PATH: Path = REPO_ROOT / "cache" / "screener.db"
PRICING_CONFIG_PATH: Path = REPO_ROOT / "config" / "pricing_config.yaml"
PROMPT_TEMPLATE_PATH: Path = REPO_ROOT / "prompts" / "concept_eval_ko_v0_3.md"
FABRIC_PATH: Path = REPO_ROOT / "design" / "hero-skyblue-fabric.png"
DIRECTION_BG_PATH: Path = REPO_ROOT / "design" / "direction-bg.png"
HF_DATASET_URL = "https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA"
PUBLIC_GITHUB_REPO_URL = "https://github.com/woooya129-ai/us-fashion-persona"
PUBLIC_GITHUB_LICENSE_URL = f"{PUBLIC_GITHUB_REPO_URL}/blob/main/LICENSE"
logger = logging.getLogger(__name__)

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


PRODUCT_CARD_EMPTY_PLACEHOLDER = "미입력"
PRODUCT_CARD_FIELD_ORDER: tuple[str, ...] = (
    "category",
    "price",
    "fit",
    "material",
    "color",
    "season",
    "occasion",
    "style_tone",
    "target_hypothesis",
    "description",
)
PRODUCT_CARD_FIELD_LABELS_KR: dict[str, str] = {
    "category": "카테고리",
    "price": "가격",
    "fit": "핏",
    "material": "소재",
    "color": "컬러",
    "season": "시즌",
    "occasion": "착용 상황",
    "style_tone": "스타일 톤",
    "target_hypothesis": "타깃 가설",
    "description": "브랜드 메시지/제품 설명",
}

DEFAULT_PRICE_CONTEXT_VERSION = "us_official_bls_2024_census_2024_scf_2022_v1"
DEFAULT_UI_LANGUAGE = "EN"
DEFAULT_TEMPERATURE = 0.3
MAX_SAMPLE_SIZE = 1000
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
RUN_MODE_PRESETS: dict[str, dict[str, Any]] = {
    "quick": {"sample_size": 10, "temperature": 0.2},
    "balanced": {"sample_size": 30, "temperature": 0.3},
    "deep": {"sample_size": 60, "temperature": 0.3},
    "max": {"sample_size": 1000, "temperature": 0.3},
}
US_STATE_OPTIONS: tuple[str, ...] = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "PR",
)
OCCUPATION_KEYWORD_OPTIONS: tuple[str, ...] = (
    "사무",
    "전문",
    "관리",
    "서비스",
    "판매",
    "자영",
    "학생",
    "주부",
    "교육",
    "의료",
    "기술",
    "생산",
    "운전",
    "농림어업",
    "예술",
)
BEGINNER_MODEL_PRIORITY: tuple[str, ...] = (
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.3-chat-latest",
    "gpt-4o-mini",
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "gemini-flash",
    "gpt-4o",
)

ResultRow = dict[str, Any]
EvaluatorResult = dict[str, Any]
SyncEvaluator = Callable[[dict], EvaluatorResult]


UI_COPY: dict[str, dict[str, str]] = {
    "KR": {
        "nav_brand": "US Fashion",
        "nav_concept": "컨셉",
        "nav_panel": "패널",
        "nav_model": "모델",
        "nav_report": "리포트",
        "subnav_title": "Persona Screener",
        "subnav_local": "로컬 실행",
        "subnav_keys": "키 비공개",
        "subnav_panel": "합성 패널",
        "subnav_run": "실행",
        "hero_title": "US Fashion Persona Screener",
        "intro_badge": "NVIDIA built · based on USA synthetic-persona distributions",
        "intro_title": "Use USA synthetic personas to pre-check a fashion concept",
        "intro_body": (
            "Nemotron-Personas-USA is a fully synthetic persona dataset developed by NVIDIA. "
            "It provides USA synthetic personas with state, city, zipcode, occupation, "
            "and demographic fields for local fashion concept screening."
        ),
        "api_intro_title": "먼저 확인: API와 요금",
        "api_intro_body": (
            "실행하면 선택한 LLM provider API로 요청이 나가고, 입력/출력 토큰 단가와 "
            "패널 수로 비용을 추정해. 실제 청구는 provider 공식 요금과 계정 조건을 따라."
        ),
        "api_intro_1": "API key는 화면에 그대로 노출하지 않음",
        "api_intro_2": "패널 수가 늘수록 호출 수와 비용 증가",
        "api_intro_3": "실행 전 예상 비용 확인 체크 필요",
        "hero_main": "설문 전, 먼저 반응을 읽다",
        "hero_subtext": (
            "패션 컨셉을 AI 페르소나 패널을 통해 전문 설문이나 "
            "본조사 전 반응의 흐름을 빠르게 확인합니다."
        ),
        "hero_eyebrow": f"로컬 퍼블릭 베타 · v{APP_VERSION}",
        "hero_pill_1": "로컬 실행",
        "hero_pill_2": "원문 저장 없음",
        "hero_pill_3": "리포트 내보내기",
        "hero_pill_4": "🤗 nvidia/Nemotron-Personas-USA",
        "hero_pill_5": "GitHub",
        "hero_pill_docs": "Docs",
        "hero_pill_license": "AGPL-3.0-only",
        "hero_docs_aria": "정적 설명 페이지 (docs) 열기",
        "hero_license_aria": "GitHub LICENSE 파일 열기",
        "cost_confirm_toast": "실행하려면 예상 비용·시간 확인에 체크하세요.",
        "active_job_notice": "진행 중인 작업이 있어. 완료 또는 취소 후 새 실행이 가능해.",
        "guide_eyebrow": "쉬운 4단계 진행",
        "guide_title": "입력하고, 고르고, 실행하고, 읽으면 끝.",
        "guide_1_title": "컨셉 입력",
        "guide_1_body": "제품 설명과 가격을 적는다.",
        "guide_1_detail": "상품 특징, 가격, 타깃 가설만 적으면 첫 검토가 시작된다.",
        "guide_2_title": "패널 선택",
        "guide_2_body": "샘플 수와 조건을 고른다.",
        "guide_2_detail": "합성 페르소나 패널을 골라 어떤 사람들에게 물어볼지 정한다.",
        "guide_3_title": "비용 확인",
        "guide_3_body": "예상 호출과 비용을 확인한다.",
        "guide_3_detail": "실행 전 호출 수와 예상 비용을 먼저 보고 과한 실행을 막는다.",
        "guide_4_title": "결과 확인",
        "guide_4_body": "분포와 이유를 리포트로 받는다.",
        "guide_4_detail": "좋음, 애매함, 어려움 같은 반응 방향을 한 장 리포트처럼 읽는다.",
        "dataset_story_eyebrow": "데이터셋 이해",
        "dataset_story_title": "왜 이 데이터셋이 나왔나",
        "dataset_story_body": (
            "USA fashion screening needs more than generic global personas. State, city, "
            "occupation, lifestyle, and demographic context affect how a concept reads. "
            "This dataset gives a synthetic panel for early directional checks."
        ),
        "dataset_card_1_title": "USA persona fields",
        "dataset_card_1_body": (
            "Includes state, city, zipcode, occupation, age, sex, and lifestyle fields."
        ),
        "dataset_card_2_title": "완전 합성",
        "dataset_card_2_body": "실제 사람 명단이 아니라 분포를 반영한 인공 페르소나.",
        "dataset_card_3_title": "패션 가설 검토",
        "dataset_card_3_body": "이 도구는 일부 페르소나를 패널처럼 뽑아 컨셉 반응을 요약.",
        "section_project": "방향성을 잡아보세요",
        "section_project_caption": (
            "아래 칸에 컨셉, 가격, 타깃 가설을 넣으면 바로 검토 준비가 된다."
        ),
        "section_econ": "Economic Context",
        "section_econ_caption": (
            "BLS, Census, Federal Reserve 공식 기준으로 가격/소득/자산 맥락을 함께 본다."
        ),
        "section_run": "Run",
        "section_run_caption": "비용 확인 후 worker thread를 시작하고 진행률을 1초마다 갱신한다.",
        "setup": "설정",
        "quick_setup_header": "쉬운 설정",
        "quick_setup_caption": "처음이면 BALANCE만 고르고 바로 진행해도 된다.",
        "run_mode": "실행 방식",
        "mode_quick": "FAST",
        "mode_balanced": "BALANCE",
        "mode_deep": "HIGH",
        "mode_max": "MAX",
        "mode_quick_help": "10명 패널. 컨셉 초안 확인용.",
        "mode_balanced_help": "30명 패널. 기본 추천.",
        "mode_deep_help": "60명 패널. 더 넓게 확인.",
        "mode_max_help": "1000명 패널. 비용 상한선까지 확인.",
        "simple_summary": "{mode} · 합성 패널 {sample_size}명 · temperature {temperature}",
        "estimated_price_label": "Estimate",
        "token_price_basis": "{sample_size} personas",  # nosec B105
        "total_cost_label": "Final total",
        "total_cost_basis": "Input + output",
        "advanced_header": "Advanced",
        "advanced_caption": "모델, 데이터, 샘플링, 필터를 직접 조정한다.",
        "advanced_enable": "세부 설정 직접 조정",
        "concept_header": "컨셉 입력",
        "input_section_basics": "기본 정보",
        "input_section_style": "스타일/착용 맥락",
        "input_section_product": "제품 디테일",
        "input_section_target": "타깃/브랜드 가설",
        "project_name": "프로젝트명",
        "category": "제품 카테고리",
        "category_placeholder": "예: 여성 니트웨어",
        "price": "가격(USD)",
        "concept_text": "브랜드 메시지 / 제품 설명",
        "concept_placeholder": "예: 조용한 고급감의 미니멀 니트. 출근복과 주말복 겸용.",
        "fit": "핏",
        "fit_placeholder": "예: 슬림 / 레귤러 / 오버사이즈",
        "material": "소재",
        "material_placeholder": "예: 메리노 울 / 코튼 100%",
        "color": "컬러",
        "color_placeholder": "예: 차콜, 아이보리",
        "season": "시즌",
        "season_placeholder": "예: F/W, S/S, 올시즌",
        "occasion": "착용 상황",
        "occasion_placeholder": "예: 출근복, 주말 캐주얼",
        "style_tone": "스타일 톤",
        "style_tone_placeholder": "예: 미니멀, 고급감",
        "target": "타깃 가설",
        "target_placeholder": "예: 20대 후반-30대 초반 직장인 여성",
        "enter_card_title": "ENTER",
        "enter_card_subtitle": "",
        "enter_card_body": (
            "실행하면 LLM API 요청이 나가고 비용이 발생할 수 있어. "
            "실행 전 예상 비용 확인 체크가 필요해."
        ),
        "dataset_header": "데이터 소스",
        "source": "소스",
        "hf": "NVIDIA dataset",
        "local": "로컬 CSV/Parquet",
        "local_path": "로컬 파일 경로(data/ 하위 .csv 또는 .parquet)",
        "panel_header": "합성 패널",
        "sample_size": "샘플 수",
        "sample_help": "비용 보호 상한 {max_sample}명.",
        "age": "연령",
        "sex": "성별",
        "sampling_seed": "sampling-seed",
        "sampling_seed_help": (
            "같은 숫자를 쓰면 같은 조건에서 같은 페르소나 샘플을 다시 뽑기 위한 재현용 값이야."
        ),
        "state": "지역",
        "state_help": "Select up to 52 state or territory codes. Multiple choices are OR filters.",
        "occupation": "직업 키워드",
        "occupation_help": "최대 15개 대표 키워드를 선택할 수 있어. 여러 개면 OR로 부분 검색돼.",
        "model_header": "모델",
        "model_missing": "pricing_config.yaml에 모델이 없다.",
        "model": "모델",
        "api_key": "API KEY",
        "api_key_placeholder": "키를 붙여넣기",
        "api_key_help": "LLM API 요청용 키야. 입력값은 화면에 표시하지 않아.",
        "hf_token": "HF TOKEN",  # nosec B105
        "hf_token_placeholder": "토큰을 붙여넣기",  # nosec B105
        "hf_token_help": "Hugging Face 데이터 접근용 토큰이야. 공개 데이터셋은 보통 없어도 돼.",  # nosec B105
        "secrets_status_header": "API KEY / HF TOKEN 상태",
        "env_file_missing": ".env 파일 없음",
        "secret_present": "OK",  # nosec B105
        "secret_missing": "MISSING",  # nosec B105
        "openai_key_help": "OpenAI 모델 실행용 API KEY 상태야. 값은 표시하지 않아.",
        "anthropic_key_help": "Claude 모델 실행용 API KEY 상태야. 값은 표시하지 않아.",
        "google_key_help": "Gemini 모델 실행용 API KEY 상태야. 값은 표시하지 않아.",
        "hf_status_help": (
            "Hugging Face 데이터셋 접근용 TOKEN 상태야. 공개 데이터는 보통 없어도 돼."
        ),
        "price_context_header": "미국 공식 경제 맥락",
        "price_context_caption": (
            "BLS, Census, Federal Reserve 기준 참고값이며 "
            "개인별 실제 구매력이나 지불 의향이 아니다."
        ),
        "cost_header": "비용 / 시간 사전 추정",
        "need_concept": "컨셉을 먼저 입력해.",
        "new_calls": "신규 호출 예상",
        "estimated_cost": "예상 비용",
        "estimated_time": "예상 시간",
        "cost_caption": "토큰과 비용은 사전 추정치다. 실제 provider 과금과 다를 수 있다.",
        "debug_hash": "debug hash",
        "injection_warning": "프롬프트 인젝션 의심 문구가 감지됐다. 컨셉 문구를 다시 확인해.",
        "run_confirm_header": "실행 확인",
        "cost_confirm": "예상 비용과 시간이 발생할 수 있음을 확인했다.",
        "injection_confirm": "감지된 문구를 확인했고 그대로 실행한다.",
        "need_api_key": (
            "선택한 provider의 API KEY가 필요해. "
            "입력칸에 붙여넣거나 OS 환경변수/로컬 환경 파일에 넣어둔 값을 써."
        ),
        "run_button": "ENTER",
        "run_panel_body": (
            "실행하면 선택한 AI 모델이 합성 페르소나에게 컨셉을 물어봐. "
            "패널 수만큼 API 요청이 나가고 비용이 발생할 수 있어."
        ),
        "details_header": "자세히",
        "details_summary": "가격 기준, 예상 비용, 재현용 값을 확인한다.",
        "results_preview_header": "페르소나 의견 미리보기",
        "results_preview_body": "대표 의견 5개만 먼저 보여줘. 전체 결과는 엑셀용 파일로 내려받아.",
        "excel_download": "엑셀용 CSV 다운로드",
        "results_loading": "합성 페르소나 의견을 모으는 중",
        "persona_preview_empty": "아직 보여줄 성공 결과가 없다.",
        "persona_card_reasons": "좋게 본 점",
        "persona_card_concerns": "망설인 점",
        "persona_card_note": "한줄 의견",
        "status_header": "진행 상태",
        "job_missing": "현재 작업 정보를 찾을 수 없다.",
        "refresh": "Refresh",
        "cancel": "Cancel",
        "no_results": "저장된 결과가 없다.",
        "report_header": "리포트",
        "included": "분포 포함",
        "parse_failed": "파싱 실패",
        "api_failed": "API 실패",
        "md_download": "Markdown 다운로드",
        "csv_download": "CSV 다운로드",
        "md_preview": "Markdown 미리보기",
        "report_export_button": "리포트 내보내기",
        "report_tab_rendered": "미리보기",
        "report_tab_source": "Markdown 원문",
        "report_placeholder_title": "Markdown 리포트",
        "report_placeholder_body": "결과물이 이곳에 출력됩니다.",
        "report_placeholder_hint": "ENTER 실행 후 완료되면 자동으로 이 창으로 이동합니다.",
        "report_footer_disclaimer": (
            "이 결과는 합성 페르소나 기반의 pre-screening 참고용이야. "
            "실제 조사나 사업 판단을 대체하지 않아."
        ),
    },
    "EN": {
        "nav_brand": "US Fashion",
        "nav_concept": "Concept",
        "nav_panel": "Panel",
        "nav_model": "Model",
        "nav_report": "Report",
        "subnav_title": "Persona Screener",
        "subnav_local": "Local run",
        "subnav_keys": "Private keys",
        "subnav_panel": "Synthetic panel",
        "subnav_run": "Run",
        "hero_title": "US Fashion Persona Screener",
        "intro_badge": "Built by NVIDIA · grounded in USA synthetic-persona distributions",
        "intro_title": "Use USA synthetic personas to pre-check a fashion concept",
        "intro_body": (
            "Nemotron-Personas-USA is a fully synthetic persona dataset developed by NVIDIA. "
            "It provides USA synthetic personas with state, city, zipcode, occupation, "
            "and demographic fields for local fashion concept screening."
        ),
        "api_intro_title": "Check first: API and cost",
        "api_intro_body": (
            "When you run screening, requests go to the selected LLM provider API. "
            "The app estimates cost from input/output token prices and panel size. "
            "Actual billing follows the provider's official pricing and your account terms."
        ),
        "api_intro_1": "API keys are hidden on screen",
        "api_intro_2": "Larger panels mean more calls and cost",
        "api_intro_3": "Cost confirmation is required before running",
        "hero_main": "Read concept reaction direction before survey",
        "hero_subtext": (
            "Show a fashion concept to an AI persona panel and quickly check reaction flow "
            "before expert surveys or main research."
        ),
        "hero_eyebrow": f"Local public beta · v{APP_VERSION}",
        "hero_pill_1": "Local run",
        "hero_pill_2": "No raw concept storage",
        "hero_pill_3": "Report export",
        "hero_pill_4": "🤗 nvidia/Nemotron-Personas-USA",
        "hero_pill_5": "GitHub",
        "hero_pill_docs": "Docs",
        "hero_pill_license": "AGPL-3.0-only",
        "hero_docs_aria": "Open documentation page (docs)",
        "hero_license_aria": "Open GitHub LICENSE file",
        "cost_confirm_toast": "Check the cost/time confirmation box before running.",
        "active_job_notice": (
            "A job is already running. Finish or cancel it before starting a new run."
        ),
        "guide_eyebrow": "Simple 4-step flow",
        "guide_title": "Type it, choose a panel, run, then read.",
        "guide_1_title": "Describe",
        "guide_1_body": "Enter concept and price.",
        "guide_1_detail": "Start with the product idea, price, and target hypothesis.",
        "guide_2_title": "Choose panel",
        "guide_2_body": "Set sample size and filters.",
        "guide_2_detail": "Pick which synthetic personas should react to the concept.",
        "guide_3_title": "Check cost",
        "guide_3_body": "Review calls and estimate.",
        "guide_3_detail": "See expected calls and cost before any paid run.",
        "guide_4_title": "Read report",
        "guide_4_body": "Export response patterns.",
        "guide_4_detail": "Read the direction of responses as a compact report.",
        "dataset_story_eyebrow": "Dataset context",
        "dataset_story_title": "Why this dataset exists",
        "dataset_story_body": (
            "USA fashion screening needs more than generic global personas. State, city, "
            "occupation, lifestyle, and demographic context affect how a concept reads. "
            "This dataset gives a synthetic panel for early directional checks."
        ),
        "dataset_card_1_title": "USA persona fields",
        "dataset_card_1_body": (
            "Includes state, city, zipcode, occupation, age, sex, and lifestyle fields."
        ),
        "dataset_card_2_title": "Fully synthetic",
        "dataset_card_2_body": "Not a list of real people; personas mirror statistical patterns.",
        "dataset_card_3_title": "Fashion hypothesis check",
        "dataset_card_3_body": (
            "This tool samples personas as a panel and summarizes concept reactions."
        ),
        "section_project": "Shape the direction",
        "section_project_caption": (
            "Enter concept, price, and target hypothesis below to prepare a run."
        ),
        "section_econ": "Economic Context",
        "section_econ_caption": (
            "Price is contextualized with BLS, Census, and Federal Reserve official baselines."
        ),
        "section_run": "Run",
        "section_run_caption": (
            "Start a worker thread after cost confirmation and poll progress every second."
        ),
        "setup": "Setup",
        "quick_setup_header": "Quick setup",
        "quick_setup_caption": "For a first run, choose BALANCE and continue.",
        "run_mode": "Run mode",
        "mode_quick": "FAST",
        "mode_balanced": "BALANCE",
        "mode_deep": "HIGH",
        "mode_max": "MAX",
        "mode_quick_help": "10-person panel for rough drafts.",
        "mode_balanced_help": "30-person panel. Recommended default.",
        "mode_deep_help": "60-person panel for broader signal.",
        "mode_max_help": "1000-person panel. Uses the full cost guardrail.",
        "simple_summary": "{mode} · {sample_size} synthetic personas · temperature {temperature}",
        "estimated_price_label": "Estimate",
        "token_price_basis": "{sample_size} personas",  # nosec B105
        "total_cost_label": "Final total",
        "total_cost_basis": "Input + output",
        "advanced_header": "Advanced",
        "advanced_caption": "Directly control model, data source, sampling, and filters.",
        "advanced_enable": "Customize advanced settings",
        "concept_header": "Concept",
        "input_section_basics": "Basics",
        "input_section_style": "Style and Wearing Context",
        "input_section_product": "Product Details",
        "input_section_target": "Target and Brand Hypothesis",
        "project_name": "Project name",
        "category": "Product category",
        "category_placeholder": "e.g. women's knitwear",
        "price": "Price (USD)",
        "concept_text": "Brand message / product description",
        "concept_placeholder": "e.g. minimal knitwear for weekday office and weekend wear.",
        "fit": "Fit",
        "fit_placeholder": "e.g. slim / regular / oversize",
        "material": "Material",
        "material_placeholder": "e.g. merino wool / 100% cotton",
        "color": "Color",
        "color_placeholder": "e.g. charcoal, ivory",
        "season": "Season",
        "season_placeholder": "e.g. F/W, S/S, all-season",
        "occasion": "Occasion",
        "occasion_placeholder": "e.g. office, weekend casual",
        "style_tone": "Style tone",
        "style_tone_placeholder": "e.g. minimal, refined",
        "target": "Target hypothesis",
        "target_placeholder": "e.g. women in their late 20s to early 30s",
        "enter_card_title": "ENTER",
        "enter_card_subtitle": "",
        "enter_card_body": (
            "Running can send LLM API requests and incur cost. "
            "Cost confirmation is required before running."
        ),
        "dataset_header": "Data source",
        "source": "Source",
        "hf": "NVIDIA dataset",
        "local": "Local CSV/Parquet",
        "local_path": "Local file path under data/ (.csv or .parquet)",
        "panel_header": "Synthetic panel",
        "sample_size": "Sample size",
        "sample_help": "Cost guardrail: up to {max_sample} personas.",
        "age": "Age",
        "sex": "Sex",
        "sampling_seed": "sampling-seed",
        "sampling_seed_help": (
            "A reproducibility value. Reusing the same number keeps sampling stable "
            "under the same conditions."
        ),
        "state": "Region",
        "state_help": "Select up to 52 state or territory codes. Multiple choices are OR filters.",
        "occupation": "Occupation keyword",
        "occupation_help": (
            "Select up to 15 representative keywords. Multiple choices are OR partial matches."
        ),
        "model_header": "Model",
        "model_missing": "No models in pricing_config.yaml.",
        "model": "Model",
        "api_key": "API KEY",
        "api_key_placeholder": "Paste key",
        "api_key_help": "Used for LLM API requests. Typed values are hidden on screen.",
        "hf_token": "HF TOKEN",  # nosec B105
        "hf_token_placeholder": "Paste token",  # nosec B105
        "hf_token_help": (
            "Used for Hugging Face data access. Public datasets usually do not need it."  # nosec B105
        ),
        "secrets_status_header": "API KEY / HF TOKEN status",
        "env_file_missing": ".env file not found",
        "secret_present": "OK",  # nosec B105
        "secret_missing": "MISSING",  # nosec B105
        "openai_key_help": "OpenAI API KEY status for model calls. Values are never shown.",
        "anthropic_key_help": "Claude API KEY status for model calls. Values are never shown.",
        "google_key_help": "Gemini API KEY status for model calls. Values are never shown.",
        "hf_status_help": (
            "HF TOKEN status for Hugging Face data access. Public data usually works without it."
        ),
        "price_context_header": "U.S. official economic context",
        "price_context_caption": (
            "BLS, Census, and Federal Reserve baselines only. This is not real purchasing "
            "power or purchase intent."
        ),
        "cost_header": "Cost / time estimate",
        "need_concept": "Enter a concept first.",
        "new_calls": "New calls",
        "estimated_cost": "Estimated cost",
        "estimated_time": "Estimated time",
        "cost_caption": "Token and cost values are estimates. Actual provider billing may differ.",
        "debug_hash": "debug hash",
        "injection_warning": (
            "Possible prompt-injection text detected. Review the concept before running."
        ),
        "run_confirm_header": "Run confirmation",
        "cost_confirm": "I understand this may incur estimated cost and time.",
        "injection_confirm": "I reviewed the detected text and want to run anyway.",
        "need_api_key": (
            "The selected provider needs an API KEY. "
            "Paste one here or use one set in your OS environment or local env file."
        ),
        "run_button": "ENTER",
        "run_panel_body": (
            "Running asks the selected AI model to evaluate the concept through synthetic "
            "personas. API requests and cost can increase with panel size."
        ),
        "details_header": "Details",
        "details_summary": "Check price context, cost estimate, and reproducibility values.",
        "results_preview_header": "Persona opinion preview",
        "results_preview_body": (
            "Shows 5 representative opinions first. Download the full data for Excel."
        ),
        "excel_download": "Download CSV for Excel",
        "results_loading": "Collecting synthetic persona opinions",
        "persona_preview_empty": "No successful opinion rows to preview yet.",
        "persona_card_reasons": "Reasons",
        "persona_card_concerns": "Concerns",
        "persona_card_note": "Note",
        "status_header": "Progress",
        "job_missing": "Current job record was not found.",
        "refresh": "Refresh",
        "cancel": "Cancel",
        "no_results": "No saved results yet.",
        "report_header": "Report",
        "included": "Included",
        "parse_failed": "Parse failed",
        "api_failed": "API failed",
        "md_download": "Download Markdown",
        "csv_download": "Download CSV",
        "md_preview": "Markdown preview",
        "report_export_button": "Export report",
        "report_tab_rendered": "Preview",
        "report_tab_source": "Markdown source",
        "report_placeholder_title": "Markdown report",
        "report_placeholder_body": "Results will appear here.",
        "report_placeholder_hint": "After ENTER completes, the page scrolls to this panel.",
        "report_footer_disclaimer": (
            "This result is reference-only pre-screening based on synthetic personas. "
            "It does not replace real research or business decisions."
        ),
    },
}


@dataclass(frozen=True)
class RunReport:
    report_markdown: str
    report_csv: str
    quality: QualityCounts


APPLE_UI_CSS = """
<style>
:root {
  --kfps-primary: #0066cc;
  --kfps-primary-focus: #0071e3;
  --kfps-primary-on-dark: #2997ff;
  --kfps-ink: #1d1d1f;
  --kfps-muted: #7a7a7a;
  --kfps-muted-dark: #cccccc;
  --kfps-hairline: #e0e0e0;
  --kfps-canvas: #ffffff;
  --kfps-parchment: #f5f5f7;
  --kfps-pearl: #fafafc;
  --kfps-dark: #272729;
  --kfps-black: #000000;
}

.stApp {
  background: var(--kfps-canvas);
  color: var(--kfps-ink);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}

[data-testid="stAppViewContainer"] {
  background: var(--kfps-canvas);
}

[data-testid="stHeader"] {
  background: rgba(245, 245, 247, 0.82);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.block-container {
  max-width: 1180px;
  padding-top: 0;
  padding-bottom: 64px;
}

.kfps-global-nav {
  width: 100vw;
  height: 44px;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  background: var(--kfps-black);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  font-size: 12px;
  line-height: 1;
  letter-spacing: -0.12px;
}

.kfps-global-nav span:first-child {
  font-weight: 600;
}

.kfps-subnav {
  width: 100vw;
  min-height: 52px;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  background: rgba(245, 245, 247, 0.88);
  color: var(--kfps-ink);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: saturate(180%) blur(20px);
  font-size: 14px;
  letter-spacing: -0.224px;
}

.kfps-subnav strong {
  font-size: 21px;
  line-height: 1.19;
  letter-spacing: 0.231px;
}

.kfps-subnav .kfps-buy-chip {
  background: var(--kfps-primary);
  color: #ffffff;
  border-radius: 9999px;
  padding: 7px 15px;
}

.kfps-hero {
  width: 100vw;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  padding: 80px 24px 72px;
  background: var(--kfps-parchment);
  color: var(--kfps-ink);
  text-align: center;
}

.kfps-hero h1 {
  margin: 0;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: clamp(34px, 5vw, 56px);
  font-weight: 600;
  line-height: 1.07;
  letter-spacing: -0.28px;
}

.kfps-hero p {
  max-width: 760px;
  margin: 17px auto 0;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: clamp(21px, 2.6vw, 28px);
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: 0.196px;
}

.kfps-hero .kfps-hero-pills {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 24px;
}

.kfps-hero .kfps-pill {
  border: 1px solid var(--kfps-primary);
  border-radius: 9999px;
  color: var(--kfps-primary);
  background: #ffffff;
  padding: 10px 18px;
  font-size: 14px;
  line-height: 1.29;
  letter-spacing: -0.224px;
}

.kfps-hero .kfps-pill-primary {
  background: var(--kfps-primary);
  color: #ffffff;
}

.kfps-section-band {
  width: 100vw;
  margin: 56px calc(50% - 50vw) 24px;
  padding: 48px 24px;
  text-align: center;
  background: var(--kfps-dark);
  color: #ffffff;
}

.kfps-section-band.light {
  background: var(--kfps-parchment);
  color: var(--kfps-ink);
}

.kfps-section-band h2 {
  margin: 0;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: clamp(28px, 3.4vw, 40px);
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: 0;
}

.kfps-section-band p {
  margin: 12px auto 0;
  max-width: 720px;
  color: var(--kfps-muted-dark);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

.kfps-section-band.light p {
  color: var(--kfps-muted);
}

h1, h2, h3, [data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  color: var(--kfps-ink);
  font-weight: 600;
  letter-spacing: -0.28px;
}

p, label, [data-testid="stMarkdownContainer"] p, .stMarkdown {
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

[data-testid="stSidebar"] {
  background: rgba(245, 245, 247, 0.94);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}

[data-testid="stSidebar"] h3 {
  font-size: 21px;
  line-height: 1.19;
  letter-spacing: 0.231px;
}

[data-testid="stMetric"] {
  background: var(--kfps-canvas);
  border: 1px solid var(--kfps-hairline);
  border-radius: 18px;
  padding: 24px;
  box-shadow: none;
}

[data-testid="stMetric"] label,
[data-testid="stMetricLabel"] {
  color: var(--kfps-muted);
  font-size: 14px;
  line-height: 1.29;
  letter-spacing: -0.224px;
}

[data-testid="stMetricValue"] {
  color: var(--kfps-ink);
  font-size: 34px;
  line-height: 1.18;
  letter-spacing: -0.374px;
}

.stButton > button,
.stDownloadButton > button {
  min-height: 44px;
  border-radius: 9999px;
  border: 1px solid var(--kfps-primary);
  background: var(--kfps-primary);
  color: #ffffff;
  padding: 11px 22px;
  box-shadow: none;
  font-size: 17px;
  font-weight: 400;
  letter-spacing: -0.374px;
  transition: transform 120ms ease, background-color 120ms ease;
}

.stButton > button:active,
.stDownloadButton > button:active {
  transform: scale(0.95);
}

.stButton > button:focus,
.stDownloadButton > button:focus {
  outline: 2px solid var(--kfps-primary-focus);
  outline-offset: 2px;
}

.stButton > button:disabled,
.stDownloadButton > button:disabled {
  background: var(--kfps-pearl);
  color: var(--kfps-muted);
  border-color: var(--kfps-hairline);
}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] textarea {
  border-radius: 18px;
  border-color: rgba(0, 0, 0, 0.08);
  background: var(--kfps-canvas);
  box-shadow: none;
}

[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

[data-testid="stExpander"] {
  border: 1px solid var(--kfps-hairline);
  border-radius: 18px;
  box-shadow: none;
}

[data-testid="stAlert"] {
  border-radius: 18px;
  border: 1px solid var(--kfps-hairline);
  box-shadow: none;
}

[data-testid="stProgress"] > div > div {
  background-color: var(--kfps-primary);
}

hr {
  border-color: var(--kfps-hairline);
}

@media (max-width: 640px) {
  .block-container {
    padding-left: 16px;
    padding-right: 16px;
  }
  .kfps-global-nav {
    gap: 14px;
    overflow: hidden;
  }
  .kfps-subnav {
    justify-content: space-between;
    padding: 0 16px;
    gap: 12px;
  }
  .kfps-subnav span:not(:first-child):not(.kfps-buy-chip) {
    display: none;
  }
  .kfps-hero {
    padding: 56px 20px 48px;
  }
  .kfps-section-band {
    padding: 40px 20px;
  }
}
</style>
"""


@st.cache_data(show_spinner=False)
def _image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_comfort_ui_css(dark_mode: bool) -> str:
    if dark_mode:
        root = {
            "primary": "#5f8ff7",
            "primary_focus": "#7aa2ff",
            "ink": "#f3f0ea",
            "body": "#e8e4dc",
            "muted": "#c7c0b5",
            "canvas": "#303236",
            "parchment": "#3a3d42",
            "surface": "#42464c",
            "surface_alt": "#383b40",
            "dark": "#34373c",
            "hairline": "#5a5f66",
            "chip": "#4d525a",
            "info": "#dfe8ff",
            "help_dot_ink": "#c7c0b5",
        }
    else:
        root = {
            "primary": "#2f6fdd",
            "primary_focus": "#1f5fc6",
            "ink": "#27282c",
            "body": "#3a3a3d",
            "muted": "#6d7078",
            "canvas": "#f7f6f2",
            "parchment": "#ece9e2",
            "surface": "#fffdfa",
            "surface_alt": "#f1eee7",
            "dark": "#3a3d42",
            "hairline": "#d8d3c9",
            "chip": "#e6e1d7",
            "info": "#22314f",
            "help_dot_ink": "#3a3d42",
        }
    color_scheme = "dark" if dark_mode else "light"
    fabric_uri = _image_data_uri(FABRIC_PATH)
    direction_uri = _image_data_uri(DIRECTION_BG_PATH)
    hero_background = (
        f"background: url('{fabric_uri}') center / cover no-repeat;"
        if fabric_uri
        else "background: linear-gradient(135deg, #9edcff 0%, #5fb3ff 100%);"
    )
    direction_background = (
        f"background: url('{direction_uri}') center / cover no-repeat;"
        if direction_uri
        else "background: var(--kfps-parchment);"
    )
    return f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,0,0");
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");

:root {{
  color-scheme: {color_scheme};
  --kfps-primary: {root["primary"]};
  --kfps-primary-focus: {root["primary_focus"]};
  --kfps-primary-on-dark: #9bb9ff;
  --kfps-ink: {root["ink"]};
  --kfps-body: {root["body"]};
  --kfps-muted: {root["muted"]};
  --kfps-muted-dark: {root["muted"]};
  --kfps-hairline: {root["hairline"]};
  --kfps-canvas: {root["canvas"]};
  --kfps-parchment: {root["parchment"]};
  --kfps-pearl: {root["surface"]};
  --kfps-surface: {root["surface"]};
  --kfps-surface-alt: {root["surface_alt"]};
  --kfps-dark: {root["dark"]};
  --kfps-black: {root["dark"]};
  --kfps-chip: {root["chip"]};
  --kfps-info: {root["info"]};
  --kfps-help-dot-ink: {root["help_dot_ink"]};
  --kfps-radius: 16px;
  --kfps-radius-pill: 9999px;
  --kfps-enter-card-height: 272px;
}}

.material-symbols-rounded {{
  font-family: "Material Symbols Rounded";
  font-weight: normal;
  font-style: normal;
  font-size: 24px;
  line-height: 1;
  letter-spacing: 0;
  text-transform: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  direction: ltr;
  font-feature-settings: "liga";
  -webkit-font-feature-settings: "liga";
  -webkit-font-smoothing: antialiased;
}}

html,
body,
.stApp,
[data-testid="stApp"],
[data-testid="stAppViewContainer"] {{
  background: var(--kfps-canvas);
  color: var(--kfps-body);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

[data-testid="stHeader"] {{
  background: color-mix(in srgb, var(--kfps-canvas) 88%, transparent);
  border-bottom: 1px solid var(--kfps-hairline);
  z-index: 900 !important;
}}

button[data-testid="stBaseButton-header"][kind="header"],
[data-testid="stMainMenuButton"],
[data-testid="stToolbar"] button[data-testid="stBaseButton-header"],
[data-testid="stToolbar"] [data-testid="stMainMenuButton"] {{
  display: none !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"],
[data-testid="stExpandSidebarButton"],
[data-testid="stHeader"] button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebar"] button[title*="sidebar" i],
[data-testid="stSidebar"] button[aria-label*="sidebar" i] {{
  position: fixed !important;
  top: 10px !important;
  left: 12px !important;
  z-index: 1000000 !important;
  width: 36px !important;
  height: 36px !important;
  min-width: 36px !important;
  min-height: 36px !important;
  margin: 0 !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  border: 0 !important;
  border-radius: 9px !important;
  background: transparent !important;
  color: var(--kfps-ink) !important;
  font-size: 0 !important;
  line-height: 0 !important;
  box-shadow: none !important;
  opacity: 1 !important;
  outline: none !important;
  overflow: hidden !important;
}}

[data-testid="stExpandSidebarButton"] svg,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"] svg,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"] span,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebar"] button[title*="sidebar" i] svg,
[data-testid="stSidebar"] button[aria-label*="sidebar" i] svg {{
  display: none !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] *,
[data-testid="stExpandSidebarButton"] *,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"] *,
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebar"] button[title*="sidebar" i] *,
[data-testid="stSidebar"] button[aria-label*="sidebar" i] * {{
  color: transparent !important;
  font-size: 0 !important;
  line-height: 0 !important;
  opacity: 0 !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]::before,
[data-testid="stExpandSidebarButton"]::before,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]::before,
[data-testid="stSidebarCollapseButton"]::before,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]::before,
[data-testid="stSidebar"] button[title*="sidebar" i]::before,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]::before {{
  content: "";
  position: absolute;
  left: 9px;
  top: 10px;
  width: 17px;
  height: 14px;
  border: 1.8px solid currentColor;
  border-radius: 4px;
  background: transparent;
  opacity: 1;
  visibility: visible !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]::after,
[data-testid="stExpandSidebarButton"]::after,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]::after,
[data-testid="stSidebarCollapseButton"]::after,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]::after,
[data-testid="stSidebar"] button[title*="sidebar" i]::after,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]::after {{
  content: "";
  position: absolute;
  left: 15px;
  top: 11px;
  width: 1.8px;
  height: 12px;
  border-radius: 2px;
  background: currentColor;
  opacity: 1;
  visibility: visible !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]:hover,
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]:hover,
[data-testid="stSidebarCollapseButton"]:hover,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:hover,
[data-testid="stSidebar"] button[title*="sidebar" i]:hover,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]:hover {{
  background: color-mix(in srgb, var(--kfps-ink) 7%, transparent) !important;
}}

[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]:focus,
[data-testid="stExpandSidebarButton"]:focus,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]:focus,
[data-testid="stSidebarCollapseButton"]:focus,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:focus,
[data-testid="stSidebar"] button[title*="sidebar" i]:focus,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]:focus,
[data-testid="stHeader"] [data-testid="stExpandSidebarButton"]:active,
[data-testid="stExpandSidebarButton"]:active,
[data-testid="stHeader"]
  button[data-testid="stBaseButton-headerNoPadding"][kind="headerNoPadding"]:active,
[data-testid="stSidebarCollapseButton"]:active,
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]:active,
[data-testid="stSidebar"] button[title*="sidebar" i]:active,
[data-testid="stSidebar"] button[aria-label*="sidebar" i]:active {{
  background: color-mix(in srgb, var(--kfps-ink) 10%, transparent) !important;
  box-shadow: none !important;
}}

.block-container {{
  max-width: 1120px;
  padding-top: 0;
}}

.st-key-kfps_top_bar {{
  position: sticky;
  top: 0;
  z-index: 999;
  width: 100vw;
  min-height: 52px;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  padding: 7px max(16px, calc((100vw - 1120px) / 2 + 24px)) 7px
    max(56px, calc((100vw - 1120px) / 2 + 24px));
  background: #3a3d42;
  backdrop-filter: saturate(140%) blur(18px);
  border-bottom: 1px solid color-mix(in srgb, #f7f6f2 18%, transparent);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  white-space: nowrap;
}}

.kfps-sidebar-toggle-visual {{
  display: none;
}}

.st-key-kfps_sidebar_toggle_button {{
  position: fixed !important;
  left: 12px !important;
  top: 10px !important;
  z-index: 1000002 !important;
  width: 36px !important;
  height: 36px !important;
}}

.st-key-kfps_sidebar_toggle_button button {{
  position: relative !important;
  width: 36px !important;
  min-width: 36px !important;
  height: 36px !important;
  min-height: 36px !important;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 9px !important;
  background: transparent !important;
  color: var(--kfps-ink) !important;
  box-shadow: none !important;
  font-size: 0 !important;
  line-height: 0 !important;
}}

.st-key-kfps_sidebar_toggle_button button:hover,
.st-key-kfps_sidebar_toggle_button button:focus,
.st-key-kfps_sidebar_toggle_button button:active {{
  background: color-mix(in srgb, var(--kfps-ink) 7%, transparent) !important;
  border: 0 !important;
  box-shadow: none !important;
}}

.st-key-kfps_sidebar_toggle_button button::before {{
  content: "";
  position: absolute;
  left: 9px;
  top: 10px;
  width: 17px;
  height: 14px;
  border: 1.8px solid currentColor;
  border-radius: 4px;
}}

.st-key-kfps_sidebar_toggle_button button::after {{
  content: "";
  position: absolute;
  left: 15px;
  top: 11px;
  width: 1.8px;
  height: 12px;
  border-radius: 2px;
  background: currentColor;
}}

[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] {{
  display: none !important;
}}

.stApp:has(.kfps-sidebar-hidden) [data-testid="stSidebar"] {{
  display: none !important;
}}

.stApp:has(.kfps-sidebar-hidden) .kfps-hero,
.stApp:has(.kfps-sidebar-hidden) .kfps-section-band,
.stApp:has(.kfps-sidebar-hidden) .kfps-guide {{
  width: 100vw !important;
  margin-left: calc(50% - 50vw) !important;
  margin-right: calc(50% - 50vw) !important;
}}

.st-key-kfps_top_bar::-webkit-scrollbar {{
  display: none;
}}

.st-key-kfps_top_bar [data-testid="stHorizontalBlock"] {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center;
  flex-wrap: nowrap !important;
  width: max(720px, 100%) !important;
}}

.st-key-kfps_top_bar [data-testid="column"] {{
  min-width: 0 !important;
  flex-shrink: 0 !important;
}}

.st-key-kfps_top_controls [data-testid="stHorizontalBlock"] {{
  display: flex !important;
  flex-direction: row !important;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: nowrap !important;
  gap: 0;
  min-width: 300px;
  width: 300px !important;
}}

.kfps-toggle-copy {{
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f7f6f2;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.03em;
}}

.kfps-toggle-divider {{
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: color-mix(in srgb, #f7f6f2 66%, transparent);
  font-size: 16px;
  font-weight: 800;
}}

.kfps-sidebar-title {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 4px 0 24px;
  color: var(--kfps-muted);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.01em;
}}

.kfps-sidebar-gear {{
  width: 18px;
  height: 18px;
  color: var(--kfps-muted);
  font-size: 18px;
  font-variation-settings: "FILL" 0, "wght" 580, "GRAD" 0, "opsz" 20;
}}

.kfps-top-brandbar {{
  display: inline-flex;
  align-items: center;
  min-width: 260px;
  height: 38px;
  color: #f7f6f2;
  overflow: visible;
}}

.kfps-top-brandbar strong {{
  color: #f7f6f2;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 15px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -0.01em;
  white-space: nowrap;
}}

.st-key-kfps_lang_is_kor,
.st-key-kfps_theme_is_dark {{
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
}}

.st-key-kfps_lang_is_kor label,
.st-key-kfps_theme_is_dark label {{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  margin: 0 !important;
}}

.st-key-kfps_lang_is_kor [data-testid="stWidgetLabel"],
.st-key-kfps_theme_is_dark [data-testid="stWidgetLabel"],
.st-key-kfps_lang_is_kor [data-testid="stMarkdownContainer"],
.st-key-kfps_theme_is_dark [data-testid="stMarkdownContainer"],
.st-key-kfps_lang_is_kor [data-testid="stMarkdownContainer"] p,
.st-key-kfps_theme_is_dark [data-testid="stMarkdownContainer"] p {{
  display: none !important;
}}

.st-key-kfps_lang_is_kor [role="switch"],
.st-key-kfps_theme_is_dark [role="switch"] {{
  position: relative !important;
  width: 48px !important;
  min-width: 48px !important;
  height: 28px !important;
  border-radius: var(--kfps-radius-pill) !important;
  border: 3px solid #f7f6f2 !important;
  background: color-mix(in srgb, #f7f6f2 92%, transparent) !important;
  box-shadow: none !important;
  overflow: hidden !important;
  transition: background-color 160ms ease, border-color 160ms ease;
}}

.st-key-kfps_lang_is_kor [role="switch"][aria-checked="true"],
.st-key-kfps_theme_is_dark [role="switch"][aria-checked="true"] {{
  border-color: #f8f6ef !important;
  background: #26272a !important;
}}

.st-key-kfps_lang_is_kor [role="switch"] *,
.st-key-kfps_theme_is_dark [role="switch"] * {{
  box-shadow: none !important;
}}

.st-key-kfps_lang_is_kor [role="switch"]::after,
.st-key-kfps_theme_is_dark [role="switch"]::after {{
  content: "";
  position: absolute;
  top: 4px;
  left: 4px;
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: #3a3d42;
  transition: transform 160ms ease, background-color 160ms ease;
}}

.st-key-kfps_lang_is_kor [role="switch"][aria-checked="true"]::after,
.st-key-kfps_theme_is_dark [role="switch"][aria-checked="true"]::after {{
  transform: translateX(22px);
  background: #f8f6ef;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] {{
  display: flex;
  justify-content: flex-end;
  flex-wrap: nowrap;
  width: 100%;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] button {{
  border-radius: var(--kfps-radius-pill) !important;
  min-height: 36px;
  color: var(--kfps-ink);
  border-color: var(--kfps-hairline);
  background: var(--kfps-surface);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  padding-left: 10px;
  padding-right: 10px;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] button:hover {{
  border-color: var(--kfps-primary) !important;
  color: var(--kfps-primary) !important;
}}

.st-key-kfps_top_bar [data-baseweb="button-group"] button[aria-pressed="true"],
.st-key-kfps_top_bar [data-baseweb="button-group"] button[aria-selected="true"],
.st-key-kfps_top_bar [data-baseweb="button-group"] button[aria-checked="true"],
.st-key-kfps_top_bar [data-baseweb="button-group"] button[data-selected="true"] {{
  background: var(--kfps-primary) !important;
  border-color: var(--kfps-primary) !important;
  color: #f8f6ef !important;
}}

.kfps-global-nav,
.kfps-subnav {{
  display: none !important;
}}

.kfps-top-brandbar {{
  min-height: 40px;
  display: flex;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  color: var(--kfps-body);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

.kfps-top-brandbar strong {{
  color: var(--kfps-ink);
  font-size: 18px;
  line-height: 1;
  font-weight: 800;
}}

.kfps-subnav .kfps-buy-chip,
.kfps-hero .kfps-pill-primary {{
  background: var(--kfps-primary);
  color: #f8f6ef;
}}

.kfps-hero {{
  {hero_background}
  position: relative;
  isolation: isolate;
  overflow: hidden;
  color: #ffffff;
  padding: 72px 24px 56px;
  margin-top: 0 !important;
}}

.kfps-hero::before {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background: rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(1.4px);
  -webkit-backdrop-filter: blur(1.4px);
}}

.kfps-hero h1,
.kfps-section-band h2 {{
  color: inherit;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.02em;
}}

.kfps-hero-eyebrow {{
  display: table;
  margin: 0 auto 14px;
  position: relative;
  z-index: 1;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.95);
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.32);
  padding: 7px 14px;
  border-radius: var(--kfps-radius-pill);
}}

.kfps-hero p,
.kfps-hero-copy {{
  color: #ffffff;
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.01em;
}}

.kfps-hero-copy {{
  display: grid;
  gap: 12px;
  max-width: 880px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
  text-align: center;
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.34);
}}

.kfps-hero-main {{
  display: block;
  margin: 0;
  padding: 0;
  font-size: clamp(21px, 2.4vw, 27px);
  font-weight: 650;
  line-height: 1.2;
}}

.kfps-hero-subtext {{
  display: block;
  max-width: 760px;
  margin: 0 auto;
  padding: 0;
  color: #ffffff;
  font-size: clamp(13px, 1.35vw, 16px);
  font-weight: 300;
  line-height: 1.6;
}}

.kfps-footer-badges,
.kfps-hero-pills {{
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
}}

.kfps-hero-pills {{
  margin-top: 24px;
  position: relative;
  z-index: 1;
}}

.kfps-footer-badges {{
  margin: 18px 0 12px;
  justify-content: flex-start;
}}

.kfps-footer-badge,
.kfps-hero .kfps-pill {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 34px;
  padding: 8px 13px;
  background: var(--kfps-surface);
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius-pill);
  color: var(--kfps-body);
  font-size: 13px;
  font-weight: 300;
  line-height: 1;
  white-space: nowrap;
}}

.kfps-footer-badges .kfps-footer-badge.kfps-pill-link {{
  text-decoration: none !important;
  font-weight: 450;
}}

.kfps-footer-badges .kfps-footer-badge.kfps-pill-link:hover {{
  border-color: color-mix(in srgb, var(--kfps-primary) 42%, var(--kfps-hairline));
  background: color-mix(in srgb, var(--kfps-primary) 5%, var(--kfps-surface));
}}

.kfps-hero .kfps-pill {{
  background: rgba(18, 25, 35, 0.38);
  border-color: rgba(255, 255, 255, 0.32);
  color: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.20), 0 8px 24px rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(16px) saturate(125%);
  -webkit-backdrop-filter: blur(16px) saturate(125%);
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.30);
}}

.kfps-hero .kfps-pill:hover {{
  background: rgba(18, 25, 35, 0.48);
  border-color: rgba(255, 255, 255, 0.48);
}}

.kfps-pill-link {{
  text-decoration: none !important;
  cursor: pointer;
}}

.kfps-pill-link:focus-visible {{
  outline: 2px solid rgba(255, 255, 255, 0.78);
  outline-offset: 3px;
}}

.kfps-footer-badges .kfps-footer-badge.kfps-pill-link:focus-visible {{
  outline: 2px solid var(--kfps-primary);
  outline-offset: 2px;
}}

.kfps-pill-emoji,
.kfps-footer-emoji {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-size: 16px;
  line-height: 1;
}}

.kfps-hero .kfps-pill.kfps-pill-dataset,
.kfps-footer-badges .kfps-footer-badge.kfps-pill-dataset {{
  gap: 7px;
  padding-left: 14px;
  padding-right: 14px;
}}

.kfps-pill-dataset .kfps-pill-emoji {{
  width: 16px;
  height: 16px;
  font-size: 14px;
  flex-shrink: 0;
}}

.kfps-pill-icon {{
  width: 18px;
  height: 18px;
  font-size: 18px;
  color: currentColor;
}}

.kfps-pill-github {{
  display: inline-block;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  background: currentColor;
  -webkit-mask: url("{GITHUB_MARK_MASK_URI}") center / contain no-repeat;
  mask: url("{GITHUB_MARK_MASK_URI}") center / contain no-repeat;
}}

.kfps-symbol {{
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--kfps-primary);
  font-size: 0;
  line-height: 1;
}}

.kfps-symbol-screen::before {{
  content: "";
  width: 13px;
  height: 9px;
  border: 1.6px solid currentColor;
  border-radius: 3px;
}}

.kfps-symbol-screen::after {{
  content: "";
  position: absolute;
  left: 5px;
  bottom: 1px;
  width: 6px;
  height: 1.6px;
  background: currentColor;
  box-shadow: 3px 2px 0 currentColor;
}}

.kfps-symbol-lock::before {{
  content: "";
  position: absolute;
  left: 3px;
  bottom: 2px;
  width: 10px;
  height: 8px;
  border: 1.6px solid currentColor;
  border-radius: 3px;
}}

.kfps-symbol-lock::after {{
  content: "";
  position: absolute;
  left: 5px;
  top: 2px;
  width: 6px;
  height: 7px;
  border: 1.6px solid currentColor;
  border-bottom: 0;
  border-radius: 7px 7px 0 0;
}}

.kfps-symbol-export::before {{
  content: "";
  position: absolute;
  left: 3px;
  bottom: 3px;
  width: 9px;
  height: 9px;
  border-left: 1.6px solid currentColor;
  border-bottom: 1.6px solid currentColor;
}}

.kfps-symbol-export::after {{
  content: "";
  position: absolute;
  right: 2px;
  top: 2px;
  width: 9px;
  height: 9px;
  border-top: 1.8px solid currentColor;
  border-right: 1.8px solid currentColor;
  transform: rotate(0deg);
}}

.kfps-footer-note {{
  margin: 0;
}}

.kfps-guide {{
  width: 100vw;
  margin: 0 calc(50% - 50vw);
  padding: 36px 24px 48px;
  background: var(--kfps-canvas);
}}

.kfps-guide-inner {{
  max-width: 1120px;
  margin: 0 auto;
}}

.kfps-eyebrow {{
  color: var(--kfps-primary);
  font-size: 18px;
  font-weight: 850;
  letter-spacing: -0.01em;
}}

.kfps-guide h2 {{
  margin: 6px 0 22px;
  color: var(--kfps-ink);
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1.16;
  letter-spacing: -0.03em;
}}

.kfps-flow {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}}

.kfps-flow-card {{
  position: relative;
  min-height: 164px;
  padding: 22px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
  align-self: start;
}}

.kfps-flow-card summary {{
  display: block;
  cursor: pointer;
  list-style: none;
}}

.kfps-flow-card summary:focus,
.kfps-flow-card summary:focus-visible {{
  outline: none !important;
}}

.kfps-flow-card summary::-webkit-details-marker {{
  display: none;
}}

.kfps-flow-card:hover {{
  border-color: color-mix(in srgb, var(--kfps-primary) 46%, var(--kfps-hairline));
  background: color-mix(in srgb, var(--kfps-primary) 4%, var(--kfps-surface));
}}

.kfps-flow-detail {{
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px solid var(--kfps-hairline);
  color: var(--kfps-muted);
  font-size: 13px;
  line-height: 1.5;
}}

.kfps-flow-card:not(:last-child)::after {{
  content: "";
  position: absolute;
  right: -11px;
  top: 50%;
  width: 18px;
  height: 18px;
  border-top: 2px solid var(--kfps-primary);
  border-right: 2px solid var(--kfps-primary);
  transform: translateY(-50%) rotate(45deg);
  background: transparent;
}}

.kfps-icon {{
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: var(--kfps-radius);
  display: grid;
  place-items: center;
  background: var(--kfps-chip);
  color: var(--kfps-primary);
  margin-bottom: 16px;
}}

.kfps-step-icon {{
  position: relative;
  width: 28px;
  height: 28px;
  color: currentColor;
}}

.kfps-step-icon.material-symbols-rounded {{
  position: static;
  width: auto;
  height: auto;
  font-size: 31px;
  font-variation-settings: "FILL" 1, "wght" 560, "GRAD" 0, "opsz" 32;
}}

.kfps-step-concept::before {{
  content: "";
  position: absolute;
  left: 9px;
  top: 3px;
  width: 6px;
  height: 21px;
  border: 2px solid currentColor;
  border-radius: 4px;
  transform: rotate(-38deg);
}}

.kfps-step-concept::after {{
  content: "";
  position: absolute;
  left: 4px;
  bottom: 2px;
  width: 13px;
  height: 2px;
  background: currentColor;
  border-radius: 2px;
}}

.kfps-step-people i {{
  position: absolute;
  top: 5px;
  width: 7px;
  height: 7px;
  border: 2px solid currentColor;
  border-radius: 9999px;
}}

.kfps-step-people i::after {{
  content: "";
  position: absolute;
  left: -3px;
  top: 10px;
  width: 9px;
  height: 9px;
  border: 2px solid currentColor;
  border-top: 0;
  border-radius: 0 0 9px 9px;
}}

.kfps-step-people i:nth-child(1) {{
  left: 0;
  top: 8px;
}}

.kfps-step-people i:nth-child(2) {{
  left: 10px;
}}

.kfps-step-people i:nth-child(3) {{
  right: 0;
  top: 8px;
}}

.kfps-step-cost::before {{
  content: "$";
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 22px;
  font-weight: 900;
  line-height: 1;
}}

.kfps-step-report::before {{
  content: "";
  position: absolute;
  left: 6px;
  top: 3px;
  width: 16px;
  height: 22px;
  border: 2px solid currentColor;
  border-radius: 4px;
  background:
    linear-gradient(currentColor 0 0) 4px 8px / 8px 2px no-repeat,
    linear-gradient(currentColor 0 0) 4px 13px / 8px 2px no-repeat;
}}

.kfps-step-report::after {{
  content: "";
  position: absolute;
  right: 5px;
  top: 3px;
  width: 7px;
  height: 7px;
  border-left: 2px solid currentColor;
  border-bottom: 2px solid currentColor;
  background: var(--kfps-chip);
}}

.kfps-secret-field-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 14px 0 7px;
}}

.kfps-secret-field-actions {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: 0 0 auto;
  overflow: visible;
}}

.kfps-key-name {{
  color: var(--kfps-ink);
  font-size: 13px;
  font-weight: 850;
  line-height: 1;
}}

.kfps-key-mark {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 9999px;
  border: 1px solid var(--kfps-hairline);
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
}}

.kfps-key-mark.ok {{
  color: #0f8f5f;
  background: color-mix(in srgb, #18a66f 13%, var(--kfps-surface));
}}

.kfps-key-mark.missing {{
  color: var(--kfps-muted);
  background: var(--kfps-chip);
}}

.kfps-help-dot {{
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 9999px;
  border: 1px solid var(--kfps-hairline);
  background: var(--kfps-chip);
  color: var(--kfps-help-dot-ink);
  font-size: 12px;
  font-weight: 900;
  cursor: help;
  overflow: visible;
  outline: none;
}}

.kfps-secret-field-actions .kfps-help-dot {{
  width: 20px;
  height: 20px;
  border: 0;
  background: transparent;
  color: var(--kfps-muted);
  font-size: 18px !important;
  font-variation-settings: "FILL" 0, "wght" 450, "GRAD" 0, "opsz" 20;
  font-weight: normal;
  line-height: 1 !important;
}}

.kfps-secret-field-actions .kfps-help-dot:hover,
.kfps-secret-field-actions .kfps-help-dot:focus-visible {{
  background: color-mix(in srgb, var(--kfps-ink) 8%, transparent);
  color: var(--kfps-ink);
}}

.kfps-help-dot::before,
.kfps-help-dot::after {{
  position: absolute;
  right: 0;
  z-index: 1000006;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
}}

.kfps-help-dot::before {{
  content: "";
  top: calc(100% + 2px);
  width: 10px;
  height: 10px;
  transform: translate(-6px, -2px) rotate(45deg);
  background: var(--kfps-surface);
  border-left: 1px solid var(--kfps-hairline);
  border-top: 1px solid var(--kfps-hairline);
  box-shadow: -2px -2px 6px rgba(39, 40, 44, 0.04);
}}

.kfps-help-dot::after {{
  content: attr(data-tooltip);
  top: calc(100% + 7px);
  min-width: 210px;
  max-width: min(320px, calc(100vw - 32px));
  padding: 9px 11px;
  border: 1px solid var(--kfps-hairline);
  border-radius: 8px;
  background: var(--kfps-surface);
  color: var(--kfps-body);
  box-shadow: 0 14px 36px rgba(39, 40, 44, 0.14);
  font-size: 12px;
  font-weight: 650;
  line-height: 1.45;
  letter-spacing: 0;
  text-align: left;
  white-space: normal;
  word-break: keep-all;
  transform: translateY(-3px);
}}

.kfps-secret-field-actions .kfps-help-dot::after {{
  font-size: 11px;
  line-height: 1.4;
}}

.kfps-help-dot:hover::before,
.kfps-help-dot:hover::after,
.kfps-help-dot:focus-visible::before,
.kfps-help-dot:focus-visible::after {{
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}}

.kfps-help-dot:hover::before,
.kfps-help-dot:focus-visible::before {{
  transform: translate(-6px, 0) rotate(45deg);
}}

.kfps-secret-field-head,
.kfps-secret-status-grid,
.kfps-secret-status-card {{
  overflow: visible;
}}

[role="tooltip"],
[data-baseweb="tooltip"],
[data-testid="stTooltip"] {{
  border: 1px solid var(--kfps-hairline) !important;
  border-radius: 8px !important;
  background: var(--kfps-surface) !important;
  color: var(--kfps-body) !important;
  box-shadow: 0 14px 36px rgba(39, 40, 44, 0.14) !important;
}}

[role="tooltip"] *,
[data-baseweb="tooltip"] *,
[data-testid="stTooltip"] * {{
  background: transparent !important;
  color: var(--kfps-body) !important;
}}

.kfps-secret-status-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}}

.kfps-secret-status-card {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
}}

.kfps-secret-provider {{
  color: var(--kfps-ink);
  font-size: 13px;
  font-weight: 850;
  min-width: 0;
}}

.kfps-secret-state {{
  color: var(--kfps-muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.04em;
}}

.kfps-secret-state.ok {{
  color: #0f8f5f;
}}

.kfps-secret-state.missing {{
  color: var(--kfps-muted);
}}

.kfps-input-section-title {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 22px 0 12px;
  padding: 7px 12px;
  border: 1px solid var(--kfps-hairline);
  border-radius: 9px;
  background: color-mix(in srgb, var(--kfps-primary) 6%, var(--kfps-surface));
  color: var(--kfps-ink);
  font-size: 17px;
  font-weight: 720;
  line-height: 1.08;
  letter-spacing: 0;
}}

.kfps-input-section-title::before {{
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: var(--kfps-primary);
}}

@media (max-width: 760px) {{
  .kfps-secret-status-grid {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
}}

.kfps-enter-card {{
  box-sizing: border-box;
  height: var(--kfps-enter-card-height);
  min-height: var(--kfps-enter-card-height);
  margin-top: 27px;
  padding: 92px 28px 30px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
  display: grid;
  align-content: start;
  gap: 0;
  box-shadow: 0 10px 28px rgba(39, 40, 44, 0.04);
  transition: none;
}}

.kfps-enter-card:hover {{
  border-color: color-mix(in srgb, #ef4444 44%, var(--kfps-hairline));
  background: color-mix(in srgb, #ef4444 5%, var(--kfps-surface));
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.22);
}}

.st-key-kfps_enter_overlay {{
  position: relative !important;
}}

.st-key-kfps_enter_overlay [data-testid="stVerticalBlock"] {{
  display: block !important;
  gap: 0 !important;
}}

.st-key-kfps_enter_card_button {{
  box-sizing: border-box !important;
  position: absolute !important;
  top: 27px !important;
  left: 0 !important;
  right: 0 !important;
  width: 100% !important;
  margin: 0 !important;
  z-index: 7 !important;
  min-height: var(--kfps-enter-card-height) !important;
}}

.st-key-kfps_enter_card_button button {{
  box-sizing: border-box !important;
  width: 100% !important;
  min-height: var(--kfps-enter-card-height) !important;
  border: 1px solid transparent !important;
  border-radius: var(--kfps-radius) !important;
  background: transparent !important;
  box-shadow: none !important;
  color: transparent !important;
  cursor: pointer !important;
  transition: none !important;
}}

.st-key-kfps_enter_card_button button p {{
  color: transparent !important;
}}

.st-key-kfps_enter_card_button button:hover,
.st-key-kfps_enter_card_button button:focus-visible {{
  border-color: color-mix(in srgb, #ef4444 44%, var(--kfps-hairline)) !important;
  background: color-mix(in srgb, #ef4444 5%, transparent) !important;
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.22) !important;
}}

.st-key-kfps_enter_card_button button:active {{
  transform: none;
}}

.kfps-enter-top {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
}}

.kfps-enter-title-stack {{
  display: grid;
  gap: 4px;
  min-width: 0;
  text-align: center;
  grid-column: 2;
}}

.kfps-enter-arrow {{
  display: inline-grid;
  place-items: center;
  justify-self: end;
  grid-column: 1;
  width: 30px;
  height: 30px;
  border-radius: 0;
  background: transparent;
  color: var(--kfps-ink);
  font-size: 27px !important;
  font-variation-settings: "FILL" 0, "wght" 680, "GRAD" 0, "opsz" 28;
}}

.kfps-enter-card strong {{
  color: var(--kfps-body);
  font-size: 28px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0;
}}

.kfps-enter-subtitle {{
  color: var(--kfps-muted);
  font-size: 13px;
  font-weight: 650;
  line-height: 1.15;
  letter-spacing: 0;
}}

.kfps-enter-warning {{
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  max-width: 250px;
  margin: 44px auto 0;
  color: var(--kfps-body);
  font-size: 13px;
  line-height: 1.55;
  word-break: keep-all;
}}

.kfps-enter-warning-icon {{
  color: #b45309;
  font-size: 17px !important;
  line-height: 1.25 !important;
  font-variation-settings: "FILL" 1, "wght" 620, "GRAD" 0, "opsz" 20;
}}

.kfps-run-panel {{
  margin: 18px 0 18px;
  padding: 18px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
}}

.kfps-run-panel h3 {{
  margin: 0 0 7px;
  color: var(--kfps-ink);
  font-size: 20px;
  line-height: 1.25;
}}

.kfps-run-panel p {{
  margin: 0;
  color: var(--kfps-muted);
  font-size: 14px;
  line-height: 1.55;
  word-break: keep-all;
}}

.st-key-kfps_cost_confirm {{
  border: 1px solid transparent !important;
  border-radius: var(--kfps-radius) !important;
  padding: 10px 12px !important;
  transition: none !important;
}}

.st-key-kfps_cost_confirm * {{
  transition: none !important;
}}

.st-key-kfps_advanced_expander,
.st-key-kfps_advanced_expander *,
.st-key-kfps_advanced_expander summary,
.st-key-kfps_advanced_expander details {{
  animation: none !important;
  transition: none !important;
}}

.st-key-kfps_advanced_expander summary:hover,
.st-key-kfps_advanced_expander summary:focus,
.st-key-kfps_advanced_expander summary:active {{
  background: transparent !important;
  box-shadow: none !important;
}}

[data-testid="stExpander"] {{
  transition: none !important;
}}

.kfps-result-anchor {{
  display: block;
  height: 1px;
  scroll-margin-top: 86px;
}}

.st-key-kfps_export_md_pending button,
[class*="st-key-kfps_export_md_"] button {{
  pointer-events: auto !important;
  transition: none !important;
}}

.st-key-kfps_export_md_pending button:hover,
.st-key-kfps_export_md_pending button:focus-visible,
[class*="st-key-kfps_export_md_"] button:hover,
[class*="st-key-kfps_export_md_"] button:focus-visible {{
  border-color: color-mix(in srgb, #ef4444 44%, var(--kfps-hairline)) !important;
  background: color-mix(in srgb, #ef4444 5%, var(--kfps-surface)) !important;
  color: #b91c1c !important;
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.22) !important;
}}

.st-key-kfps_export_md_pending button:hover p,
.st-key-kfps_export_md_pending button:focus-visible p,
[class*="st-key-kfps_export_md_"] button:hover p,
[class*="st-key-kfps_export_md_"] button:focus-visible p {{
  color: #b91c1c !important;
}}

.kfps-report-shell {{
  margin: 16px 0 20px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  overflow: hidden;
  user-select: text;
}}

.kfps-report-empty {{
  min-height: 168px;
  display: grid;
  place-items: center;
  padding: 24px;
  color: var(--kfps-muted);
  text-align: center;
}}

.kfps-report-empty strong {{
  display: block;
  margin-bottom: 8px;
  color: color-mix(in srgb, var(--kfps-muted) 82%, var(--kfps-surface));
  font-size: 15px;
  font-weight: 800;
}}

.kfps-report-empty span {{
  display: block;
  color: color-mix(in srgb, var(--kfps-muted) 64%, var(--kfps-surface));
  font-size: 13px;
  line-height: 1.45;
}}

.kfps-report-selectable {{
  min-height: 520px;
  max-height: 520px;
  margin: 0;
  padding: 20px;
  overflow: auto;
  color: var(--kfps-body);
  background: var(--kfps-surface);
  border: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  user-select: text;
  cursor: text;
  font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
  font-size: 13px;
  line-height: 1.55;
}}

.kfps-report-selectable::selection,
.kfps-report-shell ::selection {{
  background: color-mix(in srgb, var(--kfps-primary) 24%, transparent);
}}

[class*="st-key-kfps_report_md_source"] textarea {{
  min-height: 520px !important;
  color: var(--kfps-body) !important;
  background: var(--kfps-surface) !important;
  border-color: var(--kfps-hairline) !important;
  font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace !important;
  font-size: 13px !important;
  line-height: 1.55 !important;
}}

.kfps-loading-panel {{
  margin-top: 16px;
  padding: 24px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--kfps-body);
}}

.kfps-dot-spinner {{
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  border: 4px dotted color-mix(in srgb, var(--kfps-primary) 42%, transparent);
  border-top-color: var(--kfps-primary);
  animation: kfps-spin 900ms linear infinite;
}}

@keyframes kfps-spin {{
  to {{
    transform: rotate(360deg);
  }}
}}

.kfps-opinion-head {{
  margin-top: 18px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}}

.kfps-opinion-head h3 {{
  margin: 0 0 5px;
  color: var(--kfps-ink);
  font-size: 24px;
  line-height: 1.2;
}}

.kfps-opinion-head p {{
  margin: 0;
  color: var(--kfps-muted);
  font-size: 14px;
  line-height: 1.5;
}}

.kfps-opinion-grid {{
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}}

.kfps-opinion-card {{
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  color: var(--kfps-body);
}}

.kfps-opinion-meta {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--kfps-muted);
  font-size: 12px;
  font-weight: 750;
}}

.kfps-sentiment {{
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 9999px;
  background: var(--kfps-chip);
  color: var(--kfps-ink);
  font-size: 12px;
  font-weight: 850;
}}

.kfps-sentiment.positive {{
  background: color-mix(in srgb, #18a66f 15%, var(--kfps-surface));
  color: #0f7a51;
}}

.kfps-sentiment.neutral {{
  background: color-mix(in srgb, #64748b 13%, var(--kfps-surface));
  color: var(--kfps-body);
}}

.kfps-sentiment.negative {{
  background: color-mix(in srgb, #ef4444 12%, var(--kfps-surface));
  color: #b91c1c;
}}

.kfps-opinion-profile {{
  margin: 0 0 10px;
  color: var(--kfps-ink);
  font-size: 13px;
  line-height: 1.35;
  font-weight: 780;
}}

.kfps-opinion-card h4 {{
  margin: 12px 0 5px;
  color: var(--kfps-muted);
  font-size: 12px;
  line-height: 1.2;
}}

.kfps-opinion-card p {{
  margin: 0;
  color: var(--kfps-body);
  font-size: 13px;
  line-height: 1.45;
  word-break: keep-all;
}}

.kfps-inline-note {{
  margin: 10px 0 12px;
  padding: 13px 14px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: color-mix(in srgb, var(--kfps-primary) 8%, var(--kfps-surface));
  color: var(--kfps-body);
  font-size: 14px;
  line-height: 1.45;
  overflow: hidden;
}}

.kfps-run-mode-note {{
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 44px;
}}

.kfps-model-meta {{
  display: grid;
  gap: 7px;
  margin: 12px 0 12px;
  padding: 12px;
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  background: var(--kfps-surface);
  overflow: hidden;
}}

.kfps-model-meta-row {{
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 9px;
  align-items: baseline;
  min-width: 0;
}}

.kfps-model-meta-label {{
  color: var(--kfps-muted);
  font-size: 12px;
  line-height: 1.25;
  font-weight: 700;
  text-transform: none;
}}

.kfps-model-meta-value {{
  color: var(--kfps-ink);
  font-size: 13px;
  line-height: 1.3;
  font-weight: 700;
  word-break: break-word;
}}

.kfps-flow-card h3 {{
  margin: 0 0 7px;
  color: var(--kfps-ink);
  font-size: 18px;
  line-height: 1.24;
  letter-spacing: -0.02em;
}}

.kfps-flow-card p {{
  margin: 0;
  color: var(--kfps-muted);
  font-size: 15px;
  line-height: 1.45;
  letter-spacing: -0.01em;
}}

.kfps-section-band {{
  background: var(--kfps-dark);
  color: #f4f1ea;
  margin-top: 36px;
  padding: 42px 24px;
}}

.kfps-section-band.light {{
  background: var(--kfps-parchment);
  color: var(--kfps-ink);
}}

.kfps-section-band.direction {{
  {direction_background}
  color: #1d1d1f !important;
}}

.kfps-section-band.direction .kfps-section-band-inner {{
  max-width: 1120px;
  margin: 0 auto;
  text-align: left;
}}

.kfps-section-band.direction p {{
  margin-left: 0;
  margin-right: 0;
  color: #3a3d42 !important;
}}

.kfps-section-band h2 {{
  color: inherit;
}}

.kfps-section-band p,
.kfps-section-band.light p {{
  color: color-mix(in srgb, currentColor 72%, transparent);
}}

h1, h2, h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
  color: var(--kfps-ink);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.02em;
}}

p, label, .stMarkdown,
[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] {{
  color: var(--kfps-body);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
  letter-spacing: -0.01em;
}}

[data-testid="stElementContainer"]:has([data-testid="stTextInputRootElement"])
  [data-testid="stWidgetLabel"],
[data-testid="stElementContainer"]:has([data-testid="stNumberInputContainer"])
  [data-testid="stWidgetLabel"],
[data-testid="stElementContainer"]:has([data-testid="stTextAreaRootElement"])
  [data-testid="stWidgetLabel"] {{
  padding-left: 14px !important;
  margin-bottom: 7px !important;
}}

[data-testid="stElementContainer"]:has([data-testid="stTextInputRootElement"])
  [data-testid="stWidgetLabel"] p,
[data-testid="stElementContainer"]:has([data-testid="stNumberInputContainer"])
  [data-testid="stWidgetLabel"] p,
[data-testid="stElementContainer"]:has([data-testid="stTextAreaRootElement"])
  [data-testid="stWidgetLabel"] p {{
  margin: 0 !important;
}}

[data-testid="stSidebar"] {{
  background: var(--kfps-parchment);
  border-right: 1px solid var(--kfps-hairline);
  min-width: 360px !important;
}}

[data-testid="stSidebar"] > div {{
  min-width: 360px !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] {{
  width: 100% !important;
  min-width: 0 !important;
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button {{
  width: 100% !important;
  min-width: 0 !important;
  white-space: nowrap !important;
  color: var(--kfps-ink) !important;
  background: var(--kfps-surface) !important;
  font-size: 0 !important;
  padding: 0 5px !important;
  min-height: 32px !important;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button p {{
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
  color: inherit !important;
  font-size: 10px !important;
  font-weight: 720 !important;
  letter-spacing: 0 !important;
  line-height: 1 !important;
}}

[data-testid="stSidebar"] [data-testid="stSegmentedControl"],
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] > div,
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"],
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"] > div {{
  width: 100% !important;
  max-width: none !important;
}}

[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"],
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [data-baseweb="button-group"] > div {{
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] div[role="radiogroup"][aria-label="button group"] {{
  width: 100% !important;
  max-width: none !important;
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] div[role="radiogroup"][aria-label="button group"] > button {{
  width: 100% !important;
  min-width: 0 !important;
  justify-content: center !important;
}}

[data-testid="stSidebar"] .st-key-kfps_run_mode,
[data-testid="stSidebar"] .st-key-kfps_run_mode > div,
[data-testid="stSidebar"] .st-key-kfps_run_mode div[role="radiogroup"],
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(
  div[role="radiogroup"][aria-label="button group"]
) {{
  width: 100% !important;
  max-width: none !important;
}}

[data-testid="stSidebar"] .st-key-kfps_run_mode div[role="radiogroup"] {{
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}}

[data-testid="stSidebar"] .st-key-kfps_run_mode div[role="radiogroup"] > button {{
  width: 100% !important;
  min-width: 0 !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button
  [data-testid="stMarkdownContainer"] {{
  overflow: visible !important;
  min-width: max-content !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-checked="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[data-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"]
  button[data-testid="stBaseButton-segmented_controlActive"] {{
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
  border-color: #3b82f6 !important;
  color: #ffffff !important;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.22),
    0 8px 20px rgba(59, 130, 246, 0.18) !important;
}}

[data-testid="stMetric"],
[data-testid="stExpander"],
[data-testid="stAlert"] {{
  background: var(--kfps-surface);
  color: var(--kfps-body);
  border: 1px solid var(--kfps-hairline);
  border-radius: var(--kfps-radius);
  overflow: hidden;
}}

[data-testid="stExpander"] > details,
[data-testid="stExpander"] > details > summary,
[data-testid="stExpander"] [data-testid="stVerticalBlock"],
[data-testid="stAlert"] > div,
[data-testid="stAlert"] [role="alert"] {{
  border-radius: var(--kfps-radius) !important;
  box-shadow: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] {{
  margin-top: 18px;
  background: transparent !important;
  border: 0 !important;
  border-top: 1px solid var(--kfps-hairline) !important;
  border-radius: 0 !important;
  overflow: visible !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] details {{
  border-radius: 0 !important;
  overflow: visible !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
  position: relative !important;
  min-height: 52px !important;
  padding: 15px 42px 15px 0 !important;
  color: var(--kfps-muted) !important;
  border-radius: 0 !important;
  background: transparent !important;
  cursor: pointer !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{
  color: var(--kfps-muted) !important;
  font-size: 14px !important;
  font-weight: 800 !important;
  line-height: 1.25 !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
  position: absolute !important;
  right: 8px !important;
  top: 50% !important;
  z-index: 2 !important;
  width: 18px !important;
  height: 18px !important;
  transform: translateY(-50%) !important;
  color: var(--kfps-muted) !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::after {{
  content: "";
  position: absolute;
  right: 1px;
  top: 50%;
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  background: color-mix(in srgb, var(--kfps-ink) 0%, transparent);
  transform: translateY(-50%);
  opacity: 0;
  transition: background-color 140ms ease, opacity 140ms ease;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover::after {{
  background: color-mix(in srgb, var(--kfps-ink) 9%, transparent);
  opacity: 1;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  padding-top: 8px !important;
  border-radius: 0 !important;
}}

[data-baseweb="button-group"] {{
  border: 1px solid var(--kfps-hairline) !important;
  border-radius: var(--kfps-radius) !important;
  background: var(--kfps-surface) !important;
  box-shadow: none !important;
  overflow: hidden !important;
}}

[data-baseweb="button-group"] button {{
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
  color: var(--kfps-ink) !important;
}}

[data-baseweb="button-group"] button:not(:last-child) {{
  border-right: 1px solid var(--kfps-hairline) !important;
}}

[data-baseweb="button-group"] button:first-child {{
  border-top-left-radius: var(--kfps-radius) !important;
  border-bottom-left-radius: var(--kfps-radius) !important;
}}

[data-baseweb="button-group"] button:last-child {{
  border-top-right-radius: var(--kfps-radius) !important;
  border-bottom-right-radius: var(--kfps-radius) !important;
}}

[data-baseweb="button-group"] button[aria-pressed="true"],
[data-baseweb="button-group"] button[aria-selected="true"],
[data-baseweb="button-group"] button[aria-checked="true"],
[data-baseweb="button-group"] button[data-selected="true"] {{
  background: color-mix(in srgb, var(--kfps-primary) 14%, var(--kfps-surface)) !important;
  color: var(--kfps-ink) !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button {{
  width: 100% !important;
  min-width: 0 !important;
  white-space: nowrap !important;
  font-size: 0 !important;
  padding: 0 5px !important;
  min-height: 32px !important;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button p {{
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
  color: inherit !important;
  font-size: 10px !important;
  font-weight: 720 !important;
  letter-spacing: 0 !important;
  line-height: 1 !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button
  [data-testid="stMarkdownContainer"] {{
  overflow: visible !important;
  min-width: max-content !important;
}}

[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-checked="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"] button[data-selected="true"],
[data-testid="stSidebar"] [data-baseweb="button-group"]
  button[data-testid="stBaseButton-segmented_controlActive"] {{
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
  border-color: #3b82f6 !important;
  color: #ffffff !important;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.22),
    0 8px 20px rgba(59, 130, 246, 0.18) !important;
}}

[data-testid="stMetricValue"] {{
  color: var(--kfps-ink);
}}

[data-testid="stMetricLabel"],
[data-testid="stCaptionContainer"],
small {{
  color: var(--kfps-muted);
}}

.stButton > button,
.stDownloadButton > button {{
  background: var(--kfps-primary);
  border-color: var(--kfps-primary);
  color: #f8f6ef;
  border-radius: var(--kfps-radius-pill);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

.stButton > button:disabled,
.stDownloadButton > button:disabled {{
  background: var(--kfps-chip);
  color: var(--kfps-muted);
  border-color: var(--kfps-hairline);
}}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] textarea,
[data-baseweb="slider"] {{
  background: var(--kfps-surface);
  color: var(--kfps-ink);
  border-color: var(--kfps-hairline);
}}

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="textarea"] textarea {{
  border: 1px solid var(--kfps-hairline) !important;
  box-shadow: none !important;
  outline: none !important;
}}

[data-baseweb="input"] > div:hover,
[data-baseweb="select"] > div:hover,
[data-baseweb="textarea"] > div:hover,
[data-baseweb="textarea"] textarea:hover {{
  border-color: var(--kfps-hairline) !important;
}}

[data-baseweb="input"] > div:focus-within,
[data-baseweb="select"] > div:focus-within,
[data-baseweb="textarea"] > div:focus-within,
[data-baseweb="textarea"] textarea:focus {{
  border-color: var(--kfps-primary) !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--kfps-primary) 22%, transparent) !important;
}}

[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"],
[data-testid="stTextAreaRootElement"],
[data-baseweb="input"],
[data-baseweb="input"] [data-baseweb="base-input"],
[data-baseweb="textarea"],
[data-baseweb="textarea"] [data-baseweb="base-input"] {{
  border: 1px solid var(--kfps-hairline) !important;
  border-radius: var(--kfps-radius) !important;
  box-shadow: none !important;
  outline: none !important;
  background: var(--kfps-surface) !important;
  overflow: hidden !important;
  clip-path: inset(0 round var(--kfps-radius));
}}

[data-testid="stTextInputRootElement"] {{
  display: flex !important;
  align-items: stretch !important;
}}

[data-testid="stTextInputRootElement"] [data-baseweb="base-input"] {{
  flex: 1 1 auto !important;
  min-width: 0 !important;
  border: 0 !important;
}}

[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"],
[data-testid="stTextAreaRootElement"],
[data-baseweb="input"],
[data-baseweb="input"] > div,
[data-baseweb="input"] [data-baseweb="base-input"],
[data-baseweb="select"] > div,
[data-baseweb="textarea"],
[data-baseweb="textarea"] > div,
[data-baseweb="textarea"] [data-baseweb="base-input"],
[data-baseweb="textarea"] textarea,
[data-testid="stMetric"],
[data-testid="stExpander"],
[data-testid="stAlert"],
.kfps-inline-note,
.kfps-secret-status-card,
.kfps-flow-card,
.kfps-icon {{
  border-radius: var(--kfps-radius) !important;
}}

[data-testid="stTextInputRootElement"]::before,
[data-testid="stTextInputRootElement"]::after,
[data-testid="stNumberInputContainer"]::before,
[data-testid="stNumberInputContainer"]::after,
[data-testid="stTextAreaRootElement"]::before,
[data-testid="stTextAreaRootElement"]::after,
[data-baseweb="input"] > div::before,
[data-baseweb="input"] > div::after,
[data-baseweb="textarea"] > div::before,
[data-baseweb="textarea"] > div::after {{
  border: 0 !important;
  box-shadow: none !important;
  outline: none !important;
}}

[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within,
[data-baseweb="input"]:focus-within,
[data-baseweb="textarea"]:focus-within {{
  border-color: var(--kfps-primary) !important;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--kfps-primary) 22%, transparent) !important;
}}

[data-testid="stTextInputRootElement"] button,
[data-testid="stTextInputRootElement"] button:hover,
[data-testid="stTextInputRootElement"] button:focus,
[data-testid="stTextInputRootElement"] button:active {{
  align-self: stretch !important;
  min-width: 42px !important;
  width: 42px !important;
  height: auto !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  border-left: 1px solid var(--kfps-hairline) !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  outline: none !important;
  color: var(--kfps-muted) !important;
}}

[data-testid="stTextInputRootElement"] button svg {{
  color: var(--kfps-muted) !important;
  fill: currentColor !important;
  margin-left: auto !important;
  margin-right: 10px !important;
}}

[data-testid="stTextInputRootElement"] button,
[data-testid="stTextInputRootElement"] button:hover,
[data-testid="stTextInputRootElement"] button:focus,
[data-testid="stTextInputRootElement"] button:active {{
  border-left: 0 !important;
  justify-content: flex-end !important;
  width: 48px !important;
  min-width: 48px !important;
}}

[data-testid="stTextInputRootElement"] button::before,
[data-testid="stTextInputRootElement"] button::after {{
  display: none !important;
  border: 0 !important;
  box-shadow: none !important;
}}

[data-testid="stTextInputRootElement"] [data-baseweb="base-input"],
[data-testid="stNumberInputContainer"] [data-baseweb="base-input"],
[data-testid="stTextAreaRootElement"] [data-baseweb="base-input"],
[data-testid="stTextInputRootElement"] [data-baseweb="base-input"] > div,
[data-testid="stNumberInputContainer"] [data-baseweb="base-input"] > div,
[data-testid="stTextAreaRootElement"] [data-baseweb="base-input"] > div,
[data-testid="stNumberInputContainer"] [data-baseweb="input"],
[data-testid="stNumberInputContainer"] input,
[data-testid="stTextAreaRootElement"] textarea {{
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  outline: none !important;
  background: transparent !important;
  clip-path: none !important;
}}

[data-testid="stNumberInputContainer"] button,
[data-testid="stNumberInputContainer"] button:hover,
[data-testid="stNumberInputContainer"] button:focus,
[data-testid="stNumberInputContainer"] button:active {{
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}}

[data-testid="stExpander"] > details,
[data-testid="stExpander"] > details > summary,
[data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  background: var(--kfps-surface) !important;
}}

[data-testid="stExpander"] > details[open] > summary {{
  border-bottom: 1px solid var(--kfps-hairline) !important;
  border-bottom-left-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
}}

[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea,
[data-baseweb="select"] span {{
  color: var(--kfps-ink);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
}}

[data-baseweb="input"] input::placeholder,
[data-baseweb="textarea"] textarea::placeholder,
[data-testid="stTextInputRootElement"] input::placeholder,
[data-testid="stNumberInputContainer"] input::placeholder,
[data-testid="stTextAreaRootElement"] textarea::placeholder {{
  color: color-mix(in srgb, var(--kfps-muted) 72%, var(--kfps-surface)) !important;
  -webkit-text-fill-color:
    color-mix(in srgb, var(--kfps-muted) 72%, var(--kfps-surface)) !important;
  opacity: 1 !important;
}}

.st-key-kfps_concept_description [data-testid="stTextAreaRootElement"],
.st-key-kfps_target_hypothesis [data-testid="stTextAreaRootElement"],
.st-key-kfps_concept_description [data-baseweb="textarea"],
.st-key-kfps_target_hypothesis [data-baseweb="textarea"],
.st-key-kfps_concept_description [data-baseweb="textarea"] > div,
.st-key-kfps_target_hypothesis [data-baseweb="textarea"] > div,
.st-key-kfps_concept_description [data-baseweb="textarea"] [data-baseweb="base-input"],
.st-key-kfps_target_hypothesis [data-baseweb="textarea"] [data-baseweb="base-input"] {{
  box-sizing: border-box !important;
  height: var(--kfps-enter-card-height) !important;
  min-height: var(--kfps-enter-card-height) !important;
  max-height: var(--kfps-enter-card-height) !important;
}}

.st-key-kfps_concept_description textarea,
.st-key-kfps_target_hypothesis textarea {{
  box-sizing: border-box !important;
  height: 100% !important;
  min-height: 100% !important;
  max-height: 100% !important;
  resize: none !important;
}}

div[role="radiogroup"] label,
[data-testid="stCheckbox"] label {{
  background: transparent;
  color: var(--kfps-body);
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"],
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] {{
  position: relative !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 10px !important;
  width: auto !important;
  min-width: 0 !important;
  height: auto !important;
  min-height: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: var(--kfps-body) !important;
  accent-color: var(--kfps-primary) !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"] input[type="checkbox"],
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] input[type="checkbox"] {{
  -webkit-appearance: none !important;
  appearance: none !important;
  position: absolute !important;
  inset: 0 auto auto 0 !important;
  z-index: 3 !important;
  width: 22px !important;
  min-width: 22px !important;
  height: 22px !important;
  min-height: 22px !important;
  margin: 0 !important;
  padding: 0 !important;
  opacity: 0 !important;
  cursor: pointer !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"] > div:first-child,
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] > div:first-child {{
  position: relative !important;
  width: 22px !important;
  min-width: 22px !important;
  height: 22px !important;
  min-height: 22px !important;
  border: 1.5px solid var(--kfps-hairline) !important;
  border-radius: 6px !important;
  background: var(--kfps-surface) !important;
  box-shadow: none !important;
  pointer-events: none !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"]:has(input:checked) > div:first-child,
.st-key-kfps_injection_confirm [data-baseweb="checkbox"]:has(input:checked) > div:first-child {{
  border-color: var(--kfps-primary) !important;
  background: var(--kfps-primary) !important;
}}

.st-key-kfps_cost_confirm [data-baseweb="checkbox"] svg,
.st-key-kfps_injection_confirm [data-baseweb="checkbox"] svg {{
  color: #ffffff !important;
  fill: currentColor !important;
  pointer-events: none !important;
}}

[data-testid="stProgress"] > div > div {{
  background-color: var(--kfps-primary);
}}

hr {{
  border-color: var(--kfps-hairline);
}}

@media (max-width: 900px) {{
  .kfps-flow {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
  .kfps-flow-card::after {{
    display: none;
  }}
}}

/* Final layout overrides: keep the app bar, hero, and guide visually full-width. */
.block-container {{
  padding-top: 42px !important;
}}

.st-key-kfps_top_bar {{
  position: fixed !important;
  inset: 0 0 auto 0 !important;
  z-index: 999999 !important;
  width: 100vw !important;
  height: 60px !important;
  min-height: 60px !important;
  margin: 0 !important;
  padding: 8px 28px 8px 64px !important;
  box-sizing: border-box !important;
  background: var(--kfps-surface-alt) !important;
  border-bottom: 0 !important;
  box-shadow: none !important;
  overflow: hidden !important;
}}

.st-key-kfps_top_bar [data-testid="stHorizontalBlock"] {{
  width: 100% !important;
  min-width: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  flex-wrap: nowrap !important;
}}

.st-key-kfps_top_bar [data-testid="column"] {{
  width: auto !important;
  min-width: 0 !important;
}}

.st-key-kfps_top_bar [data-testid="column"]:first-child {{
  flex: 1 1 auto !important;
}}

.st-key-kfps_top_bar [data-testid="column"]:last-child {{
  flex: 0 0 318px !important;
  max-width: 318px !important;
}}

.st-key-kfps_top_controls [data-testid="stHorizontalBlock"] {{
  width: 100% !important;
  min-width: 0 !important;
  justify-content: flex-end !important;
  gap: 8px !important;
}}

.kfps-top-brandbar {{
  min-width: 0 !important;
  height: 40px !important;
  color: var(--kfps-ink) !important;
  position: fixed !important;
  top: 8px !important;
  left: 360px !important;
  z-index: 1000001 !important;
  width: auto !important;
  max-width: clamp(120px, calc(100vw - 678px), 330px) !important;
  transform: translateY(-1px);
}}

.stApp:has(.kfps-sidebar-hidden) .kfps-top-brandbar {{
  left: 56px !important;
  max-width: clamp(120px, calc(100vw - 374px), 330px) !important;
}}

.kfps-top-brandbar strong {{
  color: var(--kfps-ink) !important;
  font-size: 19px !important;
  font-weight: 900 !important;
  line-height: 1 !important;
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.kfps-top-toggle-labels {{
  position: fixed !important;
  top: 10px !important;
  right: 24px !important;
  z-index: 1000001 !important;
  display: grid !important;
  grid-template-columns: 32px 48px 32px 10px 42px 48px 34px;
  column-gap: 6px;
  align-items: center;
  height: 34px;
  color: var(--kfps-ink);
  pointer-events: none;
}}

.kfps-top-toggle-labels span,
.kfps-top-toggle-labels b {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--kfps-ink);
  font-size: 11px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0;
}}

.st-key-kfps_lang_is_kor,
.st-key-kfps_theme_is_dark {{
  position: fixed !important;
  top: 14px !important;
  z-index: 1000002 !important;
  width: 48px !important;
  min-width: 48px !important;
  height: 26px !important;
  min-height: 26px !important;
  margin: 0 !important;
}}

.st-key-kfps_lang_is_kor {{
  right: 220px !important;
}}

.st-key-kfps_theme_is_dark {{
  right: 64px !important;
}}

.st-key-kfps_lang_is_kor label,
.st-key-kfps_theme_is_dark label {{
  width: 48px !important;
  min-width: 48px !important;
  height: 26px !important;
  min-height: 26px !important;
}}

.kfps-toggle-copy,
.kfps-toggle-divider {{
  color: var(--kfps-ink) !important;
  font-size: 11px !important;
  font-weight: 900 !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"],
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"] {{
  position: relative !important;
  width: 48px !important;
  min-width: 48px !important;
  height: 26px !important;
  min-height: 26px !important;
  padding: 0 !important;
  border: 2.5px solid var(--kfps-ink) !important;
  border-radius: 9999px !important;
  background: var(--kfps-surface) !important;
  box-shadow: none !important;
  cursor: pointer !important;
  overflow: hidden !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"]:has(input:checked),
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"]:has(input:checked) {{
  background: var(--kfps-ink) !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"] > div,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"] > div {{
  opacity: 0 !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"] input,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"] input {{
  position: absolute !important;
  inset: 0 !important;
  z-index: 2 !important;
  width: 100% !important;
  height: 100% !important;
  opacity: 0 !important;
  cursor: pointer !important;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"]::after,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"]::after {{
  content: "";
  position: absolute;
  top: 4px;
  left: 4px;
  width: 13px;
  height: 13px;
  border-radius: 9999px;
  background: var(--kfps-ink);
  transition: transform 160ms ease, background-color 160ms ease;
}}

.st-key-kfps_lang_is_kor [data-baseweb="checkbox"]:has(input:checked)::after,
.st-key-kfps_theme_is_dark [data-baseweb="checkbox"]:has(input:checked)::after {{
  transform: translateX(23px);
  background: var(--kfps-surface);
}}

.kfps-hero,
.kfps-section-band {{
  width: calc(100vw - 360px) !important;
  margin-left: calc(50% - 50vw + 180px) !important;
  margin-right: 0 !important;
  box-sizing: border-box !important;
}}

.kfps-hero {{
  margin-top: -4px !important;
  padding-top: 44px !important;
  padding-bottom: 58px !important;
}}

div[data-testid="stElementContainer"]:has(.kfps-hero) {{
  margin-top: -4px !important;
}}

.kfps-guide {{
  width: calc(100vw - 360px) !important;
  margin-left: calc(50% - 50vw + 180px) !important;
  margin-right: 0 !important;
  box-sizing: border-box !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"],
[data-testid="stSidebar"] [data-testid="stExpander"] > details,
[data-testid="stSidebar"] [data-testid="stExpander"] details,
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  position: static !important;
  transform: none !important;
  clip-path: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"],
[data-testid="stSidebar"] [data-testid="stExpander"] > details {{
  overflow: hidden !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
  min-height: 44px !important;
  padding: 12px 34px 12px 0 !important;
  margin-bottom: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  list-style: none !important;
  position: relative !important;
  transition: color 180ms ease, background-color 180ms ease;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::-webkit-details-marker {{
  display: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary > div:first-child {{
  display: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
  display: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::before {{
  content: "";
  position: absolute;
  right: 9px;
  left: auto;
  top: 50%;
  z-index: 2;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--kfps-muted);
  border-bottom: 2px solid var(--kfps-muted);
  transform: translateY(-68%) rotate(45deg);
  transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1), border-color 180ms ease;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] details[open] summary::before {{
  transform: translateY(-34%) rotate(225deg);
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary::after {{
  right: -4px !important;
  left: auto !important;
  top: 50% !important;
  width: 28px !important;
  height: 28px !important;
  transform: translateY(-50%) !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stVerticalBlock"] {{
  padding-top: 8px !important;
  padding-bottom: 18px !important;
  overflow: hidden !important;
  opacity: 1 !important;
  animation: none !important;
  transition: none !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] details[open]
  [data-testid="stVerticalBlock"] {{
  display: block !important;
}}

.st-key-kfps_advanced_expander,
.st-key-kfps_advanced_expander *,
.st-key-kfps_advanced_expander summary,
.st-key-kfps_advanced_expander summary::before,
.st-key-kfps_advanced_expander summary::after,
.st-key-kfps_advanced_expander details,
.st-key-kfps_advanced_expander [data-testid="stVerticalBlock"] {{
  animation: none !important;
  transition: none !important;
}}

.st-key-kfps_advanced_expander summary:hover,
.st-key-kfps_advanced_expander summary:focus,
.st-key-kfps_advanced_expander summary:focus-visible,
.st-key-kfps_advanced_expander summary:active {{
  background: transparent !important;
  box-shadow: none !important;
  outline: none !important;
}}

.st-key-kfps_advanced_expander summary:hover::after,
.st-key-kfps_advanced_expander summary:focus::after,
.st-key-kfps_advanced_expander summary:focus-visible::after,
.st-key-kfps_advanced_expander summary:active::after {{
  background: transparent !important;
  opacity: 0 !important;
}}

@media (max-width: 640px) {{
  .st-key-kfps_top_bar {{
    left: 0 !important;
    padding-left: 56px !important;
    padding-right: 14px !important;
  }}
  .st-key-kfps_top_bar [data-testid="column"]:last-child {{
    flex-basis: 310px !important;
    max-width: 310px !important;
  }}
  .kfps-hero,
  .kfps-section-band,
  .kfps-guide {{
    width: 100vw !important;
    margin-left: calc(50% - 50vw) !important;
  }}
  .kfps-flow {{
    grid-template-columns: 1fr;
  }}
  .kfps-opinion-grid {{
    grid-template-columns: 1fr;
  }}
  .st-key-kfps_top_bar {{
    position: sticky;
    padding-left: 56px;
    padding-right: 16px;
  }}
  .kfps-top-brandbar {{
    min-width: 240px;
  }}
  .st-key-kfps_top_bar [data-baseweb="button-group"] {{
    justify-content: flex-start;
  }}
}}

/* 비용 확인 미체크 시 안내: 중앙 모달, 라이트 시트 (toast 대체) */
[data-testid="stDialog"] {{
  background: #ffffff !important;
  color: #111827 !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  border-radius: var(--kfps-radius) !important;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.22) !important;
}}

[data-testid="stDialog"] h2,
[data-testid="stDialog"] [data-testid="stDialogHeader"] {{
  color: #0f172a !important;
}}

[data-testid="stDialog"] [data-testid="stMarkdownContainer"],
[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p {{
  color: #1f2937 !important;
  font-size: 15px !important;
  line-height: 1.55 !important;
}}

[data-testid="stDialog"] button[aria-label="Close"],
[data-testid="stDialog"] header button {{
  color: #374151 !important;
}}
</style>
"""


def _utc_now_iso8601_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _provider_from_str(provider: str) -> Provider:
    normalized = provider.lower()
    if normalized not in {"openai", "anthropic", "google"}:
        raise ValueError(f"지원하지 않는 provider: {provider}")
    return cast(Provider, normalized)


def _safe_provider_key(provider: str, override_key: str) -> str | None:
    if override_key.strip():
        return override_key.strip()
    try:
        return get_provider_key(provider)
    except ValueError:
        return None


def _default_model_alias(model_options: list[str]) -> str:
    for preferred in BEGINNER_MODEL_PRIORITY:
        for option in model_options:
            if preferred in option:
                return option
    return model_options[0]


def _model_version_sort(alias: str) -> tuple[int, ...]:
    return tuple(-int(token) for token in alias.replace(".", "-").split("-") if token.isdigit())


def _model_sort_key(alias: str) -> tuple[str, int, tuple[int, ...], str]:
    lower = alias.lower()
    if lower.startswith("claude-"):
        claude_family_order = {"haiku": 0, "sonnet": 1, "opus": 2}
        for family, rank in claude_family_order.items():
            if f"claude-{family}" in lower:
                return ("claude", rank, _model_version_sort(lower), lower)
        return ("claude", 99, _model_version_sort(lower), lower)
    return (lower, 0, _model_version_sort(lower), lower)


def _sorted_model_options(pricing_config: dict[str, ModelPricing]) -> list[str]:
    return sorted(pricing_config.keys(), key=_model_sort_key)


def _run_mode_label(lang: str, mode_key: str) -> str:
    return ui_text(lang, f"mode_{mode_key}")


def ui_text(lang: str, key: str) -> str:
    return UI_COPY.get(lang, UI_COPY["KR"]).get(key, UI_COPY["KR"].get(key, key))


def _current_ui_state() -> tuple[str, str]:
    if "kfps_lang_is_kor" not in st.session_state:
        if "kfps_lang_is_en" in st.session_state:
            st.session_state["kfps_lang_is_kor"] = not bool(st.session_state["kfps_lang_is_en"])
        else:
            st.session_state["kfps_lang_is_kor"] = (
                st.session_state.get("kfps_language", DEFAULT_UI_LANGUAGE) == "KR"
            )

    if "kfps_theme_is_dark" not in st.session_state:
        st.session_state["kfps_theme_is_dark"] = st.session_state.get("kfps_theme") in {
            "Dark",
            "dark",
        }

    lang = "KR" if bool(st.session_state.get("kfps_lang_is_kor")) else "EN"
    theme = "dark" if bool(st.session_state.get("kfps_theme_is_dark")) else "light"
    return lang, theme


def apply_design_system(dark_mode: bool) -> None:
    st.html(build_comfort_ui_css(dark_mode))


def render_top_bar(lang_seed: str, theme_seed: str) -> tuple[str, bool]:
    product_name = html.escape(ui_text(lang_seed, "hero_title"))
    with st.container(key="kfps_top_bar"):
        if "kfps_sidebar_hidden" not in st.session_state:
            st.session_state["kfps_sidebar_hidden"] = False
        if st.button(" ", key="kfps_sidebar_toggle_button"):
            st.session_state["kfps_sidebar_hidden"] = not bool(
                st.session_state.get("kfps_sidebar_hidden")
            )
            st.rerun()
        state_class = "kfps-sidebar-hidden" if st.session_state.get("kfps_sidebar_hidden") else ""
        st.html(f'<span class="kfps-sidebar-state {state_class}" aria-hidden="true"></span>')
        st.html(
            f"""
            <div class="kfps-top-brandbar" aria-label="Product">
              <strong>{product_name}</strong>
            </div>
            <div class="kfps-top-toggle-labels" aria-hidden="true">
              <span>ENG</span>
              <span></span>
              <span>KOR</span>
              <b>/</b>
              <span>LIGHT</span>
              <span></span>
              <span>DARK</span>
            </div>
            """
        )
        lang_is_kor = st.toggle(
            "Language",
            key="kfps_lang_is_kor",
            label_visibility="collapsed",
            width="content",
        )
        theme_is_dark = st.toggle(
            "Theme",
            key="kfps_theme_is_dark",
            label_visibility="collapsed",
            width="content",
        )
    return ("KR" if lang_is_kor else "EN"), bool(theme_is_dark)


def render_secret_field_header(label: str, present: bool, help_text: str) -> None:
    state_class = "ok" if present else "missing"
    mark = "O" if present else "X"
    st.html(
        f"""
        <div class="kfps-secret-field-head">
          <span class="kfps-key-name">{html.escape(label)}</span>
          <span class="kfps-secret-field-actions">
            <span class="kfps-key-mark {state_class}" aria-label="{mark}">{mark}</span>
            <span class="material-symbols-rounded kfps-help-dot kfps-secret-help-icon"
                  data-tooltip="{html.escape(help_text, quote=True)}"
                  aria-label="{html.escape(help_text, quote=True)}" tabindex="0">help</span>
          </span>
        </div>
        """
    )


def render_secret_password_input(
    label: str,
    *,
    placeholder: str,
    key: str,
    present: bool,
    help_text: str,
) -> str:
    render_secret_field_header(label, present, help_text)
    return st.text_input(
        label,
        placeholder=placeholder,
        type="password",
        key=key,
        label_visibility="collapsed",
    )


def render_enter_card(lang: str) -> None:
    title = html.escape(ui_text(lang, "enter_card_title"))
    subtitle_raw = ui_text(lang, "enter_card_subtitle").strip()
    subtitle_html = (
        f'<span class="kfps-enter-subtitle">{html.escape(subtitle_raw)}</span>'
        if subtitle_raw
        else ""
    )
    body = html.escape(ui_text(lang, "enter_card_body"))
    st.html(
        f"""
        <div class="kfps-enter-card" role="note" aria-label="{title}">
          <div class="kfps-enter-top">
            <span class="material-symbols-rounded kfps-enter-arrow"
                  aria-hidden="true">keyboard_return</span>
            <span class="kfps-enter-title-stack">
              <strong>{title}</strong>
              {subtitle_html}
            </span>
          </div>
          <span class="kfps-enter-warning">
            <span class="material-symbols-rounded kfps-enter-warning-icon"
                  aria-hidden="true">warning</span>
            <span>{body}</span>
          </span>
        </div>
        """
    )


def render_inline_note(message: str, *, extra_class: str = "") -> None:
    class_name = "kfps-inline-note"
    if extra_class:
        class_name += f" {html.escape(extra_class, quote=True)}"
    st.html(f'<div class="{class_name}">{html.escape(message)}</div>')


def render_input_section_heading(title: str) -> None:
    st.html(
        f"""
        <div class="kfps-input-section-title" role="heading" aria-level="4">
          {html.escape(title)}
        </div>
        """
    )


def _estimate_sidebar_cost(sample_size: int, pricing: ModelPricing) -> tuple[float, float]:
    token_est = estimate_tokens(
        system_prompt_tokens=400,
        persona_tokens=350,
        concept_tokens=0,
        economic_context_tokens=140,
        schema_instruction_tokens=120,
        expected_output_tokens_per_persona=325,
        new_call_count=sample_size,
        cached_count=0,
    )
    cost_est = estimate_cost(
        token_est,
        pricing.input_per_million_usd,
        pricing.output_per_million_usd,
        concurrency=DEFAULT_CONCURRENCY,
    )
    return cost_est.estimated_cost_usd_low, cost_est.estimated_cost_usd_high


def render_model_metadata(
    pricing: ModelPricing,
    model_name: str,
    *,
    sample_size: int | None = None,
    lang: str = "KR",
) -> None:
    rows: list[tuple[str, str]] = [
        ("Provider", pricing.provider),
        ("Model", model_name),
        ("Input", f"${pricing.input_per_million_usd:.2f}/1M"),
        ("Output", f"${pricing.output_per_million_usd:.2f}/1M"),
    ]
    if sample_size is not None:
        low, high = _estimate_sidebar_cost(sample_size, pricing)
        rows.extend(
            [
                (
                    ui_text(lang, "estimated_price_label"),
                    ui_text(lang, "token_price_basis").format(sample_size=sample_size),
                ),
                (ui_text(lang, "total_cost_basis"), "included"),
                (ui_text(lang, "total_cost_label"), f"${low:.4f} - ${high:.4f}"),
            ]
        )
    row_html = "".join(
        '<div class="kfps-model-meta-row">'
        f'<span class="kfps-model-meta-label">{html.escape(label)}</span>'
        f'<span class="kfps-model-meta-value">{html.escape(value)}</span>'
        "</div>"
        for label, value in rows
    )
    st.html(f'<div class="kfps-model-meta">{row_html}</div>')


def nav_link_pills_html(lang: str, *, footer: bool = False) -> str:
    """Hero + footer: dataset, GitHub, Docs (same order as static landing)."""
    specs: tuple[tuple[str, str, str, str, bool, str], ...] = (
        (
            "🤗",
            ui_text(lang, "hero_pill_4").removeprefix("🤗 "),
            HF_DATASET_URL,
            "Hugging Face dataset",
            False,
            "kfps-pill-dataset",
        ),
        ("github", ui_text(lang, "hero_pill_5"), PUBLIC_GITHUB_REPO_URL, "GitHub", False, ""),
        (
            "📄",
            ui_text(lang, "hero_pill_docs"),
            docs_page_url(),
            ui_text(lang, "hero_docs_aria"),
            True,
            "",
        ),
        (
            "⚖",
            ui_text(lang, "hero_pill_license"),
            PUBLIC_GITHUB_LICENSE_URL,
            ui_text(lang, "hero_license_aria"),
            False,
            "kfps-pill-license",
        ),
    )
    cls_link = "kfps-footer-badge kfps-pill-link" if footer else "kfps-pill kfps-pill-link"
    parts: list[str] = []
    for icon, label, href, aria_label, same_tab, extra_class in specs:
        if icon == "github":
            icon_html = GITHUB_PILL_ICON_HTML
        else:
            icon_html = (
                f'<span class="kfps-pill-emoji" aria-hidden="true">{html.escape(icon)}</span>'
            )
        safe_label = html.escape(label)
        safe_href = html.escape(href)
        safe_aria = html.escape(aria_label)
        safe_class = f"{cls_link} {extra_class}".strip()
        target = "" if same_tab else ' target="_blank"'
        rel_attr = "" if same_tab else ' rel="noreferrer"'
        parts.append(
            f'<a class="{safe_class}" href="{safe_href}"{target}{rel_attr} '
            f'aria-label="{safe_aria}">{icon_html}<span>{safe_label}</span></a>'
        )
    return "".join(parts)


def hero_badges_html(lang: str) -> str:
    return nav_link_pills_html(lang, footer=False)


def utility_badges_html(lang: str, *, badge_class: str) -> str:
    assert badge_class == "kfps-footer-badge"
    return nav_link_pills_html(lang, footer=True)


def render_sidebar_title(lang: str) -> None:
    title = html.escape(ui_text(lang, "setup"))
    st.html(
        f"""
        <div class="kfps-sidebar-title">
          <span class="material-symbols-rounded kfps-sidebar-gear"
                aria-hidden="true">settings</span>
          <span>{title}</span>
        </div>
        """
    )


def render_section_band(
    title: str,
    caption: str,
    *,
    light: bool = False,
    variant: str = "",
) -> None:
    mode = " light" if light else ""
    variant_class = f" {variant}" if variant else ""
    safe_title = html.escape(title)
    safe_caption = html.escape(caption)
    st.html(
        f"""
        <section class="kfps-section-band{mode}{variant_class}">
          <div class="kfps-section-band-inner">
            <h2>{safe_title}</h2>
            <p>{safe_caption}</p>
          </div>
        </section>
        """
    )


def render_header(lang: str) -> None:
    hero_main = html.escape(ui_text(lang, "hero_main"))
    hero_subtext = html.escape(ui_text(lang, "hero_subtext"))
    hero_eyebrow = html.escape(ui_text(lang, "hero_eyebrow"))
    badges_html = hero_badges_html(lang)
    st.html(
        f"""
        <section class="kfps-hero">
          <div class="kfps-hero-eyebrow" aria-label="Release context">{hero_eyebrow}</div>
          <div class="kfps-hero-copy" aria-label="Tool summary">
            <span class="kfps-hero-main">{hero_main}</span>
            <span class="kfps-hero-subtext">{hero_subtext}</span>
          </div>
          <div class="kfps-hero-pills" aria-label="Run context">
            {badges_html}
          </div>
        </section>
        """
    )


def render_quick_guide(lang: str) -> None:
    cards = [
        (
            "guide_1_title",
            "guide_1_body",
            "guide_1_detail",
            "edit_note",
        ),
        (
            "guide_2_title",
            "guide_2_body",
            "guide_2_detail",
            "groups",
        ),
        (
            "guide_3_title",
            "guide_3_body",
            "guide_3_detail",
            "paid",
        ),
        (
            "guide_4_title",
            "guide_4_body",
            "guide_4_detail",
            "description",
        ),
    ]
    card_html = []
    for title_key, body_key, detail_key, icon_name in cards:
        card_html.append(
            f"""
            <details class="kfps-flow-card" name="kfps-flow">
              <summary>
                <div class="kfps-icon" aria-hidden="true">
                  <span class="material-symbols-rounded kfps-step-icon">
                    {html.escape(icon_name)}
                  </span>
                </div>
                <h3>{html.escape(ui_text(lang, title_key))}</h3>
                <p>{html.escape(ui_text(lang, body_key))}</p>
              </summary>
              <div class="kfps-flow-detail">{html.escape(ui_text(lang, detail_key))}</div>
            </details>
            """
        )
    st.html(
        f"""
        <section class="kfps-guide">
          <div class="kfps-guide-inner">
            <div class="kfps-eyebrow">{html.escape(ui_text(lang, "guide_eyebrow"))}</div>
            <h2>{html.escape(ui_text(lang, "guide_title"))}</h2>
            <div class="kfps-flow">
              {"".join(card_html)}
            </div>
          </div>
        </section>
        """
    )


def render_secrets_status(lang: str) -> None:
    status = load_secrets_from_env_path()
    with st.expander(ui_text(lang, "secrets_status_header"), expanded=False):
        if not status.env_path_exists:
            st.warning(ui_text(lang, "env_file_missing"))
        providers = (
            ("OpenAI", status.openai_present, ui_text(lang, "openai_key_help")),
            ("Anthropic", status.anthropic_present, ui_text(lang, "anthropic_key_help")),
            ("Google", status.google_present, ui_text(lang, "google_key_help")),
            ("HF Token", status.hf_token_present, ui_text(lang, "hf_status_help")),
        )
        cards = []
        for label, present, help_text in providers:
            state_class = "ok" if present else "missing"
            mark = ui_text(lang, "secret_present") if present else ui_text(lang, "secret_missing")
            cards.append(
                f"""
                <div class="kfps-secret-status-card">
                  <span class="kfps-secret-provider">{html.escape(label)}</span>
                  <span class="kfps-secret-state {state_class}">{html.escape(mark)}</span>
                  <span class="kfps-help-dot" data-tooltip="{html.escape(help_text, quote=True)}"
                        aria-label="{html.escape(help_text, quote=True)}" tabindex="0">?</span>
                </div>
                """
            )
        st.html(f'<div class="kfps-secret-status-grid">{"".join(cards)}</div>')


def render_concept_inputs(lang: str) -> dict[str, Any]:
    st.subheader(ui_text(lang, "concept_header"))

    render_input_section_heading(ui_text(lang, "input_section_basics"))
    basic_project_col, basic_category_col, basic_price_col = st.columns(3, gap="small")
    with basic_project_col:
        project_name = st.text_input(ui_text(lang, "project_name"), max_chars=100)
    with basic_category_col:
        category = st.text_input(
            ui_text(lang, "category"),
            placeholder=ui_text(lang, "category_placeholder"),
            max_chars=80,
        )
    with basic_price_col:
        product_price_usd = st.number_input(
            ui_text(lang, "price"),
            min_value=0.01,
            max_value=100_000.00,
            value=159.00,
            step=1.00,
            format="%.2f",
        )
        product_price_usd_cents = int(round(float(product_price_usd) * 100))

    render_input_section_heading(ui_text(lang, "input_section_style"))
    season_col, occasion_col, style_col = st.columns(3, gap="small")
    with season_col:
        season = st.text_input(
            ui_text(lang, "season"),
            placeholder=ui_text(lang, "season_placeholder"),
            max_chars=40,
        )
    with occasion_col:
        occasion = st.text_input(
            ui_text(lang, "occasion"),
            placeholder=ui_text(lang, "occasion_placeholder"),
            max_chars=120,
        )
    with style_col:
        style_tone = st.text_input(
            ui_text(lang, "style_tone"),
            placeholder=ui_text(lang, "style_tone_placeholder"),
            max_chars=80,
        )

    render_input_section_heading(ui_text(lang, "input_section_product"))
    fit_col, material_col, color_col = st.columns(3, gap="small")
    with fit_col:
        fit = st.text_input(
            ui_text(lang, "fit"),
            placeholder=ui_text(lang, "fit_placeholder"),
            max_chars=80,
        )
    with material_col:
        material = st.text_input(
            ui_text(lang, "material"),
            placeholder=ui_text(lang, "material_placeholder"),
            max_chars=80,
        )
    with color_col:
        color = st.text_input(
            ui_text(lang, "color"),
            placeholder=ui_text(lang, "color_placeholder"),
            max_chars=80,
        )

    render_input_section_heading(ui_text(lang, "input_section_target"))
    description_col, target_col, run_col = st.columns([1.35, 0.9, 0.9], gap="small")
    with description_col:
        description = st.text_area(
            ui_text(lang, "concept_text"),
            placeholder=ui_text(lang, "concept_placeholder"),
            max_chars=3000,
            height=272,
            key="kfps_concept_description",
        )
    with target_col:
        target_hypothesis = st.text_area(
            ui_text(lang, "target"),
            placeholder=ui_text(lang, "target_placeholder"),
            max_chars=1000,
            height=272,
            key="kfps_target_hypothesis",
        )

    with run_col, st.container(key="kfps_enter_overlay"):
        render_enter_card(lang)
        enter_button_placeholder = st.empty()
    raw_fields: dict[str, Any] = {
        "category": category,
        "price": product_price_usd_cents,
        "fit": fit,
        "material": material,
        "color": color,
        "season": season,
        "occasion": occasion,
        "style_tone": style_tone,
        "target_hypothesis": target_hypothesis,
        "description": description,
    }
    canonical_text = build_canonical_product_card_text(raw_fields)
    return {
        "project_name": project_name.strip() or "us-fashion-screener",
        "category": category.strip(),
        "product_price_usd_cents": product_price_usd_cents,
        "fit": fit.strip(),
        "material": material.strip(),
        "color": color.strip(),
        "season": season.strip(),
        "occasion": occasion.strip(),
        "style_tone": style_tone.strip(),
        "target_hypothesis": target_hypothesis.strip(),
        "description": normalize_concept_text(description),
        "canonical_product_card_text": canonical_text,
        "concept_text": canonical_text,
        "_enter_button_placeholder": enter_button_placeholder,
    }


def render_enter_button(placeholder: Any, lang: str, *, disabled: bool) -> None:
    """Paint ENTER into the slot created beside concept inputs (disabled follows run guards)."""
    with placeholder.container():
        if st.button(
            ui_text(lang, "run_button"),
            key="kfps_enter_card_button",
            use_container_width=True,
            disabled=disabled,
        ):
            st.session_state["kfps_enter_requested"] = True


def render_dataset_inputs(lang: str) -> dict[str, Any]:
    st.subheader(ui_text(lang, "dataset_header"))
    source = st.radio(
        ui_text(lang, "source"),
        ["huggingface", "local"],
        format_func=lambda v: ui_text(lang, "hf") if v == "huggingface" else ui_text(lang, "local"),
        horizontal=True,
    )
    if source == "huggingface":
        st.text_input(
            "HF dataset_id",
            value=DEFAULT_HF_DATASET_ID,
            disabled=True,
            help="공개판의 Hugging Face 연결은 이 데이터셋으로 고정해.",
        )
        split = st.text_input("split", value=DEFAULT_SPLIT)
        revision = st.text_input(
            "revision",
            value=DEFAULT_HF_REVISION,
            disabled=True,
            help="Pinned dataset commit SHA. This public release does not allow revision override.",
        )
        return {
            "source": source,
            "dataset_id": DEFAULT_HF_DATASET_ID,
            "split": split.strip() or DEFAULT_SPLIT,
            "revision": revision.strip() or DEFAULT_HF_REVISION,
        }

    local_path = st.text_input(ui_text(lang, "local_path"))
    return {"source": source, "local_path": local_path.strip()}


def render_sample_inputs(lang: str) -> dict[str, Any]:
    st.subheader(ui_text(lang, "panel_header"))
    sample_size = st.number_input(
        ui_text(lang, "sample_size"),
        min_value=1,
        max_value=MAX_SAMPLE_SIZE,
        value=30,
        step=10,
        help=ui_text(lang, "sample_help").format(max_sample=MAX_SAMPLE_SIZE),
    )
    sampling_seed = st.number_input(
        ui_text(lang, "sampling_seed"),
        min_value=0,
        value=42,
        step=1,
        help=ui_text(lang, "sampling_seed_help"),
    )
    age_min, age_max = st.slider(ui_text(lang, "age"), min_value=0, max_value=100, value=(0, 100))
    sex = st.multiselect(ui_text(lang, "sex"), ["M", "F"])
    state = st.multiselect(
        ui_text(lang, "state"),
        US_STATE_OPTIONS,
        help=ui_text(lang, "state_help"),
    )
    occupation = st.multiselect(
        ui_text(lang, "occupation"),
        OCCUPATION_KEYWORD_OPTIONS,
        help=ui_text(lang, "occupation_help"),
    )
    return {
        "sample_size": int(sample_size),
        "sampling_seed": int(sampling_seed),
        "filter": PersonaFilter(
            age_min=int(age_min) if age_min > 0 else None,
            age_max=int(age_max) if age_max < 100 else None,
            sex=frozenset(sex),
            state=frozenset(state),
            occupation_contains=frozenset(occupation),
        ),
    }


def render_model_inputs(pricing_config: dict[str, ModelPricing], lang: str) -> dict[str, Any]:
    st.subheader(ui_text(lang, "model_header"))
    model_options = _sorted_model_options(pricing_config)
    if not model_options:
        st.error(ui_text(lang, "model_missing"))
        return {}

    model_alias = st.selectbox(ui_text(lang, "model"), model_options)
    pricing = get_model_pricing(pricing_config, model_alias)
    model_name = pricing.provider_model_id or model_alias
    render_model_metadata(pricing, model_name, lang=lang)
    temperature = st.slider("temperature", 0.0, 1.0, DEFAULT_TEMPERATURE, 0.1)
    api_override = str(st.session_state.get("kfps_api_key", ""))
    hf_override = str(st.session_state.get("kfps_hf_token", ""))
    secrets_status = load_secrets_from_env_path()
    api_label = ui_text(lang, "api_key").format(provider=pricing.provider)
    api_key = render_secret_password_input(
        api_label,
        placeholder=ui_text(lang, "api_key_placeholder"),
        key="kfps_api_key",
        present=bool(_safe_provider_key(pricing.provider, api_override)),
        help_text=ui_text(lang, "api_key_help"),
    )
    hf_token = render_secret_password_input(
        ui_text(lang, "hf_token"),
        placeholder=ui_text(lang, "hf_token_placeholder"),
        key="kfps_hf_token",
        present=bool(hf_override.strip()) or secrets_status.hf_token_present,
        help_text=ui_text(lang, "hf_token_help"),
    )
    return {
        "model_alias": model_alias,
        "model_name": model_name,
        "provider": pricing.provider,
        "pricing": pricing,
        "temperature": float(temperature),
        "api_key": api_key,
        "hf_token": hf_token,
    }


def render_simple_setup(pricing_config: dict[str, ModelPricing], lang: str) -> dict[str, Any]:
    st.subheader(ui_text(lang, "quick_setup_header"))
    st.caption(ui_text(lang, "quick_setup_caption"))

    mode_labels = {
        _run_mode_label(lang, "quick"): "quick",
        _run_mode_label(lang, "balanced"): "balanced",
        _run_mode_label(lang, "deep"): "deep",
        _run_mode_label(lang, "max"): "max",
    }
    if st.session_state.get("kfps_run_mode") not in mode_labels:
        st.session_state.pop("kfps_run_mode", None)
    selected_mode_label = st.segmented_control(
        ui_text(lang, "run_mode"),
        options=list(mode_labels.keys()),
        default=_run_mode_label(lang, "balanced"),
        key="kfps_run_mode",
    )
    run_mode = mode_labels[str(selected_mode_label or _run_mode_label(lang, "balanced"))]
    preset = RUN_MODE_PRESETS[run_mode]
    render_inline_note(ui_text(lang, f"mode_{run_mode}_help"), extra_class="kfps-run-mode-note")

    model_options = _sorted_model_options(pricing_config)
    if not model_options:
        st.error(ui_text(lang, "model_missing"))
        return {}

    default_alias = _default_model_alias(model_options)
    pricing = get_model_pricing(pricing_config, default_alias)
    model_alias = default_alias
    model_name = pricing.provider_model_id or model_alias
    sample_size = int(preset["sample_size"])
    sampling_seed = 42
    temperature = float(preset["temperature"])
    dataset: dict[str, Any] = {
        "source": "huggingface",
        "dataset_id": DEFAULT_HF_DATASET_ID,
        "split": DEFAULT_SPLIT,
        "revision": DEFAULT_HF_REVISION,
    }
    sample = {
        "sample_size": sample_size,
        "sampling_seed": sampling_seed,
        "filter": PersonaFilter(),
    }

    with st.expander(
        ui_text(lang, "advanced_header"),
        expanded=False,
        key="kfps_advanced_expander",
        on_change="ignore",
    ):
        st.caption(ui_text(lang, "advanced_caption"))
        dataset = render_dataset_inputs(lang)

        st.subheader(ui_text(lang, "panel_header"))
        sample_size = st.number_input(
            ui_text(lang, "sample_size"),
            min_value=1,
            max_value=MAX_SAMPLE_SIZE,
            value=sample_size,
            step=10,
            help=ui_text(lang, "sample_help").format(max_sample=MAX_SAMPLE_SIZE),
        )
        sampling_seed = st.number_input(
            ui_text(lang, "sampling_seed"),
            min_value=0,
            value=sampling_seed,
            step=1,
            help=ui_text(lang, "sampling_seed_help"),
        )
        age_min, age_max = st.slider(
            ui_text(lang, "age"),
            min_value=0,
            max_value=100,
            value=(0, 100),
        )
        sex = st.multiselect(ui_text(lang, "sex"), ["M", "F"])
        state = st.multiselect(
            ui_text(lang, "state"),
            US_STATE_OPTIONS,
            help=ui_text(lang, "state_help"),
        )
        occupation = st.multiselect(
            ui_text(lang, "occupation"),
            OCCUPATION_KEYWORD_OPTIONS,
            help=ui_text(lang, "occupation_help"),
        )
        sample = {
            "sample_size": int(sample_size),
            "sampling_seed": int(sampling_seed),
            "filter": PersonaFilter(
                age_min=int(age_min) if age_min > 0 else None,
                age_max=int(age_max) if age_max < 100 else None,
                sex=frozenset(sex),
                state=frozenset(state),
                occupation_contains=frozenset(occupation),
            ),
        }

        temperature = st.slider("temperature", 0.0, 1.0, temperature, 0.1)

    st.caption(
        ui_text(lang, "simple_summary").format(
            mode=_run_mode_label(lang, run_mode),
            sample_size=sample["sample_size"],
            temperature=temperature,
        )
    )
    st.markdown(f"**{ui_text(lang, 'model_header')}**")
    model_alias = st.selectbox(
        ui_text(lang, "model"),
        model_options,
        index=model_options.index(model_alias),
        key="kfps_model_alias",
    )
    pricing = get_model_pricing(pricing_config, model_alias)
    model_name = pricing.provider_model_id or model_alias
    render_model_metadata(pricing, model_name, sample_size=int(sample["sample_size"]), lang=lang)
    api_override = str(st.session_state.get("kfps_api_key", ""))
    hf_override = str(st.session_state.get("kfps_hf_token", ""))
    secrets_status = load_secrets_from_env_path()
    api_label = ui_text(lang, "api_key").format(provider=pricing.provider)
    api_key = render_secret_password_input(
        api_label,
        placeholder=ui_text(lang, "api_key_placeholder"),
        key="kfps_api_key",
        present=bool(_safe_provider_key(pricing.provider, api_override)),
        help_text=ui_text(lang, "api_key_help"),
    )
    hf_token = render_secret_password_input(
        ui_text(lang, "hf_token"),
        placeholder=ui_text(lang, "hf_token_placeholder"),
        key="kfps_hf_token",
        present=bool(hf_override.strip()) or secrets_status.hf_token_present,
        help_text=ui_text(lang, "hf_token_help"),
    )

    return {
        "dataset": dataset,
        "sample": sample,
        "model": {
            "model_alias": model_alias,
            "model_name": model_name,
            "provider": pricing.provider,
            "pricing": pricing,
            "temperature": float(temperature),
            "api_key": api_key,
            "hf_token": hf_token,
        },
    }


def make_price_context(product_price_usd_cents: int) -> dict[str, Any]:
    ratio = price_burden_ratio(product_price_usd_cents)
    label = price_burden_label(ratio)
    return {
        "price_burden_ratio": ratio,
        "price_burden_label": label,
        "income_ratio": income_ratio(product_price_usd_cents),
        "bls_income_ratio": bls_income_ratio(product_price_usd_cents),
        "net_worth_ratio": net_worth_ratio(product_price_usd_cents),
        "apparel_services_annual_usd": BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS // 100,
        "bls_average_income_before_taxes_usd": BLS_2024_AVERAGE_INCOME_BEFORE_TAXES_USD,
        "census_median_household_income_usd": CENSUS_2024_MEDIAN_HOUSEHOLD_INCOME_USD,
        "fed_scf_median_family_net_worth_usd": FED_SCF_2022_MEDIAN_FAMILY_NET_WORTH_USD,
        "fed_scf_mean_family_net_worth_usd": FED_SCF_2022_MEAN_FAMILY_NET_WORTH_USD,
        "sources": OFFICIAL_US_CONTEXT_SOURCES,
    }


def _usd_whole(value: int | float) -> str:
    return f"${value:,.0f}"


def render_price_context(price_context: dict[str, Any], lang: str) -> None:
    st.subheader(ui_text(lang, "price_context_header"))
    apparel = _usd_whole(price_context["apparel_services_annual_usd"])
    census_income = _usd_whole(price_context["census_median_household_income_usd"])
    fed_net_worth = _usd_whole(price_context["fed_scf_median_family_net_worth_usd"])
    if lang == "KR":
        st.write(
            "상품 가격은 BLS 2024 연간 의류/서비스 지출 기준의 "
            f"**{price_context['price_burden_ratio']:.2f}배**야. "
            f"기준값: **{apparel}**, 라벨: **{price_context['price_burden_label']}**"
        )
        st.write(
            f"Census 2024 중위 가구소득 **{census_income}** 대비 "
            f"**{price_context['income_ratio']:.2%}**, Federal Reserve SCF 2022 "
            f"중위 가족 순자산 **{fed_net_worth}** 대비 "
            f"**{price_context['net_worth_ratio']:.2%}**야."
        )
    else:
        st.write(
            "Product price is "
            f"**{price_context['price_burden_ratio']:.2f}x** the BLS 2024 annual "
            f"Apparel and services baseline. Baseline: **{apparel}**, "
            f"label: **{price_context['price_burden_label']}**"
        )
        st.write(
            f"It is **{price_context['income_ratio']:.2%}** of Census 2024 median "
            f"household income **{census_income}** and "
            f"**{price_context['net_worth_ratio']:.2%}** of Federal Reserve SCF 2022 "
            f"median family net worth **{fed_net_worth}**."
        )
    st.caption(ui_text(lang, "price_context_caption"))


def make_cost_state(
    concept: dict[str, Any],
    sample: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    if not concept.get("description"):
        return {"ready": False}

    persona_avg_tokens = 350
    system_prompt_tokens = 400
    economic_context_tokens = 140
    schema_instruction_tokens = 120
    expected_output_tokens_per_persona = 325
    cached_count = 0
    new_call_count = sample["sample_size"] - cached_count

    concept_tokens = count_tokens_approx(concept["concept_text"])
    token_est = estimate_tokens(
        system_prompt_tokens=system_prompt_tokens,
        persona_tokens=persona_avg_tokens,
        concept_tokens=concept_tokens,
        economic_context_tokens=economic_context_tokens,
        schema_instruction_tokens=schema_instruction_tokens,
        expected_output_tokens_per_persona=expected_output_tokens_per_persona,
        new_call_count=new_call_count,
        cached_count=cached_count,
    )
    cost_est = estimate_cost(
        token_est,
        model["pricing"].input_per_million_usd,
        model["pricing"].output_per_million_usd,
        concurrency=DEFAULT_CONCURRENCY,
    )
    return {
        "ready": True,
        "new_call_count": new_call_count,
        "token_estimate": token_est,
        "cost_estimate": cost_est,
    }


def render_cost_estimate(cost_state: dict[str, Any], lang: str) -> None:
    st.subheader(ui_text(lang, "cost_header"))
    if not cost_state.get("ready"):
        render_inline_note(ui_text(lang, "need_concept"))
        return

    cost_est = cost_state["cost_estimate"]
    c1, c2, c3 = st.columns(3)
    c1.metric(ui_text(lang, "new_calls"), f"{cost_state['new_call_count']}명")
    c2.metric(
        ui_text(lang, "estimated_cost"),
        f"${cost_est.estimated_cost_usd_low:.4f} - ${cost_est.estimated_cost_usd_high:.4f}",
    )
    c3.metric(
        ui_text(lang, "estimated_time"),
        f"{cost_est.estimated_time_min_low:.1f} - {cost_est.estimated_time_min_high:.1f}분",
    )
    st.caption(ui_text(lang, "cost_caption"))


def _normalize_card_field(value: Any) -> str:
    text = normalize_concept_text("" if value is None else str(value))
    return text or PRODUCT_CARD_EMPTY_PLACEHOLDER


def _format_card_price(value: Any) -> str:
    try:
        price_cents = int(value)
    except (TypeError, ValueError):
        return PRODUCT_CARD_EMPTY_PLACEHOLDER
    if price_cents <= 0:
        return PRODUCT_CARD_EMPTY_PLACEHOLDER
    return f"${price_cents / 100:,.2f} USD"


def build_canonical_product_card_text(fields: dict[str, Any]) -> str:
    """Render the canonical product card text (locked field order and labels).

    The format is fixed: 10 lines, one per field, in PRODUCT_CARD_FIELD_ORDER.
    Each value is normalised through normalize_concept_text (NFC + invisible
    char strip + whitespace collapse + trim) so that semantically identical
    user input always produces an identical canonical string. Empty values
    collapse to "미입력". The price field is formatted from USD cents.

    The downstream concept_hash uses this canonical text, so the hash is
    stable across re-renders of the same product card and a single field
    change always changes the hash.
    """
    lines: list[str] = []
    for key in PRODUCT_CARD_FIELD_ORDER:
        label = PRODUCT_CARD_FIELD_LABELS_KR[key]
        if key == "price":
            normalized = _format_card_price(
                fields.get(key, fields.get("product_price_usd_cents", 0))
            )
        else:
            normalized = _normalize_card_field(fields.get(key, ""))
        lines.append(f"{label}: {normalized}")
    return "\n".join(lines)


def make_hashes(concept: dict[str, Any]) -> dict[str, str]:
    concept_hash = compute_concept_hash(
        concept["concept_text"],
        concept["category"],
        concept["product_price_usd_cents"],
    )
    price_context_hash = compute_price_context_hash(
        source="bls_census_federal_reserve",
        period="bls_2024+census_2024+scf_2022",
        denominator_usd_cents=BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS,
        price_context_version=DEFAULT_PRICE_CONTEXT_VERSION,
        extra_context=economic_baseline_hash_payload(),
    )
    return {"concept_hash": concept_hash, "price_context_hash": price_context_hash}


def render_hashes(hashes: dict[str, str], lang: str) -> None:
    with st.expander(ui_text(lang, "debug_hash")):
        st.code(
            f"concept_hash: {hashes['concept_hash']}\n"
            f"price_context_hash: {hashes['price_context_hash']}"
        )


def render_run_panel(lang: str) -> None:
    st.html(
        f"""
        <section class="kfps-run-panel">
          <h3>{html.escape(ui_text(lang, "run_confirm_header"))}</h3>
          <p>{html.escape(ui_text(lang, "run_panel_body"))}</p>
        </section>
        """
    )


def render_report_placeholder(lang: str) -> None:
    _, export_col = st.columns([4, 1])
    with export_col:
        st.download_button(
            ui_text(lang, "report_export_button"),
            data="",
            file_name="us-fashion-screener-report.md",
            mime="text/markdown",
            key="kfps_export_md_pending",
            type="primary",
            use_container_width=True,
            disabled=True,
        )
    st.html(
        f"""
        <span class="kfps-result-anchor" data-kfps-anchor="report-markdown"></span>
        <section class="kfps-report-shell kfps-report-empty" aria-live="polite">
          <div>
            <strong>{html.escape(ui_text(lang, "report_placeholder_title"))}</strong>
            <span>{html.escape(ui_text(lang, "report_placeholder_body"))}</span>
            <span>{html.escape(ui_text(lang, "report_placeholder_hint"))}</span>
          </div>
        </section>
        """
    )


def render_detailed_run_context(
    price_context: dict[str, Any],
    cost_state: dict[str, Any],
    hashes: dict[str, str],
    lang: str,
) -> None:
    with st.expander(ui_text(lang, "details_header"), expanded=False):
        st.caption(ui_text(lang, "details_summary"))
        render_price_context(price_context, lang)
        render_cost_estimate(cost_state, lang)
        render_hashes(hashes, lang)


def scroll_to_persona_results_once() -> None:
    if not st.session_state.pop("scroll_to_persona_results", False):
        return
    components.html(
        """
        <script>
        requestAnimationFrame(() => {
          const target = window.parent.document.querySelector(
            '[data-kfps-anchor="persona-results"]'
          );
          if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        });
        </script>
        """,
        height=0,
    )


def scroll_to_report_panel_once() -> None:
    components.html(
        """
        <script>
        requestAnimationFrame(() => {
          const target = window.parent.document.querySelector(
            '[data-kfps-anchor="report-markdown"]'
          );
          if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        });
        </script>
        """,
        height=0,
    )


def render_persona_results_anchor() -> None:
    st.html('<span class="kfps-result-anchor" data-kfps-anchor="persona-results"></span>')


def render_loading_panel(lang: str) -> None:
    st.html(
        f"""
        <section class="kfps-loading-panel" role="status" aria-live="polite">
          <span class="kfps-dot-spinner" aria-hidden="true"></span>
          <div>
            <strong>{html.escape(ui_text(lang, "results_loading"))}</strong>
          </div>
        </section>
        """
    )


def _persona_profile(persona_id: str, attrs: dict[str, Any]) -> str:
    values = [
        f"{attrs.get('age')}세" if attrs.get("age") is not None else "",
        str(attrs.get("sex", "")),
        str(attrs.get("state", "")),
        str(attrs.get("city", "")),
        str(attrs.get("occupation", "")),
    ]
    profile = " / ".join(value for value in values if value)
    return profile or persona_id


def build_persona_opinion_rows(
    result_rows: list[ResultRow],
    persona_attributes: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in result_rows:
        if row["status"] not in {"success", "cached"} or not row["response_json"]:
            continue
        parsed: EvaluationResult | None = None
        try:
            parsed = parse_evaluation_result(json.loads(row["response_json"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = None
        if parsed is None:
            continue
        attrs = persona_attributes.get(parsed.persona_id, {})
        rows.append(
            {
                "persona_id": parsed.persona_id,
                "profile": _persona_profile(parsed.persona_id, attrs),
                "sentiment": parsed.sentiment,
                "interest_score": str(parsed.interest_score),
                "price_burden": parsed.price_burden,
                "main_reasons": " / ".join(parsed.main_reasons),
                "main_concerns": " / ".join(parsed.main_concerns),
                "confidence_note": parsed.confidence_note,
            }
        )
    return rows


def persona_opinions_csv(rows: list[dict[str, str]]) -> str:
    fieldnames = [
        "persona_id",
        "profile",
        "sentiment",
        "interest_score",
        "price_burden",
        "main_reasons",
        "main_concerns",
        "confidence_note",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return "\ufeff" + output.getvalue()


def render_persona_opinion_preview(
    result_rows: list[ResultRow],
    persona_attributes: dict[str, dict[str, Any]],
    project_name: str,
    job_id: str,
    lang: str,
) -> None:
    opinion_rows = build_persona_opinion_rows(result_rows, persona_attributes)
    if not opinion_rows:
        render_inline_note(ui_text(lang, "persona_preview_empty"))
        return

    st.html(
        f"""
        <div class="kfps-opinion-head">
          <div>
            <h3>{html.escape(ui_text(lang, "results_preview_header"))}</h3>
            <p>{html.escape(ui_text(lang, "results_preview_body"))}</p>
          </div>
        </div>
        """
    )
    cards = []
    for row in opinion_rows[:5]:
        sentiment = html.escape(row["sentiment"])
        cards.append(
            f"""
            <article class="kfps-opinion-card">
              <div class="kfps-opinion-meta">
                <span>{html.escape(row["persona_id"])}</span>
                <span class="kfps-sentiment {sentiment}">{sentiment}</span>
              </div>
              <p class="kfps-opinion-profile">{html.escape(row["profile"])}</p>
              <h4>{html.escape(ui_text(lang, "persona_card_reasons"))}</h4>
              <p>{html.escape(row["main_reasons"] or "-")}</p>
              <h4>{html.escape(ui_text(lang, "persona_card_concerns"))}</h4>
              <p>{html.escape(row["main_concerns"] or "-")}</p>
              <h4>{html.escape(ui_text(lang, "persona_card_note"))}</h4>
              <p>{html.escape(row["confidence_note"])}</p>
            </article>
            """
        )
    st.html(f'<div class="kfps-opinion-grid">{"".join(cards)}</div>')
    st.download_button(
        ui_text(lang, "excel_download"),
        data=persona_opinions_csv(opinion_rows),
        file_name=f"{project_name}-{job_id}-persona-opinions.csv",
        mime="text/csv",
    )


def _persona_attributes_text(persona: Persona) -> str:
    location = " ".join(part for part in [persona.city, persona.state, persona.zipcode] if part)
    fields = [
        f"{persona.age}세",
        persona.sex,
        location,
        persona.occupation,
        persona.marital_status,
        persona.education_level,
    ]
    return " / ".join(field for field in fields if field)


def _persona_summary_text(persona: Persona) -> str:
    parts = [
        persona.persona_summary,
        persona.professional_text,
        persona.lifestyle_text,
        persona.interests_text,
    ]
    return "\n\n".join(part for part in parts if part)


def _persona_attributes(persona: Persona) -> dict[str, Any]:
    return {
        "age": persona.age,
        "sex": persona.sex,
        "state": persona.state,
        "city": persona.city,
        "zipcode": persona.zipcode,
        "occupation": persona.occupation,
    }


def _economic_context_text(concept: dict[str, Any], price_context: dict[str, Any]) -> str:
    return (
        f"Product price is ${concept['product_price_usd_cents'] / 100:,.2f} USD. "
        "Official U.S. economic reference points: "
        "BLS Consumer Expenditure Survey 2024 annual Apparel and services baseline "
        f"${price_context['apparel_services_annual_usd']:,.0f}; "
        "BLS 2024 average income before taxes "
        f"${price_context['bls_average_income_before_taxes_usd']:,.0f}; "
        "Census CPS ASEC 2024 median household income "
        f"${price_context['census_median_household_income_usd']:,.0f}; "
        "Federal Reserve SCF 2022 median family net worth "
        f"${price_context['fed_scf_median_family_net_worth_usd']:,.0f}. "
        f"Price is {price_context['price_burden_ratio']:.2f}x the apparel baseline, "
        f"{price_context['income_ratio']:.2%} of Census median household income, "
        f"and {price_context['net_worth_ratio']:.2%} of Fed SCF median family net worth. "
        f"Price burden label: {price_context['price_burden_label']}. "
        "These are national official baselines only, not persona-specific income, "
        "wealth, purchasing power, or purchase intent."
    )


def build_persona_payloads(
    personas: list[Persona],
    concept: dict[str, Any],
    model: dict[str, Any],
    price_context: dict[str, Any],
    hashes: dict[str, str],
    prompt_template_md: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    economic_context_text = _economic_context_text(concept, price_context)
    pricing = model["pricing"]
    for persona in personas:
        prompt = build_prompt(
            persona_id=persona.persona_id,
            persona_summary=_persona_summary_text(persona),
            persona_attributes_text=_persona_attributes_text(persona),
            economic_context_text=economic_context_text,
            category=concept["category"],
            concept_text=concept["concept_text"],
            price_usd_cents=concept["product_price_usd_cents"],
            prompt_template_md=prompt_template_md,
        )
        cache_key = compute_cache_key(
            persona_id=persona.persona_id,
            provider=model["provider"],
            concept_hash=hashes["concept_hash"],
            price_context_hash=hashes["price_context_hash"],
            model_name=model["model_name"],
            temperature=model["temperature"],
            prompt_version=prompt.prompt_version,
            schema_version=prompt.schema_version,
        )
        payloads.append(
            {
                "persona_id": persona.persona_id,
                "_cache_key": cache_key,
                "product_price_usd_cents": concept["product_price_usd_cents"],
                "prompt": {
                    "system": prompt.system,
                    "developer": prompt.developer,
                    "user": prompt.user,
                },
                "cache_metadata": {
                    "persona_id": persona.persona_id,
                    "concept_hash": hashes["concept_hash"],
                    "price_context_hash": hashes["price_context_hash"],
                    "provider": model["provider"],
                    "model_name": model["model_name"],
                    "temperature": model["temperature"],
                    "prompt_version": prompt.prompt_version,
                    "schema_version": prompt.schema_version,
                    "price_context_version": DEFAULT_PRICE_CONTEXT_VERSION,
                    "product_price_usd_cents": concept["product_price_usd_cents"],
                    "input_per_million_usd": pricing.input_per_million_usd,
                    "output_per_million_usd": pricing.output_per_million_usd,
                },
            }
        )
    return payloads


def make_run_meta(
    job_id: str,
    run_id: str,
    loaded_dataset: LoadedDataset,
    sample_size: int,
    sampling_seed: int,
    model: dict[str, Any],
    hashes: dict[str, str],
    matched_count_before_sample: int = 0,
    sampling_strategy: str = "unknown",
    filter_summary_text: str = "",
) -> RunMeta:
    return RunMeta(
        run_id=run_id,
        job_id=job_id,
        dataset_name=loaded_dataset.source,
        dataset_revision=loaded_dataset.dataset_revision,
        sample_size=sample_size,
        sampling_seed=sampling_seed,
        provider=model["provider"],
        model_name=model["model_name"],
        temperature=float(model["temperature"]),
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        price_context_version=DEFAULT_PRICE_CONTEXT_VERSION,
        concept_hash=hashes["concept_hash"],
        price_context_hash=hashes["price_context_hash"],
        dataset_split=loaded_dataset.dataset_split,
        matched_count_before_sample=matched_count_before_sample,
        sampling_strategy=sampling_strategy,
        filter_summary=filter_summary_text,
    )


def _cache_lookup(db_path: Path, cache_key: str) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT response_json FROM llm_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    return None if row is None else str(row[0])


def _cache_store(
    db_path: Path,
    cache_key: str,
    result: EvaluatorResult,
    metadata: dict[str, Any],
) -> None:
    response_json = result.get("response_json")
    if not response_json:
        return
    input_tokens_actual = result.get("input_tokens_actual")
    output_tokens_actual = result.get("output_tokens_actual")
    input_price = metadata.get("input_per_million_usd")
    output_price = metadata.get("output_per_million_usd")
    cost_actual_usd = None
    if (
        input_tokens_actual is not None
        and output_tokens_actual is not None
        and input_price is not None
        and output_price is not None
    ):
        cost_actual_usd = int(input_tokens_actual) / 1_000_000 * float(input_price) + int(
            output_tokens_actual
        ) / 1_000_000 * float(output_price)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO llm_cache ("
            "cache_key, persona_id, concept_hash, price_context_hash, provider, "
            "model_name, temperature, prompt_version, schema_version, "
            "price_context_version, response_json, raw_response_path, "
            "input_tokens_actual, output_tokens_actual, cost_actual_usd, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cache_key,
                metadata["persona_id"],
                metadata["concept_hash"],
                metadata["price_context_hash"],
                metadata["provider"],
                metadata["model_name"],
                float(metadata["temperature"]),
                metadata["prompt_version"],
                metadata["schema_version"],
                metadata["price_context_version"],
                response_json,
                None,
                input_tokens_actual,
                output_tokens_actual,
                cost_actual_usd,
                _utc_now_iso8601_z(),
            ),
        )
        conn.commit()


def _result_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def make_llm_evaluator_async(
    provider: Provider,
    model_name: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int = 600,
) -> Callable[[dict[str, Any]], Any]:
    async def _evaluate(payload: dict[str, Any]) -> EvaluatorResult:
        prompt = payload["prompt"]
        request_kwargs = {
            "provider": provider,
            "model_name": model_name,
            "api_key": api_key,
            "system": prompt["system"],
            "developer": prompt["developer"],
            "user": prompt["user"],
            "max_output_tokens": max_output_tokens,
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                request = LLMRequest(temperature=temperature, **request_kwargs)
                raw = await call_with_retry(request, client)
                status, parsed, error_summary = parse_llm_evaluation_result(
                    raw,
                    expected_persona_id=payload["persona_id"],
                )
                if status != "success" and temperature != 0.1:
                    retry_request = LLMRequest(temperature=0.1, **request_kwargs)
                    raw = await call_with_retry(retry_request, client)
                    status, parsed, error_summary = parse_llm_evaluation_result(
                        raw,
                        expected_persona_id=payload["persona_id"],
                    )
        except LLMClientError as exc:
            return {
                "status": "api_failed",
                "error_type": exc.error_type,
                "response_json": None,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        latency_ms = int((time.perf_counter() - started) * 1000)
        if status == "success" and parsed is not None:
            return {
                "status": "success",
                "error_type": None,
                "response_json": _result_json(parsed),
                "latency_ms": latency_ms,
                "input_tokens_actual": raw.input_tokens_actual,
                "output_tokens_actual": raw.output_tokens_actual,
            }
        return {
            "status": "parse_failed",
            "error_type": error_summary or "parse_failed",
            "response_json": None,
            "latency_ms": latency_ms,
        }

    return _evaluate


def make_cached_evaluator_async(
    db_path: Path,
    payloads: list[dict[str, Any]],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
) -> Callable[[dict[str, Any]], Any]:
    metadata_by_key = {payload["_cache_key"]: payload["cache_metadata"] for payload in payloads}

    async def _evaluate(payload: dict[str, Any]) -> EvaluatorResult:
        cache_key = str(payload["_cache_key"])
        cached_json = _cache_lookup(db_path, cache_key)
        if cached_json is not None:
            return {
                "status": "cached",
                "error_type": None,
                "response_json": cached_json,
                "latency_ms": 0,
                "cache_key": cache_key,
            }

        result = await llm_evaluator_async(payload)
        if result.get("status") == "success" and result.get("response_json"):
            result = dict(result)
            try:
                _cache_store(db_path, cache_key, result, metadata_by_key[cache_key])
            except Exception as exc:  # noqa: BLE001 - cache is best-effort.
                logger.warning(
                    "cache_store failed; continuing successful evaluation without cache FK: %s",
                    type(exc).__name__,
                )
            else:
                result["cache_key"] = cache_key
        return result

    return _evaluate


def make_cached_sync_evaluator(
    db_path: Path,
    payloads: list[dict[str, Any]],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
) -> SyncEvaluator:
    return make_sync_evaluator_for_worker(
        make_cached_evaluator_async(db_path, payloads, llm_evaluator_async)
    )


def load_result_rows(db_path: Path, run_id: str) -> list[ResultRow]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT persona_id, status, error_type, response_json, latency_ms "
            "FROM run_results WHERE run_id = ? ORDER BY persona_id",
            (run_id,),
        ).fetchall()
    return [
        {
            "persona_id": row[0],
            "status": row[1],
            "error_type": row[2],
            "response_json": row[3],
            "latency_ms": row[4],
        }
        for row in rows
    ]


def build_run_report(
    result_rows: list[ResultRow],
    persona_attributes: dict[str, dict[str, Any]],
    price_context: dict[str, Any] | None = None,
) -> RunReport:
    parsed_results: list[EvaluationResult] = []
    parse_failed = 0
    api_failed = 0

    for row in result_rows:
        status = row["status"]
        response_json = row["response_json"]
        if status in {"success", "cached"} and response_json:
            try:
                parsed_results.append(parse_evaluation_result(json.loads(response_json)))
            except Exception:
                parse_failed += 1
        elif status == "parse_failed":
            parse_failed += 1
        elif status == "api_failed":
            api_failed += 1

    quality = QualityCounts(
        success=len(parsed_results),
        parse_failed=parse_failed,
        api_failed=api_failed,
        total_attempted=len(result_rows),
        distribution_included=len(parsed_results),
    )
    report = aggregate(parsed_results, persona_attributes, quality)
    return RunReport(
        report_markdown=render_markdown(report, price_context),
        report_csv=render_csv(report, price_context),
        quality=quality,
    )


def _sampling_strategy_for_dataset(dataset: dict[str, Any]) -> str:
    if dataset["source"] == "huggingface":
        return "filter_then_seeded_reservoir"
    return "filter_then_seeded_random_sample"


def _load_and_sample(
    dataset: dict[str, Any],
    sample: dict[str, Any],
    *,
    hf_token: str | None = None,
):
    return _orchestrator_load_and_sample(
        dataset,
        sample,
        hf_token=hf_token,
        load_huggingface_dataset_fn=load_huggingface_dataset,
        load_local_file_fn=load_local_file,
    )


def _has_active_job_in_progress() -> bool:
    job_id = st.session_state.get("active_job_id")
    if not job_id:
        return False
    try:
        job = load_job_stats(DB_PATH, str(job_id))
    except KeyError:
        return False
    return job.status not in TERMINAL_STATUSES


def start_screening(
    concept: dict[str, Any],
    dataset: dict[str, Any],
    sample: dict[str, Any],
    model: dict[str, Any],
    price_context: dict[str, Any],
    hashes: dict[str, str],
    api_key: str,
) -> None:
    init_db(DB_PATH)
    if _has_active_job_in_progress():
        active_lang = "KR" if st.session_state.get("kfps_lang_is_kor") else "EN"
        st.warning(ui_text(active_lang, "active_job_notice"))
        return
    hf_token = str(model.get("hf_token", "")).strip() or None
    loaded, sampled = _load_and_sample(dataset, sample, hf_token=hf_token)
    if not sampled.rows:
        st.error("필터 조건에 맞는 페르소나가 0명이다.")
        return

    prompt_template_md = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    payloads = build_persona_payloads(
        sampled.rows,
        concept,
        model,
        price_context,
        hashes,
        prompt_template_md,
    )
    job_id = create_job(DB_PATH, total_count=len(payloads))
    run_id = str(uuid.uuid4())
    run_meta = make_run_meta(
        job_id=job_id,
        run_id=run_id,
        loaded_dataset=loaded,
        sample_size=sampled.sample_size,
        sampling_seed=sampled.sampling_seed,
        model=model,
        hashes=hashes,
        matched_count_before_sample=sampled.matched_count_before_sample,
        sampling_strategy=_sampling_strategy_for_dataset(dataset),
        filter_summary_text=filter_summary(sample["filter"]),
    )
    llm_evaluator = make_llm_evaluator_async(
        provider=_provider_from_str(model["provider"]),
        model_name=model["model_name"],
        api_key=api_key,
        temperature=float(model["temperature"]),
    )
    evaluator = make_cached_evaluator_async(DB_PATH, payloads, llm_evaluator)
    worker_input = WorkerInput(
        db_path=DB_PATH,
        job_id=job_id,
        run_meta=run_meta,
        persona_payloads=payloads,
        evaluator_async=evaluator,
        concurrency=DEFAULT_CONCURRENCY,
    )
    thread = start_worker_thread(worker_input)
    st.session_state["active_job_id"] = job_id
    st.session_state["active_run_id"] = run_id
    st.session_state["active_project_name"] = concept["project_name"]
    st.session_state["active_persona_attributes"] = {
        persona.persona_id: _persona_attributes(persona) for persona in sampled.rows
    }
    st.session_state["active_price_context"] = price_context
    st.session_state["active_thread_name"] = thread.name
    st.session_state["scroll_to_persona_results"] = True
    st.success(f"작업 시작: {job_id}")


def _render_job_panel_impl(lang: str) -> None:
    job_id = st.session_state.get("active_job_id")
    run_id = st.session_state.get("active_run_id")
    if not job_id or not run_id:
        render_report_placeholder(lang)
        return

    render_persona_results_anchor()
    scroll_to_persona_results_once()
    st.subheader(ui_text(lang, "status_header"))
    try:
        job = load_job_stats(DB_PATH, job_id)
    except KeyError:
        st.warning(ui_text(lang, "job_missing"))
        return

    done = job.cached_count + job.success_count + job.failed_count
    progress = done / job.total_count if job.total_count else 0.0
    st.progress(progress)
    cols = st.columns(5)
    cols[0].metric("status", job.status)
    cols[1].metric("total", job.total_count)
    cols[2].metric("cached", job.cached_count)
    cols[3].metric("success", job.success_count)
    cols[4].metric("failed", job.failed_count)

    if job.status not in TERMINAL_STATUSES:
        render_loading_panel(lang)
        render_report_placeholder(lang)
        c1, c2 = st.columns(2)
        if c1.button(ui_text(lang, "cancel")):
            request_cancel(DB_PATH, job_id)
            st.rerun()
        if c2.button(ui_text(lang, "refresh")):
            st.rerun()
        return

    result_rows = load_result_rows(DB_PATH, run_id)
    if not result_rows:
        render_inline_note(ui_text(lang, "no_results"))
        return

    persona_attributes = st.session_state.get("active_persona_attributes", {})
    try:
        run_report = build_run_report(
            result_rows,
            persona_attributes,
            st.session_state.get("active_price_context"),
        )
    except ValueError as exc:
        st.error(f"리포트 문구 검증 실패: {type(exc).__name__}")
        return

    project_name = st.session_state.get("active_project_name", "us-fashion-screener")

    st.html('<span class="kfps-result-anchor" data-kfps-anchor="report-markdown"></span>')

    rh1, rh2 = st.columns([4, 1])
    with rh1:
        st.subheader(ui_text(lang, "report_header"))
    with rh2:
        st.download_button(
            ui_text(lang, "report_export_button"),
            data=run_report.report_markdown,
            file_name=f"{project_name}-{job_id}.md",
            mime="text/markdown",
            key=f"kfps_export_md_{job_id}",
            type="primary",
            use_container_width=True,
        )

    tab_source, tab_rendered = st.tabs(
        [ui_text(lang, "report_tab_source"), ui_text(lang, "report_tab_rendered")]
    )
    with tab_source:
        report_source_label = html.escape(
            ui_text(lang, "report_tab_source"),
            quote=True,
        )
        report_source_markdown = html.escape(run_report.report_markdown)
        st.html(
            f"""
            <section class="kfps-report-shell" aria-label="{report_source_label}"
                     data-kfps-report="kfps_report_md_source">
              <pre class="kfps-report-selectable" tabindex="0">{report_source_markdown}</pre>
            </section>
            """
        )
    with tab_rendered:
        st.markdown(run_report.report_markdown)

    q = run_report.quality
    c1, c2, c3 = st.columns(3)
    c1.metric(ui_text(lang, "included"), q.distribution_included)
    c2.metric(ui_text(lang, "parse_failed"), q.parse_failed)
    c3.metric(ui_text(lang, "api_failed"), q.api_failed)

    st.caption(ui_text(lang, "report_footer_disclaimer"))

    render_persona_opinion_preview(
        result_rows,
        persona_attributes,
        project_name,
        job_id,
        lang,
    )

    st.markdown(f"#### {ui_text(lang, 'csv_download')}")
    st.download_button(
        ui_text(lang, "csv_download"),
        data=run_report.report_csv,
        file_name=f"{project_name}-{job_id}.csv",
        mime="text/csv",
        key=f"kfps_export_csv_{job_id}",
        use_container_width=True,
    )

    scroll_key = f"kfps_scrolled_report_{job_id}"
    if not st.session_state.get(scroll_key):
        st.session_state[scroll_key] = True
        scroll_to_report_panel_once()


@st.fragment(run_every=1)
def render_job_panel_fragment(lang: str) -> None:
    """Fragment wrapper: 1s polling for live job UI (disabled in AppTest via env)."""
    _render_job_panel_impl(lang)


def render_footer(lang: str) -> None:
    st.divider()
    st.html(
        f"""
        <div class="kfps-footer-badges" aria-label="Utility badges">
          {utility_badges_html(lang, badge_class="kfps-footer-badge")}
        </div>
        """
    )
    footer_lines = required_footer_text().splitlines()
    st.caption(
        "  \n".join(footer_lines[:2])
        + "\n\n"
        + "  \n".join(footer_lines[2:5])
        + "\n\n"
        + "License: AGPL-3.0-only"
        + "\n\n"
        + "  \n".join(footer_lines[5:])
    )


def main() -> None:
    st.set_page_config(page_title="US Fashion Persona Screener", layout="wide")
    lang_seed, theme_seed = _current_ui_state()
    apply_design_system(theme_seed == "dark")
    lang, _dark_mode = render_top_bar(lang_seed, theme_seed)
    init_db(DB_PATH)
    pricing_config = load_pricing_config(PRICING_CONFIG_PATH)

    render_header(lang)
    render_quick_guide(lang)
    render_secrets_status(lang)
    with st.sidebar:
        render_sidebar_title(lang)
        setup = render_simple_setup(pricing_config, lang)
        dataset = setup.get("dataset", {})
        sample = setup.get("sample", {})
        model = setup.get("model", {})
    if not model:
        return

    render_section_band(
        ui_text(lang, "section_project"),
        ui_text(lang, "section_project_caption"),
        light=True,
        variant="direction",
    )
    concept = render_concept_inputs(lang)
    enter_button_placeholder = concept.pop("_enter_button_placeholder")
    price_context = make_price_context(concept["product_price_usd_cents"])
    cost_state = make_cost_state(concept, sample, model)
    hashes = make_hashes(concept)

    injection_hits = detect_injection_keywords(concept["concept_text"])
    if injection_hits:
        st.warning(ui_text(lang, "injection_warning"))

    render_run_panel(lang)
    api_key = _safe_provider_key(model["provider"], model["api_key"])
    confirmed = st.checkbox(
        ui_text(lang, "cost_confirm"),
        value=False,
        key="kfps_cost_confirm",
    )
    if cost_state.get("ready") and not confirmed:
        render_inline_note(ui_text(lang, "cost_confirm_toast"))
    injection_confirmed = True
    if injection_hits:
        injection_confirmed = st.checkbox(
            ui_text(lang, "injection_confirm"),
            value=False,
            key="kfps_injection_confirm",
        )

    local_ready = dataset["source"] == "huggingface" or bool(dataset.get("local_path"))
    if dataset["source"] == "local" and dataset.get("local_path"):
        try:
            validate_local_path(Path(dataset["local_path"]))
        except FileNotFoundError:
            st.error("파일을 찾을 수 없습니다")
        except ValueError as exc:
            st.error(f"실행 준비 실패: {type(exc).__name__}")
    has_user_concept_input = bool(concept.get("description"))
    active_job_in_progress = _has_active_job_in_progress()
    run_button_disabled = not (
        cost_state.get("ready")
        and confirmed
        and injection_confirmed
        and has_user_concept_input
        and concept["category"]
        and api_key
        and local_ready
        and not active_job_in_progress
    )
    if not api_key:
        render_inline_note(ui_text(lang, "need_api_key"))
    if active_job_in_progress:
        render_inline_note(ui_text(lang, "active_job_notice"))

    render_enter_button(enter_button_placeholder, lang, disabled=run_button_disabled)

    enter_requested = bool(st.session_state.pop("kfps_enter_requested", False))

    if enter_requested and not run_button_disabled:
        try:
            start_screening(
                concept=concept,
                dataset=dataset,
                sample=sample,
                model=model,
                price_context=price_context,
                hashes=hashes,
                api_key=cast(str, api_key),
            )
        except DatasetAccessError as exc:
            st.error(exc.user_message)
        except (FileNotFoundError, ValueError) as exc:
            st.error(f"실행 준비 실패: {type(exc).__name__}")
        except Exception as exc:
            st.error(f"실행 시작 실패: {type(exc).__name__}")

    if os.environ.get("UFPS_APPTEST_SYNC_JOB_PANEL"):
        _render_job_panel_impl(lang)
    else:
        render_job_panel_fragment(lang)
    render_detailed_run_context(price_context, cost_state, hashes, lang)
    render_footer(lang)


if __name__ == "__main__":
    main()
