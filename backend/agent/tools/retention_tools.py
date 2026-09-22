from app.leads import is_hot_lead
from app.models import ExecutiveHandoffRequest, MockEmail
from app.pricing import get_active_offer as _get_active_offer

from agent.tools import ToolContext, ToolDef, register_tool


def get_active_offer(ctx: ToolContext, tool_input: dict) -> dict:
    return _get_active_offer(ctx.profile)


def check_handoff_eligibility(ctx: ToolContext, tool_input: dict) -> dict:
    # Deliberately returns only a boolean — never the raw visit count — so the
    # model can't quote an internal lead-scoring number to the user.
    return {"eligible": is_hot_lead(ctx.profile)}


def request_executive_handoff(ctx: ToolContext, tool_input: dict) -> dict:
    if not is_hot_lead(ctx.profile):
        return {
            "error": "not_eligible",
            "message": "This user doesn't qualify for handoff yet — keep helping them yourself. Do not tell "
            "the user they don't qualify.",
        }

    reason = tool_input.get("reason", "User requested help from a customer executive")
    request = ExecutiveHandoffRequest(profile_id=ctx.profile.id, reason=reason)
    ctx.session.add(request)
    ctx.session.add(
        MockEmail(
            to_email=ctx.profile.email,
            subject="We're on it — a ClearRank team member will follow up",
            body_html=(
                f"<p>Hi {ctx.profile.name},</p>"
                f"<p>Thanks for reaching out. A member of our team will follow up with you shortly to help with: "
                f"{reason}.</p>"
            ),
            profile_id=ctx.profile.id,
        )
    )
    ctx.session.commit()
    return {"requested": True}


register_tool(
    ToolDef(
        name="get_active_offer",
        description="Get this profile's current retention discount, if any (percent, code, expiry). Never invent "
        "a discount — only state one this tool actually returns.",
        input_schema={"type": "object", "properties": {}},
        handler=get_active_offer,
    )
)

register_tool(
    ToolDef(
        name="check_handoff_eligibility",
        description="Check whether this user currently qualifies to be connected to a human customer executive. "
        "Call this before offering a handoff — if not eligible, keep helping the user yourself and never mention "
        "eligibility to them.",
        input_schema={"type": "object", "properties": {}},
        handler=check_handoff_eligibility,
    )
)

register_tool(
    ToolDef(
        name="request_executive_handoff",
        description="Connect this user to a human customer executive. Only succeeds if they're eligible (check "
        "first) — call this only after the user has asked for human help and you've confirmed eligibility.",
        input_schema={
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "Brief reason for the handoff"}},
            "required": ["reason"],
        },
        handler=request_executive_handoff,
    )
)
