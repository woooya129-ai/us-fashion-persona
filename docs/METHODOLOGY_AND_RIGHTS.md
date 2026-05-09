# Methodology And Rights Positioning

This document explains how us-fashion-persona should be attributed, what the
public project claims, and what it does not claim. It is not legal advice.

## Method Outline

us-fashion-persona narrows early fashion concept screening into a repeatable
local workflow:

1. A user enters a structured product card: category, price, fit, material,
   color, season, wearing context, style tone, target hypothesis, and brand
   message.
2. The app builds a synthetic persona panel from NVIDIA
   Nemotron-Personas-USA with deterministic sampling and filters.
3. Official U.S. aggregate-statistics context is loaded from the committed
   `data/public/us_household_context.csv` snapshot. The selected national or
   age-reference segment is added as reference context, not as individual
   persona income, assets, or purchase power.
4. The selected LLM provider evaluates the concept against the prompt schema.
5. The result payload is parsed, validated, cached, aggregated, and exported as
   Markdown/CSV reports.

The tool is a pre-screening and hypothesis-aid workflow. It is not a real
consumer prediction model, purchase-rate predictor, sales predictor, or market
share predictor.

## U.S. Data Boundary

The USA version uses:

- Persona dataset: NVIDIA Nemotron-Personas-USA
- Consumer spending context: BLS Consumer Expenditure Survey 2024, annual
  Apparel and services by national baseline or age of reference person
- Income context: BLS 2024 average income before taxes and U.S. Census CPS ASEC
  2024 HINC-02 median household income by national baseline or age of
  householder
- Asset context: Federal Reserve Survey of Consumer Finances 2022 median and
  mean family net worth by national baseline or reference-person age group

These are aggregate reference statistics. They do not mean that any synthetic
persona has that income, those assets, or that purchasing power.

## What The Public Project Protects

The public repository is designed to protect concrete expression and execution,
not to overclaim ownership of an abstract idea.

- Source code is licensed under GNU AGPL-3.0-only.
- Documentation, report wording, prompt files, UI copy, and structured workflow
  descriptions are project materials that should be attributed when reused.
- The project name, official repository, official website, and branding are
  separate from the source-code license. See `docs/BRANDING_POLICY.md`.
- `CITATION.cff` gives a stable citation format for academic, portfolio, and
  business references.
- Commercial or closed-source adoption can be handled through a separate
  written commercial license or dual-license arrangement.

## What The Public Project Does Not Claim

This repository does not claim exclusive ownership of the abstract idea of
using LLMs, synthetic personas, or virtual panels for fashion concept screening.
Copyright generally protects concrete expression, not abstract ideas, methods,
or business concepts.

Independent implementations that do not copy this repository's protected code,
documentation, prompts, reports, UI copy, branding, or other protectable
expression may raise different legal questions. Those questions should be
handled under applicable IP, contract, unfair-competition, patent, trademark,
and trade-secret rules.

## Commercial Adoption Boundary

Research, personal learning, and open-source use are welcome under the public
AGPL-3.0-only license terms.

Contact the copyright holder before using this project in:

- closed-source products
- internal SaaS or hosted screening workflows
- redistributed products
- paid consulting or vendor workflows that embed this code, documentation,
  prompt structure, report structure, or official project branding
- cases where AGPL-3.0-only obligations cannot be accepted

Commercial discussions may cover source-code use, documentation use, official
branding permission, integration support, private benchmarks, private prompt
variants, or other non-public know-how delivered under a written agreement.

## Attribution

When referring to the project, use:

> us-fashion-persona, created by Woody Kim / woooya129-ai.
> https://github.com/woooya129-ai/us-fashion-persona

For formal citation, use `CITATION.cff`.

Do not present a fork, hosted demo, derivative workflow, or consulting service
as the official us-fashion-persona project unless written permission is granted.

## Patent, Trademark, And Trade-Secret Notes

If a specific technical method becomes important enough to protect, patent
counsel should review it before further technical disclosure. A patent claim
would need concrete technical features, not only the broad idea of synthetic
persona screening.

Trademark protection may be considered for the official project name or a more
distinctive future product name. This repository's current branding policy is a
public use policy, not a trademark registration notice.

Non-public benchmarks, private prompt variants, customer research material,
pricing playbooks, and deployment playbooks should stay out of the public
repository if they are meant to remain confidential know-how.
