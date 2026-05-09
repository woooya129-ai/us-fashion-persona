# us-fashion-persona Installation Guide

This app is not a hosted evaluation service. It is a local-first Streamlit app
that runs on your machine and uses API keys that you configure yourself.

## 1. Requirements

- Git
- Python 3.11 or newer
- `uv`
- An API key for OpenAI, Anthropic, or Gemini
- Hugging Face access if the persona dataset requires it

Install `uv` from the official documentation if needed.

```text
https://docs.astral.sh/uv/
```

## 2. Clone The Repository

```bash
git clone https://github.com/woooya129-ai/us-fashion-persona.git
cd us-fashion-persona
```

## 3. Install Dependencies

```bash
uv sync --all-extras --dev
```

Optional:

```bash
uv run pre-commit install
```

## 4. Run The App

```bash
uv run streamlit run src/app.py
```

Open:

```text
http://localhost:8501
```

To make the local Docs button work, run this in another terminal:

```bash
uv run python -m http.server 8510
```

## 5. Configure API Keys

Do not put real API keys inside the repository.

The default flow is to paste your provider key into the password field in the
Streamlit UI. The app does not display the key value or save it to the
repository.

For repeated local use, keep a local environment file outside the repository or
use OS environment variables.

```bash
mkdir -p ~/secrets/us-fashion
cp .env.example ~/secrets/us-fashion/.env
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\secrets\us-fashion"
Copy-Item .env.example "$HOME\secrets\us-fashion\.env"
```

Set only the values you need.

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
HF_TOKEN=
```

`GOOGLE_API_KEY` is for the Gemini API key from Google AI Studio, not Vertex AI.

## 6. Dataset

The default mode reads `nvidia/Nemotron-Personas-USA` from Hugging Face. The raw
dataset is not bundled in this repository.

For local file mode, place `.csv` or `.parquet` files under `data/`, preferably
under `data/raw/`. Paths outside `data/` are rejected for safety.

## 7. Checks

```bash
uv run ruff check .
uv run ruff format src tests --check
uv run pytest
uv run bandit -r src -c pyproject.toml
uv run pip-audit --skip-editable
uv run pre-commit run --all-files
```

Tests must not call real LLM providers or Hugging Face endpoints unless an
explicit integration-test path is approved by the maintainer.
