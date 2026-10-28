"""Tests for the chat API (api/chat_api.py) on the conv_ tables. They call the endpoints in-process with the model replaced by a
script, the local Redis and Postgres, and a controllable clock. The flows of the turn (clicks, fixed replies, offers, the form)
are in tests/test_turn.py; these test the API around them.

The demo site is the American restaurant's first domain (conv_domains).

Run from the app folder: uv run pytest tests/test_chat_api.py
"""

import time
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.chat_api import CHAT_UNAVAILABLE, create_app
from pipeline.abuse import block_key
from pipeline.classify import SafetyResult
from pipeline.load_chat import DATABASE_URL, connect, redis_client, session_key
from pipeline.read_message import pending_key, seen_key, taking_key
from tests.model_stub import install, install_no_model, response, text_block

with psycopg.connect(DATABASE_URL) as _c:
    SITE_KEY, DOMAIN = _c.execute(
        "select site_key, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()


@pytest.fixture()
def client():
    return redis_client()


@pytest.fixture()
def clock(monkeypatch):
    """A controllable clock. Set clock['now'] to move time forward."""
    state = {"now": 1_800_000_000.0}
    monkeypatch.setattr(time, "time", lambda: state["now"])
    return state


@pytest.fixture()
def api(client, monkeypatch):
    install(monkeypatch, [response(text_block("We have a Smash Burger at 11.50."))])
    return TestClient(create_app(redis_client=client, connect_fn=connect))


@pytest.fixture()
def chats(client):
    made = []
    yield made
    for sid in made:
        client.delete(session_key(sid), pending_key(sid), taking_key(sid), seen_key(sid))
        client.srem("session_updates", sid)
        client.srem("open_sessions", sid)
    with psycopg.connect(DATABASE_URL) as c:
        c.execute("delete from conv_question where question_text like 'chat api test%%'")
        c.commit()


def send(api, text, *, session_id=None, domain=DOMAIN, site_key=SITE_KEY):
    body = {"site_key": site_key, "domain": domain, "text": text, "msg_id": str(uuid.uuid4())}
    if session_id:
        body["session_id"] = session_id
    return api.post("/chat/message", json=body)


def test_health(api):
    assert api.get("/health").json() == {"status": "ok"}


def test_an_unknown_site_key_is_refused(api, clock):
    assert send(api, "hello", site_key="wk_test_unknown000000000001").status_code == 404
    form = {"site_key": "wk_test_unknown000000000001", "domain": DOMAIN, "session_id": str(uuid.uuid4()),
            "action_key": "book_reservation", "values": {}}
    assert api.post("/chat/form", json=form).status_code == 404


def test_a_message_gets_its_reply_at_once_with_the_card_and_errors_keys(api, clock, chats):
    body = send(api, "chat api test do you have burgers").json()
    chats.append(body["session_id"])
    assert body["state"] == "reply" and body["reply"] == "We have a Smash Burger at 11.50."
    assert body["card"] is None and body["errors"] is None and "block_token" in body


def test_a_new_chat_gets_a_session_id_from_the_server(api, clock, chats):
    body = send(api, "hello").json()
    chats.append(body["session_id"])
    assert len(body["session_id"]) == 36


def test_a_site_key_works_only_on_its_own_domain(api):
    body = send(api, "hello", domain="demo-diner-2.example").json()
    assert body["state"] == "stopped" and body["reply"] == CHAT_UNAVAILABLE
    form = {"site_key": SITE_KEY, "domain": "demo-diner-2.example", "session_id": str(uuid.uuid4()),
            "action_key": "book_reservation", "values": {}}
    assert api.post("/chat/form", json=form).json()["state"] == "stopped"


def test_a_domain_that_is_not_allowed_is_stopped(api, clock, chats):
    body = send(api, "hello", domain="evil.example").json()
    if body.get("session_id"):
        chats.append(body["session_id"])
    assert body["state"] == "stopped" and body["reply"] == CHAT_UNAVAILABLE


def test_a_message_that_is_too_long_gets_the_tables_reply(api, clock, chats):
    body = send(api, "x" * 501).json()
    chats.append(body["session_id"])
    assert body["state"] == "reply" and body["reply"] and "{" not in body["reply"]


def test_closing_the_widget_ends_the_chat(api, clock, chats, client):
    body = send(api, "chat api test where can I order takeout").json()
    chats.append(body["session_id"])
    closed = api.post("/chat/close", json={"site_key": SITE_KEY, "domain": DOMAIN, "session_id": body["session_id"]})
    assert closed.json()["closed"] is True
    assert client.hget(session_key(body["session_id"]), "status") == "closed"
    clock["now"] += 10
    after = send(api, "one more thing", session_id=body["session_id"]).json()
    assert after["state"] == "stopped" and after["reply"] == CHAT_UNAVAILABLE


def test_closing_from_another_domain_is_refused(api, clock, chats):
    body = send(api, "chat api test hello there friend").json()
    chats.append(body["session_id"])
    response_ = api.post("/chat/close", json={"site_key": SITE_KEY, "domain": "demo-diner-2.example",
                                              "session_id": body["session_id"]})
    assert response_.status_code == 403


def test_a_blocked_browser_is_refused_on_a_new_chat_with_the_block_token(client, clock, chats, monkeypatch):
    install(monkeypatch, safety=SafetyResult("no", None, True))   # every message is abusive
    api = TestClient(create_app(redis_client=client, connect_fn=connect))
    first = send(api, "chat api test you useless idiots").json()
    chats.append(first["session_id"])
    sid = first["session_id"]
    token = None
    for _ in range(2):   # the first message above is the first strike; these are the second and third
        clock["now"] += 20
        last = send(api, "chat api test you useless idiots", session_id=sid).json()
        token = last.get("block_token") or token
    assert last["state"] == "blocked" and last["reply"] == CHAT_UNAVAILABLE and token
    install_no_model(monkeypatch)
    try:
        clock["now"] += 60
        with_token = api.post("/chat/message", json={"site_key": SITE_KEY, "domain": DOMAIN, "text": "hello",
                                                     "msg_id": str(uuid.uuid4()), "block_token": token}).json()
        assert with_token["state"] == "stopped" and with_token["reply"] == CHAT_UNAVAILABLE
        form = api.post("/chat/form", json={"site_key": SITE_KEY, "domain": DOMAIN, "session_id": str(uuid.uuid4()),
                                            "action_key": "book_reservation", "values": {}, "block_token": token}).json()
        assert form["state"] == "stopped"
    finally:
        client.delete(block_key(token))


def test_config_gives_the_title_the_default_questions_and_the_quick_actions_from_the_tables(api):
    body = api.get("/chat/config", params={"site_key": SITE_KEY, "domain": DOMAIN}).json()
    assert body["enabled"] is True and body["default_questions"]
    actions = body["quick_actions"]
    assert 1 <= len(actions) <= 5 and [a["label"] for a in actions] == body["default_questions"]
    assert {"key": "book_reservation", "label": "Book a Table"} in actions
    assert not {a["key"] for a in actions} & {"critical_handover", "ai_down_handover", "fallback_handover", "direct_handover"}


def test_config_refuses_a_domain_that_is_not_allowed_and_an_unknown_site_key(api):
    assert api.get("/chat/config", params={"site_key": SITE_KEY, "domain": "evil.example"}).status_code == 403
    assert api.get("/chat/config", params={"site_key": "wk_test_unknown000000000001", "domain": DOMAIN}).status_code == 404
