# SPDX-License-Identifier: AGPL-3.0-only
"""Streamlit-free orchestration helpers for screening runs."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import ValidationError

from src.aggregator import QualityCounts, aggregate
from src.app_config import DEFAULT_HF_MAX_SCAN_ROWS, DEFAULT_PRICE_CONTEXT_VERSION
from src.async_runner import make_sync_evaluator_for_worker
from src.cache import compute_cache_key, compute_legacy_cache_key_v1
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
from src.persona_filter import (
    apply_filter,
    sample_iterable_to_result,
    sample_to_result,
    take_matching_iterable_to_result,
)
from src.persona_normalizer import Persona
from src.prompt_builder import PROMPT_VERSION, SCHEMA_VERSION, build_prompt
from src.report_writer import render_csv, render_markdown
from src.result_parser import EvaluationResult, validate_evaluation_payload

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

    if normalized not in {"openai", "anthropic", "google", "openai_compatible"}:
        raise ValueError(f"Unsupported provider: {provider}")

    return cast(Provider, normalized)


def _persona_attributes_text(persona: Persona) -> str:

    location = " ".join(part for part in [persona.city, persona.state, persona.zipcode] if part)

    fields = [
        f"{persona.age} years old",
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
            api_base_url=getattr(pricing, "api_base_url", None),
            provider_model_id=getattr(pricing, "provider_model_id", None) or model["model_name"],
        )
        legacy_cache_key = compute_legacy_cache_key_v1(
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
                "_legacy_cache_key": legacy_cache_key,
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
                    "product_price_usd_cents": concept["product_price_usd_cents"],
                    "api_base_url": getattr(pricing, "api_base_url", None),
                    "provider_model_id": getattr(pricing, "provider_model_id", None)
                    or model["model_name"],
                    "temperature": model["temperature"],
                    "prompt_version": prompt.prompt_version,
                    "schema_version": prompt.schema_version,
                    "price_context_version": DEFAULT_PRICE_CONTEXT_VERSION,
                    "input_per_million_usd": getattr(
                        pricing,
                        "input_per_million_usd",
                        None,
                    ),
                    "output_per_million_usd": getattr(
                        pricing,
                        "output_per_million_usd",
                        None,
                    ),
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


def _cache_keys_for_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    primary = str(payload["_cache_key"])
    legacy = payload.get("_legacy_cache_key")
    if legacy is None or str(legacy) == primary:
        return (primary,)
    return (primary, str(legacy))


def _cache_lookup_for_payload(
    db_path: Path,
    payload: dict[str, Any],
    cache_lookup_fn: Callable[[Path, str], str | None],
) -> tuple[str, str] | None:
    for cache_key in _cache_keys_for_payload(payload):
        cached_json = cache_lookup_fn(db_path, cache_key)
        if cached_json is not None:
            return cache_key, cached_json
    return None


def _write_through_legacy_cache_hit(
    db_path: Path,
    payload: dict[str, Any],
    hit_cache_key: str,
    cached_json: str,
    cache_store_fn: Callable[[Path, str, EvaluatorResult, dict[str, Any]], None],
) -> bool:
    primary_cache_key = str(payload["_cache_key"])
    if hit_cache_key == primary_cache_key:
        return True

    # v1 fallback: keep until v0.6.0, then remove once old cache rows have migrated.
    try:
        cache_store_fn(
            db_path,
            primary_cache_key,
            {
                "status": "cached",
                "error_type": None,
                "response_json": cached_json,
                "latency_ms": 0,
            },
            payload["cache_metadata"],
        )
    except Exception as exc:  # noqa: BLE001 - compatibility write-through is best-effort.
        logger.warning(
            "legacy cache write-through failed; keeping legacy cache key: %s",
            type(exc).__name__,
        )
        return False
    return True


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


def validate_cached_result_json(response_json: str) -> None:
    """Validate cached response JSON before trusting a preflight cache hit."""
    validate_evaluation_payload(json.loads(response_json))


async def run_preflight_and_cache_async(
    db_path: Path,
    payload: dict[str, Any],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
    *,
    cache_lookup_fn: Callable[[Path, str], str | None] = _cache_lookup,
    cache_store_fn: Callable[[Path, str, EvaluatorResult, dict[str, Any]], None] = _cache_store,
) -> None:
    """Run one persona before job creation and cache the successful result.

    This caches a valid probe before job creation. Parse-only probe failures do
    not block the run because the worker can still collect successful rows from
    the remaining panel.
    """
    cache_hit = _cache_lookup_for_payload(db_path, payload, cache_lookup_fn)
    if cache_hit is not None:
        hit_cache_key, cached_json = cache_hit
        validate_cached_result_json(cached_json)
        _write_through_legacy_cache_hit(
            db_path,
            payload,
            hit_cache_key,
            cached_json,
            cache_store_fn,
        )
        return

    cache_key = str(payload["_cache_key"])
    result = await llm_evaluator_async(payload)
    status = str(result.get("status", ""))
    response_json = result.get("response_json")
    if status == "parse_failed":
        logger.warning("preflight parse failed; continuing without preflight cache")
        return
    if status != "success" or not response_json:
        error_type = str(result.get("error_type") or status or "unknown")
        raise ValueError(f"preflight failed before job creation: {error_type}")

    validate_cached_result_json(str(response_json))
    cache_store_fn(db_path, cache_key, result, payload["cache_metadata"])
    if cache_lookup_fn(db_path, cache_key) is None:
        raise RuntimeError("preflight succeeded, but cache write failed")


def run_preflight_and_cache(
    db_path: Path,
    payload: dict[str, Any],
    llm_evaluator_async: Callable[[dict[str, Any]], Any],
) -> None:
    """Synchronous wrapper for Streamlit/start_screening."""
    asyncio.run(run_preflight_and_cache_async(db_path, payload, llm_evaluator_async))


def make_llm_evaluator_async(
    provider: Provider,
    model_name: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int = 1200,
    api_base_url: str | None = None,
    auth_header: str | None = None,
    supports_json_object: bool = True,
    supports_json_schema: bool = False,
    supports_tool_use: bool = False,
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
            "api_base_url": api_base_url,
            "auth_header": auth_header,
            "supports_json_object": supports_json_object,
            "supports_json_schema": supports_json_schema,
            "supports_tool_use": supports_tool_use,
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

        cache_hit = _cache_lookup_for_payload(db_path, payload, cache_lookup_fn)

        if cache_hit is not None:
            hit_cache_key, cached_json = cache_hit
            write_through_ok = _write_through_legacy_cache_hit(
                db_path,
                payload,
                hit_cache_key,
                cached_json,
                cache_store_fn,
            )
            return {
                "status": "cached",
                "error_type": None,
                "response_json": cached_json,
                "latency_ms": 0,
                "cache_key": cache_key if write_through_ok else hit_cache_key,
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
                parsed_results.append(validate_evaluation_payload(json.loads(response_json)))

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
    sample_size = max(1, int(sample["sample_size"]))

    if dataset["source"] == "huggingface":
        loaded, rows = load_huggingface_dataset_fn(
            dataset_id=dataset["dataset_id"],
            split=dataset["split"],
            streaming=True,
            revision=dataset["revision"],
            token=hf_token,
        )
        explicit_max_scan_rows = sample.get("max_scan_rows")
        max_scan_rows = (
            max(1, int(explicit_max_scan_rows))
            if explicit_max_scan_rows is not None
            else DEFAULT_HF_MAX_SCAN_ROWS
        )
        rows = islice(rows, max_scan_rows)

        personas_iter = normalize_rows_to_personas(rows)

        sample_func = (
            sample_iterable_to_result
            if sample.get("seeded_reservoir_sampling")
            else take_matching_iterable_to_result
        )

        sampled = sample_func(
            personas_iter,
            sample["filter"],
            sample_size,
            sample["sampling_seed"],
        )

        return loaded, sampled

    else:
        loaded, rows = load_local_file_fn(_repo_relative_path(Path(dataset["local_path"])))

    personas = list(normalize_rows_to_personas(rows))

    filtered = apply_filter(personas, sample["filter"])

    sampled = sample_to_result(filtered, sample_size, sample["sampling_seed"])

    return loaded, sampled


def _sampling_strategy_for_dataset(dataset: dict[str, Any]) -> str:

    if dataset["source"] == "huggingface":
        return "filter_then_take_until_sample_size_limited_scan"

    return "filter_then_seeded_random_sample"
