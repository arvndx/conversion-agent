from app.scoring import compute_total_score, simulate_total_score
from app.slots import simulate_rank

from agent.tools import ToolContext, ToolDef, register_tool
from agent.tour_script import ROUTE_PATH_TEMPLATES

# The data-agent-target values that actually exist in the frontend, and which page each
# one lives on. Kept here (not just in JSX) so the tool itself — not the model's guess
# about "the page the user is looking at" — decides whether a navigation is needed.
TARGET_ROUTES = {
    "score-gauge": "dashboard",
    "upsell-web_analytics": "dashboard",
    "upsell-listings": "dashboard",
    "category-reviews": "dashboard",
    "category-profile_completion": "dashboard",
    "category-connections": "dashboard",
    "category-web_analytics": "dashboard",
    "category-listings": "dashboard",
    "trial-badge": "dashboard",
    "pro-slot-status": "manage",
    "manage-profile-details": "manage",
    "manage-reviews-section": "manage",
    "manage-connections-section": "manage",
    "manage-listings-section": "manage",
    "manage-analytics-section": "manage",
    "pricing-card": "upgrade",
}
KNOWN_TARGETS = list(TARGET_ROUTES.keys())


def highlight_ui(ctx: ToolContext, tool_input: dict) -> dict:
    target = tool_input.get("target") or ""
    route_suffix = TARGET_ROUTES.get(target) or ("manage" if target.startswith("review-") else None)
    route = ROUTE_PATH_TEMPLATES[route_suffix].format(id=ctx.profile.id) if route_suffix else None
    return {"target": target, "reason": tool_input.get("reason"), "route": route}


def navigate_to(ctx: ToolContext, tool_input: dict) -> dict:
    profile_id = ctx.profile.id
    allowed_paths = {
        f"/profile/{profile_id}",
        f"/dashboard/{profile_id}",
        f"/dashboard/{profile_id}/manage",
        f"/dashboard/{profile_id}/upgrade",
        f"/claim/{profile_id}/details",
        "/inbox",
    }
    path = tool_input.get("path", "")
    if path not in allowed_paths:
        return {"error": "path not allowed for this profile", "allowed": sorted(allowed_paths)}
    return {"path": path}


def celebrate(ctx: ToolContext, tool_input: dict) -> dict:
    return {"message": tool_input.get("message", "")}


def preview_pro_card(ctx: ToolContext, tool_input: dict) -> dict:
    profile = ctx.profile
    current = compute_total_score(profile)
    current_rank = simulate_rank(ctx.session, profile, current["total"])

    hypothetical = simulate_total_score(profile, {"lifecycle_state": "pro"})
    hypothetical_rank = simulate_rank(ctx.session, profile, hypothetical["total"])

    return {
        "current": {"total": current["total"], "max_possible": current["max_possible"], **current_rank},
        "as_pro": {"total": hypothetical["total"], "max_possible": hypothetical["max_possible"], **hypothetical_rank},
    }


register_tool(
    ToolDef(
        name="highlight_ui",
        description="Visually highlight a specific known element for the user — automatically navigates them "
        "to whichever page that element actually lives on first, so you can call this directly regardless of "
        f"what page they're currently on; no separate navigate_to needed. Known targets: {', '.join(KNOWN_TARGETS)}, "
        "or 'review-<id>' for a specific review from get_unreplied_reviews.",
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "One of the known target names"},
                "reason": {"type": "string", "description": "Optional short reason, shown as a tooltip"},
            },
            "required": ["target"],
        },
        handler=highlight_ui,
        is_ui_action=True,
    )
)

register_tool(
    ToolDef(
        name="navigate_to",
        description="Send the user to a specific page in the app. Only paths belonging to this profile are "
        "allowed — you cannot navigate to another profile's pages.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        handler=navigate_to,
        is_ui_action=True,
    )
)

register_tool(
    ToolDef(
        name="preview_pro_card",
        description="Show the user a live before/after preview of their score and market rank as they are now "
        "vs. hypothetically as Pro. Grounded in simulate_total_score's real math, not a guess.",
        input_schema={"type": "object", "properties": {}},
        handler=preview_pro_card,
        is_ui_action=True,
    )
)

register_tool(
    ToolDef(
        name="celebrate",
        description="Trigger a small celebratory animation — use for a genuine win (e.g. profile fully "
        "completed, first review replied to), not for routine actions.",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
        handler=celebrate,
        is_ui_action=True,
    )
)
