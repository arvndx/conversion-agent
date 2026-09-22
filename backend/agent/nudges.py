"""Deterministic, templated (never LLM-generated) outreach — the numbers-bearing
kind of email should never risk hallucination. This is the manual "tick" for
every time-based demo mechanic, mirroring app/routers/admin.py's reset-demo
pattern since this project deliberately has no Celery/cron.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.models import MockEmail, Profile, ProSlotWaitlist
from app.scoring import COMPLETION_FIELDS, compute_total_score, recompute_and_save_score, simulate_total_score

COMPLETION_FIELD_LABELS = {
    "phone_number": "your phone number",
    "license_number": "your license number",
    "website_url": "your website",
    "bio": "your bio",
}
SENTINEL_VALUES = {
    "phone_number": "(555) 555-0100",
    "license_number": "PENDING-000000",
    "website_url": "https://example.com",
    "bio": "placeholder bio for simulation only",
}


def compute_best_nudge(profile: Profile) -> dict | None:
    """The single empty completion field that would gain the most real points if
    filled in, computed via the same simulate_total_score used by the live
    what-if tool — never a guess.
    """
    current_total = profile.search_rank_score
    best = None
    for field in COMPLETION_FIELDS:
        if getattr(profile, field):
            continue
        hypothetical = simulate_total_score(profile, {field: SENTINEL_VALUES[field]})
        delta = hypothetical["total"] - current_total
        if delta > 0 and (best is None or delta > best["delta"]):
            best = {"field": field, "label": COMPLETION_FIELD_LABELS[field], "delta": delta}
    return best


def send_nudge_emails(session: Session, profile_id: int | None = None, force: bool = False) -> list[int]:
    query = select(Profile).where(Profile.lifecycle_state == "claimed")
    if profile_id is not None:
        query = query.where(Profile.id == profile_id)

    sent_ids = []
    for profile in session.exec(query).all():
        if not force and profile.last_nudge_sent_at is not None:
            continue
        nudge = compute_best_nudge(profile)
        if nudge is None:
            continue

        current = profile.search_rank_score
        projected = current + nudge["delta"]
        session.add(
            MockEmail(
                to_email=profile.email,
                subject=f"Add {nudge['label']} to raise your Search Rank Score by {nudge['delta']} points",
                body_html=(
                    f"<p>Hi {profile.name},</p>"
                    f"<p>Adding {nudge['label']} would raise your Search Rank Score from "
                    f"{current} to {projected} — a real, computed gain of {nudge['delta']} points.</p>"
                ),
                profile_id=profile.id,
            )
        )
        profile.last_nudge_sent_at = datetime.utcnow()
        session.add(profile)
        sent_ids.append(profile.id)

    session.commit()
    return sent_ids


def process_waitlist(session: Session, category: str, location: str) -> list[int]:
    """Notify every un-notified waitlist entry for a market that just gained a
    free slot, first-come-first-served (whoever upgrades first wins — enforced
    naturally by the same capacity check every upgrade already goes through).
    """
    entries = session.exec(
        select(ProSlotWaitlist).where(
            ProSlotWaitlist.category == category,
            ProSlotWaitlist.location == location,
            ProSlotWaitlist.notified_at.is_(None),
        )
    ).all()

    notified_profile_ids = []
    for entry in entries:
        profile = session.get(Profile, entry.profile_id)
        if profile is None:
            continue
        session.add(
            MockEmail(
                to_email=profile.email,
                subject=f"A Pro spot just opened up for {category} in {location}",
                body_html=(
                    f"<p>Hi {profile.name},</p>"
                    f"<p>A Pro spot just opened up in your market. It's first-come, first-served — "
                    f"upgrade now before another business takes it.</p>"
                ),
                profile_id=profile.id,
            )
        )
        entry.notified_at = datetime.utcnow()
        session.add(entry)
        notified_profile_ids.append(profile.id)

    session.commit()
    return notified_profile_ids


def send_trial_expiry_emails(session: Session) -> list[int]:
    """For profiles whose trial has lapsed without converting to real Pro: email
    them the real point loss, clear the trial (which — via is_pro_effective —
    is what actually frees their market slot), and notify that market's waitlist.
    Detection is lazy (no cron): this scans on every manual tick.
    """
    now = datetime.utcnow()
    lapsed = session.exec(
        select(Profile).where(Profile.lifecycle_state == "claimed", Profile.trial_ends_at.is_not(None))
    ).all()
    lapsed = [p for p in lapsed if p.trial_ends_at < now]

    expired_ids = []
    markets_to_process = set()
    for profile in lapsed:
        # compute_total_score already treats this profile as non-Pro (trial_ends_at
        # is in the past), so unlock_points is exactly "what just got re-locked."
        score = compute_total_score(profile)
        lost_points = score["unlock_points"]

        session.add(
            MockEmail(
                to_email=profile.email,
                subject=f"Your Pro trial ended — you lost {lost_points} points",
                body_html=(
                    f"<p>Hi {profile.name},</p>"
                    f"<p>Your free Pro trial ended and your Search Rank Score dropped to "
                    f"{score['total']}/{score['max_possible']} — a real loss of {lost_points} points from "
                    f"Website Health and Listings. Upgrade now to get them back.</p>"
                ),
                profile_id=profile.id,
            )
        )
        profile.trial_ends_at = None
        recompute_and_save_score(session, profile)
        expired_ids.append(profile.id)
        markets_to_process.add((profile.category, profile.location))

    for category, location in markets_to_process:
        process_waitlist(session, category, location)

    return expired_ids


def run_nudges(session: Session, profile_id: int | None = None, force: bool = False) -> dict:
    return {
        "nudge_emails_sent_to": send_nudge_emails(session, profile_id=profile_id, force=force),
        "trial_expirations_processed": send_trial_expiry_emails(session),
    }
