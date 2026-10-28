"""Step 3 of the turn: abuse strikes and the block (A73).

A strike is counted for an abusive message that is not critical. The strikes are counted per chat.
  - Strikes 1 and 2: the visitor gets the warning, and no answer is given.
  - Strike 3 in the same chat: the chat is blocked, and the browser is blocked too.

The browser block is a token. The server stores it in Redis (block_<token>) with an expiry, and the widget keeps the
token in the browser. A new chat sent with a blocked token is refused (step 0). Strikes from older chats are added
to the visitor's row in the visitors table later, in the batch (not in this step).

The block length comes from BLOCK_MINUTES (60 in production, 3 in test).
"""

import os
import secrets
from dataclasses import dataclass

import redis

WARNING_ON_STRIKES = (1, 2)
BLOCK_ON_STRIKE = 3


def block_minutes() -> int:
    return int(os.environ.get("BLOCK_MINUTES", "60"))


def block_key(token: str) -> str:
    return f"block_{token}"


@dataclass
class StrikeResult:
    state: str  # "warning" or "blocked"
    strikes: int
    reply: str | None
    block_token: str | None
    blocked_for_minutes: int | None


def apply_strike(client: redis.Redis, session_id: str, warning_text: str, minutes: int | None = None) -> StrikeResult:
    """Count one strike in this chat. Return the warning, or the block on the third strike in the same chat."""
    key = f"session_{session_id}"
    strikes = int(client.hincrby(key, "abuse_strikes", 1))
    client.sadd("session_updates", session_id)
    client.hset(key, "update_status", 1)

    if strikes in WARNING_ON_STRIKES:
        return StrikeResult("warning", strikes, warning_text, None, None)

    # Third strike in the same chat: block the chat and the browser.
    minutes = block_minutes() if minutes is None else minutes
    token = secrets.token_urlsafe(24)
    client.set(block_key(token), session_id, ex=minutes * 60)
    client.hset(key, mapping={"status": "blocked", "update_status": 1})
    return StrikeResult("blocked", strikes, None, token, minutes)


def is_browser_blocked(client: redis.Redis, token: str | None) -> bool:
    if not token:
        return False
    return client.exists(block_key(token)) == 1
