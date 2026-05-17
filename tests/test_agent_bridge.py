"""Tests for subscription CLI Agent Pack export/import helpers.

No Codex, Claude Code, Hugging Face, or LLM process is invoked here.
"""

from __future__ import annotations

import json

import pytest

from src.agent_bridge import import_agent_results, write_agent_pack
from src.economic_context import build_price_context
from src.persona_normalizer import Persona, normalize_persona
from src.result_parser import EvaluationResult
from tests.fixtures.mock_personas import ALL_MOCK_PERSONAS

pytestmark = pytest.mark.no_network


def _personas(count: int = 2) -> list[Persona]:
    personas: list[Persona] = []
    for index, row in enumerate(ALL_MOCK_PERSONAS, start=1):
        persona = normalize_persona(row, source_row_id=index)
        if persona is not None:
            personas.append(persona)
        if len(personas) == count:
            return personas
    raise AssertionError("not enough mock personas")


def _concept() -> dict:
    return {
        "project_name": "agent-bridge-test",
        "category": "outerwear",
        "product_price_usd_cents": 15_900,
        "concept_text": "Minimal wool coat for commuter styling.",
        "target_hypothesis": "Office workers who prefer quiet premium styling.",
    }


def _result(persona_id: str, *, score: int = 8) -> dict:
    return EvaluationResult(
        persona_id=persona_id,
        sentiment="positive",
        interest_score=score,
        price_burden="medium",
        main_reasons=["design"],
        main_concerns=["price"],
        confidence_note="test fixture",
    ).model_dump()


def test_write_agent_pack_creates_prompts_schema_and_cli_scripts(tmp_path):
    personas = _personas()
    pack_dir = tmp_path / "agent-pack"

    summary = write_agent_pack(
        output_dir=pack_dir,
        concept=_concept(),
        personas=personas,
        price_context=build_price_context(15_900),
        dataset={"source": "test"},
        sample={
            "sample_size": len(personas),
            "sampling_seed": 42,
            "matched_count_before_sample": len(personas),
        },
    )

    assert summary.prompt_count == len(personas)
    assert (pack_dir / "manifest.json").exists()
    assert (pack_dir / "schema" / "evaluation_result.schema.json").exists()
    assert (pack_dir / "input" / "prompts.jsonl").exists()
    assert (pack_dir / "commands" / "run-codex.ps1").exists()
    assert (pack_dir / "commands" / "run-claude.ps1").exists()

    prompt_text = next((pack_dir / "prompts").glob("*.md")).read_text(encoding="utf-8")
    assert "Return exactly one JSON object" in prompt_text
    assert "$159.00 USD" in prompt_text
    assert personas[0].persona_id in prompt_text

    claude_script = (pack_dir / "commands" / "run-claude.ps1").read_text(encoding="utf-8")
    assert "--output-format" in claude_script
    assert "--json-schema" in claude_script
    assert "UFPS_CLAUDE_BARE" in claude_script


def test_import_agent_results_accepts_codex_and_claude_wrappers(tmp_path):
    personas = _personas()
    pack_dir = tmp_path / "agent-pack"
    write_agent_pack(
        output_dir=pack_dir,
        concept=_concept(),
        personas=personas,
        price_context=build_price_context(15_900),
        dataset={"source": "test"},
        sample={
            "sample_size": len(personas),
            "sampling_seed": 42,
            "matched_count_before_sample": len(personas),
        },
    )

    results_dir = pack_dir / "results" / "mixed"
    results_dir.mkdir(parents=True)
    first_result = _result(personas[0].persona_id, score=9)
    second_result = _result(personas[1].persona_id, score=7)
    (results_dir / "codex-final.json").write_text(
        json.dumps(first_result, ensure_ascii=False),
        encoding="utf-8",
    )
    (results_dir / "claude-structured.json").write_text(
        json.dumps({"structured_output": second_result}, ensure_ascii=False),
        encoding="utf-8",
    )
    (results_dir / "claude-result-string.json").write_text(
        json.dumps({"result": json.dumps(second_result, ensure_ascii=False)}, ensure_ascii=False),
        encoding="utf-8",
    )
    (results_dir / "bad.txt").write_text("not json", encoding="utf-8")

    output_dir = tmp_path / "agent-report"
    summary = import_agent_results(
        pack_dir=pack_dir,
        results_path=results_dir,
        output_dir=output_dir,
    )

    assert summary.success_count == 2
    assert summary.parse_failed_count == 0
    assert (output_dir / "agent-report.md").exists()
    assert (output_dir / "agent-report.csv").exists()
    normalized_text = (output_dir / "normalized-results.jsonl").read_text(encoding="utf-8")
    assert personas[0].persona_id in normalized_text
    assert personas[1].persona_id in normalized_text
