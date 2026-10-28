"""The request form (pipeline/forms.py): the card built from an action's collect, the pages, the checks, the saved row and the
plain query that confirms it. No model is called. What the tests save is removed afterwards.
Run from the app folder: uv run pytest tests/test_forms.py"""

import copy
import uuid
from datetime import date, datetime, timezone

import psycopg
import pytest

from pipeline import forms
from pipeline.load_chat import DATABASE_URL, redis_client, session_key
from shared.bundle_tables import load_category, load_customer

DINER = "483dc8e7-3f03-5fbb-878b-77ee433ed0b3"
LENDER = "e5e4ebed-f138-5cc2-a554-967272decabd"
TODAY = date(2026, 10, 28)


@pytest.fixture(scope="module")
def diner():
    with psycopg.connect(DATABASE_URL) as conn:
        return {"category": load_category(conn, "gcid:american_restaurant"), "customer": load_customer(conn, DINER)}


@pytest.fixture(autouse=True)
def no_email_commit(monkeypatch):
    from pipeline import worker
    monkeypatch.setattr(worker, "send_handover_emails", lambda *args, **kwargs: 0)


@pytest.fixture()
def chat():
    from pipeline.turn import _create_session
    sid, client = str(uuid.uuid4()), redis_client()
    _create_session(client, sid, "professional", DINER, "demo-diner-1.example", datetime.now(timezone.utc), False, "", "")
    yield {"sid": sid, "client": client}
    client.delete(session_key(sid))
    client.srem("session_updates", sid)
    client.srem("open_sessions", sid)
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("delete from conv_handover where session_id = %s", (sid,))
        conn.execute("delete from conv_session where session_id = %s", (sid,))
        conn.execute("delete from conv_activity where activity_id = %s", (sid,))
        conn.commit()


def keys(form):
    return [spec["key"] for page in form["pages"] for spec in page["fields"]]


def spec(form, key):
    return next(s for page in form["pages"] for s in page["fields"] if s["key"] == key)


# ---- the card ----

def test_the_booking_action_of_a_business_with_booking_on_gives_a_form_with_the_fields_of_its_collect(diner):
    form = forms.form_for(diner["category"], diner["customer"], "book_reservation")
    assert (form["route"], form["title"], form["request_type"]) == ("booking", "Reserve a Table", "table booking")
    assert keys(form) == ["name", "phone", "email", "question"]
    assert [[s["key"] for s in page["fields"]] for page in form["pages"]] == [["name", "phone", "email"], ["question"]]   # who first
    assert form["any_of"] == [["phone", "email"]]
    assert [spec(form, k)["required"] for k in keys(form)] == [True, False, False, True]
    assert form["labels"] == {"send": "Send", "next": "Next", "back": "Back", "cancel": "Cancel",
                              "cancelled": "No problem, nothing was sent."} and form["messages"]["required"]


def test_every_standard_field_has_its_label_help_and_kind_from_the_tool_row(diner):
    form = forms.form_for(diner["category"], diner["customer"], "inquire_catering")
    assert spec(form, "name")["label"] == "Your name" and "contact" in spec(form, "name")["help"]
    assert (spec(form, "phone")["format"], spec(form, "phone")["input"]) == ("phone", "tel")
    assert (spec(form, "email")["format"], spec(form, "email")["input"]) == ("email", "email")
    assert (spec(form, "question")["input"], spec(form, "question")["min_length"]) == ("textarea", 3)


def test_a_booking_action_with_booking_off_gives_its_link_when_there_is_one_and_a_form_when_not(diner):
    off = dict(diner["customer"], booking_enabled=False)
    assert forms.form_for(diner["category"], off, "book_reservation") is None
    assert forms.details_reply(diner["category"], off, "book_reservation") == "Here is the link: https://demo-diner-1.example/booking"
    no_link = dict(off, custom_fields={k: v for k, v in off["custom_fields"].items() if k != "booking_link"})
    form = forms.form_for(diner["category"], no_link, "book_reservation")
    assert form["route"] == "handover" and form["request_type"] == "table booking"   # still what the visitor wanted
    assert forms.details_reply(diner["category"], no_link, "book_reservation") is None


def test_a_details_action_gives_its_link_and_no_form(diner):
    assert forms.form_for(diner["category"], diner["customer"], "view_menu") is None
    assert forms.details_reply(diner["category"], diner["customer"], "view_menu") == "Here is the link: https://demo-diner-1.example/menu"


def test_a_booking_action_of_a_business_with_booking_on_has_no_link_reply(diner):
    assert forms.details_reply(diner["category"], diner["customer"], "book_reservation") is None


@pytest.mark.parametrize("key, label", [("critical_handover", "critical handover"), ("ai_down_handover", "ai down handover"),
                                        ("fallback_handover", "fallback handover"), ("direct_handover", "direct handover")])
def test_the_general_actions_have_forms_and_labels_from_the_table(diner, key, label):
    form = forms.form_for(diner["category"], diner["customer"], key)
    assert form["request_type"] == label and keys(form) == ["name", "phone", "email", "question"]


def test_a_key_that_is_not_an_action_has_no_form(diner):
    assert forms.form_for(diner["category"], diner["customer"], "no_such_action") is None
    assert forms.resolve(diner["category"], diner["customer"], "no_such_action") is None


def test_the_prefill_is_checked_and_a_wrong_value_is_left_out(diner):
    form = forms.form_for(diner["category"], diner["customer"], "inquire_catering",
                          {"name": "Priya Shah", "phone": "abc", "email": "P@X.com", "question": "hi", "unknown": "x"}, TODAY)
    assert form["values"] == {"name": "Priya Shah", "email": "p@x.com"}


# ---- more fields than fit on a page ----

def synthetic(diner, collect):
    category = copy.deepcopy(diner["category"])
    category["actions"] = [{"key": "x", "name": "X", "goal": "g", "button": None, "request_type": "x request",
                            "steps": [{"route": "handover", "tools": ["request_handoff"], "collect": collect}]}]
    return category


NAME = {"key": "name", "required": True}
CONTACT = {"any_of": ["phone", "email"]}
QUESTION = {"key": "question", "required": True}
PARTY = {"key": "party_size", "type": "integer", "description": "Number of guests.", "required": True, "min": 1, "max": 20}
OCCASION = {"key": "occasion", "type": "string", "description": "What is the occasion?", "required": False}


def test_three_fields_fit_on_a_page_and_the_rest_go_on_the_next(diner):
    form = forms.form_for(synthetic(diner, [NAME, CONTACT, QUESTION, PARTY, OCCASION]), diner["customer"], "x")
    assert [keys({"pages": [p]}) for p in form["pages"]] == [["name", "phone", "email"], ["question", "party_size", "occasion"]]
    assert all(len(p["fields"]) <= forms.PAGE_SIZE for p in form["pages"])


def test_an_either_group_is_never_split_across_pages(diner):
    form = forms.form_for(synthetic(diner, [NAME, QUESTION, PARTY, CONTACT]), diner["customer"], "x")
    assert [keys({"pages": [p]}) for p in form["pages"]] == [["name", "question", "party_size"], ["phone", "email"]]
    form = forms.form_for(synthetic(diner, [NAME, QUESTION, CONTACT, PARTY]), diner["customer"], "x")
    assert [keys({"pages": [p]}) for p in form["pages"]] == [["name", "question"], ["phone", "email", "party_size"]]


def test_a_field_of_the_category_carries_its_own_label_help_and_range(diner):
    form = forms.form_for(synthetic(diner, [NAME, CONTACT, PARTY, OCCASION]), diner["customer"], "x")
    party = spec(form, "party_size")
    assert (party["input"], party["help"], party["min"], party["max"], party["required"]) == ("number", "Number of guests.", 1, 20, True)
    assert spec(form, "occasion")["label"] == "Occasion" and spec(form, "occasion")["required"] is False


def test_a_required_phone_and_an_optional_note_follow_the_collect_not_the_code(diner):
    form = forms.form_for(synthetic(diner, [NAME, {"key": "phone", "required": True}, {"key": "note", "required": False}]),
                          diner["customer"], "x")
    assert [(k, spec(form, k)["required"]) for k in keys(form)] == [("name", True), ("phone", True), ("note", False)]
    assert form["any_of"] == []


# ---- what the visitor sent ----

def test_a_good_submission_is_clean_and_a_bad_one_has_errors_by_field(diner):
    clean, errors = forms.validate_request(diner["category"], diner["customer"], "inquire_catering",
                                           {"name": "Priya Shah", "phone": "+1 512 555 0199", "question": "Catering for 40"}, TODAY)
    assert errors == {} and clean == {"name": "Priya Shah", "phone": "+15125550199", "question": "Catering for 40"}
    _, errors = forms.validate_request(diner["category"], diner["customer"], "inquire_catering",
                                       {"name": "Priya", "phone": "call me", "question": ""}, TODAY)
    assert set(errors) == {"phone", "question"}


def test_a_request_for_an_action_without_a_form_is_refused(diner):
    with pytest.raises(KeyError):
        forms.validate_request(diner["category"], diner["customer"], "view_menu", {}, TODAY)


def test_a_chat_may_send_only_a_few_requests(chat):
    allowed = [forms.allow_submit(chat["client"], chat["sid"]) for _ in range(forms.SESSION_SUBMITS + 2)]
    assert allowed == [True] * forms.SESSION_SUBMITS + [False, False]


# ---- the saved row, and the plain query that confirms it ----

def row(chat, action=None):
    with psycopg.connect(DATABASE_URL) as conn:
        return conn.execute("""select name, email, phone, question, action_key, request_type, extra_fields, reason from conv_handover
                               where session_id = %s and (%s::text is null or action_key = %s) order by created_at""",
                            (chat["sid"], action, action)).fetchall()


def save(diner, chat, action, clean):
    with psycopg.connect(DATABASE_URL) as conn:   # leaving the block commits
        return forms.save_request(chat["client"], conn, chat["sid"], diner["category"], diner["customer"], action, clean)


def test_a_request_is_saved_with_its_type_action_and_extra_fields(diner, chat):
    chat["client"].hset(session_key(chat["sid"]), "handover_reason", "unavailable_answer")
    assert save(diner, chat, "book_reservation", {"name": "Priya Shah", "phone": "5125550199", "question": "Table for four",
                                                  "date": "2026-11-02", "party_size": 4})
    assert row(chat) == [("Priya Shah", None, "5125550199", "Table for four", "book_reservation", "table booking",
                          {"date": "2026-11-02", "party_size": 4}, "unavailable_answer")]


def test_the_query_defaults_to_the_action_name_and_the_reason_to_a_request_from_the_visitor(diner, chat):
    assert save(diner, chat, "inquire_catering", {"name": "Priya Shah", "email": "p@x.com"})
    name, email, phone, question, action, request_type, extra, reason = row(chat)[0]
    assert (question, request_type, extra, reason) == (forms.find_action(diner["category"], "inquire_catering")[0]["name"],
                                                       "direct handover", {}, "request_from_visitor")


def test_sending_the_same_request_twice_makes_one_row_and_another_action_makes_another(diner, chat):
    clean = {"name": "Priya Shah", "email": "p@x.com", "question": "Catering for 40"}
    assert save(diner, chat, "inquire_catering", clean) and save(diner, chat, "inquire_catering", clean)
    assert len(row(chat)) == 1
    assert save(diner, chat, "book_reservation", {"name": "Priya Shah", "email": "p@x.com", "question": "A table"})
    assert [r[4] for r in row(chat)] == ["inquire_catering", "book_reservation"]


def test_a_request_that_cannot_be_saved_leaves_nothing_held(monkeypatch, diner, chat):
    monkeypatch.setattr(forms, "save_handover_now", lambda client, conn, session_id: False)
    assert save(diner, chat, "inquire_catering", {"name": "Priya Shah", "email": "p@x.com", "question": "Catering"}) is False
    state = chat["client"].hgetall(session_key(chat["sid"]))
    assert not any(state.get(k) for k in ("handover", "handover_action", "handover_request_type", "handover_extra"))
    assert row(chat) == []


def confirm(chat, action, phone=None, email=None):
    return forms.confirm_saved(lambda: psycopg.connect(DATABASE_URL), chat["sid"], action, phone, email)


def test_the_confirmation_finds_a_committed_row_by_phone_or_email_within_a_minute(diner, chat):
    assert save(diner, chat, "inquire_catering", {"name": "Priya Shah", "phone": "5125550199", "question": "Catering"})
    assert confirm(chat, "inquire_catering", phone="5125550199")
    assert confirm(chat, "inquire_catering", phone="5125550199", email="other@x.com")   # either one is enough
    assert not confirm(chat, "inquire_catering", phone="5125550100")                     # another number
    assert not confirm(chat, "inquire_catering", email="p@x.com")                        # an email that was not saved
    assert not confirm(chat, "book_reservation", phone="5125550199")                     # another action
    assert not confirm(chat, "inquire_catering")                                          # no contact to look for


def test_a_row_that_was_not_committed_is_not_confirmed(diner, chat):
    conn = psycopg.connect(DATABASE_URL)
    try:
        assert forms.save_request(chat["client"], conn, chat["sid"], diner["category"], diner["customer"], "inquire_catering",
                                  {"name": "Priya Shah", "phone": "5125550199", "question": "Catering"})
        assert not confirm(chat, "inquire_catering", phone="5125550199")   # the new connection cannot see it
        conn.commit()
        assert confirm(chat, "inquire_catering", phone="5125550199")        # after the commit it can
    finally:
        conn.close()


def test_a_row_older_than_a_minute_is_not_confirmed(diner, chat):
    assert save(diner, chat, "inquire_catering", {"name": "Priya Shah", "phone": "5125550199", "question": "Catering"})
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("update conv_handover set created_at = now() - interval '2 minutes' where session_id = %s", (chat["sid"],))
        conn.commit()
    assert not confirm(chat, "inquire_catering", phone="5125550199")
