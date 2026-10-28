"""Tests for the chat's storage in the conv_ tables. Each test runs in one transaction that is rolled back,
so the local demo data is not changed. Run from the app folder: uv run pytest tests/test_store.py"""

import uuid
from datetime import date, datetime, timezone

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL
from pipeline import store


@pytest.fixture()
def cur():
    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as c:
            yield c
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture()
def site(cur):
    return cur.execute("select professional_id, domain from conv_domains where status = 'active' order by domain limit 1").fetchone()


def chat(professional_id, domain, consent=False, visitor_id=None):
    now = datetime.now(timezone.utc)
    return {
        "session_id": str(uuid.uuid4()), "activity_id": str(uuid.uuid4()), "professional_id": str(professional_id),
        "domain": domain, "visitor_id": visitor_id, "have_consent": consent, "started_at": now, "last_activity_at": now,
        "status": "handed_over", "messages": [{"request": "What rate for a 30-year loan?", "response": "I can't quote rates.",
                                              "event_time": now.isoformat()}],
        "topic": "rate_quote", "widget_seconds": 120, "session_score": 45, "abuse_strikes": 0,
        "summary": "Asked for a 30-year rate, handed over", "city": "Chicago", "state": "IL", "notice_version": "v1",
    }


def test_anonymous_visit_is_its_own_visitor(cur, site):
    professional_id, domain = site
    s = chat(professional_id, domain)
    store.upsert_visitor(cur, s, new_visit=True)
    assert store.upsert_activity(cur, s) is True
    store.upsert_session(cur, s)
    store.refresh_visitor(cur, s)
    row = cur.execute("select have_consent, visits, widget_seconds_total, visit_summaries from conv_visitor where visitor_id = %s",
                      (s["activity_id"],)).fetchone()
    assert row[0] is False and row[1] == 1 and row[2] == 120
    assert row[3][0]["activity_id"] == s["activity_id"]


def test_consented_visitor_adds_up_across_visits(cur, site):
    professional_id, domain = site
    vid = str(uuid.uuid4())
    first, second = chat(professional_id, domain, True, vid), chat(professional_id, domain, True, vid)
    store.upsert_visitor(cur, first, new_visit=True)
    store.upsert_activity(cur, first)
    store.upsert_visitor(cur, second, new_visit=True)
    store.upsert_activity(cur, second)
    store.refresh_visitor(cur, second)
    row = cur.execute("select visits, widget_seconds_total, score_72h, jsonb_array_length(visit_summaries) from conv_visitor "
                      "where visitor_id = %s", (vid,)).fetchone()
    assert row == (2, 240, 90, 2)


def test_handover_is_saved_once_for_the_chat(cur, site):
    professional_id, domain = site
    s = chat(professional_id, domain)
    store.upsert_visitor(cur, s, new_visit=True)
    store.upsert_activity(cur, s)
    store.upsert_session(cur, s)
    details = {"name": "Jane Demo", "email": "jane.demo@example.com", "reason": "critical_question",
               "action_key": None, "question": "What rate for a 30-year loan?", "summary": "rate question"}
    first = store.insert_handover(cur, s, details)
    second = store.insert_handover(cur, s, details)
    assert first is not None and second is None
    assert cur.execute("select count(*) from conv_handover where session_id = %s", (s["session_id"],)).fetchone()[0] == 1


def test_unanswered_question_is_counted_per_domain(cur, site):
    professional_id, domain = site
    s = chat(professional_id, domain)
    store.record_question(cur, s, "Is there free parking?", "parking", answered=False)
    store.record_question(cur, s, "is there  free parking?", "parking", answered=False)
    assert cur.execute("select asked_count from conv_question where professional_id = %s and domain = %s and question_text = %s",
                       (professional_id, domain, "is there free parking?")).fetchone()[0] == 2


def test_daily_totals_and_topic_counts(cur, site):
    professional_id, domain = site
    day = date(2000, 1, 1)  # a day with no demo rows
    store.bump_daily(cur, {"professional_id": str(professional_id), "domain": domain}, day, new_chat=True, topic="rate_quote")
    store.bump_daily(cur, {"professional_id": str(professional_id), "domain": domain}, day, new_chat=True, topic="rate_quote")
    chats, topics = cur.execute("select chats, topic_counts from conv_daily where professional_id = %s and domain = %s and day = %s",
                                (professional_id, domain, day)).fetchone()
    assert chats == 2 and topics["rate_quote"] == 2


def test_idle_visit_is_closed_and_its_open_chat_completed(cur, site):
    professional_id, domain = site
    s = chat(professional_id, domain)
    s["status"] = "open"
    store.upsert_visitor(cur, s, new_visit=True)
    store.upsert_activity(cur, s)
    later = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)
    closed = store.close_idle_visits(cur, later)
    assert s["activity_id"] in closed
    assert cur.execute("select status, ended_at is not null from conv_activity where activity_id = %s",
                       (s["activity_id"],)).fetchone() == ("completed", True)
