# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    persona_id: str
    age: int
    sex: str
    state: str
    city: str
    zipcode: str
    occupation: str
    marital_status: str
    education_level: str

    persona_summary: str
    professional_text: str
    lifestyle_text: str
    interests_text: str

    source_row_id: int


def _get_str(raw: dict, key: str) -> str:
    val = raw.get(key)
    if val is None:
        return ""
    return str(val).strip()


def _concat(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p)


def normalize_persona(raw_row: dict, source_row_id: int) -> Persona | None:
    """Convert one USA schema raw row to a Persona object."""
    persona_id = _get_str(raw_row, "uuid")
    if not persona_id:
        return None

    raw_sex = _get_str(raw_row, "sex")
    if not raw_sex:
        return None

    raw_persona = _get_str(raw_row, "persona")
    if not raw_persona:
        return None

    raw_age = raw_row.get("age")
    try:
        age = int(raw_age)
    except (TypeError, ValueError):
        return None

    interests_text = _concat(
        _get_str(raw_row, "hobbies_and_interests"),
        _get_str(raw_row, "sports_persona"),
        _get_str(raw_row, "arts_persona"),
        _get_str(raw_row, "travel_persona"),
        _get_str(raw_row, "culinary_persona"),
    )

    return Persona(
        persona_id=persona_id,
        age=age,
        sex=raw_sex,
        state=_get_str(raw_row, "state"),
        city=_get_str(raw_row, "city"),
        zipcode=_get_str(raw_row, "zipcode"),
        occupation=_get_str(raw_row, "occupation"),
        marital_status=_get_str(raw_row, "marital_status"),
        education_level=_get_str(raw_row, "education_level"),
        persona_summary=raw_persona,
        professional_text=_get_str(raw_row, "professional_persona"),
        lifestyle_text=_get_str(raw_row, "cultural_background"),
        interests_text=interests_text,
        source_row_id=source_row_id,
    )
