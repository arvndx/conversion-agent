import copy
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select

from app.constants import PRO_SLOTS_PER_MARKET
from app.db import get_session
from app.models import MarketEvent, Profile, ProSlotWaitlist
from app.routers.dashboard import build_dashboard_summary
from app.scoring import compute_total_score, is_pro_effective, recompute_and_save_score
from app.slots import count_pro_slot_holders, get_slot_status, has_open_slot
from app.suggestions import build_suggestions

TRIAL_DURATION_DAYS = 7

router = APIRouter(prefix="/api/profiles", tags=["manage"])

EDITABLE_FIELDS = [
    "phone_number",
    "license_number",
    "website_url",
    "bio",
    "business_name",
    "address",
    "business_hours",
    "tags",
    "title",
    "service_area",
    "business_timing",
    "awards",
    "products_services",
    "specialities",
    "memberships",
    "year_started",
    "achievements",
    "hobbies",
]


def _get_manageable_or_404(session: Session, profile_id: int) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.lifecycle_state == "unclaimed":
        raise HTTPException(status_code=400, detail="Profile is not claimed")
    return profile



def _manage_payload(session: Session, profile: Profile) -> dict:
    return {
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "lifecycle_state": profile.lifecycle_state,
            "is_pro": is_pro_effective(profile),
            "phone_number": profile.phone_number,
            "license_number": profile.license_number,
            "website_url": profile.website_url,
            "bio": profile.bio,
            "title": profile.title,
            "service_area": profile.service_area,
            "business_timing": profile.business_timing,
            "awards": profile.awards,
            "products_services": profile.products_services,
            "specialities": profile.specialities,
            "memberships": profile.memberships,
            "year_started": profile.year_started,
            "achievements": profile.achievements,
            "hobbies": profile.hobbies,
            "business_name": profile.business_name,
            "address": profile.address,
            "business_hours": profile.business_hours,
            "connections": profile.connections,
            "directory_listings": profile.directory_listings,
            "website_audit": profile.website_audit,
            "reviews": profile.reviews,
        },
        "score": compute_total_score(profile),
        "slot_status": get_slot_status(session, profile),
        "suggestions": build_suggestions(session, profile),
    }


@router.get("/{profile_id}/manage")
def get_manage(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    return _manage_payload(session, profile)


@router.patch("/{profile_id}")
def update_profile(profile_id: int, updates: dict = Body(...), session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    for field, value in updates.items():
        if field in EDITABLE_FIELDS:
            setattr(profile, field, value)
    recompute_and_save_score(session, profile)
    return _manage_payload(session, profile)


@router.patch("/{profile_id}/connections")
def update_connection(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    platform_name = body["platform_name"]
    is_connected = body["is_connected"]

    connections = copy.deepcopy(profile.connections)
    for entry in connections:
        if entry["platform_name"] == platform_name:
            entry["is_connected"] = is_connected
            break
    else:
        connections.append({"platform_name": platform_name, "is_connected": is_connected})

    profile.connections = connections
    recompute_and_save_score(session, profile)
    return _manage_payload(session, profile)


def perform_reply_to_review(session: Session, profile: Profile, review_id: str, reply: str) -> dict:
    reviews = copy.deepcopy(profile.reviews)
    for entry in reviews:
        if entry.get("id") == review_id:
            entry["reply"] = reply
            break
    else:
        raise HTTPException(status_code=404, detail="Review not found")

    profile.reviews = reviews
    recompute_and_save_score(session, profile)
    return _manage_payload(session, profile)


@router.patch("/{profile_id}/reviews/{review_id}/reply")
def reply_to_review(
    profile_id: int, review_id: str, body: dict = Body(...), session: Session = Depends(get_session)
):
    profile = _get_manageable_or_404(session, profile_id)
    reply = (body.get("reply") or "").strip()
    if not reply:
        raise HTTPException(status_code=400, detail="reply is required")
    return perform_reply_to_review(session, profile, review_id, reply)


@router.patch("/{profile_id}/listings")
def update_listing(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    if not is_pro_effective(profile):
        raise HTTPException(status_code=403, detail="Upgrade to Pro to manage directory listings")

    platform_name = body["platform_name"]
    is_published = body["is_published"]

    listings = copy.deepcopy(profile.directory_listings)
    platforms = listings.get("platforms", [])
    for entry in platforms:
        if entry["name"] == platform_name:
            entry["is_published"] = is_published
            break
    else:
        platforms.append({"name": platform_name, "is_published": is_published})

    listings["platforms"] = platforms
    profile.directory_listings = listings
    recompute_and_save_score(session, profile)
    return _manage_payload(session, profile)


def _market_full_error(session: Session, profile: Profile) -> HTTPException:
    waitlist_count = len(
        session.exec(
            select(ProSlotWaitlist).where(
                ProSlotWaitlist.category == profile.category,
                ProSlotWaitlist.location == profile.location,
                ProSlotWaitlist.notified_at.is_(None),
            )
        ).all()
    )
    return HTTPException(
        status_code=403,
        detail={"error": "market_full", "waitlist_count": waitlist_count},
    )


def _log_market_event(session: Session, profile: Profile, event_type: str) -> None:
    session.add(
        MarketEvent(category=profile.category, location=profile.location, event_type=event_type, profile_id=profile.id)
    )
    session.commit()


def perform_upgrade(session: Session, profile: Profile) -> dict:
    if not has_open_slot(session, profile.category, profile.location):
        raise _market_full_error(session, profile)
    profile.lifecycle_state = "pro"
    profile.trial_ends_at = None
    recompute_and_save_score(session, profile)
    _log_market_event(session, profile, "profile_went_pro")
    return build_dashboard_summary(profile, session)


def perform_start_trial(session: Session, profile: Profile) -> dict:
    if profile.lifecycle_state != "claimed":
        raise HTTPException(status_code=400, detail="Only claimed (non-Pro) profiles can start a trial")
    if not has_open_slot(session, profile.category, profile.location):
        raise _market_full_error(session, profile)
    profile.trial_ends_at = datetime.utcnow() + timedelta(days=TRIAL_DURATION_DAYS)
    recompute_and_save_score(session, profile)
    _log_market_event(session, profile, "trial_started")
    return build_dashboard_summary(profile, session)


@router.post("/{profile_id}/upgrade")
def upgrade_to_pro(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    return perform_upgrade(session, profile)


@router.post("/{profile_id}/start-trial")
def start_trial(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    return perform_start_trial(session, profile)


def perform_join_waitlist(session: Session, profile: Profile) -> dict:
    if has_open_slot(session, profile.category, profile.location):
        raise HTTPException(status_code=400, detail="This market isn't full — you can upgrade directly")

    existing = session.exec(
        select(ProSlotWaitlist).where(
            ProSlotWaitlist.profile_id == profile.id,
            ProSlotWaitlist.category == profile.category,
            ProSlotWaitlist.location == profile.location,
            ProSlotWaitlist.notified_at.is_(None),
        )
    ).first()
    if existing is None:
        session.add(ProSlotWaitlist(profile_id=profile.id, category=profile.category, location=profile.location))
        session.commit()

    waitlist_count = len(
        session.exec(
            select(ProSlotWaitlist).where(
                ProSlotWaitlist.category == profile.category,
                ProSlotWaitlist.location == profile.location,
                ProSlotWaitlist.notified_at.is_(None),
            )
        ).all()
    )
    return {"joined": True, "waitlist_count": waitlist_count}


@router.post("/{profile_id}/waitlist")
def join_waitlist(profile_id: int, session: Session = Depends(get_session)):
    profile = _get_manageable_or_404(session, profile_id)
    return perform_join_waitlist(session, profile)
