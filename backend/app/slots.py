from datetime import datetime

from sqlmodel import Session, select

from app.constants import PRO_SLOTS_PER_MARKET
from app.models import Profile
from app.scoring import is_pro_effective


def count_pro_slot_holders(session: Session, category: str, location: str) -> int:
    profiles = session.exec(
        select(Profile).where(Profile.category == category, Profile.location == location)
    )
    return sum(1 for p in profiles if is_pro_effective(p))


def has_open_slot(session: Session, category: str, location: str) -> bool:
    return count_pro_slot_holders(session, category, location) < PRO_SLOTS_PER_MARKET


def get_slot_status(session: Session, profile: Profile) -> dict:
    """Single shared shape for 'how full is this profile's market' — used by the Manage
    page's sidebar and the Pricing page alike, so the two never show different numbers."""
    taken = count_pro_slot_holders(session, profile.category, profile.location)
    return {
        "taken": taken,
        "total": PRO_SLOTS_PER_MARKET,
        "remaining": max(0, PRO_SLOTS_PER_MARKET - taken),
        "is_full": taken >= PRO_SLOTS_PER_MARKET,
        "is_trial": bool(profile.trial_ends_at and profile.trial_ends_at > datetime.utcnow()),
        "trial_ends_at": profile.trial_ends_at,
    }


def simulate_rank(session: Session, profile: Profile, hypothetical_total: int) -> dict:
    """Where `profile` would rank in its market if its total were `hypothetical_total`
    instead of its real current score — reuses the exact same peer-sort logic
    build_dashboard_summary uses for the real rank_position, just against a
    hypothetical number the caller must have obtained honestly (e.g. via
    simulate_total_score) rather than invented.
    """
    peers = list(
        session.exec(
            select(Profile).where(
                Profile.category == profile.category,
                Profile.location == profile.location,
                Profile.id != profile.id,
            )
        )
    )
    rank_position = 1 + sum(1 for p in peers if p.search_rank_score > hypothetical_total)
    return {"rank_position": rank_position, "rank_total": len(peers) + 1}
