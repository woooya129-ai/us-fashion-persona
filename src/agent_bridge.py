# SPDX-License-Identifier: AGPL-3.0-only
"""Agent Pack export/import for Codex and Claude Code subscription CLI users."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.app_config import DEFAULT_HF_MAX_SCAN_ROWS, DEFAULT_PRICE_CONTEXT_VERSION
from src.cache import compute_concept_hash, compute_price_context_hash
from src.data_loader import DEFAULT_HF_DATASET_ID, DEFAULT_SPLIT
from src.economic_context import (
    BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS,
    DEFAULT_REFERENCE_SEGMENT_ID,
    build_price_context,
    economic_baseline_hash_payload,
)
from src.orchestrator import (
    _load_and_sample,
    _persona_attributes,
    build_persona_payloads,
    build_run_report,
)
from src.persona_filter import PersonaFilter
from src.persona_normalizer import Persona
from src.prompt_builder import PROMPT_VERSION, SCHEMA_VERSION
from src.result_parser import EvaluationResult, validate_evaluation_payload

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "concept_eval_ko_v0_3.md"
AGENT_BRIDGE_VERSION = "agent-pack-v0_1"
MANIFEST_NAME = "manifest.json"
EVALUATION_RESULT_KEYS: frozenset[str] = frozenset(
    {
        "persona_id",
        "sentiment",
        "interest_score",
        "price_burden",
        "main_reasons",
        "main_concerns",
        "confidence_note",
    }
)


@dataclass(frozen=True)
class AgentPackSummary:
    pack_dir: Path
    prompt_count: int
    sample_size: int
    matched_count_before_sample: int


@dataclass(frozen=True)
class AgentImportSummary:
    output_dir: Path
    success_count: int
    parse_failed_count: int
    report_markdown_path: Path
    report_csv_path: Path


def _utc_now_iso8601_z() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return normalized.strip("-")[:80] or "persona"


def _sex_filter_for_audience(audience: str) -> frozenset[str]:
    if audience == "womenswear":
        return frozenset({"F"})
    if audience == "menswear":
        return frozenset({"M"})
    return frozenset()


def _normalize_concept(raw: dict[str, Any]) -> dict[str, Any]:
    concept_text = str(raw.get("concept_text") or raw.get("description") or "").strip()
    category = str(raw.get("category") or "").strip()
    project_name = str(raw.get("project_name") or "us-fashion-persona-agent-pack").strip()
    price_raw = raw.get("product_price_usd_cents", raw.get("price_usd_cents", 0))

    if not category:
        raise ValueError("concept.category is required")
    if not concept_text:
        raise ValueError("concept.concept_text is required")

    try:
        product_price_usd_cents = int(price_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("concept.product_price_usd_cents must be an integer") from exc
    if product_price_usd_cents <= 0:
        raise ValueError("concept.product_price_usd_cents must be positive")

    return {
        "project_name": project_name,
        "category": category,
        "product_price_usd_cents": product_price_usd_cents,
        "concept_text": concept_text,
        "target_hypothesis": str(raw.get("target_hypothesis") or "").strip(),
    }


def _make_hashes(concept: dict[str, Any], price_context: dict[str, Any]) -> dict[str, str]:
    concept_hash = compute_concept_hash(
        concept["concept_text"],
        concept["category"],
        concept["product_price_usd_cents"],
    )
    price_context_hash = compute_price_context_hash(
        source=str(price_context.get("source", "us_official")),
        period=(
            f"{price_context.get('period', 'bls_2024+census_2024+scf_2022')}:"
            f"{price_context.get('reference_segment_id', DEFAULT_REFERENCE_SEGMENT_ID)}"
        ),
        denominator_usd_cents=int(
            price_context.get(
                "denominator_usd_cents",
                BLS_2024_ANNUAL_APPAREL_SERVICES_USD_CENTS,
            )
        ),
        price_context_version=DEFAULT_PRICE_CONTEXT_VERSION,
        extra_context=economic_baseline_hash_payload(price_context),
    )
    return {"concept_hash": concept_hash, "price_context_hash": price_context_hash}


def _combined_agent_prompt(payload: dict[str, Any]) -> str:
    prompt = payload["prompt"]
    schema_hint = "schema/evaluation_result.schema.json"
    return "\n".join(
        [
            "# us-fashion-persona Agent Evaluation",
            "",
            "Return exactly one JSON object matching this pack's EvaluationResult schema.",
            f"Schema path: {schema_hint}",
            f"Expected persona_id: {payload['persona_id']}",
            "",
            "Do not include markdown fences, commentary, tool calls, or extra keys.",
            "",
            "## System",
            prompt["system"],
            "",
            "## Developer",
            prompt["developer"],
            "",
            "## User",
            prompt["user"],
            "",
        ]
    )


def _write_command_scripts(pack_dir: Path) -> None:
    commands_dir = pack_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    codex_script = r"""$ErrorActionPreference = "Stop"
$PackRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PromptDir = Join-Path $PackRoot "prompts"
$SchemaPath = Join-Path $PackRoot "schema\evaluation_result.schema.json"
$OutDir = Join-Path $PackRoot "results\codex"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

foreach ($Prompt in Get-ChildItem -LiteralPath $PromptDir -Filter "*.md" | Sort-Object Name) {
  $OutPath = Join-Path $OutDir ($Prompt.BaseName + ".json")
  Write-Host "Codex evaluating $($Prompt.Name)"
  Get-Content -Raw -LiteralPath $Prompt.FullName |
    codex exec - --skip-git-repo-check --ephemeral --output-schema $SchemaPath -o $OutPath
}

Write-Host "Done. Import results from $OutDir"
"""
    claude_script = r"""$ErrorActionPreference = "Stop"
$PackRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PromptDir = Join-Path $PackRoot "prompts"
$SchemaPath = Join-Path $PackRoot "schema\evaluation_result.schema.json"
$SchemaText = Get-Content -Raw -LiteralPath $SchemaPath
$OutDir = Join-Path $PackRoot "results\claude"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Instruction = "Use the full us-fashion-persona evaluation prompt from stdin. " +
  "Return only the validated JSON object."
$ClaudeArgs = @(
  "-p",
  $Instruction,
  "--output-format",
  "json",
  "--json-schema",
  $SchemaText,
  "--no-session-persistence"
)
if ($env:UFPS_CLAUDE_BARE -eq "1") {
  $ClaudeArgs = @("--bare") + $ClaudeArgs
}

foreach ($Prompt in Get-ChildItem -LiteralPath $PromptDir -Filter "*.md" | Sort-Object Name) {
  $OutPath = Join-Path $OutDir ($Prompt.BaseName + ".json")
  Write-Host "Claude evaluating $($Prompt.Name)"
  $RawOut = Get-Content -Raw -LiteralPath $Prompt.FullName |
    & claude @ClaudeArgs
  $RawOut | Set-Content -NoNewline -Encoding UTF8 -LiteralPath $OutPath
}

Write-Host "Done. Import results from $OutDir"
"""
    (commands_dir / "run-codex.ps1").write_text(codex_script, encoding="utf-8")
    (commands_dir / "run-claude.ps1").write_text(claude_script, encoding="utf-8")


def write_agent_pack(
    *,
    output_dir: Path,
    concept: dict[str, Any],
    personas: Iterable[Persona],
    price_context: dict[str, Any],
    dataset: dict[str, Any],
    sample: dict[str, Any],
    model_label: str = "agent-cli",
) -> AgentPackSummary:
    output_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = output_dir / "prompts"
    input_dir = output_dir / "input"
    schema_dir = output_dir / "schema"
    results_dir = output_dir / "results"
    for directory in (prompts_dir, input_dir, schema_dir, results_dir):
        directory.mkdir(parents=True, exist_ok=True)

    concept = _normalize_concept(concept)
    persona_rows = list(personas)
    price_context = dict(price_context)
    hashes = _make_hashes(concept, price_context)
    model = {
        "provider": "agent_bridge",
        "model_name": model_label,
        "temperature": 0.0,
        "pricing": None,
    }
    payloads = build_persona_payloads(
        persona_rows,
        concept,
        model,
        price_context,
        hashes,
        PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8"),
    )

    persona_attributes = {
        persona.persona_id: _persona_attributes(persona) for persona in persona_rows
    }
    _write_json(schema_dir / "evaluation_result.schema.json", EvaluationResult.model_json_schema())
    _write_json(input_dir / "concept.json", concept)
    _write_json(input_dir / "price_context.json", price_context)
    _write_json(input_dir / "persona_attributes.json", persona_attributes)

    prompt_index_rows: list[dict[str, str]] = []
    prompts_jsonl = input_dir / "prompts.jsonl"
    with prompts_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for index, payload in enumerate(payloads, start=1):
            filename = f"{index:04d}_{_safe_filename(str(payload['persona_id']))}.md"
            prompt_path = prompts_dir / filename
            prompt_text = _combined_agent_prompt(payload)
            prompt_path.write_text(prompt_text, encoding="utf-8", newline="\n")
            row = {
                "persona_id": str(payload["persona_id"]),
                "prompt_file": f"prompts/{filename}",
            }
            prompt_index_rows.append(row)
            handle.write(json.dumps({**row, "prompt": prompt_text}, ensure_ascii=False) + "\n")

    manifest = {
        "agent_bridge_version": AGENT_BRIDGE_VERSION,
        "created_at": _utc_now_iso8601_z(),
        "project_name": concept["project_name"],
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "sample": sample,
        "hashes": hashes,
        "paths": {
            "concept": "input/concept.json",
            "price_context": "input/price_context.json",
            "persona_attributes": "input/persona_attributes.json",
            "prompts_jsonl": "input/prompts.jsonl",
            "schema": "schema/evaluation_result.schema.json",
        },
        "prompt_count": len(payloads),
        "prompts": prompt_index_rows,
    }
    _write_json(output_dir / MANIFEST_NAME, manifest)
    _write_command_scripts(output_dir)

    matched_count = int(sample.get("matched_count_before_sample", len(persona_rows)))
    return AgentPackSummary(
        pack_dir=output_dir,
        prompt_count=len(payloads),
        sample_size=len(persona_rows),
        matched_count_before_sample=matched_count,
    )


def export_agent_pack(
    *,
    concept_path: Path,
    output_dir: Path,
    sample_size: int,
    sampling_seed: int = 42,
    source: str = "huggingface",
    dataset_id: str = DEFAULT_HF_DATASET_ID,
    split: str = DEFAULT_SPLIT,
    revision: str | None = None,
    local_path: str = "",
    product_audience: str = "unisex",
    reference_segment_id: str = DEFAULT_REFERENCE_SEGMENT_ID,
    max_scan_rows: int = DEFAULT_HF_MAX_SCAN_ROWS,
    model_label: str = "agent-cli",
) -> AgentPackSummary:
    raw_concept = json.loads(concept_path.read_text(encoding="utf-8"))
    concept = _normalize_concept(raw_concept)
    price_context = build_price_context(
        int(concept["product_price_usd_cents"]),
        reference_segment_id=reference_segment_id,
    )
    dataset = (
        {
            "source": "huggingface",
            "dataset_id": dataset_id,
            "split": split,
            "revision": revision,
        }
        if source == "huggingface"
        else {"source": "local", "local_path": local_path}
    )
    sample: dict[str, Any] = {
        "sample_size": int(sample_size),
        "sampling_seed": int(sampling_seed),
        "filter": PersonaFilter(sex=_sex_filter_for_audience(product_audience)),
        "max_scan_rows": int(max_scan_rows),
    }
    _loaded, sampled = _load_and_sample(dataset, sample)
    if not sampled.rows:
        raise RuntimeError("No personas matched the export filters.")
    sample_manifest = {
        "sample_size": sampled.sample_size,
        "requested_sample_size": int(sample_size),
        "sampling_seed": sampled.sampling_seed,
        "product_audience": product_audience,
        "max_scan_rows": int(max_scan_rows),
        "matched_count_before_sample": sampled.matched_count_before_sample,
    }
    return write_agent_pack(
        output_dir=output_dir,
        concept=concept,
        personas=sampled.rows,
        price_context=price_context,
        dataset=dataset,
        sample=sample_manifest,
        model_label=model_label,
    )


def _extract_json_objects(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidates.append(text[start : index + 1])
                start = None
    return candidates


def _json_documents_from_text(text: str) -> list[Any]:
    stripped = text.strip().lstrip("\ufeff")
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return parsed
    if parsed is not None:
        return [parsed]

    documents: list[Any] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            documents.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if documents:
        return documents

    for candidate in _extract_json_objects(stripped):
        try:
            documents.append(json.loads(candidate))
        except json.JSONDecodeError:
            continue
    return documents


def _coerce_evaluation_payload(value: Any, depth: int = 0) -> dict[str, Any] | None:
    if depth > 5:
        return None
    if isinstance(value, dict):
        if EVALUATION_RESULT_KEYS.issubset(value):
            return value
        for key in (
            "structured_output",
            "result",
            "response",
            "output",
            "content",
            "text",
            "message",
        ):
            if key not in value:
                continue
            coerced = _coerce_evaluation_payload(value[key], depth + 1)
            if coerced is not None:
                return coerced
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                coerced = _coerce_evaluation_payload(nested, depth + 1)
                if coerced is not None:
                    return coerced
        return None
    if isinstance(value, list):
        for item in value:
            coerced = _coerce_evaluation_payload(item, depth + 1)
            if coerced is not None:
                return coerced
        return None
    if isinstance(value, str):
        for document in _json_documents_from_text(value):
            coerced = _coerce_evaluation_payload(document, depth + 1)
            if coerced is not None:
                return coerced
    return None


def _iter_result_documents(results_path: Path) -> Iterable[Any]:
    paths: list[Path]
    if results_path.is_dir():
        paths = sorted(
            path
            for path in results_path.rglob("*")
            if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".txt"}
        )
    else:
        paths = [results_path]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        yield from _json_documents_from_text(text)


def import_agent_results(
    *,
    pack_dir: Path,
    results_path: Path,
    output_dir: Path,
) -> AgentImportSummary:
    manifest = json.loads((pack_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    paths = manifest["paths"]
    persona_attributes = json.loads(
        (pack_dir / paths["persona_attributes"]).read_text(encoding="utf-8")
    )
    price_context = json.loads((pack_dir / paths["price_context"]).read_text(encoding="utf-8"))

    rows_by_persona: dict[str, dict[str, Any]] = {}
    parse_failed_count = 0
    for document in _iter_result_documents(results_path):
        payload = _coerce_evaluation_payload(document)
        if payload is None:
            parse_failed_count += 1
            continue
        try:
            result = validate_evaluation_payload(payload)
        except ValidationError:
            parse_failed_count += 1
            continue
        rows_by_persona.setdefault(
            result.persona_id,
            {
                "persona_id": result.persona_id,
                "status": "success",
                "error_type": None,
                "response_json": result.model_dump_json(),
                "latency_ms": None,
            },
        )

    result_rows = list(rows_by_persona.values()) + [
        {
            "persona_id": f"parse_failed_{index}",
            "status": "parse_failed",
            "error_type": "agent_result_parse_failed",
            "response_json": None,
            "latency_ms": None,
        }
        for index in range(parse_failed_count)
    ]
    run_report = build_run_report(result_rows, persona_attributes, price_context)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_md_path = output_dir / "agent-report.md"
    report_csv_path = output_dir / "agent-report.csv"
    normalized_path = output_dir / "normalized-results.jsonl"
    report_md_path.write_text(run_report.report_markdown, encoding="utf-8")
    report_csv_path.write_text(run_report.report_csv, encoding="utf-8")
    with normalized_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in result_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    return AgentImportSummary(
        output_dir=output_dir,
        success_count=len(rows_by_persona),
        parse_failed_count=parse_failed_count,
        report_markdown_path=report_md_path,
        report_csv_path=report_csv_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.agent_bridge",
        description="Export/import us-fashion-persona Agent Packs for Codex and Claude Code.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Create an Agent Pack.")
    export_parser.add_argument("--concept", required=True, type=Path)
    export_parser.add_argument("--out", required=True, type=Path)
    export_parser.add_argument("--sample-size", type=int, default=50)
    export_parser.add_argument("--seed", type=int, default=42)
    export_parser.add_argument("--source", choices=("huggingface", "local"), default="huggingface")
    export_parser.add_argument("--dataset-id", default=DEFAULT_HF_DATASET_ID)
    export_parser.add_argument("--split", default=DEFAULT_SPLIT)
    export_parser.add_argument("--revision")
    export_parser.add_argument("--local-path", default="")
    export_parser.add_argument(
        "--audience",
        choices=("womenswear", "menswear", "unisex"),
        default="unisex",
    )
    export_parser.add_argument("--reference-segment-id", default=DEFAULT_REFERENCE_SEGMENT_ID)
    export_parser.add_argument("--max-scan-rows", type=int, default=DEFAULT_HF_MAX_SCAN_ROWS)
    export_parser.add_argument("--model-label", default="agent-cli")

    import_parser = subparsers.add_parser("import", help="Import Agent Pack results.")
    import_parser.add_argument("--pack", required=True, type=Path)
    import_parser.add_argument("--results", required=True, type=Path)
    import_parser.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "export":
        summary = export_agent_pack(
            concept_path=args.concept,
            output_dir=args.out,
            sample_size=args.sample_size,
            sampling_seed=args.seed,
            source=args.source,
            dataset_id=args.dataset_id,
            split=args.split,
            revision=args.revision,
            local_path=args.local_path,
            product_audience=args.audience,
            reference_segment_id=args.reference_segment_id,
            max_scan_rows=args.max_scan_rows,
            model_label=args.model_label,
        )
        print(
            "agent_pack_export=OK "
            f"pack={summary.pack_dir} prompts={summary.prompt_count} "
            f"sample_size={summary.sample_size}"
        )
        return 0
    if args.command == "import":
        summary = import_agent_results(
            pack_dir=args.pack,
            results_path=args.results,
            output_dir=args.out,
        )
        print(
            "agent_pack_import=OK "
            f"success={summary.success_count} parse_failed={summary.parse_failed_count} "
            f"report={summary.report_markdown_path}"
        )
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
