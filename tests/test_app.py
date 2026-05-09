"""Tests for src/app.py WS-APP integration helpers.

No real Streamlit browser, Hugging Face, or LLM/API calls. These tests keep
coverage on the app orchestration boundary without exercising external
services.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import src.app as app
from src.data_loader import LoadedDataset
from src.db import init_db
from src.llm_client import LLMRawResponse
from src.persona_normalizer import normalize_persona
from src.pricing_config import ModelPricing
from src.result_parser import EvaluationResult
from tests.fixtures.app_apptest_e2e import install_apptest_e2e_patches
from tests.fixtures.mock_evaluation_results import MOCK_PERSONA_ATTRIBUTES, MOCK_RESULTS

pytestmark = pytest.mark.no_network

APTEST_E2E_FAKE_API_KEY = "fake-apptest-e2e-provider-key-no-real-call"


PROMPT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "concept_eval_ko_v0_3.md"
)
APP_PATH = str(Path(__file__).resolve().parent.parent / "src" / "app.py")
APP_MODULE_SCRIPT = "import src.app as app\napp.main()\n"
HF_UNAUTH_WARNING = "Warning: You are sending unauthenticated requests to the HF Hub"


def _run_app() -> AppTest:
    return AppTest.from_file(APP_PATH).run(timeout=10)


def _run_app_kr() -> AppTest:
    at = _run_app()
    at.toggle[0].set_value(True)
    return at.run(timeout=10)


def _api_key_inputs(at: AppTest):
    return [widget for widget in at.text_input if "API KEY" in widget.proto.label.upper()]


def _hf_token_inputs(at: AppTest):
    return [widget for widget in at.text_input if "HF TOKEN" in widget.proto.label.upper()]


def _checkbox_by_label(at: AppTest, label: str):
    for widget in at.checkbox:
        if widget.proto.label == label:
            return widget
    raise AssertionError(f"checkbox not found: {label}")


def _text_input_by_label(at: AppTest, label: str):
    for widget in at.text_input:
        if widget.proto.label == label:
            return widget
    raise AssertionError(f"text input not found: {label}")


def _button_by_label(at: AppTest, label: str):
    for widget in at.button:
        if widget.proto.label == label:
            return widget
    raise AssertionError(f"button not found: {label}")


def _visible_text(at: AppTest) -> str:
    values: list[str] = []
    for group_name in ("caption", "info", "warning", "error", "success", "markdown", "html"):
        elements = getattr(at, group_name, None)
        if elements is None:
            elements = at.get(group_name)
        for element in elements:
            try:
                value = element.value
            except AttributeError:
                value = ""
            if not value and getattr(element, "type", "") == "html":
                value = getattr(getattr(element, "proto", None), "body", "")
            if value:
                text = str(value)
                if len(text) <= 100_000:
                    values.append(text)
    return "\n".join(values)


def _merge_ui_surface_text(at: AppTest) -> str:
    """Broad text sweep for completed-run assertions (markdown, headings, metrics)."""
    chunks: list[str] = [_visible_text(at)]
    for element in at.subheader:
        chunks.append(element.value)
    for element in at.markdown:
        chunks.append(element.value)
    for element in at.metric:
        chunks.append(element.proto.label)
        chunks.append(element.value)
    return "\n".join(chunks)


def _poll_until_terminal_report(at: AppTest, *, max_runs: int = 10) -> AppTest:
    """Worker + fragment may need several script reruns before job reaches terminal UI."""
    marker_avg = "평균 관심도"
    marker_report = "# us-fashion-persona"
    last_merged = ""
    for _ in range(max_runs):
        at.run(timeout=10)
        last_merged = _merge_ui_surface_text(at)
        if marker_avg in last_merged and marker_report in last_merged:
            return at
        if len(at.exception) > 0:
            pytest.fail(f"App exception during E2E poll: {at.exception[0].value!r}")
    pytest.fail(
        "Timed out waiting for completed report UI (worker/terminal path). "
        f"Last UI text tail: {last_merged[-1200:]!r}"
    )


@pytest.fixture
def concept() -> dict:
    return {
        "project_name": "test-project",
        "category": "니트웨어",
        "product_price_usd_cents": 15_900,
        "concept_text": "조용한 고급감의 미니멀 니트",
        "target_hypothesis": "30대 직장인",
    }


@pytest.fixture
def model() -> dict:
    return {
        "model_alias": "gpt-4o-mini",
        "model_name": "gpt-4o-mini",
        "provider": "openai",
        "temperature": 0.3,
        "pricing": ModelPricing(
            model_name="gpt-4o-mini",
            provider="openai",
            input_per_million_usd=0.15,
            output_per_million_usd=0.6,
        ),
    }


@pytest.fixture
def hashes() -> dict[str, str]:
    return {
        "concept_hash": "c" * 64,
        "price_context_hash": "p" * 64,
    }


@pytest.fixture
def price_context() -> dict:
    return app.make_price_context(15_900)


def test_build_persona_payloads_confines_concept_to_prompt(
    all_mock_personas: list[dict],
    concept: dict,
    model: dict,
    price_context: dict,
    hashes: dict[str, str],
) -> None:
    personas = [normalize_persona(all_mock_personas[0], 0)]
    assert personas[0] is not None

    payloads = app.build_persona_payloads(
        personas=personas,  # type: ignore[arg-type]
        concept=concept,
        model=model,
        price_context=price_context,
        hashes=hashes,
        prompt_template_md=PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8"),
    )

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["persona_id"] == all_mock_personas[0]["uuid"]
    assert payload["_cache_key"]
    assert "cache_key" not in payload
    assert payload["product_price_usd_cents"] == concept["product_price_usd_cents"]
    assert (
        payload["cache_metadata"]["product_price_usd_cents"] == concept["product_price_usd_cents"]
    )
    assert concept["concept_text"] in payload["prompt"]["user"]
    assert concept["concept_text"] not in payload["prompt"]["system"]
    assert concept["concept_text"] not in json.dumps(
        payload["cache_metadata"],
        ensure_ascii=False,
    )
    assert "Census CPS ASEC 2024 median household income" in payload["prompt"]["user"]
    assert "Federal Reserve SCF 2022 median family net worth" in payload["prompt"]["user"]
    assert "BLS Consumer Expenditure Survey 2024" in payload["prompt"]["user"]


def test_make_run_meta_uses_dataset_and_hash_metadata(
    model: dict,
    hashes: dict[str, str],
) -> None:
    loaded = LoadedDataset(
        source="local:test.csv",
        dataset_revision="loaded_at:test",
        total_rows=3,
        dataset_split="train",
    )
    meta = app.make_run_meta(
        job_id="job-1",
        run_id="run-1",
        loaded_dataset=loaded,
        sample_size=3,
        sampling_seed=42,
        model=model,
        hashes=hashes,
        matched_count_before_sample=12,
        sampling_strategy="filter_then_seeded_reservoir",
        filter_summary_text="state NY",
    )

    assert meta.job_id == "job-1"
    assert meta.run_id == "run-1"
    assert meta.dataset_name == "local:test.csv"
    assert meta.dataset_revision == "loaded_at:test"
    assert meta.concept_hash == hashes["concept_hash"]
    assert meta.price_context_hash == hashes["price_context_hash"]
    assert meta.prompt_version == app.PROMPT_VERSION
    assert meta.schema_version == app.SCHEMA_VERSION
    assert meta.dataset_split == "train"
    assert meta.matched_count_before_sample == 12
    assert meta.sampling_strategy == "filter_then_seeded_reservoir"
    assert meta.filter_summary == "state NY"


def test_make_price_context_includes_us_official_income_and_asset_baselines() -> None:
    context = app.make_price_context(20_010)

    assert context["price_burden_ratio"] == pytest.approx(0.1)
    assert context["price_burden_label"] == "low"
    assert context["apparel_services_annual_usd"] == 2_001
    assert context["bls_average_income_before_taxes_usd"] == 104_207
    assert context["census_median_household_income_usd"] == 83_730
    assert context["fed_scf_median_family_net_worth_usd"] == 192_900
    assert context["fed_scf_mean_family_net_worth_usd"] == 1_063_700
    assert context["income_ratio"] == pytest.approx(200.10 / 83_730)
    assert context["net_worth_ratio"] == pytest.approx(200.10 / 192_900)


def test_cached_sync_evaluator_uses_cache_without_llm_call(tmp_path: Path) -> None:
    db_path = tmp_path / "app-cache.db"
    init_db(db_path)
    cache_key = "k" * 64
    response_json = MOCK_RESULTS[0].model_dump_json()
    metadata = {
        "persona_id": MOCK_RESULTS[0].persona_id,
        "concept_hash": "c" * 64,
        "price_context_hash": "p" * 64,
        "provider": "openai",
        "model_name": "gpt-4o-mini",
        "temperature": 0.3,
        "prompt_version": app.PROMPT_VERSION,
        "schema_version": app.SCHEMA_VERSION,
        "price_context_version": app.DEFAULT_PRICE_CONTEXT_VERSION,
        "input_per_million_usd": 0.15,
        "output_per_million_usd": 0.6,
    }
    app._cache_store(  # noqa: SLF001 - app integration boundary helper.
        db_path,
        cache_key,
        {"status": "success", "response_json": response_json},
        metadata,
    )

    async def should_not_run(_payload: dict) -> dict:
        raise AssertionError("LLM evaluator must not run on cache hit")

    evaluator = app.make_cached_sync_evaluator(
        db_path,
        [
            {
                "persona_id": MOCK_RESULTS[0].persona_id,
                "_cache_key": cache_key,
                "cache_metadata": metadata,
            }
        ],
        should_not_run,
    )
    result = evaluator({"persona_id": MOCK_RESULTS[0].persona_id, "_cache_key": cache_key})

    assert result["status"] == "cached"
    assert result["response_json"] == response_json
    assert result["latency_ms"] == 0
    assert result["cache_key"] == cache_key


def test_make_llm_evaluator_async_parses_success(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = EvaluationResult(
        persona_id="p001",
        sentiment="positive",
        interest_score=8,
        price_burden="medium",
        main_reasons=["디자인"],
        main_concerns=[],
        confidence_note="테스트",
    )

    async def fake_call_with_retry(_request, _client):
        return LLMRawResponse(
            text=expected.model_dump_json(),
            input_tokens_actual=100,
            output_tokens_actual=50,
            used_structured_output=True,
        )

    monkeypatch.setattr(app, "call_with_retry", fake_call_with_retry)
    evaluator = app.make_llm_evaluator_async(
        provider="openai",
        model_name="gpt-4o-mini",
        api_key="fake-openai-key",
        temperature=0.3,
    )
    result = asyncio.run(
        evaluator(
            {
                "persona_id": "p001",
                "prompt": {"system": "s", "developer": None, "user": "u"},
            }
        )
    )

    assert result["status"] == "success"
    assert result["error_type"] is None
    assert json.loads(result["response_json"])["persona_id"] == "p001"
    assert result["latency_ms"] >= 0
    assert result["input_tokens_actual"] == 100
    assert result["output_tokens_actual"] == 50


def test_build_run_report_counts_cached_and_success_rows() -> None:
    result_rows = [
        {
            "persona_id": MOCK_RESULTS[0].persona_id,
            "status": "success",
            "error_type": None,
            "response_json": MOCK_RESULTS[0].model_dump_json(),
            "latency_ms": 10,
        },
        {
            "persona_id": MOCK_RESULTS[1].persona_id,
            "status": "cached",
            "error_type": None,
            "response_json": MOCK_RESULTS[1].model_dump_json(),
            "latency_ms": 0,
        },
        {
            "persona_id": "parse-bad",
            "status": "parse_failed",
            "error_type": "JSON 파싱 실패",
            "response_json": None,
            "latency_ms": 10,
        },
        {
            "persona_id": "api-bad",
            "status": "api_failed",
            "error_type": "timeout",
            "response_json": None,
            "latency_ms": None,
        },
    ]
    run_report = app.build_run_report(
        result_rows,
        MOCK_PERSONA_ATTRIBUTES,
        app.make_price_context(15_900),
    )

    assert run_report.quality.success == 2
    assert run_report.quality.parse_failed == 1
    assert run_report.quality.api_failed == 1
    assert run_report.quality.distribution_included == 2
    assert "합성 패널 2명 기준" in run_report.report_markdown
    assert "미국 공식 경제 맥락" in run_report.report_markdown
    assert "section,key,value" in run_report.report_csv
    assert "미국공식경제맥락" in run_report.report_csv

    opinion_rows = app.build_persona_opinion_rows(result_rows, MOCK_PERSONA_ATTRIBUTES)
    assert len(opinion_rows) == 2
    assert opinion_rows[0]["persona_id"] == MOCK_RESULTS[0].persona_id
    assert opinion_rows[0]["sentiment"] == MOCK_RESULTS[0].sentiment
    opinion_csv = app.persona_opinions_csv(opinion_rows)
    assert opinion_csv.startswith("\ufeffpersona_id,")
    assert "confidence_note" in opinion_csv


def test_app_source_has_no_unsafe_html_or_direct_asyncio_run() -> None:
    source = (Path(__file__).resolve().parent.parent / "src" / "app.py").read_text(encoding="utf-8")
    assert "unsafe_allow_html=True" not in source
    assert "asyncio.run" not in source
    assert "@st.fragment(run_every=1)" in source


def test_app_source_uses_readable_comfort_tokens_with_targeted_hero_gradient() -> None:
    source = (Path(__file__).resolve().parent.parent / "src" / "app.py").read_text(encoding="utf-8")
    assert "Pretendard" in source
    assert "#3a3d42" in source
    assert "#f7f6f2" in source
    assert "border-radius: 9999px" in source
    assert "--kfps-radius: 16px" in source
    assert "KOR" in source
    assert "ENG" in source
    assert "LIGHT" in source
    assert "DARK" in source
    assert "US Fashion Persona Screener" in source
    assert "api_key_help" in source
    assert "hf_token_help" in source
    assert "kfps-secret-field-head" in source
    assert "kfps-secret-status-grid" in source
    assert "kfps-help-dot" in source
    assert "kfps-secret-help-icon" in source
    assert ".kfps-secret-field-actions .kfps-help-dot::after" in source
    assert "--kfps-help-dot-ink" in source
    assert "비워두면 환경변수 사용" not in source
    assert "kfps-top-brandbar" in source
    assert 'ui_text(lang_seed, "hero_title")' in source
    assert "kfps-hero-copy" in source
    assert "kfps-hero-main" in source
    assert "kfps-hero-subtext" in source
    assert "kfps-enter-card" in source
    assert "kfps-enter-arrow" in source
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)" in source
    assert "--kfps-enter-card-height: 272px" in source
    assert "padding: 92px 28px 30px" in source
    assert "kfps_enter_overlay" in source
    assert ".st-key-kfps_enter_overlay" in source
    assert "margin: 44px auto 0" in source
    assert "kfps_enter_card_button" in source
    assert "kfps_cost_confirm" in source
    assert "render_enter_button" in source
    assert "data-tooltip" in source
    assert "Toggle sidebar" not in source
    assert "render_report_placeholder" in source
    assert "kfps_report_md_source" in source
    assert "st-key-kfps_export_md_pending" in source
    assert ".st-key-kfps_export_md_pending button:hover" in source
    assert 'class*="st-key-kfps_export_md_"' in source
    assert "pointer-events: auto !important" in source
    assert "scroll_to_report_panel_once" in source
    assert "kfps_advanced_expander" in source
    assert 'input[type="checkbox"]' in source
    assert "appearance: none !important" in source
    assert "accent-color: var(--kfps-primary)" in source
    assert ".st-key-kfps_advanced_expander summary:hover::after" in source
    assert "opacity: 0 !important" in source
    assert "kfps-dot-spinner" in source
    assert "render_persona_opinion_preview" in source
    assert "persona_opinions_csv" in source
    assert "enter_card_title" in source
    assert "enter_card_subtitle" in source
    assert "enter_card_body" in source
    assert "FABRIC_PATH" in source
    assert "hero-skyblue-fabric.png" in source
    assert "DIRECTION_BG_PATH" in source
    assert "direction-bg.png" in source
    assert 'variant="direction"' in source
    assert "설문 전, 먼저 반응을 읽다" in source
    assert "본조사 전 반응의 흐름을 빠르게 확인합니다." in source
    assert "쉬운 4단계 진행" in source
    assert "방향성을 잡아보세요" in source
    assert "Material Symbols Rounded" in source
    assert "groups" in source
    assert "description" in source
    assert "FAST" in source
    assert "BALANCE" in source
    assert "HIGH" in source
    assert "MAX" in source
    assert "MAX_SAMPLE_SIZE = 1000" in source
    assert "sampling-seed" in source
    assert "US_STATE_OPTIONS" in source
    assert "OCCUPATION_KEYWORD_OPTIONS" in source
    assert "HF TOKEN" in source
    assert "Final total" in source
    assert "kfps-run-mode-note" in source
    assert "_sorted_model_options" in source
    assert "st.toggle" in source
    assert "st.expander" in source
    assert "kfps-expander-reveal" not in source
    assert "clip-path: inset(0 0 100% 0)" not in source
    assert "stBaseButton-header" in source
    assert "stExpandSidebarButton" in source
    assert "stSidebarCollapseButton" in source
    assert "kfps_sidebar_toggle_button" in source
    assert "kfps-sidebar-hidden" in source
    assert "kfps-model-meta" in source
    assert "kfps-flow-card" in source
    assert "kfps-footer-badges" in source
    assert "kfps-footer-badge" in source
    assert "🤗 nvidia/Nemotron-Personas-USA" in source
    assert "GitHub" in source
    assert "GITHUB_PILL_ICON_HTML" in source
    assert "GITHUB_MARK_MASK_URI" in source
    assert "kfps-pill-github" in source
    assert "hero_pill_docs" in source
    assert "docs_page_url" in source
    assert "docs/index.html" not in source
    assert "docs/docs.html" in source
    assert "📄" in source
    assert "woooya129-ai/us-fashion-persona" in source
    assert "로컬 퍼블릭 베타 · v{APP_VERSION}" in source
    assert "설명 ⇄ 도구" not in source
    assert "st.segmented_control" in source


def test_apptest_initial_screen_renders_without_exceptions() -> None:
    at = _run_app()

    assert len(at.exception) == 0
    assert len(at.toggle) == 2
    assert at.toggle[0].proto.label == "Language"
    assert at.toggle[1].proto.label == "Theme"
    assert len(at.segmented_control) == 1
    assert at.segmented_control[0].proto.label == app.ui_text("EN", "run_mode")
    assert len(at.selectbox) >= 1
    assert at.selectbox[0].proto.label == app.ui_text("EN", "model")
    run_button_label = app.ui_text("EN", "run_button")
    run_buttons = [button for button in at.button if button.proto.label == run_button_label]
    assert len(run_buttons) == 1
    assert run_buttons[0].proto.disabled is True


def test_apptest_api_key_input_is_password() -> None:
    at = _run_app()
    api_inputs = _api_key_inputs(at)
    hf_inputs = _hf_token_inputs(at)

    assert len(api_inputs) == 1
    assert "type: PASSWORD" in str(api_inputs[0].proto)
    assert len(hf_inputs) == 1
    assert "type: PASSWORD" in str(hf_inputs[0].proto)


def test_app_sampling_and_filter_limits_are_explicit() -> None:
    assert app.MAX_SAMPLE_SIZE == 1000
    assert app.RUN_MODE_PRESETS["max"]["sample_size"] == 1000
    assert len(app.US_STATE_OPTIONS) == 52
    assert "CA" in app.US_STATE_OPTIONS
    assert "DC" in app.US_STATE_OPTIONS
    assert "VI" not in app.US_STATE_OPTIONS
    assert "California" not in app.US_STATE_OPTIONS
    assert len(app.OCCUPATION_KEYWORD_OPTIONS) == 15
    assert app.ui_text("KR", "sampling_seed") == "sampling-seed"


def test_v053_runtime_structure_modules_keep_us_sources() -> None:
    import src.app_config as app_config
    import src.orchestrator as orchestrator
    import src.ui.assets as assets

    assert app_config.APP_VERSION == "0.5.3"
    assert app_config.DEFAULT_PRICE_CONTEXT_VERSION == app.DEFAULT_PRICE_CONTEXT_VERSION
    assert app.DEFAULT_HF_DATASET_ID == "nvidia/Nemotron-Personas-USA"
    assert assets.HF_DATASET_URL == "https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA"
    assert hasattr(orchestrator, "build_persona_payloads")
    assert hasattr(orchestrator, "_load_and_sample")


def test_load_and_sample_hf_passes_explicit_token(
    monkeypatch: pytest.MonkeyPatch,
    all_mock_personas: list[dict],
) -> None:
    captured_kwargs: dict[str, object] = {}

    def fake_load_huggingface_dataset(**kwargs):
        captured_kwargs.update(kwargs)
        return LoadedDataset("huggingface:test", "fixture", -1), iter(all_mock_personas[:1])

    monkeypatch.setattr(app, "load_huggingface_dataset", fake_load_huggingface_dataset)

    app._load_and_sample(  # noqa: SLF001 - app orchestration helper.
        {
            "source": "huggingface",
            "dataset_id": app.DEFAULT_HF_DATASET_ID,
            "split": app.DEFAULT_SPLIT,
            "revision": app.DEFAULT_HF_REVISION,
        },
        {"sample_size": 1, "sampling_seed": 1, "filter": app.PersonaFilter()},
        hf_token="hf_TEST_TOKEN",
    )

    assert captured_kwargs["dataset_id"] == "nvidia/Nemotron-Personas-USA"
    assert captured_kwargs["revision"] == app.DEFAULT_HF_REVISION
    assert captured_kwargs["token"] == "hf_TEST_TOKEN"


def test_app_default_prompt_template_is_v0_3() -> None:
    assert app.PROMPT_TEMPLATE_PATH.name == "concept_eval_ko_v0_3.md"
    assert PROMPT_TEMPLATE_PATH == app.PROMPT_TEMPLATE_PATH


def test_model_options_sort_claude_family_order() -> None:
    pricing_config = {
        "gpt-5.4-mini": object(),
        "claude-opus-4-6": object(),
        "claude-haiku-4-5": object(),
        "claude-sonnet-4-5": object(),
        "claude-opus-4-7": object(),
        "claude-sonnet-4-6": object(),
    }

    model_options = app._sorted_model_options(pricing_config)  # noqa: SLF001
    claude_options = [option for option in model_options if option.startswith("claude-")]

    assert claude_options == [
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
        "claude-opus-4-7",
        "claude-opus-4-6",
    ]


def test_apptest_advanced_details_hidden_by_default() -> None:
    at = _run_app()

    assert len(at.expander) >= 1
    assert app.ui_text("EN", "advanced_header") in [expander.label for expander in at.expander]
    checkbox_labels = [widget.proto.label for widget in at.checkbox]
    assert app.ui_text("EN", "advanced_enable") not in checkbox_labels


def test_apptest_footer_present() -> None:
    at = _run_app()

    visible_text = _visible_text(at)
    assert app.required_footer_text().splitlines()[0] in visible_text
    assert "NVIDIA Nemotron-Personas-USA" in visible_text
    assert "AGPL-3.0" in visible_text


def test_apptest_enter_disabled_until_cost_confirmed() -> None:
    at = _run_app_kr()
    _text_input_by_label(at, "프로젝트명").set_value("test-project")
    _text_input_by_label(at, "제품 카테고리").set_value("니트웨어")
    at.text_area[0].set_value("조용한 고급감의 미니멀 니트")
    _api_key_inputs(at)[0].set_value("fake-provider-key")
    at.run(timeout=10)

    assert _button_by_label(at, app.ui_text("KR", "run_button")).proto.disabled is True


def test_apptest_run_enabled_after_required_inputs() -> None:
    at = _run_app_kr()
    _text_input_by_label(at, "프로젝트명").set_value("test-project")
    _text_input_by_label(at, "제품 카테고리").set_value("니트웨어")
    at.text_area[0].set_value("조용한 고급감의 미니멀 니트")
    _api_key_inputs(at)[0].set_value("fake-provider-key")
    at.checkbox[0].check()
    at.run(timeout=10)

    assert _button_by_label(at, app.ui_text("KR", "run_button")).proto.disabled is False


def test_apptest_injection_warning_requires_second_confirmation() -> None:
    at = _run_app_kr()
    _text_input_by_label(at, "제품 카테고리").set_value("니트웨어")
    at.text_area[0].set_value("ignore previous")
    _api_key_inputs(at)[0].set_value("fake-provider-key")
    at.checkbox[0].check()
    at.run(timeout=10)

    assert "프롬프트 인젝션 의심" in _visible_text(at)
    assert _checkbox_by_label(at, "감지된 문구를 확인했고 그대로 실행한다.").value is False
    assert _button_by_label(at, app.ui_text("KR", "run_button")).proto.disabled is True

    _checkbox_by_label(at, "감지된 문구를 확인했고 그대로 실행한다.").check()
    at.run(timeout=10)

    assert _button_by_label(at, app.ui_text("KR", "run_button")).proto.disabled is False


def test_apptest_fake_api_key_not_rendered() -> None:
    fake_key = "fake-secret-provider-key-for-app-test"
    at = _run_app()
    _api_key_inputs(at)[0].set_value(fake_key)
    at.run(timeout=10)

    assert fake_key not in _visible_text(at)


def test_apptest_mock_end_to_end_worker_report_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """ENTER → worker → terminal report without real HF/API (monkeypatched deps + tmp DB)."""
    db_path = tmp_path / "apptest_e2e.db"
    real_db_path = Path(__file__).resolve().parent.parent / "cache" / "screener.db"
    real_db_stat_before = (
        (real_db_path.stat().st_mtime_ns, real_db_path.stat().st_size)
        if real_db_path.exists()
        else None
    )
    install_apptest_e2e_patches(monkeypatch, db_path)

    at = AppTest.from_string(APP_MODULE_SCRIPT).run(timeout=10)
    at.toggle[0].set_value(True)
    at = at.run(timeout=10)
    assert len(at.exception) == 0

    _text_input_by_label(at, "프로젝트명").set_value("e2e-project")
    _text_input_by_label(at, "제품 카테고리").set_value("니트웨어")
    at.text_area[0].set_value("조용한 고급감의 미니멀 니트")
    _api_key_inputs(at)[0].set_value(APTEST_E2E_FAKE_API_KEY)
    _checkbox_by_label(at, app.ui_text("KR", "cost_confirm")).check()

    at = at.run(timeout=10)
    assert len(at.exception) == 0
    run_button = _button_by_label(at, app.ui_text("KR", "run_button"))
    assert run_button.proto.disabled is False

    at = run_button.click().run(timeout=30)

    merged_after_start = _merge_ui_surface_text(at)
    assert APTEST_E2E_FAKE_API_KEY not in merged_after_start
    assert "작업 시작" in merged_after_start or "작업 시작" in _visible_text(at)

    at = _poll_until_terminal_report(at)
    merged = _merge_ui_surface_text(at)

    assert APTEST_E2E_FAKE_API_KEY not in merged
    assert app.ui_text("KR", "status_header") in merged
    assert app.ui_text("KR", "report_header") in merged
    assert "평균 관심도" in merged
    assert "주요 긍정 이유" in merged
    assert "주요 망설임 이유" in merged
    assert app.required_footer_text().splitlines()[0] in merged
    assert app.ui_text("KR", "report_footer_disclaimer") in merged

    metric_blob = " ".join(f"{m.proto.label}:{m.value}" for m in at.metric)
    assert "status" in metric_blob
    assert app.ui_text("KR", "included") in metric_blob
    assert app.ui_text("KR", "parse_failed") in metric_blob
    assert app.ui_text("KR", "api_failed") in metric_blob

    assert app.ui_text("KR", "persona_card_reasons") in merged
    assert app.ui_text("KR", "persona_card_concerns") in merged

    export_label = app.ui_text("KR", "report_export_button")
    export_buttons = [b for b in at.get("download_button") if b.proto.label == export_label]
    assert export_buttons
    assert export_buttons[-1].proto.disabled is False

    csv_label = app.ui_text("KR", "csv_download")
    csv_widgets = [b for b in at.get("download_button") if b.proto.label == csv_label]
    assert csv_widgets
    assert csv_widgets[-1].proto.disabled is False

    assert db_path.is_file()
    assert str(db_path).startswith(str(tmp_path))
    assert db_path == app.DB_PATH
    if real_db_stat_before is None:
        assert not real_db_path.exists()
    else:
        real_db_stat_after = (real_db_path.stat().st_mtime_ns, real_db_path.stat().st_size)
        assert real_db_stat_after == real_db_stat_before

    captured = capfd.readouterr()
    assert HF_UNAUTH_WARNING not in captured.out
    assert HF_UNAUTH_WARNING not in captured.err


def test_apptest_local_path_traversal_rejected_without_api_call() -> None:
    at = _run_app_kr()
    at.radio[0].set_value("local")
    at.run(timeout=10)
    _text_input_by_label(at, "프로젝트명").set_value("test-project")
    _text_input_by_label(at, "제품 카테고리").set_value("니트웨어")
    _text_input_by_label(at, "로컬 파일 경로(data/ 하위 .csv 또는 .parquet)").set_value(
        "../outside.csv"
    )
    at.text_area[0].set_value("조용한 고급감의 미니멀 니트")
    _api_key_inputs(at)[0].set_value("fake-provider-key")
    _checkbox_by_label(at, "예상 비용과 시간이 발생할 수 있음을 확인했다.").check()
    at.run(timeout=10)

    assert _button_by_label(at, app.ui_text("KR", "run_button")).proto.disabled is False
    _button_by_label(at, app.ui_text("KR", "run_button")).click().run(timeout=10)

    assert "실행 준비 실패" in _visible_text(at) or "파일을 찾을 수 없습니다" in _visible_text(at)


# ---------------------------------------------------------------------------
# Product card: canonical text + concept_hash stability tests.
# ---------------------------------------------------------------------------


def test_product_card_field_order_matches_locked_spec() -> None:
    """PRODUCT_CARD_FIELD_ORDER 가 고정 계약대로인지 검증."""
    assert app.PRODUCT_CARD_FIELD_ORDER == (
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
    assert app.PRODUCT_CARD_EMPTY_PLACEHOLDER == "미입력"


def test_canonical_product_card_text_empty_fields_collapse_to_placeholder() -> None:
    canonical = app.build_canonical_product_card_text({})
    expected_lines = [
        "카테고리: 미입력",
        "가격: 미입력",
        "핏: 미입력",
        "소재: 미입력",
        "컬러: 미입력",
        "시즌: 미입력",
        "착용 상황: 미입력",
        "스타일 톤: 미입력",
        "타깃 가설: 미입력",
        "브랜드 메시지/제품 설명: 미입력",
    ]
    assert canonical == "\n".join(expected_lines)


def test_canonical_product_card_text_full_fields_render_in_fixed_order() -> None:
    fields = {
        "category": "니트웨어",
        "price": 15_900,
        "fit": "오버사이즈",
        "material": "메리노 울 100%",
        "color": "차콜",
        "season": "F/W",
        "occasion": "출근복",
        "style_tone": "미니멀",
        "target_hypothesis": "30대 직장인",
        "description": "조용한 고급감의 미니멀 니트",
    }
    canonical = app.build_canonical_product_card_text(fields)
    assert canonical == (
        "카테고리: 니트웨어\n"
        "가격: $159.00 USD\n"
        "핏: 오버사이즈\n"
        "소재: 메리노 울 100%\n"
        "컬러: 차콜\n"
        "시즌: F/W\n"
        "착용 상황: 출근복\n"
        "스타일 톤: 미니멀\n"
        "타깃 가설: 30대 직장인\n"
        "브랜드 메시지/제품 설명: 조용한 고급감의 미니멀 니트"
    )


def test_canonical_product_card_text_normalizes_whitespace_and_invisible_chars() -> None:
    base = {
        "category": "니트웨어",
        "price": 15_900,
        "fit": "오버사이즈",
        "material": "메리노 울 100%",
        "color": "차콜",
        "season": "F/W",
        "occasion": "출근복",
        "style_tone": "미니멀",
        "target_hypothesis": "30대 직장인",
        "description": "조용한 고급감의 미니멀 니트",
    }
    noisy = {
        **base,
        "description": "  조용한\u200b 고급감의 \t\t미니멀  니트  ",
        "color": "  차콜  ",
        "occasion": "출근복\r\n주말 캐주얼",
    }
    canonical_base = app.build_canonical_product_card_text(base)
    canonical_noisy = app.build_canonical_product_card_text(
        {
            **noisy,
            "description": "조용한 고급감의 미니멀 니트",
            "occasion": "출근복",
        }
    )
    assert canonical_base == canonical_noisy

    canonical_with_noise = app.build_canonical_product_card_text(noisy)
    assert "  " not in canonical_with_noise.replace("\n", "")
    assert "\u200b" not in canonical_with_noise
    assert "\r" not in canonical_with_noise


def test_canonical_product_card_text_invalid_or_empty_price_uses_placeholder() -> None:
    canonical_no_price = app.build_canonical_product_card_text({"price": 0})
    assert "가격: 미입력" in canonical_no_price
    canonical_negative = app.build_canonical_product_card_text({"price": -10})
    assert "가격: 미입력" in canonical_negative
    canonical_bad_type = app.build_canonical_product_card_text({"price": "not-a-number"})
    assert "가격: 미입력" in canonical_bad_type


def test_concept_hash_is_stable_for_identical_product_card_inputs() -> None:
    fields = {
        "category": "니트웨어",
        "price": 15_900,
        "fit": "오버사이즈",
        "material": "메리노 울 100%",
        "color": "차콜",
        "season": "F/W",
        "occasion": "출근복",
        "style_tone": "미니멀",
        "target_hypothesis": "30대 직장인",
        "description": "조용한 고급감의 미니멀 니트",
    }
    canonical_a = app.build_canonical_product_card_text(fields)
    canonical_b = app.build_canonical_product_card_text(dict(fields))
    assert canonical_a == canonical_b

    concept_a = {
        "category": fields["category"],
        "product_price_usd_cents": fields["price"],
        "concept_text": canonical_a,
    }
    concept_b = {
        "category": fields["category"],
        "product_price_usd_cents": fields["price"],
        "concept_text": canonical_b,
    }
    assert app.make_hashes(concept_a)["concept_hash"] == app.make_hashes(concept_b)["concept_hash"]


def test_concept_hash_changes_when_product_card_field_changes() -> None:
    base_fields = {
        "category": "니트웨어",
        "price": 15_900,
        "fit": "오버사이즈",
        "material": "메리노 울 100%",
        "color": "차콜",
        "season": "F/W",
        "occasion": "출근복",
        "style_tone": "미니멀",
        "target_hypothesis": "30대 직장인",
        "description": "조용한 고급감의 미니멀 니트",
    }
    base_concept = {
        "category": base_fields["category"],
        "product_price_usd_cents": base_fields["price"],
        "concept_text": app.build_canonical_product_card_text(base_fields),
    }
    base_hash = app.make_hashes(base_concept)["concept_hash"]

    for changed_key, changed_value in (
        ("fit", "슬림"),
        ("material", "코튼 100%"),
        ("color", "아이보리"),
        ("season", "S/S"),
        ("occasion", "주말 캐주얼"),
        ("style_tone", "스트릿"),
        ("target_hypothesis", "20대 학생"),
        ("description", "조용한 캐주얼 니트"),
    ):
        mutated_fields = {**base_fields, changed_key: changed_value}
        mutated_concept = {
            "category": mutated_fields["category"],
            "product_price_usd_cents": mutated_fields["price"],
            "concept_text": app.build_canonical_product_card_text(mutated_fields),
        }
        mutated_hash = app.make_hashes(mutated_concept)["concept_hash"]
        assert mutated_hash != base_hash, f"{changed_key} change should alter concept_hash"


def test_apptest_product_card_inputs_render_with_korean_labels() -> None:
    at = _run_app_kr()

    expected_labels = (
        "핏",
        "소재",
        "컬러",
        "시즌",
        "착용 상황",
        "스타일 톤",
    )
    rendered_labels = {widget.proto.label for widget in at.text_input}
    for label in expected_labels:
        assert label in rendered_labels, f"missing product card field: {label}"


def test_apptest_product_card_filled_canonical_text_drives_concept_hash() -> None:
    at = _run_app_kr()
    _text_input_by_label(at, "프로젝트명").set_value("test-project")
    _text_input_by_label(at, "제품 카테고리").set_value("니트웨어")
    _text_input_by_label(at, "핏").set_value("오버사이즈")
    _text_input_by_label(at, "소재").set_value("메리노 울 100%")
    _text_input_by_label(at, "컬러").set_value("차콜")
    _text_input_by_label(at, "시즌").set_value("F/W")
    _text_input_by_label(at, "착용 상황").set_value("출근복")
    _text_input_by_label(at, "스타일 톤").set_value("미니멀")
    at.text_area[0].set_value("조용한 고급감의 미니멀 니트")
    at.text_area[1].set_value("30대 직장인")
    _api_key_inputs(at)[0].set_value("fake-provider-key")
    at.checkbox[0].check()
    at.run(timeout=10)

    assert len(at.exception) == 0
    assert _button_by_label(at, app.ui_text("KR", "run_button")).proto.disabled is False
