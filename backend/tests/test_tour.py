import pytest

from agent import tour_content
from agent.models import AgentConversation
from agent.tools import ToolContext
from tests.test_onboarding import claimed_profile


@pytest.fixture(autouse=True)
def fresh_db(seeded_db, mutates_db):
    yield


def tour_for(session, monkeypatch, **profile_kwargs):
    monkeypatch.setattr(tour_content, "_generate_narrations", lambda data: {})  # the model's wording is not under test
    p = claimed_profile(session, **profile_kwargs)
    conversation = AgentConversation(profile_id=p.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return tour_content.build_tour_steps(ToolContext(session=session, profile=p, conversation=conversation, page_context={}))


def titles(steps):
    return {s["id"]: s["title"] for s in steps}


def test_the_tour_keeps_its_seven_stops_and_marks_only_what_is_locked_for_the_category(session, monkeypatch):
    mortgage = tour_for(session, monkeypatch)  # Website Health and Listings are both Pro-only
    assert [s["id"] for s in mortgage] == ["overview", "reviews", "profile_completion", "connections", "web_analytics", "listings", "wrap_up"]
    assert titles(mortgage)["web_analytics"].endswith("(Pro)") and titles(mortgage)["listings"].endswith("(Pro)")

    insurance = tour_for(session, monkeypatch, name="Ryan Davis", category="Insurance Agent")  # Listings is in the common 600
    assert titles(insurance)["web_analytics"].endswith("(Pro)")
    assert not titles(insurance)["listings"].endswith("(Pro)")
    assert [s["id"] for s in insurance] == [s["id"] for s in mortgage]  # the same tour, just honest per category


def test_tour_stops_point_at_this_profiles_own_pages(session, monkeypatch):
    steps = tour_for(session, monkeypatch)
    pid = steps[0]["route"].split("/")[2]
    assert steps[0]["route"] == f"/dashboard/{pid}" and steps[1]["route"] == f"/dashboard/{pid}/manage" and steps[-1]["route"] == f"/dashboard/{pid}/upgrade"
