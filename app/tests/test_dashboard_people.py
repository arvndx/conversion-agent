"""The dashboard's people, replies and changes routes on the conv_ tables, through the dashboard API.
Run from the app folder: uv run pytest tests/test_dashboard_people.py"""

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


def test_the_customer_header_comes_from_the_tables(client, pro):
    body = client.get(f"/api/c/{pro}/people").json()
    assert "threshold" in body and body["threshold"] == 60
    assert isinstance(body["leads"], list) and isinstance(body["hot"], list)


def test_a_lead_has_its_contact_query_reason_and_chat(client):
    with psycopg.connect(DATABASE_URL) as c:
        pid = c.execute("select professional_id from conv_handover order by created_at desc limit 1").fetchone()[0]
    body = client.get(f"/api/c/{pid}/people").json()
    if not body["leads"]:
        pytest.skip("no leads in the period")
    lead = body["leads"][0]
    assert {"id", "name", "question", "reason", "status", "when", "domain", "conversation"} <= set(lead)


def test_a_lead_status_is_changed_and_logged(client):
    with psycopg.connect(DATABASE_URL) as c:
        row = c.execute("select professional_id, handover_id, status from conv_handover order by created_at desc limit 1").fetchone()
    if row is None:
        pytest.skip("no handover in the demo data")
    pid, hid, before = str(row[0]), str(row[1]), row[2]
    try:
        response = client.put(f"/api/c/{pid}/leads/{hid}/status", json={"status": "contacted"})
        assert response.status_code == 200 and response.json()["status"] == "contacted"
        changes = client.get(f"/api/c/{pid}/changes").json()["changes"]
        assert any(c["area"] == "leads" and c["target"] == hid for c in changes)
    finally:
        client.put(f"/api/c/{pid}/leads/{hid}/status", json={"status": before})


def test_a_bad_lead_status_is_refused(client, pro):
    assert client.put(f"/api/c/{pro}/leads/00000000-0000-0000-0000-000000000000/status", json={"status": "contacted"}).status_code == 404


def test_replies_come_from_the_feedback_table(client, pro):
    body = client.get(f"/api/c/{pro}/replies").json()
    assert isinstance(body["replies"], list)


def test_an_unknown_customer_is_not_found(client):
    assert client.get("/api/c/00000000-0000-0000-0000-000000000000/people").status_code == 404


def test_a_lead_carries_its_request_type_its_action_and_its_extra_fields(client, pro):
    handover_id = None
    with psycopg.connect(DATABASE_URL) as c:
        handover_id = c.execute(
            """insert into conv_handover (handover_id, professional_id, domain, name, phone, reason, action_key, request_type, question, extra_fields)
               values (gen_random_uuid(), %s, 'demo-diner-1.example', 'Dash Test', '5125550199', 'request_from_visitor', 'book_reservation',
                       'table booking', 'A table for four', '{"party_size": 4, "preferred_time": "anytime"}') returning handover_id""",
            (pro,)).fetchone()[0]
        c.commit()
    try:
        leads = client.get(f"/api/c/{pro}/people").json()["leads"]
        lead = next(l for l in leads if l["id"] == str(handover_id))
        assert lead["request_type"] == "table booking" and lead["action"] == "Reserve a Table"
        assert lead["extra"] == {"party_size": 4, "preferred_time": "anytime"} and lead["reason"] == "Asked for it"
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("delete from conv_handover where handover_id = %s", (handover_id,))
            c.commit()


def test_a_lead_from_a_general_action_names_the_action(client, pro):
    with psycopg.connect(DATABASE_URL) as c:
        handover_id = c.execute(
            """insert into conv_handover (handover_id, professional_id, domain, name, email, reason, action_key, request_type, question)
               values (gen_random_uuid(), %s, 'demo-diner-1.example', 'Dash Test', 'd@x.com', 'system_fallback', 'ai_down_handover',
                       'ai down handover', 'anything') returning handover_id""", (pro,)).fetchone()[0]
        c.commit()
    try:
        lead = next(l for l in client.get(f"/api/c/{pro}/people").json()["leads"] if l["id"] == str(handover_id))
        assert lead["request_type"] == "ai down handover" and lead["action"] == "Chat assistant unavailable"
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("delete from conv_handover where handover_id = %s", (handover_id,))
            c.commit()
