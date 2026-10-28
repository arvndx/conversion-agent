"""Visit activity from the widget, written to conv_activity: clicks, widget opens, and time on the page and in the widget.

A visit starts with its first event. It ends after 30 minutes with no activity (the worker closes it). An event for a
visit that has ended is refused with "ended", so the widget starts a new visit. A visit id that belongs to another
site is "refused". Only counts are stored: no page addresses and no text of what was clicked.
"""

from datetime import datetime, timedelta, timezone

VISIT_IDLE = timedelta(minutes=30)
MAX_EVENTS = 50
MAX_SECONDS = 24 * 3600


def _seconds(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return min(max(number, 0), MAX_SECONDS)


def record_activity(conn, professional_id: str, domain: str, activity_id: str, events: list[dict],
                    now: datetime | None = None, visitor_id: str | None = None, have_consent: bool = False) -> str:
    """Add the events to the visit. Returns "ok", "ended" or "refused". The caller commits."""
    from pipeline import store

    now = now or datetime.now(timezone.utc)
    pages = clicks = opens = visible = widget = 0
    for event in events[:MAX_EVENTS]:
        kind = event.get("type")
        if kind == "page_view":
            pages += 1
        elif kind == "click":
            clicks += 1
        elif kind == "widget_open":
            opens += 1
        elif kind == "heartbeat":
            # The widget sends the time so far, not a change, so the largest value seen is kept.
            visible = max(visible, _seconds(event.get("visible_seconds")))
            widget = max(widget, _seconds(event.get("widget_seconds")))

    row = conn.execute("SELECT professional_id, domain, status, last_activity_at FROM conv_activity WHERE activity_id = %s",
                       (activity_id,)).fetchone()
    if row is None:
        sess = {"professional_id": professional_id, "domain": domain, "visitor_id": visitor_id,
                "have_consent": have_consent, "activity_id": activity_id, "started_at": now, "last_activity_at": now}
        with conn.cursor() as cur:
            store.upsert_visitor(cur, sess, new_visit=True)
        conn.execute("""INSERT INTO conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status,
            started_at, last_activity_at) VALUES (%s, %s, %s, %s, %s, 'open', %s, %s) ON CONFLICT (activity_id) DO NOTHING""",
                     (activity_id, professional_id, domain, visitor_id or activity_id, have_consent, now, now))
        row = conn.execute("SELECT professional_id, domain, status, last_activity_at FROM conv_activity WHERE activity_id = %s",
                           (activity_id,)).fetchone()
    visit_pro, visit_domain, status, last = row
    if str(visit_pro) != str(professional_id) or visit_domain != domain:
        return "refused"
    if status != "open" or now - last > VISIT_IDLE:
        return "ended"
    conn.execute(
        """UPDATE conv_activity SET last_activity_at = %s, updated_at = now(),
            clicks = coalesce(clicks, 0) + %s, widget_opens = coalesce(widget_opens, 0) + %s,
            time_on_site_seconds = greatest(coalesce(time_on_site_seconds, 0), %s),
            time_in_widget_seconds = greatest(coalesce(time_in_widget_seconds, 0), %s)
        WHERE activity_id = %s""",
        (now, clicks, opens, visible, widget, activity_id))
    return "ok"
