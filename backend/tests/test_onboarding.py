"""Onboarding rules: the gates, the merge, the conflicts. Pages are faked (no network, no model)."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import onboarding
from app.db import engine
from app.main import app
from app.models import Profile, ProfileConflict, ProfileLink, ProfileSource
from app.scraping import runner
from app.scraping.fetch import FetchResult


@pytest.fixture(autouse=True)
def fresh_db(seeded_db, mutates_db):
    onboarding.set_extractor(None)  # no model calls; main.py registers the real one at import
    yield
    onboarding.set_extractor(None)


def claimed_profile(session, name="Chuck Tegano", category="Mortgage Loan Officer", **kw):
    from app.models import Category

    cat = session.exec(select(Category).where(Category.name == category)).one()
    p = Profile(name=name, category=category, category_id=cat.id, vertical="Mortgage", location="", email=f"{name.split()[0].lower()}@t.test",
                phone_number="(732) 317-0735", lifecycle_state="claimed", services=["fha_home_loan"], reviews=[], connections=[], **kw)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def add_source(session, profile, url, status="confirmed", **kw):
    s = ProfileSource(profile_id=profile.id, url=url, status=status, **kw)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def done_source(session, profile, url, extracted, platform=None, validated=True):
    return add_source(session, profile, url, status="done", platform=platform, name_validated=validated, extracted=extracted)


def code(exc, status):
    assert exc.value.status_code == status
    return exc.value.detail


# --- URLs ---------------------------------------------------------------------------------------------


def test_start_turns_known_urls_into_proposed_sources_once(session):
    p = claimed_profile(session, website_url="https://chuck.example.test")
    session.add(ProfileLink(profile_id=p.id, platform="facebook", url="https://facebook.com/chuck"))
    session.add(ProfileLink(profile_id=p.id, platform="zillow", url="http://127.0.0.1/evil"))  # internal: never proposed
    session.add(ProfileLink(profile_id=p.id, platform="linkedin", url="https://www.linkedin.com/in/chuck/"))  # never read: no card
    session.commit()
    assert onboarding.start(session, p) == 2
    assert onboarding.start(session, p) == 0  # idempotent
    rows = session.exec(select(ProfileSource).where(ProfileSource.profile_id == p.id)).all()
    assert {r.status for r in rows} == {"proposed"} and len(rows) == 2


def test_nothing_proposed_is_scraped_until_the_user_confirms(session, monkeypatch):
    p = claimed_profile(session)
    s = add_source(session, p, "https://chuck.example.test", status="proposed")
    fetched = []

    async def fake(url, scrolls=0):
        fetched.append(url)
        return FetchResult(url, html="<html><body>" + "Chuck Tegano " * 50 + "</body></html>", status=200)

    monkeypatch.setattr(runner, "fetch_page", fake)
    assert onboarding.scrape_confirmed(session, p) == [] and fetched == []
    onboarding.decide(session, p, s.id, "confirm")
    out = onboarding.scrape_confirmed(session, p)
    assert fetched == ["https://chuck.example.test"] and out[0]["status"] == "done"


def test_deny_confirm_and_labels(session):
    p = claimed_profile(session)
    a, b = add_source(session, p, "https://a.example.test", status="proposed"), add_source(session, p, "https://b.example.test", status="proposed")
    assert onboarding.decide(session, p, a.id, "deny").status == "denied"
    confirmed = onboarding.decide(session, p, b.id, "confirm", label="Zillow lender directory")
    assert confirmed.status == "confirmed" and confirmed.platform == "zillow"
    link = session.exec(select(ProfileLink).where(ProfileLink.profile_id == p.id, ProfileLink.url == b.url)).one()
    assert link.confirmed
    with pytest.raises(HTTPException) as bad:
        onboarding.decide(session, p, a.id, "maybe")
    assert code(bad, 400)


def test_candidates_validate_dedupe_and_clamp_confidence(session):
    p = claimed_profile(session)
    add_source(session, p, "https://www.yelp.com/biz/chuck/", status="proposed")
    out = onboarding.propose_candidates(session, p, [
        {"url": "https://yelp.com/biz/chuck", "label": "Yelp profile", "confidence_percent": 95},   # already listed (www / slash)
        {"url": "https://www.linkedin.com/in/chuck", "label": "LinkedIn profile", "confidence_percent": 95},  # never read
        {"url": "https://www.zillow.com/lender-profile/chuck", "label": "Zillow profile", "confidence_percent": 140},
        {"url": "http://localhost:8000/api/x", "confidence_percent": 90},                                 # internal
        {"url": "javascript:alert(1)", "confidence_percent": 90},
        {"url": "https://yelp.com/biz/other", "confidence_percent": "high"},
    ])
    assert [a["url"] for a in out["added"]] == ["https://www.zillow.com/lender-profile/chuck", "https://yelp.com/biz/other"]
    assert out["added"][0]["confidence"] == 100 and out["added"][0]["platform"] == "zillow" and out["added"][1]["confidence"] == 0
    reasons = {s["url"]: s["reason"] for s in out["skipped"]}
    assert reasons["https://yelp.com/biz/chuck"] == "already listed"
    assert "not read" in reasons["https://www.linkedin.com/in/chuck"]
    assert reasons["http://localhost:8000/api/x"] == "internal addresses are not allowed"
    assert "javascript:alert(1)" in reasons


def test_manual_url_is_confirmed_and_rejects_internal_addresses(session):
    p = claimed_profile(session)
    s = onboarding.add_manual(session, p, "https://yelp.com/biz/chuck", "Yelp profile")
    assert s.status == "confirmed" and s.platform == "yelp"
    assert onboarding.add_manual(session, p, "https://instagram.com/chuck", "Instagram profile") is None  # never read: kept as a link only
    assert session.exec(select(ProfileSource).where(ProfileSource.url == "https://instagram.com/chuck")).first() is None
    with pytest.raises(HTTPException) as bad:
        onboarding.add_manual(session, p, "http://10.1.1.1/admin", "Website")
    assert code(bad, 400)


def test_skip_drops_every_undecided_url(session):
    p = claimed_profile(session)
    add_source(session, p, "https://a.example.test", status="proposed")
    add_source(session, p, "https://b.example.test", status="confirmed")
    assert onboarding.skip_remaining_urls(session, p) == 1
    assert {s.status for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == p.id)).all()} == {"denied", "confirmed"}


# --- identity -------------------------------------------------------------------------------------------


def test_unvalidated_page_data_is_not_merged_until_the_user_confirms(session):
    p = claimed_profile(session)
    s = add_source(session, p, "https://other.example.test", status="needs_identity", raw_markdown="# Somebody Else\nA realtor.",
                   extracted={"_validation": {"validated": False}, "title": "Wrong Person"})
    assert onboarding.state(session, p)["sources"][0]["preview"].startswith("Somebody Else")
    assert onboarding.merge(session, p)["applied"] == {}  # nothing validated yet
    session.refresh(p)
    assert p.title is None
    onboarding.set_extractor(lambda md, **kw: {"title": "Loan Officer"})
    try:
        onboarding.confirm_identity(session, p, s.id, True)
    finally:
        onboarding.set_extractor(None)
    assert onboarding.merge(session, p)["applied"]["title"] == "Loan Officer"


def test_saying_not_mine_drops_the_page(session):
    p = claimed_profile(session)
    s = add_source(session, p, "https://other.example.test", status="needs_identity")
    assert onboarding.confirm_identity(session, p, s.id, False).status == "denied"
    with pytest.raises(HTTPException) as bad:
        onboarding.confirm_identity(session, p, s.id, True)
    assert code(bad, 409)


# --- merge ----------------------------------------------------------------------------------------------


def test_merge_fills_empty_fields_and_never_touches_verified_ones(session):
    p = claimed_profile(session)
    done_source(session, p, "https://chuck.example.test", {
        "name": "Charles Tegano", "phone": "(999) 999-9999", "email": "x@y.test", "services": ["Jumbo loan"],  # verified at claim: ignored
        "title": "Mortgage Loan Originator", "company_name": "AnnieMac Home Mortgage", "year_started": 2005,
        "description": "Chuck <b>guides</b> buyers.", "business_hours": "Mon-Fri 9-5",
        "license": ["NMLS # 209374"], "awards": ["Top 1%"], "service_area": ["Toms River, NJ"],
    })
    out = onboarding.merge(session, p)
    session.refresh(p)
    assert (p.name, p.phone_number, p.services) == ("Chuck Tegano", "(732) 317-0735", ["fha_home_loan"])
    assert (p.title, p.business_name, p.year_started, p.business_timing) == ("Mortgage Loan Originator", "AnnieMac Home Mortgage", "2005", "Mon-Fri 9-5")
    assert p.bio == "Chuck guides buyers." and p.license_number == "NMLS # 209374" and p.awards == "Top 1%"
    assert out["conflicts"] == [] and "title" in out["applied"]


def test_agreeing_sources_do_not_conflict_but_differing_ones_do(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"title": "Mortgage Loan Originator", "business_hours": "Monday to Friday 9am-5pm", "year_started": 2005})
    done_source(session, p, "https://b.example.test", {"title": "Mortgage Loan Originator.", "business_hours": "Mon-Sat 8-6", "year_started": 2007})
    out = onboarding.merge(session, p)
    fields = {c["field"] for c in out["conflicts"]}
    assert fields == {"business_timing", "year_started"}  # the title is the same fact, written twice
    session.refresh(p)
    assert p.title == "Mortgage Loan Originator"


def test_a_scraped_value_that_contradicts_the_profile_is_a_conflict(session):
    p = claimed_profile(session, title="Senior Loan Officer")
    done_source(session, p, "https://a.example.test", {"title": "Branch Manager"})
    out = onboarding.merge(session, p)
    conflict = session.get(ProfileConflict, out["conflicts"][0]["id"])
    assert [o["value"] for o in conflict.options] == ["Senior Loan Officer", "Branch Manager"] and conflict.options[0]["sources"] == ["Your profile"]
    session.refresh(p)
    assert p.title == "Senior Loan Officer"  # not changed until the user chooses


def test_merge_is_repeatable_and_keeps_resolved_choices(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"business_hours": "Mon-Fri 9-5"})
    done_source(session, p, "https://b.example.test", {"business_hours": "Mon-Sat 8-6"})
    first = onboarding.merge(session, p)
    onboarding.resolve(session, p, first["conflicts"][0]["id"], {"choice": 1})
    again = onboarding.merge(session, p)
    assert again["conflicts"] == []  # already resolved: not asked again
    session.refresh(p)
    assert p.business_timing == "Mon-Sat 8-6"
    assert len(session.exec(select(ProfileConflict).where(ProfileConflict.profile_id == p.id)).all()) == 1


def test_lists_are_merged_not_disputed(session):
    p = claimed_profile(session, awards="Top 1%")
    done_source(session, p, "https://a.example.test", {"awards": ["Top 1%", "President's Club"], "specialities": ["FHA", "VA"]})
    done_source(session, p, "https://b.example.test", {"awards": ["president's club", "Scotsman Award"], "specialities": ["va", "Jumbo"]})
    out = onboarding.merge(session, p)
    session.refresh(p)
    assert p.awards == "Top 1%; President's Club; Scotsman Award" and p.specialities == "FHA, VA, Jumbo" and out["conflicts"] == []


def test_untrusted_text_is_stripped_and_capped(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"title": "<script>alert(1)</script>Loan   Officer\x07", "description": "x" * 5000, "year_started": "99999"})
    onboarding.merge(session, p)
    session.refresh(p)
    assert "<" not in p.title and p.title == "alert(1) Loan Officer" and len(p.bio) == 1500 and p.year_started is None


@pytest.mark.parametrize("text,ok", [
    ("Monday–Friday, 9 AM – 5 PM", True), ("Mo-Fr 09:00-17:00", True), ("Open 24 hours", True), ("By appointment", True),
    ("Closed now", False), ("Open now", False), ("Opens 9 AM", False), ("", False),
])
def test_only_real_opening_hours_count_not_a_live_open_closed_label(text, ok):
    assert bool(onboarding.usable_hours(text)) is ok


def test_a_closed_now_label_is_not_saved_as_business_hours(session):
    p = claimed_profile(session)
    done_source(session, p, "https://maps.test", {"business_hours": "Closed now", "title": "Loan Officer"}, platform="google_business_profile")
    onboarding.merge(session, p)
    session.refresh(p)
    assert p.business_timing in (None, "") and p.title == "Loan Officer"
    assert onboarding.apply_defaults(session, p) == {"business_timing": "Monday–Friday, 9 AM – 6 PM"}  # so the default offer still applies


def test_reviews_are_not_imported_from_any_page(session):
    """Review import from Google / Facebook is switched off for now: whatever a page returns, the profile's
    reviews (and so the Reviews & Replies score) are left exactly as they were."""
    p = claimed_profile(session)
    done_source(session, p, "https://maps.google.com/x", {"title": "Loan Officer", "reviews": [{"reviewer_name": "Ann B.", "rating": 5, "text": "Great"}]},
                platform="google_business_profile")
    out = onboarding.merge(session, p)
    session.refresh(p)
    assert p.reviews == [] and "reviews_added" not in out and p.title == "Loan Officer"  # the rest of the page is still used


def _confirmed(session, p, url, platform):
    source = add_source(session, p, url, status="proposed", platform=platform)
    onboarding.decide(session, p, source.id, "confirm")
    return source


def test_confirmed_social_urls_become_connections_and_directory_urls_listings(session):
    p = claimed_profile(session)  # Mortgage Loan Officer: Zillow lender directory is one of its listing slots
    _confirmed(session, p, "https://www.facebook.com/chuck", "facebook")
    _confirmed(session, p, "https://www.zillow.com/lender-profile/chuck", "zillow")
    _confirmed(session, p, "https://chuck.example.test", "website")  # a website is neither a connection nor a listing
    assert onboarding.sync_links_to_score(session, p) == {"connections": ["Facebook"], "listings": ["Zillow lender directory"]}
    session.commit()
    session.refresh(p)
    assert p.connections == [{"platform_name": "Facebook", "is_connected": True}]
    assert p.directory_listings["platforms"] == [{"name": "Zillow lender directory", "is_published": True}]
    assert onboarding.sync_links_to_score(session, p) == {"connections": [], "listings": []}  # again: nothing new


def test_a_toggle_the_owner_set_is_never_switched_off(session):
    p = claimed_profile(session)
    p.connections = [{"platform_name": "LinkedIn", "is_connected": True}]
    session.add(p)
    session.commit()
    source = _confirmed(session, p, "https://www.facebook.com/chuck", "facebook")
    onboarding.decide(session, p, source.id, "deny")  # changed their mind: no longer a confirmed link
    assert onboarding.sync_links_to_score(session, p) == {"connections": [], "listings": []}
    session.commit()
    session.refresh(p)
    assert p.connections == [{"platform_name": "LinkedIn", "is_connected": True}]


def test_saying_not_mine_at_the_identity_check_stops_the_page_counting(session):
    p = claimed_profile(session)
    source = _confirmed(session, p, "https://www.facebook.com/someone-else", "facebook")
    source.status = "needs_identity"
    session.add(source)
    session.commit()
    onboarding.confirm_identity(session, p, source.id, False)
    assert onboarding.sync_links_to_score(session, p)["connections"] == []


def test_the_audit_comes_from_the_page_of_the_website_the_owner_kept(session):
    p = claimed_profile(session, website_url="https://chuck.example.test")
    good = {"has_meta_description": True, "mobile_friendly": True, "load_time_ms": 700, "has_contact_info": True, "has_business_hours_listed": True}
    done_source(session, p, "https://elsewhere.test", {"_audit": {"has_meta_description": False}})
    done_source(session, p, "https://www.chuck.example.test/about", {"_audit": good})  # same site (www is ignored)
    assert onboarding.apply_website_audit(session, p) is True and p.website_audit == good

    other = claimed_profile(session, name="Dana Fox", website_url="https://dana.example.test")
    done_source(session, other, "https://dana.example.test", {"_audit": good}, validated=False)  # not shown to be hers
    assert onboarding.apply_website_audit(session, other) is False and not other.website_audit


def test_completion_counts_confirmed_pages_and_the_website_audit_in_the_score(session):
    p = claimed_profile(session, website_url="https://chuck.example.test")
    good = {"has_meta_description": True, "mobile_friendly": True, "load_time_ms": 700, "has_contact_info": True, "has_business_hours_listed": True}
    done_source(session, p, "https://chuck.example.test", {"_audit": good})
    session.add(ProfileLink(profile_id=p.id, platform="facebook", url="https://www.facebook.com/chuck", confirmed=True))
    session.add(ProfileLink(profile_id=p.id, platform="zillow", url="https://www.zillow.com/lender-profile/chuck", confirmed=True))
    session.commit()
    onboarding.merge(session, p)  # as in the real flow: read pages are merged before onboarding can finish
    out = onboarding.complete(session, p)
    cats = out["score"]["categories"]
    assert cats["connections"]["earned"] == 20  # 1 of the 5 social slots
    assert cats["listings"]["earned"] == 50 and cats["listings"]["locked"]  # 1 of 2 directories, Pro-locked
    assert cats["web_analytics"]["earned"] == 250 and cats["web_analytics"]["locked"]  # all five audit checks pass
    assert out["score"]["unlock_points"] == 300  # what Pro would add


def test_found_profile_links_stay_unconfirmed(session):
    p = claimed_profile(session)
    done_source(session, p, "https://chuck.example.test", {"_page": {"links": {"linkedin": "https://linkedin.com/in/c", "youtube": "https://youtube.com/c", "x": "http://127.0.0.1/n"}}})
    assert onboarding.merge(session, p)["links_added"] == 1  # youtube is not a slot for this category; the internal one is refused
    link = session.exec(select(ProfileLink).where(ProfileLink.profile_id == p.id)).one()
    assert (link.platform, link.confirmed, link.source) == ("linkedin", False, "scrape")


# --- conflicts ------------------------------------------------------------------------------------------


def test_different_licenses_ask_which_is_real_or_keep_both(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"license": ["NMLS #12345"]})
    done_source(session, p, "https://b.example.test", {"license": ["NMLS # 12345", "NMLS #23456"]})
    out = onboarding.merge(session, p)
    conflict = session.get(ProfileConflict, out["conflicts"][0]["id"])
    assert conflict.kind == "license" and [o["value"] for o in conflict.options] == ["NMLS #12345", "NMLS #23456"]  # the first two are one license
    with pytest.raises(HTTPException) as empty:
        onboarding.resolve(session, p, conflict.id, {"keep": []})
    assert code(empty, 400)
    onboarding.resolve(session, p, conflict.id, {"keep": [0, 1]})
    session.refresh(p)
    assert p.license_number == "NMLS #12345, NMLS #23456"


def test_a_single_license_is_applied_without_asking(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"license": ["NMLS # 209374"]})
    done_source(session, p, "https://b.example.test", {"license": ["NMLS #209374"]})
    assert onboarding.merge(session, p)["conflicts"] == []
    session.refresh(p)
    assert p.license_number == "NMLS # 209374"


def test_addresses_get_primary_secondary_and_not_current(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"address": "1620 Rambler Rd, Suite 200, Bettendorf, IA 52722"})
    done_source(session, p, "https://b.example.test", {"address": "4600 E 53rd St, Davenport, IA 52807"})
    done_source(session, p, "https://c.example.test", {"address": "2201 4th Ave, Moline, IL 61265"})
    out = onboarding.merge(session, p)
    conflict = session.get(ProfileConflict, out["conflicts"][0]["id"])
    assert conflict.kind == "address" and len(conflict.options) == 3
    with pytest.raises(HTTPException) as none:
        onboarding.resolve(session, p, conflict.id, {})
    assert code(none, 400)
    onboarding.resolve(session, p, conflict.id, {"primary": 0, "secondary": [1], "manual_secondary": ["9 Elm St, Austin, TX 78701"]})
    session.refresh(p)
    assert p.address.startswith("1620 Rambler") and [a["address"] for a in p.secondary_addresses] == [
        "4600 E 53rd St, Davenport, IA 52807", "9 Elm St, Austin, TX 78701"]  # the Moline one is "not a current address"
    typed = ProfileConflict(profile_id=p.id, field_key="address", kind="address", options=[{"value": "a", "sources": []}, {"value": "b", "sources": []}])
    session.add(typed)
    session.commit()
    onboarding.resolve(session, p, typed.id, {"primary": {"manual": "77 Main St, Austin, TX 78701"}})
    session.refresh(p)
    assert p.address == "77 Main St, Austin, TX 78701"


def test_pick_one_accepts_a_choice_or_a_typed_value_and_only_once(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"title": "Loan Officer"})
    done_source(session, p, "https://b.example.test", {"title": "Branch Manager"})
    cid = onboarding.merge(session, p)["conflicts"][0]["id"]
    with pytest.raises(HTTPException) as bad:
        onboarding.resolve(session, p, cid, {"choice": 7})
    assert code(bad, 400)
    onboarding.resolve(session, p, cid, {"value": "Senior Loan Officer"})
    session.refresh(p)
    assert p.title == "Senior Loan Officer"
    with pytest.raises(HTTPException) as again:
        onboarding.resolve(session, p, cid, {"choice": 0})
    assert code(again, 409)


def test_conflicts_of_other_profiles_cannot_be_touched(session):
    mine, theirs = claimed_profile(session), claimed_profile(session, name="Other Person")
    done_source(session, theirs, "https://a.example.test", {"title": "A"})
    done_source(session, theirs, "https://b.example.test", {"title": "B"})
    cid = onboarding.merge(session, theirs)["conflicts"][0]["id"]
    with pytest.raises(HTTPException) as bad:
        onboarding.resolve(session, mine, cid, {"choice": 0})
    assert code(bad, 404)


# --- fields, defaults, completion -------------------------------------------------------------------------


def test_fields_can_be_set_by_hand_but_not_the_verified_ones(session):
    p = claimed_profile(session)
    assert onboarding.update_fields(session, p, {"specialities": "FHA, VA", "year_started": "Since 2005"}) == {"specialities": "FHA, VA", "year_started": "2005"}
    for bad_field in ("name", "email", "phone_number", "services"):
        with pytest.raises(HTTPException) as bad:
            onboarding.update_fields(session, p, {bad_field: "x"})
        assert code(bad, 400)
    with pytest.raises(HTTPException) as unknown:
        onboarding.update_fields(session, p, {"hobbies": "golf"})  # not a basic field for this category
    assert code(unknown, 400)


def test_default_business_hours_fill_only_when_empty(session):
    p = claimed_profile(session)
    assert onboarding.apply_defaults(session, p) == {"business_timing": "Monday–Friday, 9 AM – 6 PM"}
    assert onboarding.apply_defaults(session, p) == {}


def test_location_is_derived_from_the_address():
    assert onboarding.derive_location("1425 Artesia Blvd Ste 18, Gardena, CA 90248, United States") == "Gardena, CA"
    assert onboarding.derive_location("37 Main St, Salem, OR") == "Salem, OR"
    assert onboarding.derive_location("somewhere") is None


def test_completion_is_blocked_until_everything_is_settled(session):
    p = claimed_profile(session)
    proposed = add_source(session, p, "https://a.example.test", status="proposed")
    with pytest.raises(HTTPException) as blocked:
        onboarding.complete(session, p)
    detail = code(blocked, 409)
    assert detail["code"] == "onboarding_blocked" and "waiting for your yes or no" in detail["blockers"][0]

    onboarding.decide(session, p, proposed.id, "confirm")
    assert any("not been read" in b for b in onboarding.blockers(session, p))
    s = session.get(ProfileSource, proposed.id)
    s.status, s.name_validated, s.extracted = "done", True, {"title": "A"}
    session.add(s)
    session.add(ProfileSource(profile_id=p.id, url="https://z.example.test", status="needs_identity"))
    session.commit()
    assert any("confirm they are yours" in b for b in onboarding.blockers(session, p)) and any("not been merged" in b for b in onboarding.blockers(session, p))


def test_complete_sets_location_defaults_score_and_rank(session):
    p = claimed_profile(session, address="1425 Artesia Blvd, Gardena, CA 90248")
    out = onboarding.complete(session, p)
    session.refresh(p)
    assert out["completed"] and out["location"] == "Gardena, CA" == p.location
    assert p.onboarding_completed_at and p.business_timing and out["rank_position"] >= 1 and out["score"]["max_possible"] == 500
    with pytest.raises(HTTPException) as again:
        onboarding.complete(session, p)
    assert code(again, 409)  # already complete: no further changes


def test_unclaimed_profiles_cannot_onboard(session):
    p = claimed_profile(session)
    p.lifecycle_state = "unclaimed"
    session.add(p)
    session.commit()
    with pytest.raises(HTTPException) as bad:
        onboarding.start(session, p)
    assert code(bad, 409)


def test_stage_follows_the_flow(session):
    p = claimed_profile(session)
    assert onboarding.stage(session, p) == "no_urls"
    a = add_source(session, p, "https://a.example.test", status="proposed")
    assert onboarding.stage(session, p) == "confirm_urls"
    onboarding.decide(session, p, a.id, "confirm")
    assert onboarding.stage(session, p) == "ready_to_scrape"
    a = session.get(ProfileSource, a.id)
    a.status, a.name_validated, a.extracted = "done", True, {"title": "T"}
    session.add(a)
    session.commit()
    assert onboarding.stage(session, p) == "merge"
    onboarding.merge(session, p)
    assert onboarding.stage(session, p) == "fields"
    assert "onboarding: stage=fields" in onboarding.summary_line(session, p)


# --- REST ------------------------------------------------------------------------------------------------


def test_onboarding_routes_need_the_owners_own_session_even_for_an_unclaimed_profile(session):
    p = claimed_profile(session)
    p.lifecycle_state = "unclaimed"  # unclaimed profiles are public elsewhere; their onboarding is not
    session.add(p)
    session.commit()
    with TestClient(app) as client:
        for method, path in (("get", ""), ("post", "/start"), ("post", "/sources/skip"), ("post", "/complete")):
            assert getattr(client, method)(f"/api/onboarding/{p.id}{path}").status_code == 401, path
        other = claimed_profile(session, name="Dana Fox")
        client.post("/api/auth/demo-login", json={"profile_id": other.id})
        assert client.get(f"/api/onboarding/{p.id}").status_code == 403  # signed in as someone else


def test_rest_routes_need_the_owner_session_and_record_decisions(session):
    p = claimed_profile(session)
    add_source(session, p, "https://a.example.test", status="proposed")
    with TestClient(app) as client:
        assert client.get(f"/api/onboarding/{p.id}").status_code == 401
        client.post("/api/auth/demo-login", json={"profile_id": p.id})
        state = client.get(f"/api/onboarding/{p.id}").json()
        assert state["stage"] == "confirm_urls" and "Website" in state["url_labels"]
        assert {"key": "license_number", "label": "License"} in state["fields"]  # the UI labels the category's fields
        sid = state["sources"][0]["id"]
        after = client.post(f"/api/onboarding/{p.id}/sources/{sid}/decision", json={"decision": "confirm"}).json()
        assert after["sources"][0]["status"] == "confirmed"
        added = client.post(f"/api/onboarding/{p.id}/sources", json={"url": "https://yelp.com/biz/chuck", "label": "Yelp profile"}).json()
        assert [s["platform"] for s in added["sources"]] == [None, "yelp"]
        assert "Instagram" not in added["url_labels"] and "Linkedin Profile" not in added["url_labels"]
        linked = client.put(f"/api/onboarding/{p.id}/links/linkedin", json={"url": "linkedin.com/in/chuck"}).json()
        assert {"platform": "linkedin", "label": "LinkedIn", "url": "https://linkedin.com/in/chuck", "confirmed": True, "found_on": "user"} in linked["link_only"]
        assert client.put(f"/api/onboarding/{p.id}/links/linkedin", json={"url": "https://facebook.com/chuck"}).status_code == 400
        assert client.put(f"/api/onboarding/{p.id}/links/zillow", json={"url": "https://zillow.com/x"}).status_code == 400
        refused = client.post(f"/api/onboarding/{p.id}/sources", json={"url": "http://localhost:9/x", "label": "Website"})
        assert refused.status_code == 400
        blocked = client.post(f"/api/onboarding/{p.id}/complete")
        assert blocked.status_code == 409 and blocked.json()["detail"]["blockers"]
        verified = client.patch(f"/api/onboarding/{p.id}/fields", json={"name": "Hacker"})
        assert verified.status_code == 400
        other = client.get("/api/onboarding/1")
        assert other.status_code in (400, 403, 404) or other.json()["profile_id"] == 1  # never someone else's data without a session


def test_nul_characters_in_a_page_do_not_lose_the_source(session, monkeypatch):
    p = claimed_profile(session)
    s = add_source(session, p, "https://nul.example.test")

    async def fake(url, scrolls=0):
        return FetchResult(url, html="<html><body>" + "Chuck Tegano\x00 loan officer. " * 30 + "</body></html>", status=200)

    monkeypatch.setattr(runner, "fetch_page", fake)
    out = onboarding.scrape_confirmed(session, p)
    assert out[0]["status"] == "done"
    session.expire_all()  # the runner wrote through its own session
    assert "\x00" not in session.get(ProfileSource, s.id).raw_markdown


def test_a_failing_extractor_is_reported_not_swallowed(session, monkeypatch):
    p = claimed_profile(session)
    add_source(session, p, "https://x.example.test")

    async def fake(url, scrolls=0):
        return FetchResult(url, html="<html><body>" + "Chuck Tegano loan officer. " * 30 + "</body></html>", status=200)

    def broken(markdown, **kw):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(runner, "fetch_page", fake)
    onboarding.set_extractor(broken)
    out = onboarding.scrape_confirmed(session, p)
    assert out[0]["status"] == "done" and "ANTHROPIC_API_KEY" in out[0]["error"]


@pytest.mark.parametrize("a,b,expected", [
    ("1425 Artesia Blvd Suite 18, Gardena, CA 90248, United States", "1425 Artesia Blvd Ste 18, Gardena, CA 90248, United States", True),
    ("1425 Artesia Blvd Suite 18, Gardena, CA 90248, United States", "1425 Artesia Blvd Suite 18, Gardena, CA, United States, California", True),
    ("1620 Rambler Rd, Suite 200, Bettendorf, IA 52722", "1620 Rambler Road, Bettendorf, Iowa", True),
    ("37-G Calumet Pkwy #201, Newnan, GA 30263", "37 G Calumet Parkway Suite 201, Newnan, GA", True),
    ("1620 Rambler Rd, Suite 200, Bettendorf, IA 52722", "4600 E 53rd St, Davenport, IA 52807", False),
    ("2201 4th Ave, Moline, IL 61265", "2201 4th Ave, Davenport, IA 52807", False),   # same street number, different city
    ("1425 Artesia Blvd, Gardena, CA", "1427 Artesia Blvd, Gardena, CA", False),     # next-door building
])
def test_the_same_address_written_differently_is_not_a_conflict(a, b, expected):
    assert onboarding._same_address(a, b) is expected


def test_two_spellings_of_one_address_do_not_raise_a_conflict(session):
    p = claimed_profile(session)
    done_source(session, p, "https://a.example.test", {"address": "1425 Artesia Blvd Suite 18, Gardena, CA 90248, United States"})
    done_source(session, p, "https://b.example.test", {"address": "1425 Artesia Blvd Suite 18, Gardena, CA, United States, California"})
    assert onboarding.merge(session, p)["conflicts"] == []
    session.refresh(p)
    assert p.address.startswith("1425 Artesia Blvd Suite 18")


# --- platforms that are never read ------------------------------------------------------------------------


def test_never_read_platforms_have_no_card_but_the_owner_can_give_the_link_and_it_counts(session):
    p = claimed_profile(session, website_url="https://chuck.example.test")
    session.add(ProfileLink(profile_id=p.id, platform="linkedin", url="https://www.linkedin.com/in/chuck/"))
    session.commit()
    onboarding.start(session, p)
    assert {s.platform for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == p.id)).all()} == {"website"}
    row = next(x for x in onboarding.state(session, p)["link_only"] if x["platform"] == "linkedin")
    assert row["url"] == "https://www.linkedin.com/in/chuck/" and row["confirmed"] is False  # known, waiting for the owner
    assert not any(c.get("is_connected") for c in (p.connections or []) if "LinkedIn" in str(c))

    onboarding.set_link(session, p, "linkedin", "https://www.linkedin.com/in/chuck-tegano")
    session.refresh(p)
    assert any(c["platform_name"] == "LinkedIn" and c["is_connected"] for c in p.connections)  # counts toward Connections
    row = next(x for x in onboarding.state(session, p)["link_only"] if x["platform"] == "linkedin")
    assert row["confirmed"] is True and row["url"].endswith("chuck-tegano")

    onboarding.set_link(session, p, "linkedin", "")  # "not mine": declined, so it is not asked about again
    row = next(x for x in onboarding.state(session, p)["link_only"] if x["platform"] == "linkedin")
    assert row["url"] is None and row["confirmed"] is False
    done_source(session, p, "https://chuck.example.test", {"_page": {"links": {"linkedin": "https://linkedin.com/in/chuck-tegano"}}})
    onboarding.merge(session, p)  # the page links to it again: a declined link is not offered a second time
    assert next(x for x in onboarding.state(session, p)["link_only"] if x["platform"] == "linkedin")["url"] is None


def test_a_link_must_match_its_platform_and_be_public(session):
    p = claimed_profile(session)
    for platform, url in [("linkedin", "https://facebook.com/chuck"), ("x", "https://instagram.com/chuck"), ("instagram", "http://10.0.0.1/x")]:
        with pytest.raises(HTTPException) as bad:
            onboarding.set_link(session, p, platform, url)
        assert code(bad, 400)
    with pytest.raises(HTTPException) as bad:
        onboarding.set_link(session, p, "zillow", "https://zillow.com/x")  # a readable platform goes through the cards
    assert code(bad, 400)
    assert onboarding.set_link(session, p, "x", "x.com/chuck").url == "https://x.com/chuck"


def test_never_read_platforms_are_not_offered_as_url_labels(session):
    p = claimed_profile(session)
    labels = onboarding.url_label_choices(p)
    assert "Website" in labels and "Facebook" in labels
    assert not any(any(w in l.lower() for w in ("linkedin", "instagram", "twitter")) for l in labels)


def test_only_listed_sites_are_read_but_any_ordinary_website_is(session):
    from app.scraping.policy import can_read
    assert all(can_read(x) for x in (None, "website", "other", "google_business_profile", "facebook", "zillow", "yelp", "healthgrades"))
    assert not any(can_read(x) for x in ("linkedin", "instagram", "x", "youtube"))  # skip list, and a named site that is on neither list
    p = claimed_profile(session)
    out = onboarding.propose_candidates(session, p, [
        {"url": "https://www.youtube.com/@chuck", "label": "YouTube", "confidence_percent": 80},
        {"url": "https://chuck-loans.example.test", "label": "Personal website", "confidence_percent": 80},
    ])
    assert [a["url"] for a in out["added"]] == ["https://chuck-loans.example.test"]
    assert "not on the list" in out["skipped"][0]["reason"]
    with pytest.raises(HTTPException) as bad:
        onboarding.add_manual(session, p, "https://www.youtube.com/@chuck", "Website")
    assert code(bad, 400)


# --- reading in the background, live progress ---------------------------------------------------------------


def test_start_scrape_reserves_the_pages_so_overlapping_batches_never_read_one_twice(session, monkeypatch):
    p = claimed_profile(session)
    first = add_source(session, p, "https://a.example.test")
    batches = []
    monkeypatch.setattr(onboarding, "SCRAPE_IN_BACKGROUND", True)
    monkeypatch.setattr(onboarding, "_scrape_batch", lambda profile_id, ids, person, services: batches.append(ids))

    started = onboarding.start_scrape(session, p)
    assert [s.id for s in started] == [first.id] and (started[0].status, started[0].phase) == ("scraping", "queued")
    assert onboarding.start_scrape(session, p) == []  # nothing new is confirmed: the first batch is not taken again

    second = add_source(session, p, "https://b.example.test")  # confirmed while the first batch is still reading
    assert [s.id for s in onboarding.start_scrape(session, p)] == [second.id]
    import time
    for _ in range(50):
        if len(batches) == 2:
            break
        time.sleep(0.02)
    assert batches == [[first.id], [second.id]]


def test_a_source_reports_each_phase_while_it_is_read_and_none_when_finished(session, monkeypatch):
    p = claimed_profile(session)
    s = add_source(session, p, "https://chuck.example.test")
    seen = []

    async def fake_fetch(url, scrolls=0):
        session.expire_all()
        seen.append(session.get(ProfileSource, s.id).phase)  # still "opening" while the page is being fetched
        return FetchResult("u", html="<html><body><h1>Chuck Tegano</h1><p>Loans in NJ " + "x" * 300 + "</p></body></html>", status=200)

    def extractor(markdown, **kw):
        session.expire_all()
        seen.append(session.get(ProfileSource, s.id).phase)
        return {"title": "Loan Officer", "phone": "(732) 317-0735"}

    monkeypatch.setattr(runner, "fetch_page", fake_fetch)
    onboarding.set_extractor(extractor)
    onboarding.scrape_confirmed(session, p)
    session.expire_all()
    row = session.get(ProfileSource, s.id)
    assert seen == ["opening", "extracting"] and row.status == "done" and row.phase is None


def test_a_read_page_shows_what_was_found_and_an_unread_one_does_not(session):
    p = claimed_profile(session)
    done_source(session, p, "https://chuck.example.test", {"title": "Loan Officer", "phone": "(732) 317-0735", "services": ["FHA", "VA"], "_page": {"title": "x"}})
    add_source(session, p, "https://other.example.test", status="needs_identity", extracted={"title": "Someone Else"}, name_validated=False)
    rows = {r["host"]: r for r in onboarding.state(session, p)["sources"]}
    found = {h["label"]: h["value"] for h in rows["chuck.example.test"]["highlights"]}
    assert found == {"Title": "Loan Officer", "Phone": "(732) 317-0735", "Services": "FHA, VA"}
    assert "highlights" not in rows["other.example.test"]  # a page that is not confirmed as theirs shows no data


def test_a_never_read_link_found_by_search_is_kept_once_for_the_owner_to_confirm(session):
    p = claimed_profile(session)
    out = onboarding.propose_candidates(session, p, [{"url": "https://www.linkedin.com/in/chuck-tegano", "label": "LinkedIn profile", "confidence_percent": 90}])
    assert out["added"] == [] and "saved as a link" in out["skipped"][0]["reason"]
    link = session.exec(select(ProfileLink).where(ProfileLink.profile_id == p.id)).one()
    assert (link.platform, link.confirmed, link.source) == ("linkedin", False, "search")
    again = onboarding.propose_candidates(session, p, [{"url": "https://linkedin.com/in/someone-else", "label": "LinkedIn profile", "confidence_percent": 50}])
    assert "already have it" in again["skipped"][0]["reason"]
    assert len(session.exec(select(ProfileLink).where(ProfileLink.profile_id == p.id)).all()) == 1
    row = next(x for x in onboarding.state(session, p)["link_only"] if x["platform"] == "linkedin")
    assert row["confirmed"] is False and row["found_on"] == "search"


def test_google_hours_for_a_single_day_are_not_taken_as_the_week(session):
    from app.onboarding import partial_week
    assert partial_week("Wednesday 8 am–8 pm") and partial_week("Tuesday 8 am–8 pm")
    assert not partial_week("Monday-Sunday: 8 AM–8 PM") and not partial_week("Mon-Fri 9-5") and not partial_week("Mon, Tue, Wed 9-5")
    p = claimed_profile(session)
    done_source(session, p, "https://antonioatoche.test", {"business_hours": "Monday-Sunday: 8 AM–8 PM"}, platform="website")
    done_source(session, p, "https://www.google.com/maps/place/x", {"business_hours": "Wednesday 8 am–8 pm"}, platform="google_business_profile")
    out = onboarding.merge(session, p)
    assert p.business_timing == "Monday-Sunday: 8 AM–8 PM" and not any(c["field"] == "business_timing" for c in out["conflicts"])


def test_the_read_route_starts_only_the_confirmed_pages_and_a_page_shows_everything_it_gave(session, monkeypatch):
    p = claimed_profile(session)
    add_source(session, p, "https://a.example.test", status="confirmed")
    proposed = add_source(session, p, "https://b.example.test", status="proposed")
    done_source(session, p, "https://c.example.test", {"title": "Loan Officer", "description": "Helping families.", "services": ["FHA", "VA"], "links": {"x": "https://x.com/a"}, "_page": {"title": "t"}})

    async def fake_fetch(url, scrolls=0):
        return FetchResult("u", html="<html><body><h1>Chuck Tegano</h1>" + "<p>Loans " * 80 + "</body></html>", status=200)

    monkeypatch.setattr(runner, "fetch_page", fake_fetch)
    with TestClient(app) as client:
        assert client.post(f"/api/onboarding/{p.id}/read").status_code == 401
        client.post("/api/auth/demo-login", json={"profile_id": p.id})
        state = client.post(f"/api/onboarding/{p.id}/read").json()
    rows = {r["host"]: r for r in state["sources"]}
    assert rows["a.example.test"]["status"] in ("done", "needs_identity") and rows["b.example.test"]["status"] == "proposed"
    details = {d["label"]: d["value"] for d in rows["c.example.test"]["details"]}
    assert details == {"Title": "Loan Officer", "About": "Helping families.", "Services": "FHA, VA"}  # no links, no internals
