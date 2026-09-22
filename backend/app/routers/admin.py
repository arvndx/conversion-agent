from fastapi import APIRouter
from sqlmodel import Session, delete

from app.db import engine
from app.seed import seed_demo

from agent.models import AgentConversation, AgentMessage, AgentToolInvocation

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/reset-demo")
def reset_demo():
    seed_demo()
    with Session(engine) as session:
        session.exec(delete(AgentToolInvocation))
        session.exec(delete(AgentMessage))
        session.exec(delete(AgentConversation))
        session.commit()
    return {"status": "ok"}
