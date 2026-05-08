"""Synthetic USA persona fixture rows.

These rows are hand-written test data, not copied Hugging Face rows.
"""

MOCK_PERSONA_1: dict = {
    "uuid": "mock-001-nyc-f25",
    "professional_persona": "Works as a digital marketing associate for a fashion retailer.",
    "sports_persona": "Takes weekend Pilates classes and follows women's soccer.",
    "arts_persona": "Visits contemporary art galleries and follows street photography.",
    "travel_persona": "Plans short city trips around shopping neighborhoods and museums.",
    "culinary_persona": "Looks for plant-forward restaurants and new coffee shops.",
    "persona": "A 25-year-old fashion-aware marketer living in New York City.",
    "cultural_background": "Grew up around urban retail, creator culture, and subway commuting.",
    "skills_and_expertise": "digital marketing, social analytics, merchandising",
    "skills_and_expertise_list": "digital marketing|social analytics|merchandising",
    "hobbies_and_interests": "fashion, coffee, photography",
    "hobbies_and_interests_list": "fashion|coffee|photography",
    "career_goals_and_ambitions": "Wants to become a brand strategy lead.",
    "sex": "F",
    "age": 25,
    "marital_status": "single",
    "education_level": "bachelor's degree",
    "bachelors_field": "business",
    "occupation": "marketing associate",
    "city": "New York",
    "state": "NY",
    "zipcode": "10011",
    "country": "United States",
}

MOCK_PERSONA_2: dict = {
    "uuid": "mock-002-austin-m42",
    "professional_persona": "Works as a residential architect focused on practical family homes.",
    "sports_persona": "Cycles on weekends and follows college football.",
    "arts_persona": "Enjoys architecture photography and live music venues.",
    "travel_persona": "Visits design neighborhoods and national parks with family.",
    "culinary_persona": "Enjoys barbecue, tacos, and cooking seafood at home.",
    "persona": "A 42-year-old architect living in Austin with a preference for durable basics.",
    "cultural_background": (
        "Lives in a fast-growing city with a mix of tech, music, and outdoor culture."
    ),
    "skills_and_expertise": "architecture, CAD, project management",
    "skills_and_expertise_list": "architecture|CAD|project management",
    "hobbies_and_interests": "cycling, music, home design",
    "hobbies_and_interests_list": "cycling|music|home design",
    "career_goals_and_ambitions": "Wants to open a small residential design studio.",
    "sex": "M",
    "age": 42,
    "marital_status": "married",
    "education_level": "master's degree",
    "bachelors_field": "architecture",
    "occupation": "architect",
    "city": "Austin",
    "state": "TX",
    "zipcode": "78704",
    "country": "United States",
}

MOCK_PERSONA_3: dict = {
    "uuid": "mock-003-chicago-f33",
    "professional_persona": "Teaches middle school language arts and runs a reading club.",
    "sports_persona": "Walks daily and attends occasional basketball games.",
    "arts_persona": "Enjoys craft fairs, local theater, and handmade stationery.",
    "travel_persona": "Prefers train trips to nearby cities and family-friendly museums.",
    "culinary_persona": "Cooks practical weeknight meals and bakes on weekends.",
    "persona": "A 33-year-old teacher in Chicago who values comfort and price clarity.",
    "cultural_background": "Balances public school work, neighborhood events, and family routines.",
    "skills_and_expertise": "teaching, curriculum planning, youth mentoring",
    "skills_and_expertise_list": "teaching|curriculum planning|youth mentoring",
    "hobbies_and_interests": "reading, crafts, walking",
    "hobbies_and_interests_list": "reading|crafts|walking",
    "career_goals_and_ambitions": "Wants to build stronger literacy programs for students.",
    "sex": "F",
    "age": 33,
    "marital_status": "married",
    "education_level": "bachelor's degree",
    "bachelors_field": "education",
    "occupation": "teacher",
    "city": "Chicago",
    "state": "IL",
    "zipcode": "60614",
    "country": "United States",
}

ALL_MOCK_PERSONAS: list[dict] = [MOCK_PERSONA_1, MOCK_PERSONA_2, MOCK_PERSONA_3]
