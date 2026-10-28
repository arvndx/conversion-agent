"""Tests for step 3 (abuse strikes and the block, A73). They use the local Redis and Postgres.

Run from the app folder: uv run pytest
"""

import uuid

import pytest

from pipeline.abuse import apply_strike, block_key, is_browser_blocked
from pipeline.load_chat import connect, redis_client, session_key, start_turn
from shared.bundles import load_bundles as write_bundles

RESOURCE_TYPE = "professional"
import psycopg as _psycopg
from pipeline.load_chat import DATABASE_URL as _DB
with _psycopg.connect(_DB) as _c:
    RESOURCE_ID = str(_c.execute("select professional_id from conv_domains where domain = %s", ("demo-diner-1.example",)).fetchone()[0])
DOMAIN = "demo-diner-1.example"
WARNING = "Please keep the chat respectful. I can help with questions about Spice Garden."


@pytest.fixture(scope="module")
def client():
    r = redis_client()
    write_bundles(r)
    yield r


@pytest.fixture()
def chat(client):
    """A new chat held in Redis, with its keys removed afterwards."""
    session_id = f"test-abuse-{uuid.uuid4()}"
    client.hset(session_key(session_id), mapping={
        "session_id": session_id, "resource_type": RESOURCE_TYPE, "resource_id": RESOURCE_ID,
        "domain": DOMAIN, "status": "open", "consent": "1", "visitor_id": "", "location": "Austin, US",
        "turn_count": "0", "update_status": "0", "conversation": "[]",
    })
    tokens = []
    yield session_id, tokens
    client.delete(session_key(session_id))
    client.srem("session_updates", session_id)
    for token in tokens:
        client.delete(block_key(token))


def test_first_strike_gives_the_warning(client, chat):
    session_id, _ = chat
    result = apply_strike(client, session_id, WARNING)
    assert result.state == "warning"
    assert result.strikes == 1
    assert result.reply == WARNING
    assert client.hget(session_key(session_id), "status") == "open"


def test_second_strike_also_gives_the_warning(client, chat):
    session_id, _ = chat
    apply_strike(client, session_id, WARNING)
    result = apply_strike(client, session_id, WARNING)
    assert result.state == "warning"
    assert result.strikes == 2


def test_third_strike_in_the_same_chat_blocks_the_chat_and_the_browser(client, chat):
    session_id, tokens = chat
    apply_strike(client, session_id, WARNING)
    apply_strike(client, session_id, WARNING)
    result = apply_strike(client, session_id, WARNING, minutes=3)
    tokens.append(result.block_token)
    assert result.state == "blocked"
    assert result.strikes == 3
    assert result.reply is None
    assert client.hget(session_key(session_id), "status") == "blocked"
    assert is_browser_blocked(client, result.block_token)
    ttl = client.ttl(block_key(result.block_token))
    assert 3 * 60 - 5 <= ttl <= 3 * 60


def test_block_length_comes_from_the_environment(client, chat, monkeypatch):
    session_id, tokens = chat
    monkeypatch.setenv("BLOCK_MINUTES", "7")
    for _ in range(2):
        apply_strike(client, session_id, WARNING)
    result = apply_strike(client, session_id, WARNING)
    tokens.append(result.block_token)
    assert result.blocked_for_minutes == 7
    assert 7 * 60 - 5 <= client.ttl(block_key(result.block_token)) <= 7 * 60


def test_strikes_in_different_chats_do_not_add_up(client, chat):
    """Two strikes in one chat and two in another do not block (confirmed 2026-10-20)."""
    session_id, _ = chat
    apply_strike(client, session_id, WARNING)
    apply_strike(client, session_id, WARNING)
    other = f"test-abuse-{uuid.uuid4()}"
    try:
        client.hset(session_key(other), mapping={"status": "open", "abuse_strikes": "0"})
        result = apply_strike(client, other, WARNING)
        assert result.state == "warning"
        assert result.strikes == 1
    finally:
        client.delete(session_key(other))
        client.srem("session_updates", other)


def test_a_blocked_browser_is_refused_on_a_new_chat(client, chat):
    session_id, tokens = chat
    for _ in range(2):
        apply_strike(client, session_id, WARNING)
    tokens.append(apply_strike(client, session_id, WARNING, minutes=3).block_token)
    with connect() as conn:
        turn = start_turn(client, conn, str(uuid.uuid4()), RESOURCE_TYPE, RESOURCE_ID, DOMAIN, block_token=tokens[-1])
    assert turn.state == "stopped"
    assert turn.reason == "browser blocked"


def test_a_blocked_chat_is_refused(client, chat):
    session_id, tokens = chat
    for _ in range(2):
        apply_strike(client, session_id, WARNING)
    tokens.append(apply_strike(client, session_id, WARNING, minutes=3).block_token)
    with connect() as conn:
        turn = start_turn(client, conn, session_id, RESOURCE_TYPE, RESOURCE_ID, DOMAIN)
    assert turn.state == "stopped"
    assert turn.reason == "chat blocked"


def test_an_expired_block_no_longer_refuses(client, chat):
    session_id, tokens = chat
    token = "expired-test-token"
    tokens.append(token)
    assert not is_browser_blocked(client, token)
