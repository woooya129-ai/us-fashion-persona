---
title: US Fashion Persona
emoji:
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: agpl-3.0
short_description: AI persona screening for US fashion concepts.
datasets:
  - nvidia/Nemotron-Personas-USA
tags:
  - streamlit
  - fashion
  - personas
  - market-research
---

# us-fashion-persona

## Check US Fashion Concepts With AI Personas First

[![Version](https://img.shields.io/badge/version-0.6.2-0F766E)](pyproject.toml)
[![HF Dataset](https://img.shields.io/badge/HF-Dataset-FFD21E?logo=huggingface&logoColor=black)](https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA)
[![GitHub](https://img.shields.io/badge/GitHub-us--fashion--persona-181717?logo=github&logoColor=white)](https://github.com/woooya129-ai/us-fashion-persona)
[![Twin Project](https://img.shields.io/badge/GitHub-k--fashion--persona-181717?logo=github&logoColor=white)](https://github.com/woooya129-ai/k-fashion-persona)
[![Docs](https://img.shields.io/badge/Docs-INSTALL-2563EB?logo=readthedocs&logoColor=white)](docs/INSTALL.md)
[![Korean README](https://img.shields.io/badge/README-Korean-2563EB)](README-KOR.md)
[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-0F766E.svg)](LICENSE)

`us-fashion-persona` is a local-first Streamlit tool for checking US fashion
product concepts before launch or formal research. Enter a product card and
persona filters, then get a Markdown/CSV report with interest reasons,
hesitation points, price burden, and fashion risk signals.

It is not a real purchase-rate, sales, trend, or market-share prediction
service. Use it to narrow hypotheses before surveys, interviews, sales-data
analysis, and expert review.

![us-fashion-persona main screen](docs/assets/us-fashion-persona-screenshot-03.webp)

![us-fashion-persona result screen](docs/assets/us-fashion-persona-screenshot-04.webp)

## At A Glance

| Item | Details |
|---|---|
| Input | Category, price, fit, material, color, season, wearing context, style tone, target hypothesis, product description |
| Panel | Synthetic personas from NVIDIA Nemotron-Personas-USA |
| Filters | Age, sex, US state/territory, occupation, seed, sample size |
| Output | Reaction distribution, interest score, reasons, concerns, price burden, representative card, Markdown/CSV |
| Presets | FAST 50, BALANCE 100, HIGH 300, MAX 1000 personas |
| Advanced | User-entered sample sizes are allowed up to the guardrail |

## Runtime Model

- UI, dataset filtering, sampling, prompt construction, SQLite cache, and
  Markdown/CSV report generation run locally on the user's machine.
- Streamlit API mode sends prompts to the selected provider API server.
- Agent Pack mode exports prompt files and lets a signed-in Codex or Claude
  Code CLI evaluate them outside the app.
- The app does not save API keys. UI-entered keys are used only for the current
  Streamlit session.
- LLM API endpoints are limited to `api_base_url` hosts in
  `config/pricing_config.yaml`. Editing that file changes the allowed host set,
  so review it before shared deployment.
- Public deployments can set `UFPS_REQUIRE_USER_PROVIDER_KEY=1` so visitors
  must enter their own provider key and shared owner LLM keys are not used.

## Installation

Requirements:

- Git
- Python 3.11 or newer
- `uv`
- An API key for your chosen AI provider or a signed-in Codex/Claude Code CLI
- Hugging Face token if needed

Install:

```bash
git clone https://github.com/woooya129-ai/us-fashion-persona.git
cd us-fashion-persona
uv sync --all-extras --dev
```

Full setup guide: [docs/INSTALL.md](docs/INSTALL.md)

## Quick Start

```bash
uv run streamlit run src/app.py
```

Open:

```text
http://localhost:8501
```

## Standard Use

1. Run the Streamlit app.
2. Choose a provider and model.
3. Enter the provider API key.
4. Fill in the product card.
5. Adjust sample size, seed, audience, and persona filters.
6. Check estimated cost and time.
7. Press `ENTER`, then download Markdown or CSV.

For repeated local runs, keep keys in an environment file outside the
repository or in OS environment variables. Do not place or commit a real `.env`
file in the repository root.

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
HF_TOKEN=
```

OpenAI-compatible providers such as Groq, DeepSeek, and Qwen use the
environment variable named by `api_key_env` in `config/pricing_config.yaml`.

## Codex / Claude Code Subscription Mode

Codex and Claude Code subscription users can use Agent Pack mode without
turning those tools into direct in-app API providers. The flow is offline:
export, CLI run, import.

Create an Agent Pack:

```powershell
uv run python -m src.agent_bridge export --concept examples/agent_bridge_concept.example.json --out outputs/agent-pack-demo --sample-size 50 --audience unisex
```

Run with Codex, then import:

```powershell
powershell -ExecutionPolicy Bypass -File outputs\agent-pack-demo\commands\run-codex.ps1
uv run python -m src.agent_bridge import --pack outputs\agent-pack-demo --results outputs\agent-pack-demo\results\codex --out outputs\agent-report-codex
```

Run with Claude Code, then import:

```powershell
powershell -ExecutionPolicy Bypass -File outputs\agent-pack-demo\commands\run-claude.ps1
uv run python -m src.agent_bridge import --pack outputs\agent-pack-demo --results outputs\agent-pack-demo\results\claude --out outputs\agent-report-claude
```

Notes:

- A 50-persona run makes 50 CLI calls. Start with `--sample-size 5` or
  `--sample-size 10`.
- Claude subscription users should use the default `run-claude.ps1`.
  `UFPS_CLAUDE_BARE=1` is for API-key or auth-helper automation.
- Import writes `agent-report.md`, `agent-report.csv`, and
  `normalized-results.jsonl`.

## Data And Statistics

- Default dataset:
  [NVIDIA Nemotron-Personas-USA](https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA)
- Dataset type: synthetic US-context personas, not real-person data
- Dataset license: CC BY 4.0 attribution applies
- Default loading: Hugging Face `datasets` streaming
- Default scan: up to 3000 rows sequentially per run to fill matching personas

Income, assets, and apparel spending are not inferred from individual personas.
Price-burden context comes from the committed U.S. official-statistics snapshot
at `data/public/us_household_context.csv`:

- BLS Consumer Expenditure Survey 2024: Apparel and services spending
- BLS Consumer Expenditure Survey 2024: average income before taxes
- U.S. Census CPS ASEC 2024 HINC-02: median household income by householder age
- Federal Reserve SCF 2022: median and mean family net worth by age group

## Recommended Specs

| Item | Minimum | Recommended |
|---|---:|---:|
| CPU | 2+ cores | 4+ cores |
| RAM | 8GB | 16GB+ |
| Disk space | 5GB+ free | 10-20GB+ free |
| GPU | Not required | Not required |
| Network | Required for HF dataset loading and LLM API calls | Stable broadband recommended |

Large samples usually increase LLM API cost and runtime before RAM becomes the
bottleneck.

## License And Attribution

- Code license: GNU AGPL-3.0-only
- Persona dataset: NVIDIA Nemotron-Personas-USA
- Dataset license: CC BY 4.0 attribution applies
- Statistics context: BLS, U.S. Census, Federal Reserve
- Full notices: [LICENSE](LICENSE), [NOTICE](NOTICE),
  [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)
- Citation format: [CITATION.cff](CITATION.cff)
- Methodology: [docs/METHODOLOGY_AND_RIGHTS.md](docs/METHODOLOGY_AND_RIGHTS.md)

Closed-source commercial use, internal SaaS, redistributed products, or use
cases that cannot adopt AGPL terms may require a separate written commercial
license or dual-license arrangement.

Contact: woooya129 [at] gmail [dot] com

Korea-context twin project:
[k-fashion-persona](https://github.com/woooya129-ai/k-fashion-persona)
