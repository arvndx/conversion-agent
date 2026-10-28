"""The turn runner (A79): the steps for one message or one form.

    0  load the chat (start_turn): stop, start a new chat, or continue
    1  read the message (receive_message, take_turn): the quiet period, the length limit, repeats
    2  a quick-question click (action_key): no model. The code resolves the action for this business and returns the request
       form, or the link or facts it provides
    3  a handover offer waiting for yes or no: a yes opens the form of the right general action, no model
    4  a fixed reply (pipeline/static_replies.py): "hi", "thanks", "are you a bot?" and similar, no model
    5  the safety check (a model call): urgent, abusive, or ordinary
    6  the agent (a model call or more, pipeline/agent.py): answers from the tools, or opens the request form
    7  the turn is saved to the session, and the session is marked for the batch

The form the visitor fills is submitted on its own (handle_form): the code checks the values, saves the request to conv_handover,
commits, and confirms with a plain query on a new connection that the row is there before the visitor is told. No model is
called for a form.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import psycopg
import redis

from pipeline import agent as chat_agent
from pipeline import forms
from pipeline import static_replies
from pipeline import store as conv_store
from pipeline.abuse import apply_strike
from pipeline.load_chat import session_key, start_turn
from pipeline.read_message import receive_message, take_turn
from tools.agent_tools import AgentContext

log = logging.getLogger(__name__)
YES_START = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please", "certainly", "definitely", "absolutely", "alright"}
# Yes answers that begin with more than one word ("of course", "go ahead").
YES_PHRASES = ("of course", "go ahead", "please do", "yes please", "sounds good", "that would be great", "that would be good")
YES_WORDS = YES_START | {"yes please"}
NO_WORDS = {"no", "nope", "nah", "not now", "no thanks", "no thank you", "not really", "i would rather not"}
# The texts are in the category bundle (conv_category_settings.other_messages). A bundle built before they were added has
# none of them, so a chat that is still on that bundle uses these.
FORM_TEXTS = {
    "form_intro": "Please fill in these details and I will pass them to {customer_name}.",
    "request_sent": "We have conveyed your request to {customer_name}. They will contact you back as soon as possible.",
    "request_not_saved": "We are unable to process your request right away. Could you please contact {customer_name} directly on {contact}?",
    "request_not_saved_no_contact": "We are unable to process your request right away. Please try again in a few minutes.",
    "details_link_reply": "Here is the link: {link}",
}
OFFER_ACTIONS = {"critical_question": "critical_handover", "system_fallback": "fallback_handover",
                 "unsure_question": "fallback_handover", "unavailable_answer": "direct_handover"}


@dataclass
class TurnOutcome:
    state: str  # "reply", "waiting", "stopped", "ignored", "blocked" or "form_errors"
    reply: str | None = None
    reason: str | None = None
    block_token: str | None = None
    card: dict | None = None      # the request form to show under the reply
    errors: dict | None = None    # field key -> message, for a form that was not accepted


def fill(text: str, customer: dict, category: dict) -> str:
    """Fill {customer_name} and {category} in a reply, from the bundles."""
    name = f'{customer["display_name"]["first_name"]} {customer["display_name"]["last_name"]}'
    words = category["category_id"].replace("_", " ")   # "mortgage_broker" reads as "mortgage broker"
    return text.replace("{customer_name}", name).replace("{category}", words)


def _text(category: dict, key: str) -> str:
    return category["message_texts"].get(key) or FORM_TEXTS[key]


def _yes_or_no(message: str) -> str | None:
    words = re.sub(r"[^a-z ]", "", message.lower()).split()
    phrase = " ".join(words)
    if phrase in NO_WORDS:
        return "no"
    if phrase in YES_WORDS:
        return "yes"
    # A short reply that starts with yes ("yes please pass it on") is a yes.
    if words and words[0] in YES_START and len(words) <= 6:
        return "yes"
    if phrase.startswith(YES_PHRASES) and len(words) <= 6:
        return "yes"
    return None


def _contact_text(customer: dict) -> str:
    """How the visitor can reach the business directly, as the business shares it in the chat: "555 0100 or a@b.com"."""
    shown, contact = customer.get("chat_contact") or {}, customer.get("public_contact") or {}
    return " or ".join(contact[k] for k in ("phone", "email") if shown.get(k) and contact.get(k))


def _create_session(client, session_id, resource_type, resource_id, domain, now_dt, consent, visitor_id, location,
                    notice_version=""):
    client.hset(session_key(session_id), mapping={
        "session_id": session_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "domain": domain,
        "started_at": now_dt.isoformat(),
        "last_activity_at": now_dt.isoformat(),
        "status": "open",
        "consent": "1" if consent else "0",
        "visitor_id": visitor_id or "",
        "location": location or "",
        "notice_version": notice_version or "",
        "turn_count": 0,
        "update_status": 0,
        "conversation": "[]",
        "abuse_strikes": 0,
        "handover_stage": "",
    })
    client.sadd("open_sessions", session_id)


def _save_turn(client, session_id, message, reply, now_dt):
    key = session_key(session_id)
    conversation = json.loads(client.hget(key, "conversation") or "[]")
    conversation.append({"request": [message], "response": reply or "", "event_time": now_dt.isoformat()})
    client.hset(key, mapping={
        "conversation": json.dumps(conversation, ensure_ascii=False),
        "turn_count": len(conversation),
        "last_activity_at": now_dt.isoformat(),
        "update_status": 1,
    })
    client.sadd("session_updates", session_id)
    client.sadd("open_sessions", session_id)


def _breaks_compliance(text: str, category: dict) -> bool:
    """A reply that uses a phrase the category prohibits (exp_category_compliance) is never sent."""
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in category.get("compliance", {}).get("prohibited_phrases", []) if phrase)


def _open_form(client, session_id, category, customer, action_key, reason, question, now_dt, prefill=None) -> TurnOutcome | None:
    """The outcome that shows the request form of an action: the fixed intro and the card. None when the action has no form
    for this business."""
    form = forms.form_for(category, customer, action_key, prefill, now_dt.astimezone(ZoneInfo(customer["timezone"])).date())
    if form is None:
        return None
    client.hset(session_key(session_id), mapping={"handover_reason": reason, "handover_question": question or "",
                                                  "handover_stage": ""})
    return TurnOutcome("reply", reply=fill(_text(category, "form_intro"), customer, category), card=form)


def _unavailable(client, session_id, category, customer) -> str:
    """The reply when nothing can be done for the visitor's request: one of the fixed apologies."""
    apology = static_replies.pick(client, session_id, "fallback_apology", category.get("static_replies") or {})
    return fill(apology or category["message_texts"].get("ai_busy") or "Sorry, I can't do that right now.", customer, category)


def _click(client, session_id, category, customer, action_key, message, now_dt) -> TurnOutcome:
    """A quick-question click: no model. The action comes from this business's bundle; the visitor's click names it only."""
    action, general = forms.find_action(category, action_key)
    if action is None or general:
        return TurnOutcome("reply", reply=_unavailable(client, session_id, category, customer))
    reply = forms.details_reply(category, customer, action_key)
    if reply is not None:
        return TurnOutcome("reply", reply=fill(reply, customer, category))
    outcome = _open_form(client, session_id, category, customer, action_key, "request_from_visitor", message, now_dt)
    return outcome or TurnOutcome("reply", reply=_unavailable(client, session_id, category, customer))


def _offer(client, session_id, category, customer, message, reason, lead: str | None = None) -> str:
    """A handover offer: the visitor is asked whether to pass the question on. A yes opens the form of the general action that
    goes with the reason. lead is what is said first (the topic's reply, or an apology)."""
    client.hset(session_key(session_id), mapping={
        "handover_stage": "offered", "handover_question": message, "handover_reason": reason,
        "handover_action": OFFER_ACTIONS.get(reason, "direct_handover")})
    follow = category["message_texts"]["critical_handover_follow" if reason == "critical_question" else "handover_offer"]
    return fill(f"{lead}\n{follow}".strip() if lead else follow, customer, category)


def _apology(client, session_id, category) -> str | None:
    return static_replies.pick(client, session_id, "fallback_apology", category.get("static_replies") or {})


def _offer_step(client, session_id, category, customer, session, message, now_dt) -> TurnOutcome | None:
    """The visitor's answer to a handover offer. Yes: the form (no model). No: the decline text. Anything else: the offer is
    dropped and the message is handled as usual (None)."""
    stage = session.get("handover_stage", "")
    if stage != "offered":
        client.hset(session_key(session_id), "handover_stage", "")   # a stage from an older version of the chat
        return None
    answer = _yes_or_no(message)
    if answer == "no":
        client.hset(session_key(session_id), "handover_stage", "")
        return TurnOutcome("reply", reply=fill(category["message_texts"]["handover_declined"], customer, category))
    if answer != "yes":
        client.hset(session_key(session_id), "handover_stage", "")
        return None
    action_key = session.get("handover_action") or "direct_handover"
    question = session.get("handover_question") or ""
    outcome = _open_form(client, session_id, category, customer, action_key, session.get("handover_reason") or "request_from_visitor",
                         question, now_dt, prefill={"question": question})
    return outcome or TurnOutcome("reply", reply=_unavailable(client, session_id, category, customer))


def _agent_handle(client, conn, category, customer, session, session_id, message, now_dt, resource_id, domain) -> TurnOutcome:
    """One turn on the agent path: the safety check first, then the agent. Urgent and abusive messages never reach it."""
    messages = category["message_texts"]
    state, token, card = "reply", None, None
    answered = None   # whether the business's question counts as answered; None: the turn is not recorded as a question
    safety = chat_agent.safety_check(category, message)
    if safety is None:   # the model could not check the message: nothing is answered, a handover is offered
        reply = _offer(client, session_id, category, customer, message, "system_fallback", _apology(client, session_id, category))
        client.hset(session_key(session_id), "handover_action", "ai_down_handover")
        answered = False
    elif safety.abusive:
        warning = static_replies.pick(client, session_id, "abuse_warning", category.get("static_replies") or {}) \
            or messages["abuse_warning"]
        strike = apply_strike(client, session_id, fill(warning, customer, category))
        if strike.state == "warning":
            reply = strike.reply
        else:
            state, token, reply = "blocked", strike.block_token, None
    elif safety.critical == "yes":
        topic = next(t for t in category["critical_topics"] if t["id"] == safety.critical_topic)
        reply = _offer(client, session_id, category, customer, message, "critical_question", topic["reply"])
    elif safety.critical == "unsure" and _yes_or_no(message) is None:
        # A plain yes or no is never urgent (the check often cannot tell a single "yes"): it goes to the agent.
        reply = _offer(client, session_id, category, customer, message, "unsure_question", _apology(client, session_id, category))
    else:
        ctx = AgentContext(client=client, conn=conn, category=category, customer=customer, session_id=session_id,
                           professional_id=resource_id, domain=domain, session=session, message=message, now=now_dt)
        try:
            result = chat_agent.run_agent(ctx)
        except Exception:
            log.exception("agent turn failed for chat %s", session_id)
            result = chat_agent.AgentResult(ok=False, reply=None, tools_used=[], failure="model_error")
        if result.card is not None:
            reply, card = fill(_text(category, "form_intro"), customer, category), result.card
            answered = client.hget(session_key(session_id), "handover_reason") == "request_from_visitor"
        elif not result.ok or _breaks_compliance(result.reply, category):
            reply = _offer(client, session_id, category, customer, message, "system_fallback", _apology(client, session_id, category))
            if result.failure == "model_error":
                client.hset(session_key(session_id), "handover_action", "ai_down_handover")
            answered = False
        else:
            reply = result.reply
            answered = result.gaps == 0
    if answered is not None:
        with conn.cursor() as cur:
            conv_store.record_question(cur, {"professional_id": resource_id, "domain": domain}, message, None, answered=answered)
    if reply:
        reply = fill(reply, customer, category)
    return TurnOutcome(state, reply=reply, block_token=token, card=card)


def _begin(client, conn, session_id, resource_type, resource_id, domain, now_dt, block_token, consent, visitor_id, location):
    """Step 0: load the chat. Returns (turn, category, customer); the chat is created and pinned to the bundles when new."""
    turn = start_turn(client, conn, session_id, resource_type, resource_id, domain, block_token=block_token)
    if turn.state == "stopped":
        return turn, None, None
    category, customer = turn.bundles.category, turn.bundles.customer
    if turn.state == "new_chat":
        _create_session(client, session_id, resource_type, resource_id, domain, now_dt, consent, visitor_id, location,
                        notice_version=(category.get("guardrails_text") or {}).get("version", "v1"))
    if turn.bundles.versions and turn.state in ("new_chat", "ready"):
        # The chat keeps these bundle versions for every later message (a newer build reaches new chats only).
        client.hset(session_key(session_id), mapping={"customer_v": turn.bundles.versions[0],
                                                      "category_v": turn.bundles.versions[1]})
    return turn, category, customer


def handle_message(
    client: redis.Redis,
    conn: psycopg.Connection,
    session_id: str,
    resource_type: str,
    resource_id: str,
    domain: str,
    *,
    text: str | None = None,
    msg_id: str | None = None,
    now: float | None = None,
    consent: bool = True,
    visitor_id: str = "",
    location: str = "",
    activity_id: str = "",
    block_token: str | None = None,
    action_key: str | None = None,
) -> TurnOutcome:
    """Run one turn. Call with text when a message arrives (and action_key when the visitor clicked a quick question), or
    without text to check whether a waiting turn is ready."""
    now_ts = time.time() if now is None else now
    now_dt = datetime.fromtimestamp(now_ts, timezone.utc)

    turn, category, customer = _begin(client, conn, session_id, resource_type, resource_id, domain, now_dt, block_token,
                                      consent, visitor_id, location)
    if activity_id:
        client.hsetnx(session_key(session_id), "activity_id", activity_id)   # the visit this chat is part of
    if turn.state == "stopped":
        return TurnOutcome("stopped", reason=turn.reason)

    if text is not None:
        receipt = receive_message(client, session_id, msg_id or str(uuid.uuid4()), text, now=now_ts)
        if receipt.state == "too_long":
            return TurnOutcome("reply", reply=fill(category["message_texts"]["too_long"], customer, category))
        if receipt.state in ("empty", "duplicate"):
            return TurnOutcome("ignored", reason=receipt.state)

    read = take_turn(client, session_id, now=now_ts)
    if read.state == "waiting":
        return TurnOutcome("waiting")
    if read.state == "stopped":
        return TurnOutcome("reply", reply=fill(category["message_texts"]["too_long"], customer, category), reason=read.reason)
    message = read.text

    if action_key:   # a quick-question click: no model
        outcome = _click(client, session_id, category, customer, action_key, message, now_dt)
        _save_turn(client, session_id, message, outcome.reply, now_dt)
        return outcome

    session = {k: v for k, v in client.hgetall(session_key(session_id)).items()}
    session["session_id"] = session_id
    if session.get("handover_stage"):
        outcome = _offer_step(client, session_id, category, customer, session, message, now_dt)
        if outcome is not None:
            _save_turn(client, session_id, message, outcome.reply, now_dt)
            return outcome

    intent = static_replies.match(message, category.get("static_replies") or {}, static_replies.asked_a_question(session))
    if intent is not None:   # a greeting, thanks, goodbye or similar: a fixed reply, no model
        reply = static_replies.pick(client, session_id, intent, category["static_replies"])
        if reply:
            reply = fill(reply, customer, category)
            _save_turn(client, session_id, message, reply, now_dt)
            return TurnOutcome("reply", reply=reply)

    outcome = _agent_handle(client, conn, category, customer, session, session_id, message, now_dt, resource_id, domain)
    _save_turn(client, session_id, message, outcome.reply or "", now_dt)
    return outcome


def handle_form(
    client: redis.Redis,
    conn: psycopg.Connection,
    open_connection,
    session_id: str,
    resource_type: str,
    resource_id: str,
    domain: str,
    action_key: str,
    values: dict,
    *,
    now: float | None = None,
    consent: bool = True,
    visitor_id: str = "",
    location: str = "",
    activity_id: str = "",
    block_token: str | None = None,
) -> TurnOutcome:
    """The visitor sent the request form. No model. The values are checked against the action's form; the request is saved to
    conv_handover and committed; then a plain query on a new connection (open_connection) confirms the row is there, and only
    then is the visitor told the request was passed on."""
    now_ts = time.time() if now is None else now
    now_dt = datetime.fromtimestamp(now_ts, timezone.utc)
    turn, category, customer = _begin(client, conn, session_id, resource_type, resource_id, domain, now_dt, block_token,
                                      consent, visitor_id, location)
    if activity_id:
        client.hsetnx(session_key(session_id), "activity_id", activity_id)
    if turn.state == "stopped":
        return TurnOutcome("stopped", reason=turn.reason)
    found = forms.resolve(category, customer, action_key)
    if found is None or found[1]["route"] not in ("booking", "handover"):
        return TurnOutcome("reply", reply=_unavailable(client, session_id, category, customer))
    today = now_dt.astimezone(ZoneInfo(customer["timezone"])).date()
    clean, errors = forms.validate_request(category, customer, action_key, values or {}, today)
    if errors:
        return TurnOutcome("form_errors", errors=errors)

    saved = forms.allow_submit(client, session_id) and forms.save_request(client, conn, session_id, category, customer,
                                                                           action_key, clean)
    if saved:
        conn.commit()   # the row must be committed before the new connection looks for it
    else:
        conn.rollback()
    confirmed = saved and forms.confirm_saved(open_connection, session_id, action_key, clean.get("phone"), clean.get("email"))
    if confirmed:
        reply = fill(_text(category, "request_sent"), customer, category)
    else:
        contact = _contact_text(customer)
        reply = fill(_text(category, "request_not_saved" if contact else "request_not_saved_no_contact").replace("{contact}", contact),
                     customer, category)
    _save_turn(client, session_id, f"[sent the request form: {found[0].get('request_type') or forms.DEFAULT_REQUEST_TYPE}]",
               reply, now_dt)
    return TurnOutcome("reply", reply=reply)
