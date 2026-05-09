# SPDX-License-Identifier: AGPL-3.0-only
"""Persona filtering and sampling."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.persona_normalizer import Persona

US_STATE_NAME_TO_CODE: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "puerto rico": "PR",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "virgin islands": "VI",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


def _normalize_state_token(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    upper = text.upper()
    if len(upper) == 2 and upper.isalpha():
        return upper
    return US_STATE_NAME_TO_CODE.get(text.casefold(), text)


@dataclass(frozen=True)
class PersonaFilter:
    """All filters are ignored when None or empty."""

    age_min: int | None = None
    age_max: int | None = None
    sex: frozenset[str] = frozenset()
    state: frozenset[str] = frozenset()
    occupation_contains: frozenset[str] = frozenset()

    def matches(self, p: Persona) -> bool:
        if self.age_min is not None and p.age < self.age_min:
            return False
        if self.age_max is not None and p.age > self.age_max:
            return False
        if self.sex and p.sex not in self.sex:
            return False
        if self.state:
            selected_states = {_normalize_state_token(state) for state in self.state}
            if _normalize_state_token(p.state) not in selected_states:
                return False
        return not (
            self.occupation_contains
            and not any(kw.lower() in p.occupation.lower() for kw in self.occupation_contains)
        )


def apply_filter(
    personas: Iterable[Persona],
    filt: PersonaFilter,
) -> list[Persona]:
    """Collect personas that pass the filter."""
    return [p for p in personas if filt.matches(p)]


def sample_personas(
    personas: list[Persona],
    sample_size: int,
    seed: int,
) -> list[Persona]:
    """Return a deterministic random sample sorted by persona_id."""
    if sample_size <= 0:
        raise ValueError(f"sample_size must be positive, got {sample_size}")

    if sample_size >= len(personas):
        return sorted(personas, key=lambda p: p.persona_id)

    rng = random.Random(seed)  # nosec B311
    selected = rng.sample(personas, sample_size)
    return sorted(selected, key=lambda p: p.persona_id)


def filter_summary(filt: PersonaFilter) -> str:
    """Build a compact UI filter summary."""
    parts = []
    if filt.age_min is not None or filt.age_max is not None:
        lo = filt.age_min if filt.age_min is not None else "*"
        hi = filt.age_max if filt.age_max is not None else "*"
        parts.append(f"age {lo}-{hi}")
    if filt.sex:
        parts.append(f"sex {','.join(sorted(filt.sex))}")
    if filt.state:
        parts.append(f"state {','.join(sorted(filt.state))}")
    if filt.occupation_contains:
        parts.append(f"occupation keyword {','.join(sorted(filt.occupation_contains))}")
    return " / ".join(parts) if parts else "no filters"


@dataclass(frozen=True)
class SampleResult:
    """Filter plus sampling result."""

    rows: list[Persona]
    matched_count_before_sample: int
    sample_size: int
    sampling_seed: int


def sample_to_result(
    personas: list[Persona],
    sample_size: int,
    seed: int,
) -> SampleResult:
    """Sample a list of already-filtered personas."""
    if sample_size <= 0:
        raise ValueError(f"sample_size must be positive, got {sample_size}")

    matched_count = len(personas)

    if matched_count == 0:
        return SampleResult(
            rows=[],
            matched_count_before_sample=0,
            sample_size=0,
            sampling_seed=seed,
        )

    if sample_size >= matched_count:
        return SampleResult(
            rows=sorted(personas, key=lambda p: p.persona_id),
            matched_count_before_sample=matched_count,
            sample_size=matched_count,
            sampling_seed=seed,
        )

    rng = random.Random(seed)  # nosec B311
    selected = rng.sample(personas, sample_size)
    return SampleResult(
        rows=sorted(selected, key=lambda p: p.persona_id),
        matched_count_before_sample=matched_count,
        sample_size=sample_size,
        sampling_seed=seed,
    )


def sample_iterable_to_result(
    personas: Iterable[Persona],
    filt: PersonaFilter,
    sample_size: int,
    seed: int,
) -> SampleResult:
    """Filter and sample an iterable without materializing every persona."""
    if sample_size <= 0:
        raise ValueError(f"sample_size must be positive, got {sample_size}")

    rng = random.Random(seed)  # nosec B311
    reservoir: list[Persona] = []
    matched_count = 0

    for persona in personas:
        if not filt.matches(persona):
            continue
        matched_count += 1
        if len(reservoir) < sample_size:
            reservoir.append(persona)
            continue
        index = rng.randrange(matched_count)
        if index < sample_size:
            reservoir[index] = persona

    if matched_count == 0:
        return SampleResult(
            rows=[],
            matched_count_before_sample=0,
            sample_size=0,
            sampling_seed=seed,
        )

    return SampleResult(
        rows=sorted(reservoir, key=lambda p: p.persona_id),
        matched_count_before_sample=matched_count,
        sample_size=min(sample_size, matched_count),
        sampling_seed=seed,
    )


def preview_first_n(rows: list[Any], n: int = 30) -> list[Any]:
    """Return the first n preview rows."""
    if n <= 0:
        return []
    return rows[:n]
