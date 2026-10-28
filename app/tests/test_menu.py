"""Tests for the menu in the bundle and the dish search tool. Read-only on the demo data.
Run from the app folder: uv run pytest tests/test_menu.py"""

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL
from shared.bundle_tables import load_category, load_customer
from tools.business_tools import search_menu


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        yield c


@pytest.fixture(scope="module")
def diner(conn):
    pid = conn.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0]
    return load_customer(conn, str(pid)), load_category(conn, "gcid:american_restaurant")


def test_the_bundle_has_the_menu_by_section_with_prices(diner):
    customer, _ = diner
    assert set(customer["menu"]) >= {"Mains", "Starters", "Desserts"}
    dish = customer["menu"]["Mains"][0]
    assert {"name", "price", "chef_special", "availability"} <= set(dish)


def test_the_chef_specials_and_the_menu_link_are_in_the_bundle(diner):
    customer, _ = diner
    assert set(customer["chef"]["specials"]) == {"Smash Burger", "Milkshake"}
    assert customer["chef"]["menu_url"] == "https://demo-diner-1.example/menu"


def test_a_dish_named_inside_the_question_is_found(diner):
    customer, _ = diner
    result = search_menu(customer, "how much is the smash burger")
    assert result["found"] and result["matches"][0]["name"] == "Smash Burger"
    assert result["matches"][0]["price"] == 11.5 and result["matches"][0]["chef_special"] is True


def test_a_dish_that_is_not_on_the_menu_is_not_found(diner):
    customer, _ = diner
    assert search_menu(customer, "do you sell sushi")["found"] is False


def test_a_dish_outside_its_hours_is_marked_not_on_offer(diner):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    customer, _ = diner
    late = datetime(2026, 10, 28, 21, 0, tzinfo=ZoneInfo("America/Chicago"))   # a Wednesday, 21:00
    result = search_menu(customer, "onion rings", now=late)
    assert result["matches"][0]["name"] == "Onion Rings" and result["matches"][0]["available_now"] is False


def test_a_dish_inside_its_hours_is_on_offer(diner):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    customer, _ = diner
    noon = datetime(2026, 10, 28, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert search_menu(customer, "onion rings", now=noon)["matches"][0]["available_now"] is True
