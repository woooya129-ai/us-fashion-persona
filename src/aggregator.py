# SPDX-License-Identifier: AGPL-3.0-only
"""Phase 4 결과 집계 — PM v3 §17.

No LLM / HF / DB calls.  Standard library only (collections.Counter).

추가 집계:
- 패션 위험 신호 카테고리 분류 (`FashionRiskBreakdown`)
- deterministic 수정 제안 후보 생성 (`ModificationSuggestion`)
- 새 EvaluationResult 필드는 추가하지 않는다 (기존 `main_concerns` / `main_reasons`만 사용).
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from src.result_parser import EvaluationResult

# ---------------------------------------------------------------------------
# Fashion risk signal categories
#
# main_concerns 텍스트를 deterministic 키워드 규칙으로 7개 카테고리로 분류한다.
# 분류는 우선순위 순서대로 첫 매칭에서 멈춘다 (한 concern 은 한 카테고리에만 들어간다).
# 매칭 안 되는 concern 은 "uncategorized" 로 카운트되지만, 수정 제안은 생성하지 않는다.
#
# 새 EvaluationResult 필드는 만들지 않는다 (스키마 확장 없음).
# 모든 키워드는 대소문자 무시 정규화된 한국어 substring 매칭이다.
# ---------------------------------------------------------------------------

FASHION_RISK_CATEGORY_KEYS: tuple[str, ...] = (
    "price_burden",
    "fit_risk",
    "material_care_burden",
    "coordination_difficulty",
    "occasion_mismatch",
    "purchase_hesitation",
    "style_burden",
)

FASHION_RISK_CATEGORY_LABELS: dict[str, str] = {
    "price_burden": "가격 부담",
    "fit_risk": "핏 리스크",
    "material_care_burden": "소재/관리 부담",
    "coordination_difficulty": "코디 난이도",
    "occasion_mismatch": "착용 상황 불일치",
    "purchase_hesitation": "구매 망설임",
    "style_burden": "스타일 부담",
}

# 우선순위 매칭 (위에서 아래로). 한 concern 은 첫 매칭 카테고리로만 들어간다.
# 가격 단어가 가장 강한 신호이므로 최상위. 이후 핏/소재처럼 구체적인 키워드,
# 그 다음 코디/착용 상황, 마지막에 일반적인 스타일 단어.
_FASHION_RISK_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "price_burden",
        ("가격", "비싸", "비쌈", "사치", "고가", "예산"),
    ),
    (
        "fit_risk",
        ("사이즈", "체형", "맞지", "핏 ", "핏감", "착용감"),
    ),
    (
        "material_care_burden",
        ("소재", "세탁", "내구", "관리"),
    ),
    (
        "coordination_difficulty",
        ("코디", "매치", "조합"),
    ),
    (
        "occasion_mismatch",
        ("착용 상황", "사용 상황", "필요 없", "필요성", "tpo"),
    ),
    (
        "purchase_hesitation",
        (
            "차별",
            "신뢰",
            "정보 부족",
            "정보가 부족",
            "망설",
            "고민",
            "대체품",
            "경쟁 제품",
            "경쟁 브랜드",
            "매력 부족",
            "매력 없",
            "구매 동기",
        ),
    ),
    (
        "style_burden",
        (
            "취향",
            "디자인",
            "유행",
            "트렌드",
            "특별함",
            "특색",
            "개성",
            "평범",
            "튀",
            "과감",
            "톤",
            "불호",
            "스타일 부담",
        ),
    ),
)

# 카테고리별 deterministic 수정 제안 문구 (LLM 호출 없음).
# 절대 forbidden phrase 를 포함하지 않는다 (PM v3 §2.3).
_FASHION_RISK_SUGGESTIONS: dict[str, str] = {
    "price_burden": (
        "소재/디테일/구성 대비 가격 설명을 강화하거나, "
        "보다 낮은 엔트리 가격 옵션을 함께 제시하는 방향이 후보입니다."
    ),
    "fit_risk": ("사이즈 가이드, 착용 컷, 체형별 안내를 보강하는 방향이 후보입니다."),
    "material_care_burden": (
        "세탁/관리 난이도 안내를 보강하거나 대체 소재 검토를 함께 표시하는 방향이 후보입니다."
    ),
    "coordination_difficulty": (
        "기본 하의·아우터 조합 예시나 손쉬운 코디 가이드를 함께 보여주는 방향이 후보입니다."
    ),
    "occasion_mismatch": (
        "타깃 occasion 을 재정의하거나 주력 사용 장면을 좁혀 보는 방향이 후보입니다."
    ),
    "purchase_hesitation": (
        "차별 포인트, 관리 편의성, 실착 이미지가 더 필요한지 점검하는 방향이 후보입니다."
    ),
    "style_burden": (
        "톤다운된 컬러 옵션, 베이직 코디 예시, 착용 상황을 "
        "더 구체적으로 보여주는 방향이 후보입니다."
    ),
}


def _categorize_fashion_concern(text: str) -> str | None:
    """concern 텍스트를 우선순위 키워드 규칙으로 1개 카테고리에 매핑.

    매칭 없으면 None 반환 (호출자가 'uncategorized' 로 카운트).
    한국어 substring 매칭. 대소문자는 영문 키워드(tpo)에만 의미.
    """
    if not text:
        return None
    haystack = text.lower()
    for category, keywords in _FASHION_RISK_KEYWORDS:
        for keyword in keywords:
            if keyword in haystack:
                return category
    return None


# ---------------------------------------------------------------------------
# Dataclasses (frozen=True — immutable value objects)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityCounts:
    """PM v3 §16.3 결과 품질 카운트."""

    success: int
    parse_failed: int
    api_failed: int
    total_attempted: int
    distribution_included: int  # success 만 (parse_failed / api_failed 제외)


@dataclass(frozen=True)
class SentimentDistribution:
    """긍정 / 중립 / 부정 분포."""

    positive: int
    neutral: int
    negative: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float


@dataclass(frozen=True)
class PriceBurdenDistribution:
    """가격 부담도 분포."""

    counts: dict  # {"low": n, "medium": n, ...}
    high_or_above_count: int  # high + very_high
    high_or_above_pct: float


@dataclass(frozen=True)
class SegmentRow:
    """세그먼트별 집계 행."""

    segment_label: str  # "30대 / 수도권 / 사무직" 등
    n: int
    positive_pct: float
    avg_interest_score: float


@dataclass(frozen=True)
class TopReasons:
    """주요 긍정 / 망설임 이유 상위 N."""

    positive: list  # list[tuple[str, int]] — (reason, count)
    concerns: list  # list[tuple[str, int]]


@dataclass(frozen=True)
class FashionRiskBreakdown:
    """패션 위험 신호 카테고리 집계.

    counts: 카테고리 키 → main_concerns 매칭 수.
    examples: 카테고리 키 → 매칭된 concern 텍스트 상위 N (정규화 후).
    total_concerns: 분류 대상 main_concerns 총 개수 (중복 포함).
    uncategorized_count: 어떤 카테고리에도 매칭되지 않은 concern 수.
    """

    counts: dict
    examples: dict
    total_concerns: int
    uncategorized_count: int


@dataclass(frozen=True)
class ModificationSuggestion:
    """deterministic 수정 제안.

    LLM 호출 없이 카테고리 카운트 → 고정 문구 매핑.
    n_signals 가 1 이상인 카테고리만 생성된다.
    """

    category: str  # FASHION_RISK_CATEGORY_KEYS 중 하나
    category_label: str  # 한국어 라벨
    n_signals: int
    suggestion: str


@dataclass(frozen=True)
class AggregateReport:
    """집계 결과 전체."""

    sample_size: int
    quality: QualityCounts
    sentiment: SentimentDistribution
    avg_interest_score: float  # 1자리 소수
    price_burden: PriceBurdenDistribution
    segments_age: list  # list[SegmentRow]
    segments_sex: list
    segments_state: list
    segments_occupation: list
    segments_price_burden: list
    top_reasons: TopReasons
    sample_warning: str | None  # PM v3 §17.3 표 매핑

    # 패션 위험 신호 + 수정 제안 + 대표 페르소나
    fashion_risks: FashionRiskBreakdown = field(
        default_factory=lambda: FashionRiskBreakdown(
            counts={k: 0 for k in FASHION_RISK_CATEGORY_KEYS},
            examples={k: [] for k in FASHION_RISK_CATEGORY_KEYS},
            total_concerns=0,
            uncategorized_count=0,
        )
    )
    modification_suggestions: list = field(default_factory=list)
    representative_responses: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sample warning (PM v3 §17.3)
# ---------------------------------------------------------------------------

_SAMPLE_WARNING_100 = "기본 리포트 권장"


def _sample_warning(n: int) -> str | None:
    """PM v3 §17.3 표에서 샘플 수 → 경고 문구 매핑.

    n < 30  → "데모/프롬프트 테스트용. 분포 해석 금지"
    30 ≤ n < 50 → "방향성 참고용. 세그먼트 비교 부적합"
    50 ≤ n < 100 → "간단한 반응 분포 참고 가능"
    n ≥ 100 → "기본 리포트 권장"
    """
    if n < 30:
        return "데모/프롬프트 테스트용. 분포 해석 금지"
    if n < 50:
        return "방향성 참고용. 세그먼트 비교 부적합"
    if n < 100:
        return "간단한 반응 분포 참고 가능"
    return _SAMPLE_WARNING_100


# ---------------------------------------------------------------------------
# Age bucketing
# ---------------------------------------------------------------------------

_AGE_BUCKETS: list[tuple[int, int, str]] = [
    (0, 9, "10대 미만"),
    (10, 19, "10대"),
    (20, 29, "20대"),
    (30, 39, "30대"),
    (40, 49, "40대"),
    (50, 59, "50대"),
    (60, 69, "60대"),
    (70, 9999, "70대 이상"),
]


def _age_bucket(age: int) -> str:
    for lo, hi, label in _AGE_BUCKETS:
        if lo <= age <= hi:
            return label
    return "기타"


# ---------------------------------------------------------------------------
# Segment helpers
# ---------------------------------------------------------------------------


def _build_segment_rows(
    results: list[EvaluationResult],
    key_fn,
) -> list[SegmentRow]:
    """results를 key_fn(result)로 그룹화 → SegmentRow 목록 (n>0 만)."""
    groups: dict[str, list[EvaluationResult]] = {}
    for r in results:
        label = key_fn(r)
        groups.setdefault(label, []).append(r)

    rows = []
    for label, group in sorted(groups.items()):
        n = len(group)
        pos = sum(1 for r in group if r.sentiment == "positive")
        positive_pct = round(pos / n * 100, 1) if n else 0.0
        avg_score = round(sum(r.interest_score for r in group) / n, 1) if n else 0.0
        rows.append(
            SegmentRow(
                segment_label=label,
                n=n,
                positive_pct=positive_pct,
                avg_interest_score=avg_score,
            )
        )
    return rows


def _occupation_first_word(occupation: str) -> str:
    """직업명 첫 단어 추출 (공백 기준)."""
    if not occupation:
        return "기타"
    return occupation.split()[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def aggregate(
    results: list[EvaluationResult],
    persona_attributes: dict[str, dict],
    quality_counts: QualityCounts,
) -> AggregateReport:
    """results는 status=success인 것만. parse_failed / api_failed는 quality_counts로 전달.

    세그먼트:
      age 구간: 10대 미만 / 10대 / 20대 / 30대 / 40대 / 50대 / 60대 / 70대 이상
      sex: M / F
      state: 데이터셋 값 그대로
      occupation: 첫 단어 정규화
      price_burden: 5개 라벨

    sample_warning: PM v3 §17.3 표 (10/30/50/100명 경계)
    avg_interest_score: round(mean, 1)
    모든 %는 round(.., 1)
    """
    n = len(results)

    # --- Sentiment distribution ---
    sent_counter: Counter = Counter(r.sentiment for r in results)
    pos_n = sent_counter.get("positive", 0)
    neu_n = sent_counter.get("neutral", 0)
    neg_n = sent_counter.get("negative", 0)

    def _pct(count: int) -> float:
        return round(count / n * 100, 1) if n else 0.0

    sentiment = SentimentDistribution(
        positive=pos_n,
        neutral=neu_n,
        negative=neg_n,
        positive_pct=_pct(pos_n),
        neutral_pct=_pct(neu_n),
        negative_pct=_pct(neg_n),
    )

    # --- Average interest score ---
    avg_interest = round(sum(r.interest_score for r in results) / n, 1) if n else 0.0

    # --- Price burden distribution ---
    pb_labels: list[Literal["low", "medium", "high", "very_high", "unknown"]] = [
        "low",
        "medium",
        "high",
        "very_high",
        "unknown",
    ]
    pb_counter: Counter = Counter(r.price_burden for r in results)
    pb_counts: dict[str, int] = {label: pb_counter.get(label, 0) for label in pb_labels}
    high_above = pb_counts.get("high", 0) + pb_counts.get("very_high", 0)
    price_burden = PriceBurdenDistribution(
        counts=pb_counts,
        high_or_above_count=high_above,
        high_or_above_pct=_pct(high_above),
    )

    # --- Segment: age ---
    def _age_key(r: EvaluationResult) -> str:
        attrs = persona_attributes.get(r.persona_id, {})
        age = attrs.get("age", 0)
        return _age_bucket(age)

    segments_age = _build_segment_rows(results, _age_key)

    # --- Segment: sex ---
    def _sex_key(r: EvaluationResult) -> str:
        attrs = persona_attributes.get(r.persona_id, {})
        return str(attrs.get("sex", "기타"))

    segments_sex = _build_segment_rows(results, _sex_key)

    # --- Segment: state ---
    def _state_key(r: EvaluationResult) -> str:
        attrs = persona_attributes.get(r.persona_id, {})
        return str(attrs.get("state", "기타"))

    segments_state = _build_segment_rows(results, _state_key)

    # --- Segment: occupation (first-word normalization) ---
    def _occupation_key(r: EvaluationResult) -> str:
        attrs = persona_attributes.get(r.persona_id, {})
        occ = str(attrs.get("occupation", "기타"))
        return _occupation_first_word(occ)

    segments_occupation = _build_segment_rows(results, _occupation_key)

    # --- Segment: price_burden label ---
    def _pb_label_key(r: EvaluationResult) -> str:
        return r.price_burden

    segments_price_burden = _build_segment_rows(results, _pb_label_key)

    # --- Top reasons ---
    top_reasons = extract_top_reasons(results)

    # --- Sample warning ---
    warning = _sample_warning(n)

    # --- Fashion risk breakdown + suggestions + representatives ---
    fashion_risks = categorize_fashion_risks(results)
    modification_suggestions = generate_modification_suggestions(fashion_risks)
    representative_responses = representative_personas(results, persona_attributes)

    return AggregateReport(
        sample_size=n,
        quality=quality_counts,
        sentiment=sentiment,
        avg_interest_score=avg_interest,
        price_burden=price_burden,
        segments_age=segments_age,
        segments_sex=segments_sex,
        segments_state=segments_state,
        segments_occupation=segments_occupation,
        segments_price_burden=segments_price_burden,
        top_reasons=top_reasons,
        sample_warning=warning,
        fashion_risks=fashion_risks,
        modification_suggestions=modification_suggestions,
        representative_responses=representative_responses,
    )


def extract_top_reasons(
    results: list[EvaluationResult],
    top_n: int = 5,
) -> TopReasons:
    """main_reasons / main_concerns를 평탄화 후 빈도 카운트.

    정규화: strip() + 연속 공백 → 단일 공백 (한국어는 case 변환 없이).
    """

    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    pos_counter: Counter = Counter()
    con_counter: Counter = Counter()

    for r in results:
        for reason in r.main_reasons:
            key = _normalize(reason)
            if key:
                pos_counter[key] += 1
        for concern in r.main_concerns:
            key = _normalize(concern)
            if key:
                con_counter[key] += 1

    positive_top = pos_counter.most_common(top_n)
    concerns_top = con_counter.most_common(top_n)

    return TopReasons(
        positive=positive_top,
        concerns=concerns_top,
    )


def representative_personas(
    results: list[EvaluationResult],
    persona_attributes: dict[str, dict],
    n: int = 3,
) -> list[dict]:
    """세그먼트 다양성을 살린 대표 N명 (positive/neutral/negative 각 1).

    dict 필드: {persona_id, segment_label, sentiment, interest_score, main_reasons (top 1)}.
    persona 원문 전체 포함 금지 — 추상화 라벨만 (PM v3 §7.3).
    n > 가능한 수 → 가능한 만큼만 반환.
    """
    sentiment_order = ["positive", "neutral", "negative"]
    picked: list[dict] = []

    # Build index by sentiment
    by_sentiment: dict[str, list[EvaluationResult]] = {}
    for r in results:
        by_sentiment.setdefault(r.sentiment, []).append(r)

    # Pick one representative per sentiment, in priority order
    for sentiment_label in sentiment_order:
        if len(picked) >= n:
            break
        candidates = by_sentiment.get(sentiment_label, [])
        if not candidates:
            continue
        # Pick the one with the highest (or lowest for negative) interest_score
        if sentiment_label == "positive":
            rep = max(candidates, key=lambda r: r.interest_score)
        elif sentiment_label == "negative":
            rep = min(candidates, key=lambda r: r.interest_score)
        else:
            # neutral: pick middle interest_score
            sorted_cands = sorted(candidates, key=lambda r: r.interest_score)
            rep = sorted_cands[len(sorted_cands) // 2]

        attrs = persona_attributes.get(rep.persona_id, {})
        segment_label = _make_segment_label(attrs)
        main_reason_top = rep.main_reasons[0] if rep.main_reasons else ""

        picked.append(
            {
                "persona_id": rep.persona_id,
                "segment_label": segment_label,
                "sentiment": rep.sentiment,
                "interest_score": rep.interest_score,
                "main_reasons": main_reason_top,
            }
        )

    return picked


def _make_segment_label(attrs: dict) -> str:
    """추상화 라벨 생성: "32세 / 서울 / 사무직" 형식 (PM v3 §7.3)."""
    age = attrs.get("age", "?")
    state = attrs.get("state", "?")
    occupation = attrs.get("occupation", "?")
    return f"{age}세 / {state} / {occupation}"


# ---------------------------------------------------------------------------
# Fashion risk categorization
# ---------------------------------------------------------------------------


def categorize_fashion_risks(
    results: list[EvaluationResult],
    *,
    examples_per_category: int = 3,
) -> FashionRiskBreakdown:
    """results 의 main_concerns 를 7개 패션 위험 카테고리로 분류.

    - 한 concern 은 첫 매칭 카테고리에만 카운트 (중복 매핑 없음).
    - 매칭 안 되는 concern 은 ``uncategorized_count`` 에 누적되지만,
      FashionRiskBreakdown.counts 에는 포함되지 않는다.
    - examples 는 빈도 상위 ``examples_per_category`` 개를 정규화 텍스트 그대로 보존한다.
    - 새 LLM 호출/필드는 사용하지 않는다.
    """
    counts: dict[str, int] = {key: 0 for key in FASHION_RISK_CATEGORY_KEYS}
    counters: dict[str, Counter] = {key: Counter() for key in FASHION_RISK_CATEGORY_KEYS}
    total_concerns = 0
    uncategorized = 0

    for r in results:
        for concern in r.main_concerns:
            normalized = re.sub(r"\s+", " ", concern).strip()
            if not normalized:
                continue
            total_concerns += 1
            category = _categorize_fashion_concern(normalized)
            if category is None:
                uncategorized += 1
                continue
            counts[category] += 1
            counters[category][normalized] += 1

    examples: dict[str, list[str]] = {
        key: [text for text, _ in counter.most_common(examples_per_category)]
        for key, counter in counters.items()
    }

    return FashionRiskBreakdown(
        counts=counts,
        examples=examples,
        total_concerns=total_concerns,
        uncategorized_count=uncategorized,
    )


def generate_modification_suggestions(
    breakdown: FashionRiskBreakdown,
) -> list[ModificationSuggestion]:
    """카테고리 카운트 → deterministic 수정 제안 후보 목록.

    - n_signals >= 1 인 카테고리만 포함.
    - 우선순위는 빈도(desc) → ``FASHION_RISK_CATEGORY_KEYS`` 정의 순서.
    - 모든 문구는 PM v3 §2.3 forbidden phrase 를 포함하지 않는다 (단위 테스트로 검증).
    - 새 LLM 호출/필드는 사용하지 않는다.
    """
    suggestions: list[ModificationSuggestion] = []
    # 정의 순서 유지를 위해 인덱스 매핑
    order_index = {key: i for i, key in enumerate(FASHION_RISK_CATEGORY_KEYS)}
    sorted_items = sorted(
        breakdown.counts.items(),
        key=lambda kv: (-kv[1], order_index.get(kv[0], 999)),
    )
    for category, count in sorted_items:
        if count <= 0:
            continue
        suggestions.append(
            ModificationSuggestion(
                category=category,
                category_label=FASHION_RISK_CATEGORY_LABELS.get(category, category),
                n_signals=count,
                suggestion=_FASHION_RISK_SUGGESTIONS[category],
            )
        )
    return suggestions
