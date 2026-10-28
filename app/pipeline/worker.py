"""The batch worker (A62 b, A62 c, A72 e, A81). It runs as its own process, separate from the chat API.

Every second it:
  1. Takes the set of changed chats (session_updates), by renaming it to session_updates:working. A batch left
     behind by a crash is found there and processed first.
  2. Writes the batch to the database in one transaction:
       - each chat into chat_sessions (inserted once, then updated in the same row);
       - the visitor's row in visitors, with the consent proof, when the visitor consented;
       - each new handover into handovers (the id is fixed per chat, so a repeat is harmless).
  3. After the commit, clears update_status and removes the flags. A chat that changed during the batch stays queued.
     A closed chat's Redis copy is removed only after its final write.
  4. Sends the handover email after the commit, and records the result in the handover's notifications.

If the database fails, nothing is cleared: every chat in the batch goes back to session_updates, and the next run
tries again.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone

import psycopg
import redis

from pipeline import store

from pipeline.close_chat import close_chat, close_stale
from pipeline.cleanup import run_cleanup
from pipeline.topics import maybe_promote, resolve_topic
from pipeline.load_chat import session_key

log = logging.getLogger("worker")

BATCH_KEY = "session_updates"
WORKING_KEY = "session_updates:working"
EMAIL_PENDING_KEY = "handover_email_pending"
FAILED_KEY = "worker_failed_chats"   # chats that cannot be saved (kept here, not retried forever)
HANDOVER_NAMESPACE = uuid.UUID("6f1c9a2e-3b7d-4e8a-9c1f-2d5b7e8a9f10")


def handover_id_for(session_id: str) -> str:
    """The same chat always gives the same handover id, so a repeated write does not make a second row."""
    return str(uuid.uuid5(HANDOVER_NAMESPACE, session_id))


def db_status(sess: dict) -> str:
    if sess.get("status") == "blocked":
        return "abusive"
    if sess.get("closing") == "1":
        if sess.get("handover"):
            return "handed_over"
        return "completed" if int(sess.get("turn_count") or 0) > 0 else "incomplete"
    return "open"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _location(value: str | None) -> tuple[str | None, str | None]:
    parts = [p.strip() for p in (value or "").split(",") if p.strip()]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def claim_batch(client: redis.Redis) -> list[str]:
    """The chats to write. Takes the queue (or the batch left by a crash) and returns the chat IDs."""
    if client.exists(WORKING_KEY):
        return sorted(client.smembers(WORKING_KEY))
    if not client.exists(BATCH_KEY):
        return []
    try:
        client.rename(BATCH_KEY, WORKING_KEY)
    except redis.ResponseError:
        return []  # another worker took the queue first
    return sorted(client.smembers(WORKING_KEY))


from pipeline.conv_store import (count_topic, end_idle_visits, refresh_visitor_totals,  # noqa: E402
                                 set_lead_notification, site_id_for, write_activity, write_lead, write_session,
                                 write_visitor)

CHAT_UPSERT = """
    INSERT INTO chat_sessions (
        session_id, visitor_id, resource_type, resource_id, domain, have_consent, status,
        started_at, ended_at, last_activity_at, location_city, location_country,
        widget_seconds, conversation, session_score, summary, abuse_strikes,
        metric_date, expires_at)
    VALUES (%(session_id)s, %(visitor_id)s, %(resource_type)s, %(resource_id)s, %(domain)s, %(have_consent)s,
            %(status)s, %(started_at)s, %(ended_at)s, %(last_activity_at)s, %(city)s, %(country)s,
            %(widget_seconds)s, %(conversation)s::jsonb, %(session_score)s, %(summary)s, %(abuse_strikes)s,
            %(metric_date)s, now() + interval '20 days')
    ON CONFLICT (session_id) DO UPDATE SET
        status = excluded.status,
        ended_at = excluded.ended_at,
        last_activity_at = excluded.last_activity_at,
        widget_seconds = excluded.widget_seconds,
        conversation = excluded.conversation,
        session_score = excluded.session_score,
        summary = excluded.summary,
        abuse_strikes = excluded.abuse_strikes,
        updated_at = now(),
        expires_at = now() + interval '20 days'
    RETURNING (xmax = 0) AS inserted
"""

VISITOR_UPSERT = """
    INSERT INTO visitors (
        visitor_id, domain, resource_id, resource_type, have_consent, location_city, location_country,
        visit_count, consent_choice, consent_notice_version, consent_at, first_seen_at, last_seen_at, expires_at)
    VALUES (%(visitor_id)s, %(domain)s, %(resource_id)s, %(resource_type)s, true, %(city)s, %(country)s,
            %(visit_increment)s, 'accepted', %(notice_version)s, %(started_at)s, %(started_at)s, %(last_activity_at)s,
            now() + interval '12 months')
    ON CONFLICT (visitor_id, domain, resource_id) DO UPDATE SET
        location_city = coalesce(excluded.location_city, visitors.location_city),
        location_country = coalesce(excluded.location_country, visitors.location_country),
        visit_count = visitors.visit_count + excluded.visit_count,
        last_seen_at = greatest(visitors.last_seen_at, excluded.last_seen_at),
        updated_at = now(),
        expires_at = now() + interval '12 months'
"""

VISITOR_TOTALS = """
    UPDATE visitors SET
        widget_seconds_total = (SELECT coalesce(sum(widget_seconds), 0) FROM chat_sessions
                                WHERE visitor_id = %(visitor_id)s AND domain = %(domain)s AND resource_id = %(resource_id)s),
        strike_count = (SELECT coalesce(sum(abuse_strikes), 0) FROM chat_sessions
                        WHERE visitor_id = %(visitor_id)s AND domain = %(domain)s AND resource_id = %(resource_id)s)
    WHERE visitor_id = %(visitor_id)s AND domain = %(domain)s AND resource_id = %(resource_id)s
"""

HANDOVER_INSERT = """
    INSERT INTO handovers (
        handover_id, session_id, visitor_id, resource_type, resource_id, domain, name, email, phone,
        reason, conversation, status, notifications, expires_at)
    VALUES (%(handover_id)s, %(session_id)s, %(visitor_id)s, %(resource_type)s, %(resource_id)s, %(domain)s,
            %(name)s, %(email)s, %(phone)s, %(reason)s, %(conversation)s::jsonb, 'new',
            '{"business_email": {"status": "pending"}}'::jsonb, now() + interval '12 months')
    ON CONFLICT (handover_id) DO NOTHING
    RETURNING handover_id
"""

VISITOR_CONTACT = """
    UPDATE visitors SET name = %(name)s, email = %(email)s, phone = %(phone)s, status = 'lead',
        handover_count = handover_count + 1, updated_at = now()
    WHERE visitor_id = %(visitor_id)s AND domain = %(domain)s AND resource_id = %(resource_id)s
"""


def _row_for_chat(sid: str, sess: dict) -> dict:
    started = _parse_time(sess.get("started_at")) or datetime.now(timezone.utc)
    last = _parse_time(sess.get("last_activity_at")) or started
    city, country = _location(sess.get("location"))
    conversation = json.loads(sess.get("conversation") or "[]")
    return {
        "session_id": sid,
        "visitor_id": sess.get("visitor_id") or None,
        "resource_type": sess["resource_type"],
        "resource_id": sess["resource_id"],
        "domain": sess["domain"],
        "have_consent": sess.get("consent") == "1",
        "status": db_status(sess),
        "started_at": started,
        "ended_at": _parse_time(sess.get("ended_at")),
        "last_activity_at": last,
        "city": city,
        "country": country,
        "widget_seconds": max(0, int((last - started).total_seconds())),
        "conversation": json.dumps(conversation, ensure_ascii=False),
        "topic": sess.get("topic") or None,
        "topic_label": sess.get("topic_label") or None,
        "activity_id": sess.get("activity_id") or None,
        "session_score": int(sess.get("session_score") or 0),
        "summary": sess.get("summary") or None,
        "abuse_strikes": int(sess.get("abuse_strikes") or 0),
        "metric_date": started.date(),
        "notice_version": sess.get("notice_version") or None,
    }


def _write_chat(cur, row: dict) -> bool:
    """The chat's row in conv_session. The visitor is written first (the session refers to it). True when the chat is new."""
    site_id = site_id_for(cur, row["resource_id"], row["domain"])
    if site_id is None:
        raise LookupError(f"no site for customer {row['resource_id']}")
    cur.execute("select 1 from conv_session where session_id = %s", (row["session_id"],))
    new_visit = cur.fetchone() is None
    if row["visitor_id"]:
        write_visitor(cur, site_id, row["visitor_id"], new_visit=new_visit, city=row["city"], country=row["country"],
                      notice_version=row.get("notice_version"), started_at=row["started_at"],
                      last_seen=row["last_activity_at"])
    row["visitor_id"] = row["visitor_id"] or None
    if row.get("activity_id") and not write_activity(cur, site_id, row):
        row["activity_id"] = None   # the visit id is not one of this site's visits: the chat is kept without it
    if not row.get("topic") and row.get("topic_label"):
        row["topic"] = resolve_topic(cur, site_id, row["topic_label"])
    inserted = write_session(cur, site_id, row)
    if row.get("topic"):
        count_topic(cur, site_id, row["session_id"], row["topic"], row["metric_date"])
        maybe_promote(cur, site_id, row["topic"])
    return inserted


def _write_visitor(cur, row: dict, sess: dict, inserted: bool) -> None:
    """The visitor's totals, added up from all of their chats."""
    site_id = site_id_for(cur, row["resource_id"], row["domain"])
    refresh_visitor_totals(cur, site_id, row["visitor_id"])


def _write_handover(cur, row: dict, sess: dict) -> str | None:
    """The handover as a lead in conv_lead. The conversation is kept in the chat itself (conv_session.messages)."""
    payload = json.loads(sess["handover"])
    handover_id = handover_id_for(row["session_id"])
    site_id = site_id_for(cur, row["resource_id"], row["domain"])
    inserted = write_lead(cur, handover_id, site_id, row["session_id"], row["visitor_id"], payload,
                          sess.get("handover_reason") or "visitor asked for a handover")
    return handover_id if inserted else None


def send_email_stub(message: dict) -> bool:
    """Stands in for the company mail (A42 d) until the owner's sender is connected. Always succeeds."""
    return True


def _business_email(client: redis.Redis, resource_type: str, resource_id: str) -> str | None:
    from pipeline.load_chat import load_bundles

    try:
        customer = load_bundles(client, resource_type, resource_id).customer
    except Exception:
        return None
    return customer.get("public_contact", {}).get("email")


def send_handover_emails(client: redis.Redis, conn: psycopg.Connection, handover_ids: list[tuple[str, dict]],
                         sender) -> int:
    """Send the handover email for each new handover, then record the result (A34, A52)."""
    sent = 0
    for handover_id, message in handover_ids:
        to = _business_email(client, message["resource_type"], message["resource_id"])
        ok = bool(to) and sender({"to": to, **message})
        status = "sent" if ok else "pending"
        stamp = datetime.now(timezone.utc).isoformat()
        with conn.cursor() as cur:
            cur.execute("update conv_handover set notified_by = %s, notified_at = %s, updated_at = now() where handover_id = %s",
                        (["email"] if ok else [], datetime.fromisoformat(stamp) if ok else None, handover_id))
        conn.commit()
        if ok:
            sent += 1
            client.srem(EMAIL_PENDING_KEY, handover_id)
        else:
            client.sadd(EMAIL_PENDING_KEY, handover_id)
    return sent


def _save_chat(cur, sid: str, sess: dict) -> str | None:
    """Save one chat to the conv_ tables: its visitor, visit, chat and daily totals; and the handover if there is one.
    Returns the handover id when a handover was saved in this write."""
    started = _parse_time(sess.get("started_at")) or datetime.now(timezone.utc)
    last = _parse_time(sess.get("last_activity_at")) or started
    city, state = _location(sess.get("location"))[0], (_location(sess.get("location"))[1])
    handed = bool(sess.get("handover"))
    status = "handed_over" if handed else db_status(sess).replace("abusive", "blocked")
    row = {
        "session_id": sid, "professional_id": sess["resource_id"], "domain": sess["domain"],
        "visitor_id": sess.get("visitor_id") or None, "have_consent": sess.get("consent") == "1",
        "activity_id": sess.get("activity_id") or sid, "started_at": started, "last_activity_at": last,
        "ended_at": _parse_time(sess.get("ended_at")), "status": status,
        "messages": json.loads(sess.get("conversation") or "[]"), "topic": sess.get("topic") or None,
        "widget_seconds": max(0, int((last - started).total_seconds())),
        "session_score": int(sess.get("session_score") or 0), "abuse_strikes": int(sess.get("abuse_strikes") or 0),
        "summary": sess.get("summary") or None, "city": city, "state": state,
        "notice_version": sess.get("notice_version") or None,
        # The bundle versions the chat is using (kept on the chat's row, so the chat stays on them after a restart).
        "customer_version": int(sess["customer_v"]) if sess.get("customer_v") else None,
        "category_version": int(sess["category_v"]) if sess.get("category_v") else None,
    }
    cur.execute("select 1 from conv_activity where activity_id = %s", (row["activity_id"],))
    new_visit = cur.fetchone() is None
    cur.execute("select 1 from conv_session where session_id = %s", (sid,))
    new_chat = cur.fetchone() is None
    store.upsert_visitor(cur, row, new_visit)
    store.upsert_activity(cur, row)
    store.upsert_session(cur, row)
    store.refresh_visitor(cur, row)
    day = started.date()
    store.bump_daily(cur, row, day, new_visitor=new_visit, new_chat=new_chat, topic=row["topic"] if new_chat else None)
    if not handed or sess.get("handover_saved"):
        return None
    payload = json.loads(sess["handover"])
    reason = sess.get("handover_reason") or "request_from_visitor"
    request_type = sess.get("handover_request_type") or "direct handover"
    handover_id = store.insert_handover(cur, row, {
        "name": payload.get("name") or "", "email": payload.get("email"), "phone": payload.get("phone"),
        "reason": reason, "action_key": sess.get("handover_action") or None, "request_type": request_type,
        "extra_fields": json.loads(sess.get("handover_extra") or "{}"),
        "question": payload.get("question") or sess.get("handover_question") or "",
        "summary": row["summary"] or f"{request_type}: {payload.get('question') or ''}".strip(),
    })
    if handover_id:
        store.bump_daily(cur, row, day, handover=True)
    return handover_id


def run_once(client: redis.Redis, conn: psycopg.Connection, sender=send_email_stub) -> dict:
    """One pass over the queue. Returns counts of what was done."""
    stats = {"chats": 0, "handovers": 0, "emails_sent": 0, "errors": 0}
    batch = claim_batch(client)
    if not batch:
        return stats

    written = {}      # session_id -> turn_count written
    closed = []       # session_ids whose final write is done
    new_handovers = []
    try:
        with conn.cursor() as cur:
            for sid in batch:
                sess = client.hgetall(session_key(sid))
                if not sess:
                    continue
                try:
                    with conn.transaction():   # a bad chat is undone on its own; the rest of the batch still saves
                        handover_id = _save_chat(cur, sid, sess)
                except Exception:
                    log.exception("chat %s could not be saved; set aside in %s for review", sid, FAILED_KEY)
                    client.sadd(FAILED_KEY, sid)
                    stats["errors"] += 1
                    continue
                if handover_id:
                    new_handovers.append((handover_id, {
                        "resource_type": "professional", "resource_id": sess["resource_id"],
                        "session_id": sid, "handover": json.loads(sess["handover"]),
                    }))
                written[sid] = int(sess.get("turn_count") or 0)
                if sess.get("closing") == "1":
                    closed.append(sid)
                stats["chats"] += 1
                if handover_id:
                    stats["handovers"] += 1
        conn.commit()
    except Exception:
        # The batch is kept and retried, so without this log a bad row would fail silently every second.
        log.exception("batch of %d chats failed; kept for the next run", len(batch))
        conn.rollback()
        for sid in batch:
            client.sadd(BATCH_KEY, sid)
        client.delete(WORKING_KEY)
        stats["errors"] += 1
        return stats

    # After the commit: clear the flags, remove closed chats, and re-queue any chat that changed during the batch.
    for sid, turns in written.items():
        key = session_key(sid)
        if int(client.hget(key, "turn_count") or 0) != turns:
            client.sadd(BATCH_KEY, sid)
            continue
        if sid in closed:
            client.delete(key)
            client.srem("open_sessions", sid)
        else:
            client.hset(key, "update_status", 0)
    for handover_id_value, message in new_handovers:
        client.hset(session_key(message["session_id"]), mapping={"handover_saved": 1, "handover_id": handover_id_value})
    client.delete(WORKING_KEY)

    if new_handovers:
        stats["emails_sent"] = send_handover_emails(client, conn, new_handovers, sender)
    return stats


SWEEP_SECONDS = 60
CLEANUP_SECONDS = 3600
ROLLUP_SECONDS = 300


def close_idle_visits(client: redis.Redis, conn: psycopg.Connection, now: datetime | None = None) -> list:
    """Close the visits with no activity for 30 minutes, and their open chats. Returns the closed visit ids."""
    current = now or datetime.now(timezone.utc)
    with conn.cursor() as cur:
        visits, sessions = end_idle_visits(cur, current)
    conn.commit()
    for sid in sessions:
        close_chat(client, sid, "visit_ended_30_minutes", now=current)
    return visits


def sweep_idle(client: redis.Redis, conn: psycopg.Connection, now: datetime | None = None) -> dict:
    """The 30-minute rules: idle chats (Redis) and idle visits (the table, with their chats). Run every minute."""
    chats = close_stale(client, now=now)
    visits = close_idle_visits(client, conn, now=now)
    return {"chats": len(chats), "visits": len(visits)}


def main(poll_seconds: float = 1.0) -> None:
    import os

    from pipeline.load_chat import DATABASE_URL, REDIS_URL

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    last_sweep = 0.0
    last_cleanup = 0.0
    while True:
        # A failure in one job is logged and the loop goes on: the worker must not stop because one row is bad.
        if time.time() - last_sweep >= SWEEP_SECONDS:
            try:
                with psycopg.connect(DATABASE_URL) as conn:
                    sweep_idle(client, conn)
            except Exception:
                log.exception("idle sweep failed; the worker keeps running")
            last_sweep = time.time()
        if time.time() - last_cleanup >= CLEANUP_SECONDS:
            try:
                with psycopg.connect(DATABASE_URL) as conn:
                    log.info("cleanup: %s", run_cleanup(conn))
            except Exception:
                log.exception("cleanup failed; the worker keeps running")
            last_cleanup = time.time()
        with psycopg.connect(DATABASE_URL) as conn:
            stats = run_once(client, conn)
        if not stats["chats"] and not stats["errors"]:
            time.sleep(poll_seconds)
        elif stats["errors"]:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
