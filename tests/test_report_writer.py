"""Tests for src/report_writer.py — Phase 4.

No LLM / HF / DB calls.  Uses tmp_path only — no writes to actual outputs/.
"""

import pytest

from src.aggregator import (
    AggregateReport,
    QualityCounts,
    aggregate,
)
from src.report_writer import (
    FORBIDDEN_PHRASES,
    assert_safe_phrasing,
    escape_csv_cell,
    render_csv,
    render_markdown,
    required_footer_text,
    write_report_files,
)
from src.result_parser import EvaluationResult
from tests.fixtures.mock_evaluation_results import (
    MOCK_PERSONA_ATTRIBUTES,
    MOCK_RESULTS,
)

pytestmark = pytest.mark.no_network

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_QUALITY = QualityCounts(
    success=40,
    parse_failed=2,
    api_failed=1,
    total_attempted=43,
    distribution_included=40,
)


@pytest.fixture()
def full_report() -> AggregateReport:
    return aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)


# ---------------------------------------------------------------------------
# required_footer_text
# ---------------------------------------------------------------------------


class TestRequiredFooterText:
    def test_exact_match_line1(self):
        footer = required_footer_text()
        assert "본 도구는 합성 페르소나와 LLM 기반의 사전 가설 분석 도구입니다." in footer

    def test_exact_match_line2(self):
        footer = required_footer_text()
        expected = "실제 소비자 조사, 매출 예측, 법률 자문, 최종 사업 판단을 대체하지 않습니다."
        assert expected in footer

    def test_data_source_line(self):
        footer = required_footer_text()
        expected = "Data source (only external dataset): NVIDIA Nemotron-Personas-USA, CC BY 4.0."
        assert expected in footer
        assert "https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA" in footer

    def test_attribution_and_obfuscated_contact_line(self):
        footer = required_footer_text()
        assert "US Fashion Persona Screener." in footer
        assert "Contact: woooya129 [at] gmail [dot] com" in footer
        assert "woooya129@gmail.com" not in footer

    def test_footer_does_not_raise_safe_phrasing(self):
        # Critical: the mandatory footer must not trigger assert_safe_phrasing
        footer = required_footer_text()
        # This should NOT raise
        assert_safe_phrasing(footer)


# ---------------------------------------------------------------------------
# assert_safe_phrasing
# ---------------------------------------------------------------------------


class TestAssertSafePhrasing:
    def test_clean_text_does_not_raise(self):
        assert_safe_phrasing("합성 패널 100명 기준 분석 결과입니다.")

    def test_forbidden_phrase_한국_소비자의_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("한국 소비자의 42%가 좋아합니다.")

    def test_forbidden_phrase_구매_가능성_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("구매 가능성 72%로 분석됩니다.")

    def test_forbidden_phrase_시장_반응_예측_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("시장 반응 예측 결과입니다.")

    def test_forbidden_phrase_AI_시장조사_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("AI 시장조사 플랫폼 소개")

    def test_forbidden_phrase_실제_고객_반응_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("실제 고객 반응 데이터")

    def test_forbidden_phrase_이_가격이면_구매_가능_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("이 가격이면 구매 가능합니다.")

    def test_forbidden_phrase_구매율_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("구매율 80%")

    def test_forbidden_phrase_이_제품을_산다_raises(self):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing("합성 패널이 이 제품을 산다고 응답.")

    @pytest.mark.parametrize(
        "phrase",
        [
            "US consumers",
            "U.S. consumers",
            "American consumers",
            "미국 소비자의",
            "purchase rate",
            "sales forecast",
            "market share",
        ],
    )
    def test_usa_public_release_generalization_phrases_raise(self, phrase: str):
        with pytest.raises(ValueError, match="금지 표현"):
            assert_safe_phrasing(f"Directional output for {phrase}")


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


class TestRenderMarkdown:
    def test_contains_synthetic_panel_phrase(self, full_report):
        md = render_markdown(full_report)
        assert "합성 패널" in md

    def test_contains_n_명_기준(self, full_report):
        md = render_markdown(full_report)
        n = full_report.sample_size
        assert f"합성 패널 {n}명 기준" in md

    def test_footer_present(self, full_report):
        md = render_markdown(full_report)
        assert "본 도구는 합성 페르소나와 LLM 기반의 사전 가설 분석 도구입니다." in md

    def test_data_source_line_present(self, full_report):
        md = render_markdown(full_report)
        expected = "Data source (only external dataset): NVIDIA Nemotron-Personas-USA, CC BY 4.0."
        assert expected in md

    def test_does_not_raise_safe_phrasing(self, full_report):
        # render_markdown internally calls assert_safe_phrasing
        md = render_markdown(full_report)
        # Must also pass external call
        assert_safe_phrasing(md)

    def test_forbidden_phrase_in_report_raises(self):
        # Manually inject a forbidden phrase — render_markdown must raise
        # We cannot easily inject via AggregateReport (frozen dataclass),
        # so we test assert_safe_phrasing directly with forbidden text.
        with pytest.raises(ValueError):
            assert_safe_phrasing("한국 소비자의 반응")

    def test_all_forbidden_phrases_trigger_error(self):
        for phrase in FORBIDDEN_PHRASES:
            with pytest.raises(ValueError):
                assert_safe_phrasing(f"테스트: {phrase}")

    def test_sample_warning_included_when_small(self):
        results = MOCK_RESULTS[:10]
        quality = QualityCounts(
            success=10, parse_failed=0, api_failed=0, total_attempted=10, distribution_included=10
        )
        report = aggregate(results, MOCK_PERSONA_ATTRIBUTES, quality)
        md = render_markdown(report)
        assert "데모/프롬프트 테스트용" in md

    def test_returns_string(self, full_report):
        md = render_markdown(full_report)
        assert isinstance(md, str)
        assert len(md) > 100


# ---------------------------------------------------------------------------
# render_csv
# ---------------------------------------------------------------------------


class TestRenderCsv:
    def test_bom_prefix(self, full_report):
        csv_text = render_csv(full_report)
        assert csv_text.startswith("﻿"), "CSV must start with UTF-8 BOM"

    def test_section_key_value_header(self, full_report):
        csv_text = render_csv(full_report)
        assert "section,key,value" in csv_text

    def test_formula_injection_equals(self, full_report):
        # escape_csv_cell handles injection; verify via escape_csv_cell unit test
        result = escape_csv_cell("=SUM(A1)")
        assert result == "'=SUM(A1)"

    def test_formula_injection_at(self, full_report):
        result = escape_csv_cell("@user")
        assert result == "'@user"

    def test_formula_injection_minus(self, full_report):
        result = escape_csv_cell("-1")
        assert result == "'-1"

    def test_formula_injection_plus(self, full_report):
        result = escape_csv_cell("+1")
        assert result == "'+1"

    def test_formula_injection_tab(self, full_report):
        result = escape_csv_cell("\tfoo")
        assert result == "'\tfoo"

    def test_korean_cell_passes_through(self, full_report):
        result = escape_csv_cell("합성 패널")
        assert result == "합성 패널"

    def test_footer_in_csv(self, full_report):
        csv_text = render_csv(full_report)
        assert "본 도구는 합성 페르소나와 LLM 기반의 사전 가설 분석 도구입니다." in csv_text

    def test_csv_contains_sentiment_data(self, full_report):
        csv_text = render_csv(full_report)
        assert "반응분포" in csv_text

    def test_forbidden_phrase_in_reasons_raises(self):
        # 금지 표현이 EvaluationResult.main_reasons 를 통해 CSV 셀에 들어오면
        # render_csv 가 assert_safe_phrasing 으로 차단해야 한다.
        from src.aggregator import aggregate
        from src.result_parser import EvaluationResult

        poisoned = EvaluationResult(
            persona_id="poison-1",
            sentiment="positive",
            interest_score=8,
            price_burden="medium",
            main_reasons=["가격 대비 만족", "한국 소비자의 평균 반응"],  # 금지 표현 포함
            main_concerns=[],
            confidence_note="injection check",
        )
        attrs = {
            "poison-1": {
                "age": 30,
                "sex": "F",
                "state": "NY",
                "occupation": "회사원",
            }
        }
        quality = QualityCounts(
            success=1,
            parse_failed=0,
            api_failed=0,
            total_attempted=1,
            distribution_included=1,
        )
        report = aggregate([poisoned], attrs, quality)
        with pytest.raises(ValueError, match="금지 표현"):
            render_csv(report)


# ---------------------------------------------------------------------------
# escape_csv_cell unit tests
# ---------------------------------------------------------------------------


class TestEscapeCsvCell:
    def test_equals_sign(self):
        assert escape_csv_cell("=SUM(A1)") == "'=SUM(A1)"

    def test_at_sign(self):
        assert escape_csv_cell("@user") == "'@user"

    def test_minus(self):
        assert escape_csv_cell("-1") == "'-1"

    def test_plus(self):
        assert escape_csv_cell("+1") == "'+1"

    def test_tab(self):
        assert escape_csv_cell("\tfoo") == "'\tfoo"

    def test_carriage_return(self):
        assert escape_csv_cell("\rbar") == "'\rbar"

    def test_normal_string_unchanged(self):
        assert escape_csv_cell("hello") == "hello"

    def test_korean_unchanged(self):
        assert escape_csv_cell("합성 패널") == "합성 패널"

    def test_empty_string(self):
        assert escape_csv_cell("") == ""

    def test_non_string_converted(self):
        assert escape_csv_cell(42) == "42"
        assert escape_csv_cell(3.14) == "3.14"


# ---------------------------------------------------------------------------
# write_report_files
# ---------------------------------------------------------------------------


class TestWriteReportFiles:
    def test_creates_md_and_csv(self, tmp_path, full_report):
        md_path, csv_path = write_report_files(full_report, tmp_path, "테스트프로젝트", "job-001")
        assert md_path.exists()
        assert csv_path.exists()
        assert md_path.suffix == ".md"
        assert csv_path.suffix == ".csv"

    def test_project_slug_normalization_removes_specials(self, tmp_path, full_report):
        md_path, _ = write_report_files(full_report, tmp_path, "Test Project!@#", "job-002")
        assert "TestProject" in str(md_path) or "Test-Project" in str(md_path)

    def test_project_slug_preserves_korean(self, tmp_path, full_report):
        md_path, _ = write_report_files(full_report, tmp_path, "패션프로젝트", "job-003")
        assert "패션프로젝트" in str(md_path)

    def test_same_job_id_overwrites(self, tmp_path, full_report):
        write_report_files(full_report, tmp_path, "proj", "job-overwrite")
        write_report_files(full_report, tmp_path, "proj", "job-overwrite")
        # Second call should not raise

    def test_path_traversal_raises(self, tmp_path, full_report):
        with pytest.raises(ValueError, match="경로 탐색"):
            write_report_files(full_report, tmp_path, "proj", "../evil")

    def test_path_traversal_slash_raises(self, tmp_path, full_report):
        with pytest.raises(ValueError, match="경로 탐색"):
            write_report_files(full_report, tmp_path, "proj", "sub/evil")

    def test_empty_job_id_raises(self, tmp_path, full_report):
        with pytest.raises(ValueError):
            write_report_files(full_report, tmp_path, "proj", "")

    def test_md_content_has_footer(self, tmp_path, full_report):
        md_path, _ = write_report_files(full_report, tmp_path, "proj", "job-footer")
        content = md_path.read_text(encoding="utf-8")
        assert "본 도구는 합성 페르소나와 LLM 기반의 사전 가설 분석 도구입니다." in content

    def test_csv_content_has_bom(self, tmp_path, full_report):
        _, csv_path = write_report_files(full_report, tmp_path, "proj", "job-bom")
        raw = csv_path.read_bytes()
        # utf-8-sig writes BOM as EF BB BF
        assert raw[:3] == b"\xef\xbb\xbf"

    def test_no_write_to_real_outputs_dir(self, tmp_path, full_report):
        """Ensure test only writes to tmp_path, never to the real outputs/ dir."""
        import pathlib

        real_outputs = pathlib.Path("outputs")
        write_report_files(full_report, tmp_path, "proj", "job-isolation")
        # tmp_path must not be inside or equal to real outputs/
        try:
            tmp_path.relative_to(real_outputs.resolve())
        except ValueError:
            pass  # expected — tmp_path is NOT under real outputs/
        else:
            raise AssertionError("tmp_path must not be inside real outputs/")


# ---------------------------------------------------------------------------
# fashion-public-beta v3 — fashion sections in markdown / csv
# ---------------------------------------------------------------------------


class TestFashionRiskSectionsMarkdown:
    """render_markdown 에 새 섹션이 포함되고 forbidden phrase 가 없는지."""

    def test_fashion_risk_section_present(self, full_report):
        md = render_markdown(full_report)
        assert "## 패션 위험 신호" in md

    def test_price_burden_interpretation_section_present(self, full_report):
        md = render_markdown(full_report)
        assert "## 가격 부담 해석" in md

    def test_style_coordination_section_present(self, full_report):
        md = render_markdown(full_report)
        assert "## 스타일/코디 장벽" in md

    def test_purchase_hesitation_section_present(self, full_report):
        md = render_markdown(full_report)
        assert "## 구매 망설임" in md

    def test_modification_suggestion_section_present(self, full_report):
        md = render_markdown(full_report)
        assert "## 수정 제안 후보" in md
        assert "deterministic rule" in md or "LLM 호출 없음" in md

    def test_representative_responses_section_present(self, full_report):
        md = render_markdown(full_report)
        assert "## 대표 페르소나 반응" in md

    def test_fashion_sections_pass_safe_phrasing(self, full_report):
        # render_markdown 자체가 assert_safe_phrasing 호출 — raise 없으면 통과
        md = render_markdown(full_report)
        assert_safe_phrasing(md)

    def test_modification_suggestions_render_when_present(self, full_report):
        # MOCK_RESULTS 에는 가격 부담 / 스타일 / 핏 등 다양한 신호가 포함되어 있음
        md = render_markdown(full_report)
        # 최소한 가격 부담 카테고리는 mock 에서 트리거되어 표시되어야 한다
        assert "가격 부담" in md

    def test_no_modification_suggestions_when_no_signals(self):
        # main_concerns 가 모두 미분류 키워드일 때 — suggestions 비어 있음
        results = [
            EvaluationResult(
                persona_id="x1",
                sentiment="neutral",
                interest_score=5,
                price_burden="medium",
                main_reasons=[],
                main_concerns=["배송 시간 우려"],
                confidence_note="신호 없음.",
            ),
        ]
        attrs = {"x1": {"age": 30, "sex": "M", "state": "NY", "occupation": "사무직"}}
        quality = QualityCounts(
            success=1, parse_failed=0, api_failed=0, total_attempted=1, distribution_included=1
        )
        report = aggregate(results, attrs, quality)
        md = render_markdown(report)
        # suggestions 섹션은 존재하되 "트리거할 위험 신호가 잡히지 않았습니다" 안내
        assert "## 수정 제안 후보" in md
        assert "위험 신호가 잡히지" in md


class TestFashionRiskSectionsCsv:
    """render_csv 에 새 섹션 행이 들어가는지."""

    def test_csv_includes_fashion_risk_rows(self, full_report):
        csv_text = render_csv(full_report)
        assert "패션위험신호" in csv_text

    def test_csv_includes_modification_rows_when_signals(self, full_report):
        csv_text = render_csv(full_report)
        # mock 에 가격/스타일/핏 신호가 있어 최소 1개 수정 제안 행이 존재
        assert "수정제안" in csv_text

    def test_csv_includes_representative_persona_rows(self, full_report):
        csv_text = render_csv(full_report)
        assert "대표페르소나반응" in csv_text

    def test_csv_passes_safe_phrasing(self, full_report):
        csv_text = render_csv(full_report)
        assert_safe_phrasing(csv_text)


class TestForbiddenPhrasesNotInSuggestions:
    """deterministic 수정 제안 텍스트가 절대 forbidden phrase 를 포함하지 않음."""

    def test_all_default_suggestions_clean(self):
        from src.aggregator import _FASHION_RISK_SUGGESTIONS

        for category, text in _FASHION_RISK_SUGGESTIONS.items():
            assert_safe_phrasing(text)
            for phrase in FORBIDDEN_PHRASES:
                assert phrase not in text, f"{category}: {phrase!r}"
