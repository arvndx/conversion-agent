"""Retention: the job that deletes old rows. Each window is counted from the row's updated_at (no expires_at column).

  conv_activity, conv_session        20 days (a visit, and its chat, go together)
  conv_visitor                       1 year, consented and anonymous rows alike
  conv_handover                      1 year
  conv_log, conv_change_log          1 year
  conv_question                      30 days (an answered question keeps its answer for 30 days)
  conv_reply_feedback, conv_daily    no expiry for now
"""

from datetime import datetime, timedelta, timezone

WINDOWS = [
    ("conv_session", "20 days", "session_id"),
    ("conv_activity", "20 days", "activity_id"),
    ("conv_hot_visitor", "1 year", None),
    ("conv_visitor", "1 year", None),
    ("conv_handover", "1 year", None),
    ("conv_log", "1 year", None),
    ("conv_change_log", "1 year", None),
    ("conv_question", "30 days", "question_id"),
]
ORDER = ["conv_session", "conv_activity", "conv_hot_visitor", "conv_visitor", "conv_handover", "conv_log",
         "conv_change_log", "conv_question"]


def run_cleanup(conn, now: datetime | None = None) -> dict[str, int]:
    """Delete the rows past their window. Returns the number deleted per table. The caller commits."""
    now = now or datetime.now(timezone.utc)
    removed = {}
    for table in ORDER:
        window = next(w for t, w, _ in WINDOWS if t == table)
        days = 365 if window.endswith("year") else int(window.split()[0])
        cutoff = now - timedelta(days=days)
        removed[table] = conn.execute(f"DELETE FROM {table} WHERE updated_at < %s", (cutoff,)).rowcount
    return removed
