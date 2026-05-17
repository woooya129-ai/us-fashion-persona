# us-fashion-persona

## 미국 패션 컨셉을 AI 페르소나로 먼저 점검

[![Version](https://img.shields.io/badge/version-0.6.2-0F766E)](pyproject.toml)
[![HF Dataset](https://img.shields.io/badge/HF-Dataset-FFD21E?logo=huggingface&logoColor=black)](https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA)
[![GitHub](https://img.shields.io/badge/GitHub-us--fashion--persona-181717?logo=github&logoColor=white)](https://github.com/woooya129-ai/us-fashion-persona)
[![Twin Project](https://img.shields.io/badge/GitHub-k--fashion--persona-181717?logo=github&logoColor=white)](https://github.com/woooya129-ai/k-fashion-persona)
[![Docs](https://img.shields.io/badge/Docs-INSTALL--KOR-2563EB?logo=readthedocs&logoColor=white)](docs/INSTALL-KOR.md)
[![English README](https://img.shields.io/badge/README-English-2563EB)](README.md)
[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-0F766E.svg)](LICENSE)

`us-fashion-persona`는 미국 패션 제품 컨셉을 실제 출시나 공식 조사 전에
합성 페르소나 패널로 먼저 점검하는 local-first Streamlit 도구다. 제품
카드와 필터를 입력하면 관심 이유, 망설임, 가격 부담, 패션 리스크를
Markdown/CSV 리포트로 정리한다.

실제 구매율, 매출, 트렌드, 시장점유율 예측 서비스가 아니다. 설문, 인터뷰,
판매 데이터 분석, 전문가 검토 전에 가설을 좁히는 보조도구다.

![us-fashion-persona main screen](docs/assets/us-fashion-persona-screenshot-03.webp)

![us-fashion-persona result screen](docs/assets/us-fashion-persona-screenshot-04.webp)

## 빠른 이해

| 구분 | 내용 |
|---|---|
| 입력 | 카테고리, 가격, 핏, 소재, 컬러, 시즌, 착용 맥락, 스타일 톤, 타깃 가설, 제품 설명 |
| 패널 | NVIDIA Nemotron-Personas-USA 기반 합성 페르소나 |
| 필터 | 연령, 성별, 미국 주/준주, 직업, seed, 샘플 수 |
| 출력 | 반응 분포, 관심 점수, 이유, 우려, 가격 부담, 대표 카드, Markdown/CSV |
| 기본 프리셋 | FAST 50명, BALANCE 100명, HIGH 300명, MAX 1000명 |
| Advanced | 비용 보호 상한 안에서 샘플 수 직접 입력 가능 |

## 실행 구조

- UI, 데이터셋 필터링, 샘플링, 프롬프트 생성, SQLite 캐시, Markdown/CSV
  리포트 생성은 사용자 PC에서 로컬로 실행된다.
- Streamlit API 모드는 선택한 provider API 서버로 프롬프트를 전송한다.
- Agent Pack 모드는 프롬프트 파일을 내보내고, 사용자의 Codex 또는 Claude
  Code CLI가 평가한 결과를 다시 가져온다.
- API key 값은 저장하지 않는다. 화면에 입력한 key는 현재 Streamlit 세션에서만 쓴다.
- LLM API endpoint는 `config/pricing_config.yaml`의 `api_base_url` host로 제한된다.
- 공개 배포에서는 `UFPS_REQUIRE_USER_PROVIDER_KEY=1`로 사용자 본인 provider key 입력을 강제할 수 있다.

## 설치

필요 조건:

- Git
- Python 3.11 이상
- `uv`
- 선택한 AI provider API key 또는 로그인된 Codex/Claude Code CLI
- 필요 시 Hugging Face token

```bash
git clone https://github.com/woooya129-ai/us-fashion-persona.git
cd us-fashion-persona
uv sync --all-extras --dev
uv run streamlit run src/app.py
```

브라우저에서 연다.

```text
http://localhost:8501
```

자세한 설치는 [docs/INSTALL-KOR.md](docs/INSTALL-KOR.md)를 본다.

## 반복 실행용 환경 변수

실제 key를 저장소 안에 넣지 마라. 반복 실행용 key는 저장소 밖 환경 파일이나
OS 환경변수에 둔다.

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
HF_TOKEN=
```

Groq, DeepSeek, Qwen 같은 OpenAI-compatible provider는
`config/pricing_config.yaml`의 `api_key_env`로 지정된 환경변수를 쓴다.

## Codex / Claude Code 구독 모드

구독형 Codex 또는 Claude Code 사용자는 앱 안에 별도 API provider로 붙이지 않고
Agent Pack 방식으로 평가 흐름을 쓸 수 있다. 순서는 export, CLI 실행, import다.

```powershell
uv run python -m src.agent_bridge export --concept examples/agent_bridge_concept.example.json --out outputs/agent-pack-demo --sample-size 50 --audience unisex
powershell -ExecutionPolicy Bypass -File outputs\agent-pack-demo\commands\run-codex.ps1
uv run python -m src.agent_bridge import --pack outputs\agent-pack-demo --results outputs\agent-pack-demo\results\codex --out outputs\agent-report-codex
```

Claude Code는 `commands\run-claude.ps1`을 실행한 뒤 같은 방식으로 import한다.
처음에는 `--sample-size 5` 또는 `--sample-size 10`으로 확인하는 편이 낫다.

## 데이터와 통계

- 기본 데이터셋: [NVIDIA Nemotron-Personas-USA](https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA)
- 데이터 성격: 실제 사람 명단이 아닌 미국 맥락 합성 페르소나
- 기본 로딩: Hugging Face `datasets` streaming
- 기본 scan: 실행당 최대 3000행을 순차 scan해서 조건에 맞는 패널을 채운다

개별 페르소나의 소득, 자산, 구매력을 추정하지 않는다. 가격 부담 참고값은
`data/public/us_household_context.csv`의 미국 공식 통계 스냅샷을 쓴다.

- BLS Consumer Expenditure Survey 2024: Apparel and services 지출
- BLS Consumer Expenditure Survey 2024: 세전 평균 소득
- U.S. Census CPS ASEC 2024 HINC-02: 가구주 연령별 중위 가구소득
- Federal Reserve SCF 2022: 연령대별 중위/평균 가족 순자산

## 라이선스와 출처

- 코드 라이선스: GNU AGPL-3.0-only
- 페르소나 데이터셋: NVIDIA Nemotron-Personas-USA
- 데이터셋 라이선스: CC BY 4.0 attribution 적용
- 통계 맥락: BLS, U.S. Census, Federal Reserve
- 전체 고지: [LICENSE](LICENSE), [NOTICE](NOTICE), [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)
- 인용 형식: [CITATION.cff](CITATION.cff)
- 방법론: [docs/METHODOLOGY_AND_RIGHTS.md](docs/METHODOLOGY_AND_RIGHTS.md)

폐쇄소스 상업 사용, 사내 SaaS, 재배포 제품, AGPL 조건 적용이 어려운 사용은
별도 서면 상업 라이선스 또는 듀얼 라이선스 협의 대상일 수 있다.

문의: woooya129 [at] gmail [dot] com

한국 맥락 twin project: [k-fashion-persona](https://github.com/woooya129-ai/k-fashion-persona)
