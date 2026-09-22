from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.constants import PRO_SLOTS_PER_MARKET
from app.db import get_session
from app.models import Profile
from app.scoring import is_pro_effective

router = APIRouter(prefix="/api/search", tags=["search"])


def _to_result(profile: Profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "avatar_url": profile.avatar_url,
        "category": profile.category,
        "location": profile.location,
        "lifecycle_state": profile.lifecycle_state,
        "is_verified": profile.lifecycle_state in ("claimed", "pro"),
        "is_pro": is_pro_effective(profile),
        "top_5_percent": profile.top_5_percent,
        "business_name": profile.business_name,
        "tags": profile.tags,
        "review_snippet": profile.reviews[0]["body"] if profile.reviews else None,
        "avg_rating": profile.avg_rating,
        "review_count": profile.review_count,
        "search_rank_score": profile.search_rank_score,
    }


@router.get("")
def search(
    category: str | None = None,
    location: str | None = None,
    service: str | None = None,
    min_rating: float = 0,
    min_score: int = 0,
    sort: str = "score",
    session: Session = Depends(get_session),
):
    profiles = list(session.exec(select(Profile)))

    if category:
        profiles = [p for p in profiles if p.category == category]
    if location:
        profiles = [p for p in profiles if p.location == location]
    if service:
        profiles = [p for p in profiles if service in p.tags]
    if min_rating:
        profiles = [p for p in profiles if p.avg_rating >= min_rating]
    if min_score:
        profiles = [p for p in profiles if p.search_rank_score >= min_score]

    if sort == "rating":
        profiles.sort(key=lambda p: p.avg_rating, reverse=True)
    else:
        profiles.sort(key=lambda p: p.search_rank_score, reverse=True)

    results = [_to_result(p) for p in profiles]
    return {"count": len(results), "results": results}


@router.get("/filters")
def search_filters(session: Session = Depends(get_session)):
    profiles = list(session.exec(select(Profile)))
    categories = sorted({p.category for p in profiles})
    locations = sorted({p.location for p in profiles})
    services = sorted({tag for p in profiles for tag in p.tags})
    return {
        "categories": categories,
        "locations": locations,
        "services": services,
        "pro_slots_per_market": PRO_SLOTS_PER_MARKET,
    }
