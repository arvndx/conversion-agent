"""The UI's side of onboarding: reading the state and recording the user's own decisions (yes/no on a
URL, a typed URL, an identity answer, a conflict resolution, typed fields, completion).

Scraping and merging are deliberately NOT here: the onboarding agent triggers those through its tools,
so the agent stays in charge of the flow while these routes only record what the user chose.
"""

from fastapi import APIRouter, Body, Depends
from sqlmodel import Session

from app import onboarding
from app.auth import require_owner
from app.db import get_session
from app.models import Profile

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/{profile_id}")
def get_state(profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    """Safe to poll: the UI watches this while the agent is reading pages."""
    return onboarding.state(session, profile)


@router.post("/{profile_id}/start")
def start(profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    onboarding.start(session, profile)
    return onboarding.state(session, profile)


@router.post("/{profile_id}/sources")
def add_url(body: dict = Body(...), profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    """A URL the user typed in (with a label from the dropdown)."""
    onboarding.add_manual(session, profile, body.get("url"), body.get("label"))
    return onboarding.state(session, profile)


@router.put("/{profile_id}/links/{platform}")
def set_link(platform: str, body: dict = Body(...), profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    """The owner's LinkedIn / Instagram / X address: saved and counted, never read."""
    onboarding.set_link(session, profile, platform, body.get("url"))
    return onboarding.state(session, profile)


@router.post("/{profile_id}/sources/{source_id}/decision")
def decide(source_id: int, body: dict = Body(...), profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    onboarding.decide(session, profile, source_id, body.get("decision"), body.get("label"))
    return onboarding.state(session, profile)


@router.post("/{profile_id}/sources/skip")
def skip_urls(profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    onboarding.skip_remaining_urls(session, profile)
    return onboarding.state(session, profile)


@router.post("/{profile_id}/read")
def read(profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    """Start reading the pages the owner confirmed (in the background; the page watches each one finish). Only
    confirmed pages are taken, whoever asks, so this is the same step the agent's tool performs."""
    onboarding.start_scrape(session, profile)
    return onboarding.state(session, profile)


@router.post("/{profile_id}/sources/{source_id}/identity")
def identity(source_id: int, body: dict = Body(...), profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    onboarding.confirm_identity(session, profile, source_id, bool(body.get("is_mine")))
    return onboarding.state(session, profile)


@router.post("/{profile_id}/conflicts/{conflict_id}/resolve")
def resolve(conflict_id: int, body: dict = Body(...), profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    onboarding.resolve(session, profile, conflict_id, body)
    return onboarding.state(session, profile)


@router.patch("/{profile_id}/fields")
def update_fields(body: dict = Body(...), profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    onboarding.update_fields(session, profile, body)
    return onboarding.state(session, profile)


@router.post("/{profile_id}/complete")
def complete(profile: Profile = Depends(require_owner), session: Session = Depends(get_session)):
    return onboarding.complete(session, profile)
