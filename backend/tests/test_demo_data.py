from collections import Counter

from sqlmodel import select

from app.models import Category, CategoryService, Profile, ProfileLink
from app.seed_demo_profiles import DEMO_EMAIL_DOMAIN, DEMO_PROFILES
from app.slots import count_pro_slot_holders


def _demo(session):
    return session.exec(select(Profile).where(Profile.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))).all()


def test_eight_demo_professionals_two_per_core1_category(session):
    demo = _demo(session)
    assert len(demo) == 8
    assert Counter(p.category for p in demo) == {
        "Mortgage Loan Officer": 2, "Mortgage Lender": 2, "Real Estate Agent": 2, "Insurance Agent": 2,
    }
    assert all(p.lifecycle_state == "unclaimed" for p in demo)


def test_seeded_claimed_and_pro_accounts_count_as_onboarded_but_demo_professionals_do_not(session):
    from app.constants import CLAIMED_STATES

    accounts = session.exec(select(Profile).where(Profile.lifecycle_state.in_(CLAIMED_STATES))).all()
    assert accounts and all(p.onboarding_completed_at and p.claimed_at for p in accounts)
    assert all(p.onboarding_completed_at is None for p in _demo(session))  # claiming one starts onboarding


def test_demo_professionals_hold_only_the_scraped_basics(session):
    for p in _demo(session):
        assert p.name and p.phone_number and p.email and p.vertical and p.category_id and p.services
        # left empty on purpose, for onboarding to find by scraping the URLs
        assert not any([p.bio, p.address, p.license_number, p.year_started, p.awards, p.service_area, p.specialities])


def test_demo_services_are_valid_for_their_category(session):
    for p in _demo(session):
        valid = {s.key for s in session.exec(select(CategoryService).where(CategoryService.category_id == p.category_id)).all()}
        assert set(p.services) <= valid and p.services, p.name


def test_demo_profile_links_use_the_category_url_slots(session):
    for p in _demo(session):
        category = session.get(Category, p.category_id)
        slots = {s["platform"] for s in category.url_slots} | {"website"}
        links = session.exec(select(ProfileLink).where(ProfileLink.profile_id == p.id)).all()
        assert links and all(link.platform in slots and not link.confirmed for link in links), p.name
    antonio = next(p for p in _demo(session) if p.name == "Antonio Atoche")
    platforms = {link.platform for link in session.exec(select(ProfileLink).where(ProfileLink.profile_id == antonio.id)).all()}
    assert {"website", "google_business_profile", "facebook", "linkedin", "x", "instagram", "zillow"} <= platforms


def test_no_real_email_addresses_are_stored(session):
    emails = [p.email for p in session.exec(select(Profile)).all()]
    assert all(e.endswith(("@example.com", "@example.test", f"@{DEMO_EMAIL_DOMAIN}")) for e in emails)


def test_each_demo_market_has_peers_and_a_free_pro_slot(session):
    for spec in DEMO_PROFILES:
        market = session.exec(
            select(Profile).where(Profile.category == spec["category"], Profile.location == spec["location"])
        ).all()
        states = Counter(p.lifecycle_state for p in market)
        assert len(market) >= 20, spec["name"]
        assert states["enterprise"] >= 1 and states["claimed"] >= 5
        # the demo professional can still upgrade: enterprise peers take no slot
        assert count_pro_slot_holders(session, spec["category"], spec["location"]) < 5


def test_dentists_are_kept_and_the_real_looking_extras_are_gone(session):
    dentists = session.exec(select(Profile).where(Profile.category == "Dentist")).all()
    assert len(dentists) == 38
    names = {p.name for p in session.exec(select(Profile)).all()}
    assert "Amber Ernst" not in names and "Dr. Ria Sahara" not in names
