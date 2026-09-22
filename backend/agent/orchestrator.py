import json
import threading
import time
from collections import defaultdict
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from agent.config import AGENT_MAX_TOOL_ROUNDS, AGENT_MODEL, get_client
from agent.models import AgentConversation, AgentMessage, AgentToolInvocation
from agent.prompts import STATIC_SYSTEM_PROMPT, build_context_block
from agent.server_tools import WEB_SEARCH_TOOL
from agent.tools import TOOL_REGISTRY, ToolContext

MILESTONE_THRESHOLDS = [100, 200, 300, 400, 500, 600, 700, 800]

# FastAPI runs these sync route handlers in a threadpool, so two requests for the same
# conversation (e.g. a dashboard-then-redirect double greet, or a fast double-send) can
# genuinely overlap. Both would read the same "next sequence index" and interleave writes,
# corrupting message ordering — so every run_turn for a given conversation is serialized.
_conversation_locks: dict[int, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock_for(conversation_id: int) -> threading.Lock:
    with _locks_guard:
        return _conversation_locks[conversation_id]

# Cap how much history is replayed into the model on each call, so a long-running
# demo conversation doesn't grow the request unboundedly. Windowed by whole turns
# (a "turn"/"auto_greeting" message plus every "tool_results" continuation that
# follows it), never mid-turn — splitting a tool_use from its tool_result would
# make the request invalid.
MAX_HISTORY_TURNS = 20


def get_or_create_conversation(session: Session, profile_id: int) -> AgentConversation:
    conversation = session.exec(
        select(AgentConversation).where(AgentConversation.profile_id == profile_id)
    ).first()
    if conversation is not None:
        return conversation

    # Two first-ever requests for the same profile (a double-fired effect, two tabs, a
    # fast double-click) can both see "no conversation yet" and race to create one —
    # profile_id is unique, so the loser's insert fails. Fall back to re-reading the
    # winner's row rather than erroring the whole turn.
    conversation = AgentConversation(profile_id=profile_id)
    session.add(conversation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        conversation = session.exec(
            select(AgentConversation).where(AgentConversation.profile_id == profile_id)
        ).first()
        if conversation is None:
            raise
        return conversation
    session.refresh(conversation)
    return conversation


def _load_history(session: Session, conversation_id: int) -> list[dict]:
    messages = session.exec(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation_id)
        .order_by(AgentMessage.sequence_index)
    ).all()

    turn_start_indices = [i for i, m in enumerate(messages) if m.kind in ("turn", "auto_greeting")]
    if len(turn_start_indices) > MAX_HISTORY_TURNS:
        cutoff = turn_start_indices[-MAX_HISTORY_TURNS]
        messages = messages[cutoff:]

    return [{"role": m.role, "content": m.content} for m in messages]


def _next_sequence_index(session: Session, conversation_id: int) -> int:
    last = session.exec(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation_id)
        .order_by(AgentMessage.sequence_index.desc())
    ).first()
    return (last.sequence_index + 1) if last else 0


def _persist_message(session, conversation_id, role, content, kind="turn", stop_reason=None, model=None, usage=None):
    msg = AgentMessage(
        conversation_id=conversation_id,
        sequence_index=_next_sequence_index(session, conversation_id),
        role=role,
        kind=kind,
        content=content,
        stop_reason=stop_reason,
        model=model,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg


def _tool_schemas() -> list[dict]:
    custom_tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOL_REGISTRY.values()
    ]
    return [WEB_SEARCH_TOOL, *custom_tools]


def _run_tool(ctx: ToolContext, name: str, tool_input: dict) -> tuple[dict, bool]:
    tool_def = TOOL_REGISTRY.get(name)
    if tool_def is None:
        return {"error": f"unknown tool '{name}'"}, True
    try:
        return tool_def.handler(ctx, tool_input), False
    except Exception as exc:  # noqa: BLE001 — tool failures become a tool_result, not a crash
        return {"error": str(exc)}, True


def run_turn(
    session: Session,
    profile,
    conversation: AgentConversation,
    user_text: str,
    page_context: dict,
    kind: str = "turn",
) -> dict:
    with _lock_for(conversation.id):
        return _run_turn_locked(session, profile, conversation, user_text, page_context, kind)


def _run_turn_locked(
    session: Session,
    profile,
    conversation: AgentConversation,
    user_text: str,
    page_context: dict,
    kind: str,
) -> dict:
    context_block = build_context_block(profile, page_context, conversation)
    _persist_message(
        session,
        conversation.id,
        "user",
        [
            {"type": "text", "text": context_block},
            {"type": "text", "text": user_text},
        ],
        kind=kind,
    )

    client = get_client()
    tools = _tool_schemas()
    ui_actions: list[dict] = []
    reply_text = ""
    score_before = profile.search_rank_score
    detected_outcome: str | None = None

    for _round in range(AGENT_MAX_TOOL_ROUNDS):
        messages = _load_history(session, conversation.id)
        create_kwargs = dict(
            model=AGENT_MODEL,
            max_tokens=2048,
            system=[{"type": "text", "text": STATIC_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        if tools:
            create_kwargs["tools"] = tools
        response = client.messages.create(**create_kwargs)
        content_blocks = [block.model_dump() for block in response.content]
        _persist_message(
            session,
            conversation.id,
            "assistant",
            content_blocks,
            stop_reason=response.stop_reason,
            model=response.model,
            usage=response.usage,
        )

        text_blocks = [b["text"] for b in content_blocks if b["type"] == "text"]
        if text_blocks:
            reply_text = "\n".join(text_blocks)

        if response.stop_reason == "pause_turn":
            continue  # a server tool (e.g. web_search) needs another round; no tool_result to give

        tool_use_blocks = [b for b in content_blocks if b["type"] == "tool_use"]
        if not tool_use_blocks:
            break

        ctx = ToolContext(session=session, profile=profile, conversation=conversation, page_context=page_context)
        tool_results = []
        invocations = []
        for block in tool_use_blocks:
            start = time.monotonic()
            result, is_error = _run_tool(ctx, block["name"], block["input"])
            latency_ms = int((time.monotonic() - start) * 1000)

            tool_def = TOOL_REGISTRY.get(block["name"])
            if tool_def and tool_def.is_ui_action and not is_error:
                ui_actions.append({"type": block["name"], "input": block["input"], "result": result})

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "is_error": is_error,
                }
            )
            invocations.append((block, result, is_error, latency_ms))

            if not is_error:
                if block["name"] == "confirm_and_upgrade_to_pro" and result.get("upgraded"):
                    detected_outcome = "converted"
                elif block["name"] == "start_pro_trial" and result.get("trial_started") and detected_outcome != "converted":
                    detected_outcome = "trial_started"

        result_message = _persist_message(session, conversation.id, "user", tool_results, kind="tool_results")

        for block, result, is_error, latency_ms in invocations:
            session.add(
                AgentToolInvocation(
                    conversation_id=conversation.id,
                    message_id=result_message.id,
                    tool_name=block["name"],
                    tool_use_id=block["id"],
                    input=block["input"],
                    result=result,
                    is_error=is_error,
                    latency_ms=latency_ms,
                )
            )
        session.commit()

    session.refresh(profile)
    score_after = profile.search_rank_score
    if score_after > score_before:
        crossed = [t for t in MILESTONE_THRESHOLDS if score_before < t <= score_after]
        if crossed:
            ui_actions.append({"type": "celebrate", "input": {}, "result": {"milestone": crossed[-1]}})

    if detected_outcome == "converted" or (detected_outcome == "trial_started" and conversation.outcome != "converted"):
        conversation.outcome = detected_outcome

    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    session.commit()

    return {"conversation_id": conversation.id, "reply_text": reply_text, "ui_actions": ui_actions}


GREETING_INSTRUCTION = (
    "[The user just arrived at this page — this isn't something they typed.] Greet them briefly and "
    "proactively. If you have something genuinely worth surfacing right now (an unreplied review, a trial "
    "ending soon, a scarce Pro slot in their market, a competitor recently taking a slot via "
    "get_recent_market_events), mention it — otherwise just a short, warm hello and an offer to help. Keep it to "
    "1-2 sentences; do not repeat this instruction back."
)

CLAIM_GREETING_INSTRUCTION = (
    "[The user just arrived at the claim flow's search step — this isn't something they typed.] Greet them "
    "briefly (1-2 sentences), then immediately act on job #3: call web_search using their known name and location "
    "right now — don't wait for them to ask. Then call present_candidate_matches with up to 5 real results (or "
    "skip it and say so plainly if you found none). Do not repeat this instruction back."
)


def run_greeting(session: Session, profile, conversation: AgentConversation, page_context: dict) -> dict:
    """Fire a proactive, low-key greeting turn. Callers (the frontend widget) decide
    when it's worth asking for one — once per route per page load — so a hard refresh
    naturally gets a fresh greeting instead of staying silent forever after the first visit.
    """
    route = (page_context or {}).get("route", "")
    instruction = (
        CLAIM_GREETING_INSTRUCTION
        if profile.lifecycle_state == "unclaimed" and route.startswith("/claim/")
        else GREETING_INSTRUCTION
    )
    return run_turn(session, profile, conversation, instruction, page_context, kind="auto_greeting")


def run_tour_start(session: Session, profile, conversation: AgentConversation, page_context: dict) -> dict:
    """Pre-computes and pre-narrates all 7 tour steps in one shot (see tour_content.py)
    so the frontend can step through them instantly afterward — no per-step model call.
    Locked like run_turn since it also mutates conversation state.
    """
    from agent.tour_content import build_tour_steps  # local import: avoids a circular import at module load

    if profile.lifecycle_state == "unclaimed":
        # The tour walks through the dashboard/manage pages, which don't exist until this
        # profile is claimed — fail cleanly instead of generating content that can't be shown.
        return {
            "error": "not_claimed",
            "message": "This profile hasn't been claimed yet, so there's no dashboard to tour.",
        }

    with _lock_for(conversation.id):
        conversation.tour_active = True
        conversation.tour_step_index = 0
        conversation.doubt_open = False
        conversation.doubt_topic = None
        conversation.doubt_attempts = 0
        conversation.awaiting_handoff_resolution = False
        session.add(conversation)
        session.commit()

        ctx = ToolContext(session=session, profile=profile, conversation=conversation, page_context=page_context)
        steps = build_tour_steps(ctx)

        _persist_message(
            session,
            conversation.id,
            "assistant",
            [{"type": "text", "text": json.dumps({"tour_batch": [s["id"] for s in steps]})}],
            kind="tour_batch",
        )
        return {"steps": steps}


RESUME_AFTER_HANDOFF_INSTRUCTION = (
    "[System: the simulated specialist has just finished following up on the user's open question — this isn't "
    "something the user typed.] There is no real specialist reply to relay, so do not invent one or describe "
    "what they supposedly said. Just warmly let the user know their question should be sorted now and ask if "
    "it's clear. If the context block shows a guided tour is active, mention they can hit 'Next step' whenever "
    "they're ready to continue — you don't control tour progression yourself. Keep it to 1-2 sentences."
)


def run_resume_after_handoff(session: Session, profile, conversation: AgentConversation, page_context: dict) -> dict:
    """Fires once the frontend's simulated wait has elapsed after escalate_unresolved_doubt.
    Clears the paused/doubt state server-side first — deterministically, not by trusting the
    model to call a cleanup tool — then lets the model narrate the resume turn naturally.
    """
    conversation.doubt_open = False
    conversation.doubt_topic = None
    conversation.doubt_attempts = 0
    conversation.awaiting_handoff_resolution = False
    session.add(conversation)
    session.commit()

    return run_turn(session, profile, conversation, RESUME_AFTER_HANDOFF_INSTRUCTION, page_context, kind="auto_resume")
