"""Checks on the tools (conv_tool) and on the steps of the actions (conv_action.steps).

An action's steps are an ordered list. Each step is one route: booking, details or handover. A step names its tools, what
to collect from the visitor (collect) and, for details, which business fields it gives (provides):

  {"route": "booking",  "tools": ["request_handoff"], "collect": [{"key": "name", "required": true}, {"any_of": ["phone", "email"]}, ...]}
  {"route": "details",  "tools": ["get_business_info"],  "provides": ["booking_link"]}
  {"route": "handover", "tools": ["request_handoff"],    "collect": [{"key": "name", "required": true}, {"any_of": ["phone", "email"]}, {"key": "question", "required": true}]}

A collect entry is a field ({"key", "required"}, plus "type" and "description" for a field that is not a standard one), or an
either group ({"any_of": [...]}: at least one of them is required). A plain field name still means a required standard
field. Every enabled action has a request_type (the label saved on its requests). The actions under the shared gcid
"general" are the situations that end in a handover without a business button. The fixed replies (conv_static_reply) are
checked here too. The checks are run on the demo data in the tests, and by hand:
  .venv/bin/python -m shared.tool_checks
"""

import os
import re

import psycopg

from shared.action_steps import STANDARD_KEYS, collect_entries, collects_contact

ROUTES = ("booking", "details", "handover")
REQUIRED_TOOLS = ("get_business_info", "request_handoff")   # every category must be able to answer and to hand over
FIELD_TYPES = ("string", "integer", "number", "boolean")
GENERAL = "general"   # the gcid of the actions and fixed replies every category shares
GENERAL_ACTIONS = ("critical_handover", "ai_down_handover", "fallback_handover", "direct_handover")
MATCHED_INTENTS = ("greeting", "how_are_you", "ai_identity", "thanks", "goodbye", "acknowledgement", "apology", "just_browsing", "social",
                   "privacy", "unclear")   # a visitor's whole message triggers these
TRIGGERED_INTENTS = ("abuse_warning", "fallback_apology")   # the code triggers these itself
MIN_REPLIES = 10
FIELD_FORMATS = ("name", "phone", "email", "text", "date", "time")   # what a standard field may be checked as
PLACEHOLDERS = {"{customer_name}", "{category}"}


def _any_of_problem(entry: dict) -> str | None:
    names = entry.get("any_of")
    if set(entry) != {"any_of"} or not isinstance(names, list) or len(names) < 2 or not all(isinstance(n, str) and n for n in names):
        return "an any_of needs two or more field names and nothing else"
    return None


def _collect_problem(entry) -> str | None:
    if isinstance(entry, str):
        return None if entry else "an empty field name"
    if not isinstance(entry, dict):
        return "a collect entry must be a field, an any_of or a field name"
    if "any_of" in entry:
        return _any_of_problem(entry)
    key = entry.get("key")
    if not isinstance(key, str) or not key:
        return "a collect field needs a key"
    if "required" in entry and not isinstance(entry["required"], bool):
        return f"field {key}: required must be true or false"
    if key not in STANDARD_KEYS or "type" in entry:
        if entry.get("type") not in FIELD_TYPES:
            return f"field {key}: type must be one of {', '.join(FIELD_TYPES)}"
        if not isinstance(entry.get("description"), str) or not entry["description"].strip():
            return f"field {key}: needs a description"
    return None


def _provides_problem(entry) -> str | None:
    if isinstance(entry, str):
        return None if entry else "an empty provides name"
    if isinstance(entry, dict):
        return _any_of_problem(entry)
    return "a provides entry must be a field name or an any_of"


def find_problems(tools: dict[str, bool], actions: list[dict]) -> list[str]:
    """tools: tool name -> enabled. actions: dicts with gcid, action_key, enabled and steps. Returns the problems found."""
    problems = []
    used: dict[str, set[str]] = {}            # gcid -> tools named by its enabled actions
    extra_types: dict[str, dict[str, str]] = {}   # gcid -> extra field key -> type
    for a in actions:
        where = f"{a['gcid']} / {a['action_key']}"
        if a["enabled"] and not (a.get("request_type") or "").strip():
            problems.append(f"{where}: has no request_type")
        steps = a.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"{where}: has no steps")
            continue
        routes = []
        for i, step in enumerate(steps, 1):
            at = f"{where} step {i}"
            if not isinstance(step, dict) or step.get("route") not in ROUTES:
                problems.append(f"{at}: route must be one of {', '.join(ROUTES)}")
                continue
            routes.append(step["route"])
            names = step.get("tools")
            if not isinstance(names, list) or not names:
                problems.append(f"{at}: names no tools")
                names = []
            for name in names:
                if name not in tools:
                    problems.append(f"{at}: tool {name} is not in conv_tool")
                elif a["enabled"] and not tools[name]:
                    problems.append(f"{at}: tool {name} is switched off")
                elif a["enabled"]:
                    used.setdefault(a["gcid"], set()).add(name)
            for entry in step.get("collect", []):
                message = _collect_problem(entry)
                if message:
                    problems.append(f"{at}: {message}")
                elif isinstance(entry, dict) and "key" in entry and "type" in entry:
                    seen = extra_types.setdefault(a["gcid"], {})
                    if seen.setdefault(entry["key"], entry["type"]) != entry["type"]:
                        problems.append(f"{at}: extra field {entry['key']} has two different types in this category")
            if step["route"] in ("booking", "handover"):   # the table needs a name and a way to reach the visitor
                valid = {"collect": [e for e in step.get("collect") or [] if _collect_problem(e) is None]}
                if not any(e.get("key") == "name" and e["required"] for e in collect_entries(valid)):
                    problems.append(f"{at}: a {step['route']} step must collect a required name")
                if not collects_contact(valid):
                    problems.append(f"{at}: a {step['route']} step must collect a phone or an email")
            if step["route"] == "details" and not step.get("provides"):
                problems.append(f"{at}: a details step must say what it provides")
            for entry in step.get("provides", []):
                message = _provides_problem(entry)
                if message:
                    problems.append(f"{at}: {message}")
        if len(set(routes)) != len(routes):
            problems.append(f"{where}: a route appears twice")
        if routes and routes[-1] != "handover":
            problems.append(f"{where}: the last step must be handover")
    for gcid, names in sorted(used.items()):
        if gcid == GENERAL:   # these only hand over; a category's own actions are what must answer
            continue
        for required in REQUIRED_TOOLS:
            if required not in names:
                problems.append(f"{gcid}: its enabled actions never name {required}")
    return problems


def general_problems(actions: list[dict]) -> list[str]:
    """The shared actions must exist, be on, and only hand over."""
    mine = {a["action_key"]: a for a in actions if a["gcid"] == GENERAL}
    problems = [f"{GENERAL}: the action {key} is missing or switched off" for key in GENERAL_ACTIONS
                if key not in mine or not mine[key]["enabled"]]
    for key, a in mine.items():
        if [s.get("route") for s in a.get("steps") or []] != ["handover"]:
            problems.append(f"{GENERAL} / {key}: a general action has only a handover step")
    return problems


def static_reply_problems(rows: list[tuple]) -> list[str]:
    """rows: (gcid, intent, patterns, replies). The shared set must have every intent; each intent needs enough replies, only
    the placeholders the chat fills, and (for matched intents) phrases that no other intent uses."""
    problems = []
    by_gcid: dict[str, dict[str, tuple]] = {}
    for gcid, intent, patterns, replies in rows:
        by_gcid.setdefault(gcid, {})[intent] = (patterns, replies)
    for intent in MATCHED_INTENTS + TRIGGERED_INTENTS:
        if intent not in by_gcid.get(GENERAL, {}):
            problems.append(f"{GENERAL} / {intent}: the shared fixed replies are missing")
    for gcid, intents in sorted(by_gcid.items()):
        seen: dict[str, str] = {}
        for intent, (patterns, replies) in sorted(intents.items()):
            where = f"{gcid} / {intent}"
            if len(replies) < MIN_REPLIES:
                problems.append(f"{where}: needs at least {MIN_REPLIES} replies")
            if len({r.strip().lower() for r in replies}) != len(replies) or any(not r.strip() for r in replies):
                problems.append(f"{where}: replies must be different and not empty")
            for reply in replies:
                unknown = set(re.findall(r"\{[^}]*\}", reply)) - PLACEHOLDERS
                if unknown:
                    problems.append(f"{where}: unknown placeholder {', '.join(sorted(unknown))}")
            if intent in TRIGGERED_INTENTS and patterns:
                problems.append(f"{where}: the code triggers this itself, so it has no patterns")
            if intent not in TRIGGERED_INTENTS and not patterns:
                problems.append(f"{where}: needs at least one pattern")
            for phrase in patterns:
                if not re.fullmatch(r"[a-z0-9]+( [a-z0-9]+)*", phrase):
                    problems.append(f"{where}: pattern {phrase!r} must be lower case words and digits only, no punctuation")
                if seen.setdefault(phrase, intent) != intent:
                    problems.append(f"{where}: pattern {phrase!r} is also used by {seen[phrase]}")
    return problems


def request_handoff_problems(inputs: dict | None) -> list[str]:
    """The request_handoff row defines every standard field once (label, format, why we ask) under prefill, for the form."""
    props = ((inputs or {}).get("properties") or {})
    problems = [] if "action_key" in props else ["request_handoff: its inputs need an action_key"]
    fields = (props.get("prefill") or {}).get("properties") or {}
    for key in STANDARD_KEYS:
        spec = fields.get(key)
        if not isinstance(spec, dict):
            problems.append(f"request_handoff: prefill does not define the field {key}")
            continue
        if not str(spec.get("title") or "").strip() or not str(spec.get("description") or "").strip():
            problems.append(f"request_handoff: the field {key} needs a title and a description (the label and why we ask)")
        if spec.get("format") not in FIELD_FORMATS:
            problems.append(f"request_handoff: the field {key} needs a format, one of {', '.join(FIELD_FORMATS)}")
    return problems


def load_rows(conn: psycopg.Connection) -> tuple[dict[str, bool], list[dict]]:
    tools = dict(conn.execute("select name, enabled from conv_tool").fetchall())
    actions = [{"gcid": g, "action_key": k, "enabled": e, "steps": s, "request_type": r} for g, k, e, s, r in conn.execute(
        "select gcid, action_key, enabled, steps, request_type from conv_action order by gcid, action_key").fetchall()]
    return tools, actions


def check_database(conn: psycopg.Connection) -> list[str]:
    tools, actions = load_rows(conn)
    static = conn.execute("select gcid, intent, patterns, replies from conv_static_reply order by gcid, intent").fetchall()
    handoff = conn.execute("select inputs from conv_tool where name = 'request_handoff'").fetchone()
    return (find_problems(tools, actions) + general_problems(actions) + static_reply_problems(static)
            + (request_handoff_problems(handoff[0]) if handoff else []))


if __name__ == "__main__":
    with psycopg.connect(os.environ.get("DATABASE_URL", "postgresql://localhost:5432/conversion_agent")) as c:
        found = check_database(c)
    print("\n".join(found) if found else "no problems")
    raise SystemExit(1 if found else 0)
