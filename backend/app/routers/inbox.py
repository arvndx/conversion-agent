from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import MockEmail

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


@router.get("")
def list_inbox(session: Session = Depends(get_session)):
    emails = session.exec(select(MockEmail).order_by(MockEmail.created_at.desc()))
    return [
        {
            "id": e.id,
            "to_email": e.to_email,
            "subject": e.subject,
            "profile_id": e.profile_id,
            "created_at": e.created_at,
            "is_opened": e.is_opened,
        }
        for e in emails
    ]


@router.get("/{email_id}")
def get_email(email_id: int, session: Session = Depends(get_session)):
    email = session.get(MockEmail, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    if not email.is_opened:
        email.is_opened = True
        session.add(email)
        session.commit()
        session.refresh(email)
    return {
        "id": email.id,
        "to_email": email.to_email,
        "subject": email.subject,
        "body_html": email.body_html,
        "profile_id": email.profile_id,
        "created_at": email.created_at,
        "is_opened": email.is_opened,
    }
