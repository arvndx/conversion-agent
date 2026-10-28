"""The dashboard's menu, chef specials and chat contact switches, on the conv_ tables. Each test puts back what it changed.
Run from the app folder: uv run pytest tests/test_dashboard_menu.py"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from dashboard import store
from dashboard.server import app
from pipeline.load_chat import DATABASE_URL


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def pro():
    with psycopg.connect(DATABASE_URL) as c:
        return str(c.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0])


def test_the_menu_lists_the_dishes_with_their_price_and_chef_flag(client, pro):
    dishes = client.get(f"/api/c/{pro}/menu").json()["dishes"]
    burger = next(d for d in dishes if d["name"] == "Smash Burger")
    assert burger["price"] == 11.5 and burger["chef_special"] is True and burger["enabled"] is True


def test_a_dish_is_added_and_removed_again(client, pro):
    name = f"Test dish {uuid.uuid4().hex[:6]}"
    try:
        added = client.post(f"/api/c/{pro}/menu", json={"name": name, "section": "Mains", "price": 9.0}).json()
        assert added["name"] == name and added["price"] == 9.0
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            menu_id = next((d["menu_id"] for d in store.menu(c, pro) if d["name"] == name), None)
            if menu_id:
                c.execute("delete from conv_professional_menu where professional_id = %s and menu_id = %s", (pro, menu_id))
                c.execute("delete from conv_menu where menu_id = %s", (menu_id,))
            c.commit()


def test_a_dish_can_be_switched_off_and_back_on(client, pro):
    dish = next(d for d in client.get(f"/api/c/{pro}/menu").json()["dishes"] if d["name"] == "Apple Pie")
    try:
        off = client.put(f"/api/c/{pro}/menu/{dish['id']}", json={"enabled": False, "days": [0, 1, 2, 3, 4, 5, 6]}).json()
        assert off["enabled"] is False
    finally:
        client.put(f"/api/c/{pro}/menu/{dish['id']}", json={"enabled": True, "days": [0, 1, 2, 3, 4, 5, 6]})


def test_two_or_three_chef_specials_are_required(client, pro):
    assert client.put(f"/api/c/{pro}/chef-specials", json={"specials": ["Smash Burger"], "menu_url": "https://x.example/m"}).status_code == 422


def test_the_chef_specials_and_the_menu_link_are_saved(client, pro):
    before = client.get(f"/api/c/{pro}/menu").json()
    try:
        saved = client.put(f"/api/c/{pro}/chef-specials", json={"specials": ["Smash Burger", "Apple Pie"],
                                                                "menu_url": "https://demo-diner-1.example/menu"}).json()
        assert saved["specials"] == ["Smash Burger", "Apple Pie"]
        assert {d["name"] for d in client.get(f"/api/c/{pro}/menu").json()["dishes"] if d["chef_special"]} == {"Smash Burger", "Apple Pie"}
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("""update conv_professional_menu pm set chef_special = (m.name in ('Smash Burger','Milkshake'))
                from conv_menu m where m.menu_id = pm.menu_id and pm.professional_id = %s""", (pro,))
            c.commit()
    assert before


def test_the_chat_contact_switches_are_kept(client, pro):
    try:
        on = client.put(f"/api/c/{pro}/chat-contact", json={"phone": True, "email": False}).json()
        assert on == {"phone": True, "email": False}
        assert client.get(f"/api/c/{pro}/chat-contact").json() == {"phone": True, "email": False}
    finally:
        client.put(f"/api/c/{pro}/chat-contact", json={"phone": True, "email": False})
