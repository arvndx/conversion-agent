"""What a visitor types into the request form is checked in code (shared/field_rules.py): digits only in a phone number, a
proper email, a real name, a date that has not passed, required fields and either groups. No model is involved.
Run from the app folder: uv run pytest tests/test_field_rules.py"""

from datetime import date

import pytest

from shared.field_rules import MESSAGES, check_field, clean_phone, validate_values

TODAY = date(2026, 10, 28)
NAME = {"key": "name", "format": "name", "required": True, "max": 60}
PHONE = {"key": "phone", "format": "phone", "required": False}
EMAIL = {"key": "email", "format": "email", "required": False}
QUESTION = {"key": "question", "format": "text", "required": True, "max": 500, "min_length": 3}


@pytest.mark.parametrize("typed, expected", [
    ("5125550199", "5125550199"),
    ("+1 (512) 555-0199", "+15125550199"),
    ("512.555.0199", "5125550199"),
    ("  0044 20 7946 0958 ", "00442079460958"),
])
def test_a_phone_number_keeps_its_digits(typed, expected):
    assert clean_phone(typed) == expected


@pytest.mark.parametrize("typed", ["call me", "512-555-CALL", "12345", "1234567890123456", "++15125550199", "5125550199x2"])
def test_a_phone_number_with_letters_or_the_wrong_length_is_refused(typed):
    assert clean_phone(typed) is None
    assert check_field(PHONE, typed, TODAY) == (None, MESSAGES["phone"])


@pytest.mark.parametrize("typed", ["Jane@Example.com", "  jane@example.com "])
def test_an_email_is_lower_cased_and_trimmed(typed):
    assert check_field(EMAIL, typed, TODAY) == ("jane@example.com", None)


@pytest.mark.parametrize("typed", ["jane", "jane@", "@example.com", "jane@example", "jane @example.com"])
def test_a_bad_email_is_refused(typed):
    assert check_field(EMAIL, typed, TODAY) == (None, MESSAGES["email"])


@pytest.mark.parametrize("typed", ["I do not want to share my name", "no", "Jane123", "What name?", "a b c d e"])
def test_a_refusal_a_question_or_digits_are_not_a_name(typed):
    assert check_field(NAME, typed, TODAY) == (None, MESSAGES["name"])


def test_a_name_with_a_lead_in_gives_the_name():
    assert check_field(NAME, "my name is Priya Shah", TODAY) == ("Priya Shah", None)


@pytest.mark.parametrize("typed, error", [
    ("2026-10-28", None), ("2027-10-28", None), ("2026-10-27", "date_past"), ("2028-01-01", "date_far"),
    ("28/10/2026", "date"), ("tomorrow", "date"), ("2026-02-30", "date"),
])
def test_a_date_must_be_a_real_date_that_has_not_passed(typed, error):
    value, message = check_field({"key": "date", "format": "date"}, typed, TODAY)
    assert (message is None) == (error is None)
    if error:
        assert message == MESSAGES[error]
    else:
        assert value == typed


@pytest.mark.parametrize("typed, ok", [("09:30", True), ("23:59", True), ("24:00", False), ("9:30", False), ("noon", False)])
def test_a_time_is_hours_and_minutes(typed, ok):
    assert (check_field({"key": "time", "format": "time"}, typed, TODAY)[1] is None) is ok


def test_a_whole_number_in_a_range_for_a_field_of_the_category():
    spec = {"key": "party_size", "type": "integer", "min": 1, "max": 20}
    assert check_field(spec, "4", TODAY) == (4, None)
    assert check_field(spec, "0", TODAY)[1] == MESSAGES["range"].format(min=1, max=20)
    assert check_field(spec, "21", TODAY)[1] == MESSAGES["range"].format(min=1, max=20)
    assert check_field(spec, "four", TODAY)[1] == MESSAGES["integer"]
    assert check_field(spec, "2.5", TODAY)[1] == MESSAGES["integer"]


def test_text_is_tidied_and_limited():
    assert check_field(QUESTION, "  I   want\x00 a table  ", TODAY) == ("I want a table", None)
    assert check_field(QUESTION, "hi", TODAY) == (None, MESSAGES["too_short"].format(n=3))
    assert check_field(QUESTION, "x" * 501, TODAY) == (None, MESSAGES["too_long"].format(n=500))


def test_an_empty_value_is_not_an_error_for_the_field_itself():
    assert check_field(NAME, "", TODAY) == (None, None) and check_field(NAME, None, TODAY) == (None, None)
    assert check_field(NAME, "   ", TODAY) == (None, None)


FIELDS = [NAME, PHONE, EMAIL, QUESTION]
EITHER = [["phone", "email"]]


def test_a_good_submission_has_no_errors_and_keeps_only_clean_values():
    clean, errors = validate_values(FIELDS, EITHER, {"name": "Priya", "email": "P@x.com", "question": "A table for four",
                                                     "ignored": "not a field of the form"}, TODAY)
    assert errors == {} and clean == {"name": "Priya", "email": "p@x.com", "question": "A table for four"}


def test_a_required_field_left_empty_is_an_error():
    _, errors = validate_values(FIELDS, EITHER, {"name": "", "phone": "5125550199", "question": ""}, TODAY)
    assert errors == {"name": MESSAGES["required"], "question": MESSAGES["required"]}


def test_either_phone_or_email_is_needed_and_both_are_marked_when_neither_is_given():
    _, errors = validate_values(FIELDS, EITHER, {"name": "Priya", "question": "A table"}, TODAY)
    assert set(errors) == {"phone", "email"} and "phone or email" in errors["phone"]


def test_either_is_met_by_one_and_a_wrong_one_is_reported_on_its_own():
    clean, errors = validate_values(FIELDS, EITHER, {"name": "Priya", "question": "A table", "phone": "5125550199",
                                                     "email": "nope"}, TODAY)
    assert errors == {"email": MESSAGES["email"]} and clean["phone"] == "5125550199"
    _, errors = validate_values(FIELDS, EITHER, {"name": "Priya", "question": "A table", "phone": "abc"}, TODAY)
    assert set(errors) == {"phone"}   # the wrong phone is reported once; the group is not reported again


def test_an_optional_field_is_checked_only_when_it_is_filled_in():
    optional = {"key": "note", "format": "text", "required": False, "max": 10}
    assert validate_values([NAME, optional], [], {"name": "Priya"}, TODAY) == ({"name": "Priya"}, {})
    assert validate_values([NAME, optional], [], {"name": "Priya", "note": "x" * 11}, TODAY)[1] == {"note": MESSAGES["too_long"].format(n=10)}
