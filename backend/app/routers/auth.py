from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import DEMO_MODE, check_otp, create_otp, current_session, end_session, normalize_email, start_session
from app.claims import EMAIL_RE, mailbox_path
from app.constants import CLAIMED_STATES
from app.db import get_session
from app.mail import otp_email_html, send_mock_email
from app.models import Profile

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _owner_of(session: Session, email: str) -> Profile | None:
    return session.exec(
        select(Profile).where(func.lower(Profile.email) == email, Profile.lifecycle_state.in_(CLAIMED_STATES)).order_by(Profile.id)
    ).first()


@router.get("/config")
def auth_config():
    return {"demo_mode": DEMO_MODE}


@router.get("/me")
def me(request: Request, session: Session = Depends(get_session)):
    current = current_session(request, session)
    if current is None:
        return {"authenticated": False}
    profile = session.get(Profile, current.profile_id)
    return {
        "authenticated": True,
        "profile_id": profile.id,
        "name": profile.name,
        "email": current.email,
        "category": profile.category,
        "category_id": profile.category_id,
        "lifecycle_state": profile.lifecycle_state,
        "onboarding_completed": profile.onboarding_completed_at is not None,
        "demo_mode": DEMO_MODE,
    }


@router.post("/otp/request")
def request_login_otp(body: dict = Body(...), session: Session = Depends(get_session)):
    """Sign in: a code goes to the mailbox of the email that owns a claimed profile. The answer is the
    same whether or not the email matches an account, so it cannot be used to look accounts up."""
    email = normalize_email(body.get("email"))
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    profile = _owner_of(session, email)
    if profile is not None:
        code = create_otp(session, email, "login", profile_id=profile.id)
        send_mock_email(session, to_email=email, subject="Your ClearRank sign-in code",
                        html=otp_email_html(profile.name, code, "login"), profile_id=profile.id)
    return {"sent": True, "mailbox_url": mailbox_path(email)}


@router.post("/otp/verify")
def verify_login_otp(response: Response, body: dict = Body(...), session: Session = Depends(get_session)):
    email = normalize_email(body.get("email"))
    profile = _owner_of(session, email)
    if profile is None:
        raise HTTPException(status_code=400, detail="That code is not right.")  # same message as a wrong code
    check_otp(session, email, "login", str(body.get("code") or ""))
    start_session(session, response, profile, email)
    return {"profile_id": profile.id, "name": profile.name, "onboarding_completed": profile.onboarding_completed_at is not None}


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session)):
    end_session(session, request, response)
    return {"ok": True}


# --- Demo mode only ----------------------------------------------------------------------------------


@router.get("/demo-profiles")
def demo_profiles(session: Session = Depends(get_session)):
    """A short list of ready-made accounts for the 'Viewing as' switcher: one claimed and one Pro (or
    enterprise) profile per category, excluding the synthetic peers' bulk."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    rows = session.exec(select(Profile).where(Profile.lifecycle_state.in_(CLAIMED_STATES)).order_by(Profile.category, Profile.id)).all()
    picked, seen = [], set()
    for p in rows:
        kind = "pro" if p.lifecycle_state in ("pro", "enterprise") else "claimed"
        if (p.category, kind) not in seen:
            seen.add((p.category, kind))
            picked.append({"id": p.id, "name": p.name, "category": p.category, "lifecycle_state": p.lifecycle_state})
    return {"profiles": picked}


@router.post("/demo-login")
def demo_login(response: Response, body: dict = Body(...), session: Session = Depends(get_session)):
    """Sign in as a claimed profile without a code. Only when DEMO_MODE is on (the default for this demo)."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    profile = session.get(Profile, body.get("profile_id"))
    if profile is None or profile.lifecycle_state not in CLAIMED_STATES:
        raise HTTPException(status_code=400, detail="Pick a claimed profile")
    start_session(session, response, profile)
    return {"profile_id": profile.id, "name": profile.name, "onboarding_completed": profile.onboarding_completed_at is not None}
