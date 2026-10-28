"""The loader's checks on the conv_ tables: the switches (enabled, kill switch, domains) and the rebuild of a chat from
the tables. Run from the app folder: uv run pytest tests/test_load_chat.py"""

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL, check_switches, rebuild_session, redis_client, session_key
from shared.bundle_tables import load_customer


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
    pid, domain = conn.execute("select professional_id, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()
    return str(pid), domain


def _customer(conn, pid, **changes):
    customer = load_customer(conn, pid)
    customer.update(changes)
    return customer


def test_an_enabled_site_on_its_domain_may_chat(conn, pro):
    pid, domain = pro
    result = check_switches(_customer(conn, pid), "professional", pid, domain, new_chat=True)
    assert result.allowed is True


def test_a_site_on_another_domain_may_not_chat(conn, pro):
    pid, _ = pro
    result = check_switches(_customer(conn, pid), "professional", pid, "evil.example", new_chat=True)
    assert result.allowed is False and "domain" in result.reason


def test_stop_everything_stops_all_chats(conn, pro):
    pid, domain = pro
    result = check_switches(_customer(conn, pid, kill_switch="stop_everything"), "professional", pid, domain, new_chat=True)
    assert result.allowed is False


def test_stop_new_chats_lets_a_running_chat_finish(conn, pro):
    pid, domain = pro
    customer = _customer(conn, pid, kill_switch="stop_new_chats")
    assert check_switches(customer, "professional", pid, domain, new_chat=True).allowed is False
    assert check_switches(customer, "professional", pid, domain, new_chat=False).allowed is True


def test_a_chat_is_rebuilt_from_its_row_and_visit(conn, pro):
    pid, domain = pro
    visit, chat = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    conn.execute("""insert into conv_visitor (professional_id, domain, visitor_id, have_consent, first_seen_at, last_seen_at)
        values (%s, %s, %s, false, %s, %s)""", (pid, domain, visit, now, now))
    conn.execute("""insert into conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status,
        started_at, last_activity_at, city, state) values (%s, %s, %s, %s, false, 'open', %s, %s, 'Chicago', 'IL')""",
                 (visit, pid, domain, visit, now, now))
    conn.execute("insert into conv_session (session_id, activity_id, messages, topic) values (%s, %s, %s::jsonb, 'hours')",
                 (chat, visit, '[{"request": "hi", "response": "hello", "event_time": "x"}]'))
    row = rebuild_session(conn, str(chat))
    assert row["resource_id"] == pid and row["domain"] == domain and row["location"] == "Chicago, IL"
    assert row["turn_count"] == 1 and row["visitor_id"] == "" and row["status"] == "open"


def test_a_chat_rebuilt_from_its_row_stays_on_the_bundle_versions_it_started_with(conn, pro):
    pid, domain = pro
    visit, chat = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    conn.execute("""insert into conv_visitor (professional_id, domain, visitor_id, have_consent, first_seen_at, last_seen_at)
        values (%s, %s, %s, false, %s, %s)""", (pid, domain, visit, now, now))
    conn.execute("""insert into conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status,
        started_at, last_activity_at) values (%s, %s, %s, %s, false, 'open', %s, %s)""", (visit, pid, domain, visit, now, now))
    conn.execute("insert into conv_session (session_id, activity_id, messages, customer_version, category_version) "
                 "values (%s, %s, '[]'::jsonb, 7, 9)", (chat, visit))
    row = rebuild_session(conn, str(chat))
    assert (row["customer_v"], row["category_v"]) == (7, 9)
    other = uuid.uuid4()
    conn.execute("insert into conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status, started_at, "
                 "last_activity_at) values (%s, %s, %s, %s, false, 'open', %s, %s)", (other, pid, domain, visit, now, now))
    conn.execute("insert into conv_session (session_id, activity_id, messages) values (%s, %s, '[]'::jsonb)", (other, other))
    assert "customer_v" not in rebuild_session(conn, str(other))   # a chat saved without versions is not pinned


def test_a_business_whose_subscription_is_not_active_may_not_chat(conn, pro):
    pid, domain = pro
    result = check_switches(_customer(conn, pid, enabled=False), "professional", pid, domain, new_chat=False)
    assert result.allowed is False and "subscription" in result.reason


def test_a_domain_that_is_not_among_the_active_ones_may_not_chat(conn, pro):
    pid, domain = pro
    assert check_switches(_customer(conn, pid, allowed_domains=[]), "professional", pid, domain, new_chat=True).allowed is False


def test_the_checks_need_no_database(pro):
    pid, domain = pro
    customer = {"enabled": True, "kill_switch": "none", "allowed_domains": [domain]}
    assert check_switches(customer, "professional", pid, domain, new_chat=True).allowed is True


def test_an_unknown_chat_cannot_be_rebuilt(conn):
    assert rebuild_session(conn, str(uuid.uuid4())) is None
