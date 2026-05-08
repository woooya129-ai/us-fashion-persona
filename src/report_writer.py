# SPDX-License-Identifier: AGPL-3.0-only
"""Phase 4 리포트 출력 — PM v3 §2, §17, §18.2, §18.3.

CSV formula injection 방어 + PM v3 §2.3 금지 표현 검증 포함.
No LLM / HF / DB calls.

추가 섹션 (fashion-public-beta v3):
- 패션 위험 신호, 가격 부담 해석, 스타일/코디 장벽, 구매 망설임,
  수정 제안 후보, 대표 페르소나 반응 섹션.
- 수정 제안은 deterministic rule 로 생성된 ``AggregateReport.modification_suggestions``
  를 그대로 출력한다 (LLM 호출/새 schema 필드 없음).
"""

import csv
import re
from io import StringIO
from pathlib import Path

from src.aggregator import (
    FASHION_RISK_CATEGORY_KEYS,
    FASHION_RISK_CATEGORY_LABELS,
    AggregateReport,
)

# ---------------------------------------------------------------------------
# PM v3 §2.3 금지 표현 매트릭스
#
# 주의: bare "예측" 또는 bare "정확한"은 포함하지 않는다.
#  → PM v3 §18.3 footer가 "매출 예측"을 포함하므로
#    bare 토큰을 금지하면 모든 리포트가 ValueError를 일으킨다.
#  → compound phrase 단위로 금지한다.
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES: list[str] = [
    # PM v3 §2.3 표 — 금지 표현 그대로
    "한국 소비자의",
    "구매 가능성",
    "시장 반응 예측",
    "AI 시장조사",
    "실제 고객 반응",
    "이 가격이면 구매 가능",
    # PM v3 §1 금지 포지셔닝 토큰 (단독 단어 수준)
    "구매율",
    "시장점유율",
    "지불의향",
    "이 제품을 산다",
    "은(는) 이 제품을 산다",
    # USA-public release: block country-wide or real-consumer generalization too.
    "미국 소비자의",
    "미국 소비자",
    "US consumers",
    "U.S. consumers",
    "American consumers",
    "real consumers",
    "actual consumers",
    "purchase rate",
    "sales forecast",
    "market share",
]


# ---------------------------------------------------------------------------
# Footer (PM v3 §18.3)
# ---------------------------------------------------------------------------

CONTACT_DISPLAY = "woooya129 [at] gmail [dot] com"


def required_footer_text() -> str:
    """PM v3 §18.3 footer 그대로 반환 — 모든 리포트에 필수."""
    return (
        "본 도구는 합성 페르소나와 LLM 기반의 사전 가설 분석 도구입니다.\n"
        "실제 소비자 조사, 매출 예측, 법률 자문, 최종 사업 판단을 대체하지 않습니다.\n"
        "Data source (only external dataset): NVIDIA Nemotron-Personas-USA, CC BY 4.0.\n"
        "Dataset URL: https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA\n"
        "CC BY 4.0: https://creativecommons.org/licenses/by/4.0/\n"
        "US Fashion Persona Screener.\n"
        f"Contact: {CONTACT_DISPLAY}"
    )


# ---------------------------------------------------------------------------
# Safety check
# ---------------------------------------------------------------------------


def assert_safe_phrasing(markdown_text: str) -> None:
    """FORBIDDEN_PHRASES 검출 시 ValueError.

    호출자가 render_markdown 결과 검증용.
    required_footer_text()를 포함한 텍스트도 이 검증을 통과해야 한다.
    """
    for phrase in FORBIDDEN_PHRASES:
        if phrase in markdown_text:
            raise ValueError(f"금지 표현 발견: {phrase!r}. PM v3 §2.3 참조.")


# ---------------------------------------------------------------------------
# CSV cell escape (formula injection defense)
# ---------------------------------------------------------------------------

_FORMULA_START_CHARS = frozenset("=+-@\t\r")


def escape_csv_cell(value: object) -> str:
    """첫 글자가 = / + / - / @ / \\t / \\r 면 ' prefix.

    그 외 str() 변환만.
    """
    text = str(value)
    if text and text[0] in _FORMULA_START_CHARS:
        return "'" + text
    return text


# ---------------------------------------------------------------------------
# fashion-public-beta v3 helpers
#
# 패션 위험 신호 / 가격 부담 해석 / 스타일·코디 장벽 / 구매 망설임 / 수정 제안 /
# 대표 페르소나 반응 섹션을 lines 리스트에 in-place 로 누적한다.
# ---------------------------------------------------------------------------

# 패션 위험 신호 섹션을 가격/스타일·코디/구매 망설임 3개 묶음으로 그룹핑.
# (리포트 가독성 — 동일 정보를 다른 시각으로 보여줌)
_PRICE_GROUP: tuple[str, ...] = ("price_burden",)
_STYLE_COORD_GROUP: tuple[str, ...] = (
    "style_burden",
    "coordination_difficulty",
    "occasion_mismatch",
    "fit_risk",
    "material_care_burden",
)
_HESITATION_GROUP: tuple[str, ...] = ("purchase_hesitation",)


def _format_examples(examples: list[str], max_items: int = 3) -> str:
    """대표 concern 예시 목록 → 한 줄 콤마 표기.

    빈 리스트면 빈 문자열을 반환한다 (호출자가 표기 생략).
    """
    if not examples:
        return ""
    return ", ".join(examples[:max_items])


def _append_fashion_risk_sections(lines: list[str], report: AggregateReport) -> None:
    """패션 위험 신호 / 가격 부담 해석 / 스타일·코디 장벽 / 구매 망설임 섹션."""
    risks = report.fashion_risks

    # ---- 1) 패션 위험 신호 (전체 카테고리 카운트 표) ----
    lines.append("## 패션 위험 신호 (합성 패널 main_concerns 분류)")
    lines.append("")
    lines.append("| 카테고리 | 신호 수 | 대표 concern 예시 |")
    lines.append("|---|---:|---|")
    for key in FASHION_RISK_CATEGORY_KEYS:
        label = FASHION_RISK_CATEGORY_LABELS.get(key, key)
        count = risks.counts.get(key, 0)
        example_text = _format_examples(risks.examples.get(key, []))
        lines.append(f"| {label} | {count} | {example_text} |")
    lines.append("")
    lines.append(
        f"> 분류 대상 concern 총 {risks.total_concerns}건 중 "
        f"미분류 {risks.uncategorized_count}건 "
        "(키워드 매칭 안 됨, 수정 제안에서는 제외)."
    )
    lines.append("")

    # ---- 2) 가격 부담 해석 ----
    pb = report.price_burden
    lines.append("## 가격 부담 해석")
    lines.append("")
    lines.append(f"- 가격 부담도 high 이상: {pb.high_or_above_count}명 / {pb.high_or_above_pct}%")
    price_signal = sum(risks.counts.get(k, 0) for k in _PRICE_GROUP)
    lines.append(f"- main_concerns 가격 관련 신호: {price_signal}건")
    if risks.examples.get("price_burden"):
        examples = _format_examples(risks.examples["price_burden"])
        lines.append(f"- 대표 concern: {examples}")
    lines.append("")
    lines.append(
        "> 합성 패널 응답 기준의 가격 신호 분포일 뿐, "
        "실제 가격 수용성이나 실제 결제 결정의 근거가 아닙니다."
    )
    lines.append("")

    # ---- 3) 스타일/코디 장벽 ----
    lines.append("## 스타일/코디 장벽")
    lines.append("")
    has_any = False
    for key in _STYLE_COORD_GROUP:
        count = risks.counts.get(key, 0)
        if count <= 0:
            continue
        has_any = True
        label = FASHION_RISK_CATEGORY_LABELS.get(key, key)
        examples = _format_examples(risks.examples.get(key, []))
        line = f"- {label}: {count}건"
        if examples:
            line += f" — {examples}"
        lines.append(line)
    if not has_any:
        lines.append("- 합성 패널 응답에서 스타일/코디 장벽 신호가 잡히지 않았습니다.")
    lines.append("")

    # ---- 4) 구매 망설임 ----
    lines.append("## 구매 망설임")
    lines.append("")
    hesitation_signal = sum(risks.counts.get(k, 0) for k in _HESITATION_GROUP)
    lines.append(f"- 구매 망설임 신호: {hesitation_signal}건")
    if risks.examples.get("purchase_hesitation"):
        examples = _format_examples(risks.examples["purchase_hesitation"])
        lines.append(f"- 대표 concern: {examples}")
    if hesitation_signal == 0:
        lines.append("- 합성 패널 응답에서 구매 망설임 신호가 잡히지 않았습니다.")
    lines.append("")


def _append_modification_suggestions_section(lines: list[str], report: AggregateReport) -> None:
    """deterministic 수정 제안 후보 섹션."""
    suggestions = report.modification_suggestions
    lines.append("## 수정 제안 후보 (deterministic rule, LLM 호출 없음)")
    lines.append("")
    if not suggestions:
        lines.append(
            "- 합성 패널 응답에서 수정 제안 후보를 트리거할 위험 신호가 잡히지 않았습니다."
        )
        lines.append("")
        return
    for i, s in enumerate(suggestions, start=1):
        lines.append(f"{i}. **{s.category_label}** (신호 {s.n_signals}건)")
        lines.append(f"   - {s.suggestion}")
    lines.append("")
    lines.append(
        "> 위 제안은 합성 패널 응답을 키워드 규칙으로 분류한 결과를 기반으로 한 후보 방향이며, "
        "실제 소비자 의견을 대체하거나 실제 매출/판매 결과를 보장하지 않습니다."
    )
    lines.append("")


def _append_representative_responses_section(lines: list[str], report: AggregateReport) -> None:
    """대표 페르소나 반응 섹션 (추상화 라벨만)."""
    reps = report.representative_responses
    lines.append("## 대표 페르소나 반응 (추상화 라벨, 원문 비포함)")
    lines.append("")
    if not reps:
        lines.append("- 대표 페르소나 응답이 없습니다.")
        lines.append("")
        return
    lines.append("| 세그먼트 | 반응 | 관심도 | 대표 긍정 이유 |")
    lines.append("|---|---|---:|---|")
    for rep in reps:
        segment = rep.get("segment_label", "")
        sentiment = rep.get("sentiment", "")
        score = rep.get("interest_score", "")
        reason = rep.get("main_reasons", "")
        lines.append(f"| {segment} | {sentiment} | {score} | {reason} |")
    lines.append("")


def _csv_fashion_rows(writer_row, report: AggregateReport) -> None:
    """CSV 에 패션 위험 신호 / 수정 제안 / 대표 페르소나 행을 추가.

    writer_row: callable(section, key, value)  — render_csv 의 _row 헬퍼.
    """
    risks = report.fashion_risks

    # 패션 위험 신호 카운트
    for key in FASHION_RISK_CATEGORY_KEYS:
        label = FASHION_RISK_CATEGORY_LABELS.get(key, key)
        count = risks.counts.get(key, 0)
        writer_row("패션위험신호", label, f"{count}건")
        examples = risks.examples.get(key, [])
        if examples:
            writer_row("패션위험신호_대표concern", label, _format_examples(examples))
    writer_row("패션위험신호_총합", "분류 대상 concern", risks.total_concerns)
    writer_row("패션위험신호_총합", "미분류 concern", risks.uncategorized_count)

    # 수정 제안 후보
    for rank, suggestion in enumerate(report.modification_suggestions, start=1):
        writer_row(
            "수정제안",
            f"rank{rank}_{suggestion.category}",
            f"{suggestion.category_label} (신호 {suggestion.n_signals}건): {suggestion.suggestion}",
        )

    # 대표 페르소나 반응 (추상화 라벨만)
    for rank, rep in enumerate(report.representative_responses, start=1):
        segment = rep.get("segment_label", "")
        sentiment = rep.get("sentiment", "")
        score = rep.get("interest_score", "")
        reason = rep.get("main_reasons", "")
        writer_row(
            "대표페르소나반응",
            f"rank{rank}",
            f"{segment} | {sentiment} | 관심도 {score} | {reason}",
        )


# ---------------------------------------------------------------------------
# Markdown render
# ---------------------------------------------------------------------------


def render_markdown(report: AggregateReport) -> str:
    """PM v3 §17.1 메인 지표 + §18.2 Main Results 섹션.

    모든 표현은 '합성 패널 N명 기준'으로 시작.
    출력 텍스트에 FORBIDDEN_PHRASES 매치 시 ValueError raise.
    """
    n = report.sample_size
    s = report.sentiment
    pb = report.price_burden
    q = report.quality

    lines: list[str] = []

    # Header
    lines.append("# US Fashion Persona Screener — 합성 패널 분석 리포트")
    lines.append("")

    # Sample warning
    if report.sample_warning:
        lines.append(f"> **주의**: {report.sample_warning}")
        lines.append("")

    # Main metrics
    lines.append(f"## 합성 패널 {n}명 기준 반응 분포")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 긍정 반응 | {s.positive}명 / {s.positive_pct}% |")
    lines.append(f"| 중립 반응 | {s.neutral}명 / {s.neutral_pct}% |")
    lines.append(f"| 부정 반응 | {s.negative}명 / {s.negative_pct}% |")
    lines.append(f"| 평균 관심도 | {report.avg_interest_score} / 10 |")
    lines.append(
        f"| 가격 부담도 high 이상 | {pb.high_or_above_count}명 / {pb.high_or_above_pct}% |"
    )
    lines.append(f"| 파싱 실패/제외 | {q.parse_failed + q.api_failed}명 |")
    lines.append("")

    # Quality
    lines.append("## 결과 품질")
    lines.append("")
    lines.append("| 항목 | 수 |")
    lines.append("|---|---|")
    lines.append(f"| 성공 | {q.success}명 |")
    lines.append(f"| 파싱 실패 | {q.parse_failed}명 |")
    lines.append(f"| API 실패 | {q.api_failed}명 |")
    lines.append(f"| 분포 계산 포함 | {q.distribution_included}명 |")
    lines.append("")

    # Price burden distribution
    lines.append("## 가격 부담도 분포")
    lines.append("")
    lines.append("| 라벨 | 명수 |")
    lines.append("|---|---|")
    for label, count in report.price_burden.counts.items():
        lines.append(f"| {label} | {count}명 |")
    lines.append("")

    # Top reasons
    if report.top_reasons.positive:
        lines.append("## 주요 긍정 이유 (합성 패널 응답 기준)")
        lines.append("")
        for reason, count in report.top_reasons.positive:
            lines.append(f"- {reason} ({count}건)")
        lines.append("")

    if report.top_reasons.concerns:
        lines.append("## 주요 망설임 이유 (합성 패널 응답 기준)")
        lines.append("")
        for concern, count in report.top_reasons.concerns:
            lines.append(f"- {concern} ({count}건)")
        lines.append("")

    # ------------------------------------------------------------------
    # fashion-public-beta v3 — 패션 위험 신호 + 수정 제안 후보
    # ------------------------------------------------------------------
    _append_fashion_risk_sections(lines, report)
    _append_modification_suggestions_section(lines, report)
    _append_representative_responses_section(lines, report)

    # Segment tables
    def _segment_table(title: str, rows: list) -> None:
        if not rows:
            return
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| 세그먼트 | n | 긍정률 | 평균 관심도 |")
        lines.append("|---|---:|---:|---:|")
        for row in rows:
            cell = (
                f"| {row.segment_label} | {row.n}"
                f" | {row.positive_pct}% | {row.avg_interest_score} |"
            )
            lines.append(cell)
        lines.append("")

    _segment_table("연령대별 반응 (합성 패널 기준)", report.segments_age)
    _segment_table("성별 반응 (합성 패널 기준)", report.segments_sex)
    _segment_table("주별 반응 (합성 패널 기준)", report.segments_state)
    _segment_table("직업 계열별 반응 (합성 패널 기준)", report.segments_occupation)
    _segment_table("가격 부담도별 반응 (합성 패널 기준)", report.segments_price_burden)

    # Footer (PM v3 §18.3 — 필수)
    lines.append("---")
    lines.append("")
    lines.append(required_footer_text())
    lines.append("")

    result = "\n".join(lines)

    # Validate forbidden phrases
    assert_safe_phrasing(result)

    return result


# ---------------------------------------------------------------------------
# CSV render
# ---------------------------------------------------------------------------


def render_csv(report: AggregateReport) -> str:
    """평면화된 표: section, key, value 컬럼.

    formula injection 방어: 모든 셀에 대해 첫 글자가 = / + / - / @ / \\t / \\r 면 ' prefix.
    BOM 추가 (Excel 호환): \\ufeff 시작.
    """
    buf = StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    def _row(section: str, key: str, value: object) -> None:
        writer.writerow(
            [
                escape_csv_cell(section),
                escape_csv_cell(key),
                escape_csv_cell(value),
            ]
        )

    # Header
    writer.writerow(["section", "key", "value"])

    n = report.sample_size
    s = report.sentiment
    pb = report.price_burden
    q = report.quality

    # Main metrics
    _row("반응분포", f"합성 패널 {n}명 기준 - 긍정", f"{s.positive}명 / {s.positive_pct}%")
    _row("반응분포", f"합성 패널 {n}명 기준 - 중립", f"{s.neutral}명 / {s.neutral_pct}%")
    _row("반응분포", f"합성 패널 {n}명 기준 - 부정", f"{s.negative}명 / {s.negative_pct}%")
    _row("반응분포", "평균 관심도", f"{report.avg_interest_score} / 10")
    _row(
        "반응분포",
        "가격부담도 high 이상",
        f"{pb.high_or_above_count}명 / {pb.high_or_above_pct}%",
    )

    # Quality
    _row("결과품질", "성공", q.success)
    _row("결과품질", "파싱 실패", q.parse_failed)
    _row("결과품질", "API 실패", q.api_failed)
    _row("결과품질", "분포 계산 포함", q.distribution_included)

    # Price burden
    for label, count in pb.counts.items():
        _row("가격부담도", label, count)

    # Top reasons
    for rank, (reason, count) in enumerate(report.top_reasons.positive, start=1):
        _row("주요긍정이유", f"rank{rank}", f"{reason} ({count}건)")

    for rank, (concern, count) in enumerate(report.top_reasons.concerns, start=1):
        _row("주요망설임이유", f"rank{rank}", f"{concern} ({count}건)")

    # fashion-public-beta v3 — 패션 위험 신호 / 수정 제안 / 대표 페르소나
    _csv_fashion_rows(_row, report)

    def _seg_val(row) -> str:
        return f"n={row.n} 긍정률={row.positive_pct}% 평균관심도={row.avg_interest_score}"

    # Segment: age
    for row in report.segments_age:
        _row("세그먼트_연령대", row.segment_label, _seg_val(row))

    # Segment: sex
    for row in report.segments_sex:
        _row("세그먼트_성별", row.segment_label, _seg_val(row))

    # Segment: state
    for row in report.segments_state:
        _row("세그먼트_주", row.segment_label, _seg_val(row))

    # Segment: occupation
    for row in report.segments_occupation:
        _row("세그먼트_직업", row.segment_label, _seg_val(row))

    # Segment: price_burden
    for row in report.segments_price_burden:
        _row("세그먼트_가격부담도", row.segment_label, _seg_val(row))

    # Sample warning
    if report.sample_warning:
        _row("경고", "표본수경고", report.sample_warning)

    # Footer (PM v3 §18.3 — 필수)
    for line in required_footer_text().splitlines():
        _row("고지", "footer", line)

    result = "﻿" + buf.getvalue()

    # PM v3 §2.3 금지 표현은 Markdown 뿐 아니라 CSV export 에도 적용된다.
    # (사용자/LLM 텍스트가 reasons/concerns 경로로 셀에 들어올 수 있다.)
    assert_safe_phrasing(result)

    return result


# ---------------------------------------------------------------------------
# Slug normalization
# ---------------------------------------------------------------------------

_SLUG_PATTERN = re.compile(r"[^\w가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\-]", re.UNICODE)
_SLUG_HYPHEN_COLLAPSE = re.compile(r"-{2,}")


def _project_slug(project_name: str) -> str:
    """project_name → slug (한글/영문/숫자/하이픈만, 그 외 제거).

    공백 → 하이픈, 연속 하이픈 축소, strip.
    """
    slug = project_name.strip()
    slug = slug.replace(" ", "-")
    slug = _SLUG_PATTERN.sub("", slug)
    slug = _SLUG_HYPHEN_COLLAPSE.sub("-", slug)
    slug = slug.strip("-")
    return slug or "report"


# ---------------------------------------------------------------------------
# Write report files
# ---------------------------------------------------------------------------

_UNSAFE_JOB_ID_PATTERN = re.compile(r"[/\\]|\.\.")


def write_report_files(
    report: AggregateReport,
    output_dir: Path,
    project_name: str,
    job_id: str,
) -> tuple[Path, Path]:
    """output_dir/{project_slug}/{job_id}.md, .csv 작성.

    project_slug: project_name 정규화.
    output_dir 부재 시 mkdir.
    리턴: (md_path, csv_path).
    path traversal 방어: job_id에 .. / / \\ 금지.
    """
    # Path traversal defense
    if _UNSAFE_JOB_ID_PATTERN.search(job_id):
        raise ValueError(f"job_id에 경로 탐색 문자가 포함되어 있습니다: {job_id!r}")
    if not job_id or not job_id.strip():
        raise ValueError("job_id는 비어 있을 수 없습니다.")

    slug = _project_slug(project_name)
    target_dir = output_dir / slug

    # Normalize and verify the path stays within output_dir
    try:
        resolved_target = target_dir.resolve()
        resolved_base = output_dir.resolve()
        resolved_target.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"출력 경로가 output_dir 밖을 가리킵니다: {target_dir}") from exc

    target_dir.mkdir(parents=True, exist_ok=True)

    md_path = target_dir / f"{job_id}.md"
    csv_path = target_dir / f"{job_id}.csv"

    md_content = render_markdown(report)
    csv_content = render_csv(report)

    md_path.write_text(md_content, encoding="utf-8")
    # csv_content already starts with ﻿ BOM — use plain utf-8 to avoid double BOM
    csv_path.write_text(csv_content, encoding="utf-8")

    return md_path, csv_path
