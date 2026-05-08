"""AppTest E2E helpers: mock dataset + LLM path without network/HF/real API calls."""

from __future__ import annotations

import sys
import types
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import src.app as app
import src.data_loader as data_loader
import src.llm_client as llm_client
import src.secrets_loader as secrets_loader
import src.worker as worker
from src.data_loader import LoadedDataset
from src.persona_filter import apply_filter, sample_to_result
from src.persona_normalizer import normalize_persona
from src.worker import WorkerInput, run_worker
from tests.fixtures.mock_evaluation_results import MOCK_RESULTS
from tests.fixtures.mock_personas import MOCK_PERSONA_1, MOCK_PERSONA_2


def _forbidden(name: str):
    def _inner(*_a: Any, **_k: Any) -> Any:
        raise AssertionError(f"{name} must not be called in AppTest E2E")

    return _inner


class _ForbiddenModule(types.ModuleType):
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"{self.__name__}.{name} must not be accessed in AppTest E2E")

    def __call__(self, *_a: Any, **_k: Any) -> Any:
        raise AssertionError(f"{self.__name__} must not be called in AppTest E2E")


def _fake_datasets_module() -> types.ModuleType:
    module = _ForbiddenModule("datasets")
    module.__file__ = "<apptest-forbidden-datasets>"
    module.load_dataset = _forbidden("datasets.load_dataset")  # type: ignore[attr-defined]
    return module


def _fake_huggingface_hub_module() -> types.ModuleType:
    module = _ForbiddenModule("huggingface_hub")
    module.__file__ = "<apptest-forbidden-huggingface-hub>"
    return module


def _fake_secrets_status(db_path: Path) -> secrets_loader.LoadedSecretsStatus:
    return secrets_loader.LoadedSecretsStatus(
        openai_present=False,
        anthropic_present=False,
        hf_token_present=False,
        env_path=db_path.parent / "apptest-disabled.env",
        env_path_exists=False,
        google_present=False,
    )


def fake_load_and_sample(dataset: dict[str, Any], sample: dict[str, Any]):
    """Return two synthetic personas aligned with MOCK_RESULTS + MOCK_PERSONA_ATTRIBUTES."""
    r1 = deepcopy(MOCK_PERSONA_1)
    r1["uuid"] = "p001"
    r2 = deepcopy(MOCK_PERSONA_2)
    r2["uuid"] = "p002"
    p1 = normalize_persona(r1, 0)
    p2 = normalize_persona(r2, 1)
    assert p1 is not None and p2 is not None
    filtered = apply_filter([p1, p2], sample["filter"])
    sr = sample_to_result(filtered, sample["sample_size"], sample["sampling_seed"])
    loaded = LoadedDataset(
        source="local:apptest-mock",
        dataset_revision="fixture",
        total_rows=len(filtered),
    )
    return loaded, sr


def fake_make_llm_evaluator_async(
    provider: str,
    model_name: str,
    api_key: str,
    temperature: float,
    max_output_tokens: int = 600,
):
    by_pid = {"p001": MOCK_RESULTS[0], "p002": MOCK_RESULTS[1]}

    async def _evaluate(payload: dict[str, Any]):
        er = by_pid[payload["persona_id"]]
        return {
            "status": "success",
            "error_type": None,
            "response_json": er.model_dump_json(),
            "latency_ms": 1,
        }

    return _evaluate


def _sync_start_worker_thread(input_: WorkerInput):
    """Run WS-JOB inline so AppTest does not race a background thread."""

    class _DummyThread:
        name = "apptest-sync-worker"

    run_worker(input_)
    return _DummyThread()


def install_apptest_e2e_patches(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    """Wire tmp DB + fake sampling + fake LLM; block real HF/local load and HTTP LLM."""
    monkeypatch.setenv("UFPS_APPTEST_SYNC_JOB_PANEL", "1")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "1")
    monkeypatch.delenv(secrets_loader.HF_TOKEN_VAR, raising=False)
    monkeypatch.delenv(secrets_loader.OPENAI_KEY_VAR, raising=False)
    monkeypatch.delenv(secrets_loader.ANTHROPIC_KEY_VAR, raising=False)
    monkeypatch.delenv(secrets_loader.GOOGLE_KEY_VAR, raising=False)
    monkeypatch.setitem(sys.modules, "datasets", _fake_datasets_module())
    monkeypatch.setitem(sys.modules, "huggingface_hub", _fake_huggingface_hub_module())
    monkeypatch.setattr(app, "DB_PATH", db_path)
    monkeypatch.setattr(app, "_load_and_sample", fake_load_and_sample)
    monkeypatch.setattr(app, "make_llm_evaluator_async", fake_make_llm_evaluator_async)
    monkeypatch.setattr(app, "start_worker_thread", _sync_start_worker_thread)
    monkeypatch.setattr(app, "load_huggingface_dataset", _forbidden("app.load_huggingface_dataset"))
    monkeypatch.setattr(app, "load_local_file", _forbidden("app.load_local_file"))
    monkeypatch.setattr(
        data_loader,
        "load_huggingface_dataset",
        _forbidden("src.data_loader.load_huggingface_dataset"),
    )
    monkeypatch.setattr(
        data_loader,
        "load_local_file",
        _forbidden("src.data_loader.load_local_file"),
    )
    monkeypatch.setattr(app, "call_with_retry", _forbidden("app.call_with_retry"))
    monkeypatch.setattr(llm_client, "call_with_retry", _forbidden("src.llm_client.call_with_retry"))
    monkeypatch.setattr(app.httpx, "AsyncClient", _forbidden("httpx.AsyncClient"))
    monkeypatch.setattr(app, "load_secrets_from_env_path", lambda: _fake_secrets_status(db_path))
    monkeypatch.setattr(
        secrets_loader,
        "load_secrets_from_env_path",
        lambda env_path=secrets_loader.SECRETS_ENV_PATH: _fake_secrets_status(db_path),
    )
    monkeypatch.setattr(app, "get_provider_key", lambda _provider: None)
    monkeypatch.setattr(secrets_loader, "get_provider_key", lambda _provider: None)
    monkeypatch.setattr(worker, "start_worker_thread", _sync_start_worker_thread)
