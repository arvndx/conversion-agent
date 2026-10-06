from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlmodel import Session, select

from app.constants import CLAIMED_STATES, PRO_SLOTS_PER_MARKET
from app.db import get_session
from app.models import CategoryService, Profile
from app.scoring import is_pro_effective
from app.seed_taxonomy import _slug as service_key

router = APIRouter(prefix="/api/search", tags=["search"])

DEFAULT_LIMIT = 100


def _like(value: str) -> str:
    """A contains-pattern with the user's own % and _ made literal."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _to_result(profile: Profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "avatar_url": profile.avatar_url,
        "category": profile.category,
        "vertical": profile.vertical,
        "location": profile.location,
        "lifecycle_state": profile.lifecycle_state,
        "is_verified": profile.lifecycle_state in CLAIMED_STATES,
        "can_claim": profile.lifecycle_state == "unclaimed",
        "is_pro": is_pro_effective(profile),
        "top_5_percent": profile.top_5_percent,
        "business_name": profile.business_name,
        "title": profile.title,
        "tags": profile.tags,
        "services": profile.services,
        "review_snippet": profile.reviews[0].get("body") if profile.reviews else None,
        "avg_rating": profile.avg_rating,
        "review_count": profile.review_count,
        "search_rank_score": profile.search_rank_score,
    }


@router.get("")
def search(
    keyword: str | None = None,
    category: str | None = None,
    location: str | None = None,
    service: str | None = None,
    min_rating: float = 0,
    min_score: int = 0,
    sort: str = "score",
    limit: int = DEFAULT_LIMIT,
    session: Session = Depends(get_session),
):
    """Filtering happens in SQL. `keyword` matches the person's name, company, title, city or category; `location` is a
    contains-match so "Austin" finds "Austin, TX"."""
    query = select(Profile)
    if keyword and keyword.strip():
        pattern = _like(keyword.strip())
        query = query.where(
            or_(
                Profile.name.ilike(pattern, escape="\\"),
                Profile.business_name.ilike(pattern, escape="\\"),
                Profile.title.ilike(pattern, escape="\\"),
                Profile.location.ilike(pattern, escape="\\"),  # one search box: a city or a category works too
                Profile.category.ilike(pattern, escape="\\"),
            )
        )
    if category:
        query = query.where(Profile.category == category)
    if location and location.strip():
        query = query.where(Profile.location.ilike(_like(location.strip()), escape="\\"))
    if service:
        # A service name from the taxonomy (profiles hold its key), or a legacy tag.
        query = query.where(or_(Profile.services.contains([service_key(service)]), Profile.tags.contains([service])))
    if min_rating:
        query = query.where(Profile.avg_rating >= min_rating)
    if min_score:
        query = query.where(Profile.search_rank_score >= min_score)

    order = Profile.avg_rating.desc() if sort == "rating" else Profile.search_rank_score.desc()
    total = len(session.exec(query).all())
    profiles = session.exec(query.order_by(order, Profile.id).limit(max(1, min(limit, 500)))).all()
    return {"count": total, "results": [_to_result(p) for p in profiles]}


@router.get("/filters")
def search_filters(session: Session = Depends(get_session)):
    # session.exec on a single-column select yields the values themselves, not 1-tuples
    categories = sorted(session.exec(select(Profile.category).distinct()).all())
    locations = sorted(l for l in session.exec(select(Profile.location).distinct()).all() if l)
    services = sorted({s.name for s in session.exec(select(CategoryService)).all()})
    return {
        "categories": categories,
        "locations": locations,
        "services": services,
        "pro_slots_per_market": PRO_SLOTS_PER_MARKET,
    }
