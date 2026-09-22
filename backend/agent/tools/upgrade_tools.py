from app.routers.manage import perform_start_trial, perform_upgrade

from agent.tools import ToolContext, ToolDef, register_tool


def confirm_and_upgrade_to_pro(ctx: ToolContext, tool_input: dict) -> dict:
    if not tool_input.get("confirmed"):
        return {"error": "not_confirmed", "message": "Ask the user to explicitly confirm before calling this again."}
    if ctx.profile.lifecycle_state != "claimed":
        return {"error": "not_eligible", "lifecycle_state": ctx.profile.lifecycle_state}

    try:
        summary = perform_upgrade(ctx.session, ctx.profile)
    except Exception as exc:  # HTTPException from perform_upgrade (e.g. market_full)
        detail = getattr(exc, "detail", str(exc))
        return {"error": "upgrade_failed", "detail": detail}

    return {"upgraded": True, "new_score": summary["score"]}


def start_pro_trial(ctx: ToolContext, tool_input: dict) -> dict:
    if not tool_input.get("confirmed"):
        return {"error": "not_confirmed", "message": "Ask the user to explicitly confirm before calling this again."}

    try:
        summary = perform_start_trial(ctx.session, ctx.profile)
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        return {"error": "trial_failed", "detail": detail}

    return {"trial_started": True, "trial_ends_at": str(ctx.profile.trial_ends_at), "new_score": summary["score"]}


register_tool(
    ToolDef(
        name="confirm_and_upgrade_to_pro",
        description="Actually upgrade this profile to Pro. Only call this after the user has explicitly said yes "
        "in this conversation — pass confirmed=true only at that point. Will fail cleanly if the profile isn't "
        "claimed or the market is full (offer the waitlist in that case).",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
        },
        handler=confirm_and_upgrade_to_pro,
    )
)

register_tool(
    ToolDef(
        name="start_pro_trial",
        description="Start a free 7-day Pro trial for this profile. Only call this after explicit user "
        "confirmation (confirmed=true). Will fail cleanly if the market is full.",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
        },
        handler=start_pro_trial,
    )
)
