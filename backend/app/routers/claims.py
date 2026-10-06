from fastapi import APIRouter, Body, Depends, Response
from sqlmodel import Session

from app.claims import start_claim, verify_claim
from app.db import get_session

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.post("/start")
def claim_start(body: dict = Body(...), session: Session = Depends(get_session)):
    """Option 1 (with `profile_id`, from a search result) or option 2 (without, a new profile)."""
    return start_claim(session, body)


@router.post("/verify")
def claim_verify(response: Response, body: dict = Body(...), session: Session = Depends(get_session)):
    return verify_claim(session, response, int(body.get("claim_id") or 0), str(body.get("code") or ""))
