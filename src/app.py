# SPDX-License-Identifier: AGPL-3.0-only
"""Streamlit entry point for the local screener UI.

The app is a thin orchestration layer. Core work stays in the existing
modules: data loading, persona filtering, prompt construction, LLM calls,
worker lifecycle, aggregation, and report rendering.
"""

# ruff: noqa: E402

from __future__ import annotations

import html
import logging
import os
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx
import streamlit as st

from src.app_config import (
    APP_VERSION,
    DEFAULT_PRICE_CONTEXT_VERSION,
    DEFAULT_UI_LANGUAGE,
    MAX_SAMPLE_SIZE,
    OCCUPATION_KEYWORD_OPTIONS,
    PRODUCT_CARD_EMPTY_PLACEHOLDER,
    PRODUCT_CARD_FIELD_LABELS_KR,
    PRODUCT_CARD_FIELD_ORDER,
    RUN_MODE_PRESETS,
    TERMINAL_STATUSES,
    US_STATE_OPTIONS,
)
from src.cost_estimator import DEFAULT_CONCURRENCY
from src.data_loader import (
    DEFAULT_HF_DATASET_ID,
    DEFAULT_HF_REVISION,
    DEFAULT_SPLIT,
    DatasetAccessError,
    load_huggingface_dataset,
    load_local_file,
    validate_local_path,
)
from src.db import init_db
from src.job_manager import create_job, load_job_stats, request_cancel
from src.llm_client import call_with_retry
from src.orchestrator import (
    RunReport,
    _cache_lookup,
    _cache_store,
    _persona_attributes,
    _provider_from_str,
    _sampling_strategy_for_dataset,
    build_persona_payloads,
    build_run_report,
    load_result_rows,
    make_run_meta,
)
from src.orchestrator import _load_and_sample as _orchestrator_load_and_sample
from src.orchestrator import (
    make_cached_evaluator_async as _orchestrator_make_cached_evaluator_async,
)
from src.orchestrator import (
    make_cached_sync_evaluator as _orchestrator_make_cached_sync_evaluator,
)
from src.orchestrator import (
    make_llm_evaluator_async as _orchestrator_make_llm_evaluator_async,
)
from src.persona_filter import PersonaFilter, filter_summary
from src.pricing_config import load_pricing_config
from src.prompt_builder import PROMPT_VERSION, SCHEMA_VERSION, detect_injection_keywords
from src.report_writer import required_footer_text
from src.secrets_loader import get_provider_key, load_secrets_from_env_path
from src.ui.rendering import (
    _current_ui_state,
    _safe_provider_key,
    _sorted_model_options,
    apply_design_system,
    build_canonical_product_card_text,
    build_persona_opinion_rows,
    make_cost_state,
    make_hashes,
    make_price_context,
    persona_opinions_csv,
    render_concept_inputs,
    render_detailed_run_context,
    render_enter_button,
    render_header,
    render_inline_note,
    render_loading_panel,
    render_persona_opinion_preview,
    render_persona_results_anchor,
    render_quick_guide,
    render_reference_segment_control,
    render_report_placeholder,
    render_run_panel,
    render_secrets_status,
    render_section_band,
    render_sidebar_title,
    render_simple_setup,
    render_top_bar,
    scroll_to_persona_results_once,
    scroll_to_report_panel_once,
    ui_text,
    utility_badges_html,
)
from src.worker import WorkerInput, start_worker_thread

__all__ = (
    "APP_VERSION",
    "DB_PATH",
    "DEFAULT_HF_DATASET_ID",
    "DEFAULT_HF_REVISION",
    "DEFAULT_PRICE_CONTEXT_VERSION",
    "DEFAULT_SPLIT",
    "DEFAULT_UI_LANGUAGE",
    "MAX_SAMPLE_SIZE",
    "OCCUPATION_KEYWORD_OPTIONS",
    "PRODUCT_CARD_EMPTY_PLACEHOLDER",
    "PRODUCT_CARD_FIELD_LABELS_KR",
    "PRODUCT_CARD_FIELD_ORDER",
    "PROMPT_TEMPLATE_PATH",
    "PROMPT_VERSION",
    "PRICING_CONFIG_PATH",
    "RUN_MODE_PRESETS",
    "TERMINAL_STATUSES",
    "US_STATE_OPTIONS",
    "RunReport",
    "SCHEMA_VERSION",
    "DatasetAccessError",
    "PersonaFilter",
    "WorkerInput",
    "_cache_lookup",
    "_cache_store",
    "_current_ui_state",
    "_load_and_sample",
    "_persona_attributes",
    "_provider_from_str",
    "_sampling_strategy_for_dataset",
    "_sorted_model_options",
    "build_canonical_product_card_text",
    "build_persona_opinion_rows",
    "build_persona_payloads",
    "build_run_report",
    "call_with_retry",
    "detect_injection_keywords",
    "filter_summary",
    "get_provider_key",
    "httpx",
    "load_huggingface_dataset",
    "load_local_file",
    "load_pricing_config",
    "load_result_rows",
    "load_secrets_from_env_path",
    "main",
    "make_cached_evaluator_async",
    "make_cached_sync_evaluator",
    "make_hashes",
    "make_llm_evaluator_async",
    "make_price_context",
    "make_run_meta",
    "persona_opinions_csv",
    "required_footer_text",
    "start_worker_thread",
    "ui_text",
    "validate_local_path",
)

DB_PATH: Path = REPO_ROOT / "cache" / "screener.db"
PRICING_CONFIG_PATH: Path = REPO_ROOT / "config" / "pricing_config.yaml"
PROMPT_TEMPLATE_PATH: Path = REPO_ROOT / "prompts" / "concept_eval_ko_v0_3.md"
logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


ResultRow = dict[str, Any]
EvaluatorResult = dict[str, Any]
SyncEvaluator = Callable[[dict], EvaluatorResult]


def _active_job_status() -> str | None:
    job_id = st.session_state.get("active_job_id")
    if not job_id:
        return None
    try:
        return load_job_stats(DB_PATH, str(job_id)).status
    except KeyError:
        return None


def _has_active_job_in_progress() -> bool:
    return _active_job_status() in {"queued", "running"}


def make_llm_evaluator_async(
    provider,
    model_name: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int = 600,
):
    return _orchestrator_make_llm_evaluator_async(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        call_with_retry_fn=call_with_retry,
    )


def make_cached_evaluator_async(
    db_path: Path,
    payloads: list[dict[str, Any]],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
) -> Callable[[dict[str, Any]], Any]:
    return _orchestrator_make_cached_evaluator_async(
        db_path,
        payloads,
        llm_evaluator_async,
        cache_lookup_fn=_cache_lookup,
        cache_store_fn=_cache_store,
    )


def make_cached_sync_evaluator(
    db_path: Path,
    payloads: list[dict[str, Any]],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
) -> SyncEvaluator:
    return _orchestrator_make_cached_sync_evaluator(
        db_path,
        payloads,
        llm_evaluator_async,
        cache_lookup_fn=_cache_lookup,
        cache_store_fn=_cache_store,
    )


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
        reference_segment_id = render_reference_segment_control(lang)
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
    price_context = make_price_context(
        concept["product_price_usd_cents"],
        reference_segment_id=reference_segment_id,
    )
    cost_state = make_cost_state(concept, sample, model)
    hashes = make_hashes(concept, price_context)

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
