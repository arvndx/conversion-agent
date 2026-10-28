"""Helpers for the steps of an action (conv_action.steps). Pure functions: no database, no model.

A step is {"route", "tools", "collect"?, "provides"?} (see shared/tool_checks.py). A details step provides business fields:
a name, or an any_of of names. A link is a business field whose name ends in _link (booking_link, menu_link, ...). The
business's links live in conv_professional_settings.special_fields under those names.

What a step collects is a list of entries, stored in the table (nothing is decided in code):
  {"key": "name", "required": true}                       a standard field; its label and rules come from the tool's inputs
  {"any_of": ["phone", "email"]}                          either: at least one of these is required
  {"key": "party_size", "type": "integer", "description": "...", "required": false}   any other field of the category
A plain name (the older shape) means a required standard field.
"""

LINK_SUFFIX = "_link"
STANDARD_KEYS = ("name", "phone", "email", "question", "date", "time", "note")   # fields every business may collect
CONTACT_KEYS = ("phone", "email")


def normalize_key(key: str) -> str:
    return "_".join((key or "").strip().lower().split())


def is_link_key(key: str) -> bool:
    return normalize_key(key).endswith(LINK_SUFFIX)


def provided_keys(step: dict) -> list[str]:
    """The business fields a step provides, in order; an any_of is flattened."""
    keys: list[str] = []
    for entry in step.get("provides") or []:
        keys += [entry] if isinstance(entry, str) else list(entry.get("any_of") or [])
    return keys


def step_for(steps: list[dict], route: str) -> dict | None:
    return next((s for s in steps or [] if s.get("route") == route), None)


def collect_entries(step: dict) -> list[dict]:
    """What a step collects, in one shape: {"key", "required", ...} for a field, {"any_of": [...]} for an either group."""
    entries = []
    for entry in step.get("collect") or []:
        if isinstance(entry, str):
            entries.append({"key": entry, "required": True})
        elif "any_of" in entry:
            entries.append({"any_of": list(entry["any_of"])})
        else:
            entries.append({**entry, "required": entry.get("required", True)})
    return entries


def extras_of(step: dict) -> list[dict]:
    """The fields this step collects that are special to the category: {"key", "type", "description"}."""
    return [e for e in collect_entries(step) if "key" in e and "type" in e]


def collects_contact(step: dict) -> bool:
    """True when the step asks for a phone or an email: an either group that names one, or a required one."""
    for entry in collect_entries(step):
        if "any_of" in entry and any(k in CONTACT_KEYS for k in entry["any_of"]):
            return True
        if entry.get("key") in CONTACT_KEYS and entry["required"]:
            return True
    return False


def collect_words(step: dict) -> list[str]:
    """What a step collects, as words for the agent: name, "phone or email", party_size (number of guests...)."""
    words = []
    for entry in collect_entries(step):
        if "any_of" in entry:
            words.append(" or ".join(entry["any_of"]))
            continue
        word = f"{entry['key']} ({entry['description'].rstrip('.')})" if entry.get("description") and "type" in entry else entry["key"]
        words.append(word if entry["required"] else word + " (optional)")
    return words


def links_for_actions(actions: list[dict], fields: dict) -> dict[str, str]:
    """{action_key: url} for the actions whose details step provides a link the business has. fields is the business's
    special_fields."""
    links = {}
    for action in actions:
        step = step_for(action.get("steps"), "details")
        for key in provided_keys(step) if step else []:
            if is_link_key(key) and fields.get(key):
                links[action["key"]] = fields[key]
                break
    return links
