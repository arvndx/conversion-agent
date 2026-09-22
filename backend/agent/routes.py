from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Profile

from agent.config import AgentNotConfiguredError, is_configured
from agent.models import AgentMessage
from agent.nudges import run_nudges
from agent.orchestrator import get_or_create_conversation, run_greeting, run_resume_after_handoff, run_tour_start, run_turn

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/status")
def get_status():
    return {"configured": is_configured()}


@router.post("/conversations/{profile_id}/messages")
def send_message(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    page_context = body.get("page_context") or {}

    conversation = get_or_create_conversation(session, profile.id)

    try:
        return run_turn(session, profile, conversation, message, page_context)
    except AgentNotConfiguredError:
        raise HTTPException(status_code=503, detail="Agent is not configured yet")


@router.post("/conversations/{profile_id}/greet")
def greet(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    page_context = body.get("page_context") or {}
    conversation = get_or_create_conversation(session, profile.id)

    try:
        result = run_greeting(session, profile, conversation, page_context)
    except AgentNotConfiguredError:
        raise HTTPException(status_code=503, detail="Agent is not configured yet")

    return result or {"conversation_id": conversation.id, "reply_text": None, "ui_actions": []}


@router.post("/conversations/{profile_id}/resume-after-handoff")
def resume_after_handoff(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    page_context = body.get("page_context") or {}
    conversation = get_or_create_conversation(session, profile.id)

    try:
        return run_resume_after_handoff(session, profile, conversation, page_context)
    except AgentNotConfiguredError:
        raise HTTPException(status_code=503, detail="Agent is not configured yet")


@router.post("/conversations/{profile_id}/tour/start")
def start_tour_batch(profile_id: int, body: dict = Body(...), session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    page_context = body.get("page_context") or {}
    conversation = get_or_create_conversation(session, profile.id)

    try:
        return run_tour_start(session, profile, conversation, page_context)
    except AgentNotConfiguredError:
        raise HTTPException(status_code=503, detail="Agent is not configured yet")


@router.post("/nudges/run")
def run_nudges_endpoint(profile_id: int | None = None, force: bool = False, session: Session = Depends(get_session)):
    return run_nudges(session, profile_id=profile_id, force=force)


@router.get("/conversations/{profile_id}")
def get_conversation(profile_id: int, session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    conversation = get_or_create_conversation(session, profile.id)
    messages = session.exec(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation.id)
        .order_by(AgentMessage.sequence_index)
    ).all()

    return {
        "conversation_id": conversation.id,
        "outcome": conversation.outcome,
        "messages": [
            {
                "role": m.role,
                "kind": m.kind,
                "content": m.content,
                "stop_reason": m.stop_reason,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }
