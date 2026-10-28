"""Save a chat's handover to the table now, and read it back, before the visitor is told it was passed on.

The chat holds the handover on the session in Redis, and the worker saves it to conv_handover a second or two later. The
visitor must not be told "passed on" before the row is in the table, so the chat saves it itself, in its own transaction (the
same write the worker does, pipeline/worker.py _save_chat), then reads the row back. The chat API commits the transaction
before the reply goes out.
"""

import json
import logging

import psycopg
import redis

from pipeline.load_chat import session_key

log = logging.getLogger(__name__)


def handover_in_table(conn: psycopg.Connection, session_id: str, action_key: str | None = None) -> bool:
    """A request for this chat is in conv_handover (for this action, when one is given)."""
    if action_key:
        return conn.execute("select 1 from conv_handover where session_id = %s and action_key = %s limit 1",
                            (session_id, action_key)).fetchone() is not None
    return conn.execute("select 1 from conv_handover where session_id = %s limit 1", (session_id,)).fetchone() is not None


def save_handover_now(client: redis.Redis, conn: psycopg.Connection, session_id: str) -> bool:
    """Write the chat's held handover to conv_handover and read the row back. True only when the row is in the table."""
    from pipeline import worker   # imported here: the worker imports the chat modules

    key = session_key(session_id)
    sess = client.hgetall(key)
    if not sess.get("handover"):
        return False
    try:
        with conn.cursor() as cur:
            handover_id = worker._save_chat(cur, session_id, sess)   # None when the row was already saved
    except Exception:
        log.exception("handover for chat %s could not be saved", session_id)
        conn.rollback()
        return False
    if not handover_in_table(conn, session_id, sess.get("handover_action") or None):
        return False
    if handover_id:   # this call saved it: the worker must not save it again, and the business is told as the worker would
        client.hset(key, mapping={"handover_saved": 1, "handover_id": handover_id})
        worker.send_handover_emails(client, conn, [(handover_id, {
            "resource_type": "professional", "resource_id": sess["resource_id"], "session_id": session_id,
            "handover": json.loads(sess["handover"])})], worker.send_email_stub)
    return True
