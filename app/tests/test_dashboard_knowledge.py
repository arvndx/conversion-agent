"""The dashboard's knowledge page (predefined fields, web check, choices, sharing, custom fields) and the playground (the
real chat pipeline, with a scripted model). The web page is replaced by a fixed page. Each test puts back what it changed.
Run from the app folder: uv run pytest tests/test_dashboard_knowledge.py"""

import psycopg
import pytest
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient

import dashboard.server as server
from dashboard import store
from dashboard.server import app
from pipeline.load_chat import DATABASE_URL

PAGE = """<html><body><h1>Demo diner</h1><p>Call us on +1 555 0999 or write to hello@demo-diner.example.</p>
<p>Open Mon-Fri 11:00 - 22:00</p></body></html>"""


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def pro():
    with psycopg.connect(DATABASE_URL) as c:
        return str(c.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0])


@pytest.fixture()
def restore(pro):
    """Save the demo settings the tests may change, and put them back afterwards."""
    with psycopg.connect(DATABASE_URL) as c:
        c.execute("delete from conv_web_fact where professional_id = %s", (pro,))
        c.commit()
        saved = c.execute("""select public_phone, public_email, opening_hours, special_fields, display_switches
            from conv_professional_settings where professional_id = %s""", (pro,)).fetchone()
    yield
    with psycopg.connect(DATABASE_URL) as c:
        phone, email, hours, special, switches = saved
        c.execute("""update conv_professional_settings set public_phone = %s, public_email = %s, opening_hours = %s,
            special_fields = %s, display_switches = %s where professional_id = %s""",
                  (phone, email, Jsonb(hours), Jsonb(special), Jsonb(switches), pro))
        c.execute("delete from conv_web_fact where professional_id = %s", (pro,))
        c.commit()


@pytest.fixture()
def fixed_page(monkeypatch):
    monkeypatch.setattr(server, "fetch_page", lambda url: PAGE)


def test_every_predefined_field_has_a_row_and_a_status(client, pro):
    rows = client.get(f"/api/c/{pro}/knowledge").json()["fields"]
    assert [r["key"] for r in rows] == server.KNOWLEDGE_ORDER
    assert all(r["status"] in ("database", "chosen", "conflict", "web_only", "missing") for r in rows)


def test_a_web_check_finds_the_facts_and_a_different_phone_is_a_conflict(client, pro, restore, fixed_page):
    response = client.post(f"/api/c/{pro}/scrape", json={"url": "https://demo-diner-1.example/"}).json()
    assert response["found"] >= 2
    rows = {r["key"]: r for r in client.get(f"/api/c/{pro}/knowledge").json()["fields"]}
    assert rows["phone"]["status"] == "conflict" and rows["phone"]["scraped"] == "+1 555 0999"


def test_choosing_the_web_value_resolves_the_conflict_and_the_chat_uses_it(client, pro, restore, fixed_page):
    client.post(f"/api/c/{pro}/scrape", json={"url": "https://demo-diner-1.example/"})
    row = client.put(f"/api/c/{pro}/knowledge/phone/choice", json={"source": "scraped"}).json()
    assert row["status"] == "chosen" and row["value"] == "+1 555 0999"
    with psycopg.connect(DATABASE_URL) as c:
        assert c.execute("select public_phone from conv_professional_settings where professional_id = %s", (pro,)).fetchone()[0] == "+1 555 0999"


def test_a_phone_typed_by_hand_must_have_seven_digits(client, pro, restore):
    assert client.put(f"/api/c/{pro}/knowledge/phone/choice", json={"source": "manual", "manual": "12"}).status_code == 422


def test_a_field_can_be_kept_back_from_the_chat(client, pro, restore):
    client.put(f"/api/c/{pro}/knowledge/offers", json={"enabled": False})
    row = next(r for r in client.get(f"/api/c/{pro}/knowledge").json()["fields"] if r["key"] == "offers")
    assert row["enabled"] is False
    client.put(f"/api/c/{pro}/knowledge/offers", json={"enabled": True})


def test_a_custom_field_is_saved_and_listed(client, pro, restore):
    client.put(f"/api/c/{pro}/custom-fields", json={"key": "Dress code", "value": "Smart casual"})
    fields = client.get(f"/api/c/{pro}/custom-fields").json()["fields"]
    assert {"key": "Dress code", "value": "Smart casual"} in fields


def test_a_predefined_name_is_not_a_custom_field(client, pro, restore):
    assert client.put(f"/api/c/{pro}/custom-fields", json={"key": "Phone", "value": "x"}).status_code == 422


def test_the_playground_runs_the_real_pipeline(client, pro, monkeypatch):
    from tests.model_stub import install, response, text_block
    install(monkeypatch, [response(text_block("The Smash Burger is 11.50."))])
    answer = client.post(f"/api/c/{pro}/playground", json={"message": "how much is the smash burger"}).json()
    assert answer["state"] == "reply" and "Smash Burger" in answer["answer"]


def test_the_playground_setup_has_the_teaser_and_the_questions(client, pro):
    body = client.get(f"/api/c/{pro}/playground").json()
    assert body["widget"]["teaser"] and body["widget"]["default_questions"]
