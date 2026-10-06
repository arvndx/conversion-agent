from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select

from app.constants import CLAIMED_STATES
from app.db import get_session
from app.models import Profile
from app.scoring import is_pro_effective

router = APIRouter(prefix="/api", tags=["profiles"])


def _get_or_404(session: Session, profile_id: int) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def _to_public_detail(profile: Profile) -> dict:
    is_claimed_or_pro = profile.lifecycle_state in CLAIMED_STATES
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "avatar_url": profile.avatar_url,
        "category": profile.category,
        "location": profile.location,
        "lifecycle_state": profile.lifecycle_state,
        "is_pro": is_pro_effective(profile),
        "is_claimed_or_pro": is_claimed_or_pro,
        "top_5_percent": profile.top_5_percent,
        "business_name": profile.business_name,
        "address": profile.address,
        "business_hours": profile.business_hours,
        "phone_number": profile.phone_number,
        "bio": profile.bio,
        "title": profile.title,
        "service_area": profile.service_area,
        "business_timing": profile.business_timing,
        "awards": profile.awards,
        "license_number": profile.license_number,
        "products_services": profile.products_services,
        "specialities": profile.specialities,
        "memberships": profile.memberships,
        "year_started": profile.year_started,
        "achievements": profile.achievements,
        "hobbies": profile.hobbies,
        "tags": profile.tags,
        "reviews": profile.reviews,
        "avg_rating": profile.avg_rating,
        "review_count": profile.review_count,
        "search_rank_score": profile.search_rank_score,
        "vertical": profile.vertical,
        "category_id": profile.category_id,
        "services": profile.services,
    }


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_or_404(session, profile_id)
    profile.view_count += 1
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return _to_public_detail(profile)


@router.get("/profiles/{profile_id}/related")
def get_related(profile_id: int, sort: str = "rating", limit: int = 5, session: Session = Depends(get_session)):
    profile = _get_or_404(session, profile_id)
    others = [p for p in session.exec(select(Profile)) if p.id != profile.id]

    if sort == "views":
        others.sort(key=lambda p: p.view_count, reverse=True)
    else:
        others.sort(key=lambda p: p.avg_rating, reverse=True)

    return [
        {
            "id": p.id,
            "name": p.name,
            "avatar_url": p.avatar_url,
            "category": p.category,
            "avg_rating": p.avg_rating,
            "review_count": p.review_count,
        }
        for p in others[:limit]
    ]
