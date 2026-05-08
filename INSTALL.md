# US Fashion Persona Screener 설치 및 실행 가이드

이 문서는 US Fashion Persona Screener를 로컬에서 설치하고 실행하는 방법을 설명합니다.

이 앱은 hosted evaluation service가 아닙니다. 사용자의 컴퓨터에서 실행되는 local-first Streamlit 앱이며, 사용자가 직접 준비한 API key를 사용합니다.

## 1. 필요 조건

- Git
- Python 3.11 이상
- `uv`
- Gitleaks (pre-commit secret scan)
- 사용할 LLM provider의 API key
- 필요 시 Hugging Face 접근 권한

`uv`가 없다면 공식 설치 문서를 참고해 설치하세요.

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

pre-commit hook을 사용할 경우:

```bash
gitleaks version
uv run pre-commit install
```

## 4. API key 설정

실제 API key를 저장소 안에 넣지 마세요.

기본 방식은 Streamlit 앱 실행 후 화면의 API key 입력칸에 붙여넣는 것입니다. 입력칸은 password 타입이고, 키 값을 화면에 그대로 보여주거나 저장소에 저장하지 않습니다.

```bash
uv run streamlit run src/app.py
```

브라우저에서 `http://localhost:8501`을 연 뒤 API key 입력칸에 키를 넣습니다.

반복 실행이 필요하면 저장소 밖에 로컬 환경 파일을 두거나 OS 환경변수로 설정합니다.

### macOS / Linux

```bash
mkdir -p ~/secrets/us-fashion
cp .env.example ~/secrets/us-fashion/.env
```

그다음 아래 파일을 편집합니다.

```text
~/secrets/us-fashion/.env
```

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force "$HOME\secrets\us-fashion"
Copy-Item .env.example "$HOME\secrets\us-fashion\.env"
```

그다음 아래 파일을 편집합니다.

```text
$HOME\secrets\us-fashion\.env
```

필요한 변수는 사용하는 provider에 따라 달라질 수 있습니다.

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
HF_TOKEN=
```

셸 환경변수로 직접 지정해도 됩니다.

저장소 root에 실제 `.env` 파일을 두지 마세요.

## 5. 로컬 앱 실행

```bash
uv run streamlit run src/app.py
```

브라우저에서 아래 주소를 엽니다.

```text
http://localhost:8501
```

## 6. 데이터셋 위치

기본값인 `NVIDIA dataset` 모드를 쓰면 원본 데이터셋을 저장소에 직접 넣지 않아도 됩니다. 앱이 Hugging Face의 `nvidia/Nemotron-Personas-USA`를 읽습니다. 접근이 필요한 경우에는 저장소 밖 환경 파일이나 환경변수에 `HF_TOKEN`을 설정합니다.

로컬 파일 모드를 쓰는 경우에는 `.csv` 또는 `.parquet` 파일을 저장소의 `data/` 하위에 둬야 합니다. 권장 위치는 다음입니다.

```text
data/raw/
```

예시:

```text
data/raw/nemotron-personas-usa.parquet
data/raw/nemotron-personas-usa.csv
```

앱의 `로컬 파일 경로` 입력칸에는 다음처럼 입력합니다.

```text
data/raw/nemotron-personas-usa.parquet
```

`data/` 바깥 경로는 보안상 거부됩니다. 원본 데이터, cache, outputs, logs는 공개 저장소에 포함하지 않습니다.

## 7. 앱에서 입력하는 내용

앱은 패션 제품 컨셉을 제품 카드 형태로 입력받습니다.

대표 입력 항목:

- 카테고리
- 가격
- 시즌
- 착용 상황
- 스타일 톤
- 핏 / 실루엣
- 소재
- 컬러
- 타깃 가설
- 브랜드 메시지
- 제품 설명

핏, 소재, 컬러 같은 항목은 자유 입력입니다. 짧은 문구가 가장 잘 맞습니다.

예시:


| 항목      | 예시                                       |
| ------- | ---------------------------------------- |
| 핏 / 실루엣 | 오버핏, 레귤러핏, 슬림핏, 크롭, 와이드, 스트레이트, A라인, H라인 |
| 소재      | 코튼, 울 혼방, 데님, 나일론, 페이크 레더, 골지 니트, 시어 소재  |
| 컬러      | 블랙, 아이보리, 차콜, 베이지, 스카이블루, 워싱 데님, 뮤트 핑크   |
| 스타일 톤   | 미니멀, 캐주얼, 스트리트, 페미닌, 클래식, 스포티, 로맨틱       |
| 착용 상황   | 출근, 주말, 데이트, 여행, 하객룩, 데일리, 오피스 캐주얼       |


## 8. 테스트 실행

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

보안/의존성 검사까지 실행하려면:

```bash
uv run bandit -r src -c pyproject.toml
uv run pip-audit
uv run pre-commit run --all-files
```

테스트는 실제 OpenAI, Anthropic, Gemini, Hugging Face API를 호출하지 않습니다.

## 9. 주의 사항

- 이 앱은 실제 소비자 조사 도구가 아닙니다.
- 실제 구매율, 매출, 시장점유율, 유행을 예측하지 않습니다.
- 출력은 합성 페르소나 기반의 사전 탐색용 가설입니다.
- 최종 의사결정은 실제 조사, 판매 데이터, 전문가 판단과 함께 해야 합니다.

## 10. 문제 해결

### `uv` 명령을 찾을 수 없음

`uv`가 설치되어 있는지 확인하고, 설치 경로가 PATH에 포함되어 있는지 확인하세요.

### `http://localhost:8501`이 열리지 않음

Streamlit 실행 명령이 아직 실행 중인지 확인하세요. 포트가 이미 사용 중이면 Streamlit이 다른 포트를 안내할 수 있습니다.

### API key 오류가 남

로컬 환경 파일 또는 셸 환경변수에 필요한 key가 설정되어 있는지 확인하세요. 실제 key를 저장소 안에 commit하지 마세요.

### Hugging Face 접근 오류가 남

사용하는 persona dataset이 접근 권한을 요구할 수 있습니다. 필요한 경우 Hugging Face 계정과 token 설정을 확인하세요.
