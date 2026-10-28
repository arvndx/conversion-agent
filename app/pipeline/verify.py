"""Check every reply before the visitor sees it, with fixed rules and no model call.

The model writes the reply, so the reply is checked against what is true before it goes out:
  1. It may say a request was passed on only when a request for this chat is in conv_handover (read back from the table,
     not taken from the model's word). It may never say something was booked or confirmed: a request form only passes the
     visitor's details to the business, which contacts them, so nothing is ever confirmed in the chat.
  2. Every link, email address, phone number, amount, clock time and id in it must come from somewhere real: what the tools
     returned this turn, the business's own data, or what the visitor said in this chat. Nothing the model made up.

The success and failure texts of the request form are fixed, and are not written by the model, so they are not checked here.
verify_reply returns the problems found (an empty list when the reply is fine). pipeline/agent.py gives the model one chance
to write the reply again with the problems named; a reply that still fails is not sent.
"""

import json
import logging
import re

import psycopg

from pipeline.claims import BOOKED, SENT
from pipeline.handover_save import handover_in_table
from tools.agent_tools import AgentContext

log = logging.getLogger(__name__)
NOTHING_SAVED = "(nothing is saved for this chat)"

UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
URL = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{5,}\d(?!\w)")
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\w)(?!\.\d)")   # a full stop that ends a sentence is not part of it
DECIMAL = re.compile(r"(?<![\w.])\d+\.\d+(?!\w)(?!\.\d)")
MONEY = re.compile(r"[$₹€£]\s?(\d[\d,]*(?:\.\d+)?)")
CLOCK = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?!\d)\s*(?:([ap])\.?m\b)?", re.IGNORECASE)
CLOCK_HOUR = re.compile(r"(?<![\d:.])(\d{1,2})\s*([ap])\.?m\b", re.IGNORECASE)


def _minutes(hour: int, minute: int, meridiem: str | None) -> list[int]:
    """The minutes after midnight a clock time can mean. Without am or pm, an hour up to 12 may be either."""
    if minute > 59 or hour > 24:
        return []
    if meridiem:
        return [(hour % 12 + (12 if meridiem.lower() == "p" else 0)) * 60 + minute] if 1 <= hour <= 12 else []
    return [hour * 60 + minute] + ([(hour % 12 + 12) * 60 + minute] if 1 <= hour <= 12 else [])


def _url(value: str) -> str:
    return value.rstrip(".,;:!?)").rstrip("/").lower()


def facts_in(text: str) -> dict[str, list]:
    """The links, emails, phone numbers, amounts, clock times and ids in a text. Clock times are lists of the minutes each can
    mean."""
    ids = [u.lower() for u in UUID.findall(text)]
    text = ISO_DATE.sub(" ", UUID.sub(" ", text))
    urls = [_url(u) for u in URL.findall(text)]
    text = URL.sub(" ", text)
    emails = [e.lower() for e in EMAIL.findall(text)]
    text = EMAIL.sub(" ", text)
    phones = [d for d in (re.sub(r"\D", "", p) for p in PHONE.findall(text)) if 7 <= len(d) <= 15]
    times = [_minutes(int(h), int(m), mer) for h, m, mer in CLOCK.findall(text)]
    times += [_minutes(int(h), 0, mer) for h, mer in CLOCK_HOUR.findall(text)]
    amounts = [float(a) for a in DECIMAL.findall(text)] + [float(a.replace(",", "")) for a in MONEY.findall(text)]
    return {"ids": ids, "urls": urls, "emails": emails, "phones": phones, "times": [t for t in times if t],
            "amounts": amounts, "numbers": [float(n) for n in NUMBER.findall(text)]}


def evidence(ctx: AgentContext) -> dict[str, list]:
    """What the reply may rely on: what the tools returned this turn, the business's own data, the held booking, and what
    was said in this chat (the visitor's words, and the earlier replies, which were checked the same way)."""
    parts = [json.dumps(ctx.results, ensure_ascii=False, default=str), json.dumps(ctx.customer, ensure_ascii=False, default=str),
             ctx.message, records_text(ctx.conn, ctx.session_id, ctx.customer["timezone"])]
    for turn in json.loads(ctx.session.get("conversation") or "[]"):
        parts += list(turn.get("request") or []) + [turn.get("response") or ""]
    return facts_in("\n".join(parts))


def _clock_text(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def verify_reply(ctx: AgentContext, reply: str) -> list[str]:
    """The problems with a reply: things it says that no tool, no business data and no visitor words support."""
    problems = []
    if SENT.search(reply) and not handover_in_table(ctx.conn, ctx.session_id):
        problems.append("it says the request was passed on, but no request is saved")
    if BOOKED.search(reply):
        problems.append("it says something is booked or confirmed, but nothing is confirmed in the chat: the business "
                        "contacts the visitor after they send the request form")
    said, known = facts_in(reply), evidence(ctx)
    problems += [f"the link {u} is not one the business has on record" for u in said["urls"] if u not in known["urls"]]
    problems += [f"the email address {e} was not given by the visitor or the business" for e in said["emails"]
                 if e not in known["emails"]]
    problems += [f"the phone number {p} was not given by the visitor or the business" for p in said["phones"]
                 if not any(p == k or (min(len(p), len(k)) >= 7 and (p.endswith(k) or k.endswith(p))) for k in known["phones"])]
    problems += [f"the booking id {i} is not from a booking" for i in said["ids"] if i not in known["ids"]]
    problems += [f"the amount {a:g} is not in the business's data" for a in said["amounts"]
                 if not any(abs(a - k) < 1e-9 for k in known["numbers"])]
    known_times = {t for alternatives in known["times"] for t in alternatives}
    problems += [f"the time {_clock_text(options[0])} was not in any tool result or said by the visitor"
                 for options in said["times"] if not known_times & set(options)]
    return problems


def records_text(conn: psycopg.Connection, session_id: str, timezone: str = "UTC") -> str:
    """What is saved in the tables for this chat: the requests the visitor sent."""
    lines = []
    for name, email, phone, question, action, request_type in conn.execute(
            """select name, email, phone, question, action_key, request_type from conv_handover where session_id = %s
               order by created_at""", (session_id,)).fetchall():
        lines.append(f"request (saved, passed on to the business): type={request_type!r} action={action!r} name={name!r} "
                     f"email={email!r} phone={phone!r} question={question!r}")
    return "\n".join(lines) or NOTHING_SAVED


def saved_note(ctx: AgentContext) -> str | None:
    """A note for the model when a request is saved for this chat. The model cannot see earlier turns' tool calls, so
    without this it cannot tell the visitor what was saved, and may deny it."""
    records = records_text(ctx.conn, ctx.session_id, ctx.customer["timezone"])
    return None if records == NOTHING_SAVED else "Saved for this chat (from the tables, this is what really happened):\n" + records
