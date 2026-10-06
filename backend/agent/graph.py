"""Profile Pilot's LangGraph agent graph.

    START -> model -> (tool calls?) -> tools -> model -> ... -> END

* `model` calls Claude with the static (cached) system prompt plus the windowed history.
* `tools` runs the client-side tools from agent/tools (registry unchanged), records the
  UI actions the frontend should perform, writes the AgentToolInvocation audit rows, and
  detects conversion outcomes.
* Conversation history is the graph state, persisted per conversation by a Postgres
  checkpointer (thread_id == AgentConversation.id).

The graph is compiled per request because the tool handlers need that request's DB session,
profile and page context; they're closed over in `build_graph` rather than passed through
state, since state is what gets checkpointed.
"""

import json
import os
import time
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.db import psycopg_conninfo

from agent.config import AGENT_MAX_TOOL_ROUNDS, get_chat_model
from agent.models import AgentToolInvocation
from agent.prompts import STATIC_SYSTEM_PROMPT
from agent.server_tools import WEB_SEARCH_TOOL
from agent.tools import TOOL_REGISTRY, ToolContext

# Cap how much history is replayed into the model on each call, so a long-running
# demo conversation doesn't grow the request unboundedly. Windowed by whole turns
# (a human message plus every AI/tool message that follows it), never mid-turn —
# splitting a tool_use from its tool_result would make the request invalid.
MAX_HISTORY_TURNS = 20

# Cached system prompt: the static prompt never changes between calls, so only the
# per-turn context block (in the human message) varies and the prefix stays a cache hit.
SYSTEM_MESSAGE = SystemMessage(
    content=[{"type": "text", "text": STATIC_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Everything below is per-turn bookkeeping, reset by the input of every invoke().
    ui_actions: list[dict]
    rounds: int
    reply_text: str
    detected_outcome: str | None


@lru_cache(maxsize=1)
def get_checkpointer() -> PostgresSaver:
    # The checkpoint tables live in the same database as the product data. A connection pool
    # because FastAPI runs sync handlers in a threadpool; autocommit / prepare_threshold=0 /
    # dict_row are what PostgresSaver requires of its connections.
    pool = ConnectionPool(
        conninfo=psycopg_conninfo(),
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    saver = PostgresSaver(pool)
    saver.setup()
    return saver


@lru_cache(maxsize=1)
def _model_with_tools():
    custom_tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOL_REGISTRY.values()
    ]
    return get_chat_model(max_tokens=2048).bind_tools([WEB_SEARCH_TOOL, *custom_tools])


def _window(messages: list[AnyMessage]) -> list[AnyMessage]:
    turn_starts = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if len(turn_starts) > MAX_HISTORY_TURNS:
        return messages[turn_starts[-MAX_HISTORY_TURNS] :]
    return messages


def _reply_text(ai: AIMessage) -> str:
    # Newline-joined, not AIMessage.text (which concatenates with no separator): a turn that
    # runs web_search has separate text blocks before and after the search, and gluing them
    # together reads "...typing.I searched...".
    if isinstance(ai.content, str):
        return ai.content
    return "\n".join(b["text"] for b in ai.content if isinstance(b, dict) and b.get("type") == "text")


def _run_tool(ctx: ToolContext, name: str, tool_input: dict) -> tuple[dict, bool]:
    tool_def = TOOL_REGISTRY.get(name)
    if tool_def is None:
        return {"error": f"unknown tool '{name}'"}, True
    try:
        return tool_def.handler(ctx, tool_input), False
    except Exception as exc:  # noqa: BLE001 — tool failures become a tool_result, not a crash
        return {"error": str(exc)}, True


def build_graph(ctx: ToolContext | None):
    """Compile the agent graph. `ctx=None` gives a read-only graph (history lookups, thread
    resets) that can't run tool calls."""

    def model_node(state: AgentState) -> dict:
        ai: AIMessage = _model_with_tools().invoke([SYSTEM_MESSAGE, *_window(state["messages"])])
        update: dict = {"messages": [ai], "rounds": state["rounds"] + 1}
        reply_text = _reply_text(ai)
        if reply_text:
            update["reply_text"] = reply_text
        return update

    def tools_node(state: AgentState) -> dict:
        ai: AIMessage = state["messages"][-1]
        ui_actions = list(state["ui_actions"])
        detected_outcome = state["detected_outcome"]
        results: list[ToolMessage] = []

        for call in ai.tool_calls:
            start = time.monotonic()
            result, is_error = _run_tool(ctx, call["name"], call["args"])
            latency_ms = int((time.monotonic() - start) * 1000)

            tool_def = TOOL_REGISTRY.get(call["name"])
            if tool_def and tool_def.is_ui_action and not is_error:
                ui_actions.append({"type": call["name"], "input": call["args"], "result": result})

            results.append(
                ToolMessage(
                    content=json.dumps(result),
                    tool_call_id=call["id"],
                    name=call["name"],
                    status="error" if is_error else "success",
                )
            )
            ctx.session.add(
                AgentToolInvocation(
                    conversation_id=ctx.conversation.id,
                    tool_name=call["name"],
                    tool_use_id=call["id"],
                    input=call["args"],
                    result=result,
                    is_error=is_error,
                    latency_ms=latency_ms,
                )
            )

            if not is_error:
                if call["name"] == "confirm_and_upgrade_to_pro" and result.get("upgraded"):
                    detected_outcome = "converted"
                elif (
                    call["name"] == "start_pro_trial"
                    and result.get("trial_started")
                    and detected_outcome != "converted"
                ):
                    detected_outcome = "trial_started"

        ctx.session.commit()
        return {"messages": results, "ui_actions": ui_actions, "detected_outcome": detected_outcome}

    def after_model(state: AgentState) -> str:
        ai = state["messages"][-1]
        if ai.tool_calls:
            return "tools"  # always run requested tools, even on the last round — never leave a dangling tool_use
        if ai.response_metadata.get("stop_reason") == "pause_turn" and state["rounds"] < AGENT_MAX_TOOL_ROUNDS:
            return "model"  # a server tool (e.g. web_search) needs another round; no tool_result to give
        return END

    def after_tools(state: AgentState) -> str:
        return "model" if state["rounds"] < AGENT_MAX_TOOL_ROUNDS else END

    graph = StateGraph(AgentState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", after_model, {"tools": "tools", "model": "model", END: END})
    graph.add_conditional_edges("tools", after_tools, {"model": "model", END: END})
    return graph.compile(checkpointer=get_checkpointer())


def turn_input(user_text: str, context_block: str, kind: str) -> dict:
    """The graph input for one turn: the new human message (context block + what was typed),
    plus a reset of the per-turn bookkeeping."""
    return {
        "messages": [
            HumanMessage(
                content=[
                    {"type": "text", "text": context_block},
                    {"type": "text", "text": user_text},
                ],
                additional_kwargs={"kind": kind},
            )
        ],
        "ui_actions": [],
        "rounds": 0,
        "reply_text": "",
        "detected_outcome": None,
    }


def run_config(conversation_id: int, profile_id: int) -> dict:
    callbacks = []
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        from langfuse.langchain import CallbackHandler  # optional tracing, off unless Langfuse keys are set

        callbacks.append(CallbackHandler())
    return {
        "configurable": {"thread_id": str(conversation_id)},
        "recursion_limit": 2 * AGENT_MAX_TOOL_ROUNDS + 5,
        "callbacks": callbacks,
        "metadata": {"langfuse_session_id": f"profile-{profile_id}", "profile_id": profile_id},
    }


def _blocks(content) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b if isinstance(b, dict) else {"type": "text", "text": str(b)} for b in content]


def load_history(conversation_id: int) -> list[dict]:
    """The conversation as the GET /conversations/{profile_id} endpoint returns it."""
    state = build_graph(None).get_state({"configurable": {"thread_id": str(conversation_id)}})
    history = []
    for m in (state.values or {}).get("messages", []):
        if isinstance(m, HumanMessage):
            history.append({"role": "user", "kind": m.additional_kwargs.get("kind", "turn"), "content": _blocks(m.content), "stop_reason": None})
        elif isinstance(m, AIMessage):
            history.append(
                {
                    "role": "assistant",
                    "kind": "turn",
                    "content": _blocks(m.content),
                    "stop_reason": m.response_metadata.get("stop_reason"),
                }
            )
        elif isinstance(m, ToolMessage):
            history.append(
                {
                    "role": "user",
                    "kind": "tool_results",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": [{"type": "text", "text": m.content}],
                            "is_error": m.status == "error",
                        }
                    ],
                    "stop_reason": None,
                }
            )
    return history


def delete_threads(conversation_ids: list[int]) -> None:
    saver = get_checkpointer()
    for conversation_id in conversation_ids:
        saver.delete_thread(str(conversation_id))
