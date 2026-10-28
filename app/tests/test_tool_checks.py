"""The tools (conv_tool) and the steps of the actions (conv_action.steps): the checks, and the demo data against them.
Run from the app folder: uv run pytest tests/test_tool_checks.py"""

import copy

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL
from shared.action_steps import collect_entries, collect_words, collects_contact, extras_of
from shared.tool_checks import MATCHED_INTENTS, TRIGGERED_INTENTS, check_database, find_problems, general_problems, static_reply_problems

TOOLS = {"get_business_info": True, "check_slot": True, "book": True, "request_handoff": True}
CONTACT = {"any_of": ["phone", "email"]}
NAME = {"key": "name", "required": True}
GOOD_STEPS = [
    {"route": "booking", "tools": ["check_slot", "book"],
     "collect": [NAME, CONTACT, {"key": "date", "required": True}, {"key": "time", "required": True}]},
    {"route": "details", "tools": ["get_business_info"], "provides": ["booking_link"]},
    {"route": "handover", "tools": ["request_handoff"], "collect": [NAME, CONTACT, {"key": "question", "required": True}]},
]


def action(steps, gcid="gcid:x", key="a", enabled=True, request_type="appointment booking"):
    return {"gcid": gcid, "action_key": key, "enabled": enabled, "steps": steps, "request_type": request_type}


def test_good_steps_have_no_problems():
    assert find_problems(TOOLS, [action(GOOD_STEPS)]) == []


def test_the_older_shape_with_plain_field_names_is_still_read_as_required_fields():
    old = [{"route": "details", "tools": ["get_business_info"], "provides": ["x"]},
           {"route": "handover", "tools": ["request_handoff"], "collect": ["name", CONTACT, "question"]}]
    assert find_problems(TOOLS, [action(old)]) == []
    assert collect_entries(old[1])[0] == {"key": "name", "required": True}


@pytest.mark.parametrize("steps, expected", [
    (None, "has no steps"),
    ([], "has no steps"),
    ([{"route": "link", "tools": ["request_handoff"]}], "route must be one of"),
    ([{"route": "handover", "tools": ["send_pigeon"]}], "send_pigeon is not in conv_tool"),
    ([{"route": "handover", "tools": []}], "names no tools"),
    ([{"route": "details", "tools": ["get_business_info"], "provides": ["x"]}], "the last step must be handover"),
    ([{"route": "details", "tools": ["get_business_info"]}, {"route": "handover", "tools": ["request_handoff"]}],
     "must say what it provides"),
    ([{"route": "handover", "tools": ["request_handoff"]}, {"route": "handover", "tools": ["request_handoff"]}],
     "appears twice"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [{"any_of": ["phone"]}]}], "any_of needs two or more"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [{"key": "party_size", "type": "integer"}]}],
     "needs a description"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [{"key": "k", "type": "blob", "description": "d"}]}],
     "type must be one of"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [{"key": "budget", "description": "d"}]}],
     "type must be one of"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [{"key": "name", "required": "yes"}, CONTACT]}],
     "required must be true or false"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [CONTACT]}], "must collect a required name"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [{"key": "name", "required": False}, CONTACT]}],
     "must collect a required name"),
    ([{"route": "handover", "tools": ["request_handoff"], "collect": [NAME]}], "must collect a phone or an email"),
    ([{"route": "booking", "tools": ["request_handoff"], "collect": [NAME, {"key": "phone", "required": False}]},
      {"route": "handover", "tools": ["request_handoff"], "collect": [NAME, CONTACT]}], "must collect a phone or an email"),
])
def test_bad_steps_are_reported(steps, expected):
    problems = find_problems(TOOLS, [action(steps)])
    assert any(expected in p for p in problems), problems


def test_a_required_phone_or_an_either_group_counts_as_a_way_to_reach_the_visitor():
    phone = {"collect": [NAME, {"key": "phone", "required": True}]}
    assert collects_contact(phone) and collects_contact({"collect": [NAME, CONTACT]})
    assert not collects_contact({"collect": [NAME, {"key": "email", "required": False}]})


def test_an_optional_field_is_marked_for_the_agent_and_an_extra_field_keeps_its_description():
    step = {"collect": [NAME, CONTACT, {"key": "note", "required": False},
                        {"key": "party_size", "type": "integer", "description": "Number of guests.", "required": True}]}
    assert collect_words(step) == ["name", "phone or email", "note (optional)", "party_size (Number of guests)"]
    assert [e["key"] for e in extras_of(step)] == ["party_size"]   # note is a standard field: no type, not an extra


def test_an_enabled_action_needs_a_request_type_but_a_switched_off_one_does_not():
    assert any("has no request_type" in p for p in find_problems(TOOLS, [action(GOOD_STEPS, request_type="")]))
    assert any("has no request_type" in p for p in find_problems(TOOLS, [action(GOOD_STEPS, request_type=None)]))
    assert find_problems(TOOLS, [action(GOOD_STEPS, request_type=None, enabled=False)]) == []


def test_a_switched_off_tool_is_reported_only_for_an_enabled_action():
    off = {**TOOLS, "book": False}
    assert any("switched off" in p for p in find_problems(off, [action(GOOD_STEPS)]))
    assert not any("switched off" in p for p in find_problems(off, [action(GOOD_STEPS, enabled=False)]))


def test_a_category_must_be_able_to_answer_and_hand_over():
    only_booking = [{"route": "booking", "tools": ["check_slot", "book"]},
                    {"route": "handover", "tools": ["request_handoff"]}]
    problems = find_problems(TOOLS, [action(only_booking)])
    assert any("never name get_business_info" in p for p in problems)
    assert not any("request_handoff" in p for p in problems)


def test_an_extra_field_cannot_have_two_types_in_one_category():
    one = copy.deepcopy(GOOD_STEPS)
    one[0]["collect"].append({"key": "party_size", "type": "integer", "description": "Guests."})
    two = copy.deepcopy(GOOD_STEPS)
    two[0]["collect"].append({"key": "party_size", "type": "string", "description": "Guests."})
    assert any("two different types" in p for p in find_problems(TOOLS, [action(one, key="a"), action(two, key="b")]))
    assert find_problems(TOOLS, [action(one, gcid="gcid:x", key="a"), action(two, gcid="gcid:y", key="b")]) == []


@pytest.fixture()
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        yield c


def test_the_demo_data_passes_the_checks(conn):
    assert check_database(conn) == []


def test_every_action_has_steps_and_the_two_generic_tools_exist(conn):
    assert conn.execute("select count(*) from conv_action where steps is null").fetchone()[0] == 0
    names = [r[0] for r in conn.execute("select name from conv_tool where enabled order by name").fetchall()]
    assert names == ["get_business_info", "request_handoff"]


def test_the_lender_pre_approval_is_off_and_the_loan_consultation_uses_the_booking_link(conn):
    enabled = dict(conn.execute("select action_key, enabled from conv_action where gcid = 'gcid:mortgage_lender'").fetchall())
    assert enabled["get_preapproved"] is False and enabled["schedule_loan_consultation"] is True
    steps = conn.execute("select steps from conv_action where gcid = 'gcid:mortgage_lender' and action_key = "
                         "'schedule_loan_consultation'").fetchone()[0]
    assert [s["route"] for s in steps] == ["booking", "details", "handover"]
    assert steps[1]["provides"] == ["booking_link"]


def test_every_booking_step_asks_the_request_form_for_a_name_a_contact_and_the_request(conn):
    rows = conn.execute("select gcid, action_key, steps from conv_action where enabled").fetchall()
    for gcid, key, steps in rows:
        for step in steps:
            if step["route"] in ("booking", "handover"):
                assert step["tools"] == ["request_handoff"], (gcid, key)
                assert [e.get("key") or "either" for e in step["collect"]] == ["name", "either", "question"], (gcid, key)
                assert [e["required"] for e in step["collect"] if "key" in e] == [True, True], (gcid, key)


def test_the_disabled_action_is_not_in_the_category_bundle(conn):
    from shared.bundle_tables import load_category
    bundle = load_category(conn, "gcid:mortgage_lender")
    keys = {a["key"] for a in bundle["actions"]}
    assert "get_preapproved" not in keys and "schedule_loan_consultation" in keys


def test_general_actions_must_exist_and_only_hand_over():
    handover = [{"route": "handover", "tools": ["request_handoff"], "collect": [NAME, CONTACT]}]
    complete = [action(handover, gcid="general", key=k, request_type=k.replace("_", " ")) for k in
                ("critical_handover", "ai_down_handover", "fallback_handover", "direct_handover")]
    assert general_problems(complete) == []
    assert any("direct_handover is missing" in p for p in general_problems(complete[:3]))
    assert any("only a handover step" in p for p in general_problems([*complete[:3], action(GOOD_STEPS, gcid="general", key="direct_handover")]))
    assert find_problems(TOOLS, complete) == []   # the shared actions are not asked to name get_business_info


def _replies(n=10):
    return [f"Reply number {i} for {{customer_name}}." for i in range(n)]


def _good_static():
    rows = [("general", i, [f"phrase {i.replace('_', ' ')}"], _replies()) for i in MATCHED_INTENTS]
    return rows + [("general", i, [], _replies()) for i in TRIGGERED_INTENTS]


def test_good_fixed_replies_have_no_problems():
    assert static_reply_problems(_good_static()) == []


@pytest.mark.parametrize("change, expected", [
    (lambda r: r[1:], "the shared fixed replies are missing"),
    (lambda r: [(g, i, p, rep[:9]) if i == "greeting" else (g, i, p, rep) for g, i, p, rep in r], "needs at least 10 replies"),
    (lambda r: [(g, i, p, rep[:9] + [rep[0]]) if i == "greeting" else (g, i, p, rep) for g, i, p, rep in r],
     "replies must be different"),
    (lambda r: [(g, i, p, rep[:9] + ["Hello {name}"]) if i == "greeting" else (g, i, p, rep) for g, i, p, rep in r],
     "unknown placeholder {name}"),
    (lambda r: [(g, i, [], rep) if i == "greeting" else (g, i, p, rep) for g, i, p, rep in r], "needs at least one pattern"),
    (lambda r: [(g, i, ["oops"], rep) if i == "abuse_warning" else (g, i, p, rep) for g, i, p, rep in r], "has no patterns"),
    (lambda r: [(g, i, ["what's up"], rep) if i == "greeting" else (g, i, p, rep) for g, i, p, rep in r], "no punctuation"),
    (lambda r: [(g, i, ["Hello"], rep) if i == "greeting" else (g, i, p, rep) for g, i, p, rep in r], "no punctuation"),
    (lambda r: [(g, i, ["phrase greeting"], rep) if i == "thanks" else (g, i, p, rep) for g, i, p, rep in r], "is also used by"),
])
def test_bad_fixed_replies_are_reported(change, expected):
    problems = static_reply_problems(change(_good_static()))
    assert any(expected in p for p in problems), problems


# ---- the data in the local database: request types, general actions, fixed replies ----

CATEGORIES = ["gcid:american_restaurant", "gcid:commercial_real_estate_agency", "gcid:health_insurance_agency",
              "gcid:mortgage_broker", "gcid:mortgage_lender"]


def test_every_enabled_action_has_a_request_type_and_the_booking_ones_are_named_by_what_they_book(conn):
    labels = {(g, k): r for g, k, r in conn.execute("select gcid, action_key, request_type from conv_action where enabled").fetchall()}
    assert all(labels.values())
    assert labels[("gcid:american_restaurant", "book_reservation")] == "table booking"
    assert labels[("gcid:mortgage_broker", "schedule_consultation")] == "appointment booking"
    assert labels[("gcid:commercial_real_estate_agency", "request_property_listing_tour")] == "property tour booking"
    assert labels[("gcid:mortgage_broker", "get_prequalified")] == "direct handover"      # a handover-only action
    assert labels[("gcid:mortgage_lender", "track_loan_status")] == "business detail handover"   # details first


def test_the_four_general_actions_exist_and_a_handover_row_defaults_to_a_direct_handover(conn):
    rows = dict(conn.execute("select action_key, request_type from conv_action where gcid = 'general' and enabled").fetchall())
    assert rows == {"critical_handover": "critical handover", "ai_down_handover": "ai down handover",
                    "fallback_handover": "fallback handover", "direct_handover": "direct handover"}
    default = conn.execute("select column_default from information_schema.columns where table_name = 'conv_handover' "
                           "and column_name = 'request_type'").fetchone()[0]
    assert "direct handover" in default


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_a_category_bundle_carries_the_general_actions_and_the_fixed_replies_but_shows_no_general_chip(conn, gcid):
    from shared.bundle_tables import load_category
    bundle = load_category(conn, gcid)
    assert set(bundle["general_actions"]) == {"critical_handover", "ai_down_handover", "fallback_handover", "direct_handover"}
    assert all(a["steps"][0]["route"] == "handover" for a in bundle["general_actions"].values())
    assert not set(bundle["general_actions"]) & {a["key"] for a in bundle["actions"]}   # never offered as a business action
    assert set(MATCHED_INTENTS + TRIGGERED_INTENTS) <= set(bundle["static_replies"])
    assert all(len(r["replies"]) >= 10 for r in bundle["static_replies"].values())
    assert all(a["request_type"] for a in bundle["actions"])
    for key in ("form_intro", "request_sent", "request_not_saved", "request_not_saved_no_contact", "details_link_reply"):
        assert bundle["message_texts"][key]


def test_a_category_row_replaces_the_shared_replies_for_that_intent(conn):
    from shared.bundle_tables import load_category
    own = [f"Welcome to the diner, number {i}." for i in range(10)]
    conn.execute("insert into conv_static_reply (gcid, intent, patterns, replies) values ('gcid:american_restaurant', 'greeting', "
                 "array['hi'], %s)", (own,))
    try:
        assert load_category(conn, "gcid:american_restaurant")["static_replies"]["greeting"]["replies"] == own
        assert load_category(conn, "gcid:mortgage_broker")["static_replies"]["greeting"]["replies"] != own
    finally:
        conn.rollback()


def test_the_database_refuses_fewer_than_ten_replies(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into conv_static_reply (gcid, intent, patterns, replies) values ('general', 'test_few', '{}', %s)",
                     ([f"reply {i}" for i in range(9)],))
    conn.rollback()
