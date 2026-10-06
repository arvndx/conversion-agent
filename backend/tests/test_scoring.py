import pytest
from sqlmodel import select

from app.category_config import CategoryConfig, SectionConfig, get_config
from app.models import Category, Profile
from app.scoring import (
    compute_profile_completion_score,
    compute_total_score,
    field_points,
    simulate_total_score,
)


def make(session, category_name, state="claimed", **kwargs):
    category = session.exec(select(Category).where(Category.name == category_name)).one()
    defaults = dict(name="Test Agent", email="t@example.test", location="Testville, TX", reviews=[], connections=[])
    defaults.update(kwargs)
    return Profile(category=category_name, category_id=category.id, lifecycle_state=state, **defaults)


def full_reviews():
    return [{"rating": 5, "reply": "thanks"} for _ in range(10)]


def test_claimed_and_pro_maximums_per_category(session):
    for name in ("Mortgage Loan Officer", "Mortgage Lender", "Real Estate Agent", "Dentist"):
        claimed = compute_total_score(make(session, name, "claimed"))
        pro = compute_total_score(make(session, name, "pro"))
        assert (claimed["max_possible"], claimed["pro_max"], pro["max_possible"]) == (500, 850, 850), name
    claimed = compute_total_score(make(session, "Insurance Agent", "claimed"))
    assert (claimed["max_possible"], claimed["pro_max"]) == (600, 850)


def test_insurance_listings_are_common_not_locked(session):
    published = {"platforms": [{"name": "Yelp", "is_published": True}, {"name": "Trusted Choice (independent agents)", "is_published": True}]}
    insurance = compute_total_score(make(session, "Insurance Agent", directory_listings=published))
    assert not insurance["categories"]["listings"]["locked"]
    assert insurance["categories"]["listings"]["earned"] == 100
    assert insurance["total"] == 100  # nothing else earned; the listings points count
    assert insurance["locked_max"] == 250  # only Website Health is Pro-locked

    mortgage_listings = {"platforms": [{"name": "Zillow lender directory", "is_published": True}, {"name": "LendingTree", "is_published": True}]}
    mortgage = compute_total_score(make(session, "Mortgage Lender", directory_listings=mortgage_listings))
    assert mortgage["categories"]["listings"]["locked"] and mortgage["total"] == 0
    assert mortgage["unlock_points"] == 100 and mortgage["locked_max"] == 350


def test_listings_follow_the_category_directory_slots(session):
    only_zillow = {"platforms": [{"name": "Zillow lender directory", "is_published": True}]}
    result = compute_total_score(make(session, "Mortgage Loan Officer", "pro", directory_listings=only_zillow))
    assert result["categories"]["listings"]["earned"] == 50
    assert result["categories"]["listings"]["opportunities"] == ["Publish your listing on LendingTree"]
    # Zillow means nothing to an insurance profile
    result = compute_total_score(make(session, "Insurance Agent", directory_listings=only_zillow))
    assert result["categories"]["listings"]["earned"] == 0


def test_connections_are_the_five_social_slots(session):
    names = ["Google Business Profile", "Facebook"]
    connections = [{"platform_name": n, "is_connected": True} for n in names]
    result = compute_total_score(make(session, "Real Estate Agent", connections=connections))
    assert result["categories"]["connections"]["earned"] == 40
    assert "Connect LinkedIn" in result["categories"]["connections"]["opportunities"]


def test_profile_completion_uses_category_fields_and_weights(session):
    profile = make(session, "Mortgage Loan Officer", license_number="NMLS 1")
    config = get_config(profile.category_id)
    points, missing = compute_profile_completion_score(profile, config)
    assert points == 8  # 1 of 12 equal-weight fields
    assert "Add your license number" not in missing and len(missing) == 11

    heavy = CategoryConfig(
        id=config.id, key=config.key, name=config.name, vertical=config.vertical, sections=config.sections,
        basic_fields=[{**f, "weight": 3 if f["key"] == "license_number" else 1} for f in config.basic_fields],
        url_slots=config.url_slots,
    )
    points, _ = compute_profile_completion_score(profile, heavy)
    assert points == round(3 / 14 * 100)


def test_field_points_match_the_weights(session):
    profile = make(session, "Insurance Agent")
    assert field_points(profile, "license_number") == 8
    assert field_points(profile, "hobbies") == 0  # not a completion field for this category
    profile.license_number = "X"
    assert field_points(profile, "license_number") == 0  # already filled


def test_section_scaling_follows_the_category_max(session):
    base = make(session, "Mortgage Lender", reviews=full_reviews())
    config = get_config(base.category_id)
    assert compute_total_score(base)["categories"]["reviews"]["earned"] == 300
    half = {**config.sections, "reviews": SectionConfig("reviews", "Reviews & Replies", 150, False, 0)}
    scaled = CategoryConfig(id=config.id, key=config.key, name=config.name, vertical=config.vertical,
                            sections=half, basic_fields=config.basic_fields, url_slots=config.url_slots)
    # compute with the scaled config by temporarily registering it
    from app import category_config

    original = category_config._by_id[config.id]
    category_config._by_id[config.id] = scaled
    try:
        assert compute_total_score(base)["categories"]["reviews"]["earned"] == 150
    finally:
        category_config._by_id[config.id] = original


def test_enterprise_unlocks_everything(session):
    result = compute_total_score(make(session, "Mortgage Lender", "enterprise"))
    assert result["max_possible"] == 850 and not any(c["locked"] for c in result["categories"].values())


def test_simulate_total_score_never_mutates_the_profile(session):
    profile = make(session, "Dentist")
    before = (profile.license_number, profile.lifecycle_state)
    simulated = simulate_total_score(profile, {"license_number": "X", "lifecycle_state": "pro"})
    assert simulated["max_possible"] == 850
    assert (profile.license_number, profile.lifecycle_state) == before


def test_unknown_category_falls_back_to_the_standard_split(session):
    profile = Profile(name="N", category="Underwater Basket Weaver", location="X", email="n@x.test",
                      lifecycle_state="claimed", reviews=[], connections=[])
    result = compute_total_score(profile)
    assert (result["max_possible"], result["pro_max"]) == (500, 850)
