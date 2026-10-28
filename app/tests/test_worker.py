"""The worker saves each chat to the conv_ tables: the visitor (with consent), the visit, the chat, the handover (once),
and the daily totals. Run from the app folder: uv run pytest tests/test_worker.py"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.chat_api import create_app
from pipeline import worker
from pipeline.load_chat import DATABASE_URL, connect, redis_client, session_key
from tests.model_stub import install_no_model

with psycopg.connect(DATABASE_URL) as _c:
    SITE_KEY, DOMAIN, PRO = _c.execute(
        "select site_key, domain, professional_id from conv_domains where domain = 'demo-diner-2.example'").fetchone()



@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    install_no_model(monkeypatch)   # these chats use clicks, fixed replies and the form: none of them calls a model


@pytest.fixture()
def api():
    return TestClient(create_app(redis_client=redis_client(), connect_fn=connect))


@pytest.fixture()
def chat():
    made = {"session": None, "activity": str(uuid.uuid4()), "visitor": str(uuid.uuid4())}
    yield made
    r = redis_client()
    with psycopg.connect(DATABASE_URL) as c:
        c.execute("delete from conv_handover where professional_id = %s and name like 'Worker %%'", (PRO,))
        if made["session"]:
            c.execute("delete from conv_session where session_id = %s", (made["session"],))
        c.execute("delete from conv_activity where activity_id = %s", (made["activity"],))
        c.execute("delete from conv_visitor where professional_id = %s and domain = %s and visitor_id = %s",
                  (PRO, DOMAIN, made["visitor"]))
        c.commit()
    if made["session"]:
        r.delete(session_key(made["session"]))
        r.srem("session_updates", made["session"])


def say(api, chat, text, consent=True, **extra):
    body = {"site_key": SITE_KEY, "domain": DOMAIN, "text": text, "msg_id": str(uuid.uuid4()),
            "activity_id": chat["activity"], "consent": consent, "visitor_id": chat["visitor"], **extra}
    if chat["session"]:
        body["session_id"] = chat["session"]
    response = api.post("/chat/message", json=body).json()
    chat["session"] = response.get("session_id") or chat["session"]
    return response


def test_a_chat_with_consent_is_saved_with_its_visitor_and_visit(api, chat):
    say(api, chat, "hello")
    with psycopg.connect(DATABASE_URL) as c:
        worker.run_once(redis_client(), c)
        session = c.execute("select count(*) from conv_session where session_id = %s", (chat["session"],)).fetchone()[0]
        visit = c.execute("select have_consent, status from conv_activity where activity_id = %s", (chat["activity"],)).fetchone()
        visitor = c.execute("select have_consent, visits from conv_visitor where professional_id = %s and domain = %s and visitor_id = %s",
                            (PRO, DOMAIN, chat["visitor"])).fetchone()
        c.commit()
    assert session == 1 and visit == (True, "open") and visitor == (True, 1)


def test_a_request_is_saved_once_with_its_type_and_extra_fields_even_if_the_worker_runs_again(api, chat):
    tag = "".join(c for c in uuid.uuid4().hex if c.isalpha())[:6]   # letters only: it is part of a name
    say(api, chat, "Book a Table", action_key="book_reservation")
    api.post("/chat/form", json={"site_key": SITE_KEY, "domain": DOMAIN, "session_id": chat["session"], "action_key": "book_reservation",
                                 "values": {"name": f"Worker {tag}", "email": f"worker.{tag}@example.com", "question": "A table for two"}})
    with psycopg.connect(DATABASE_URL) as c:
        before = c.execute("select handover_id, request_type, status from conv_handover where session_id = %s", (chat["session"],)).fetchall()
        worker.run_once(redis_client(), c)
        worker.run_once(redis_client(), c)
        after = c.execute("select handover_id, request_type, status, action_key from conv_handover where session_id = %s",
                          (chat["session"],)).fetchall()
        c.commit()
    assert len(before) == 1 and after == [(before[0][0], "table booking", "new", "book_reservation")]


def test_a_chat_that_closes_leaves_the_open_list(api, chat):
    say(api, chat, "hello")
    redis_client().sadd("open_sessions", chat["session"])
    api.post("/chat/close", json={"site_key": SITE_KEY, "domain": DOMAIN, "session_id": chat["session"]})
    with psycopg.connect(DATABASE_URL) as c:
        worker.run_once(redis_client(), c)
        c.commit()
    assert not redis_client().sismember("open_sessions", chat["session"])
