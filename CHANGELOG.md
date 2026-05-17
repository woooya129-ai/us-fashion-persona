# Changelog

## 0.6.2 - 2026-05-18 (Provider expansion and Agent Pack workflow)

- Added Docker/HF Space-ready runtime files: `Dockerfile`, `.dockerignore`,
  and `requirements.txt`.
- Expanded model/provider configuration to cover OpenAI, Anthropic, Google,
  Groq, DeepSeek, and Qwen-style OpenAI-compatible endpoints through
  `config/pricing_config.yaml`.
- Added endpoint and provider-model-id dimensions to cache keys, with legacy
  cache fallback for prior results.
- Added preflight validation before job creation so malformed provider output
  fails before a full paid panel run starts.
- Added `UFPS_REQUIRE_USER_PROVIDER_KEY` handling so shared deployments can
  require visitors to paste their own provider API key.
- Added Agent Pack export/import workflow for Codex and Claude Code CLI users,
  plus an example concept and tests.
- Raised public run guardrails to FAST 50, BALANCE 100, HIGH 300, and MAX 1000
  personas with a default Hugging Face scan cap of 3000 rows.
- Kept USA data boundaries on Nemotron-Personas-USA and U.S. official
  BLS/Census/Federal Reserve economic context.

## 0.5.3 - 2026-05-10 (Attribution and rights positioning)

- Aligned repository structure and file management with the k-fashion-persona
  v0.5.3 twin: root-only duplicate docs removed, install docs kept under
  `docs/`, and local operating files kept out of the public commit surface.
- Split Streamlit UI copy, CSS, assets, and rendering helpers into `src/ui/*`
  and restored `src/app.py` to a thin entry point over `src/orchestrator`.
- Fixed USA orchestration fields to use `state`, `city`, `zipcode`, and
  `price_usd_cents` consistently in prompt payloads.
- Updated pre-commit Bandit hook to a version that supports the configured
  security skip profile.
- Added `data/public/us_household_context.csv` and segment-based U.S. official
  economic context so the USA project can run national or age-reference
  baselines like the Korea twin.
- Updated price-context hashing, prompts, reports, and UI selection to include
  the selected U.S. official-statistics segment.
- Added `CITATION.cff` to make project attribution explicit.
- Added `docs/METHODOLOGY_AND_RIGHTS.md` to document the US pre-screening
  workflow, attribution expectations, commercial adoption boundary, and IP
  positioning.
- Clarified README, commercial-license, and NOTICE references for citation,
  methodology, branding, and commercial adoption.
- Rechecked USA dataset and official aggregate-statistics boundaries:
  NVIDIA Nemotron-Personas-USA, BLS, U.S. Census, and Federal Reserve SCF.
- Updated release labels to `0.5.3`.

## 0.5.2 - 2026-05-10 (US twin alignment)

- Aligned public license and notice structure with k-fashion-persona.
- Kept the USA dataset boundary on NVIDIA Nemotron-Personas-USA.
- Kept consumer spending, income, and asset context on U.S. official aggregate
  sources rather than persona-level inference.
- Added v0.5.x runtime structure notes and explicit Hugging Face token passing.
