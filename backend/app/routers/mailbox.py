"""The mock mailbox: one page per email address. Nothing is sent; emails written for an address show up
here. Typing an address is all it takes to open its mailbox, which is the nature of a mock."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import normalize_email
from app.db import get_session
from app.models import MockEmail

router = APIRouter(prefix="/api/mailbox", tags=["mailbox"])


@router.get("")
def list_mailbox(email: str, session: Session = Depends(get_session)):
    address = normalize_email(email)
    rows = session.exec(select(MockEmail).where(MockEmail.to_email == address).order_by(MockEmail.created_at.desc())).all()
    return [
        {"id": e.id, "to_email": e.to_email, "subject": e.subject, "created_at": e.created_at, "is_opened": e.is_opened}
        for e in rows
    ]


@router.get("/{email_id}")
def get_mail(email_id: int, email: str, session: Session = Depends(get_session)):
    message = session.get(MockEmail, email_id)
    if message is None or message.to_email != normalize_email(email):
        raise HTTPException(status_code=404, detail="Email not found")
    if not message.is_opened:
        message.is_opened = True
        session.add(message)
        session.commit()
        session.refresh(message)
    return {
        "id": message.id, "to_email": message.to_email, "subject": message.subject,
        "body_html": message.body_html, "created_at": message.created_at, "is_opened": message.is_opened,
    }
