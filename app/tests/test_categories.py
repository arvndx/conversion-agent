"""The category bundle built from the conv_ tables, for each of the five categories. Read-only.
Run from the app folder: uv run pytest tests/test_categories.py"""

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL
from shared.bundle_tables import load_category

CATEGORIES = ["gcid:mortgage_lender", "gcid:mortgage_broker", "gcid:health_insurance_agency",
              "gcid:commercial_real_estate_agency", "gcid:american_restaurant"]


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        yield c


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_every_enabled_action_is_in_the_bundle_with_its_steps_and_request_type(conn, gcid):
    bundle = load_category(conn, gcid)
    actions = conn.execute("select count(*) from conv_action where gcid = %s and enabled", (gcid,)).fetchone()[0]
    assert len(bundle["actions"]) == actions and actions > 0
    assert all(a["steps"] and a["request_type"] for a in bundle["actions"])


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_the_bundle_has_the_messages_rules_and_compliance(conn, gcid):
    bundle = load_category(conn, gcid)
    assert bundle["category_id"] == gcid.split(":", 1)[1]
    assert bundle["message_texts"]["handover_offer"]
    assert bundle["message_texts"]["form_intro"] and bundle["message_texts"]["request_sent"]
    assert bundle["never_ask"] and bundle["scoring_rules"] and bundle["abuse_rules"]
    assert bundle["compliance"]["prohibited_phrases"] is not None


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_the_default_questions_come_from_the_actions(conn, gcid):
    bundle = load_category(conn, gcid)
    assert 1 <= len(bundle["default_questions"]) <= 5


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_the_quick_actions_are_the_buttons_with_their_keys(conn, gcid):
    bundle = load_category(conn, gcid)
    keys = {a["key"] for a in bundle["actions"]}
    assert 1 <= len(bundle["quick_actions"]) <= 5 and {q["key"] for q in bundle["quick_actions"]} <= keys
    assert [q["label"] for q in bundle["quick_actions"]] == bundle["default_questions"]


def test_booking_actions_use_the_request_form_tool(conn):
    bundle = load_category(conn, "gcid:american_restaurant")
    booking = [a for a in bundle["actions"] if a["steps"][0]["route"] == "booking"]
    assert booking and all(a["steps"][0]["tools"] == ["request_handoff"] for a in booking)


def test_a_critical_topic_has_its_fixed_reply(conn):
    bundle = load_category(conn, "gcid:mortgage_lender")
    assert bundle["critical_topics"] and all(t["reply"] for t in bundle["critical_topics"])
