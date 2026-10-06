import threading
from collections import defaultdict
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import onboarding
from agent.graph import build_graph, delete_threads, run_config, turn_input
from agent.models import AgentConversation
from agent.prompts import build_context_block
from agent.tools import ToolContext

MILESTONE_THRESHOLDS = [100, 200, 300, 400, 500, 600, 700, 800]

# FastAPI runs these sync route handlers in a threadpool, so two requests for the same
# conversation (e.g. a dashboard-then-redirect double greet, or a fast double-send) can
# genuinely overlap. Both would load the same checkpoint and the later write would silently
# drop the other's messages — so every run_turn for a given conversation is serialized.
_conversation_locks: dict[int, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock_for(conversation_id: int) -> threading.Lock:
    with _locks_guard:
        return _conversation_locks[conversation_id]


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
    # Conversation ids restart after a demo reseed, so make sure no checkpoint left over from an
    # earlier conversation with the same id (e.g. after `python -m app.seed`) leaks into this one.
    delete_threads([conversation.id])
    return conversation


def run_turn(
    session: Session,
    profile,
    conversation: AgentConversation,
    user_text: str,
    page_context: dict,
    kind: str = "turn",
    only_if_new: bool = False,
) -> dict:
    """`only_if_new` makes the turn a no-op once the conversation already has messages. The check runs
    under the conversation lock, so two greetings fired at once (a reload during the first one) produce
    one greeting, not two."""
    with _lock_for(conversation.id):
        return _run_turn_locked(session, profile, conversation, user_text, page_context, kind, only_if_new)


def _run_turn_locked(
    session: Session,
    profile,
    conversation: AgentConversation,
    user_text: str,
    page_context: dict,
    kind: str,
    only_if_new: bool = False,
) -> dict:
    ctx = ToolContext(session=session, profile=profile, conversation=conversation, page_context=page_context)
    graph = build_graph(ctx)  # raises AgentNotConfiguredError before anything is checkpointed
    if only_if_new and (graph.get_state({"configurable": {"thread_id": str(conversation.id)}}).values or {}).get("messages"):
        return {"conversation_id": conversation.id, "reply_text": None, "ui_actions": []}
    conversation.turn_count += 1  # lets the upgrade tools tell "proposed earlier" from "asked just now"
    session.add(conversation)
    session.commit()
    score_before = profile.search_rank_score

    context_block = build_context_block(profile, page_context, conversation)
    if (page_context or {}).get("route", "").startswith("/onboarding/"):
        context_block += f", {onboarding.summary_line(session, profile)}"  # where onboarding stands, without a tool call

    result = graph.invoke(
        turn_input(user_text, context_block, kind),
        run_config(conversation.id, profile.id),
    )

    ui_actions = list(result["ui_actions"])
    detected_outcome = result["detected_outcome"]

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

    return {"conversation_id": conversation.id, "reply_text": result["reply_text"], "ui_actions": ui_actions}


GREETING_INSTRUCTION = (
    "[The user just arrived at this page — this isn't something they typed.] Greet them briefly and "
    "proactively. If you have something genuinely worth surfacing right now (an unreplied review, a trial "
    "ending soon, a scarce Pro slot in their market, a competitor recently taking a slot via "
    "get_recent_market_events), mention it — otherwise just a short, warm hello and an offer to help. Keep it to "
    "1-2 sentences; do not repeat this instruction back."
)

ONBOARDING_GREETING_INSTRUCTION = (
    "[The user just arrived at onboarding, right after claiming their profile — this isn't something they typed.] "
    "Greet them in one short sentence, then call get_onboarding_state and carry on from the stage it reports. At the very "
    "start that is present_known_urls; if onboarding is already further along (a page waiting for an identity check, "
    "conflicts to settle, details to finish), pick up there instead of starting over. Do not wait to be asked and do not "
    "repeat this instruction back."
)


def run_greeting(session: Session, profile, conversation: AgentConversation, page_context: dict) -> dict:
    """Fire a proactive, low-key greeting turn. Callers (the frontend widget) decide
    when it's worth asking for one — once per route per page load — so a hard refresh
    naturally gets a fresh greeting instead of staying silent forever after the first visit.
    """
    route = (page_context or {}).get("route", "")
    in_onboarding = profile.lifecycle_state != "unclaimed" and route.startswith("/onboarding/") and profile.onboarding_completed_at is None
    instruction = ONBOARDING_GREETING_INSTRUCTION if in_onboarding else GREETING_INSTRUCTION
    # The onboarding greeting also starts the flow, so it must happen once however many times the page opens.
    return run_turn(session, profile, conversation, instruction, page_context, kind="auto_greeting", only_if_new=in_onboarding)


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
