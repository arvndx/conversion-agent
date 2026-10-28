"""Tests for step 1 (read the visitor's message). They use the local Redis.

Run from the app folder: uv run pytest
"""

import uuid

import pytest

from pipeline.load_chat import redis_client
from pipeline.read_message import (
    MAX_CHARS,
    QUIET_SECONDS,
    pending_key,
    receive_message,
    seen_key,
    take_turn,
)


@pytest.fixture()
def client():
    return redis_client()


@pytest.fixture()
def sid(client):
    """A fresh chat ID for each test, with its Redis keys removed afterwards."""
    session_id = f"test-{uuid.uuid4()}"
    yield session_id
    for key in (pending_key(session_id), f"pending_{session_id}:taking", seen_key(session_id)):
        client.delete(key)


def test_one_message_is_ready_at_once(client, sid):
    receive_message(client, sid, "m1", "Do you have vegetarian options?", now=100.0)
    ready = take_turn(client, sid, now=100.0 + QUIET_SECONDS)
    assert ready.state == "turn"
    assert ready.text == "Do you have vegetarian options?"
    assert ready.msg_ids == ["m1"]


def test_short_messages_are_combined_in_order(client, sid):
    receive_message(client, sid, "m1", "Hi", now=100.0)
    receive_message(client, sid, "m2", "do you have", now=101.0)
    receive_message(client, sid, "m3", "parking?", now=102.0)
    turn = take_turn(client, sid, now=102.0 + QUIET_SECONDS)
    assert turn.state == "turn"
    assert turn.text == "Hi\ndo you have\nparking?"
    assert turn.msg_ids == ["m1", "m2", "m3"]
    assert client.llen(pending_key(sid)) == 0


def test_repeated_message_id_is_ignored(client, sid):
    first = receive_message(client, sid, "same", "hello", now=100.0)
    second = receive_message(client, sid, "same", "hello", now=101.0)
    assert first.state == "queued"
    assert second.state == "duplicate"
    assert client.llen(pending_key(sid)) == 1


def test_empty_message_is_refused(client, sid):
    receipt = receive_message(client, sid, "m1", "   ", now=100.0)
    assert receipt.state == "empty"
    assert client.llen(pending_key(sid)) == 0


def test_long_message_is_refused(client, sid):
    receipt = receive_message(client, sid, "m1", "x" * (MAX_CHARS + 1), now=100.0)
    assert receipt.state == "too_long"
    assert client.llen(pending_key(sid)) == 0


def test_message_at_the_limit_is_accepted(client, sid):
    receipt = receive_message(client, sid, "m1", "x" * MAX_CHARS, now=100.0)
    assert receipt.state == "queued"


def test_combined_text_over_the_limit_is_stopped(client, sid):
    half = "x" * (MAX_CHARS // 2 + 10)
    receive_message(client, sid, "m1", half, now=100.0)
    receive_message(client, sid, "m2", half, now=101.0)
    turn = take_turn(client, sid, now=101.0 + QUIET_SECONDS)
    assert turn.state == "stopped"
    assert "together are longer" in turn.reason


def test_nothing_pending_means_waiting(client, sid):
    assert take_turn(client, sid, now=100.0).state == "waiting"
