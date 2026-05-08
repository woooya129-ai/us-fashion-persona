# US Fashion Persona Screener Installation Guide

This guide explains how to install and run US Fashion Persona Screener locally.

This app is not a hosted evaluation service. It is a local-first Streamlit app that runs on your machine and uses API keys that you configure yourself.

## 1. Requirements

- Git
- Python 3.11 or newer
- `uv`
- Gitleaks for pre-commit secret scanning
- An API key for your chosen LLM provider
- Hugging Face access if the persona dataset requires it

If you do not have `uv`, install it from the official documentation.

```text
https://docs.astral.sh/uv/
```

## 2. Clone the Repository

```bash
git clone https://github.com/woooya129-ai/us-fashion-persona.git
cd us-fashion-persona
```

## 3. Install Dependencies

```bash
uv sync --all-extras --dev
```

To enable pre-commit hooks:

```bash
gitleaks version
uv run pre-commit install
```

## 4. Configure API Keys

Do not put real API keys inside the repository.

The default flow is to run the Streamlit app and paste your key into the API key field on the screen. The field uses password input, and the app does not display the key value or save it to the repository.

```bash
uv run streamlit run src/app.py
```

Open `http://localhost:8501` in your browser, then paste the key into the API key field.

For repeated local use, keep a local environment file outside the repository or use OS environment variables.

### macOS / Linux

```bash
mkdir -p ~/secrets/us-fashion
cp .env.example ~/secrets/us-fashion/.env
```

Then edit:

```text
~/secrets/us-fashion/.env
```

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force "$HOME\secrets\us-fashion"
Copy-Item .env.example "$HOME\secrets\us-fashion\.env"
```

Then edit:

```text
$HOME\secrets\us-fashion\.env
```

Required variables depend on the provider you use.

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
HF_TOKEN=
```

You can also provide these values through shell environment variables.

Do not place a real `.env` file in the repository root.

## 5. Run the Local App

```bash
uv run streamlit run src/app.py
```

Open this address in your browser:

```text
http://localhost:8501
```

## 6. Dataset Location

If you use the default `NVIDIA dataset` mode, you do not need to place the raw dataset inside the repository. The app reads `nvidia/Nemotron-Personas-USA` from Hugging Face. If access is required, configure `HF_TOKEN` through your local environment file or shell environment variables outside the repository.

If you use local file mode, place a `.csv` or `.parquet` file under the repository's `data/` directory. The recommended location is:

```text
data/raw/
```

Examples:

```text
data/raw/nemotron-personas-usa.parquet
data/raw/nemotron-personas-usa.csv
```

In the app's `Local file path` field, enter a path such as:

```text
data/raw/nemotron-personas-usa.parquet
```

Paths outside `data/` are rejected for safety. Do not include raw data, cache, outputs, or logs in the public repository.

## 7. What You Enter in the App

The app asks for a fashion product concept in product-card form.

Typical fields:

- Category
- Price
- Season
- Wearing occasion
- Style tone
- Fit / silhouette
- Material
- Color
- Target hypothesis
- Brand message
- Product description

Fields such as fit, material, and color are free text. Short phrases work best.

Examples:

| Field | Examples |
| --- | --- |
| Fit / silhouette | oversized, regular fit, slim fit, cropped, wide-leg, straight, A-line, H-line |
| Material | cotton, wool blend, denim, nylon, faux leather, rib knit, sheer fabric |
| Color | black, ivory, charcoal, beige, sky blue, washed denim, muted pink |
| Style tone | minimal, casual, street, feminine, classic, sporty, romantic |
| Occasion | commute, weekend, date, travel, wedding guest, daily wear, office casual |

## 8. Run Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

To run security and dependency checks:

```bash
uv run bandit -r src -c pyproject.toml
uv run pip-audit
uv run pre-commit run --all-files
```

Tests do not make real calls to OpenAI, Anthropic, Gemini, or Hugging Face.

## 9. Important Limits

- This app is not real consumer research.
- It does not predict real purchase rate, sales, market share, or fashion trends.
- Outputs are synthetic-persona-based hypotheses for early concept exploration.
- Final decisions should be combined with real research, sales data, and qualified human judgment.

## 10. Troubleshooting

### `uv` is not found

Check that `uv` is installed and that its installation path is included in your PATH.

### `http://localhost:8501` does not open

Check that the Streamlit process is still running. If port 8501 is already in use, Streamlit may show a different local URL.

### API key errors

Check your local environment file or shell environment variables. Do not commit real keys to the repository.

### Hugging Face access errors

The persona dataset may require access permissions. If needed, check your Hugging Face account and token settings.
