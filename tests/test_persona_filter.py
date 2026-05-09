"""src/persona_filter.py tests."""

import pytest

from src.persona_filter import (
    PersonaFilter,
    SampleResult,
    apply_filter,
    filter_summary,
    preview_first_n,
    sample_iterable_to_result,
    sample_personas,
    sample_to_result,
)
from src.persona_normalizer import Persona

pytestmark = pytest.mark.no_network


def _make(
    persona_id: str,
    age: int,
    sex: str,
    state: str = "NY",
    occupation: str = "marketer",
) -> Persona:
    return Persona(
        persona_id=persona_id,
        age=age,
        sex=sex,
        state=state,
        city="",
        zipcode="",
        occupation=occupation,
        marital_status="",
        education_level="",
        persona_summary="test",
        professional_text="",
        lifestyle_text="",
        interests_text="",
        source_row_id=0,
    )


SAMPLE_PERSONAS = [
    _make("p1", 25, "F", "NY", "marketer"),
    _make("p2", 33, "F", "CA", "teacher"),
    _make("p3", 42, "M", "TX", "architect"),
    _make("p4", 19, "M", "NY", "student"),
    _make("p5", 65, "F", "FL", "retiree"),
]


class TestPersonaFilter:
    def test_no_filter_matches_all(self):
        f = PersonaFilter()
        assert all(f.matches(p) for p in SAMPLE_PERSONAS)

    def test_age_min(self):
        f = PersonaFilter(age_min=30)
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p2", "p3", "p5"}

    def test_age_max(self):
        f = PersonaFilter(age_max=40)
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p1", "p2", "p4"}

    def test_age_range(self):
        f = PersonaFilter(age_min=20, age_max=50)
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p1", "p2", "p3"}

    def test_sex_filter(self):
        f = PersonaFilter(sex=frozenset(["F"]))
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p1", "p2", "p5"}

    def test_state_filter(self):
        f = PersonaFilter(state=frozenset(["NY"]))
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p1", "p4"}

    def test_state_filter_accepts_full_name_input(self):
        f = PersonaFilter(state=frozenset(["California"]))
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p2"}

    def test_state_filter_normalizes_full_name_rows(self):
        p = _make("p-ca", 30, "F", state="California")
        f = PersonaFilter(state=frozenset(["CA"]))
        assert f.matches(p)

    def test_occupation_contains(self):
        f = PersonaFilter(occupation_contains=frozenset(["teacher", "architect"]))
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p2", "p3"}

    def test_combined_filters(self):
        f = PersonaFilter(
            age_min=30,
            age_max=50,
            sex=frozenset(["M"]),
            state=frozenset(["TX"]),
        )
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert {p.persona_id for p in result} == {"p3"}

    def test_zero_match(self):
        f = PersonaFilter(age_min=100)
        result = apply_filter(SAMPLE_PERSONAS, f)
        assert result == []


class TestSamplePersonas:
    def test_deterministic_with_seed(self):
        a = sample_personas(SAMPLE_PERSONAS, 3, seed=42)
        b = sample_personas(SAMPLE_PERSONAS, 3, seed=42)
        assert [p.persona_id for p in a] == [p.persona_id for p in b]

    def test_different_seeds_different_results(self):
        a = sample_personas(SAMPLE_PERSONAS, 3, seed=42)
        b = sample_personas(SAMPLE_PERSONAS, 3, seed=99)
        assert len(a) == 3 and len(b) == 3

    def test_sample_size_equals_population(self):
        result = sample_personas(SAMPLE_PERSONAS, 5, seed=42)
        assert len(result) == 5

    def test_sample_size_exceeds_population_returns_all(self):
        result = sample_personas(SAMPLE_PERSONAS, 100, seed=42)
        assert len(result) == 5
        assert {p.persona_id for p in result} == {p.persona_id for p in SAMPLE_PERSONAS}

    def test_sample_zero_raises(self):
        with pytest.raises(ValueError):
            sample_personas(SAMPLE_PERSONAS, 0, seed=42)

    def test_sample_negative_raises(self):
        with pytest.raises(ValueError):
            sample_personas(SAMPLE_PERSONAS, -1, seed=42)

    def test_results_sorted_by_persona_id(self):
        result = sample_personas(SAMPLE_PERSONAS, 3, seed=42)
        ids = [p.persona_id for p in result]
        assert ids == sorted(ids)


class TestFilterSummary:
    def test_no_filter(self):
        assert "no filters" in filter_summary(PersonaFilter())

    def test_age_only(self):
        s = filter_summary(PersonaFilter(age_min=20, age_max=40))
        assert "20" in s and "40" in s

    def test_combined(self):
        s = filter_summary(PersonaFilter(age_min=30, sex=frozenset(["M"]), state=frozenset(["NY"])))
        assert "30" in s and "M" in s and "NY" in s


class TestOccupationCaseInsensitive:
    def test_uppercase_keyword_matches_lowercase_occupation(self):
        p = _make("p1", 30, "F", occupation="teacher")
        f = PersonaFilter(occupation_contains=frozenset(["TEACHER"]))
        assert f.matches(p)

    def test_mixed_case_keyword_matches(self):
        p = _make("p1", 30, "M", occupation="IT Manager")
        f = PersonaFilter(occupation_contains=frozenset(["it"]))
        assert f.matches(p)

    def test_upper_occupation_lower_keyword_matches(self):
        p = _make("p1", 30, "M", occupation="DOCTOR")
        f = PersonaFilter(occupation_contains=frozenset(["doctor"]))
        assert f.matches(p)

    def test_partial_match_case_insensitive(self):
        p = _make("p1", 28, "F", occupation="Software Engineer")
        f = PersonaFilter(occupation_contains=frozenset(["engineer"]))
        assert f.matches(p)

    def test_no_match_returns_false(self):
        p = _make("p1", 28, "F", occupation="teacher")
        f = PersonaFilter(occupation_contains=frozenset(["doctor"]))
        assert not f.matches(p)


class TestSampleToResult:
    def test_returns_sample_result_type(self):
        result = sample_to_result(SAMPLE_PERSONAS, 3, seed=42)
        assert isinstance(result, SampleResult)

    def test_matched_count_reflects_input_size(self):
        result = sample_to_result(SAMPLE_PERSONAS, 3, seed=42)
        assert result.matched_count_before_sample == len(SAMPLE_PERSONAS)

    def test_sample_size_reflects_requested(self):
        result = sample_to_result(SAMPLE_PERSONAS, 3, seed=42)
        assert result.sample_size == 3
        assert len(result.rows) == 3

    def test_sample_size_exceeds_population_returns_all(self):
        result = sample_to_result(SAMPLE_PERSONAS, 100, seed=42)
        assert len(result.rows) == len(SAMPLE_PERSONAS)
        assert result.sample_size == len(SAMPLE_PERSONAS)

    def test_empty_population_returns_empty_result(self):
        result = sample_to_result([], 5, seed=42)
        assert result.rows == []
        assert result.matched_count_before_sample == 0
        assert result.sample_size == 0

    def test_seed_determinism(self):
        a = sample_to_result(SAMPLE_PERSONAS, 3, seed=42)
        b = sample_to_result(SAMPLE_PERSONAS, 3, seed=42)
        assert [p.persona_id for p in a.rows] == [p.persona_id for p in b.rows]

    def test_different_seeds_may_differ(self):
        a = sample_to_result(SAMPLE_PERSONAS, 3, seed=1)
        b = sample_to_result(SAMPLE_PERSONAS, 3, seed=999)
        assert len(a.rows) == 3 and len(b.rows) == 3

    def test_sampling_seed_stored(self):
        result = sample_to_result(SAMPLE_PERSONAS, 3, seed=77)
        assert result.sampling_seed == 77

    def test_no_duplicate_in_sample(self):
        result = sample_to_result(SAMPLE_PERSONAS, 4, seed=42)
        ids = [p.persona_id for p in result.rows]
        assert len(ids) == len(set(ids))

    def test_negative_sample_size_raises(self):
        with pytest.raises(ValueError):
            sample_to_result(SAMPLE_PERSONAS, -1, seed=42)

    def test_zero_sample_size_raises(self):
        with pytest.raises(ValueError):
            sample_to_result(SAMPLE_PERSONAS, 0, seed=42)

    def test_results_sorted_by_persona_id(self):
        result = sample_to_result(SAMPLE_PERSONAS, 3, seed=42)
        ids = [p.persona_id for p in result.rows]
        assert ids == sorted(ids)


class TestSampleIterableToResult:
    def test_streaming_sample_tracks_matched_count(self):
        result = sample_iterable_to_result(
            iter(SAMPLE_PERSONAS),
            PersonaFilter(state=frozenset(["NY"])),
            sample_size=10,
            seed=42,
        )
        assert result.matched_count_before_sample == 2
        assert result.sample_size == 2
        assert [p.persona_id for p in result.rows] == ["p1", "p4"]

    def test_streaming_sample_is_deterministic(self):
        personas = [_make(f"p{i:03d}", 20 + i, "F" if i % 2 else "M") for i in range(100)]
        a = sample_iterable_to_result(iter(personas), PersonaFilter(), sample_size=10, seed=7)
        b = sample_iterable_to_result(iter(personas), PersonaFilter(), sample_size=10, seed=7)
        assert [p.persona_id for p in a.rows] == [p.persona_id for p in b.rows]
        assert a.matched_count_before_sample == 100

    def test_streaming_sample_empty_match(self):
        result = sample_iterable_to_result(
            iter(SAMPLE_PERSONAS),
            PersonaFilter(age_min=100),
            sample_size=5,
            seed=42,
        )
        assert result.rows == []
        assert result.matched_count_before_sample == 0
        assert result.sample_size == 0

    def test_streaming_sample_rejects_non_positive_size(self):
        with pytest.raises(ValueError):
            sample_iterable_to_result(iter(SAMPLE_PERSONAS), PersonaFilter(), 0, seed=42)


class TestPreviewFirstN:
    def test_returns_first_n_items(self):
        data = list(range(50))
        result = preview_first_n(data, n=30)
        assert result == list(range(30))

    def test_shorter_than_n_returns_all(self):
        data = list(range(10))
        result = preview_first_n(data, n=30)
        assert result == list(range(10))

    def test_default_n_is_30(self):
        data = list(range(100))
        result = preview_first_n(data)
        assert len(result) == 30

    def test_n_zero_returns_empty(self):
        data = list(range(10))
        result = preview_first_n(data, n=0)
        assert result == []

    def test_empty_input_returns_empty(self):
        result = preview_first_n([], n=30)
        assert result == []

    def test_works_with_persona_objects(self):
        result = preview_first_n(SAMPLE_PERSONAS, n=3)
        assert len(result) == 3
        assert all(isinstance(p, Persona) for p in result)
