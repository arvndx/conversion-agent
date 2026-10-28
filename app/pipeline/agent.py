"""The chat agent: one model (Sonnet 5.5) that chooses tools in a loop (tools/agent_tools.py).

Each visitor message that is not a quick-question click or a fixed reply goes through two steps:
  1. The safety check: urgent, abusive, or ordinary. Urgent and abusive messages never reach the agent.
  2. The agent loop: the model reads the recent chat and the message, calls tools as it needs them, and writes the reply.
     The loop stops when the model writes a reply without asking for a tool, or after MAX_STEPS tool rounds, or after
     TIME_LIMIT_SECONDS. At the step limit the model is asked once more for a reply with no tools. When the model opens
     the request form (request_handoff) the loop stops at once: the model is not called again, and the code writes the
     fixed reply that goes with the form.

The model never writes a price, a time, a link or a phone number from memory: those come from the tools.
"""

import json
import logging
import re
import time
from dataclasses import dataclass

from pipeline.action_plan import resolved_actions
from pipeline.classify import SAFETY_MODEL, SafetyResult, _checked, build_safety_prompt, parse_safety
from pipeline.verify import records_text, saved_note, verify_reply
from tools.agent_tools import AgentContext, run_tool, tool_schemas

AGENT_MODEL = "claude-sonnet-5-5"
MAX_STEPS = 6
TIME_LIMIT_SECONDS = 25
MAX_TOKENS = 1024
HISTORY_TURNS = 8
log = logging.getLogger(__name__)
TOOL_TEXT = re.compile(r"<\s*/?\s*(?:invoke|function_calls|parameter)\b", re.IGNORECASE)
MAX_REPAIRS = 1   # how many times the model may write a reply again after the check found a problem
REPAIR_NOTE = ("Your reply was not sent, because: {problems}.\nWhat is saved for this chat:\n{records}\nWrite the reply again. Say "
               "only what the tools returned, what is saved above, or what the visitor said. Do not deny what is saved above. "
               "If something was not done, say so plainly and offer to pass it on.")
FINAL_NUDGE = "Write the reply to the visitor now, in one to three short sentences, without asking for any tool."


@dataclass
class AgentResult:
    ok: bool                 # False: the model wrote nothing usable or the reply failed its checks; the caller offers a handover
    reply: str | None        # None when a form was opened: the caller writes the fixed reply that goes with it
    tools_used: list[str]
    gaps: int = 0            # lookups that found nothing this turn
    card: dict | None = None     # the request form the model opened
    failure: str | None = None   # "check_failed" when ok is False (the caller sets "model_error" when the model raised)


_CLIENT = None
CLIENT_TIMEOUT_SECONDS = 30.0


def _default_client():
    """One model client for the process, with a timeout, so a slow call fails and the visitor gets the busy reply."""
    global _CLIENT
    if _CLIENT is None:
        from anthropic import Anthropic
        from dotenv import load_dotenv
        from pipeline.classify import APP_DIR

        load_dotenv(APP_DIR / ".env")
        _CLIENT = Anthropic(timeout=CLIENT_TIMEOUT_SECONDS)
    return _CLIENT


def safety_check(category: dict, message: str, client=None) -> SafetyResult | None:
    """The urgent and abusive check on the raw message. None if the check failed (the caller uses the busy reply)."""
    system, user = build_safety_prompt(category, message)
    try:
        return _checked(SAFETY_MODEL, system, user, parse_safety, category, client or _default_client())
    except Exception:
        log.exception("safety check failed")
        return None


REQUEST_PLAN = ("Call request_handoff with action_key {key}. A form opens for the visitor, with: {collect}. Do not ask for "
                "these yourself; put in prefill only what the visitor already said. Write nothing after it.")
ROUTE_PLAN = {
    "booking": REQUEST_PLAN,
    "details": "Give the visitor what the business has on record: call get_business_info for {fields}.",
    "handover": REQUEST_PLAN,
}


def actions_text(category: dict, customer: dict) -> str:
    """The actions a visitor may ask for, each with the way to complete it for this business (chosen in code from the
    action's steps, pipeline/action_plan.py)."""
    lines = []
    for a in resolved_actions(category, customer):
        button = f' (button "{a["button"]}")' if a["button"] else ""
        plan = ROUTE_PLAN[a["route"]].format(collect=", ".join(a["collect"]), fields=" or ".join(a["provides"]), key=a["key"])
        lines.append(f"- {a['key']}{button}: {a['goal']} How, for this business: {plan}")
    if not lines:
        return ""
    return ("\n\nWhat visitors may ask for. The way to complete each one is already chosen for this business: follow it and "
            "do not use another way. When the visitor asks for one, start it.\n"
            + "\n".join(lines))


def build_system(category: dict, customer: dict, today) -> str:
    name = f'{customer["display_name"]["first_name"]} {customer["display_name"]["last_name"]}'.strip()
    words = category["category_id"].replace("_", " ")
    comp = category.get("compliance", {})
    rules = [f"- Never say: {p}" for p in comp.get("prohibited_phrases", [])[:12] if p]
    rules += [f"- Rule: {r}" for r in comp.get("content_restrictions", [])[:8]]
    never_ask = category.get("never_ask") or []
    text = f"""You are the chat assistant on the website of {name}, a {words} business. Today is {today.isoformat()} \
({customer["timezone"]}). You answer the visitor's questions about this business, and you can take a booking or pass the \
visitor's question to the business.

How to work:
- Use the tools for every fact: prices, times, links, phone numbers, availability, and what the business offers. Never \
guess or write these from memory. If a tool does not have the answer, say so plainly and offer to pass the question on \
(request_handoff).
- Ask one question at a time, in plain, short sentences. Keep each reply to one to three sentences.
- Write plain text only: no bold, no bullet symbols, no headings. For several items, list them with commas.
- Show prices as the tools give them, without adding a currency sign.
- Do not mention earlier replies or mistakes unless the visitor asks about them.
- To book, schedule, request, get a quote or reach the business, call request_handoff: it opens a form that collects the \
details, so do not ask for them yourself. You cannot confirm a booking or a time: the business contacts the visitor.
- Before you say something is not on record, check the matching field with get_business_info: the business may have added it.
- If the visitor asks for a person, or the question is unclear after one try, call request_handoff with action_key \
direct_handover.
- Do not quote rates, approvals, eligibility or prices that the tools did not give you.
- Offer only what the tools can do. You cannot change or add to a handover or a booking after it was made; say so if asked.
- If the menu or the business information does not list something, say you do not have it on record. Do not say the business
  does not offer it.
- Do not ask for national ID numbers, bank or card numbers, or income{"; also do not ask for: " + "; ".join(never_ask) if never_ask else ""}.
{chr(10).join(rules)}"""
    return text + actions_text(category, customer)


def history_messages(session: dict) -> list[dict]:
    """The last few turns of the chat as user and assistant messages, oldest first."""
    turns = json.loads(session.get("conversation") or "[]")[-HISTORY_TURNS:]
    messages = []
    for turn in turns:
        request = " ".join(turn.get("request") or [])
        response = turn.get("response") or ""
        if request:
            messages.append({"role": "user", "content": request})
        if response:
            messages.append({"role": "assistant", "content": response})
    # The API needs the messages to start with a user message and alternate.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    merged: list[dict] = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(dict(m))
    return merged


def _text(response) -> str:
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()


def run_agent(ctx: AgentContext, client=None, model: str = AGENT_MODEL) -> AgentResult:
    """The agent loop for one visitor message. Errors from the model are raised; the caller handles them."""
    client = client or _default_client()
    system = build_system(ctx.category, ctx.customer, ctx.today)
    tools = tool_schemas(ctx.category, ctx.customer)
    if not tools:   # for example a category bundle built before tools were read from conv_tool: the caller offers a handover
        raise RuntimeError("no tools for this chat: the category bundle names none")
    # What the model cannot see in the history: what is saved for this chat.
    notes = [n for n in (saved_note(ctx),) if n]
    message = ctx.message if not notes else [{"type": "text", "text": ctx.message}] + [{"type": "text", "text": n} for n in notes]
    messages = history_messages(ctx.session) + [{"role": "user", "content": message}]
    started = time.monotonic()

    def finish(reply: str | None) -> AgentResult:
        if reply and TOOL_TEXT.search(reply):   # the model wrote a tool call as text: never show that to the visitor
            log.warning("the model wrote a tool call as text: %s", reply[:200])
            reply = None
        return AgentResult(ok=bool(reply), reply=reply or None, tools_used=list(ctx.tools_used), gaps=ctx.gaps,
                           failure=None if reply else "check_failed")

    repairs = 0
    for _ in range(MAX_STEPS):
        if time.monotonic() - started > TIME_LIMIT_SECONDS:
            break
        response = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools, messages=messages,
        )
        if response.stop_reason != "tool_use":
            text = _text(response)
            problems = verify_reply(ctx, text) if text else []
            if problems and repairs < MAX_REPAIRS:   # the reply says something that is not true: one chance to write it again
                repairs += 1
                log.warning("reply not sent, written again: %s", "; ".join(problems))
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": REPAIR_NOTE.format(
                    problems="; ".join(problems), records=records_text(ctx.conn, ctx.session_id, ctx.customer["timezone"]))})
                continue
            return finish(None if problems else text)
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_tool(ctx, block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(output, ensure_ascii=False, default=str)})
        if not results:
            text = _text(response)
            return finish(None if text and verify_reply(ctx, text) else text)
        if ctx.card is not None:   # the form is open: the visitor fills it, and the model writes nothing more
            return AgentResult(ok=True, reply=None, tools_used=list(ctx.tools_used), gaps=ctx.gaps, card=ctx.card)
        messages.append({"role": "user", "content": results})

    # The steps are used up: one last reply, with no tools.
    messages.append({"role": "user", "content": FINAL_NUDGE})
    response = client.messages.create(
        model=model, max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    )
    text = _text(response)
    return finish(None if text and verify_reply(ctx, text) else text)
