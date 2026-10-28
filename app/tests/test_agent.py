"""The chat agent: the two tools, the tool loop (with the model replaced by a script), and the checks on every reply. The request
form the agent opens is tested in tests/test_forms.py, and the turn around the agent in tests/test_turn.py.
Run from the app folder: uv run pytest tests/test_agent.py"""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import psycopg
import pytest

from pipeline import agent as chat_agent
from pipeline.load_chat import DATABASE_URL, redis_client, session_key
from shared.bundle_tables import load_category, load_customer
from tools import agent_tools
from tools.agent_tools import AgentContext

DINER = "483dc8e7-3f03-5fbb-878b-77ee433ed0b3"


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(name, args, block_id=None):
    return SimpleNamespace(type="tool_use", id=block_id or f"tool_{uuid.uuid4().hex[:8]}", name=name, input=args)


def response(*blocks, stop=None):
    stop = stop or ("tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn")
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


class ScriptedModel:
    """Stands in for the Anthropic client: returns the scripted answers in order, and records what it was sent."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.answers:
            return response(text_block("(no more scripted answers)"))
        answer = self.answers.pop(0)
        return answer(kwargs) if callable(answer) else answer


@pytest.fixture()
def diner():
    with psycopg.connect(DATABASE_URL) as conn:
        category = load_category(conn, "gcid:american_restaurant")
        customer = load_customer(conn, DINER)
        domain = conn.execute("select domain from conv_domains where professional_id = %s and domain = 'demo-diner-1.example'",
                              (DINER,)).fetchone()[0]
    return {"category": category, "customer": customer, "domain": domain}


@pytest.fixture(autouse=True)
def no_email_commit(monkeypatch):
    """A request saved by the chat sends the business its email, which commits. Not in these tests."""
    from pipeline import worker
    monkeypatch.setattr(worker, "send_handover_emails", lambda *args, **kwargs: 0)


@pytest.fixture()
def chat(diner):
    """A fresh chat for the diner. What it made is removed afterwards."""
    from pipeline.turn import _create_session
    session_id = str(uuid.uuid4())
    client = redis_client()
    _create_session(client, session_id, "professional", DINER, diner["domain"], datetime.now(timezone.utc), False, "", "")
    made = {"session_id": session_id, "conns": []}
    yield {"session_id": session_id, "client": client, "made": made}
    for conn in made["conns"]:
        conn.close()
    client.delete(session_key(session_id))
    client.srem("session_updates", session_id)
    client.srem("open_sessions", session_id)
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("delete from conv_handover where session_id = %s", (session_id,))
        conn.execute("delete from conv_session where session_id = %s", (session_id,))
        conn.execute("delete from conv_activity where activity_id = %s", (session_id,))
        conn.commit()


def make_ctx(diner, chat, message, now=None):
    conn = psycopg.connect(DATABASE_URL)
    chat["made"]["conns"].append(conn)
    session = {k: v for k, v in chat["client"].hgetall(session_key(chat["session_id"])).items()}
    return AgentContext(client=chat["client"], conn=conn, category=diner["category"], customer=diner["customer"],
                        session_id=chat["session_id"], professional_id=DINER, domain=diner["domain"], session=session,
                        message=message, now=now or datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc))


def run(diner, chat, model, message="a question"):
    ctx = make_ctx(diner, chat, message)
    return chat_agent.run_agent(ctx, client=model), ctx


# ---- the tools the model is offered ----

def schemas(diner):
    return {t["name"]: t for t in agent_tools.tool_schemas(diner["category"], diner["customer"])}


def test_the_model_is_offered_two_tools_and_the_menu_tools_for_a_business_with_a_menu(diner):
    names = set(schemas(diner))
    assert names == {"get_business_info", "request_handoff", "search_menu", "get_menu"}
    assert not names & {"check_slot", "book", "propose_booking", "get_conversion_link", "get_services"}


def test_request_handoff_names_the_actions_and_tells_the_model_only_types_and_descriptions(diner):
    schema = schemas(diner)["request_handoff"]["input_schema"]
    keys = set(schema["properties"]["action_key"]["enum"])
    assert {"book_reservation", "inquire_catering", "direct_handover"} <= keys
    assert "critical_handover" not in keys   # the code opens that one, not the model
    prefill = schema["properties"]["prefill"]["properties"]
    assert set(prefill) >= {"name", "phone", "email", "question"}
    assert all(set(spec) <= {"type", "description"} for spec in prefill.values())   # no labels or formats for the model


def test_get_business_info_lists_the_fields_this_business_may_read(diner):
    fields = schemas(diner)["get_business_info"]["input_schema"]["properties"]["field"]["enum"]
    assert {"phone", "opening_hours", "booking_link", "menu_link"} <= set(fields)


def test_a_business_without_a_menu_is_not_offered_the_menu_tools(diner):
    no_menu = dict(diner["customer"], menu={})
    assert {t["name"] for t in agent_tools.tool_schemas(diner["category"], no_menu)} == {"get_business_info", "request_handoff"}


# ---- the request form tool ----

def test_request_handoff_opens_the_form_and_saves_nothing(diner, chat):
    ctx = make_ctx(diner, chat, "I want to book a table")
    result = agent_tools.run_tool(ctx, "request_handoff", {"action_key": "book_reservation", "reason": "visitor_asked",
                                                          "prefill": {"name": "Agent Test Jane", "question": "A table for four"}})
    assert result == {"ok": True, "form_opened": True, "request_type": "table booking"}
    assert ctx.card["action_key"] == "book_reservation" and ctx.card["values"]["name"] == "Agent Test Jane"
    state = chat["client"].hgetall(session_key(chat["session_id"]))
    assert state["handover_reason"] == "request_from_visitor" and state["handover_question"] == "I want to book a table"
    assert not state.get("handover")   # nothing is held or saved until the visitor sends the form
    assert ctx.conn.execute("select count(*) from conv_handover where session_id = %s", (chat["session_id"],)).fetchone()[0] == 0


def test_the_reason_the_model_gives_is_kept_for_the_row(diner, chat):
    ctx = make_ctx(diner, chat, "do you have a parking garage")
    agent_tools.run_tool(ctx, "request_handoff", {"action_key": "direct_handover", "reason": "not_on_record"})
    assert chat["client"].hget(session_key(chat["session_id"]), "handover_reason") == "unavailable_answer"


def test_a_wrong_prefill_is_dropped_not_shown(diner, chat):
    ctx = make_ctx(diner, chat, "book")
    agent_tools.run_tool(ctx, "request_handoff", {"action_key": "book_reservation",
                                                  "prefill": {"phone": "call me maybe", "email": "not-an-email", "name": "Jane Test"}})
    assert ctx.card["values"] == {"name": "Jane Test"}


@pytest.mark.parametrize("action_key, expected", [
    ("view_menu", "get_business_info"),        # completed with the menu link, not with a form
    ("not_an_action", "not an action"),
    ("critical_handover", "not an action"),    # general actions the code opens are not the model's to pick
])
def test_a_key_with_no_form_gives_the_model_an_error(diner, chat, action_key, expected):
    ctx = make_ctx(diner, chat, "hi")
    result = agent_tools.run_tool(ctx, "request_handoff", {"action_key": action_key})
    assert result["ok"] is False and expected in result["error"] and ctx.card is None


def test_the_model_may_pick_direct_handover_when_no_action_fits(diner, chat):
    ctx = make_ctx(diner, chat, "can I talk to someone")
    assert agent_tools.run_tool(ctx, "request_handoff", {"action_key": "direct_handover"})["ok"]
    assert ctx.card["request_type"] == "direct handover"


# ---- the tool loop ----

def test_the_agent_uses_a_tool_then_writes_the_reply(diner, chat):
    model = ScriptedModel([
        response(tool_block("search_menu", {"query": "smash burger"})),
        response(text_block("The Smash Burger is 11.50.")),
    ])
    result, _ = run(diner, chat, model, "how much is the smash burger")
    assert result.ok and result.reply == "The Smash Burger is 11.50." and result.card is None
    assert result.tools_used == ["search_menu"]
    second_call_messages = model.calls[1]["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert json.loads(second_call_messages[-1]["content"][0]["content"])["found"] is True


def test_the_model_is_not_called_again_once_the_form_is_open(diner, chat):
    model = ScriptedModel([
        response(text_block("Sure, one moment."), tool_block("request_handoff", {"action_key": "book_reservation"})),
        response(text_block("This must never be asked for.")),
    ])
    result, ctx = run(diner, chat, model, "book a table")
    assert result.ok and result.reply is None and result.card["action_key"] == "book_reservation"
    assert len(model.calls) == 1 and result.tools_used == ["request_handoff"]


def test_the_form_opens_even_after_a_lookup_in_the_same_turn(diner, chat):
    model = ScriptedModel([
        response(tool_block("get_business_info", {"field": "phone"})),
        response(tool_block("request_handoff", {"action_key": "inquire_catering"})),
    ])
    result, _ = run(diner, chat, model, "catering for 40")
    assert result.card["action_key"] == "inquire_catering" and len(model.calls) == 2


def test_a_failed_form_does_not_end_the_turn(diner, chat):
    model = ScriptedModel([
        response(tool_block("request_handoff", {"action_key": "view_menu"})),
        response(tool_block("get_business_info", {"field": "menu_link"})),
        response(text_block("Our menu is at https://demo-diner-1.example/menu")),
    ])
    result, _ = run(diner, chat, model, "show me the menu")
    assert result.ok and result.card is None and "demo-diner-1.example/menu" in result.reply


def test_the_loop_stops_at_the_step_limit_and_asks_once_more_without_tools(diner, chat):
    looping = [response(tool_block("get_business_info", {"field": "phone"})) for _ in range(chat_agent.MAX_STEPS)]
    model = ScriptedModel(looping + [response(text_block("Let me pass this on."))])
    result, _ = run(diner, chat, model)
    assert result.ok and result.reply == "Let me pass this on."
    assert len(model.calls) == chat_agent.MAX_STEPS + 1
    assert "tools" not in model.calls[-1]


def test_an_empty_reply_is_reported_as_not_ok(diner, chat):
    result, _ = run(diner, chat, ScriptedModel([response(text_block("   "))]))
    assert result.ok is False and result.failure == "check_failed"


def test_the_model_sees_the_recent_chat(diner, chat):
    turns = [{"request": ["Do you have parking?"], "response": "Which day will you visit?", "event_time": "x"}]
    chat["client"].hset(session_key(chat["session_id"]), "conversation", json.dumps(turns))
    model = ScriptedModel([response(text_block("ok"))])
    run(diner, chat, model, "tomorrow")
    sent = model.calls[0]["messages"]
    assert sent[0] == {"role": "user", "content": "Do you have parking?"}
    assert sent[1] == {"role": "assistant", "content": "Which day will you visit?"}
    assert sent[-1] == {"role": "user", "content": "tomorrow"}


def test_the_prompt_tells_the_model_to_open_the_form_and_not_to_ask_for_the_details(diner):
    system = chat_agent.build_system(diner["category"], diner["customer"], datetime(2026, 10, 25).date())
    assert "request_handoff" in system and "do not ask for them yourself" in system
    assert "check_slot" not in system and "confirmed false" not in system
    assert "book_reservation" in system and "Ask for:" not in system


def test_an_empty_lookup_counts_as_a_gap_for_the_turn(diner, chat):
    ctx = make_ctx(diner, chat, "a question nobody has answered")
    agent_tools.run_tool(ctx, "get_business_info", {"field": "zzqqxx nothing like this"})
    assert ctx.gaps == 1


def test_a_tool_call_written_as_text_is_never_shown(diner, chat):
    model = ScriptedModel([response(text_block('<invoke name="request_handoff">\n<parameter name="action_key">x</parameter>\n</invoke>'))])
    result, _ = run(diner, chat, model, "book a table tomorrow")
    assert result.ok is False and result.reply is None


def test_a_category_bundle_without_tools_fails_cleanly(diner, chat):
    ctx = make_ctx(diner, chat, "hello")
    ctx.category = {k: v for k, v in diner["category"].items() if k not in ("tools", "actions")}
    ctx.customer = dict(diner["customer"], menu={})   # a business with a menu is still offered the menu tools
    with pytest.raises(RuntimeError, match="no tools"):
        chat_agent.run_agent(ctx, client=ScriptedModel([response(text_block("hi"))]))


# ---- every reply is checked before the visitor sees it (no model call) ----

def repair_note(model):
    """The note the model got when its first reply was not sent, or None."""
    for call in model.calls[1:]:
        last = call["messages"][-1]["content"]
        if isinstance(last, str) and "was not sent, because" in last:
            return last
    return None


def test_a_reply_that_says_it_was_passed_on_without_a_saved_request_is_written_again(diner, chat):
    model = ScriptedModel([response(text_block("I've sent your request to the restaurant.")),
                           response(text_block("I have not passed it on yet. Shall I open the form?"))])
    result, _ = run(diner, chat, model)
    assert result.ok and result.reply == "I have not passed it on yet. Shall I open the form?"
    assert "no request is saved" in repair_note(model)
    assert len(model.calls) == 2   # no judge call


def test_a_reply_that_keeps_saying_so_is_not_sent(diner, chat):
    model = ScriptedModel([response(text_block("I've sent your request.")), response(text_block("I've passed it on, done."))])
    result, _ = run(diner, chat, model)
    assert result.ok is False and result.reply is None and result.failure == "check_failed"


def test_a_request_that_is_in_the_table_can_be_reported(diner, chat):
    from pipeline import forms
    ctx = make_ctx(diner, chat, "pass it on")
    assert forms.save_request(ctx.client, ctx.conn, chat["session_id"], diner["category"], diner["customer"], "inquire_catering",
                              {"name": "Agent Test Jane", "email": "jane@example.com", "question": "Catering for 40"})
    model = ScriptedModel([response(text_block("I've passed your request to the restaurant, Jane."))])
    result = chat_agent.run_agent(ctx, client=model)
    assert result.ok and repair_note(model) is None


@pytest.mark.parametrize("claim", ["Your table is booked for tomorrow at 10:00.", "I've booked it for you.",
                                   "Your booking is confirmed.", "Your booking reference is: 12345."])
def test_the_model_may_never_say_something_is_booked_or_confirmed(diner, chat, claim):
    model = ScriptedModel([response(text_block(claim)), response(text_block("The restaurant will contact you to arrange it."))])
    result, _ = run(diner, chat, model, "book it")
    assert result.reply == "The restaurant will contact you to arrange it." and "nothing is confirmed" in repair_note(model)


def test_a_link_the_business_does_not_have_is_not_sent(diner, chat):
    model = ScriptedModel([response(text_block("Order here: https://made-up.example/order")),
                           response(text_block("You can order here: https://demo-diner-1.example/order"))])
    result, _ = run(diner, chat, model, "can I order takeout")
    assert result.reply == "You can order here: https://demo-diner-1.example/order"
    assert "made-up.example" in repair_note(model)


def test_a_phone_number_nobody_gave_is_not_sent(diner, chat):
    phone = diner["customer"]["public_contact"]["phone"]
    model = ScriptedModel([response(text_block("Call us on 555 987 6543.")), response(text_block(f"You can reach us on {phone}."))])
    result, _ = run(diner, chat, model, "what is your phone number")
    assert "5559876543" in repair_note(model) and result.ok
    again = ScriptedModel([response(text_block(f"Call us on {phone}."))])
    assert run(diner, chat, again, "what is your phone number")[0].reply == f"Call us on {phone}."


def test_the_visitors_own_email_and_phone_can_be_repeated_back(diner, chat):
    model = ScriptedModel([response(text_block("Thanks, I have jane@example.com and 512 555 0199 for you."))])
    result, _ = run(diner, chat, model, "my email is jane@example.com and my phone is 512-555-0199")
    assert result.ok and repair_note(model) is None


def test_a_time_no_tool_returned_is_not_sent(diner, chat):
    model = ScriptedModel([response(tool_block("get_business_info", {"field": "opening_hours"})),
                           response(text_block("We open tomorrow at 6:30pm.")),
                           response(text_block("Please check the opening hours above."))])
    result, _ = run(diner, chat, model, "when do you open tomorrow")
    assert result.ok and "18:30" in repair_note(model)


def test_a_price_not_in_the_data_is_not_sent(diner, chat):
    model = ScriptedModel([response(tool_block("search_menu", {"query": "burger"})),
                           response(text_block("The Smash Burger is 9.99.")),
                           response(text_block("The Smash Burger is 11.50."))])
    result, _ = run(diner, chat, model, "how much is the burger")
    assert result.reply == "The Smash Burger is 11.50." and "9.99" in repair_note(model)


def test_an_id_that_is_not_from_this_chat_is_not_sent(diner, chat):
    model = ScriptedModel([response(text_block("Your request id is 11111111-2222-3333-4444-555555555555.")),
                           response(text_block("I have no id for you."))])
    result, _ = run(diner, chat, model, "what is my request id")
    assert result.ok and "is not from a booking" in repair_note(model)


def test_the_check_unit_reads_clock_times_and_numbers():
    from pipeline.verify import facts_in
    facts = facts_in("Open 9:00am to 5pm, call +1 (555) 010-0105, 11.50 and $20, https://x.example/a/ done 2026-10-27")
    assert {540, 1020} <= {m for options in facts["times"] for m in options}
    assert facts["phones"] == ["15550100105"] and facts["urls"] == ["https://x.example/a"]
    assert 11.5 in facts["amounts"] and 20.0 in facts["amounts"]


def test_the_saved_records_name_the_request_type_and_what_the_visitor_sent(diner, chat):
    from pipeline import forms
    from pipeline.verify import records_text, saved_note
    ctx = make_ctx(diner, chat, "pass it on")
    assert records_text(ctx.conn, chat["session_id"]) == "(nothing is saved for this chat)" and saved_note(ctx) is None
    assert forms.save_request(ctx.client, ctx.conn, chat["session_id"], diner["category"], diner["customer"], "book_reservation",
                              {"name": "Agent Test Jane", "phone": "5125550199", "question": "Table for four"})
    text = records_text(ctx.conn, chat["session_id"])
    assert "type='table booking'" in text and "Agent Test Jane" in text and "Table for four" in text
    assert saved_note(ctx).startswith("Saved for this chat")


def test_the_repair_note_tells_the_model_what_is_saved(diner, chat):
    from pipeline import forms
    ctx = make_ctx(diner, chat, "pass it on")
    forms.save_request(ctx.client, ctx.conn, chat["session_id"], diner["category"], diner["customer"], "inquire_catering",
                       {"name": "Agent Test Jane", "email": "jane@example.com", "question": "Catering for 40"})
    model = ScriptedModel([response(text_block("Your table is booked.")), response(text_block("Your request is with the restaurant."))])
    chat_agent.run_agent(ctx, client=model)
    assert "Catering for 40" in repair_note(model) and "Agent Test Jane" in repair_note(model)


def test_the_model_is_told_what_is_saved_in_the_chat(diner, chat):
    from pipeline import forms
    ctx = make_ctx(diner, chat, "did you get my request")
    forms.save_request(ctx.client, ctx.conn, chat["session_id"], diner["category"], diner["customer"], "inquire_catering",
                       {"name": "Agent Test Jane", "email": "jane@example.com", "question": "Catering for 40"})
    model = ScriptedModel([response(text_block("Yes, your request is with the restaurant."))])
    chat_agent.run_agent(ctx, client=model)
    last = model.calls[0]["messages"][-1]["content"]
    assert isinstance(last, list) and any("Saved for this chat" in block["text"] for block in last)
