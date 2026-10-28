"""The dashboard's insights (what visitors asked for) and feedback topics, on the conv_ tables. The model call is turned off,
so the keyword rule makes the suggestion. Each test cleans up what it made. Run: uv run pytest tests/test_dashboard_insights.py"""

import uuid
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient

import dashboard.server as server
from dashboard.server import app
from pipeline.load_chat import DATABASE_URL


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def pro():
    with psycopg.connect(DATABASE_URL) as c:
        return str(c.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0])


@pytest.fixture()
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("model off in tests")
    monkeypatch.setattr(server, "call_model", refuse)


@pytest.fixture()
def question(pro):
    text = f"is there a rooftop bar {uuid.uuid4().hex[:6]}"
    with psycopg.connect(DATABASE_URL) as c:
        c.execute("""insert into conv_question (question_id, professional_id, domain, question_text, topic, asked_count,
            first_asked_at, last_asked_at, answered) values (%s, %s, 'demo-diner-1.example', %s, 'menu', 3, now(), now(), false)""",
                  (uuid.uuid4(), pro, text))
        c.commit()
    yield text
    with psycopg.connect(DATABASE_URL) as c:
        c.execute("delete from conv_question where professional_id = %s and question_text = %s", (pro, text))
        c.commit()


def test_a_question_is_a_card_with_a_suggestion_by_the_rule(client, pro, no_model, question):
    cards = client.get(f"/api/c/{pro}/insights").json()["cards"]
    card = next(c for c in cards if c["text"] == question)
    assert card["count"] == 3 and card["suggested_by"] == "rule"
    assert card["suggested"]["tab"] == "custom" and card["confirmed"] is None
    assert card["suggested_answer"] == ""   # the model is off in this test, so no answer is suggested


def test_the_business_confirms_the_answer_and_it_is_logged(client, pro, no_model, question):
    client.get(f"/api/c/{pro}/insights")
    response = client.put(f"/api/c/{pro}/insights/confirm", json={"text": question, "tab": "defaults", "key": "offers"})
    assert response.status_code == 200 and response.json()["target"] == {"tab": "defaults", "key": "offers"}
    card = next(c for c in client.get(f"/api/c/{pro}/insights").json()["cards"] if c["text"] == question)
    assert card["confirmed"] == {"tab": "defaults", "key": "offers"}
    assert any(c["area"] == "insights" and c["target"] == question for c in client.get(f"/api/c/{pro}/changes").json()["changes"])


def test_a_custom_name_that_is_a_default_field_is_refused(client, pro, no_model, question):
    response = client.put(f"/api/c/{pro}/insights/confirm", json={"text": question, "tab": "custom", "key": "offers"})
    assert response.status_code == 422


def test_feedback_counts_come_from_the_daily_totals(client, pro):
    with psycopg.connect(DATABASE_URL) as c:
        c.execute("""insert into conv_daily (professional_id, domain, day, topic_counts) values (%s, 'demo-diner-1.example', %s,
            '{"happy_hour_details": 2}'::jsonb) on conflict (professional_id, domain, day) do update set topic_counts = excluded.topic_counts""",
                  (pro, date(2000, 1, 2)))
        c.commit()
    try:
        body = client.get(f"/api/c/{pro}/feedback").json()
        assert "View Happy Hour Specials" in body["topics"]
        assert body["reasons"] and len(body["daily"]) == 90
    finally:
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("delete from conv_daily where professional_id = %s and day = %s", (pro, date(2000, 1, 2)))
            c.commit()
