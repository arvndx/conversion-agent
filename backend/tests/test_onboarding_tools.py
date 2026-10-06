"""The onboarding tools as the agent sees them: results are plain dicts, and the rules come back as errors."""

import pytest
from sqlmodel import select

from agent.models import AgentConversation
from agent.tools import TOOL_REGISTRY, ToolContext
from app import onboarding
from app.models import Category, Profile, ProfileConflict, ProfileLink, ProfileSource
from app.scraping import runner
from app.scraping.fetch import FetchResult


@pytest.fixture(autouse=True)
def fresh_db(seeded_db, mutates_db):
    onboarding.set_extractor(None)
    yield
    onboarding.set_extractor(None)


def make_ctx(session, **kw):
    cat = session.exec(select(Category).where(Category.name == "Real Estate Agent")).one()
    p = Profile(name="Antonio Atoche", category="Real Estate Agent", category_id=cat.id, vertical="Real Estate", location="", email="a@t.test",
                phone_number="(310) 345-1513", lifecycle_state="claimed", services=["residential_real_estate"], reviews=[], connections=[], **kw)
    session.add(p)
    session.commit()
    session.refresh(p)
    return ToolContext(session=session, profile=p, conversation=AgentConversation(profile_id=p.id), page_context={"route": f"/onboarding/{p.id}"})


def call(ctx, name, **args):
    return TOOL_REGISTRY[name].handler(ctx, args)


def test_the_onboarding_tools_are_registered_and_ui_flags_are_right():
    ui = {"present_known_urls", "present_url_candidates", "request_manual_urls", "request_identity_confirmation", "present_conflicts", "complete_onboarding"}
    quiet = {"get_onboarding_state", "scrape_confirmed_sources", "get_scrape_results", "merge_scraped_data", "apply_default_business_hours"}
    assert all(TOOL_REGISTRY[n].is_ui_action for n in ui) and not any(TOOL_REGISTRY[n].is_ui_action for n in quiet)
    for gone in ("fetch_and_extract_website", "confirm_website_url", "present_candidate_matches", "check_missing_mandatory_fields"):
        assert gone not in TOOL_REGISTRY  # the old claim-assist tools


def test_the_agent_cannot_confirm_urls_or_scrape_unconfirmed_ones(session, monkeypatch):
    ctx = make_ctx(session, website_url="https://antonioatoche.test")
    fetched = []

    async def fake(url, scrolls=0):
        fetched.append(url)
        return FetchResult(url, html="<html>" + "Antonio Atoche " * 60 + "</html>", status=200)

    monkeypatch.setattr(runner, "fetch_page", fake)
    shown = call(ctx, "present_known_urls")
    assert shown["new_cards"] == 1 and shown["waiting_for_user"][0]["status"] == "proposed"
    assert call(ctx, "scrape_confirmed_sources")["scraped"] == [] and fetched == []  # nothing confirmed, nothing read
    # no tool exists that makes the user's decisions for them
    assert not {"confirm_url", "confirm_source", "decide_source", "resolve_conflict", "deny_url", "skip_urls"} & set(TOOL_REGISTRY)

    onboarding.decide(session, ctx.profile, shown["waiting_for_user"][0]["id"], "confirm")  # the user's click, via REST
    out = call(ctx, "scrape_confirmed_sources")
    assert fetched == ["https://antonioatoche.test"] and out["scraped"][0]["status"] == "done"


def test_candidates_come_back_cleaned_and_internal_urls_are_refused(session):
    ctx = make_ctx(session)
    out = call(ctx, "present_url_candidates", candidates=[
        {"url": "https://www.zillow.com/profile/antonioatoche/", "label": "Zillow profile", "confidence_percent": 91},
        {"url": "https://www.linkedin.com/in/antonioatoche/", "label": "LinkedIn profile", "confidence_percent": 91},
        {"url": "http://169.254.169.254/latest", "label": "Website", "confidence_percent": 99},
    ])
    assert [s["host"] for s in out["shown"]] == ["zillow.com"] and out["shown"][0]["confidence"] == 91
    reasons = [n["reason"] for n in out["not_shown"]]
    assert any("LinkedIn pages are not read" in r for r in reasons) and "internal addresses are not allowed" in reasons
    assert call(ctx, "request_manual_urls")["labels"][0] == "Website"


def test_unvalidated_pages_give_the_agent_no_data(session):
    ctx = make_ctx(session)
    wrong = ProfileSource(profile_id=ctx.profile.id, url="https://other.test", status="needs_identity", name_validated=False,
                          extracted={"title": "SECRET WRONG PERSON"}, raw_markdown="Somebody else")
    right = ProfileSource(profile_id=ctx.profile.id, url="https://antonio.test", status="done", name_validated=True,
                          extracted={"title": "Broker Associate", "_page": {"title": "x"}}, platform="google_business_profile")
    session.add_all([wrong, right])
    session.commit()
    out = call(ctx, "get_scrape_results")
    assert [r["fields"] for r in out["validated_pages"]] == [{"title": "Broker Associate"}]
    assert "SECRET WRONG PERSON" not in str(out) and out["waiting_for_identity_check"][0]["status"] == "needs_identity"
    assert call(ctx, "request_identity_confirmation", source_id=wrong.id)["host"] == "other.test"
    assert "error" in call(ctx, "request_identity_confirmation", source_id=right.id)  # not waiting for a check


def test_merge_then_conflicts_then_a_refused_completion_with_reasons(session):
    ctx = make_ctx(session)
    for url, title in (("https://a.test", "Broker Associate"), ("https://b.test", "Broker")):
        session.add(ProfileSource(profile_id=ctx.profile.id, url=url, status="done", name_validated=True, extracted={"title": title, "business_hours": "Mon-Fri 9-5"}))
    session.commit()
    merged = call(ctx, "merge_scraped_data")
    assert merged["filled"] == {"business_timing": "Mon-Fri 9-5"} and [c["field"] for c in merged["conflicts"]] == ["title"]
    shown = call(ctx, "present_conflicts")
    assert shown["open"][0]["options"][0] == {"value": "Broker Associate", "seen_on": ["a.test"]}
    refused = call(ctx, "complete_onboarding")
    assert "error" in refused and any("conflicting" in b for b in refused["blockers"])
    state = call(ctx, "get_onboarding_state")
    assert state["stage"] == "conflicts" and "name" in state["verified_already"] and state["open_conflicts"][0]["field"] == "title"

    onboarding.resolve(session, ctx.profile, merged["conflicts"][0]["id"], {"choice": 0})  # the user's choice, via REST
    done = call(ctx, "complete_onboarding")
    assert done["completed"] and done["max_possible"] == 500 and done["rank_total"] >= 1
    assert "error" in call(ctx, "merge_scraped_data")  # no further changes once complete


def test_default_hours_tool(session):
    ctx = make_ctx(session)
    assert call(ctx, "apply_default_business_hours")["applied"] == {"business_timing": "Monday–Friday, 9 AM – 6 PM"}
    assert "note" in call(ctx, "apply_default_business_hours")


def test_navigation_allows_the_onboarding_page_only_for_this_profile(session):
    ctx = make_ctx(session)
    nav = TOOL_REGISTRY["navigate_to"].handler
    assert nav(ctx, {"path": f"/onboarding/{ctx.profile.id}"}) == {"path": f"/onboarding/{ctx.profile.id}"}
    assert "error" in nav(ctx, {"path": "/onboarding/1"}) and "error" in nav(ctx, {"path": "/inbox"})


def test_the_assistant_can_only_draft_bio_specialities_and_service_area(session):
    ctx = make_ctx(session)
    out = call(ctx, "propose_field_updates", fields={"bio": "A short honest bio.", "year_started": "2020", "awards": "Top Agent", "specialities": "FHA, VA"})
    assert out["fields"] == {"bio": "A short honest bio.", "specialities": "FHA, VA"}
    assert out["not_drafted"] == ["awards", "year_started"]  # facts are never invented
    refused = call(ctx, "propose_field_updates", fields={"year_started": "2020", "license_number": "X1"})
    assert "error" in refused and "fields" not in refused
    assert "error" in call(ctx, "propose_field_updates", fields={"bio": "   "})
