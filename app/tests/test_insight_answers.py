"""Answers to the questions the chat could not answer. The AI suggests an answer from the business's own facts; the
business confirms it; it is saved in the predefined field's column, or as a custom field; the question stays, marked
answered, for 30 days; the customer bundle is published as a new version. Each test restores what it changed.
Run from the app folder: uv run pytest tests/test_insight_answers.py"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from dashboard import server, store
from dashboard.server import app as dashboard_app
from pipeline import cleanup, site_bundles
from pipeline.load_chat import DATABASE_URL, redis_client
from shared.bundle_tables import load_customer
from tools.business_tools import get_business_info

DINER = "483dc8e7-3f03-5fbb-878b-77ee433ed0b3"
DOMAIN = "demo-diner-1.example"


@pytest.fixture()
def diner_settings():
    """The diner's contact, services and custom fields as they were, put back after the test."""
    with psycopg.connect(DATABASE_URL) as conn:
        before = conn.execute("""select public_phone, services, special_fields from conv_professional_settings
            where professional_id = %s""", (DINER,)).fetchone()
    yield
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""update conv_professional_settings set public_phone = %s, services = %s, special_fields = %s
            where professional_id = %s""", (before[0], before[1], json.dumps(before[2] or {}), DINER))
        conn.execute("delete from conv_question where question_text like 'answer test%'")
        conn.commit()


@pytest.fixture()
def question():
    text = f"answer test {uuid.uuid4().hex[:8]} kids pizza"
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("""insert into conv_question (question_id, professional_id, domain, question_text, asked_count,
            first_asked_at, last_asked_at, answered, status) values (gen_random_uuid(), %s, %s, %s, 2, now(), now(), false, 'open')""",
                     (DINER, DOMAIN, text))
        conn.commit()
    return text


def test_a_predefined_field_takes_the_answer_in_its_column_and_the_bundle(diner_settings, question):
    with psycopg.connect(DATABASE_URL) as conn:
        where = store.save_insight_answer(conn, DINER, question, "+1 555 0199", "phone", "Demo Owner")
        conn.commit()
        bundle = load_customer(conn, DINER)
    assert where == {"key": "phone", "label": "Phone", "custom": False}
    assert bundle["public_contact"]["phone"] == "+1 555 0199"


def test_a_list_field_takes_the_answer_as_one_more_item(diner_settings, question):
    with psycopg.connect(DATABASE_URL) as conn:
        before = conn.execute("select services from conv_professional_settings where professional_id = %s", (DINER,)).fetchone()[0] or []
        store.save_insight_answer(conn, DINER, question, "Private dining for groups", "services", "Demo Owner")
        conn.commit()
        services = conn.execute("select services from conv_professional_settings where professional_id = %s", (DINER,)).fetchone()[0]
    assert services == list(before) + ["Private dining for groups"]


def test_any_other_name_is_saved_as_a_custom_field_the_chat_can_read(diner_settings, question):
    with psycopg.connect(DATABASE_URL) as conn:
        where = store.save_insight_answer(conn, DINER, question, "Yes, a kids pizza is on request.", "kids pizza", "Demo Owner")
        conn.commit()
        customer = load_customer(conn, DINER)
    assert where["custom"] is True
    assert customer["custom_fields"]["kids pizza"] == "Yes, a kids pizza is on request."
    assert get_business_info(customer, "kids pizza") == {"found": True, "field": "kids pizza",
                                                         "value": "Yes, a kids pizza is on request."}


def test_the_answered_question_stays_marked_and_leaves_the_list(diner_settings, question):
    with psycopg.connect(DATABASE_URL) as conn:
        assert any(card["question"] == question for card in store.insights(conn, DINER))
        store.save_insight_answer(conn, DINER, question, "+1 555 0199", "phone", "Demo Owner")
        conn.commit()
        row = conn.execute("""select answered, answer_text, answer_key, answered_at, status from conv_question
            where professional_id = %s and question_text = %s""", (DINER, question)).fetchone()
        assert not any(card["question"] == question for card in store.insights(conn, DINER))
    assert row[0] is True and row[1] == "+1 555 0199" and row[2] == "phone" and row[3] is not None and row[4] == "added"


def test_the_ai_suggestion_uses_the_business_facts_and_falls_back_safely(monkeypatch):
    monkeypatch.setattr(server, "call_model", lambda *a, **k: json.dumps({"answer": "Yes, kids pizza on request.",
                                                                           "key": "kids pizza"}))
    got = server._suggest_answer("do you have a kids pizza?", {"menu_dishes": []}, {})
    assert got == {"answer": "Yes, kids pizza on request.", "key": "kids pizza", "by": "llm"}

    def broken(*a, **k):
        raise RuntimeError("model down")
    monkeypatch.setattr(server, "call_model", broken)
    fallback = server._suggest_answer("do you have a kids pizza?", {}, {})
    assert fallback["answer"] == "" and fallback["by"] == "rule"


def test_the_endpoint_saves_publishes_a_new_version_and_refuses_bad_input(diner_settings, question):
    api = TestClient(dashboard_app)
    client = redis_client()
    with psycopg.connect(DATABASE_URL) as conn:
        before, _ = site_bundles.ensure_bundles(conn, client, DINER)
    response = api.put(f"/api/c/{DINER}/insights/answer", json={"text": question, "answer": "Yes, kids pizza on request.",
                                                               "key": "kids pizza"})
    assert response.status_code == 200, response.text
    assert response.json()["custom"] is True
    assert int(client.get(site_bundles.current_customer_key(DINER))) > before
    assert api.put(f"/api/c/{DINER}/insights/answer", json={"text": question, "answer": " ", "key": "phone"}).status_code == 422
    assert api.put(f"/api/c/{DINER}/insights/answer", json={"text": question, "answer": "Yes.", "key": "x"}).status_code == 422


def test_an_answered_question_is_kept_for_30_days_then_removed(question):
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("update conv_question set updated_at = now() - interval '10 days' where question_text = %s", (question,))
        cleanup.run_cleanup(conn)
        assert conn.execute("select 1 from conv_question where question_text = %s", (question,)).fetchone() is not None
        conn.execute("update conv_question set updated_at = now() - interval '31 days' where question_text = %s", (question,))
        cleanup.run_cleanup(conn)
        assert conn.execute("select 1 from conv_question where question_text = %s", (question,)).fetchone() is None
        conn.commit()
