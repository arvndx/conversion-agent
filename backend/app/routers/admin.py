from fastapi import APIRouter
from sqlmodel import Session, SQLModel, select

from app.category_config import invalidate as invalidate_category_config
from app.db import engine, init_db
from app.seed import seed_demo
from app.seed_taxonomy import seed_taxonomy

from agent.db import init_agent_db
from agent.graph import delete_threads
from agent.models import AgentConversation

router = APIRouter(prefix="/api", tags=["admin"])


def reset_demo_data() -> None:
    """Drop and recreate every table, then seed the taxonomy and the demo profiles. Shared by the
    reset endpoint and the optional reset-on-startup in main.py. Dropping (rather than truncating)
    means schema changes never need a migration while this is a demo."""
    # Checkpoints are keyed by conversation id, which a rebuilt table restarts from 1, so clear them
    # first or a new conversation would inherit an old one's history. The tables may not exist yet
    # (first run) or may predate the current schema, so a failure here is not fatal.
    try:
        with Session(engine) as session:
            delete_threads([c.id for c in session.exec(select(AgentConversation)).all()])
    except Exception:  # noqa: BLE001
        pass
    SQLModel.metadata.drop_all(engine)
    init_db()
    init_agent_db()
    with Session(engine) as session:
        seed_taxonomy(session)
    invalidate_category_config()
    seed_demo()


@router.post("/reset-demo")
def reset_demo():
    reset_demo_data()
    return {"status": "ok"}
