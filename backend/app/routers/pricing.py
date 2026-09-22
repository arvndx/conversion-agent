from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models import Profile
from app.pricing import MONTHLY_PRICE_USD, get_active_offer, record_pricing_page_visit
from app.scoring import compute_total_score
from app.slots import get_slot_status, simulate_rank

router = APIRouter(prefix="/api/profiles", tags=["pricing"])


def _get_claimed_or_404(session: Session, profile_id: int) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.lifecycle_state == "unclaimed":
        raise HTTPException(status_code=400, detail="Profile is not claimed")
    return profile


@router.get("/{profile_id}/pricing")
def get_pricing(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_claimed_or_404(session, profile_id)
    score = compute_total_score(profile)
    unlock_points = score["unlock_points"]

    rank_preview = None
    if unlock_points > 0:
        current_rank = simulate_rank(session, profile, score["total"])
        new_rank = simulate_rank(session, profile, score["total"] + unlock_points)
        rank_preview = {
            "rank_from": current_rank["rank_position"],
            "rank_to": new_rank["rank_position"],
            "rank_total": new_rank["rank_total"],
        }

    return {
        "monthly_price_usd": MONTHLY_PRICE_USD,
        "offer": get_active_offer(profile),
        "unlock_points": unlock_points,
        "categories": score["categories"],
        "rank_preview": rank_preview,
        "slot_status": get_slot_status(session, profile),
        "category": profile.category,
        "location": profile.location,
        "is_pro": profile.lifecycle_state == "pro",
    }


@router.post("/{profile_id}/track-pricing-visit")
def track_pricing_visit(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_claimed_or_404(session, profile_id)
    return record_pricing_page_visit(session, profile)
