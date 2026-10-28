"""Step 0 of the turn: load the chat.

1. Load the chat's session from Redis (session_<session_id>). If it is not there, rebuild it from the
   chat_sessions row, as in A62 f.
2. Load the customer bundle and the category bundle from Redis.
3. Check the switches (A67 d): the enabled flag and the kill switch come from the customer bundle, with the
   database as the fallback if the bundle does not have them. The allowed domains (A69) work the same way.

The result is one of:
  "ready"     an existing open chat; continue with step 1
  "new_chat"  no session exists anywhere; the chat start (a later build step) creates it
  "stopped"   a switch, a closed chat, or a domain mismatch stops the turn; reason says why
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime

import psycopg
import redis

from pipeline.abuse import is_browser_blocked
from pipeline.site_bundles import current_category_key, current_customer_key, ensure_bundles, versioned_key
from shared.bundles import category_key, customer_key

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/conversion_agent")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# A chat_sessions status in this set means the chat has ended.
CLOSED_STATUSES = {"completed", "incomplete", "handed_over", "abusive"}


class BundleMissing(Exception):
    """The customer or category bundle is not in Redis. Run: uv run python -m shared.bundles"""


def session_key(session_id: str) -> str:
    return f"session_{session_id}"


@dataclass
class Bundles:
    customer: dict
    category: dict
    versions: tuple[int, int] | None = None   # (customer version, category version) these bundles were read from


def load_bundles(client: redis.Redis, resource_type: str, resource_id: str,
                 pinned: tuple[int, int] | None = None) -> Bundles:
    """The bundles for a chat. A chat that started earlier (pinned) keeps its versions while they exist; otherwise the
    current versions are used."""
    base = customer_key(resource_type, resource_id)
    raw_customer, customer_version = None, None
    if pinned:
        customer_version = pinned[0]
        raw_customer = client.get(versioned_key(base, customer_version))
    if raw_customer is None:
        customer_version = _version(client, current_customer_key(resource_id))
        raw_customer = client.get(versioned_key(base, customer_version)) if customer_version else None
    if raw_customer is None:
        raise BundleMissing(f"customer bundle missing for {resource_type} {resource_id}")
    customer = json.loads(raw_customer)
    category_base = category_key(customer["category_id"])
    raw_category, category_version = None, None
    if pinned:
        category_version = pinned[1]
        raw_category = client.get(versioned_key(category_base, category_version))
    if raw_category is None:
        category_version = _version(client, current_category_key(customer["category_id"]))
        raw_category = client.get(versioned_key(category_base, category_version)) if category_version else None
    if raw_category is None:
        raise BundleMissing(f"category bundle missing for {customer['category_id']}")
    return Bundles(customer=customer, category=json.loads(raw_category), versions=(customer_version, category_version))


def _version(client: redis.Redis, pointer: str) -> int | None:
    value = client.get(pointer)
    return int(value) if value else None


@dataclass
class SwitchResult:
    allowed: bool
    reason: str | None


def check_switches(
    customer: dict,
    resource_type: str,
    resource_id: str,
    domain: str,
    new_chat: bool,
) -> SwitchResult:
    """May this chat run? Decided from the customer bundle alone: its subscription (enabled), its kill switch and its active
    domains. A change to any of them builds a new bundle (the dashboard and POST /bundles/rebuild do), which new messages use."""
    if not customer.get("enabled"):
        return SwitchResult(False, "subscription not active")
    kill_switch = customer.get("kill_switch", "none")
    if kill_switch == "stop_everything":
        return SwitchResult(False, "kill switch: stop everything")
    # stop_new_chats: a running chat finishes, but no new chat may start.
    if kill_switch == "stop_new_chats" and new_chat:
        return SwitchResult(False, "kill switch: no new chats")
    if domain not in (customer.get("allowed_domains") or []):
        return SwitchResult(False, f"domain not allowed: {domain}")
    return SwitchResult(True, None)


def _to_hash(session: dict) -> dict[str, str]:
    return {k: "" if v is None else str(v) for k, v in session.items()}


def _from_hash(data: dict[str, str]) -> dict:
    session = dict(data)
    session["consent"] = session.get("consent") == "1"
    session["turn_count"] = int(session.get("turn_count") or 0)
    session["update_status"] = int(session.get("update_status") or 0)
    session["conversation"] = json.loads(session.get("conversation") or "[]")
    return session


SESSION_ROW_SQL = """
    SELECT s.session_id, s.activity_id, a.professional_id, a.domain, a.have_consent, a.status, a.started_at,
           a.visitor_id, a.city, a.state, s.messages, s.customer_version, s.category_version
    FROM conv_session s JOIN conv_activity a ON a.activity_id = s.activity_id
    WHERE s.session_id = %s
"""


def rebuild_session(conn: psycopg.Connection, session_id: str) -> dict | None:
    """Rebuild the Redis hash fields from the chat's row in conv_session and its visit in conv_activity."""
    row = conn.execute(SESSION_ROW_SQL, (session_id,)).fetchone()
    if row is None:
        return None
    (sid, activity_id, professional_id, domain, have_consent, status, started_at, visitor_id, city, state, messages,
     customer_version, category_version) = row
    location = ", ".join(part for part in (city, state) if part)
    anonymous = str(visitor_id) == str(activity_id)   # the visit id stands in for the visitor id when there is no consent
    conversation = messages or []
    return {
        "session_id": str(sid),
        "activity_id": str(activity_id),
        "resource_type": "professional",
        "resource_id": str(professional_id),
        "domain": domain,
        "started_at": started_at.isoformat() if isinstance(started_at, datetime) else str(started_at),
        "status": "closed" if status in ("completed", "incomplete", "handed_over", "blocked") else "open",
        "consent": "1" if have_consent else "0",
        "visitor_id": "" if anonymous or not have_consent else str(visitor_id),
        "location": location,
        "turn_count": len(conversation),
        "update_status": 0,
        "conversation": json.dumps(conversation, ensure_ascii=False),
        # the bundle versions the chat was using, so a chat rebuilt from the tables stays on them
        **({"customer_v": customer_version, "category_v": category_version} if customer_version and category_version else {}),
    }


def load_session(client: redis.Redis, conn: psycopg.Connection, session_id: str) -> dict | None:
    key = session_key(session_id)
    data = client.hgetall(key)
    if data:
        return _from_hash(data)
    rebuilt = rebuild_session(conn, session_id)
    if rebuilt is None:
        return None
    client.hset(key, mapping=_to_hash(rebuilt))
    return _from_hash(rebuilt)


@dataclass
class TurnStart:
    state: str  # "ready", "new_chat" or "stopped"
    session: dict | None
    bundles: Bundles | None
    reason: str | None


def start_turn(
    client: redis.Redis,
    conn: psycopg.Connection,
    session_id: str,
    resource_type: str,
    resource_id: str,
    domain: str,
    block_token: str | None = None,
) -> TurnStart:
    # A73: a browser that holds a live block token is refused, even for a new chat.
    if is_browser_blocked(client, block_token):
        return TurnStart("stopped", None, None, "browser blocked")

    session = load_session(client, conn, session_id)
    is_new = session is None

    pinned = None
    if session and session.get("customer_v") and session.get("category_v"):
        pinned = (int(session["customer_v"]), int(session["category_v"]))
    if resource_type == "professional":
        ensure_bundles(conn, client, resource_id)   # built if missing; a change to the business's data builds a new version
    bundles = load_bundles(client, resource_type, resource_id, pinned=pinned)
    switches = check_switches(bundles.customer, resource_type, resource_id, domain, new_chat=is_new)
    if not switches.allowed:
        return TurnStart("stopped", session, bundles, switches.reason)

    if is_new:
        return TurnStart("new_chat", None, bundles, None)
    if session["resource_id"] != resource_id or session["domain"] != domain:
        return TurnStart("stopped", session, bundles, "session belongs to another domain or location")
    if session["status"] == "blocked":
        return TurnStart("stopped", session, bundles, "chat blocked")
    if session["status"] == "closed":
        return TurnStart("stopped", session, bundles, "chat already closed")
    return TurnStart("ready", session, bundles, None)


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)
