# Third-Party Notices

This file lists third-party datasets, libraries, statistics, and materials
referenced by us-fashion-persona. It is an attribution and notice file, not a
license override.

## NVIDIA Nemotron-Personas-USA

- Provider: NVIDIA Corporation
- Source: Hugging Face dataset card, `nvidia/Nemotron-Personas-USA`
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Use in this project: documented dataset loading and synthetic persona-based
  evaluation workflow
- Dataset bundled in this repository: No
- Changes to dataset content included in this repository: None
- Endorsement: No endorsement by NVIDIA is implied

Attribution statement:

> NVIDIA Nemotron-Personas-USA is provided by NVIDIA Corporation and licensed
> under CC BY 4.0. This project may reference the dataset for synthetic
> persona-based evaluation workflows. This project is not affiliated with or
> endorsed by NVIDIA.

If any dataset sample, transformed row, generated persona text, or derived
artifact is later added to the public repository, update this section with the
exact file path, transformation method, and change statement before release.

## U.S. Official Aggregate Statistics

- Providers: U.S. Bureau of Labor Statistics (BLS), U.S. Census Bureau, and
  Board of Governors of the Federal Reserve System
- Use in this project: report and prompt context based on apparel and services
  spending, household income, family net worth, and aggregate economic context
- Not used for: direct inference of individual persona income, assets, or real
  purchasing power
- Data bundled in this repository: No separate raw data files. The app uses
  stable aggregate context constants in `src/economic_context.py`.
- Source pages used for the committed context:
  - BLS Consumer Expenditures 2024 news release and annual tables:
    https://www.bls.gov/news.release/cesan.nr0.htm
  - U.S. Census Bureau, Income in the United States: 2024:
    https://www.census.gov/library/publications/2025/demo/p60-286.html
  - Federal Reserve, Changes in U.S. Family Finances from 2019 to 2022:
    https://www.federalreserve.gov/publications/october-2023-changes-in-us-family-finances-from-2019-to-2022.htm

## Direct Python Dependencies

The public source repository lists dependencies in `pyproject.toml` and
`uv.lock`. These packages are not relicensed by this project.

| Package | Role | License metadata observed in local environment |
|---|---|---|
| `streamlit` | Local UI | Apache-2.0 |
| `pydantic` | Data validation | MIT |
| `pyyaml` | YAML parsing | MIT |
| `python-dotenv` | Environment loading helper | BSD-3-Clause |
| `httpx` | HTTP client | BSD-3-Clause |
| `pandas` | Dataframe processing | BSD-3-Clause |
| `datasets` | Hugging Face dataset loading | Apache-2.0 |
| `pyarrow` | Parquet support | Apache-2.0 |
| `pytest` | Tests | MIT |
| `respx` | HTTPX mocking in tests | BSD-3-Clause |
| `ruff` | Lint and format checks | MIT |
| `bandit` | Security lint | Apache-2.0 |
| `pip-audit` | Dependency vulnerability audit | Apache-2.0 |
| `pre-commit` | Local quality hooks | MIT |

Before publishing a binary distribution, container image, or hosted derivative,
run a fresh dependency license review and update this file if any dependency
requires additional notices.

## External Services

This project can be configured by the user to call third-party LLM providers or
Hugging Face from the user's own local environment. API keys and tokens are not
bundled with this repository. Each provider's own terms and pricing apply.
