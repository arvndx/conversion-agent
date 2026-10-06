"""Writing mock emails. Every dynamic value is HTML-escaped here, because the mailbox page renders
`body_html` as HTML."""

from html import escape

from sqlmodel import Session

from app.models import MockEmail


def paragraphs(*parts: str) -> str:
    """Join plain-text paragraphs into safe HTML (each one escaped)."""
    return "".join(f"<p>{escape(part)}</p>" for part in parts)


def send_mock_email(session: Session, *, to_email: str, subject: str, html: str, profile_id: int | None = None) -> MockEmail:
    email = MockEmail(to_email=(to_email or "").strip().lower(), subject=subject, body_html=html, profile_id=profile_id)
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


def otp_email_html(name: str, code: str, purpose: str) -> str:
    if purpose == "claim":
        intro = f"Hi {name}, enter this code on ClearRank to claim your profile."
    else:
        intro = f"Hi {name}, enter this code on ClearRank to sign in."
    return (
        f"<p>{escape(intro)}</p>"
        f"<p style='font-size:28px;font-weight:700;letter-spacing:6px;'>{escape(code)}</p>"
        "<p>It expires in 10 minutes. If you did not ask for it, ignore this email.</p>"
    )
