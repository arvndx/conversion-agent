"""The tools the agent may call (A65). Each tool reads the bundles it is given and never writes to the database.

The category decides which tools a chat may use: a tool outside the category's "tools" list is refused.
The business is taken from the bundles the code loaded, never from the model's arguments.

Tools:
    get_menu()                        the full menu, grouped by section
    search_menu(query)                dishes that match the query (fuzzy); the full menu if nothing matches
    get_business_info(field)          one allowed field of the business
The request form (request_handoff) is opened by tools/agent_tools.py and saved by pipeline/forms.py.
"""

import re
from typing import Callable

from rapidfuzz import fuzz, process

MATCH_THRESHOLD = 75
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_FILLER = re.compile(r"^(ok|okay|well|fine|alright|sure|yes|yeah|yep|hi|hello|hey)\b[\s,.!:-]*", re.IGNORECASE)
NAME_LEAD_IN = re.compile(r"^(my name is|my name's|i am|i'm|im|this is|it's|it is|call me|you can call me)\s+", re.IGNORECASE)
PERSON_NAME = re.compile(r"[^\W\d_](?:[^\W\d_]|[ '\-.]){1,59}")   # letters, spaces, ' - . ; no digits or question marks
NOT_A_NAME = re.compile(r"\b(not willing|unwilling|don'?t want|do not want|dont want|won'?t|wont|rather not|prefer not|"
                        r"no thanks|no name|none of your|not sharing|not telling|refuse|skip|anonymous|no|nope|nah|never|"
                        r"none|nothing|why|which|what|who|how|share|name)\b", re.IGNORECASE)
BUSINESS_FIELDS = {
    "display_name": lambda c: f'{c["display_name"]["first_name"]} {c["display_name"]["last_name"]}',
    "phone": lambda c: c["public_contact"]["phone"],
    "email": lambda c: c["public_contact"]["email"],
    "address": lambda c: c["primary_location"],
    "service_area": lambda c: c["service_area"],
    "opening_hours": lambda c: c["business_hours"],
    "timezone": lambda c: c["timezone"],
    "website": lambda c: c["weblink"],
    "parking": lambda c: c.get("parking"),
    "offers": lambda c: c.get("offers"),
    "response_hours": lambda c: c.get("response_hours"),
    "services": lambda c: c.get("services"),
}


def clean_person_name(text: str | None) -> str | None:
    """The name a visitor gave, or None when it is not a name: a refusal ("I am not willing to share my name"), a question,
    a sentence, or something with digits. "My name is Sam" gives "Sam". A first name or a nickname is enough."""
    cleaned = " ".join(NAME_LEAD_IN.sub("", NAME_FILLER.sub("", (text or "").strip())).split())
    if not cleaned or len(cleaned.split()) > 4 or NOT_A_NAME.search(cleaned) or not PERSON_NAME.fullmatch(cleaned):
        return None
    return cleaned


def _menu_items(customer: dict) -> list[dict]:
    items = []
    for section, dishes in customer["menu"].items():
        for dish in dishes:
            items.append({**dish, "section": section})
    return items


def get_menu(customer: dict) -> dict:
    return {"found": True, "menu": customer["menu"]}


def _dish_score(query: str, name: str, **_) -> float:
    """A dish matches when its name is in the question (partial) or the question is close to its name (whole)."""
    return max(fuzz.WRatio(query, name), fuzz.partial_ratio(name.lower(), query.lower()))


WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def dish_available(availability: dict, now) -> bool:
    """Is the dish on offer at this local time? No days or times set means always. Days are mon..sun; start and end
    are HH:MM in the business's time zone."""
    if not availability:
        return True
    if availability.get("enabled") is False:
        return False
    days = availability.get("days")
    if days and WEEKDAY_KEYS[now.weekday()] not in days:
        return False
    start, end = availability.get("start"), availability.get("end")
    if start and end:
        clock = now.strftime("%H:%M")
        return start <= clock <= end
    return True


def search_menu(customer: dict, query: str, now=None) -> dict:
    """Dishes that match the query. Each match says whether it is on offer at this time (available_now)."""
    query = (query or "").strip()
    if not query:
        return get_menu(customer)
    if now is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(customer.get("timezone") or "UTC"))
    items = _menu_items(customer)
    names = [item["name"] for item in items]
    matches = process.extract(query, names, scorer=_dish_score, score_cutoff=MATCH_THRESHOLD, limit=5)
    if not matches:
        return {"found": False, "menu": customer["menu"], "matches": []}
    found = [{**items[index], "available_now": dish_available(items[index].get("availability") or {}, now)}
             for _, _, index in matches]
    return {"found": True, "matches": found}


def field_value(customer: dict, field: str):
    """A business field as it is on record, or None: a predefined field, or a field the business added (its links, such as
    booking_link and menu_link, are among them)."""
    getter = BUSINESS_FIELDS.get(field)
    value = getter(customer) if getter is not None else (customer.get("custom_fields") or {}).get(field)
    return None if value in (None, "", []) else value


def get_business_info(customer: dict, field: str) -> dict:
    if field not in BUSINESS_FIELDS and field not in (customer.get("custom_fields") or {}):
        return {"found": False, "error": f"field not allowed: {field}"}
    value = field_value(customer, field)
    if value is None:
        return {"found": False, "field": field}
    return {"found": True, "field": field, "value": value}


TOOL_FUNCTIONS: dict[str, Callable] = {
    "get_menu": get_menu,
    "search_menu": search_menu,
    "get_business_info": get_business_info,
}


def available_tools(category: dict) -> list[str]:
    """The tools call_tool may run for this category: the bundle's allowed_tools (a plain list of names, for the lookups), or
    the names in the category's tools when there is no such list."""
    names = category.get("allowed_tools")
    if names is None:
        names = [t["name"] for t in category.get("tools", [])]
    return [n for n in names if n in TOOL_FUNCTIONS]


def call_tool(category: dict, customer: dict, tool_name: str, **args) -> dict:
    """Run one tool, if the category allows it. The business comes from the bundles, not the arguments."""
    if tool_name not in available_tools(category):
        return {"ok": False, "error": f"tool not allowed for this category: {tool_name}"}
    return TOOL_FUNCTIONS[tool_name](customer, **args)
