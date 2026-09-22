import secrets
from datetime import datetime, timedelta

from sqlmodel import Session

from app.models import Profile

MONTHLY_PRICE_USD = 49

# (min_visits, discount_percent), checked highest-first. Capped at 8% — never
# exceed this, enforced here rather than just in a prompt.
DISCOUNT_TIERS = [(5, 8), (3, 5)]
DISCOUNT_WINDOW_HOURS = 48


def compute_discount_percent(visits: int) -> int | None:
    for min_visits, percent in DISCOUNT_TIERS:
        if visits >= min_visits:
            return percent
    return None


def get_active_offer(profile: Profile) -> dict:
    is_active = bool(
        profile.active_discount_percent
        and profile.discount_expires_at
        and profile.discount_expires_at > datetime.utcnow()
    )
    if not is_active:
        return {"active": False}
    return {
        "active": True,
        "percent": profile.active_discount_percent,
        "code": profile.discount_code,
        "expires_at": profile.discount_expires_at.isoformat(),
    }


def record_pricing_page_visit(session: Session, profile: Profile) -> dict:
    now = datetime.utcnow()
    profile.pricing_page_visits += 1
    profile.last_pricing_page_visit_at = now

    new_tier = compute_discount_percent(profile.pricing_page_visits)
    currently_active = get_active_offer(profile)["active"]
    if new_tier and (new_tier != profile.active_discount_percent or not currently_active):
        profile.active_discount_percent = new_tier
        profile.discount_code = f"SAVE{new_tier}-{secrets.token_hex(3).upper()}"
        profile.discount_expires_at = now + timedelta(hours=DISCOUNT_WINDOW_HOURS)

    session.add(profile)
    session.commit()
    session.refresh(profile)

    return {
        "visits": profile.pricing_page_visits,
        "monthly_price_usd": MONTHLY_PRICE_USD,
        "offer": get_active_offer(profile),
    }
