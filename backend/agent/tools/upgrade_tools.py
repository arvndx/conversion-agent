from app.pricing import MONTHLY_PRICE_USD, get_active_offer
from app.routers.manage import TRIAL_DURATION_DAYS, perform_start_trial, perform_upgrade
from app.slots import has_open_slot

from agent.tools import ToolContext, ToolDef, register_tool

# A proposal stays open for this many of the user's turns; after that it must be proposed again.
PROPOSAL_TURNS = 3


def _needs_consent(ctx: ToolContext, action: str, tool_input: dict) -> dict | None:
    """Paid actions are consented to in two steps, enforced here rather than left to the model: the first call
    only records a proposal and returns the price to tell the user; the action runs only when it is called
    again with confirmed=true in a LATER user turn. "Upgrade me" alone is a request, not yet consent to a price."""
    conv = ctx.conversation
    open_proposal = (
        conv.pending_action == action and 0 < conv.turn_count - conv.pending_turn <= PROPOSAL_TURNS
    )
    if tool_input.get("confirmed") and open_proposal:
        conv.pending_action, conv.pending_turn = None, 0
        ctx.session.add(conv)
        ctx.session.commit()
        return None
    conv.pending_action, conv.pending_turn = action, conv.turn_count
    ctx.session.add(conv)
    ctx.session.commit()
    terms = {"monthly_price_usd": MONTHLY_PRICE_USD, "offer": get_active_offer(ctx.profile)}
    if action == "trial":
        terms["trial_days"] = TRIAL_DURATION_DAYS
    return {
        "error": "needs_confirmation",
        "action": action,
        **terms,
        "message": "Nothing has happened yet. Tell the user exactly what this is (the price and any active discount, or the "
        "trial length) and ask whether to go ahead. Call this tool again with confirmed=true only after they answer "
        "yes in their NEXT message.",
    }


def _refused(attempt, error: str) -> dict:
    """Run an action the app is going to refuse (a full market) and report why, in the shape the model already knows."""
    try:
        attempt()
    except Exception as exc:  # HTTPException market_full
        return {"error": error, "detail": getattr(exc, "detail", str(exc))}
    return {"error": error, "detail": "refused"}


def confirm_and_upgrade_to_pro(ctx: ToolContext, tool_input: dict) -> dict:
    if ctx.profile.lifecycle_state != "claimed":
        return {"error": "not_eligible", "lifecycle_state": ctx.profile.lifecycle_state}
    if not has_open_slot(ctx.session, ctx.profile.category, ctx.profile.location):
        return _refused(lambda: perform_upgrade(ctx.session, ctx.profile), "upgrade_failed")  # full market: no price to quote
    pending = _needs_consent(ctx, "upgrade", tool_input)
    if pending:
        return pending

    try:
        summary = perform_upgrade(ctx.session, ctx.profile)
    except Exception as exc:  # HTTPException from perform_upgrade (e.g. market_full)
        detail = getattr(exc, "detail", str(exc))
        return {"error": "upgrade_failed", "detail": detail}

    return {"upgraded": True, "new_score": summary["score"]}


def start_pro_trial(ctx: ToolContext, tool_input: dict) -> dict:
    if ctx.profile.lifecycle_state == "claimed" and not has_open_slot(ctx.session, ctx.profile.category, ctx.profile.location):
        return _refused(lambda: perform_start_trial(ctx.session, ctx.profile), "trial_failed")
    pending = _needs_consent(ctx, "trial", tool_input)
    if pending:
        return pending

    try:
        summary = perform_start_trial(ctx.session, ctx.profile)
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        return {"error": "trial_failed", "detail": detail}

    return {"trial_started": True, "trial_ends_at": str(ctx.profile.trial_ends_at), "new_score": summary["score"]}


register_tool(
    ToolDef(
        name="confirm_and_upgrade_to_pro",
        description="Upgrade this profile to Pro (a paid plan). Two steps, enforced by the app: the first call (even "
        "with confirmed=true) only returns the price and terms to tell the user, and nothing happens; call it again "
        "with confirmed=true only after they say yes in their NEXT message. Even a clear request like \"upgrade me\" "
        "needs that price-and-yes step. Fails cleanly if the profile isn't claimed or the market is full (offer the "
        "waitlist then).",
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
        description="Start a free 7-day Pro trial. Same two steps as the upgrade, enforced by the app: the first call "
        "returns the terms and starts nothing; call again with confirmed=true after they say yes in their NEXT message. "
        "Fails cleanly if the market is full.",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
        },
        handler=start_pro_trial,
    )
)
