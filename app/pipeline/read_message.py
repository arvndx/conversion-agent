"""Step 1 of the turn: read the visitor's message.

1. Each message is added to the chat's pending list in Redis (pending_<session_id>), with its time.
2. A turn starts as soon as the message arrives (QUIET_SECONDS is 0). The widget keeps its box locked until the reply comes back.
3. The pending messages become one turn, in the order they arrived.
4. The turn is checked: it must not be empty, and it must be within MAX_CHARS.
5. A message ID already seen in this chat is ignored, so a retry does not count twice.

Redis keys:
    pending_<session_id>          list of pending messages (JSON), oldest first
    pending_<session_id>:taking   the messages of a turn being taken (short-lived)
    seen_<session_id>             set of message IDs seen in this chat (expires after SEEN_TTL_SECONDS)

Values are the starting settings: no quiet period, 500 characters.
"""

import json
import time
from dataclasses import dataclass, field

import redis

QUIET_SECONDS = 0  # no wait: the reply starts with the message (the widget locks its box until it arrives)
MAX_WAIT_SECONDS = 15
MAX_CHARS = 500
SEEN_TTL_SECONDS = 24 * 60 * 60


def pending_key(session_id: str) -> str:
    return f"pending_{session_id}"


def taking_key(session_id: str) -> str:
    return f"pending_{session_id}:taking"


def seen_key(session_id: str) -> str:
    return f"seen_{session_id}"


@dataclass
class Receipt:
    state: str  # "queued", "duplicate", "empty" or "too_long"
    reason: str | None = None


def receive_message(
    client: redis.Redis, session_id: str, msg_id: str, text: str, now: float | None = None
) -> Receipt:
    """Queue one message from the widget, unless it is a repeat, empty or too long."""
    now = time.time() if now is None else now
    cleaned = (text or "").strip()
    if not cleaned:
        return Receipt("empty", "message is empty")
    if len(cleaned) > MAX_CHARS:
        return Receipt("too_long", f"message is longer than {MAX_CHARS} characters")

    seen = seen_key(session_id)
    # SADD returns 0 when the ID was already there.
    if client.sadd(seen, msg_id) == 0:
        return Receipt("duplicate", "message ID already seen")
    client.expire(seen, SEEN_TTL_SECONDS)

    item = {"msg_id": msg_id, "text": cleaned, "received_at": now}
    client.rpush(pending_key(session_id), json.dumps(item, ensure_ascii=False))
    return Receipt("queued")


@dataclass
class ReadResult:
    state: str  # "waiting", "turn" or "stopped"
    text: str | None = None
    msg_ids: list[str] = field(default_factory=list)
    reason: str | None = None


def take_turn(client: redis.Redis, session_id: str, now: float | None = None) -> ReadResult:
    """Return the combined turn once the visitor has been quiet for QUIET_SECONDS, or at MAX_WAIT_SECONDS."""
    now = time.time() if now is None else now
    key = pending_key(session_id)
    raw = client.lrange(key, 0, -1)
    if not raw:
        return ReadResult("waiting")

    items = [json.loads(r) for r in raw]
    first_at = items[0]["received_at"]
    last_at = items[-1]["received_at"]
    quiet_enough = now - last_at >= QUIET_SECONDS
    waited_long_enough = now - first_at >= MAX_WAIT_SECONDS
    if not (quiet_enough or waited_long_enough):
        return ReadResult("waiting")

    # Move the pending messages aside in one step. Anything sent after this goes to a new pending list.
    taking = taking_key(session_id)
    try:
        client.rename(key, taking)
    except redis.ResponseError:
        return ReadResult("waiting")  # another worker took them first
    taken = [json.loads(r) for r in client.lrange(taking, 0, -1)]
    client.delete(taking)

    combined = "\n".join(item["text"] for item in taken)
    msg_ids = [item["msg_id"] for item in taken]
    if len(combined) > MAX_CHARS:
        return ReadResult("stopped", msg_ids=msg_ids, reason=f"the messages together are longer than {MAX_CHARS} characters")
    return ReadResult("turn", text=combined, msg_ids=msg_ids)
