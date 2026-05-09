# SPDX-License-Identifier: AGPL-3.0-only
"""Streamlit-free orchestration helpers for screening runs."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import ValidationError

from src.aggregator import QualityCounts, aggregate
from src.app_config import DEFAULT_PRICE_CONTEXT_VERSION
from src.async_runner import make_sync_evaluator_for_worker
from src.cache import compute_cache_key
from src.data_loader import (
    LoadedDataset,
    load_huggingface_dataset,
    load_local_file,
    normalize_rows_to_personas,
)
from src.db import get_connection
from src.job_manager import RunMeta
from src.llm_client import LLMClientError, LLMRequest, Provider, call_with_retry
from src.llm_client import parse_evaluation_result as parse_llm_evaluation_result
from src.persona_filter import apply_filter, sample_iterable_to_result, sample_to_result
from src.persona_normalizer import Persona
from src.prompt_builder import PROMPT_VERSION, SCHEMA_VERSION, build_prompt
from src.report_writer import render_csv, render_markdown
from src.result_parser import EvaluationResult, parse_evaluation_result

REPO_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)
ResultRow = dict[str, Any]
EvaluatorResult = dict[str, Any]
SyncEvaluator = Callable[[dict], EvaluatorResult]


@dataclass(frozen=True)
class RunReport:
    report_markdown: str
    report_csv: str
    quality: QualityCounts


def _utc_now_iso8601_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _repo_relative_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _provider_from_str(provider: str) -> Provider:
    normalized = provider.lower()
    if normalized not in {"openai", "anthropic", "google"}:
        raise ValueError(f"지원하지 않는 provider: {provider}")
    return cast(Provider, normalized)


def _persona_attributes_text(persona: Persona) -> str:
    location = " ".join(part for part in [persona.city, persona.state, persona.zipcode] if part)
    fields = [
        f"{persona.age}세",
        persona.sex,
        location,
        persona.occupation,
        persona.marital_status,
        persona.education_level,
    ]
    return " / ".join(field for field in fields if field)


def _persona_summary_text(persona: Persona) -> str:
    parts = [
        persona.persona_summary,
        persona.professional_text,
        persona.lifestyle_text,
        persona.interests_text,
    ]
    return "\n\n".join(part for part in parts if part)


def _persona_attributes(persona: Persona) -> dict[str, Any]:
    return {
        "age": persona.age,
        "sex": persona.sex,
        "state": persona.state,
        "city": persona.city,
        "zipcode": persona.zipcode,
        "occupation": persona.occupation,
    }


def _economic_context_text(concept: dict[str, Any], price_context: dict[str, Any]) -> str:
    metric_rows = price_context.get("metric_rows") or []
    if metric_rows:
        metrics_text = "; ".join(
            f"{row.get('label', row.get('metric'))} "
            f"${int(row.get('value_usd') or 0):,.0f} "
            f"({row.get('period', '')})"
            for row in metric_rows
        )
    else:
        metrics_text = (
            "BLS Consumer Expenditure Survey 2024 annual Apparel and services "
            f"${price_context['apparel_services_annual_usd']:,.0f}; "
            "BLS Consumer Expenditure Survey 2024 average income before taxes "
            f"${price_context['bls_average_income_before_taxes_usd']:,.0f}; "
            "Census CPS ASEC 2024 median household income "
            f"${price_context['census_median_household_income_usd']:,.0f}; "
            "Federal Reserve SCF 2022 median family net worth "
            f"${price_context['fed_scf_median_family_net_worth_usd']:,.0f}; "
            "Federal Reserve SCF 2022 mean family net worth "
            f"${price_context['fed_scf_mean_family_net_worth_usd']:,.0f}"
        )
    return (
        f"Product price is ${concept['product_price_usd_cents'] / 100:,.2f} USD. "
        f"Reference segment: "
        f"{price_context.get('reference_segment_label', 'U.S. national baseline')}. "
        f"It is {price_context['price_burden_ratio']:.2f}x the selected annual Apparel "
        f"and services reference value "
        f"(${price_context['apparel_services_annual_usd']:,.0f}). "
        f"Price burden label: {price_context['price_burden_label']}. "
        f"Official aggregate context: {metrics_text}. "
        "These are aggregate U.S. official statistics and do not imply an individual "
        "persona's actual income, assets, purchase power, or willingness to pay."
    )


def build_persona_payloads(
    personas: list[Persona],
    concept: dict[str, Any],
    model: dict[str, Any],
    price_context: dict[str, Any],
    hashes: dict[str, str],
    prompt_template_md: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    economic_context_text = _economic_context_text(concept, price_context)
    pricing = model.get("pricing")

    for persona in personas:
        prompt = build_prompt(
            persona_id=persona.persona_id,
            persona_summary=_persona_summary_text(persona),
            persona_attributes_text=_persona_attributes_text(persona),
            economic_context_text=economic_context_text,
            category=concept["category"],
            concept_text=concept["concept_text"],
            price_usd_cents=concept["product_price_usd_cents"],
            prompt_template_md=prompt_template_md,
        )
        cache_key = compute_cache_key(
            persona_id=persona.persona_id,
            provider=model["provider"],
            concept_hash=hashes["concept_hash"],
            price_context_hash=hashes["price_context_hash"],
            model_name=model["model_name"],
            temperature=model["temperature"],
            prompt_version=prompt.prompt_version,
            schema_version=prompt.schema_version,
        )
        payloads.append(
            {
                "persona_id": persona.persona_id,
                "product_price_usd_cents": concept["product_price_usd_cents"],
                "_cache_key": cache_key,
                "prompt": {
                    "system": prompt.system,
                    "developer": prompt.developer,
                    "user": prompt.user,
                },
                "cache_metadata": {
                    "persona_id": persona.persona_id,
                    "concept_hash": hashes["concept_hash"],
                    "price_context_hash": hashes["price_context_hash"],
                    "provider": model["provider"],
                    "model_name": model["model_name"],
                    "temperature": model["temperature"],
                    "prompt_version": prompt.prompt_version,
                    "schema_version": prompt.schema_version,
                    "price_context_version": DEFAULT_PRICE_CONTEXT_VERSION,
                    "product_price_usd_cents": concept["product_price_usd_cents"],
                    "input_per_million_usd": getattr(pricing, "input_per_million_usd", None),
                    "output_per_million_usd": getattr(pricing, "output_per_million_usd", None),
                },
            }
        )
    return payloads


def make_run_meta(
    job_id: str,
    run_id: str,
    loaded_dataset: LoadedDataset,
    sample_size: int,
    sampling_seed: int,
    model: dict[str, Any],
    hashes: dict[str, str],
    matched_count_before_sample: int = 0,
    sampling_strategy: str = "unknown",
    filter_summary_text: str = "",
) -> RunMeta:
    return RunMeta(
        run_id=run_id,
        job_id=job_id,
        dataset_name=loaded_dataset.source,
        dataset_revision=loaded_dataset.dataset_revision,
        sample_size=sample_size,
        sampling_seed=sampling_seed,
        provider=model["provider"],
        model_name=model["model_name"],
        temperature=float(model["temperature"]),
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        price_context_version=DEFAULT_PRICE_CONTEXT_VERSION,
        concept_hash=hashes["concept_hash"],
        price_context_hash=hashes["price_context_hash"],
        dataset_split=loaded_dataset.dataset_split,
        matched_count_before_sample=matched_count_before_sample,
        sampling_strategy=sampling_strategy,
        filter_summary=filter_summary_text,
    )


def _cache_lookup(db_path: Path, cache_key: str) -> str | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT response_json FROM llm_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    return None if row is None else str(row[0])


def _cache_store(
    db_path: Path,
    cache_key: str,
    result: EvaluatorResult,
    metadata: dict[str, Any],
) -> None:
    response_json = result.get("response_json")
    if not response_json:
        return

    input_tokens_raw = result.get("input_tokens_actual")
    output_tokens_raw = result.get("output_tokens_actual")
    input_tokens_actual = None if input_tokens_raw is None else int(input_tokens_raw)
    output_tokens_actual = None if output_tokens_raw is None else int(output_tokens_raw)
    input_price = metadata.get("input_per_million_usd")
    output_price = metadata.get("output_per_million_usd")
    cost_actual_usd = None
    if (
        input_tokens_actual is not None
        and output_tokens_actual is not None
        and input_price is not None
        and output_price is not None
    ):
        cost_actual_usd = (int(input_tokens_actual) / 1_000_000) * float(input_price) + (
            int(output_tokens_actual) / 1_000_000
        ) * float(output_price)

    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO llm_cache ("
            "cache_key, persona_id, concept_hash, price_context_hash, provider, "
            "model_name, temperature, prompt_version, schema_version, "
            "price_context_version, response_json, raw_response_path, "
            "input_tokens_actual, output_tokens_actual, cost_actual_usd, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cache_key,
                metadata["persona_id"],
                metadata["concept_hash"],
                metadata["price_context_hash"],
                metadata["provider"],
                metadata["model_name"],
                float(metadata["temperature"]),
                metadata["prompt_version"],
                metadata["schema_version"],
                metadata["price_context_version"],
                response_json,
                None,
                input_tokens_actual,
                output_tokens_actual,
                cost_actual_usd,
                _utc_now_iso8601_z(),
            ),
        )
        conn.commit()


def _result_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def make_llm_evaluator_async(
    provider: Provider,
    model_name: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int = 600,
    call_with_retry_fn: Callable[[LLMRequest, httpx.AsyncClient], Any] = call_with_retry,
) -> Callable[[dict[str, Any]], Any]:
    async def _evaluate(payload: dict[str, Any]) -> EvaluatorResult:
        prompt = payload["prompt"]
        request_kwargs = {
            "provider": provider,
            "model_name": model_name,
            "api_key": api_key,
            "system": prompt["system"],
            "developer": prompt["developer"],
            "user": prompt["user"],
            "max_output_tokens": max_output_tokens,
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                request = LLMRequest(temperature=temperature, **request_kwargs)
                raw = await call_with_retry_fn(request, client)
                status, parsed, error_summary = parse_llm_evaluation_result(
                    raw,
                    expected_persona_id=payload["persona_id"],
                )
                if status != "success" and temperature != 0.1:
                    retry_request = LLMRequest(temperature=0.1, **request_kwargs)
                    raw = await call_with_retry_fn(retry_request, client)
                    status, parsed, error_summary = parse_llm_evaluation_result(
                        raw,
                        expected_persona_id=payload["persona_id"],
                    )
        except LLMClientError as exc:
            return {
                "status": "api_failed",
                "error_type": exc.error_type,
                "response_json": None,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        latency_ms = int((time.perf_counter() - started) * 1000)
        if status == "success" and parsed is not None:
            return {
                "status": "success",
                "error_type": None,
                "response_json": _result_json(parsed),
                "latency_ms": latency_ms,
                "input_tokens_actual": raw.input_tokens_actual,
                "output_tokens_actual": raw.output_tokens_actual,
            }
        return {
            "status": "parse_failed",
            "error_type": error_summary or "parse_failed",
            "response_json": None,
            "latency_ms": latency_ms,
        }

    return _evaluate


def make_cached_evaluator_async(
    db_path: Path,
    payloads: list[dict[str, Any]],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
    *,
    cache_lookup_fn: Callable[[Path, str], str | None] = _cache_lookup,
    cache_store_fn: Callable[[Path, str, EvaluatorResult, dict[str, Any]], None] = _cache_store,
) -> Callable[[dict[str, Any]], Any]:
    metadata_by_key = {payload["_cache_key"]: payload["cache_metadata"] for payload in payloads}

    async def _evaluate(payload: dict[str, Any]) -> EvaluatorResult:
        cache_key = str(payload["_cache_key"])
        cached_json = cache_lookup_fn(db_path, cache_key)
        if cached_json is not None:
            return {
                "status": "cached",
                "error_type": None,
                "response_json": cached_json,
                "latency_ms": 0,
                "cache_key": cache_key,
            }

        result = await llm_evaluator_async(payload)
        if result.get("status") == "success" and result.get("response_json"):
            result = dict(result)
            try:
                cache_store_fn(db_path, cache_key, result, metadata_by_key[cache_key])
            except Exception as exc:  # noqa: BLE001 - cache is best-effort.
                logger.warning(
                    "cache_store failed; continuing successful evaluation without cache FK: %s",
                    type(exc).__name__,
                )
            else:
                result["cache_key"] = cache_key
        return result

    return _evaluate


def make_cached_sync_evaluator(
    db_path: Path,
    payloads: list[dict[str, Any]],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
    *,
    cache_lookup_fn: Callable[[Path, str], str | None] = _cache_lookup,
    cache_store_fn: Callable[[Path, str, EvaluatorResult, dict[str, Any]], None] = _cache_store,
) -> SyncEvaluator:
    return make_sync_evaluator_for_worker(
        make_cached_evaluator_async(
            db_path,
            payloads,
            llm_evaluator_async,
            cache_lookup_fn=cache_lookup_fn,
            cache_store_fn=cache_store_fn,
        )
    )


def load_result_rows(db_path: Path, run_id: str) -> list[ResultRow]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT persona_id, status, error_type, response_json, latency_ms "
            "FROM run_results WHERE run_id = ? ORDER BY persona_id",
            (run_id,),
        ).fetchall()
    return [
        {
            "persona_id": row[0],
            "status": row[1],
            "error_type": row[2],
            "response_json": row[3],
            "latency_ms": row[4],
        }
        for row in rows
    ]


def build_run_report(
    result_rows: list[ResultRow],
    persona_attributes: dict[str, dict[str, Any]],
    price_context: dict[str, Any] | None = None,
) -> RunReport:
    parsed_results: list[EvaluationResult] = []
    parse_failed = 0
    api_failed = 0

    for row in result_rows:
        status = row["status"]
        response_json = row["response_json"]
        if status in {"success", "cached"} and response_json:
            try:
                parsed_results.append(parse_evaluation_result(json.loads(response_json)))
            except json.JSONDecodeError:
                logger.warning(
                    "Run report skipped invalid result JSON.",
                    extra={"reason": "json_decode", "persona_id": row.get("persona_id")},
                )
                parse_failed += 1
            except ValidationError:
                logger.warning(
                    "Run report skipped invalid result schema.",
                    extra={"reason": "schema_validation", "persona_id": row.get("persona_id")},
                )
                parse_failed += 1
            except TypeError:
                logger.warning(
                    "Run report skipped non-string result JSON.",
                    extra={"reason": "response_json_type", "persona_id": row.get("persona_id")},
                )
                parse_failed += 1
        elif status == "parse_failed":
            parse_failed += 1
        elif status == "api_failed":
            api_failed += 1

    quality = QualityCounts(
        success=len(parsed_results),
        parse_failed=parse_failed,
        api_failed=api_failed,
        total_attempted=len(result_rows),
        distribution_included=len(parsed_results),
    )
    report = aggregate(parsed_results, persona_attributes, quality)
    return RunReport(
        report_markdown=render_markdown(report, price_context=price_context),
        report_csv=render_csv(report, price_context=price_context),
        quality=quality,
    )


def _load_and_sample(
    dataset: dict[str, Any],
    sample: dict[str, Any],
    *,
    hf_token: str | None = None,
    load_huggingface_dataset_fn: Callable[..., Any] = load_huggingface_dataset,
    load_local_file_fn: Callable[[Path], Any] = load_local_file,
):
    if dataset["source"] == "huggingface":
        loaded, rows = load_huggingface_dataset_fn(
            dataset_id=dataset["dataset_id"],
            split=dataset["split"],
            streaming=True,
            revision=dataset["revision"],
            token=hf_token,
        )
        sampled = sample_iterable_to_result(
            normalize_rows_to_personas(rows),
            sample["filter"],
            sample["sample_size"],
            sample["sampling_seed"],
        )
        return loaded, sampled

    loaded, rows = load_local_file_fn(_repo_relative_path(Path(dataset["local_path"])))
    personas = list(normalize_rows_to_personas(rows))
    filtered = apply_filter(personas, sample["filter"])
    sampled = sample_to_result(filtered, sample["sample_size"], sample["sampling_seed"])
    return loaded, sampled


def _sampling_strategy_for_dataset(dataset: dict[str, Any]) -> str:
    if dataset["source"] == "huggingface":
        return "filter_then_seeded_reservoir"
    return "filter_then_seeded_random_sample"
