# Contributing

By submitting a pull request, patch, issue attachment, or other contribution,
you agree that your contribution is licensed under the GNU Affero General Public
License v3.0 only, the same license used by this project.

SPDX-License-Identifier: AGPL-3.0-only

## Contribution Rights

Only submit material that you have the right to contribute. Do not submit code,
data, prompts, images, documentation, or generated output copied from a source
whose license is incompatible with AGPL-3.0-only or with this repository's
public release policy.

## Do Not Submit

Do not submit:

- API keys, tokens, passwords, private keys, or credentials
- `.env` files or local secret files
- private user data, private research data, or real customer material
- raw LLM responses from private runs
- bundled NVIDIA dataset rows or transformed dataset samples unless a maintainer
  explicitly requests them and THIRD_PARTY_NOTICES.md is updated
- non-public planning docs, private operational logs, release reviews, or local machine
  paths
- claims that the tool predicts real purchase rate, real sales outcome, market
  share, trend performance, or real consumer taste

## Project Scope

This project is a local-first synthetic persona pre-screening tool for US fashion
product concepts. Contributions should preserve that scope.

The maintainer may decline changes that conflict with the project positioning,
licensing, branding policy, data boundary, or public-release safety rules.

## Local Checks

Run these checks before opening a pull request:

```bash
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run bandit -r src -c pyproject.toml
uv run pip-audit
uv run pre-commit run --all-files
```

Tests must not call real LLM providers or Hugging Face endpoints unless an
explicit integration-test path is approved by the maintainer.

## Branding

Do not present a fork, demo, hosted service, or derivative as the official
project. See BRANDING_POLICY.md.

## Third-Party Notices

If a contribution adds or changes third-party material, update
THIRD_PARTY_NOTICES.md in the same pull request.
