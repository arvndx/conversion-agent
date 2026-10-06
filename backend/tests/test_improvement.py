import pytest
from fastapi.testclient import TestClient

from app.category_config import config_for
from app.improvement import build_improvement_plan
from app.main import app
from app.scoring import compute_total_score, simulate_total_score
from tests.test_onboarding import claimed_profile

GOOD_AUDIT = {"has_meta_description": True, "mobile_friendly": True, "load_time_ms": 700, "has_contact_info": True, "has_business_hours_listed": True}


@pytest.fixture(autouse=True)
def fresh_db(seeded_db, mutates_db):
    yield


def items(plan, kind):
    return [i for i in plan["items"] if i["kind"] == kind]


def test_each_missing_field_is_a_step_worth_its_real_points(session):
    p = claimed_profile(session)  # nothing filled in
    plan = build_improvement_plan(session, p)
    base = compute_total_score(p)["total"]
    fields = {i["field"]: i for i in items(plan, "fill_field")}
    assert set(fields) == {f["key"] for f in config_for(p).basic_fields}
    for key, item in fields.items():
        assert item["points"] == simulate_total_score(p, {key: "x"})["total"] - base > 0
    assert fields["year_started"]["label"] == "Add the year you started" and fields["year_started"]["ui_target"] == "manage-profile-details"


def test_what_is_already_done_drops_off_the_plan(session):
    p = claimed_profile(session, year_started="2010", license_number="NMLS # 1")
    p.connections = [{"platform_name": "Facebook", "is_connected": True}]
    session.add(p)
    session.commit()
    keys = {i["key"] for i in build_improvement_plan(session, p)["items"]}
    assert "year_started" not in keys and "license_number" not in keys
    assert "connect:facebook" not in keys and "connect:linkedin" in keys


def test_every_unreplied_review_is_a_step_and_the_biggest_win_comes_first(session):
    p = claimed_profile(session)
    p.reviews = [
        {"id": "r1", "reviewer_name": "Ann B.", "rating": 5, "body": "Great", "reply": None},
        {"id": "r2", "reviewer_name": "Cy D.", "rating": 4, "body": "Good", "reply": "Thank you!"},
    ]
    session.add(p)
    session.commit()
    plan = build_improvement_plan(session, p)
    replies = items(plan, "reply_review")
    assert [r["review_id"] for r in replies] == ["r1"] and replies[0]["label"] == "Reply to Ann B.'s review"
    assert replies[0]["ui_target"] == "review-r1" and replies[0]["points"] > 0
    assert [i["points"] for i in plan["items"]] == sorted((i["points"] for i in plan["items"]), reverse=True)
    assert plan["reachable_points"] == sum(i["points"] for i in plan["items"])


def test_listing_steps_exist_only_where_listings_are_not_pro_locked(session):
    mortgage = claimed_profile(session)  # Listings is Pro-only for mortgage
    assert items(build_improvement_plan(session, mortgage), "publish_listing") == []
    insurance = claimed_profile(session, name="Ryan Davis", category="Insurance Agent")  # Listings is in the common 600
    steps = items(build_improvement_plan(session, insurance), "publish_listing")
    assert steps and all(s["points"] > 0 and s["ui_target"] == "manage-listings-section" for s in steps)


def test_the_pro_preview_is_the_real_before_and_after(session):
    p = claimed_profile(session, website_url="https://c.example.test")
    p.website_audit = GOOD_AUDIT
    p.directory_listings = {"platforms": [{"name": "Zillow lender directory", "is_published": True}]}
    session.add(p)
    session.commit()
    pro = build_improvement_plan(session, p)["pro"]
    assert pro["available"] and pro["score_before"] == compute_total_score(p)["total"]
    assert pro["score_after"] == simulate_total_score(p, {"lifecycle_state": "pro"})["total"]
    assert pro["points_gained"] == 250 + 50 and pro["max_before"] == 500 and pro["max_after"] == 850
    assert pro["rank_after"] <= pro["rank_before"] <= pro["rank_total"]
    assert {s["key"] for s in pro["locked_sections"]} == {"web_analytics", "listings"}
    assert pro["slots"]["total"] == 5 and pro["slots"]["remaining"] <= 5


def test_a_pro_profile_has_no_pro_preview_but_sees_listing_steps(session):
    p = claimed_profile(session)
    p.lifecycle_state = "pro"
    session.add(p)
    session.commit()
    plan = build_improvement_plan(session, p)
    assert plan["pro"] == {"available": False, "reason": "already_pro"} and items(plan, "publish_listing")


def test_the_plan_endpoint_is_owner_only(session):
    p = claimed_profile(session)
    with TestClient(app) as client:
        assert client.get(f"/api/profiles/{p.id}/improvement-plan").status_code == 401
        client.post("/api/auth/demo-login", json={"profile_id": p.id})
        plan = client.get(f"/api/profiles/{p.id}/improvement-plan").json()
        assert plan["items"] and plan["pro"]["available"] and plan["rank"]["rank_total"] >= 1


def test_the_manage_page_lists_the_categorys_scored_fields(session):
    p = claimed_profile(session)
    with TestClient(app) as client:
        client.post("/api/auth/demo-login", json={"profile_id": p.id})
        fields = client.get(f"/api/profiles/{p.id}/manage").json()["fields"]
    assert [f["key"] for f in fields] == [f["key"] for f in config_for(p).basic_fields]
    assert {"key": "year_started", "label": "Year started"} in fields


def test_the_manage_page_gets_the_categorys_connection_and_listing_slots(session):
    mortgage = claimed_profile(session)
    insurance = claimed_profile(session, name="Ryan Davis", category="Insurance Agent")
    with TestClient(app) as client:
        client.post("/api/auth/demo-login", json={"profile_id": mortgage.id})
        slots = client.get(f"/api/profiles/{mortgage.id}/manage").json()["slots"]
        assert slots["social"] == ["Google Business Profile", "Facebook", "LinkedIn", "Twitter/X", "Instagram"]
        assert slots["directory"] == ["Zillow lender directory", "LendingTree"]  # empty listings data, but the slots are there
        client.post("/api/auth/demo-login", json={"profile_id": insurance.id})
        assert client.get(f"/api/profiles/{insurance.id}/manage").json()["slots"]["directory"] == ["Trusted Choice (independent agents)", "Yelp"]


def test_a_running_trial_cannot_be_restarted(session):
    from fastapi import HTTPException

    from app.routers.manage import perform_start_trial

    p = claimed_profile(session)
    perform_start_trial(session, p)
    first_end = p.trial_ends_at
    with pytest.raises(HTTPException) as refused:
        perform_start_trial(session, p)
    assert refused.value.status_code == 400 and p.trial_ends_at == first_end  # the clock was not reset
