from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import require_access
from app.category_config import config_for
from app.constants import CLAIMED_STATES, CONNECTION_PLATFORMS, DIRECTORY_PLATFORMS
from app.db import get_session
from app.models import Profile
from app.scoring import compute_onboarding_checklist, compute_score_delta, compute_total_score, is_pro_effective

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_access)])


def _reviews_status(cat, profile):
    if not profile.reviews:
        return "No recent reviews to reply"
    unreplied = sum(1 for r in profile.reviews if not r.get("reply"))
    return f"{unreplied} unreplied review(s)" if unreplied else "All reviews replied"


def _profile_completion_status(cat, profile):
    return f"{len(cat['opportunities'])} incomplete items"


def _connections_status(cat, profile):
    total = len(config_for(profile).slots("social")) or len(CONNECTION_PLATFORMS)
    connected = total - len(cat["opportunities"])
    return f"{connected} of {total} connections"


def _web_analytics_status(cat, profile):
    if not profile.website_url:
        return "No website added yet"
    passed = 5 - len(cat["opportunities"])
    return f"{passed} of 5 health checks passing"


def _listings_status(cat, profile):
    total = len(config_for(profile).slots("directory")) or len(DIRECTORY_PLATFORMS)
    published = total - len(cat["opportunities"])
    return f"{published} of {total} platforms published"


STATUS_LINE_BUILDERS = {
    "reviews": _reviews_status,
    "profile_completion": _profile_completion_status,
    "connections": _connections_status,
    "web_analytics": _web_analytics_status,
    "listings": _listings_status,
}

UPSELL_COPY = {
    "web_analytics": "Boost Your Search Rank by up to {points} points — See Your Website Health Report",
    "listings": "Earn {points} More Search Rank Points — Manage 50+ Profiles for Search, Social, Voice & Map",
}
DEFAULT_UPSELL_COPY = "Unlock {label}: earn up to {points} more Search Rank points"


def build_dashboard_summary(profile: Profile, session: Session) -> dict:
    score = compute_total_score(profile)
    checklist = compute_onboarding_checklist(profile)

    peers = list(
        session.exec(
            select(Profile).where(
                Profile.category == profile.category, Profile.location == profile.location
            )
        )
    )
    peers.sort(key=lambda p: p.search_rank_score, reverse=True)
    rank_position = next((i + 1 for i, p in enumerate(peers) if p.id == profile.id), len(peers))

    category_cards = []
    for key in score["section_order"]:
        cat = score["categories"][key]
        if cat["locked"]:
            continue  # shown instead as an upsell_card below until Pro unlocks it
        builder = STATUS_LINE_BUILDERS[key]
        category_cards.append(
            {
                "key": key,
                "label": cat["label"],
                "status_line": builder(cat, profile),
                "progress_pct": round((cat["earned"] / cat["max"]) * 100) if cat["max"] else 0,
                "earned": cat["earned"],
                "max": cat["max"],
            }
        )

    upsell_cards = []
    for key in score["section_order"]:
        cat = score["categories"][key]
        if cat["locked"]:
            copy = UPSELL_COPY.get(key, DEFAULT_UPSELL_COPY).format(points=cat["max"], label=cat["label"])
            upsell_cards.append({"key": key, "label": cat["label"], "points": cat["max"], "copy": copy})

    return {
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "avatar_url": profile.avatar_url,
            "is_verified": profile.lifecycle_state in CLAIMED_STATES,
            "category": profile.category,
            "location": profile.location,
            "is_pro": is_pro_effective(profile),
            "lifecycle_state": profile.lifecycle_state,
            "trial_ends_at": profile.trial_ends_at,
            "rank_position": rank_position,
            "rank_total": len(peers),
            "score_delta_last_week": compute_score_delta(session, profile.id, score["total"], days=7),
        },
        "score": score,
        "onboarding": {
            "completed": sum(1 for item in checklist if item["done"]),
            "total": len(checklist),
            "items": checklist,
        },
        "ai_writing_studio": {
            "authority_score": profile.authority_score,
            "articles_count": profile.articles_count,
            "answers_count": profile.answers_count,
        },
        "category_cards": category_cards,
        "upsell_cards": upsell_cards,
    }


@router.get("/{profile_id}")
def get_dashboard(profile_id: int, session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.lifecycle_state == "unclaimed":
        raise HTTPException(status_code=400, detail="Profile is not claimed")
    return build_dashboard_summary(profile, session)
