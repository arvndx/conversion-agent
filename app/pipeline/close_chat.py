"""Closing a chat (A62 d, A79). A chat ends in two ways only:
  - the visitor closes the widget (close_by_visitor), or
  - the chat has had no activity for 30 minutes (close_stale, run every minute).

Closing marks the session in Redis as closed, and puts it in session_updates with closing=1. The batch worker then
writes the final fields to the chat table, and removes the Redis copy after that write commits (A62 d).

Redis keys used here:
    session_<session_id>       the chat (status, closing, close_reason, ended_at, last_activity_at)
    session_updates            the set of chats the worker must write
    open_sessions              the set of chats that are open (checked by close_stale)
"""

from datetime import datetime, timedelta, timezone

import redis

from pipeline.load_chat import session_key

IDLE_MINUTES = 30
OPEN_SESSIONS = "open_sessions"


def close_chat(client: redis.Redis, session_id: str, reason: str, now: datetime | None = None) -> bool:
    """Close one chat. Returns False if it was already closed, or does not exist."""
    key = session_key(session_id)
    data = client.hgetall(key)
    if not data or data.get("status") == "closed":
        client.srem(OPEN_SESSIONS, session_id)
        return False
    current = now or datetime.now(timezone.utc)
    client.hset(key, mapping={
        "status": "closed",
        "closing": 1,
        "close_reason": reason,
        "ended_at": current.isoformat(),
        "update_status": 1,
    })
    client.sadd("session_updates", session_id)
    client.srem(OPEN_SESSIONS, session_id)
    return True


def close_by_visitor(client: redis.Redis, session_id: str, now: datetime | None = None) -> bool:
    return close_chat(client, session_id, "visitor_closed", now=now)


def close_stale(client: redis.Redis, now: datetime | None = None) -> list[str]:
    """Close every open chat with no activity for IDLE_MINUTES. Run every minute. Returns the chats it closed."""
    current = now or datetime.now(timezone.utc)
    closed = []
    for session_id in client.smembers(OPEN_SESSIONS):
        last = client.hget(session_key(session_id), "last_activity_at")
        if not last:
            continue
        last_at = datetime.fromisoformat(last)
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        if current - last_at >= timedelta(minutes=IDLE_MINUTES):
            if close_chat(client, session_id, "idle_30_minutes", now=current):
                closed.append(session_id)
    return closed
