"""The doubt-resolution loop, plus a lightweight trigger for starting the guided tour
from free text. The tour's actual content (all 7 steps' data and narration) is
pre-generated in one batch by tour_content.py/run_tour_start — this module only owns
the "should we start" signal and the doubt/escalation counters, both plain bookkeeping.
"""

from app.models import ExecutiveHandoffRequest, MockEmail

from agent.tools import ToolContext, ToolDef, register_tool

DOUBT_ESCALATION_THRESHOLD = 3
SIMULATED_HANDOFF_WAIT_SECONDS = 6


def start_tour(ctx: ToolContext, tool_input: dict) -> dict:
    """Called when the user asks for a tour in free text rather than clicking a button.
    Doesn't generate any content itself — just signals the frontend to run the same
    batch-prepared tour as the button path, so there's only one tour pipeline.
    """
    return {"trigger_batch_tour": True}


def record_doubt_attempt(ctx: ToolContext, tool_input: dict) -> dict:
    conv = ctx.conversation
    resolved = bool(tool_input.get("resolved"))
    topic = (tool_input.get("topic") or "").strip()[:200]

    if resolved:
        conv.doubt_open = False
        conv.doubt_topic = None
        conv.doubt_attempts = 0
        ctx.session.add(conv)
        ctx.session.commit()
        return {"resolved": True}

    if topic and topic == conv.doubt_topic:
        conv.doubt_attempts += 1
    else:
        conv.doubt_topic = topic
        conv.doubt_attempts = 1
    conv.doubt_open = True
    ctx.session.add(conv)
    ctx.session.commit()

    must_escalate = conv.doubt_attempts >= DOUBT_ESCALATION_THRESHOLD
    return {"resolved": False, "attempts": conv.doubt_attempts, "must_escalate": must_escalate}


def escalate_unresolved_doubt(ctx: ToolContext, tool_input: dict) -> dict:
    """Always available — unlike request_executive_handoff, this is a comprehension
    escalation, not a sales one, so it isn't gated by is_hot_lead. Simulated: no real
    specialist exists, so the frontend fires a timed auto-resume after this returns.
    """
    conv = ctx.conversation
    topic = tool_input.get("topic") or conv.doubt_topic or "a question during the tour"

    ctx.session.add(
        ExecutiveHandoffRequest(
            profile_id=ctx.profile.id,
            reason=f"Unresolved after {conv.doubt_attempts} attempts: {topic}",
        )
    )
    ctx.session.add(
        MockEmail(
            to_email=ctx.profile.email,
            subject="A specialist is following up on your question",
            body_html=(
                f"<p>Hi {ctx.profile.name},</p>"
                f"<p>We noticed you had a question about: {topic}. A specialist is looking into it now.</p>"
            ),
            profile_id=ctx.profile.id,
        )
    )
    conv.awaiting_handoff_resolution = True
    ctx.session.add(conv)
    ctx.session.commit()

    return {
        "escalated": True,
        "simulated": True,
        "simulated_wait_seconds": SIMULATED_HANDOFF_WAIT_SECONDS,
        "topic": topic,
    }


register_tool(
    ToolDef(
        name="start_tour",
        description="Trigger the guided product tour. Call this when the user asks for a tour in free text "
        "(they may also start it directly via a button, which doesn't go through you at all). The app prepares "
        "and displays all steps itself — you don't need to narrate anything or call this more than once.",
        input_schema={"type": "object", "properties": {}},
        handler=start_tour,
        is_ui_action=True,
    )
)

register_tool(
    ToolDef(
        name="record_doubt_attempt",
        description="Call this right after asking the user 'is that clear now?' and getting their answer — in "
        "the tour or in any normal conversation. Pass a short, stable topic label (2-5 words) so repeated "
        "doubts on the same subject count together rather than resetting. If must_escalate comes back true, "
        "call escalate_unresolved_doubt next.",
        input_schema={
            "type": "object",
            "properties": {
                "resolved": {"type": "boolean", "description": "Did the user confirm it's clear now?"},
                "topic": {"type": "string", "description": "Short stable label for what the doubt is about"},
            },
            "required": ["resolved", "topic"],
        },
        handler=record_doubt_attempt,
        is_ui_action=True,  # the frontend tracks doubt-open state client-side from this result
    )
)

register_tool(
    ToolDef(
        name="escalate_unresolved_doubt",
        description="Loop in a (simulated) specialist after the same doubt has gone unresolved 3 times. Always "
        "available — not gated by lead score, since this is about being stuck, not about buying. Tell the user "
        "warmly that you're connecting them; never say '3 times' or anything that sounds like a scorecard.",
        input_schema={
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "What the unresolved doubt is about"}},
            "required": ["topic"],
        },
        handler=escalate_unresolved_doubt,
        is_ui_action=True,
    )
)
