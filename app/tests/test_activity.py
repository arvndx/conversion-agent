"""Visit activity from the widget (pipeline/activity.py, conv_activity). Each test is one transaction, rolled back.
Run from the app folder: uv run pytest tests/test_activity.py"""

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from pipeline.activity import record_activity
from pipeline.load_chat import DATABASE_URL


@pytest.fixture()
def conn():
    c = psycopg.connect(DATABASE_URL)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture()
def pro(conn):
    return conn.execute("select professional_id, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()


def test_a_new_visit_is_recorded_with_its_clicks_and_time(conn, pro):
    pid, domain = pro
    visit = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    events = [{"type": "click"}, {"type": "click"}, {"type": "widget_open"},
              {"type": "heartbeat", "visible_seconds": 90, "widget_seconds": 30}]
    assert record_activity(conn, str(pid), domain, visit, events, now=now) == "ok"
    row = conn.execute("select clicks, widget_opens, time_on_site_seconds, time_in_widget_seconds, status from conv_activity "
                       "where activity_id = %s", (visit,)).fetchone()
    assert row == (2, 1, 90, 30, "open")


def test_a_visit_for_another_domain_is_refused(conn, pro):
    pid, domain = pro
    visit = str(uuid.uuid4())
    record_activity(conn, str(pid), domain, visit, [], now=datetime.now(timezone.utc))
    assert record_activity(conn, str(pid), "demo-diner-2.example", visit, [], now=datetime.now(timezone.utc)) == "refused"


def test_a_visit_idle_for_thirty_minutes_has_ended(conn, pro):
    pid, domain = pro
    visit = str(uuid.uuid4())
    start = datetime.now(timezone.utc)
    record_activity(conn, str(pid), domain, visit, [], now=start)
    later = start + timedelta(minutes=31)
    assert record_activity(conn, str(pid), domain, visit, [{"type": "click"}], now=later) == "ended"


def test_the_largest_time_seen_is_kept(conn, pro):
    pid, domain = pro
    visit = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    record_activity(conn, str(pid), domain, visit, [{"type": "heartbeat", "visible_seconds": 100, "widget_seconds": 40}], now=now)
    record_activity(conn, str(pid), domain, visit, [{"type": "heartbeat", "visible_seconds": 60, "widget_seconds": 10}], now=now)
    row = conn.execute("select time_on_site_seconds, time_in_widget_seconds from conv_activity where activity_id = %s", (visit,)).fetchone()
    assert row == (100, 40)
