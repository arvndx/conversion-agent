"""Checks on what a visitor types into a request form. Pure functions: no database, no model.

A field of a form is a dict {"key", "format", "required", "max"?, "min"?, "min_length"?, "type"?}. Its format says how it is
checked: name, phone (digits only, with an optional leading + and spaces or dashes), email, text, date, time. A field of the
category that is not a standard one has a type instead (integer, number, boolean). The same rules are sent to the widget with
the form (shared/field_rules.FORMS in pipeline/forms.py) and run again here when the form is submitted.

The messages are short interface text, the same for every business.
"""

import re
from datetime import date, timedelta

from tools.business_tools import EMAIL_PATTERN, clean_person_name

MAX_AHEAD_DAYS = 366     # a date further away than this is a typing mistake
TEXT_MAX = 300           # the longest text a field takes when it does not say
PHONE_DIGITS = (7, 15)
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CLOCK = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")

MESSAGES = {
    "required": "This field is required.",
    "name": "Please enter a name, using letters only.",
    "phone": "Please enter a phone number using digits only (7 to 15 digits).",
    "email": "Please enter a valid email address, like name@example.com.",
    "date": "Please choose a date.",
    "date_past": "Please choose a date that has not passed.",
    "date_far": "Please choose a date within the next year.",
    "time": "Please choose a time.",
    "integer": "Please enter a whole number.",
    "number": "Please enter a number.",
    "range": "Please enter a value between {min} and {max}.",
    "too_short": "Please write at least {n} characters.",
    "too_long": "Please keep this to {n} characters or fewer.",
    "either": "Please give at least one of: {keys}.",
}


def clean_phone(value) -> str | None:
    """A phone number as digits (with a leading + if the visitor typed one), or None when it holds anything else. Spaces,
    dashes, dots and brackets are separators and are dropped."""
    text = str(value or "").strip()
    plus = text.startswith("+")
    digits = re.sub(r"[\s().\-]", "", text[1:] if plus else text)
    if not digits.isdigit() or not PHONE_DIGITS[0] <= len(digits) <= PHONE_DIGITS[1]:
        return None
    return ("+" if plus else "") + digits


def _text(value, spec: dict) -> tuple[str | None, str | None]:
    text = " ".join(CONTROL.sub(" ", str(value)).split())
    limit = int(spec.get("max") or TEXT_MAX)
    if len(text) < int(spec.get("min_length") or 1):
        return None, MESSAGES["too_short"].format(n=spec["min_length"])
    if len(text) > limit:
        return None, MESSAGES["too_long"].format(n=limit)
    return text, None


def _number(value, spec: dict) -> tuple[object | None, str | None]:
    kind = spec.get("type")
    text = str(value).strip()
    try:
        number = int(text) if kind == "integer" else float(text)
    except ValueError:
        return None, MESSAGES["integer" if kind == "integer" else "number"]
    low, high = spec.get("min"), spec.get("max")
    if (low is not None and number < low) or (high is not None and number > high):
        return None, MESSAGES["range"].format(min=low if low is not None else "-", max=high if high is not None else "-")
    return number, None


def check_field(spec: dict, raw, today: date) -> tuple[object | None, str | None]:
    """The clean value of one field and no error, or no value and the error text. An empty value is (None, None): the caller
    knows whether the field was required."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, None
    kind = spec.get("type")
    if kind in ("integer", "number"):
        return _number(raw, spec)
    if kind == "boolean":
        return (raw if isinstance(raw, bool) else str(raw).strip().lower() in ("true", "yes", "on", "1")), None
    form = spec.get("format") or "text"
    if form == "name":
        name = clean_person_name(str(raw))
        return (name, None) if name else (None, MESSAGES["name"])
    if form == "phone":
        phone = clean_phone(raw)
        return (phone, None) if phone else (None, MESSAGES["phone"])
    if form == "email":
        email = str(raw).strip().lower()
        return (email, None) if len(email) <= int(spec.get("max") or 120) and EMAIL_PATTERN.match(email) else (None, MESSAGES["email"])
    if form == "date":
        try:
            day = date.fromisoformat(str(raw).strip())
        except ValueError:
            return None, MESSAGES["date"]
        if day < today:
            return None, MESSAGES["date_past"]
        if day > today + timedelta(days=MAX_AHEAD_DAYS):
            return None, MESSAGES["date_far"]
        return day.isoformat(), None
    if form == "time":
        found = CLOCK.fullmatch(str(raw).strip())
        return (found.group(0), None) if found else (None, MESSAGES["time"])
    return _text(raw, spec)


def validate_values(fields: list[dict], groups: list[list[str]], values: dict, today: date) -> tuple[dict, dict]:
    """Check what the visitor gave against the form. fields are the flat field dicts; groups are the either lists (at least one
    of each is needed). Returns (clean values, errors by field key). Keys the form does not have are ignored."""
    clean: dict = {}
    errors: dict = {}
    for spec in fields:
        key = spec["key"]
        value, error = check_field(spec, (values or {}).get(key), today)
        if error:
            errors[key] = error
        elif value is None:
            if spec.get("required"):
                errors[key] = MESSAGES["required"]
        else:
            clean[key] = value
    for group in groups:
        if not any(k in clean for k in group) and not any(k in errors for k in group):
            for key in group:
                errors[key] = MESSAGES["either"].format(keys=" or ".join(k for k in group))
    return clean, errors
