from datetime import datetime

from sqlalchemy import Column, JSON
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


class AgentMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="agentconversation.id", index=True)
    sequence_index: int
    role: str  # user | assistant
    kind: str = "turn"  # turn | tool_results | auto_greeting
    content: list[dict] = Field(sa_column=Column(JSON))
    stop_reason: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentToolInvocation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="agentconversation.id", index=True)
    message_id: int = Field(foreign_key="agentmessage.id")
    tool_name: str
    tool_use_id: str
    input: dict = Field(sa_column=Column(JSON))
    result: dict = Field(sa_column=Column(JSON))
    is_error: bool = False
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
