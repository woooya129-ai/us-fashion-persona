# Changelog

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
