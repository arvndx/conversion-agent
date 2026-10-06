from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class AgentConversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", unique=True, index=True)
    outcome: str | None = None  # converted | trial_started | no_action
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Guided tour state
    tour_active: bool = False
    tour_step_index: int = 0

    # Doubt-resolution state — applies to any conversation, tour or not (see
    # record_doubt_attempt / escalate_unresolved_doubt in tools/tour_tools.py).
    doubt_open: bool = False
    doubt_topic: str | None = None
    doubt_attempts: int = 0
    awaiting_handoff_resolution: bool = False

    # Consent for paid actions (see tools/upgrade_tools.py): the app counts the user's turns, and an
    # upgrade or trial only goes through when it was proposed (price stated) in an EARLIER turn.
    turn_count: int = 0
    pending_action: str | None = None  # "upgrade" | "trial"
    pending_turn: int = 0


class AgentToolInvocation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="agentconversation.id", index=True)
    # Conversation history now lives in the LangGraph checkpointer (agent/graph.py); this table is
    # only the per-call audit log (tool, input, result, latency).
    tool_name: str
    tool_use_id: str
    input: dict = Field(sa_column=Column(JSONB))
    result: dict = Field(sa_column=Column(JSONB))
    is_error: bool = False
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
