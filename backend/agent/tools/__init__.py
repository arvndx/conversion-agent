from dataclasses import dataclass
from typing import Any, Callable

from sqlmodel import Session

from app.models import Profile

from agent.models import AgentConversation


@dataclass
class ToolContext:
    session: Session
    profile: Profile
    conversation: AgentConversation
    page_context: dict


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[ToolContext, dict], Any]
    is_ui_action: bool = False


TOOL_REGISTRY: dict[str, ToolDef] = {}


def register_tool(tool: ToolDef) -> None:
    TOOL_REGISTRY[tool.name] = tool


# Importing these registers their tools as a side effect. Done at the bottom of
# this module (after ToolContext/ToolDef/register_tool exist) since each tool
# module does `from agent.tools import ...` to reach them.
from agent.tools import (  # noqa: E402,F401
    claim_tools,
    retention_tools,
    review_tools,
    scarcity_tools,
    scoring_tools,
    tour_tools,
    ui_tools,
    upgrade_tools,
)
