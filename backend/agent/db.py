from app.db import engine

# Importing agent.models registers AgentConversation/AgentMessage/AgentToolInvocation
# on SQLModel's shared metadata. init_db()'s create_all() call must run after this
# import happens, or these tables silently never get created.
from agent import models as _agent_models  # noqa: F401
from sqlmodel import SQLModel


def init_agent_db() -> None:
    SQLModel.metadata.create_all(engine)
