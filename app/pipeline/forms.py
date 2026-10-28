"""The request form: the card the widget shows when a visitor wants to book, request something, get a quote or talk to the
business. Nothing here calls a model.

  form_for          the card for one action, from the category and business bundles: the fields come from the action's
                    collect (conv_action.steps), their labels, formats and "why we ask" text from the request_handoff row of
                    conv_tool. At most PAGE_SIZE fields a page; an either group (phone or email) stays on one page.
  resolve           which step of an action is used for this business: booking when the business has booking on, then the
                    details step when the business has what it provides (a link), and the handover step always.
  details_reply     the fixed reply for an action that resolves to details: the link or facts on record.
  validate_request  the visitor's values against the form (shared/field_rules.py).
  save_request      writes the request as a row of conv_handover (request_type, action_key, extra_fields) and reads it back.
  confirm_saved     a plain query, on a new connection after the commit: a row for this chat and action with this phone or
                    email, made in the last minute. Only then is the visitor told the request was passed on.
"""

import json
import logging
from datetime import date

from pipeline.action_plan import step_possible
from pipeline.handover_save import save_handover_now
from pipeline.load_chat import session_key
from shared.action_steps import STANDARD_KEYS, collect_entries, is_link_key, provided_keys
from shared.field_rules import MESSAGES, check_field, validate_values
from tools.business_tools import field_value

log = logging.getLogger(__name__)

PAGE_SIZE = 3                 # fields on one page of the form: name and contact first, then the request
SESSION_SUBMITS = 6           # requests one chat may send
LABELS = {"send": "Send", "next": "Next", "back": "Back", "cancel": "Cancel", "cancelled": "No problem, nothing was sent."}
REASONS = {"request_from_visitor", "critical_question", "unsure_question", "unavailable_answer", "time_in_widget",
           "system_fallback"}
DEFAULT_REQUEST_TYPE = "direct handover"
LONG_TEXT = 120               # a text field that may be longer than this is shown as a text area


def find_action(category: dict, action_key: str) -> tuple[dict | None, bool]:
    """The action with this key: one of the business's own actions, or one of the general actions every category shares.
    Returns (action, is_general)."""
    for action in category.get("actions") or []:
        if action["key"] == action_key:
            return action, False
    general = (category.get("general_actions") or {}).get(action_key)
    return (general, True) if general else (None, False)


def resolve(category: dict, customer: dict, action_key: str) -> tuple[dict, dict, bool] | None:
    """(action, step, is_general) for this business: the first step of the action that is possible, or None when the key
    is not an action of this category."""
    action, general = find_action(category, action_key)
    if action is None:
        return None
    step = next((s for s in action["steps"] if general or step_possible(s, customer)), None)
    return (action, step, general) if step else None


def _standard_defs(category: dict) -> dict:
    """The definitions of the standard fields (label, format, why we ask), from the request_handoff row."""
    for tool in category.get("tools") or []:
        if tool["name"] == "request_handoff":
            return (((tool["inputs"].get("properties") or {}).get("prefill") or {}).get("properties")) or {}
    return {}


def _spec(entry: dict, defs: dict) -> dict:
    """One field of the form, from a collect entry. A standard field takes its label, format and help from the tool row; any
    other field carries them in the entry itself."""
    key = entry["key"]
    base = defs.get(key) if key in STANDARD_KEYS else None
    if base is None and "type" not in entry:
        raise ValueError(f"the field {key} is not a standard field and has no type")
    base = base or {}
    spec = {
        "key": key,
        "label": entry.get("label") or base.get("title") or key.replace("_", " ").capitalize(),
        "help": entry.get("description") or base.get("description") or "",
        "format": entry.get("format") or base.get("format"),
        "type": entry.get("type"),
        "max": entry.get("max") or base.get("maxLength"),
        "min": entry.get("min"),
        "min_length": entry.get("min_length") or base.get("minLength"),
        "required": bool(entry.get("required")),
    }
    spec["input"] = _input_kind(spec)
    return {k: v for k, v in spec.items() if v is not None}


def _input_kind(spec: dict) -> str:
    if spec.get("type") in ("integer", "number"):
        return "number"
    if spec.get("type") == "boolean":
        return "checkbox"
    form = spec.get("format")
    if form in ("phone", "email", "date", "time"):
        return {"phone": "tel"}.get(form, form)
    return "textarea" if int(spec.get("max") or 0) > LONG_TEXT else "text"


def fields_for(category: dict, step: dict) -> tuple[list[list[dict]], list[list[str]]]:
    """The units of the form in order: a field, or the fields of an either group (kept together). And the either groups."""
    defs = _standard_defs(category)
    units: list[list[dict]] = []
    groups: list[list[str]] = []
    for entry in collect_entries(step):
        if "any_of" in entry:
            groups.append(list(entry["any_of"]))
            units.append([_spec({"key": key, "required": False}, defs) for key in entry["any_of"]])
        else:
            units.append([_spec(entry, defs)])
    return units, groups


def _pages(units: list[list[dict]]) -> list[dict]:
    pages: list[list[dict]] = [[]]
    for unit in units:
        if pages[-1] and len(pages[-1]) + len(unit) > PAGE_SIZE:
            pages.append([])
        pages[-1] += unit
    return [{"fields": page} for page in pages if page]


def form_for(category: dict, customer: dict, action_key: str, prefill: dict | None = None, today: date | None = None) -> dict | None:
    """The card for an action, or None when the action has no form for this business (it resolves to a link, or the key is
    not an action of the category). prefill holds values the visitor already said; each is checked and dropped if wrong."""
    found = resolve(category, customer, action_key)
    if found is None or found[1]["route"] not in ("booking", "handover"):
        return None
    action, step, general = found
    units, groups = fields_for(category, step)
    flat = [spec for unit in units for spec in unit]
    values = {}
    for spec in flat:
        value, error = check_field(spec, (prefill or {}).get(spec["key"]), today or date.today())
        if value is not None and not error:
            values[spec["key"]] = value
    return {"type": "form", "action_key": action_key, "route": step["route"], "title": action["name"],
            "request_type": action.get("request_type") or DEFAULT_REQUEST_TYPE, "pages": _pages(units), "any_of": groups,
            "values": values, "labels": LABELS, "messages": MESSAGES}


def details_reply(category: dict, customer: dict, action_key: str) -> str | None:
    """The reply for an action that resolves to its details step: the business's link (or the facts it provides), in the
    category's fixed wording. None when the action does not resolve to details."""
    found = resolve(category, customer, action_key)
    if found is None or found[1]["route"] != "details":
        return None
    lines = []
    for key in provided_keys(found[1]):
        value = field_value(customer, key)
        if value is None:
            continue
        if is_link_key(key):
            lines.append(category["message_texts"]["details_link_reply"].replace("{link}", str(value)))
        else:
            text = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in value.items()) if isinstance(value, dict) else (
                ", ".join(map(str, value)) if isinstance(value, list) else str(value))
            lines.append(f"{key.replace('_', ' ').capitalize()}: {text}")
    return "\n".join(lines) or None


def validate_request(category: dict, customer: dict, action_key: str, values: dict, today: date) -> tuple[dict, dict]:
    """(clean values, errors by field key) for what the visitor submitted. Raises KeyError when the action has no form."""
    form = form_for(category, customer, action_key, today=today)
    if form is None:
        raise KeyError(action_key)
    flat = [spec for page in form["pages"] for spec in page["fields"]]
    return validate_values(flat, form["any_of"], values, today)


def allow_submit(client, session_id: str) -> bool:
    """A chat may send only a few requests, so a script cannot fill the business's list from one session."""
    key = session_key(session_id)
    return int(client.hincrby(key, "form_submits", 1)) <= SESSION_SUBMITS


def save_request(client, conn, session_id: str, category: dict, customer: dict, action_key: str, clean: dict) -> bool:
    """Write the request to conv_handover (name, phone, email and the query in their columns; everything else in
    extra_fields; request_type from the action) and read the row back. True when the row is in the table."""
    action, _, _ = resolve(category, customer, action_key)
    key = session_key(session_id)
    reason = client.hget(key, "handover_reason")
    payload = {"name": clean["name"], "email": clean.get("email"), "phone": clean.get("phone"),
               "question": clean.get("question") or action["name"]}
    extra = {k: v for k, v in clean.items() if k not in ("name", "email", "phone", "question")}
    client.hdel(key, "handover_saved", "handover_id")   # a chat may send more than one request: the earlier one is saved already
    client.hset(key, mapping={
        "handover": json.dumps(payload, ensure_ascii=False),
        "handover_reason": reason if reason in REASONS else "request_from_visitor",
        "handover_action": action_key,
        "handover_request_type": action.get("request_type") or DEFAULT_REQUEST_TYPE,
        "handover_extra": json.dumps(extra, ensure_ascii=False),
        "handover_stage": "",
    })
    client.sadd("session_updates", session_id)
    if save_handover_now(client, conn, session_id):
        return True
    client.hdel(key, "handover", "handover_action", "handover_request_type", "handover_extra")
    return False


def confirm_saved(open_connection, session_id: str, action_key: str, phone: str | None, email: str | None) -> bool:
    """A row for this chat and action, with this phone or email, made in the last minute. A plain query on a new connection,
    run after the commit: it needs no model and shows the row is in the table."""
    if not (phone or email):
        return False
    with open_connection() as conn:
        return conn.execute(
            """select 1 from conv_handover where session_id = %s and action_key = %s
               and ((%s::text is not null and phone = %s) or (%s::text is not null and email = %s))
               and created_at > now() - interval '1 minute' limit 1""",
            (session_id, action_key, phone, phone, email, email)).fetchone() is not None
