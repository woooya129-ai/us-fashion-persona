"""Synchronous fake evaluator for WS-JOB worker tests.

NEVER calls a real LLM, never opens a network socket. Async fakes belong to
WS-PROMPT-LLM. The shape returned here matches the contract documented on
src.worker.WorkerInput.evaluator.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

# Default fallback for an unknown persona_id — keeps tests deterministic.
_UNKNOWN_FALLBACK = {
    "status": "api_failed",
    "error_type": "UnknownPersona",
    "response_json": None,
    "latency_ms": None,
}


def _result_from_scenario(scenario: dict, persona_id: str) -> dict:
    if scenario.get("raise"):
        exc_cls = scenario.get("exc_type", RuntimeError)
        msg = scenario.get("message", f"fake error for {persona_id}")
        raise exc_cls(msg)
    return {
        "status": scenario["status"],
        "error_type": scenario.get("error_type"),
        "response_json": scenario.get("response_json"),
        "latency_ms": scenario.get("latency_ms"),
    }


def make_fake_evaluator(
    scenarios: dict[str, dict],
) -> Callable[[dict], dict]:
    """Return a sync evaluator callable driven by a scenarios dict.

    scenarios[persona_id] keys:
        status        : ResultStatus literal (str)
        error_type    : str | None
        response_json : str | None
        latency_ms    : int | None

    Special form (raises an exception instead of returning):
        {"raise": True, "exc_type": <ExceptionClass>, "message": str}

    Unknown persona_id falls back to api_failed/UnknownPersona.
    """

    def _evaluator(payload: dict) -> dict:
        persona_id: str = payload["persona_id"]
        scenario = scenarios.get(persona_id, _UNKNOWN_FALLBACK)
        return _result_from_scenario(scenario, persona_id)

    return _evaluator


def make_blocking_fake_evaluator(
    scenarios: dict[str, dict],
    started_event: threading.Event,
    proceed_event: threading.Event,
    trigger_persona_id: str,
) -> Callable[[dict], dict]:
    """Sync evaluator that blocks on ``trigger_persona_id`` for cancel tests.

    Behaviour:
        - When called with payload['persona_id'] == trigger_persona_id:
            1. set ``started_event`` so the test thread knows we're inside
               the evaluator
            2. wait on ``proceed_event`` so the test can request_cancel
               and then release us deterministically
        - All other persona_ids return immediately from scenarios.

    This Event-driven design (no time.sleep) keeps the cancel test
    flake-free on all OSes including Windows runners.
    """

    def _evaluator(payload: dict) -> dict:
        persona_id: str = payload["persona_id"]
        if persona_id == trigger_persona_id:
            started_event.set()
            proceed_event.wait()

        scenario = scenarios.get(persona_id, _UNKNOWN_FALLBACK)
        return _result_from_scenario(scenario, persona_id)

    return _evaluator
