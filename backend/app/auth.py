"""Email-OTP sign-in, claim OTPs and server-side sessions.

OTPs are 6 digits, stored only as an HMAC (never the code), expire after OTP_TTL_MINUTES, allow
OTP_MAX_ATTEMPTS wrong tries, and are single-use. Delivery is the mock mailbox: the code is written
into that address's own mailbox page, nothing is emailed.

A session is a random token held in an HttpOnly, SameSite=Lax cookie; only its hash is stored.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app.constants import CLAIMED_STATES
from app.db import get_session
from app.models import AuthSession, OtpCode, Profile

SESSION_COOKIE = "clearrank_session"
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "7"))
OTP_TTL_MINUTES = int(os.environ.get("OTP_TTL_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))
OTP_MAX_PER_WINDOW = int(os.environ.get("OTP_MAX_PER_WINDOW", "5"))  # codes per email per OTP_TTL_MINUTES
DEMO_MODE = os.environ.get("DEMO_MODE", "true").strip().lower() in ("1", "true", "yes", "on")


def _hmac(value: str) -> str:
    return hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


# --- OTP ---------------------------------------------------------------------------------------------


def create_otp(session: Session, email: str, purpose: str, *, profile_id: int | None = None, claim_id: int | None = None) -> str:
    """Issue a new code for `email`, invalidating any earlier unused one. Returns the plain code
    (the caller writes it into the mock mailbox)."""
    email = normalize_email(email)
    window = datetime.utcnow() - timedelta(minutes=OTP_TTL_MINUTES)
    recent = session.exec(select(OtpCode).where(OtpCode.email == email, OtpCode.created_at > window)).all()
    if len(recent) >= OTP_MAX_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many codes requested. Wait a few minutes and try again.")
    for old in recent:
        if old.consumed_at is None:
            old.consumed_at = datetime.utcnow()
            session.add(old)

    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(
        OtpCode(
            email=email, purpose=purpose, profile_id=profile_id, claim_id=claim_id,
            code_hash=_hmac(f"{email}:{code}"), expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    session.commit()
    return code


def check_otp(session: Session, email: str, purpose: str, code: str, *, claim_id: int | None = None) -> OtpCode:
    """Verify `code` for the newest active OTP. Raises 400 with a clear message on any failure."""
    email = normalize_email(email)
    query = select(OtpCode).where(OtpCode.email == email, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
    if claim_id is not None:
        query = query.where(OtpCode.claim_id == claim_id)
    otp = session.exec(query.order_by(OtpCode.created_at.desc())).first()
    if otp is None:
        raise HTTPException(status_code=400, detail="No active code. Request a new one.")
    if otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="That code has expired. Request a new one.")
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many wrong attempts. Request a new code.")

    if not hmac.compare_digest(otp.code_hash, _hmac(f"{email}:{(code or '').strip()}")):
        otp.attempts += 1
        session.add(otp)
        session.commit()
        left = OTP_MAX_ATTEMPTS - otp.attempts
        raise HTTPException(status_code=400, detail=f"That code is not right. {left} attempt(s) left.")

    otp.consumed_at = datetime.utcnow()
    session.add(otp)
    session.commit()
    return otp


# --- Sessions ----------------------------------------------------------------------------------------


def start_session(session: Session, response: Response, profile: Profile, email: str | None = None) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=SESSION_DAYS)
    session.add(AuthSession(token_hash=_hmac(token), profile_id=profile.id, email=normalize_email(email or profile.email), expires_at=expires))
    session.commit()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
        secure=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
    )


def end_session(session: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        row = session.exec(select(AuthSession).where(AuthSession.token_hash == _hmac(token))).first()
        if row:
            session.delete(row)
            session.commit()
    response.delete_cookie(SESSION_COOKIE)


def current_session(request: Request, session: Session) -> AuthSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    row = session.exec(select(AuthSession).where(AuthSession.token_hash == _hmac(token))).first()
    if row is None or row.expires_at < datetime.utcnow():
        return None
    return row


def require_owner(profile_id: int, request: Request, session: Session = Depends(get_session)) -> Profile:
    """Like require_access, but always needs the owner's own session, even while the profile is unclaimed.
    For routes that have no public face (onboarding): 401 when signed out, 403 for someone else's."""
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    current = current_session(request, session)
    if current is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    if current.profile_id != profile_id:
        raise HTTPException(status_code=403, detail="This profile belongs to another account")
    return profile


def require_access(profile_id: int, request: Request, session: Session = Depends(get_session)) -> Profile:
    """FastAPI dependency for every route about one profile that only its owner should reach.

    An unclaimed profile is public (it is what people search for and claim), so it needs no session.
    A claimed profile needs a session for that same profile: 401 when signed out, 403 when signed in
    as someone else."""
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.lifecycle_state not in CLAIMED_STATES:
        return profile
    current = current_session(request, session)
    if current is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    if current.profile_id != profile_id:
        raise HTTPException(status_code=403, detail="This profile belongs to another account")
    return profile
