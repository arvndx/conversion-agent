"""The actions and tools read from the tables: the category bundle carries each action's steps and the conv_tool rows they
name; the links are fields in special_fields; the way each action is completed for a business is chosen in code; the agent
is offered the tools the steps name and told how to complete each action.
Run from the app folder: uv run pytest tests/test_action_plan.py"""

import copy
from datetime import date, datetime, timezone

import psycopg
import pytest

from pipeline import claims
from pipeline.action_plan import resolved_actions
from pipeline.agent import build_system
from pipeline.load_chat import DATABASE_URL
from shared.bundle_tables import load_category, load_customer
from tools.agent_tools import tool_schemas

PROFESSIONALS = {   # by the business's first demo domain
    "broker": ("broker-demo-1.example", "gcid:mortgage_broker"),
    "lender": ("demo-lender-1.example", "gcid:mortgage_lender"),
    "commercial": ("demo-commercial-1.example", "gcid:commercial_real_estate_agency"),
    "health": ("demo-health-1.example", "gcid:health_insurance_agency"),
    "diner": ("demo-diner-1.example", "gcid:american_restaurant"),
}


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        yield c


def bundles(conn, key):
    domain, gcid = PROFESSIONALS[key]
    pid = conn.execute("select professional_id from conv_domains where domain = %s", (domain,)).fetchone()[0]
    return load_category(conn, gcid), load_customer(conn, str(pid))


def route_of(category, customer, action_key):
    return next(a["route"] for a in resolved_actions(category, customer) if a["key"] == action_key)


# ---- the category bundle ----

@pytest.mark.parametrize("key", PROFESSIONALS)
def test_the_category_bundle_carries_the_actions_and_the_tools_their_steps_name(conn, key):
    category, _ = bundles(conn, key)
    assert category["actions"] and all(a["steps"] for a in category["actions"])
    named = {t for a in category["actions"] for s in a["steps"] for t in s["tools"]}
    assert {t["name"] for t in category["tools"]} == named
    assert {"get_business_info", "request_handoff"} <= named
    assert not any(t["name"] == "book_appointment" for t in category["tools"])   # the old hard-coded list is gone


def test_the_request_handoff_row_defines_the_standard_fields_and_no_tool_has_a_field_of_one_category(conn):
    restaurant, _ = bundles(conn, "diner")
    lender, _ = bundles(conn, "lender")
    row = next(t for t in restaurant["tools"] if t["name"] == "request_handoff")
    fields = row["inputs"]["properties"]["prefill"]["properties"]
    assert set(fields) >= {"name", "phone", "email", "question"} and fields["phone"]["format"] == "phone"
    assert row["inputs"] == next(t for t in lender["tools"] if t["name"] == "request_handoff")["inputs"]   # the same for every category


def test_the_bundle_does_not_change_the_table_rows(conn):
    bundles(conn, "diner")
    bundles(conn, "diner")
    before = conn.execute("select inputs from conv_tool where name = 'request_handoff'").fetchone()[0]
    restaurant, _ = bundles(conn, "diner")
    next(t for t in restaurant["tools"] if t["name"] == "request_handoff")["inputs"]["properties"]["action_key"]["enum"] = ["x"]
    assert conn.execute("select inputs from conv_tool where name = 'request_handoff'").fetchone()[0] == before


def test_the_disabled_action_is_not_in_the_bundle(conn):
    lender, _ = bundles(conn, "lender")
    assert "get_preapproved" not in {a["key"] for a in lender["actions"]}


# ---- links are fields in special_fields ----

def test_a_link_is_a_field_of_the_business_and_the_links_follow_the_steps(conn):
    _, diner = bundles(conn, "diner")
    assert diner["custom_fields"]["menu_link"] == "https://demo-diner-1.example/menu"
    assert diner["links"]["view_menu"] == diner["custom_fields"]["menu_link"]
    assert diner["chef"]["menu_url"] == "https://demo-diner-1.example/menu"
    assert "happy_hour_details" not in diner["links"]   # it provides the offers, not a link


def test_the_old_links_table_is_gone(conn):
    assert conn.execute("select to_regclass('public.conv_professional_link')").fetchone()[0] is None


# ---- the way each action is completed, chosen in code ----

def test_booking_on_means_the_booking_route(conn):
    category, customer = bundles(conn, "lender")
    assert customer["booking_enabled"] and route_of(category, customer, "schedule_loan_consultation") == "booking"


def test_booking_off_with_a_link_gives_the_link(conn):
    category, customer = bundles(conn, "broker")
    assert not customer["booking_enabled"]
    assert route_of(category, customer, "schedule_consultation") == "details"


def test_booking_off_and_no_link_means_a_handover(conn):
    category, customer = bundles(conn, "commercial")
    assert not customer["booking_enabled"] and "booking_link" not in customer["custom_fields"]
    assert route_of(category, customer, "request_property_listing_tour") == "handover"


def test_a_fact_that_is_on_record_is_given_and_one_that_is_not_hands_over(conn):
    category, customer = bundles(conn, "diner")
    assert route_of(category, customer, "happy_hour_details") == "handover"   # the demo diner has no offers
    customer = dict(customer, offers=["Half price starters 3 to 6"])
    assert route_of(category, customer, "happy_hour_details") == "details"


def test_handover_only_actions_stay_handover(conn):
    category, customer = bundles(conn, "broker")
    for key in ("get_prequalified", "request_rate_quote", "contact_broker"):
        assert route_of(category, customer, key) == "handover"


# ---- the tools the agent is offered ----

def names(category, customer):
    return {t["name"] for t in tool_schemas(category, customer)}


def test_every_business_is_offered_the_same_two_tools_whether_booking_is_on_or_off(conn):
    for key in ("broker", "lender", "commercial", "health"):
        category, customer = bundles(conn, key)
        assert names(category, customer) == {"get_business_info", "request_handoff"}, key
    category, customer = bundles(conn, "lender")
    assert names(category, dict(customer, booking_enabled=False)) == names(category, customer)


def test_the_slot_tools_and_the_retired_tools_are_not_offered(conn):
    category, customer = bundles(conn, "diner")
    assert not names(category, customer) & {"check_slot", "book", "get_services", "get_conversion_link", "propose_booking"}
    assert conn.execute("select count(*) from conv_tool where name in ('check_slot', 'book')").fetchone()[0] == 0


def test_the_tool_text_comes_from_the_table_and_the_business_fills_in_its_values(conn):
    category, customer = bundles(conn, "diner")
    schemas = {t["name"]: t for t in tool_schemas(category, customer)}
    row = conn.execute("select description from conv_tool where name = 'request_handoff'").fetchone()[0]
    assert schemas["request_handoff"]["description"] == row
    fields = schemas["get_business_info"]["input_schema"]["properties"]["field"]["enum"]
    assert "menu_link" in fields and "booking_link" in fields and "services" in fields
    assert len(fields) == len(set(fields)) and fields == sorted(fields)
    keys = schemas["request_handoff"]["input_schema"]["properties"]["action_key"]["enum"]
    assert "inquire_catering" in keys and "book_reservation" in keys and keys[-1] == "direct_handover"


def test_the_menu_tools_are_offered_to_a_business_with_a_menu(conn):
    category, customer = bundles(conn, "diner")
    assert {"search_menu", "get_menu"} <= names(category, customer)
    broker_category, broker = bundles(conn, "broker")
    assert not names(broker_category, broker) & {"search_menu", "get_menu"}


def test_the_bundle_tool_rows_are_not_changed_by_a_business(conn):
    category, customer = bundles(conn, "diner")
    before = copy.deepcopy(category["tools"])
    tool_schemas(category, customer)
    assert category["tools"] == before


# ---- what the agent is told ----

def system(category, customer):
    return build_system(category, customer, date(2026, 10, 27))


def test_the_agent_is_told_how_to_complete_each_action_for_this_business(conn):
    category, customer = bundles(conn, "broker")
    text = system(category, customer)
    assert "What visitors may ask for" in text
    line = next(l for l in text.splitlines() if l.startswith("- schedule_consultation"))
    assert "Book a Consult" in line and "get_business_info for booking_link" in line   # booking is off: the link
    rate = next(l for l in text.splitlines() if l.startswith("- request_rate_quote"))
    assert "Do not quote or estimate any rate" in rate and "request_handoff with action_key request_rate_quote" in rate
    assert "name, phone or email, question" in rate


def test_a_booking_action_is_completed_with_the_form_not_with_a_dialogue(conn):
    category, customer = bundles(conn, "diner")
    line = next(l for l in system(category, customer).splitlines() if l.startswith("- book_reservation"))
    assert "request_handoff with action_key book_reservation" in line and "name, phone or email, question" in line
    assert "check_slot" not in line and "confirmed" not in line and "Find the day" not in line


# ---- replies that claim an action was done ----

@pytest.mark.parametrize("reply", [
    "I've sent your consultation request to the broker.",
    "I have passed your details to the team.",
    "Your request has been forwarded and they will be in touch.",
    "We've just submitted it for you.",
])
def test_a_sent_claim_is_recognised(reply):
    assert claims.SENT.search(reply) and not claims.BOOKED.search(reply)


@pytest.mark.parametrize("reply", [
    "Your table is booked for Tuesday at 10:00.",
    "I've booked you in for 10:00.",
    "Your booking is confirmed. Your booking ID is 123.",
    "It has been reserved.",
])
def test_a_booked_claim_is_recognised(reply):
    assert claims.BOOKED.search(reply)


@pytest.mark.parametrize("reply", [
    "Shall I pass this to the business?",
    "I'll pass this to the team once I have your phone number.",
    "Would you like me to open the request form?",
    "Please fill in the form and the business will contact you.",
    "The business is open from 9 to 5.",
])
def test_a_question_or_a_promise_is_not_a_claim(reply):
    assert not claims.SENT.search(reply) and not claims.BOOKED.search(reply)
