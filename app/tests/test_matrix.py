"""The chat's basic flows on every active domain in conv_domains. The model is replaced by a script; each test removes the
rows it made. Run from the app folder: uv run pytest tests/test_matrix.py"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.chat_api import create_app
from pipeline import worker
from pipeline.load_chat import DATABASE_URL, connect, redis_client, session_key
from tests.model_stub import install, install_no_model, response, text_block, tool_block

with psycopg.connect(DATABASE_URL) as _c:
    SITES = _c.execute("select site_key, domain, professional_id from conv_domains where status = 'active' order by domain").fetchall()

@pytest.fixture()
def api(monkeypatch):
    install(monkeypatch, [response(text_block("Thanks, I have noted that."))])
    return TestClient(create_app(redis_client=redis_client(), connect_fn=connect))


@pytest.fixture()
def made():
    rows = {"sessions": [], "activities": [], "visitors": []}
    yield rows
    r = redis_client()
    with psycopg.connect(DATABASE_URL) as c:
        for sid in rows["sessions"]:
            c.execute("delete from conv_handover where session_id = %s", (sid,))
            c.execute("delete from conv_session where session_id = %s", (sid,))
            r.delete(session_key(sid))
            r.srem("session_updates", sid)
        for activity in rows["activities"]:
            c.execute("delete from conv_activity where activity_id = %s", (activity,))
        for pid, domain, visitor in rows["visitors"]:
            c.execute("delete from conv_visitor where professional_id = %s and domain = %s and visitor_id = %s", (pid, domain, visitor))
        c.execute("delete from conv_question where question_text ~ %s",   # the questions these tests asked
                  (r"^(please pass me on|pass me on|first|no consent|repeat|hello|new chat) [a-z0-9]{6}$",))
        c.commit()


def send(api, site, text, made, session_id=None, consent=None, visitor_id=None, activity=None):
    key, domain, _ = site
    activity = activity or str(uuid.uuid4())
    body = {"site_key": key, "domain": domain, "text": text, "msg_id": str(uuid.uuid4()), "activity_id": activity}
    if session_id:
        body["session_id"] = session_id
    if consent is not None:
        body["consent"] = consent
    if visitor_id:
        body["visitor_id"] = visitor_id
    response = api.post("/chat/message", json=body).json()
    if response.get("session_id") and response["session_id"] not in made["sessions"]:
        made["sessions"].append(response["session_id"])
    if activity not in made["activities"]:
        made["activities"].append(activity)
    return response


@pytest.mark.parametrize("site", SITES, ids=[s[1] for s in SITES])
def test_a_question_gets_a_reply(api, site, made):
    reply = send(api, site, f"hello {uuid.uuid4().hex[:6]}", made)
    assert reply["state"] == "reply" and reply["reply"]


@pytest.mark.parametrize("site", SITES, ids=[s[1] for s in SITES])
def test_a_repeated_message_is_ignored(api, site, made):
    text = f"repeat {uuid.uuid4().hex[:6]}"
    first = send(api, site, text, made)
    msg = str(uuid.uuid4())
    body = {"site_key": site[0], "domain": site[1], "text": text, "msg_id": msg, "session_id": first["session_id"]}
    api.post("/chat/message", json=body)
    again = api.post("/chat/message", json=body).json()
    assert again["state"] in ("ignored", "waiting", "reply")
    assert redis_client().llen(f"pending_{first['session_id']}") == 0


@pytest.mark.parametrize("site", SITES, ids=[s[1] for s in SITES])
def test_a_closed_chat_stops_and_a_new_chat_works(api, site, made):
    first = send(api, site, f"first {uuid.uuid4().hex[:6]}", made)
    sid = first["session_id"]
    closed = api.post("/chat/close", json={"site_key": site[0], "domain": site[1], "session_id": sid}).json()
    assert closed["closed"] is True
    after = send(api, site, "one more", made, session_id=sid)
    assert after["state"] == "stopped"
    fresh = send(api, site, f"new chat {uuid.uuid4().hex[:6]}", made)
    assert fresh["state"] == "reply" and fresh["session_id"] != sid


@pytest.mark.parametrize("site", SITES, ids=[s[1] for s in SITES])
def test_a_visit_without_consent_gets_its_own_visitor_row(api, site, made):
    text = f"no consent {uuid.uuid4().hex[:6]}"
    reply = send(api, site, text, made, consent=False)
    with psycopg.connect(DATABASE_URL) as c:
        worker.run_once(redis_client(), c)
        row = c.execute("select v.visitor_id, v.have_consent from conv_activity a join conv_visitor v using (professional_id, domain, visitor_id) "
                        "where a.activity_id = %s", (reply.get("activity") or made["activities"][-1],)).fetchone()
    if row:
        made["visitors"].append((site[2], site[1], row[0]))
        assert row[1] is False


@pytest.mark.parametrize("site", SITES, ids=[s[1] for s in SITES])
def test_a_quick_question_gives_its_form_or_its_link_with_no_model_call(site, made, monkeypatch):
    install_no_model(monkeypatch)
    api = TestClient(create_app(redis_client=redis_client(), connect_fn=connect))
    config = api.get("/chat/config", params={"site_key": site[0], "domain": site[1]}).json()
    assert config["quick_actions"]
    for action in config["quick_actions"]:
        body = {"site_key": site[0], "domain": site[1], "text": action["label"], "action_key": action["key"], "msg_id": str(uuid.uuid4())}
        out = api.post("/chat/message", json=body).json()
        made["sessions"].append(out["session_id"])
        assert out["state"] == "reply" and out["reply"]
        assert (out["card"] is None) == ("Here is" in out["reply"] or ": " in out["reply"])   # a link or facts, or a form


@pytest.mark.parametrize("site", SITES, ids=[s[1] for s in SITES])
def test_a_request_made_through_the_agent_is_saved_as_a_row_with_its_request_type(api, site, made, monkeypatch):
    tag = "".join(c for c in uuid.uuid4().hex if c.isalpha())[:6]   # letters only: it is part of a name
    install(monkeypatch, [response(tool_block("request_handoff", {"action_key": "direct_handover"}))])
    opened = send(api, site, f"please pass me on {tag}", made)
    assert opened["card"]["action_key"] == "direct_handover"
    install_no_model(monkeypatch)
    body = {"site_key": site[0], "domain": site[1], "session_id": opened["session_id"], "action_key": "direct_handover",
            "values": {"name": f"Matrix {tag}", "email": f"matrix.{tag}@example.com", "question": f"please pass me on {tag}"}}
    done = api.post("/chat/form", json=body).json()
    assert done["state"] == "reply" and "conveyed" in done["reply"]
    with psycopg.connect(DATABASE_URL) as c:
        worker.run_once(redis_client(), c)
        row = c.execute("select name, reason, request_type, action_key from conv_handover where session_id = %s", (opened["session_id"],)).fetchone()
        c.commit()
    assert row == (f"Matrix {tag}", "request_from_visitor", "direct handover", "direct_handover")
