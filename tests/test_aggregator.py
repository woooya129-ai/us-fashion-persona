"""Tests for src/aggregator.py — Phase 4.

No LLM / HF / DB calls.  All inputs are mock EvaluationResult objects.
"""

import pytest

from src.aggregator import (
    FASHION_RISK_CATEGORY_KEYS,
    FASHION_RISK_CATEGORY_LABELS,
    FashionRiskBreakdown,
    ModificationSuggestion,
    QualityCounts,
    SegmentRow,
    SentimentDistribution,
    TopReasons,
    _age_bucket,
    _categorize_fashion_concern,
    _sample_warning,
    aggregate,
    categorize_fashion_risks,
    extract_top_reasons,
    generate_modification_suggestions,
    representative_personas,
)
from src.result_parser import EvaluationResult
from tests.fixtures.mock_evaluation_results import (
    MOCK_PERSONA_ATTRIBUTES,
    MOCK_RESULTS,
)

pytestmark = pytest.mark.no_network

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_QUALITY = QualityCounts(
    success=40,
    parse_failed=2,
    api_failed=1,
    total_attempted=43,
    distribution_included=40,
)


def _make_quality(n: int) -> QualityCounts:
    return QualityCounts(
        success=n,
        parse_failed=0,
        api_failed=0,
        total_attempted=n,
        distribution_included=n,
    )


def _make_result(
    persona_id: str,
    sentiment: str = "positive",
    interest_score: int = 7,
    price_burden: str = "medium",
    main_reasons: list | None = None,
    main_concerns: list | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        persona_id=persona_id,
        sentiment=sentiment,
        interest_score=interest_score,
        price_burden=price_burden,
        main_reasons=main_reasons or [],
        main_concerns=main_concerns or [],
        confidence_note="테스트용",
    )


# ---------------------------------------------------------------------------
# aggregate — sentiment distribution
# ---------------------------------------------------------------------------


class TestAggregateSentiment:
    def test_sentiment_counts_sum_to_sample_size(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        s = report.sentiment
        assert s.positive + s.neutral + s.negative == report.sample_size

    def test_sentiment_pct_sum_approx_100(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        s = report.sentiment
        total = s.positive_pct + s.neutral_pct + s.negative_pct
        assert abs(total - 100.0) <= 0.3, f"% 합이 100에서 벗어남: {total}"

    def test_sentiment_pct_matches_counts(self):
        results = [
            _make_result("a", sentiment="positive"),
            _make_result("b", sentiment="positive"),
            _make_result("c", sentiment="negative"),
        ]
        report = aggregate(results, {}, _make_quality(3))
        assert report.sentiment.positive_pct == pytest.approx(66.7, abs=0.1)
        assert report.sentiment.negative_pct == pytest.approx(33.3, abs=0.1)

    def test_sentiment_distribution_type(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        assert isinstance(report.sentiment, SentimentDistribution)


# ---------------------------------------------------------------------------
# aggregate — avg_interest_score
# ---------------------------------------------------------------------------


class TestAggregateAvgScore:
    def test_avg_interest_score_is_round_1(self):
        results = [
            _make_result("a", interest_score=7),
            _make_result("b", interest_score=8),
            _make_result("c", interest_score=9),
        ]
        report = aggregate(results, {}, _make_quality(3))
        assert report.avg_interest_score == pytest.approx(8.0, abs=0.05)

    def test_avg_interest_score_rounding(self):
        # mean = (7+8) / 2 = 7.5  → round(7.5, 1) = 7.5
        results = [_make_result("a", interest_score=7), _make_result("b", interest_score=8)]
        report = aggregate(results, {}, _make_quality(2))
        assert report.avg_interest_score == 7.5

    def test_avg_interest_score_from_mock(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        # Just verify it's a float within valid range
        assert 1.0 <= report.avg_interest_score <= 10.0


# ---------------------------------------------------------------------------
# aggregate — price_burden distribution
# ---------------------------------------------------------------------------


class TestAggregatePriceBurden:
    def test_high_or_above_is_high_plus_very_high(self):
        results = [
            _make_result("a", price_burden="high"),
            _make_result("b", price_burden="very_high"),
            _make_result("c", price_burden="low"),
        ]
        report = aggregate(results, {}, _make_quality(3))
        assert report.price_burden.high_or_above_count == 2

    def test_price_burden_counts_cover_all_labels(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        labels = set(report.price_burden.counts.keys())
        assert labels == {"low", "medium", "high", "very_high", "unknown"}

    def test_high_or_above_pct_correct(self):
        results = [_make_result(f"p{i}", price_burden="high") for i in range(2)] + [
            _make_result("px", price_burden="low")
        ]
        report = aggregate(results, {}, _make_quality(3))
        assert report.price_burden.high_or_above_pct == pytest.approx(66.7, abs=0.1)


# ---------------------------------------------------------------------------
# aggregate — quality counts
# ---------------------------------------------------------------------------


class TestAggregateQuality:
    def test_quality_counts_passed_through(self):
        quality = QualityCounts(
            success=10,
            parse_failed=3,
            api_failed=1,
            total_attempted=14,
            distribution_included=10,
        )
        report = aggregate(MOCK_RESULTS[:10], MOCK_PERSONA_ATTRIBUTES, quality)
        assert report.quality.success == 10
        assert report.quality.parse_failed == 3
        assert report.quality.api_failed == 1
        assert report.quality.distribution_included == 10

    def test_distribution_included_is_success_only(self):
        quality = QualityCounts(
            success=8,
            parse_failed=2,
            api_failed=0,
            total_attempted=10,
            distribution_included=8,
        )
        report = aggregate(MOCK_RESULTS[:8], MOCK_PERSONA_ATTRIBUTES, quality)
        assert report.quality.distribution_included == 8


# ---------------------------------------------------------------------------
# aggregate — segments
# ---------------------------------------------------------------------------


class TestAggregateSegments:
    def test_age_bucket_29_is_20s(self):
        assert _age_bucket(29) == "20대"

    def test_age_bucket_30_is_30s(self):
        assert _age_bucket(30) == "30대"

    def test_segments_age_no_empty_rows(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        for row in report.segments_age:
            assert row.n > 0

    def test_segments_sex_has_m_and_f(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        labels = {row.segment_label for row in report.segments_sex}
        assert "M" in labels
        assert "F" in labels

    def test_segments_state_rows_are_segment_rows(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        for row in report.segments_state:
            assert isinstance(row, SegmentRow)
            assert row.n > 0

    def test_segments_occupation_first_word_normalization(self):
        results = [
            _make_result("a", sentiment="positive"),
            _make_result("b", sentiment="neutral"),
        ]
        attrs = {
            "a": {"age": 30, "sex": "M", "state": "NY", "occupation": "사무직 계장"},
            "b": {"age": 25, "sex": "F", "state": "CA", "occupation": "사무직 사원"},
        }
        report = aggregate(results, attrs, _make_quality(2))
        labels = {row.segment_label for row in report.segments_occupation}
        # Both should normalize to "사무직"
        assert "사무직" in labels
        assert len(report.segments_occupation) == 1  # merged into one group

    def test_segments_price_burden_labels_match_data(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        labels = {row.segment_label for row in report.segments_price_burden}
        # Every label in segments must exist in price_burden.counts
        for label in labels:
            assert label in report.price_burden.counts


# ---------------------------------------------------------------------------
# aggregate — sample_warning
# ---------------------------------------------------------------------------


class TestAggregateSampleWarning:
    def test_warning_n_10(self):
        results = MOCK_RESULTS[:10]
        report = aggregate(results, MOCK_PERSONA_ATTRIBUTES, _make_quality(10))
        assert report.sample_warning == "데모/프롬프트 테스트용. 분포 해석 금지"

    def test_warning_n_29_boundary(self):
        results = MOCK_RESULTS[:29]
        report = aggregate(results, MOCK_PERSONA_ATTRIBUTES, _make_quality(29))
        assert report.sample_warning == "데모/프롬프트 테스트용. 분포 해석 금지"

    def test_warning_n_30(self):
        results = MOCK_RESULTS[:30]
        report = aggregate(results, MOCK_PERSONA_ATTRIBUTES, _make_quality(30))
        assert report.sample_warning == "방향성 참고용. 세그먼트 비교 부적합"

    def test_warning_n_49_boundary(self):
        # Test _sample_warning directly for boundary value
        assert _sample_warning(49) == "방향성 참고용. 세그먼트 비교 부적합"

    def test_warning_n_50(self):
        assert _sample_warning(50) == "간단한 반응 분포 참고 가능"

    def test_warning_n_99_boundary(self):
        assert _sample_warning(99) == "간단한 반응 분포 참고 가능"

    def test_warning_n_100(self):
        assert _sample_warning(100) == "기본 리포트 권장"


# ---------------------------------------------------------------------------
# extract_top_reasons
# ---------------------------------------------------------------------------


class TestExtractTopReasons:
    def test_frequency_count_top_n(self):
        results = [
            _make_result("a", main_reasons=["가성비", "디자인"]),
            _make_result("b", main_reasons=["가성비", "소재"]),
            _make_result("c", main_reasons=["디자인"]),
        ]
        top = extract_top_reasons(results, top_n=2)
        # "가성비" should be rank 1 (count=2)
        assert top.positive[0] == ("가성비", 2)

    def test_whitespace_normalization_same_key(self):
        results = [
            _make_result("a", main_reasons=["가성비  우수"]),
            _make_result("b", main_reasons=["가성비 우수"]),
        ]
        top = extract_top_reasons(results, top_n=5)
        # Both should normalize to "가성비 우수" → count=2
        assert top.positive[0] == ("가성비 우수", 2)

    def test_empty_input_returns_empty_top_reasons(self):
        top = extract_top_reasons([])
        assert isinstance(top, TopReasons)
        assert top.positive == []
        assert top.concerns == []

    def test_concerns_counted_separately(self):
        results = [
            _make_result("a", main_concerns=["가격 부담", "사이즈"]),
            _make_result("b", main_concerns=["가격 부담"]),
        ]
        top = extract_top_reasons(results)
        assert top.concerns[0] == ("가격 부담", 2)

    def test_top_n_limits_result(self):
        # EvaluationResult.main_reasons capped at 5 by schema — split across two results
        # so the flattened pool exceeds top_n.
        results = [
            _make_result("a", main_reasons=["A", "B", "C", "D", "E"]),
            _make_result("b", main_reasons=["F", "G", "H", "I", "J"]),
        ]
        top = extract_top_reasons(results, top_n=3)
        assert len(top.positive) <= 3


# ---------------------------------------------------------------------------
# representative_personas
# ---------------------------------------------------------------------------


class TestRepresentativePersonas:
    def test_returns_one_per_sentiment(self):
        reps = representative_personas(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, n=3)
        sentiments = {r["sentiment"] for r in reps}
        assert "positive" in sentiments
        assert "negative" in sentiments

    def test_no_raw_persona_text(self):
        reps = representative_personas(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, n=3)
        for rep in reps:
            # Only abstracted label fields expected
            assert "persona_id" in rep
            assert "segment_label" in rep
            assert "sentiment" in rep
            assert "interest_score" in rep
            assert "main_reasons" in rep

    def test_n_exceeds_available_sentiments(self):
        # Only positive results
        results = [r for r in MOCK_RESULTS if r.sentiment == "positive"]
        reps = representative_personas(results, MOCK_PERSONA_ATTRIBUTES, n=3)
        assert len(reps) <= 3
        for rep in reps:
            assert rep["sentiment"] == "positive"

    def test_segment_label_is_abstracted(self):
        reps = representative_personas(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, n=3)
        for rep in reps:
            # Must match "N세 / 지역 / 직업" pattern (abstracted, not raw)
            label = rep["segment_label"]
            parts = label.split(" / ")
            assert len(parts) == 3

    def test_single_result_returns_one(self):
        single = [MOCK_RESULTS[0]]
        reps = representative_personas(single, MOCK_PERSONA_ATTRIBUTES, n=3)
        assert len(reps) == 1


# ---------------------------------------------------------------------------
# fashion-public-beta v3 — fashion risk categorization
# ---------------------------------------------------------------------------


class TestCategorizeFashionConcernKeywords:
    """우선순위 기반 키워드 매칭 단위 테스트."""

    def test_price_keywords_to_price_burden(self):
        assert _categorize_fashion_concern("가격이 부담") == "price_burden"
        assert _categorize_fashion_concern("가격 너무 높음") == "price_burden"
        assert _categorize_fashion_concern("사치품 수준 가격") == "price_burden"
        assert _categorize_fashion_concern("예산 초과") == "price_burden"

    def test_size_keywords_to_fit_risk(self):
        assert _categorize_fashion_concern("사이즈 다양성 부족") == "fit_risk"
        assert _categorize_fashion_concern("체형에 맞지 않음") == "fit_risk"

    def test_material_keywords_to_material_care(self):
        assert _categorize_fashion_concern("세탁 주의 필요") == "material_care_burden"
        assert _categorize_fashion_concern("내구성 불확실") == "material_care_burden"
        assert _categorize_fashion_concern("소재 불량 우려") == "material_care_burden"

    def test_coordination_keywords(self):
        assert _categorize_fashion_concern("코디가 어렵다") == "coordination_difficulty"
        assert _categorize_fashion_concern("매치하기 어려움") == "coordination_difficulty"

    def test_occasion_keywords(self):
        assert _categorize_fashion_concern("필요 없음") == "occasion_mismatch"
        assert _categorize_fashion_concern("필요성 불확실") == "occasion_mismatch"
        assert _categorize_fashion_concern("착용 상황 불일치") == "occasion_mismatch"

    def test_purchase_hesitation_keywords(self):
        assert _categorize_fashion_concern("브랜드 신뢰 부족") == "purchase_hesitation"
        assert _categorize_fashion_concern("정보 부족") == "purchase_hesitation"
        assert _categorize_fashion_concern("대체품 존재") == "purchase_hesitation"
        assert _categorize_fashion_concern("브랜드 매력 없음") == "purchase_hesitation"

    def test_style_keywords(self):
        assert _categorize_fashion_concern("디자인 평범") == "style_burden"
        assert _categorize_fashion_concern("취향 아님") == "style_burden"
        assert _categorize_fashion_concern("유행 지남") == "style_burden"
        assert _categorize_fashion_concern("디자인 불호") == "style_burden"

    def test_unmatched_returns_none(self):
        assert _categorize_fashion_concern("배송 시간 우려") is None
        assert _categorize_fashion_concern("포장 개선 필요") is None
        assert _categorize_fashion_concern("") is None

    def test_priority_price_over_style(self):
        # "가격" 과 "디자인" 이 함께 있을 때 price_burden 이 먼저 매칭
        assert _categorize_fashion_concern("가격 대비 디자인 아쉬움") == "price_burden"


class TestCategorizeFashionRisks:
    """집계 함수: results.main_concerns → FashionRiskBreakdown."""

    def test_returns_breakdown_type(self):
        breakdown = categorize_fashion_risks(MOCK_RESULTS)
        assert isinstance(breakdown, FashionRiskBreakdown)

    def test_counts_keys_match_known_categories(self):
        breakdown = categorize_fashion_risks(MOCK_RESULTS)
        assert set(breakdown.counts.keys()) == set(FASHION_RISK_CATEGORY_KEYS)

    def test_total_concerns_includes_all_non_empty(self):
        # _make_result helpers — 강제 텍스트
        results = [
            _make_result("a", main_concerns=["가격 부담", "사이즈 부족"]),
            _make_result("b", main_concerns=["디자인 평범"]),
        ]
        breakdown = categorize_fashion_risks(results)
        assert breakdown.total_concerns == 3

    def test_uncategorized_counts_unmatched(self):
        results = [
            _make_result("a", main_concerns=["배송 시간 우려", "포장 개선 필요"]),
        ]
        breakdown = categorize_fashion_risks(results)
        assert breakdown.uncategorized_count == 2
        # counts 합은 0 (모두 미분류)
        assert sum(breakdown.counts.values()) == 0

    def test_empty_results_returns_zeros(self):
        breakdown = categorize_fashion_risks([])
        assert breakdown.total_concerns == 0
        assert breakdown.uncategorized_count == 0
        for key in FASHION_RISK_CATEGORY_KEYS:
            assert breakdown.counts[key] == 0
            assert breakdown.examples[key] == []

    def test_examples_capped_per_category(self):
        # 같은 키워드가 여러 번 등장 → examples 는 capped
        results = [
            _make_result(
                f"p{i}",
                main_concerns=[f"가격 사례 {i}"],
            )
            for i in range(10)
        ]
        breakdown = categorize_fashion_risks(results, examples_per_category=3)
        assert len(breakdown.examples["price_burden"]) <= 3

    def test_whitespace_normalized_examples(self):
        # 공백 변형은 같은 텍스트로 정규화되어 빈도 합산
        results = [
            _make_result("a", main_concerns=["가격  부담"]),
            _make_result("b", main_concerns=["가격 부담"]),
        ]
        breakdown = categorize_fashion_risks(results)
        assert breakdown.counts["price_burden"] == 2
        assert breakdown.examples["price_burden"] == ["가격 부담"]

    def test_each_concern_counted_once_only(self):
        # 한 concern 은 한 카테고리에만 들어간다.
        results = [
            _make_result("a", main_concerns=["가격 대비 디자인 아쉬움"]),
        ]
        breakdown = categorize_fashion_risks(results)
        # 가격 매칭이 우선 → price_burden 만 +1, style_burden 은 0
        assert breakdown.counts["price_burden"] == 1
        assert breakdown.counts["style_burden"] == 0
        assert breakdown.total_concerns == 1


class TestGenerateModificationSuggestions:
    """deterministic 수정 제안 생성."""

    def test_empty_breakdown_returns_empty_list(self):
        empty = FashionRiskBreakdown(
            counts={k: 0 for k in FASHION_RISK_CATEGORY_KEYS},
            examples={k: [] for k in FASHION_RISK_CATEGORY_KEYS},
            total_concerns=0,
            uncategorized_count=0,
        )
        assert generate_modification_suggestions(empty) == []

    def test_only_categories_with_signals_appear(self):
        breakdown = FashionRiskBreakdown(
            counts={
                "price_burden": 3,
                "fit_risk": 0,
                "material_care_burden": 1,
                "coordination_difficulty": 0,
                "occasion_mismatch": 0,
                "purchase_hesitation": 0,
                "style_burden": 0,
            },
            examples={k: [] for k in FASHION_RISK_CATEGORY_KEYS},
            total_concerns=4,
            uncategorized_count=0,
        )
        suggestions = generate_modification_suggestions(breakdown)
        cats = [s.category for s in suggestions]
        assert cats == ["price_burden", "material_care_burden"]

    def test_sorted_by_count_desc_then_definition_order(self):
        breakdown = FashionRiskBreakdown(
            counts={
                "price_burden": 1,
                "fit_risk": 5,
                "material_care_burden": 2,
                "coordination_difficulty": 0,
                "occasion_mismatch": 0,
                "purchase_hesitation": 5,
                "style_burden": 1,
            },
            examples={k: [] for k in FASHION_RISK_CATEGORY_KEYS},
            total_concerns=14,
            uncategorized_count=0,
        )
        suggestions = generate_modification_suggestions(breakdown)
        # fit_risk(5) 가 정의 순서상 더 앞 → fit_risk 가 먼저, 그 다음 purchase_hesitation(5)
        assert suggestions[0].category == "fit_risk"
        assert suggestions[1].category == "purchase_hesitation"
        # 이후 material_care_burden(2)
        assert suggestions[2].category == "material_care_burden"
        # 동률 1 인 price_burden 과 style_burden — price_burden 이 정의 순서상 앞
        assert suggestions[3].category == "price_burden"
        assert suggestions[4].category == "style_burden"

    def test_each_category_has_known_suggestion_text(self):
        # 모든 카테고리가 트리거되도록 가짜 breakdown
        breakdown = FashionRiskBreakdown(
            counts={k: 1 for k in FASHION_RISK_CATEGORY_KEYS},
            examples={k: [] for k in FASHION_RISK_CATEGORY_KEYS},
            total_concerns=len(FASHION_RISK_CATEGORY_KEYS),
            uncategorized_count=0,
        )
        suggestions = generate_modification_suggestions(breakdown)
        assert len(suggestions) == len(FASHION_RISK_CATEGORY_KEYS)
        for s in suggestions:
            assert isinstance(s, ModificationSuggestion)
            assert s.category in FASHION_RISK_CATEGORY_KEYS
            assert s.category_label == FASHION_RISK_CATEGORY_LABELS[s.category]
            assert s.suggestion.strip() != ""

    def test_no_forbidden_phrases_in_suggestions(self):
        # 모든 카테고리 제안 텍스트가 금지 표현을 포함하지 않아야 함
        from src.report_writer import FORBIDDEN_PHRASES, assert_safe_phrasing

        breakdown = FashionRiskBreakdown(
            counts={k: 1 for k in FASHION_RISK_CATEGORY_KEYS},
            examples={k: [] for k in FASHION_RISK_CATEGORY_KEYS},
            total_concerns=len(FASHION_RISK_CATEGORY_KEYS),
            uncategorized_count=0,
        )
        suggestions = generate_modification_suggestions(breakdown)
        for s in suggestions:
            assert_safe_phrasing(s.suggestion)
            assert_safe_phrasing(s.category_label)
            for phrase in FORBIDDEN_PHRASES:
                assert phrase not in s.suggestion
                assert phrase not in s.category_label


class TestAggregateFashionFields:
    """aggregate() 가 새 필드를 올바르게 채우는지."""

    def test_aggregate_populates_fashion_risks(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        assert isinstance(report.fashion_risks, FashionRiskBreakdown)
        # mock 데이터에는 가격 부담 신호가 다수 존재
        assert report.fashion_risks.counts["price_burden"] >= 5

    def test_aggregate_populates_modification_suggestions(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        assert isinstance(report.modification_suggestions, list)
        # mock 에 다양한 concern 이 있어 최소 1개 이상의 카테고리는 트리거됨
        assert len(report.modification_suggestions) >= 1
        for s in report.modification_suggestions:
            assert isinstance(s, ModificationSuggestion)

    def test_aggregate_populates_representative_responses(self):
        report = aggregate(MOCK_RESULTS, MOCK_PERSONA_ATTRIBUTES, _DEFAULT_QUALITY)
        assert isinstance(report.representative_responses, list)
        assert len(report.representative_responses) >= 1
        for rep in report.representative_responses:
            assert "segment_label" in rep
            assert "sentiment" in rep
            assert "interest_score" in rep

    def test_empty_results_still_produces_default_breakdown(self):
        # n=0 인 경우에도 fashion_risks 는 0-카운트로 채워지고 suggestions 는 빈 리스트
        empty_quality = QualityCounts(
            success=0, parse_failed=0, api_failed=0, total_attempted=0, distribution_included=0
        )
        report = aggregate([], {}, empty_quality)
        assert report.fashion_risks.total_concerns == 0
        assert report.modification_suggestions == []
        assert report.representative_responses == []
