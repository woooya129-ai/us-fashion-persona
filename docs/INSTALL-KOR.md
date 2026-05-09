# us-fashion-persona 설치 가이드

이 앱은 hosted evaluation service가 아니다. 사용자의 컴퓨터에서 실행되는
local-first Streamlit 앱이고, 사용자가 직접 준비한 API key를 사용한다.

## 1. 필요 조건

- Git
- Python 3.11 이상
- `uv`
- OpenAI, Anthropic, Gemini 중 사용할 provider의 API key
- 필요 시 Hugging Face 접근 권한

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

선택 사항:

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

정적 문서 버튼까지 로컬에서 열고 싶으면 다른 터미널에서 실행한다.

```bash
uv run python -m http.server 8510
```

## 5. API key 설정

실제 API key를 저장소 안에 넣지 마라.

기본 방식은 Streamlit 화면의 password 입력칸에 provider key를 붙여넣는 것이다.
앱은 key 값을 화면에 그대로 보여주거나 저장소에 저장하지 않는다.

반복 실행이 필요하면 저장소 밖에 로컬 환경 파일을 두거나 OS 환경변수를 사용한다.

```bash
mkdir -p ~/secrets/us-fashion
cp .env.example ~/secrets/us-fashion/.env
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\secrets\us-fashion"
Copy-Item .env.example "$HOME\secrets\us-fashion\.env"
```

필요한 값만 설정한다.

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
HF_TOKEN=
```

`GOOGLE_API_KEY`는 Google AI Studio의 Gemini API key 기준이다. Vertex AI key가 아니다.

## 6. 데이터셋

기본 모드는 Hugging Face의 `nvidia/Nemotron-Personas-USA`를 읽는다. 원본
데이터셋은 이 저장소에 포함하지 않는다.

로컬 파일 모드를 쓰려면 `.csv` 또는 `.parquet` 파일을 `data/` 아래에 둔다.
권장 위치는 `data/raw/`다. `data/` 바깥 경로는 보안상 거부된다.

## 7. 검증

```bash
uv run ruff check .
uv run ruff format src tests --check
uv run pytest
uv run bandit -r src -c pyproject.toml
uv run pip-audit --skip-editable
uv run pre-commit run --all-files
```

테스트는 명시적으로 승인된 integration-test 경로가 아닌 이상 실제 LLM provider나
Hugging Face endpoint를 호출하면 안 된다.
