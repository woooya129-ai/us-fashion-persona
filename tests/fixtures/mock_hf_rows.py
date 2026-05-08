"""Synthetic USA HF-like rows.

These rows are hand-written test data, not copied Hugging Face rows.
"""

from tests.fixtures.mock_personas import ALL_MOCK_PERSONAS


def _row(
    idx: int,
    *,
    age: int,
    sex: str,
    city: str,
    state: str,
    zipcode: str,
    occupation: str,
    marital_status: str = "single",
    education_level: str = "bachelor's degree",
    bachelors_field: str = "business",
) -> dict:
    return {
        "uuid": f"11111111-{idx:04d}-4000-8000-{idx:012d}",
        "professional_persona": f"Works as a {occupation} in {city}.",
        "sports_persona": "Exercises weekly and watches local sports.",
        "arts_persona": "Enjoys neighborhood arts events and music.",
        "travel_persona": "Takes short domestic trips during holidays.",
        "culinary_persona": "Looks for practical meals and local restaurants.",
        "persona": f"A {age}-year-old {occupation} living in {city}, {state}.",
        "cultural_background": f"Lives in {city} and follows local retail and community trends.",
        "skills_and_expertise": f"{occupation}, communication, planning",
        "skills_and_expertise_list": f"{occupation}|communication|planning",
        "hobbies_and_interests": "shopping, fitness, streaming",
        "hobbies_and_interests_list": "shopping|fitness|streaming",
        "career_goals_and_ambitions": "Wants steady career growth and better work-life balance.",
        "sex": sex,
        "age": age,
        "marital_status": marital_status,
        "education_level": education_level,
        "bachelors_field": bachelors_field,
        "occupation": occupation,
        "city": city,
        "state": state,
        "zipcode": zipcode,
        "country": "United States",
    }


MOCK_HF_ROWS: list[dict] = [
    *ALL_MOCK_PERSONAS,
    _row(4, age=29, sex="F", city="Seattle", state="WA", zipcode="98101", occupation="buyer"),
    _row(
        5, age=36, sex="M", city="Phoenix", state="AZ", zipcode="85004", occupation="sales manager"
    ),
    _row(6, age=51, sex="F", city="Atlanta", state="GA", zipcode="30308", occupation="nurse"),
    _row(7, age=22, sex="M", city="Denver", state="CO", zipcode="80202", occupation="student"),
    _row(
        8, age=44, sex="F", city="Miami", state="FL", zipcode="33130", occupation="restaurant owner"
    ),
    _row(9, age=39, sex="M", city="Boston", state="MA", zipcode="02118", occupation="analyst"),
    _row(10, age=58, sex="F", city="Portland", state="OR", zipcode="97205", occupation="librarian"),
    _row(11, age=31, sex="M", city="Detroit", state="MI", zipcode="48201", occupation="mechanic"),
    _row(12, age=27, sex="F", city="Nashville", state="TN", zipcode="37203", occupation="stylist"),
    _row(13, age=63, sex="M", city="Las Vegas", state="NV", zipcode="89109", occupation="retiree"),
    _row(
        14,
        age=48,
        sex="F",
        city="Minneapolis",
        state="MN",
        zipcode="55402",
        occupation="accountant",
    ),
    _row(
        15,
        age=34,
        sex="M",
        city="San Diego",
        state="CA",
        zipcode="92101",
        occupation="software engineer",
    ),
]
