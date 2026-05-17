# SPDX-License-Identifier: AGPL-3.0-only
"""Bilingual UI copy for us-fashion-persona."""

from __future__ import annotations

from src.app_config import APP_VERSION

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
        "job_already_running": "이미 실행 중인 작업이 있어. 취소하거나 완료를 기다려.",
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
        "provider_label": "Provider",
        "model_label": "Model",
        "rate_unit_label": "요금 단위",
        "per_million_tokens": "USD / 1M tokens",
        "input_rate_label": "Input 단가",
        "output_rate_label": "Output 단가",
        "checked_at_label": "가격 확인일",
        "source_url_label": "가격 출처",
        "price_unset": "가격 미설정",
        "verification_label": "호출 검증",
        "unverified_provider": "검증 전 provider라 실제 호출이 실패할 수 있어.",
        "estimate_only": "참고 추정",
        "estimate_basis_label": "추정 기준",
        "sidebar_estimate_basis": "{sample_size}명 · 짧은 제품 카드",
        "run_tokens_label": "이번 실행 토큰",
        "cost_input_label": "입력 비용",
        "cost_output_label": "출력 비용",
        "cost_max_output_label": "출력 추정 / 상한",
        "cost_unit_note": (
            "1M token 단가는 과금 단위고, 이번 실행은 그중 일부만 써. "
            "실제 과금은 tokenizer, 출력 길이, 재시도, provider 계정 조건에 따라 달라질 수 있어."
        ),
        "model_compare_header": "모델별 비용 비교",
        "model_compare_caption": "현재 제품 카드 길이와 샘플 수 기준 참고 추정치야.",
        "cost_table_model": "Model",
        "cost_table_provider": "Provider",
        "cost_table_rate": "Input/Output 단가",
        "cost_table_estimate": "실행 추정",
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
        "provider_key_help": (
            "OpenAI-compatible provider 실행용 API KEY 상태야. 값은 표시하지 않아."
        ),
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
        "start_pending_title": "작동 중",
        "start_pending_toast": "작업을 시작하는 중이야. 잠시 기다려.",
        "start_pending_body": (
            "API 연결과 첫 응답을 확인하고 있어. 화면이 잠시 멈춘 것처럼 보여도 작업은 이어져."
        ),
        "job_started": "작업 시작",
        "details_header": "자세히",
        "details_summary": "가격 기준, 예상 비용, 재현용 값을 확인한다.",
        "results_preview_header": "페르소나 의견 미리보기",
        "results_preview_body": "대표 의견 5개만 먼저 보여줘. 전체 결과는 엑셀용 파일로 내려받아.",
        "dominant_preview_header": "최다 반응 대표 카드",
        "dominant_preview_body": "{sentiment} 반응이 {pct}% ({count}/{total})로 가장 높아.",
        "dominant_preview_project": "대표 페르소나",
        "excel_download": "엑셀용 CSV 다운로드",
        "results_loading": "합성 페르소나 의견을 모으는 중",
        "persona_preview_empty": "아직 보여줄 성공 결과가 없다.",
        "persona_card_reasons": "좋게 본 점",
        "persona_card_concerns": "망설인 점",
        "persona_card_note": "한줄 의견",
        "status_header": "진행 상태",
        "status_help_button": "도움말",
        "status_help_title": "성공/실패 기준",
        "status_help_body": (
            "success: API 응답을 받았고 JSON 파싱과 스키마 검증을 통과한 결과야.\n\n"
            "failed: API 실패, 빈 응답, JSON 파싱 실패, 필수 필드 누락 때문에 "
            "리포트 분포에서 제외된 결과야.\n\n"
            "cached: 같은 컨셉과 모델로 저장된 결과를 재사용한 상태야.\n\n"
            "최종 분포와 요약에는 유효한 JSON 결과만 포함돼."
        ),
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
        "job_already_running": (
            "A screening job is already running. Cancel it or wait for completion."
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
        "provider_label": "Provider",
        "model_label": "Model",
        "rate_unit_label": "Rate unit",
        "per_million_tokens": "USD / 1M tokens",
        "input_rate_label": "Input rate",
        "output_rate_label": "Output rate",
        "checked_at_label": "Price checked",
        "source_url_label": "Price source",
        "price_unset": "Price unset",
        "verification_label": "Live-call verification",
        "unverified_provider": "Unverified provider; calls may fail.",
        "estimate_only": "Reference estimate",
        "estimate_basis_label": "Estimate basis",
        "sidebar_estimate_basis": "{sample_size} personas · short product card",
        "run_tokens_label": "Run tokens",
        "cost_input_label": "Input cost",
        "cost_output_label": "Output cost",
        "cost_max_output_label": "Output estimate / cap",
        "cost_unit_note": (
            "The 1M-token price is the billing unit. This run uses only part of it. "
            "Actual billing can vary by tokenizer, output length, retries, "
            "and provider account terms."
        ),
        "model_compare_header": "Model Cost Comparison",
        "model_compare_caption": (
            "Reference one-run estimate for the current product-card length and sample size."
        ),
        "cost_table_model": "Model",
        "cost_table_provider": "Provider",
        "cost_table_rate": "Input/output rate",
        "cost_table_estimate": "Run estimate",
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
        "provider_key_help": (
            "API KEY status for OpenAI-compatible provider calls. Values are never shown."
        ),
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
        "start_pending_title": "Working",
        "start_pending_toast": "Starting the run. Please wait a moment.",
        "start_pending_body": (
            "Checking the API connection and first response. "
            "Work continues even if the screen looks dim for a moment."
        ),
        "job_started": "Job started",
        "details_header": "Details",
        "details_summary": "Check price context, cost estimate, and reproducibility values.",
        "results_preview_header": "Persona opinion preview",
        "results_preview_body": (
            "Shows 5 representative opinions first. Download the full data for Excel."
        ),
        "dominant_preview_header": "Top-response representative card",
        "dominant_preview_body": "{sentiment} responses are highest at {pct}% ({count}/{total}).",
        "dominant_preview_project": "Representative persona",
        "excel_download": "Download CSV for Excel",
        "results_loading": "Collecting synthetic persona opinions",
        "persona_preview_empty": "No successful opinion rows to preview yet.",
        "persona_card_reasons": "Reasons",
        "persona_card_concerns": "Concerns",
        "persona_card_note": "Note",
        "status_header": "Progress",
        "status_help_button": "Help",
        "status_help_title": "Success/failure criteria",
        "status_help_body": (
            "success: API response was received and passed JSON parsing plus schema validation.\n\n"
            "failed: API failure, missing response, JSON parsing failure, "
            "or missing required fields "
            "kept the row out of the report distribution.\n\n"
            "cached: A stored result for the same concept and model was reused.\n\n"
            "Only valid JSON results are included in the final distribution and summary."
        ),
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
