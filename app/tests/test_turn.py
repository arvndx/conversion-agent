"""The chat turn through the chat API, with the model replaced by a script: the quick-question click (no model), the fixed
replies (no model), the handover offers and their forms, the agent opening the form, and the request form sent by the visitor
(no model). Each test removes what it made.
Run from the app folder: uv run pytest tests/test_turn.py"""

import json
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.chat_api import FORM_SITE_LIMIT, create_app
from pipeline import forms
from pipeline.classify import SafetyResult
from pipeline.load_chat import DATABASE_URL, connect, redis_client, session_key
from pipeline.turn import _contact_text, fill
from shared.bundle_tables import load_category, load_customer
from tests.model_stub import ScriptedModel, install, install_no_model, response, text_block, tool_block

DINER = "483dc8e7-3f03-5fbb-878b-77ee433ed0b3"

with psycopg.connect(DATABASE_URL) as _c:
    SITE_KEY, DOMAIN = _c.execute("select site_key, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()
    CATEGORY = load_category(_c, "gcid:american_restaurant")
    CUSTOMER = load_customer(_c, DINER)
MESSAGES = CATEGORY["message_texts"]
NAME = "Demo Chef Owner"


@pytest.fixture(autouse=True)
def no_email_commit(monkeypatch):
    from pipeline import worker
    monkeypatch.setattr(worker, "send_handover_emails", lambda *args, **kwargs: 0)


@pytest.fixture()
def api():
    return TestClient(create_app(redis_client=redis_client(), connect_fn=connect))


@pytest.fixture()
def made():
    rows = {"sessions": []}
    yield rows
    r = redis_client()
    with psycopg.connect(DATABASE_URL) as c:
        for sid in rows["sessions"]:
            c.execute("delete from conv_handover where session_id = %s", (sid,))
            c.execute("delete from conv_session where session_id = %s", (sid,))
            c.execute("delete from conv_activity where activity_id = %s", (sid,))
            r.delete(session_key(sid))
            r.srem("session_updates", sid)
            r.srem("open_sessions", sid)
        c.execute("delete from conv_question where professional_id = %s and question_text like 'turn test%%'", (DINER,))
        c.commit()


def post(api, path, made, **body):
    body = {"site_key": SITE_KEY, "domain": DOMAIN, **body}
    out = api.post(path, json=body).json()
    if out.get("session_id") and out["session_id"] not in made["sessions"]:
        made["sessions"].append(out["session_id"])
    return out


def say(api, made, text, session_id=None):
    return post(api, "/chat/message", made, text=text, msg_id=str(uuid.uuid4()), **({"session_id": session_id} if session_id else {}))


def click(api, made, action_key, label=None, session_id=None):
    return post(api, "/chat/message", made, text=label or action_key, action_key=action_key, msg_id=str(uuid.uuid4()),
                **({"session_id": session_id} if session_id else {}))


def submit(api, made, session_id, action_key, **values):
    return post(api, "/chat/form", made, session_id=session_id, action_key=action_key, values=values)


def rows(session_id):
    with psycopg.connect(DATABASE_URL) as c:
        return c.execute("""select name, email, phone, question, action_key, request_type, reason, extra_fields from conv_handover
                            where session_id = %s order by created_at""", (session_id,)).fetchall()


def state(session_id, field):
    return redis_client().hget(session_key(session_id), field)


def conversation(session_id):
    return json.loads(state(session_id, "conversation"))


# ---- a quick-question click: no model ----

def test_a_click_on_a_booking_action_opens_the_form_with_no_model_call(api, made, monkeypatch):
    install_no_model(monkeypatch)
    out = click(api, made, "book_reservation", "Book a Table")
    card = out["card"]
    assert out["state"] == "reply" and out["reply"] == fill(MESSAGES["form_intro"], CUSTOMER, CATEGORY)
    assert (card["action_key"], card["route"], card["request_type"]) == ("book_reservation", "booking", "table booking")
    assert [[f["key"] for f in page["fields"]] for page in card["pages"]] == [["name", "phone", "email"], ["question"]]
    assert state(out["session_id"], "handover_reason") == "request_from_visitor"


def test_a_click_on_a_handover_only_action_opens_its_form(api, made, monkeypatch):
    install_no_model(monkeypatch)
    out = click(api, made, "inquire_catering")
    assert out["card"]["route"] == "handover" and out["card"]["request_type"] == "direct handover"


def test_a_click_on_a_link_action_gives_the_link_and_no_form(api, made, monkeypatch):
    install_no_model(monkeypatch)
    out = click(api, made, "view_menu", "See Our Menu")
    assert out["card"] is None and out["reply"] == "Here is the link: https://demo-diner-1.example/menu"


def test_a_click_on_a_key_that_is_not_a_button_of_the_business_gets_a_fixed_apology(api, made, monkeypatch):
    install_no_model(monkeypatch)
    apologies = [fill(r, CUSTOMER, CATEGORY) for r in CATEGORY["static_replies"]["fallback_apology"]["replies"]]
    for key in ("no_such_action", "critical_handover", "direct_handover"):   # the general actions are not buttons
        out = click(api, made, key)
        assert out["card"] is None and out["reply"] in apologies


def test_a_click_is_kept_in_the_chat_as_the_buttons_label_with_its_reply(api, made, monkeypatch):
    install_no_model(monkeypatch)
    out = click(api, made, "book_reservation", "Book a Table")
    turn = conversation(out["session_id"])[-1]
    assert turn["request"] == ["Book a Table"] and turn["response"] == out["reply"]


def test_a_click_that_is_sent_twice_is_answered_once(api, made, monkeypatch):
    install_no_model(monkeypatch)
    body = dict(text="Book a Table", action_key="book_reservation", msg_id=str(uuid.uuid4()))
    first = post(api, "/chat/message", made, **body)
    again = post(api, "/chat/message", made, session_id=first["session_id"], **body)
    assert first["card"] and again["state"] == "ignored" and len(conversation(first["session_id"])) == 1


# ---- fixed replies: no model ----

def test_a_greeting_gets_one_of_the_greeting_replies_and_calls_no_model(api, made, monkeypatch):
    install_no_model(monkeypatch)
    out = say(api, made, "hi")
    assert out["reply"] in [fill(r, CUSTOMER, CATEGORY) for r in CATEGORY["static_replies"]["greeting"]["replies"]]
    assert out["card"] is None and conversation(out["session_id"])[-1]["request"] == ["hi"]


def test_the_same_greeting_reply_is_not_repeated_back_to_back(api, made, monkeypatch):
    install_no_model(monkeypatch)
    first = say(api, made, "hello")
    seen = [first["reply"]]
    for text in ["hi", "hey", "hello there", "good morning", "hi again"]:
        seen.append(say(api, made, text, first["session_id"])["reply"])
    assert all(a != b for a, b in zip(seen, seen[1:]))


@pytest.mark.parametrize("text, intent", [("thanks", "thanks"), ("bye", "goodbye"), ("are you a bot?", "ai_identity"),
                                          ("sorry", "apology"), ("is this chat recorded", "privacy")])
def test_thanks_goodbye_the_bot_question_and_the_rest_are_fixed_replies(api, made, monkeypatch, text, intent):
    install_no_model(monkeypatch)
    out = say(api, made, text)
    assert out["reply"] in [fill(r, CUSTOMER, CATEGORY) for r in CATEGORY["static_replies"][intent]["replies"]]


def test_a_greeting_with_a_question_goes_to_the_safety_check_and_the_agent(api, made, monkeypatch):
    model, safety = install(monkeypatch, [response(text_block("We open at nine."))])
    out = say(api, made, "hi, what time do you open")
    assert out["reply"] == "We open at nine." and len(safety.calls) == 1 and len(model.calls) == 1


def test_ok_after_a_question_goes_to_the_agent_but_ok_after_a_statement_is_a_fixed_reply(api, made, monkeypatch):
    model, safety = install(monkeypatch, [response(text_block("Which day would you like to visit?")),
                                          response(text_block("Saturday it is."))])
    first = say(api, made, "when can I come")
    assert say(api, made, "ok", first["session_id"])["reply"] == "Saturday it is."   # the agent knows the question
    install_no_model(monkeypatch)
    assert say(api, made, "ok", None)["reply"]   # a new chat: nothing was asked, so a fixed reply


# ---- the agent ----

def test_the_agent_opens_the_form_and_the_model_is_not_called_again(api, made, monkeypatch):
    model, safety = install(monkeypatch, [response(tool_block("request_handoff", {"action_key": "book_reservation",
                                                                                  "prefill": {"question": "A table for four"}})),
                                          response(text_block("never asked for"))])
    out = say(api, made, "can you book a table for four")
    assert out["reply"] == fill(MESSAGES["form_intro"], CUSTOMER, CATEGORY)
    assert out["card"]["action_key"] == "book_reservation" and out["card"]["values"] == {"question": "A table for four"}
    assert len(safety.calls) == 1 and len(model.calls) == 1   # two calls in all: the safety check and the agent


def test_an_ordinary_answer_from_the_agent_has_no_card(api, made, monkeypatch):
    install(monkeypatch, [response(text_block("The Smash Burger is 11.50."))])
    out = say(api, made, "turn test how much is the smash burger")
    assert out["reply"] == "The Smash Burger is 11.50." and out["card"] is None


# ---- a handover offer, and its form ----

def offer(api, made, monkeypatch, safety, text="turn test what is in the dish"):
    model, check = install(monkeypatch, safety=safety)
    return say(api, made, text), model, check


def test_a_critical_question_is_answered_with_the_topics_reply_and_a_yes_opens_the_critical_form(api, made, monkeypatch):
    topic = next(t for t in CATEGORY["critical_topics"] if t["id"] == "allergy_food_safety")
    out, model, check = offer(api, made, monkeypatch, SafetyResult("yes", "allergy_food_safety", False), "I am allergic to nuts")
    sid = out["session_id"]
    assert out["reply"] == fill(f'{topic["reply"]}\n{MESSAGES["critical_handover_follow"]}', CUSTOMER, CATEGORY)
    assert state(sid, "handover_stage") == "offered" and not model.calls
    install_no_model(monkeypatch)
    opened = say(api, made, "yes please", sid)
    assert opened["card"]["request_type"] == "critical handover" and opened["card"]["values"] == {"question": "I am allergic to nuts"}
    done = submit(api, made, sid, "critical_handover", name="Priya Shah", phone="5125550199", question="I am allergic to nuts")
    assert done["reply"] == fill(MESSAGES["request_sent"], CUSTOMER, CATEGORY)
    assert rows(sid) == [("Priya Shah", None, "5125550199", "I am allergic to nuts", "critical_handover", "critical handover",
                          "critical_question", {})]


def test_a_no_to_an_offer_is_declined_in_the_tables_words_and_nothing_is_saved(api, made, monkeypatch):
    out, _, _ = offer(api, made, monkeypatch, SafetyResult("yes", "medical_emergency", False), "I feel dizzy")
    install_no_model(monkeypatch)
    declined = say(api, made, "no thanks", out["session_id"])
    assert declined["reply"] == fill(MESSAGES["handover_declined"], CUSTOMER, CATEGORY) and state(out["session_id"], "handover_stage") == ""
    assert rows(out["session_id"]) == []


def test_another_message_after_an_offer_drops_the_offer_and_is_answered_as_usual(api, made, monkeypatch):
    out, _, _ = offer(api, made, monkeypatch, SafetyResult("yes", "medical_emergency", False), "I feel dizzy")
    install(monkeypatch, [response(text_block("We open at nine."))])
    answer = say(api, made, "what time do you open", out["session_id"])
    assert answer["reply"] == "We open at nine." and state(out["session_id"], "handover_stage") == ""


def test_the_model_being_down_offers_a_handover_with_an_apology_and_its_form_is_the_ai_down_form(api, made, monkeypatch):
    model, _ = install(monkeypatch, [TimeoutError("the model did not answer")])
    out = say(api, made, "turn test do you do catering")
    sid = out["session_id"]
    apologies = [fill(r, CUSTOMER, CATEGORY) for r in CATEGORY["static_replies"]["fallback_apology"]["replies"]]
    assert any(out["reply"] == f'{a}\n{fill(MESSAGES["handover_offer"], CUSTOMER, CATEGORY)}' for a in apologies)
    assert state(sid, "handover_stage") == "offered" and state(sid, "handover_action") == "ai_down_handover"
    install_no_model(monkeypatch)   # from here on the model is down: nothing needs it
    opened = say(api, made, "yes", sid)
    assert opened["card"]["request_type"] == "ai down handover"
    submit(api, made, sid, "ai_down_handover", name="Lee Test", email="lee@example.com", question="turn test do you do catering")
    assert rows(sid)[0][4:7] == ("ai_down_handover", "ai down handover", "system_fallback")


def test_a_failed_safety_check_is_also_an_ai_down_handover(api, made, monkeypatch):
    from pipeline import agent as chat_agent
    monkeypatch.setattr(chat_agent, "safety_check", lambda category, message, client=None: None)
    out = say(api, made, "turn test anything at all")
    assert state(out["session_id"], "handover_action") == "ai_down_handover" and state(out["session_id"], "handover_stage") == "offered"


def test_a_reply_that_keeps_failing_its_checks_offers_the_fallback_form(api, made, monkeypatch):
    install(monkeypatch, [response(text_block("I've sent your request to the restaurant."))])   # nothing was sent: never allowed
    out = say(api, made, "turn test please pass this on")
    assert state(out["session_id"], "handover_action") == "fallback_handover"
    assert say(api, made, "yes", out["session_id"])["card"]["request_type"] == "fallback handover"


def test_an_unsure_safety_check_offers_the_fallback_form_but_a_plain_yes_still_reaches_the_agent(api, made, monkeypatch):
    out, _, _ = offer(api, made, monkeypatch, SafetyResult("unsure", None, False), "turn test hmm")
    assert state(out["session_id"], "handover_action") == "fallback_handover"
    model, _ = install(monkeypatch, [response(text_block("Sure."))], safety=SafetyResult("unsure", None, False))
    assert say(api, made, "no", None)["reply"] == "Sure." and len(model.calls) == 1


# ---- an abusive message ----

def test_an_abusive_message_gets_a_warning_from_the_fixed_replies_and_three_strikes_block(api, made, monkeypatch):
    install(monkeypatch, safety=SafetyResult("no", None, True))
    first = say(api, made, "turn test you idiots")
    warnings = [fill(r, CUSTOMER, CATEGORY) for r in CATEGORY["static_replies"]["abuse_warning"]["replies"]]
    assert first["reply"] in warnings
    states = [say(api, made, "turn test you idiots", first["session_id"])["state"] for _ in range(2)]
    assert states[-1] == "blocked"


# ---- the request form, sent by the visitor ----

def open_booking(api, made, monkeypatch):
    install_no_model(monkeypatch)
    return click(api, made, "book_reservation", "Book a Table")["session_id"]


def test_a_good_form_is_saved_confirmed_and_answered_in_the_tables_words(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    done = submit(api, made, sid, "book_reservation", name="Priya Shah", phone="+1 512 555 0199", email="",
                  question="A table for four on Saturday, anytime")
    assert done["state"] == "reply" and done["reply"] == fill(MESSAGES["request_sent"], CUSTOMER, CATEGORY)
    assert NAME in done["reply"] and "as soon as possible" in done["reply"]
    assert rows(sid) == [("Priya Shah", None, "+15125550199", "A table for four on Saturday, anytime", "book_reservation",
                          "table booking", "request_from_visitor", {})]
    assert conversation(sid)[-1]["request"] == ["[sent the request form: table booking]"]


def test_a_form_with_wrong_values_comes_back_with_errors_by_field_and_saves_nothing(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    out = submit(api, made, sid, "book_reservation", name="no", phone="call me", question="")
    assert out["state"] == "form_errors" and out["reply"] is None
    assert set(out["errors"]) == {"name", "phone", "question"} and "digits only" in out["errors"]["phone"]
    assert rows(sid) == []


def test_neither_phone_nor_email_is_an_error_on_both(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    out = submit(api, made, sid, "book_reservation", name="Priya Shah", question="A table")
    assert set(out["errors"]) == {"phone", "email"}


def test_sending_the_form_twice_saves_one_row_and_says_the_same_thing(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    values = dict(name="Priya Shah", email="p@x.com", question="A table for two")
    first, second = submit(api, made, sid, "book_reservation", **values), submit(api, made, sid, "book_reservation", **values)
    assert first["reply"] == second["reply"] == fill(MESSAGES["request_sent"], CUSTOMER, CATEGORY) and len(rows(sid)) == 1


def test_one_chat_may_send_requests_for_different_actions(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    submit(api, made, sid, "book_reservation", name="Priya Shah", email="p@x.com", question="A table")
    submit(api, made, sid, "inquire_catering", name="Priya Shah", email="p@x.com", question="Catering for 40")
    assert [r[4:6] for r in rows(sid)] == [("book_reservation", "table booking"), ("inquire_catering", "direct handover")]


def test_a_chat_that_sends_too_many_requests_is_told_it_could_not_be_processed(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    for i in range(forms.SESSION_SUBMITS):
        submit(api, made, sid, "book_reservation", name="Priya Shah", email=f"p{i}@x.com", question=f"A table {i}")
    over = submit(api, made, sid, "inquire_catering", name="Priya Shah", email="p@x.com", question="Catering")
    contact = _contact_text(CUSTOMER)
    assert "unable to process your request right away" in over["reply"] and rows(sid)[-1][4] == "book_reservation"
    assert (contact in over["reply"]) is bool(contact)


def test_a_form_for_an_action_with_no_form_gets_the_fixed_apology(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    for key in ("view_menu", "no_such_action"):
        out = submit(api, made, sid, key, name="Priya Shah", email="p@x.com", question="x")
        assert out["reply"] in [fill(r, CUSTOMER, CATEGORY) for r in CATEGORY["static_replies"]["fallback_apology"]["replies"]]
    assert rows(sid) == []


def test_when_the_row_cannot_be_found_afterwards_the_visitor_is_told_to_contact_the_business(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    monkeypatch.setattr(forms, "confirm_saved", lambda *args, **kwargs: False)
    out = submit(api, made, sid, "book_reservation", name="Priya Shah", email="p@x.com", question="A table")
    contact = _contact_text(CUSTOMER)
    expected = MESSAGES["request_not_saved" if contact else "request_not_saved_no_contact"].replace("{contact}", contact)
    assert out["reply"] == fill(expected, CUSTOMER, CATEGORY) and "unable to process your request right away" in out["reply"]
    assert "conveyed" not in out["reply"]


def test_when_the_save_fails_nothing_is_reported_as_sent(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    monkeypatch.setattr(forms, "save_request", lambda *args, **kwargs: False)
    out = submit(api, made, sid, "book_reservation", name="Priya Shah", email="p@x.com", question="A table")
    assert "unable to process your request right away" in out["reply"] and rows(sid) == []


def test_without_a_contact_the_business_shows_the_failure_text_has_no_phone_or_email(api, made, monkeypatch):
    from pipeline import turn
    sid = open_booking(api, made, monkeypatch)
    monkeypatch.setattr(forms, "confirm_saved", lambda *args, **kwargs: False)
    monkeypatch.setattr(turn, "_contact_text", lambda customer: "")
    out = submit(api, made, sid, "book_reservation", name="Priya Shah", email="p@x.com", question="A table")
    assert out["reply"] == fill(MESSAGES["request_not_saved_no_contact"], CUSTOMER, CATEGORY) and "{contact}" not in out["reply"]


def test_a_form_sent_to_a_closed_chat_is_refused(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    api.post("/chat/close", json={"site_key": SITE_KEY, "domain": DOMAIN, "session_id": sid})
    out = submit(api, made, sid, "book_reservation", name="Priya Shah", email="p@x.com", question="A table")
    assert out["state"] == "stopped" and rows(sid) == []


def test_a_site_may_send_only_so_many_forms_a_minute(api, made, monkeypatch):
    sid = open_booking(api, made, monkeypatch)
    r = redis_client()
    import time
    window = f"form_rate:{SITE_KEY}:{int(time.time() // 60)}"
    r.set(window, FORM_SITE_LIMIT)
    try:
        out = submit(api, made, sid, "book_reservation", name="Priya Shah", email="p@x.com", question="A table")
        assert out["state"] == "reply" and "Too many requests" in out["reply"] and rows(sid) == []
    finally:
        r.delete(window, f"form_rate:{SITE_KEY}:{int(time.time() // 60) + 1}")
