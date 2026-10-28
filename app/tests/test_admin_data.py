"""The knowledge batch (one Save for the knowledge section) and the change log on the conv_ tables. Each test puts back what
it changed. Run from the app folder: uv run pytest tests/test_admin_data.py"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from dashboard.server import app
from pipeline.load_chat import DATABASE_URL


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def pro():
    with psycopg.connect(DATABASE_URL) as c:
        return str(c.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0])


def test_a_batch_saves_a_custom_field_and_logs_it_under_one_batch(client, pro):
    key = f"Test field {uuid.uuid4().hex[:6]}"
    try:
        body = client.put(f"/api/c/{pro}/knowledge-batch", json={"custom_fields": [{"key": key, "value": "value 1"}]}).json()
        assert body["saved"] is True and body["changes"] >= 1
        changes = client.get(f"/api/c/{pro}/changes").json()["changes"]
        assert any(c["target"] == key and c["batch"] == body["batch"] for c in changes)
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("update conv_professional_settings set special_fields = special_fields - %s where professional_id = %s", (key, pro))
            c.commit()


def test_a_refused_batch_keeps_nothing(client, pro):
    key = f"Refused {uuid.uuid4().hex[:6]}"
    response = client.put(f"/api/c/{pro}/knowledge-batch", json={"custom_fields": [{"key": key, "value": "x"},
                                                                                  {"key": "Phone", "value": "x"}]})
    assert response.status_code == 422
    with psycopg.connect(DATABASE_URL) as c:
        found = c.execute("select special_fields ? %s from conv_professional_settings where professional_id = %s", (key, pro)).fetchone()[0]
    assert found is False


def test_a_dish_added_in_a_batch_is_on_the_menu(client, pro):
    name = f"Batch dish {uuid.uuid4().hex[:6]}"
    try:
        client.put(f"/api/c/{pro}/knowledge-batch", json={"new_dishes": [{"name": name, "section": "Mains", "price": 7.5}]})
        assert any(d["name"] == name for d in client.get(f"/api/c/{pro}/menu").json()["dishes"])
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            menu_id = c.execute("select menu_id from conv_menu where name = %s", (name,)).fetchone()
            if menu_id:
                c.execute("delete from conv_professional_menu where professional_id = %s and menu_id = %s", (pro, menu_id[0]))
                c.execute("delete from conv_menu where menu_id = %s", (menu_id[0],))
            c.commit()


def test_the_change_log_is_newest_first(client, pro):
    changes = client.get(f"/api/c/{pro}/changes").json()["changes"]
    times = [c["at"] for c in changes]
    assert times == sorted(times, reverse=True)
