# us-fashion-persona Installation Guide

This app is not a hosted evaluation service. It is a local Streamlit app that
runs on your machine and uses API keys that you provide.

## 1. Requirements

- Git
- Python 3.11 or newer
- `uv`
- An API key for your chosen AI provider
- Hugging Face token if needed

`uv` installation docs:

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

To make the README Docs button work locally, run this in another terminal:

```bash
uv run python -m http.server 8510
```

## 5. Enter API Keys

The easiest path is to paste keys into the password fields in the app UI.

Supported key inputs:

- LLM provider API key: the provider for the selected model
- `HF TOKEN`: when Hugging Face access is needed

LLM API endpoints are limited to `api_base_url` hosts registered in
`config/pricing_config.yaml`. Editing that YAML changes the allowed host set, so
treat config changes as code-reviewed changes in shared environments.

## 6. Environment File For Repeated Runs

Do not put real keys inside the repository. For repeated runs, keep a local
environment file outside the repository.

### macOS / Linux

```bash
mkdir -p ~/secrets/us-fashion
cp .env.example ~/secrets/us-fashion/.env
```

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force "$HOME\secrets\us-fashion"
Copy-Item .env.example "$HOME\secrets\us-fashion\.env"
```

Environment file example:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
HF_TOKEN=
```

`GOOGLE_API_KEY` is for the Gemini API key from Google AI Studio, not Vertex AI.
OpenAI-compatible providers such as Groq, DeepSeek, and Qwen use the
environment variable named by `api_key_env` in `pricing_config.yaml`.

Do not place or commit a real `.env` file in the repository root.

For public demos or shared deployments, set:

```env
UFPS_REQUIRE_USER_PROVIDER_KEY=1
```

This prevents fallback to owner-side provider keys and requires visitors to
enter their own provider API key.

## 7. Basic Workflow

1. Choose the LLM provider and model.
2. Enter the provider API key.
3. Enter `HF TOKEN` if needed.
4. Choose the U.S. economic reference segment.
5. Fill in category, price, fit, material, color, season, wearing context,
   style tone, target hypothesis, and product description.
6. Adjust sample size, seed, audience, and filters.
7. Confirm estimated cost and time.
8. Press `ENTER`.
9. Download the Markdown or CSV report.

## 8. Data Location

If you use the default `NVIDIA dataset` mode, you do not need to place the raw
dataset inside the repository. The app reads `nvidia/Nemotron-Personas-USA` from
Hugging Face.

For local file mode, place a `.csv` or `.parquet` file under `data/`.

Recommended location:

```text
data/raw/
```

Examples:

```text
data/raw/nemotron-personas-usa.parquet
data/raw/nemotron-personas-usa.csv
```

Enter a local path like this in the app:

```text
data/raw/nemotron-personas-usa.parquet
```

Paths outside `data/` are rejected for safety.

Optional design assets can be placed at these repository-root-relative paths:

```text
design/hero-skyblue-fabric.png
design/direction-bg.png
```

If the files are missing, the app uses built-in fallback backgrounds and logs
that once.

## 9. Agent Pack Mode

Codex and Claude Code subscription users can export prompts, run them with their
local CLI, and import results back into a report.

```powershell
uv run python -m src.agent_bridge export --concept examples/agent_bridge_concept.example.json --out outputs/agent-pack-demo --sample-size 10 --audience unisex
powershell -ExecutionPolicy Bypass -File outputs\agent-pack-demo\commands\run-codex.ps1
uv run python -m src.agent_bridge import --pack outputs\agent-pack-demo --results outputs\agent-pack-demo\results\codex --out outputs\agent-report-codex
```

Use `commands\run-claude.ps1` for Claude Code results.

## 10. U.S. Statistics

The repository includes a committed public-statistics snapshot.

```text
data/public/us_household_context.csv
```

The snapshot is used for report and prompt economic context.

- BLS 2024 Apparel and services spending
- BLS 2024 average income before taxes
- Census CPS ASEC 2024 HINC-02 median household income by householder age
- Federal Reserve SCF 2022 median and mean family net worth by age group

These values are aggregate statistics. They do not mean an individual persona's
real income, assets, purchasing power, or purchase intent.

## 11. Run Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Security and dependency checks:

```bash
uv run bandit -r src -c pyproject.toml
uv run pip-audit
uv run pre-commit run --all-files
```

Tests do not make real calls to LLM providers or Hugging Face.

## 12. Troubleshooting

### `uv` is not found

Check that `uv` is installed and included in your PATH.

### `http://localhost:8501` does not open

Check that the Streamlit process is still running. If port 8501 is already in
use, Streamlit may show another local URL.

### API key errors

Check the UI field, external environment file, or OS environment variable for
the key you need.

### Hugging Face access errors

The persona dataset may require access permission. If needed, check your
Hugging Face account and token settings.
