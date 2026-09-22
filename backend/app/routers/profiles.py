import secrets

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import MockEmail, Profile
from app.scoring import is_pro_effective, recompute_and_save_score

CLAIM_DETAIL_FIELDS = [
    "name",
    "phone_number",
    "location",
    "business_timing",
    "awards",
    "title",
    "bio",
    "service_area",
    "email",
    "website_url",
    "license_number",
    "products_services",
    "specialities",
    "memberships",
    "year_started",
    "achievements",
    "hobbies",
]

router = APIRouter(prefix="/api", tags=["profiles"])


def _get_or_404(session: Session, profile_id: int) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def _to_public_detail(profile: Profile) -> dict:
    is_claimed_or_pro = profile.lifecycle_state in ("claimed", "pro")
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
        "otp_verified": profile.otp_verified,
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


@router.post("/profiles/{profile_id}/claim")
def claim_profile(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_or_404(session, profile_id)
    if profile.lifecycle_state != "unclaimed":
        raise HTTPException(status_code=400, detail="Profile is already claimed")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    profile.pending_otp = otp
    profile.otp_verified = False
    session.add(profile)

    email = MockEmail(
        to_email=profile.email,
        subject="Verify your email to claim your ClearRank profile",
        body_html=(
            f"<p>Hi {profile.name},</p>"
            f"<p>Your profile on ClearRank is getting views but isn't ranking yet. "
            f"Enter the verification code below to claim it and start managing your Search Rank Score.</p>"
            f"<p style='font-size:24px;font-weight:700;letter-spacing:4px;'>{otp}</p>"
        ),
        profile_id=profile.id,
    )
    session.add(email)
    session.commit()
    session.refresh(email)
    return {"mock_email_id": email.id}


@router.post("/profiles/{profile_id}/verify-otp")
def verify_otp(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = _get_or_404(session, profile_id)
    if profile.lifecycle_state != "unclaimed":
        raise HTTPException(status_code=400, detail="Profile is already claimed")
    if not profile.pending_otp or body.get("otp") != profile.pending_otp:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    profile.pending_otp = None
    profile.otp_verified = True
    session.add(profile)
    session.commit()
    return {"id": profile.id, "otp_verified": True}


@router.post("/profiles/{profile_id}/claim-details")
def submit_claim_details(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = _get_or_404(session, profile_id)
    if profile.lifecycle_state != "unclaimed":
        raise HTTPException(status_code=400, detail="Profile is already claimed")
    if not profile.otp_verified:
        raise HTTPException(status_code=400, detail="Verify your email before completing your profile")
    if not (body.get("email") or "").strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not (body.get("phone_number") or "").strip():
        raise HTTPException(status_code=400, detail="Phone number is required")

    for field in CLAIM_DETAIL_FIELDS:
        value = body.get(field)
        if value:
            setattr(profile, field, value)

    profile.lifecycle_state = "claimed"
    profile.otp_verified = False
    recompute_and_save_score(session, profile)
    return _to_public_detail(profile)
