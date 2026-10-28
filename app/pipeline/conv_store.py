"""Where the chat writes its sessions, visitors and leads: the conversion agent's own tables (conv_*, db/agent_schema.sql).

The worker calls these with its open cursor. A site is found from its customer id and its domain (conv_site.resource_id, conv_site.domain). The visitor
id comes from the browser and is stored only where the visitor consented (the worker passes None otherwise).
"""

import json
import uuid
from datetime import timedelta

from psycopg.types.json import Jsonb

from pipeline.reasons import lead_reason



def site_id_for(cur, resource_id: str, domain: str) -> uuid.UUID | None:
    cur.execute("select site_id from conv_site where resource_id = %s and domain = %s", (resource_id, domain))
    row = cur.fetchone()
    return row[0] if row else None


VISIT_IDLE_MINUTES = 30
TOPIC_DAYS = 90


def write_session(cur, site_id, row: dict) -> bool:
    """Insert or update the chat. Returns True when the chat was inserted in this write. The first topic is kept."""
    cur.execute(
        """
        insert into conv_session (session_id, site_id, visitor_id, activity_id, domain, started_at, ended_at,
            last_activity_at, have_consent, location_city, location_country, status, messages, summary, topic,
            widget_seconds, abuse_strikes, session_score, metric_date, expires_at)
        values (%(session_id)s, %(site_id)s, %(visitor_id)s, %(activity_id)s, %(domain)s, %(started_at)s, %(ended_at)s,
            %(last_activity_at)s, %(have_consent)s, %(city)s, %(country)s, %(status)s, %(messages)s::jsonb,
            %(summary)s, %(topic)s, %(widget_seconds)s, %(abuse_strikes)s, %(session_score)s, %(metric_date)s,
            now() + interval '20 days')
        on conflict (session_id) do update set
            status = excluded.status, ended_at = excluded.ended_at, last_activity_at = excluded.last_activity_at,
            widget_seconds = excluded.widget_seconds, messages = excluded.messages, summary = excluded.summary,
            topic = coalesce(conv_session.topic, excluded.topic),
            activity_id = coalesce(conv_session.activity_id, excluded.activity_id),
            abuse_strikes = excluded.abuse_strikes, session_score = excluded.session_score,
            expires_at = now() + interval '20 days'
        returning (xmax = 0) as inserted
        """,
        {
            "session_id": row["session_id"], "site_id": site_id, "visitor_id": row["visitor_id"],
            "activity_id": row.get("activity_id"), "domain": row["domain"], "started_at": row["started_at"],
            "ended_at": row["ended_at"], "last_activity_at": row["last_activity_at"],
            "have_consent": row["have_consent"], "city": row["city"], "country": row["country"],
            "status": row["status"], "messages": row["conversation"], "summary": row["summary"],
            "topic": row.get("topic"), "widget_seconds": row["widget_seconds"],
            "abuse_strikes": row["abuse_strikes"], "session_score": row["session_score"],
            "metric_date": row["metric_date"],
        },
    )
    return bool(cur.fetchone()[0])


def write_activity(cur, site_id, row: dict) -> bool:
    """The visit a chat belongs to. Created on the first write; later writes move its last activity forward.
    False when the visit id belongs to another site (the chat is then written without a visit)."""
    cur.execute(
        """
        insert into conv_activity (activity_id, site_id, visitor_id, domain, started_at, last_activity_at, have_consent,
            location_city, location_country, expires_at)
        values (%(activity_id)s, %(site_id)s, %(visitor_id)s, %(domain)s, %(started_at)s, %(last_activity_at)s,
            %(have_consent)s, %(city)s, %(country)s, now() + interval '20 days')
        on conflict (activity_id) do update set
            last_activity_at = greatest(conv_activity.last_activity_at, excluded.last_activity_at),
            visitor_id = coalesce(conv_activity.visitor_id, excluded.visitor_id),
            have_consent = conv_activity.have_consent or excluded.have_consent,
            expires_at = now() + interval '20 days'
        where conv_activity.site_id = excluded.site_id
        returning activity_id
        """,
        {
            "activity_id": row["activity_id"], "site_id": site_id, "visitor_id": row["visitor_id"],
            "domain": row["domain"], "started_at": row["started_at"], "last_activity_at": row["last_activity_at"],
            "have_consent": row["have_consent"], "city": row["city"], "country": row["country"],
        },
    )
    return cur.fetchone() is not None


def count_topic(cur, site_id, session_id, topic: str, day) -> bool:
    """Add the chat's topic to its site's count for the chat's day. Once per chat. Keeps the last TOPIC_DAYS days.
    Returns True when the count changed."""
    cur.execute(
        "update conv_session set topic_counted_at = now() "
        "where session_id = %s and topic_counted_at is null returning 1",
        (session_id,),
    )
    if cur.fetchone() is None:
        return False
    cur.execute("select topic_counts from conv_site where site_id = %s for update", (site_id,))
    counts = cur.fetchone()[0] or {}
    per_day = counts.setdefault(day.isoformat(), {})
    per_day[topic] = per_day.get(topic, 0) + 1
    oldest = (day - timedelta(days=TOPIC_DAYS - 1)).isoformat()
    counts = {d: c for d, c in counts.items() if d >= oldest}
    cur.execute("update conv_site set topic_counts = %s where site_id = %s", (Jsonb(counts), site_id))
    return True


def end_idle_visits(cur, now) -> tuple[list, list]:
    """Close the visits with no activity for VISIT_IDLE_MINUTES. Returns the closed visit ids, and the chats in them
    that are still open in the table (the caller closes them in Redis)."""
    cur.execute(
        "update conv_activity set status = 'completed', ended_at = last_activity_at "
        "where status = 'open' and last_activity_at < %s returning activity_id",
        (now - timedelta(minutes=VISIT_IDLE_MINUTES),),
    )
    visits = [row[0] for row in cur.fetchall()]
    if not visits:
        return [], []
    cur.execute("select session_id from conv_session where activity_id = any(%s)", (visits,))   # closing a closed chat does nothing
    return visits, [str(row[0]) for row in cur.fetchall()]


def write_visitor(cur, site_id, visitor_id, *, new_visit: bool, city, country, notice_version, started_at, last_seen) -> None:
    cur.execute(
        """
        insert into conv_visitor (site_id, visitor_id, visits, location_city, location_country, consent_notice_version,
            first_seen_at, last_seen_at)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (site_id, visitor_id) do update set
            visits = conv_visitor.visits + excluded.visits,
            location_city = coalesce(excluded.location_city, conv_visitor.location_city),
            location_country = coalesce(excluded.location_country, conv_visitor.location_country),
            last_seen_at = greatest(conv_visitor.last_seen_at, excluded.last_seen_at),
            expires_at = now() + interval '1 year'
        """,
        (site_id, visitor_id, 1 if new_visit else 0, city, country, notice_version, started_at, last_seen),
    )


def refresh_visitor_totals(cur, site_id, visitor_id) -> None:
    """The visitor's totals, added up from all of their chats (as the old tables did)."""
    cur.execute(
        """
        update conv_visitor set
            widget_seconds = (select coalesce(sum(widget_seconds), 0) from conv_session
                              where site_id = %(site)s and visitor_id = %(visitor)s),
            abuse_strikes = (select coalesce(sum(abuse_strikes), 0) from conv_session
                             where site_id = %(site)s and visitor_id = %(visitor)s)
        where site_id = %(site)s and visitor_id = %(visitor)s
        """,
        {"site": site_id, "visitor": visitor_id},
    )


def write_lead(cur, lead_id: str, site_id, session_id: str, visitor_id, payload: dict, reason_text: str) -> bool:
    """One handover: the visitor's details and why they were passed on. Returns True when it was new."""
    cur.execute(
        """
        insert into conv_lead (lead_id, site_id, session_id, visitor_id, kind, name, email, phone, reason, question)
        values (%s, %s, %s, %s, 'lead', %s, %s, %s, %s, %s)
        on conflict (lead_id) do nothing
        returning lead_id
        """,
        (lead_id, site_id, session_id, visitor_id, payload["name"], payload.get("email"), payload.get("phone"),
         lead_reason(reason_text), payload.get("question")),
    )
    return cur.fetchone() is not None


def set_lead_notification(cur, lead_id: str, status: str, sent_at: str | None) -> None:
    cur.execute(
        """
        update conv_lead set notifications = jsonb_build_object('business_email',
            jsonb_build_object('status', cast(%s as text), 'sent_at', cast(%s as text)))
        where lead_id = cast(%s as uuid)
        """,
        (status, sent_at, lead_id),
    )
