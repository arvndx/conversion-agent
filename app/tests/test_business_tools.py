"""Tests for the tools the agent may call (A65). They use the sample bundles and no database or model.

Run from the app folder: uv run pytest
"""

import json
import pathlib

import pytest

from tools.business_tools import available_tools, call_tool

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "shared/samples"


@pytest.fixture(scope="module")
def category():
    return json.loads((SAMPLES / "restaurant_category.json").read_text(encoding="utf-8"))


@pytest.fixture()
def customer():
    return json.loads((SAMPLES / "spice_garden_customer.json").read_text(encoding="utf-8"))


def test_the_restaurant_category_allows_the_lookups(category):
    assert available_tools(category) == ["get_menu", "search_menu", "get_business_info"]


def test_a_tool_outside_the_category_is_refused(category, customer):
    result = call_tool(category, customer, "book_flight")
    assert result["ok"] is False


def test_get_menu_returns_the_grouped_menu(category, customer):
    result = call_tool(category, customer, "get_menu")
    assert result["found"] is True
    assert "starter" in result["menu"] and "main course" in result["menu"]


def test_search_menu_finds_a_misspelt_dish(category, customer):
    result = call_tool(category, customer, "search_menu", query="chiken biryani")
    assert result["found"] is True
    assert result["matches"][0]["name"] == "Chicken Biryani"
    assert result["matches"][0]["section"] == "main course"


def test_search_menu_with_no_match_returns_the_full_menu(category, customer):
    result = call_tool(category, customer, "search_menu", query="pizza")
    assert result["found"] is False
    assert result["menu"] == customer["menu"]


def test_search_menu_with_an_empty_query_returns_the_full_menu(category, customer):
    result = call_tool(category, customer, "search_menu", query="  ")
    assert result["menu"] == customer["menu"]


@pytest.mark.parametrize("field, expected", [
    ("phone", "+1 555 0123"),
    ("email", "hello@spicegarden.example"),
    ("address", "12 Market Street, Austin, TX"),
    ("timezone", "America/Chicago"),
    ("website", "https://spicegarden.example"),
    ("display_name", "Spice Garden"),
])
def test_get_business_info_returns_allowed_fields(category, customer, field, expected):
    result = call_tool(category, customer, "get_business_info", field=field)
    assert result == {"found": True, "field": field, "value": expected}


def test_get_business_info_refuses_other_fields(category, customer):
    result = call_tool(category, customer, "get_business_info", field="licences")
    assert result["found"] is False


def test_the_request_form_and_the_old_tools_are_not_lookups(category, customer):
    for name in ("request_handoff", "get_booking_options", "get_conversion_link", "get_services"):
        assert call_tool(category, customer, name)["ok"] is False
