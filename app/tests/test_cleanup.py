"""Retention on the conv_ tables: rows are deleted once their window has passed, counted from updated_at.
Each test runs in one transaction that is rolled back. Run: uv run pytest tests/test_cleanup.py"""

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from pipeline.cleanup import run_cleanup
from pipeline.load_chat import DATABASE_URL


@pytest.fixture()
def conn():
    c = psycopg.connect(DATABASE_URL)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _visit(conn, days_old: int):
    pid, domain = conn.execute("select professional_id, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()
    visitor, activity = uuid.uuid4(), uuid.uuid4()
    old = datetime.now(timezone.utc) - timedelta(days=days_old)
    conn.execute("""insert into conv_visitor (professional_id, domain, visitor_id, have_consent, first_seen_at, last_seen_at,
        updated_at) values (%s, %s, %s, false, %s, %s, %s)""", (pid, domain, visitor, old, old, old))
    conn.execute("""insert into conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status, started_at,
        last_activity_at, updated_at) values (%s, %s, %s, %s, false, 'completed', %s, %s, %s)""",
                 (activity, pid, domain, visitor, old, old, old))
    return visitor, activity


def test_a_visit_older_than_20_days_is_removed(conn):
    _, activity = _visit(conn, days_old=25)
    run_cleanup(conn)
    assert conn.execute("select count(*) from conv_activity where activity_id = %s", (activity,)).fetchone()[0] == 0


def test_a_recent_visit_is_kept(conn):
    _, activity = _visit(conn, days_old=5)
    run_cleanup(conn)
    assert conn.execute("select count(*) from conv_activity where activity_id = %s", (activity,)).fetchone()[0] == 1


def test_a_visitor_is_kept_for_a_year_even_without_consent(conn):
    visitor, _ = _visit(conn, days_old=60)
    run_cleanup(conn)
    assert conn.execute("select count(*) from conv_visitor where visitor_id = %s", (visitor,)).fetchone()[0] == 1


def test_a_visitor_older_than_a_year_is_removed(conn):
    visitor, _ = _visit(conn, days_old=400)
    run_cleanup(conn)
    assert conn.execute("select count(*) from conv_visitor where visitor_id = %s", (visitor,)).fetchone()[0] == 0


def test_daily_totals_and_questions_have_no_expiry(conn):
    removed = run_cleanup(conn, now=datetime.now(timezone.utc) + timedelta(days=3650))
    assert set(removed) >= {"conv_session", "conv_activity", "conv_visitor"}
    assert conn.execute("select count(*) from conv_daily").fetchone()[0] >= 1
