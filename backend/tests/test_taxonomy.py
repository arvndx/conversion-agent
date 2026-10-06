from sqlmodel import select

from app.constants import CLAIMED_STATES, PRO_STATES
from app.models import Category, CategoryScoreSection, CategoryService, Profile, Vertical
from app.scoring import is_pro_effective
from app.slots import count_pro_slot_holders

EXPECTED_SERVICE_COUNTS = {
    "Mortgage Loan Officer": 5,
    "Mortgage Lender": 8,
    "Real Estate Agent": 5,
    "Insurance Agent": 6,
    "Dentist": 9,
}


def _category(session, name):
    return session.exec(select(Category).where(Category.name == name)).one()


def test_five_categories_across_four_verticals(session):
    assert {c.name for c in session.exec(select(Category)).all()} == set(EXPECTED_SERVICE_COUNTS)
    assert {v.name for v in session.exec(select(Vertical)).all()} == {"Mortgage", "Real Estate", "Insurance", "Healthcare"}


def test_service_lists_match_core1(session):
    for name, count in EXPECTED_SERVICE_COUNTS.items():
        category = _category(session, name)
        services = session.exec(select(CategoryService).where(CategoryService.category_id == category.id)).all()
        assert len(services) == count, name
    lender = _category(session, "Mortgage Lender")
    names = {s.name for s in session.exec(select(CategoryService).where(CategoryService.category_id == lender.id)).all()}
    assert {"Non-QM", "Bridge loan", "Construction loan", "Fixed rate mortgage"} <= names


def test_mandatory_and_basic_fields(session):
    for category in session.exec(select(Category)).all():
        assert category.mandatory_fields == ["name", "email", "phone_number", "vertical", "category", "services"]
        keys = [f["key"] for f in category.basic_fields]
        assert len(keys) == 12 and "license_number" in keys and "year_started" in keys
        assert all(f["weight"] > 0 for f in category.basic_fields)


def test_score_split_per_category(session):
    def totals(name):
        rows = session.exec(
            select(CategoryScoreSection).where(CategoryScoreSection.category_id == _category(session, name).id)
        ).all()
        full = sum(r.max_points for r in rows)
        common = sum(r.max_points for r in rows if not r.is_pro_only)
        return full, common, {r.section: r.is_pro_only for r in rows}

    for name in ("Mortgage Loan Officer", "Mortgage Lender", "Real Estate Agent", "Dentist"):
        full, common, flags = totals(name)
        assert (full, common) == (850, 500), name
        assert flags["web_analytics"] and flags["listings"]

    full, common, flags = totals("Insurance Agent")
    assert (full, common) == (850, 600)
    assert flags["web_analytics"] and not flags["listings"]  # Listings is common for insurance


def test_url_slots_split_social_and_directory(session):
    for category in session.exec(select(Category)).all():
        social = [s["platform"] for s in category.url_slots if s["kind"] == "social"]
        assert social == ["google_business_profile", "facebook", "linkedin", "x", "instagram"]
    zillow = {s["platform"] for s in _category(session, "Real Estate Agent").url_slots if s["kind"] == "directory"}
    assert zillow == {"zillow", "realtor_com", "homes_com"}
    insurance = {s["platform"] for s in _category(session, "Insurance Agent").url_slots if s["kind"] == "directory"}
    assert insurance == {"trusted_choice", "yelp"}


def test_seeded_profiles_are_linked_to_their_category(session):
    dentists = session.exec(select(Profile).where(Profile.category == "Dentist")).all()
    assert dentists and all(p.category_id and p.vertical == "Healthcare" for p in dentists)


def test_enterprise_is_pro_but_takes_no_slot(session):
    pro = session.exec(select(Profile).where(Profile.lifecycle_state == "pro")).first()
    assert "enterprise" in CLAIMED_STATES and "enterprise" in PRO_STATES
    before = count_pro_slot_holders(session, pro.category, pro.location)
    other = session.exec(
        select(Profile).where(Profile.category == pro.category, Profile.location == pro.location, Profile.lifecycle_state == "unclaimed")
    ).first()
    other.lifecycle_state = "enterprise"
    assert is_pro_effective(other)
    assert count_pro_slot_holders(session, pro.category, pro.location) == before
    session.rollback()  # leave the shared seed untouched


def test_updated_at_changes_on_update(session):
    profile = session.exec(select(Profile)).first()
    first = profile.updated_at
    profile.bio = "changed for the test"
    session.add(profile)
    session.commit()
    session.refresh(profile)
    assert profile.updated_at > first
    profile.bio = None
    session.add(profile)
    session.commit()
