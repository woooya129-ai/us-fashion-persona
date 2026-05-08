import pytest

from tests.fixtures.mock_personas import (
    ALL_MOCK_PERSONAS,
    MOCK_PERSONA_1,
    MOCK_PERSONA_2,
    MOCK_PERSONA_3,
)

pytestmark = pytest.mark.no_network


@pytest.fixture
def mock_persona_1() -> dict:
    return MOCK_PERSONA_1.copy()


@pytest.fixture
def mock_persona_2() -> dict:
    return MOCK_PERSONA_2.copy()


@pytest.fixture
def mock_persona_3() -> dict:
    return MOCK_PERSONA_3.copy()


@pytest.fixture
def all_mock_personas() -> list[dict]:
    return [p.copy() for p in ALL_MOCK_PERSONAS]
