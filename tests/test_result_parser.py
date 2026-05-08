import pytest
from pydantic import ValidationError

from src.result_parser import EvaluationResult, parse_evaluation_result

pytestmark = pytest.mark.no_network

VALID_DATA: dict = {
    "persona_id": "mock-001-seoulgi-f25",
    "sentiment": "positive",
    "interest_score": 8,
    "price_burden": "medium",
    "main_reasons": ["트렌디한 디자인", "합리적인 가격"],
    "main_concerns": ["소재 내구성 불확실"],
    "confidence_note": "페르소나 특성상 트렌드 민감도가 높아 긍정 반응으로 해석.",
}


class TestEvaluationResultValid:
    def test_valid_instantiation(self):
        result = EvaluationResult(**VALID_DATA)
        assert result.persona_id == VALID_DATA["persona_id"]
        assert result.sentiment == "positive"
        assert result.interest_score == 8
        assert result.price_burden == "medium"

    def test_model_validate(self):
        result = parse_evaluation_result(VALID_DATA)
        assert isinstance(result, EvaluationResult)

    def test_all_sentiments_valid(self):
        for sentiment in ("positive", "neutral", "negative"):
            data = {**VALID_DATA, "sentiment": sentiment}
            result = EvaluationResult(**data)
            assert result.sentiment == sentiment

    def test_all_price_burden_values_valid(self):
        for burden in ("low", "medium", "high", "very_high", "unknown"):
            data = {**VALID_DATA, "price_burden": burden}
            result = EvaluationResult(**data)
            assert result.price_burden == burden

    def test_interest_score_boundary_1(self):
        result = EvaluationResult(**{**VALID_DATA, "interest_score": 1})
        assert result.interest_score == 1

    def test_interest_score_boundary_10(self):
        result = EvaluationResult(**{**VALID_DATA, "interest_score": 10})
        assert result.interest_score == 10

    def test_empty_lists_valid(self):
        data = {**VALID_DATA, "main_reasons": [], "main_concerns": []}
        result = EvaluationResult(**data)
        assert result.main_reasons == []
        assert result.main_concerns == []

    def test_five_items_in_lists_valid(self):
        data = {
            **VALID_DATA,
            "main_reasons": ["r1", "r2", "r3", "r4", "r5"],
            "main_concerns": ["c1", "c2", "c3", "c4", "c5"],
        }
        result = EvaluationResult(**data)
        assert len(result.main_reasons) == 5

    def test_str_strip_whitespace(self):
        data = {**VALID_DATA, "persona_id": "  mock-001-seoulgi-f25  "}
        result = EvaluationResult(**data)
        assert result.persona_id == "mock-001-seoulgi-f25"

    def test_confidence_note_300_chars_valid(self):
        data = {**VALID_DATA, "confidence_note": "A" * 300}
        result = EvaluationResult(**data)
        assert len(result.confidence_note) == 300


class TestEvaluationResultInvalid:
    def test_invalid_sentiment_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "sentiment": "ok"})

    def test_interest_score_zero_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "interest_score": 0})

    def test_interest_score_eleven_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "interest_score": 11})

    def test_invalid_price_burden_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "price_burden": "very_low"})

    def test_main_reasons_six_items_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "main_reasons": ["r1", "r2", "r3", "r4", "r5", "r6"]})

    def test_main_concerns_six_items_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(
                **{**VALID_DATA, "main_concerns": ["c1", "c2", "c3", "c4", "c5", "c6"]}
            )

    def test_confidence_note_301_chars_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "confidence_note": "A" * 301})

    def test_extra_field_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "purchase_intent_score": 7})

    def test_v02_field_recommendation_score_raises(self):
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "recommendation_score": 9})

    def test_v02_fashion_rubric_field_fit_risk_score_raises(self):
        """Prompt v0.2 must not silently widen EvaluationResult."""
        with pytest.raises(ValidationError):
            EvaluationResult(**{**VALID_DATA, "fit_risk_score": 5})


class TestEvaluationResultV02Compatibility:
    """concept_eval_ko_v0_2 must produce EvaluationResult-compatible payloads.

    Source: public beta v3 fashion prompt rubric
    rubric for `main_concerns` and the fixed `confidence_note` direction.
    """

    def test_v02_fixed_confidence_note_within_300_chars(self):
        fixed_phrase = (
            "합성 패널 기반 가설이며 실제 소비자 조사, 실제 구매율 예측, "
            "실제 유행 예측을 대체하지 않는다."
        )
        assert len(fixed_phrase) <= 300
        result = EvaluationResult(**{**VALID_DATA, "confidence_note": fixed_phrase})
        assert result.confidence_note == fixed_phrase

    def test_v02_fashion_rubric_main_concerns_validates(self):
        """All seven rubric labels can fill main_concerns up to the 5-item cap."""
        rubric_labels = [
            "가격 부담: 평소 의류 지출 대비 부담",
            "스타일 부담: 톤이 강해 일상 코디에 어려움",
            "코디 난이도: 보유 옷장과 매칭 어려움",
            "구매 망설임: 차별 포인트 정보 부족",
            "착용 상황 불일치: 출퇴근 occasion 과 어긋남",
        ]
        result = EvaluationResult(**{**VALID_DATA, "main_concerns": rubric_labels})
        assert len(result.main_concerns) == 5
