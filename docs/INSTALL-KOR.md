# us-fashion-persona 설치 가이드

이 앱은 hosted evaluation service가 아니다. 사용자 컴퓨터에서 실행되는
local-first Streamlit 앱이고, 사용자가 직접 준비한 API key를 쓴다.

## 1. 필요 조건

- Git
- Python 3.11 이상
- `uv`
- 선택한 AI provider API key
- 필요 시 Hugging Face token

`uv` 설치 문서:

```text
https://docs.astral.sh/uv/
```

## 2. 저장소 받기

```bash
git clone https://github.com/woooya129-ai/us-fashion-persona.git
cd us-fashion-persona
```

## 3. 의존성 설치

```bash
uv sync --all-extras --dev
```

선택:

```bash
uv run pre-commit install
```

## 4. 앱 실행

```bash
uv run streamlit run src/app.py
```

브라우저에서 연다.

```text
http://localhost:8501
```

README Docs 버튼을 로컬에서 열고 싶으면 다른 터미널에서 실행한다.

```bash
uv run python -m http.server 8510
```

## 5. API key 입력

가장 단순한 방식은 앱 화면의 password 입력칸에 key를 붙여넣는 것이다.

지원 입력:

- 선택한 LLM provider API key
- Hugging Face 접근이 필요할 때 `HF TOKEN`

LLM API endpoint는 `config/pricing_config.yaml`에 등록된 `api_base_url`
host로 제한된다. 이 YAML을 바꾸면 허용 host set도 바뀌므로 공유 배포 전에는
코드 리뷰 대상으로 봐야 한다.

## 6. 반복 실행용 환경 파일

실제 key를 저장소 안에 넣지 마라. 반복 실행용 key는 저장소 밖 환경 파일이나
OS 환경변수에 둔다.

macOS / Linux:

```bash
mkdir -p ~/secrets/us-fashion
cp .env.example ~/secrets/us-fashion/.env
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\secrets\us-fashion"
Copy-Item .env.example "$HOME\secrets\us-fashion\.env"
```

환경 파일 예시:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
HF_TOKEN=
```

`GOOGLE_API_KEY`는 Google AI Studio의 Gemini API key 기준이다. Vertex AI key가 아니다.
Groq, DeepSeek, Qwen 같은 OpenAI-compatible provider는
`pricing_config.yaml`의 `api_key_env`로 지정된 환경변수를 쓴다.

공개 데모나 공유 배포에서는 다음 값을 설정할 수 있다.

```env
UFPS_REQUIRE_USER_PROVIDER_KEY=1
```

이 값은 owner-side provider key fallback을 막고, 방문자가 본인 provider API key를
입력하게 만든다.

## 7. 기본 workflow

1. LLM provider와 model을 고른다.
2. provider API key를 입력한다.
3. 필요하면 `HF TOKEN`을 입력한다.
4. 미국 경제 기준 세그먼트를 고른다.
5. 카테고리, 가격, 핏, 소재, 컬러, 시즌, 착용 맥락, 스타일 톤, 타깃 가설, 제품 설명을 입력한다.
6. 샘플 수, seed, audience, 필터를 조정한다.
7. 예상 비용과 시간을 확인한다.
8. `ENTER`를 누른다.
9. Markdown 또는 CSV 리포트를 내려받는다.

## 8. 데이터 위치

기본 `NVIDIA dataset` 모드는 Hugging Face의
`nvidia/Nemotron-Personas-USA`를 streaming으로 읽는다. 원본 데이터셋은 저장소에
포함하지 않는다.

로컬 파일 모드는 `.csv` 또는 `.parquet` 파일을 `data/` 아래에 둔다. 권장 위치:

```text
data/raw/
```

예시:

```text
data/raw/nemotron-personas-usa.parquet
data/raw/nemotron-personas-usa.csv
```

`data/` 밖 경로는 보안상 거부된다.

## 9. Agent Pack 모드

Codex 또는 Claude Code 구독 사용자는 prompt pack을 export하고, 로컬 CLI로 실행한
뒤 결과를 import해서 Markdown/CSV 리포트를 만들 수 있다.

```powershell
uv run python -m src.agent_bridge export --concept examples/agent_bridge_concept.example.json --out outputs/agent-pack-demo --sample-size 10 --audience unisex
powershell -ExecutionPolicy Bypass -File outputs\agent-pack-demo\commands\run-codex.ps1
uv run python -m src.agent_bridge import --pack outputs\agent-pack-demo --results outputs\agent-pack-demo\results\codex --out outputs\agent-report-codex
```

Claude Code는 `commands\run-claude.ps1`을 쓴다.

## 10. 테스트

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run bandit -r src -c pyproject.toml
uv run pip-audit
uv run pre-commit run --all-files
```

테스트는 실제 LLM provider나 Hugging Face endpoint를 호출하지 않는다.
