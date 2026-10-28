"""Where the chat saves its results, in the conv_ tables (db/conv_schema.sql).

One chat is one row in conv_session, inside one visit (conv_activity), by one visitor (conv_visitor). The visitor row is per
professional, domain and visitor id. Without consent there is no stored id, so the visit id stands in for the visitor id
(each visit is then its own visitor, as agreed).

The functions take an open cursor, so the caller decides the transaction.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone

from psycopg.types.json import Jsonb

HOT_WINDOW_HOURS = 72
VISIT_IDLE_MINUTES = 30
CHAT_STATUSES = ("open", "completed", "incomplete", "handed_over", "blocked")
UNANSWERED = ("unavailable_answer", "unsure_question", "critical_question")


def visitor_key(sess: dict) -> str:
    """The visitor id for a chat: the browser's id when the visitor consented, else the visit id (one visit = one visitor)."""
    return sess.get("visitor_id") or sess["activity_id"]


def upsert_visitor(cur, sess: dict, new_visit: bool) -> None:
    cur.execute(
        """insert into conv_visitor (professional_id, domain, visitor_id, have_consent, consent_choice, consent_at,
            consent_notice_version, first_seen_at, last_seen_at, visits, city, state)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (professional_id, domain, visitor_id) do update set
            last_seen_at = greatest(conv_visitor.last_seen_at, excluded.last_seen_at),
            visits = conv_visitor.visits + excluded.visits,
            city = coalesce(excluded.city, conv_visitor.city),
            state = coalesce(excluded.state, conv_visitor.state),
            updated_at = now()""",
        (sess["professional_id"], sess["domain"], visitor_key(sess), bool(sess.get("have_consent")),
         "accepted" if sess.get("have_consent") else None, sess["started_at"] if sess.get("have_consent") else None,
         sess.get("notice_version"), sess["started_at"], sess["last_activity_at"], 1 if new_visit else 0,
         sess.get("city"), sess.get("state")))


def upsert_activity(cur, sess: dict) -> bool:
    """The visit. True when it was created by this write."""
    status = sess.get("status") or "open"
    cur.execute(
        """insert into conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status, started_at,
            last_activity_at, ended_at, city, state, time_in_widget_seconds, summary, session_score, abuse_strikes)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (activity_id) do update set
            status = excluded.status, last_activity_at = greatest(conv_activity.last_activity_at, excluded.last_activity_at),
            ended_at = coalesce(excluded.ended_at, conv_activity.ended_at),
            time_in_widget_seconds = excluded.time_in_widget_seconds, summary = excluded.summary,
            session_score = excluded.session_score, abuse_strikes = excluded.abuse_strikes,
            city = coalesce(excluded.city, conv_activity.city), state = coalesce(excluded.state, conv_activity.state),
            updated_at = now()
        returning (xmax = 0)""",
        (sess["activity_id"], sess["professional_id"], sess["domain"], visitor_key(sess), bool(sess.get("have_consent")),
         status, sess["started_at"], sess["last_activity_at"], sess.get("ended_at"), sess.get("city"), sess.get("state"),
         int(sess.get("widget_seconds") or 0), sess.get("summary"), int(sess.get("session_score") or 0),
         int(sess.get("abuse_strikes") or 0)))
    return bool(cur.fetchone()[0])


def upsert_session(cur, sess: dict) -> bool:
    """The chat inside the visit. True when it was created. The first topic is kept."""
    cur.execute(
        """insert into conv_session (session_id, activity_id, messages, topic, customer_version, category_version)
        values (%s, %s, %s::jsonb, %s, %s, %s)
        on conflict (session_id) do update set messages = excluded.messages,
            topic = coalesce(conv_session.topic, excluded.topic),
            customer_version = coalesce(conv_session.customer_version, excluded.customer_version),
            category_version = coalesce(conv_session.category_version, excluded.category_version), updated_at = now()
        returning (xmax = 0)""",
        (sess["session_id"], sess["activity_id"], json.dumps(sess.get("messages") or [], ensure_ascii=False), sess.get("topic"),
         sess.get("customer_version"), sess.get("category_version")))
    return bool(cur.fetchone()[0])


def refresh_visitor(cur, sess: dict) -> None:
    """Totals and the visit summary list for the visitor, added up from all their visits in this domain."""
    cur.execute(
        """update conv_visitor set
            widget_seconds_total = (select coalesce(sum(time_in_widget_seconds), 0) from conv_activity
                where professional_id = %(p)s and domain = %(d)s and visitor_id = %(v)s),
            page_seconds_total = (select coalesce(sum(time_on_site_seconds), 0) from conv_activity
                where professional_id = %(p)s and domain = %(d)s and visitor_id = %(v)s),
            score_72h = (select coalesce(sum(session_score), 0) from conv_activity
                where professional_id = %(p)s and domain = %(d)s and visitor_id = %(v)s
                and last_activity_at > now() - interval '72 hours'),
            abuse_strikes = (select coalesce(sum(abuse_strikes), 0) from conv_activity
                where professional_id = %(p)s and domain = %(d)s and visitor_id = %(v)s),
            visit_summaries = (select coalesce(jsonb_agg(jsonb_build_object('at', started_at, 'activity_id', activity_id,
                'domain', domain, 'summary', coalesce(summary, '')) order by started_at), '[]'::jsonb)
                from conv_activity where professional_id = %(p)s and domain = %(d)s and visitor_id = %(v)s),
            updated_at = now()
        where professional_id = %(p)s and domain = %(d)s and visitor_id = %(v)s""",
        {"p": sess["professional_id"], "d": sess["domain"], "v": visitor_key(sess)})


def insert_handover(cur, sess: dict, handover: dict) -> str | None:
    """A request the visitor sent: the details they gave. One per chat and action (the id comes from both), so sending the
    same request twice makes one row and a chat can send requests for different actions."""
    action = handover.get("action_key")
    handover_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"handover:{sess['session_id']}" + (f":{action}" if action else "")))
    cur.execute(
        """insert into conv_handover (handover_id, professional_id, domain, session_id, visitor_id, name, email, phone,
            reason, action_key, request_type, question, summary, extra_fields, city, state, status, notified_by)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new', '{}')
        on conflict (handover_id) do nothing returning handover_id""",
        (handover_id, sess["professional_id"], sess["domain"], sess["session_id"], visitor_key(sess),
         handover["name"], handover.get("email"), handover.get("phone"), handover["reason"], action,
         handover.get("request_type") or "direct handover", handover["question"], handover.get("summary"),
         Jsonb(handover.get("extra_fields") or {}), sess.get("city"), sess.get("state")))
    row = cur.fetchone()
    return handover_id if row else None


def record_question(cur, sess: dict, question: str, topic: str | None, answered: bool) -> None:
    """Count a question the bot could not answer (or could), per domain. Keyed by the normalised text."""
    text = " ".join(question.lower().split())[:300]
    cur.execute(
        """insert into conv_question (question_id, professional_id, domain, question_text, topic, asked_count,
            first_asked_at, last_asked_at, answered)
        values (%s, %s, %s, %s, %s, 1, now(), now(), %s)
        on conflict (professional_id, domain, question_text) do update set
            asked_count = conv_question.asked_count + 1, last_asked_at = now(),
            topic = coalesce(conv_question.topic, excluded.topic), updated_at = now()""",
        (str(uuid.uuid4()), sess["professional_id"], sess["domain"], text, topic, answered))


def bump_daily(cur, sess: dict, day: date, *, new_visitor: bool = False, new_chat: bool = False,
               handover: bool = False, booking: bool = False, answered: int = 0, unanswered: int = 0,
               topic: str | None = None) -> None:
    """Daily totals per professional and domain. The topic counts are kept in the same row (topic_counts)."""
    topic_patch = {topic: 1} if topic else {}
    cur.execute(
        """insert into conv_daily (professional_id, domain, day, visitors, chats, handovers, bookings,
            questions_answered, questions_unanswered, topic_counts)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (professional_id, domain, day) do update set
            visitors = conv_daily.visitors + excluded.visitors, chats = conv_daily.chats + excluded.chats,
            handovers = conv_daily.handovers + excluded.handovers, bookings = conv_daily.bookings + excluded.bookings,
            questions_answered = conv_daily.questions_answered + excluded.questions_answered,
            questions_unanswered = conv_daily.questions_unanswered + excluded.questions_unanswered,
            topic_counts = (select coalesce(jsonb_object_agg(k, coalesce((conv_daily.topic_counts->>k)::int, 0)
                + coalesce((excluded.topic_counts->>k)::int, 0)), '{}'::jsonb)
                from (select jsonb_object_keys(conv_daily.topic_counts || excluded.topic_counts) k) keys),
            updated_at = now()""",
        (sess["professional_id"], sess["domain"], day, 1 if new_visitor else 0, 1 if new_chat else 0,
         1 if handover else 0, 1 if booking else 0, answered, unanswered, Jsonb(topic_patch)))


def close_idle_visits(cur, now: datetime) -> list[str]:
    """Close visits with no activity for VISIT_IDLE_MINUTES: set ended_at. A chat still open in the visit is completed."""
    cur.execute(
        """update conv_activity set ended_at = last_activity_at,
            status = case when status = 'open' then 'completed' else status end, updated_at = now()
        where ended_at is null and last_activity_at < %s returning activity_id""",
        (now - timedelta(minutes=VISIT_IDLE_MINUTES),))
    return [str(r[0]) for r in cur.fetchall()]
