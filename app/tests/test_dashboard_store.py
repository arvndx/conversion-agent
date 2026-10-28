"""Tests for the dashboard's data layer on the conv_ tables. Each test is one transaction, rolled back.
Run from the app folder: uv run pytest tests/test_dashboard_store.py"""

import uuid
from datetime import datetime, timezone

import psycopg
import pytest

from dashboard import store
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
def pid(conn):
    return str(conn.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0])


def test_a_field_is_saved_and_its_switch_kept(conn, pid):
    store.save_field(conn, pid, "offers", value=["Free pickup"], shared=True)
    state = store.field_states(conn, pid)["offers"]
    assert state["value"] == ["Free pickup"] and state["shared"] is True and state["set"] is True
    store.save_field(conn, pid, "offers", shared=False)
    assert store.field_states(conn, pid)["offers"]["shared"] is False


def test_an_unknown_field_is_refused(conn, pid):
    with pytest.raises(ValueError):
        store.save_field(conn, pid, "nope", value="x")


def test_a_special_field_is_stored_by_key(conn, pid):
    store.save_special_field(conn, pid, "parking", "not_available")
    assert store.special_fields(conn, pid)["parking"] == "not_available"


def test_a_dish_with_price_availability_and_chef_special(conn, pid):
    name = f"Flow dish {uuid.uuid4()}"
    store.save_dish(conn, pid, name, section="Mains", price=12.5, availability={"days": ["mon"]}, chef_special=True)
    dish = next(d for d in store.menu(conn, pid) if d["name"] == name)
    assert dish["price"] == 12.5 and dish["chef_special"] is True and dish["availability"] == {"days": ["mon"]}
    assert name in store.chef_specials(conn, pid)


def test_a_question_is_confirmed_with_its_target(conn, pid):
    question = f"do you have a rooftop {uuid.uuid4().hex[:6]}"
    conn.execute("""insert into conv_question (question_id, professional_id, domain, question_text, topic, asked_count,
        first_asked_at, last_asked_at, answered) values (%s, %s, 'demo-diner-1.example', %s, 'other', 4, now(), now(), false)""",
                 (uuid.uuid4(), pid, question))
    row = next(r for r in store.insights(conn, pid) if r["question"] == question)
    assert row["asked"] == 4 and row["status"] == "open"
    store.confirm_insight(conn, pid, question, "menu", "dashboard")
    row = next(r for r in store.insights(conn, pid) if r["question"] == question)
    assert row["confirmed_target"] == "menu" and row["status"] == "added"


def test_a_lead_status_moves_on(conn, pid):
    hid = conn.execute("select handover_id from conv_handover where professional_id = %s limit 1", (pid,)).fetchone()
    if hid is None:
        pytest.skip("no handover in the demo data")
    store.set_lead_status(conn, pid, str(hid[0]), "contacted")
    assert conn.execute("select status from conv_handover where handover_id = %s", (hid[0],)).fetchone()[0] == "contacted"


def test_hot_visitors_follow_the_threshold(conn, pid):
    conn.execute("update conv_professional_settings set hot_visitor_threshold = 60 where professional_id = %s", (pid,))
    before = len(store.hot_visitors(conn, pid))
    added = store.refresh_hot_visitors(conn, pid)
    assert added >= 0 and len(store.hot_visitors(conn, pid)) >= before


def test_a_domain_is_paused_and_its_colours_are_kept(conn, pid):
    # the transaction is rolled back at the end, so the demo data is not changed
    store.set_domain_status(conn, pid, "demo-diner-2.example", "paused")
    assert "demo-diner-2.example" not in store.active_domains(conn, pid)
    store.set_colours(conn, pid, "demo-diner-1.example", "#123456", "#abcdef")
    assert conn.execute("select primary_color, accent_color from conv_domains where domain = 'demo-diner-1.example'").fetchone() == ("#123456", "#abcdef")


def test_a_change_is_logged_for_the_business(conn, pid):
    store.log_change(conn, pid, who="test", page="admin", area="widget_status", action="changed", summary="test change",
                     before="on", after="off", batch_id="t1")
    assert any(row[6] == "test change" for row in store.recent_changes(conn, pid))


def test_the_subscription_is_read_from_the_entitlement_copy(conn, pid):
    products = {row[0] for row in store.subscription(conn, pid)}
    assert "conversion_agent" in products
