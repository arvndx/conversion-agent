"""Claiming a profile (core1.txt, Process 1).

Option 1 - from the search page: the card shows the stored name, email, phone, vertical, category and
services. The agent may edit the name and EITHER the phone OR the email (not both), picks the category
and services, and presses Claim now. Option 2 - "Claim a profile" for someone not in the database: all
six values are entered. Either way a 6-digit code goes to that person's mock mailbox; entering it on our
page claims the profile.

Nothing is written to the profile until the code is verified: the card's values wait in
`Claim.payload`.
"""

import re
from datetime import datetime

from fastapi import HTTPException, Response
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import create_otp, check_otp, normalize_email, start_session
from app.constants import CLAIMED_STATES
from app.mail import otp_email_html, send_mock_email
from app.models import Category, CategoryService, Claim, Profile, Vertical
from app.scoring import recompute_and_save_score

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
MIN_PHONE_DIGITS = 10


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _clean(value) -> str:
    return (value or "").strip() if isinstance(value, str) else ""


def mailbox_path(email: str) -> str:
    return f"/mailbox/{normalize_email(email)}"


def _validated_card(session: Session, data: dict) -> dict:
    """Check the six mandatory values and the vertical -> category -> services cascade."""
    name, email, phone = _clean(data.get("name")), normalize_email(data.get("email")), _clean(data.get("phone_number"))
    problems = []
    if not name:
        problems.append("Full name is required.")
    if not EMAIL_RE.match(email):
        problems.append("Enter a valid email address.")
    if len(_digits(phone)) < MIN_PHONE_DIGITS:
        problems.append("Enter a valid phone number (at least 10 digits).")

    category = session.get(Category, data.get("category_id")) if data.get("category_id") else None
    vertical = session.exec(select(Vertical).where(Vertical.key == data.get("vertical"))).first() if data.get("vertical") else None
    if vertical is None:
        problems.append("Choose a vertical.")
    if category is None or not category.is_active:
        problems.append("Choose a category.")
    elif vertical is not None and category.vertical_id != vertical.id:
        problems.append("That category does not belong to the chosen vertical.")

    services = [s for s in (data.get("services") or []) if isinstance(s, str)]
    if category is not None:
        valid = {s.key for s in session.exec(select(CategoryService).where(CategoryService.category_id == category.id)).all()}
        if not services:
            problems.append("Choose at least one service.")
        elif not set(services) <= valid:
            problems.append("One of the services does not belong to that category.")
    if problems:
        raise HTTPException(status_code=400, detail=" ".join(problems))

    return {
        "name": name, "email": email, "phone_number": phone, "vertical": vertical.key,
        "category_id": category.id, "services": list(dict.fromkeys(services)),
    }


def start_claim(session: Session, data: dict) -> dict:
    profile_id = data.get("profile_id")
    card = _validated_card(session, data)
    email = card["email"]

    profile = None
    if profile_id:
        profile = session.get(Profile, profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if profile.lifecycle_state in CLAIMED_STATES:
            raise HTTPException(status_code=409, detail={"code": "already_claimed", "message": "This profile is already claimed. Sign in instead."})

        # Edit rule: the name is free; of phone and email, at most one may differ from what we hold.
        email_changed = bool(profile.email) and email != normalize_email(profile.email)
        phone_changed = bool(_digits(profile.phone_number)) and _digits(card["phone_number"]) != _digits(profile.phone_number)
        if email_changed and phone_changed:
            raise HTTPException(status_code=400, detail="You can change your phone number or your email, not both.")
        method = "search_card"
    else:
        duplicate = session.exec(select(Profile).where(func.lower(Profile.email) == email)).first()
        if duplicate is not None:
            code = "already_claimed" if duplicate.lifecycle_state in CLAIMED_STATES else "profile_exists"
            message = (
                "An account with this email is already claimed. Sign in instead."
                if code == "already_claimed"
                else "We already have a profile with this email. Claim it from the search page."
            )
            raise HTTPException(status_code=409, detail={"code": code, "message": message, "profile_id": duplicate.id})
        method = "new_profile"

    # One claimed profile per email, so signing in by email is unambiguous.
    taken = session.exec(select(Profile).where(func.lower(Profile.email) == email)).all()
    if any(p.lifecycle_state in CLAIMED_STATES and p.id != profile_id for p in taken):
        raise HTTPException(status_code=409, detail={"code": "already_claimed", "message": "That email already belongs to a claimed profile. Sign in instead."})

    claim = Claim(profile_id=profile.id if profile else None, method=method, email=email, phone=card["phone_number"], payload=card)
    session.add(claim)
    session.commit()
    session.refresh(claim)

    code = create_otp(session, email, "claim", profile_id=claim.profile_id, claim_id=claim.id)
    send_mock_email(
        session, to_email=email, subject="Your ClearRank verification code",
        html=otp_email_html(card["name"], code, "claim"), profile_id=claim.profile_id,
    )
    return {"claim_id": claim.id, "method": method, "email": email, "mailbox_url": mailbox_path(email)}


def verify_claim(session: Session, response: Response, claim_id: int, code: str) -> dict:
    claim = session.get(Claim, claim_id)
    if claim is None or claim.status != "pending":
        raise HTTPException(status_code=404, detail="This claim is not waiting for a code. Start again.")
    check_otp(session, claim.email, "claim", code, claim_id=claim.id)

    card = claim.payload
    category = session.get(Category, card["category_id"])
    vertical = session.exec(select(Vertical).where(Vertical.key == card["vertical"])).one()

    if claim.method == "new_profile":
        # core1 collects six values for a new profile; there is no location yet. Onboarding fills it in
        # from the scraped primary address.
        profile = Profile(name=card["name"], email=card["email"], category=category.name, location="")
    else:
        profile = session.get(Profile, claim.profile_id)
        if profile.lifecycle_state in CLAIMED_STATES:
            raise HTTPException(status_code=409, detail="This profile was claimed in the meantime.")

    profile.name = card["name"]
    profile.email = card["email"]
    profile.phone_number = card["phone_number"]
    profile.vertical = vertical.name
    profile.category = category.name
    profile.category_id = category.id
    profile.services = card["services"]
    profile.lifecycle_state = "claimed"
    profile.claimed_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)

    claim.profile_id = profile.id
    claim.status = "verified"
    claim.verified_at = datetime.utcnow()
    claim.evidence = {"method": "email_otp", "email": card["email"]}
    session.add(claim)
    session.commit()

    recompute_and_save_score(session, profile)
    start_session(session, response, profile, card["email"])
    return {"profile_id": profile.id, "name": profile.name, "next": f"/onboarding/{profile.id}"}
