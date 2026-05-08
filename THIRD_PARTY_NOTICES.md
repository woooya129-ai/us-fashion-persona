# Third-Party Notices

This file lists third-party datasets, libraries, and materials referenced by
US Fashion Persona Screener. It is an attribution and notice file, not a license
override.

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
