"""A chat reads only Redis for its business and its category (the bundles and the site map). The tables are read when something is
missing from Redis, and written to; the chat's own saved rows are read to confirm a saved request. These tests record every SQL
statement of a whole chat and look at which tables it touched.
Run from the app folder: uv run pytest tests/test_redis_only.py"""

import re
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.chat_api import create_app
from pipeline import site_bundles
from pipeline.load_chat import DATABASE_URL, redis_client, session_key
from tests.model_stub import install, response, text_block, tool_block

DINER = "483dc8e7-3f03-5fbb-878b-77ee433ed0b3"
CONFIG_TABLES = {"conv_domains", "conv_professional_settings", "professionals", "organizations", "conv_category_settings",
                 "conv_action", "conv_tool", "conv_static_reply", "conv_critical_reply", "conv_menu", "conv_professional_menu",
                 "conv_calendar_connection", "exp_entitlements", "exp_category_knowledge", "exp_category_compliance", "exp_entity"}
TABLE = re.compile(r"\b(?:from|join|into|update)\s+(?:public\.)?(\w+)", re.IGNORECASE)

with psycopg.connect(DATABASE_URL) as _c:
    SITE_KEY, DOMAIN = _c.execute("select site_key, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()

STATEMENTS: list[str] = []


class RecordingCursor(psycopg.Cursor):
    def execute(self, query, params=None, **kwargs):
        STATEMENTS.append(query if isinstance(query, str) else query.as_string())
        return super().execute(query, params, **kwargs)


def recording_connection():
    return psycopg.connect(DATABASE_URL, cursor_factory=RecordingCursor)


def touched():
    return {name.lower() for sql in STATEMENTS for name in TABLE.findall(sql)} - {"set"}   # "do update set" is not a table


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    from pipeline import worker
    monkeypatch.setattr(worker, "send_handover_emails", lambda *args, **kwargs: 0)
    STATEMENTS.clear()
    made = []
    yield made
    r = redis_client()
    with psycopg.connect(DATABASE_URL) as c:
        for sid in made:
            c.execute("delete from conv_handover where session_id = %s", (sid,))
            c.execute("delete from conv_session where session_id = %s", (sid,))
            c.execute("delete from conv_activity where activity_id = %s", (sid,))
            r.delete(session_key(sid))
            r.srem("session_updates", sid)
            r.srem("open_sessions", sid)
        c.execute("delete from conv_question where professional_id = %s and question_text like 'redis only test%%'", (DINER,))
        c.commit()


@pytest.fixture()
def api():
    return TestClient(create_app(redis_client=redis_client(), connect_fn=recording_connection))


def post(api, path, made, **body):
    out = api.post(path, json={"site_key": SITE_KEY, "domain": DOMAIN, **body}).json()
    if out.get("session_id") and out["session_id"] not in made:
        made.append(out["session_id"])
    return out


def test_a_whole_chat_never_reads_the_configuration_tables(api, clean, monkeypatch):
    install(monkeypatch, [response(text_block("We open at nine."))])
    api.get("/chat/config", params={"site_key": SITE_KEY, "domain": DOMAIN})
    first = post(api, "/chat/message", clean, text="hi", msg_id=str(uuid.uuid4()))                      # a fixed reply
    sid = first["session_id"]
    post(api, "/chat/message", clean, text="redis only test when do you open", msg_id=str(uuid.uuid4()), session_id=sid)   # the agent
    card = post(api, "/chat/message", clean, text="Book a Table", action_key="book_reservation", msg_id=str(uuid.uuid4()),
                session_id=sid)
    assert card["card"] is not None
    done = post(api, "/chat/form", clean, session_id=sid, action_key="book_reservation",
                values={"name": "Priya Shah", "email": "p@x.com", "question": "A table for two"})
    assert "conveyed" in done["reply"]
    post(api, "/activity", clean, session_id=sid, activity_id=str(uuid.uuid4()), events=[])
    assert STATEMENTS, "the test recorded nothing"
    assert not touched() & CONFIG_TABLES, touched() & CONFIG_TABLES


def test_the_tables_the_chat_does_touch_are_its_own_rows(api, clean, monkeypatch):
    install(monkeypatch, [response(tool_block("request_handoff", {"action_key": "direct_handover"}))])
    post(api, "/chat/message", clean, text="redis only test please pass me on", msg_id=str(uuid.uuid4()))
    sid = clean[0]
    post(api, "/chat/form", clean, session_id=sid, action_key="direct_handover",
         values={"name": "Priya Shah", "email": "p@x.com", "question": "Please pass me on"})
    assert touched() <= {"conv_handover", "conv_session", "conv_activity", "conv_visitor", "conv_daily", "conv_question",
                         "conv_hot_visitor", "conv_log"}, touched()


def test_the_widget_theme_and_the_page_tracking_switch_come_from_the_bundle(api):
    body = api.get("/chat/config", params={"site_key": SITE_KEY, "domain": DOMAIN}).json()
    assert body["theme"] == site_bundles_customer()["theme"][DOMAIN]
    assert not touched() & CONFIG_TABLES


def site_bundles_customer():
    from pipeline.load_chat import load_bundles
    return load_bundles(redis_client(), "professional", DINER).customer


def test_a_missing_bundle_and_site_map_are_built_again_from_the_tables(api, clean, monkeypatch):
    install(monkeypatch, [response(text_block("Yes."))])
    r = redis_client()
    r.delete(site_bundles.site_map_key(SITE_KEY), site_bundles.current_customer_key(DINER))
    out = post(api, "/chat/message", clean, text="redis only test hello again friend", msg_id=str(uuid.uuid4()))
    assert out["state"] == "reply" and touched() & {"conv_domains", "conv_professional_settings"}   # read once, to build them
    STATEMENTS.clear()
    post(api, "/chat/message", clean, text="redis only test another question here", msg_id=str(uuid.uuid4()), session_id=out["session_id"])
    assert not touched() & CONFIG_TABLES


def test_the_site_map_is_written_when_a_bundle_is_built_and_read_without_the_tables():
    r = redis_client()
    r.delete(site_bundles.site_map_key(SITE_KEY))
    with psycopg.connect(DATABASE_URL) as conn:
        site_bundles.publish_customer(conn, r, DINER)
    class NoDatabase:
        def execute(self, *args, **kwargs):
            raise AssertionError("the tables were read")
    site = site_bundles.site_location(NoDatabase(), r, SITE_KEY)
    assert site == {"professional_id": DINER, "domain": DOMAIN, "status": "active", "category_id": "american_restaurant"}


def test_a_site_key_that_is_not_in_the_tables_is_remembered_as_missing_for_a_short_time():
    r = redis_client()
    key = "wk_test_nobodyhasthis000001"
    r.delete(f"site_missing_{key}")
    with psycopg.connect(DATABASE_URL, cursor_factory=RecordingCursor) as conn:
        assert site_bundles.site_location(conn, r, key) is None
        reads = len(STATEMENTS)
        assert site_bundles.site_location(conn, r, key) is None
        assert len(STATEMENTS) == reads   # the second guess did not reach the tables
    assert 0 < r.ttl(f"site_missing_{key}") <= site_bundles.SITE_MISSING_SECONDS
    r.delete(f"site_missing_{key}")


def test_a_paused_site_stops_working_after_its_bundle_is_built_again(api):
    r = redis_client()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("update conv_domains set status = 'paused' where site_key = %s", (SITE_KEY,))
        conn.commit()
        try:
            site_bundles.publish_customer(conn, r, DINER)   # what the dashboard does after a change
            assert api.get("/chat/config", params={"site_key": SITE_KEY, "domain": DOMAIN}).status_code == 404
        finally:
            conn.execute("update conv_domains set status = 'active' where site_key = %s", (SITE_KEY,))
            conn.commit()
            site_bundles.publish_customer(conn, r, DINER)
    assert api.get("/chat/config", params={"site_key": SITE_KEY, "domain": DOMAIN}).status_code == 200


def test_the_current_bundles_need_no_table_to_be_found():
    r = redis_client()
    with psycopg.connect(DATABASE_URL, cursor_factory=RecordingCursor) as conn:
        STATEMENTS.clear()
        versions = site_bundles.ensure_bundles(conn, r, DINER)
    assert STATEMENTS == [] and all(versions)
