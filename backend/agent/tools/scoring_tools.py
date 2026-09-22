from sqlmodel import select

from app.constants import CONNECTION_PLATFORMS, PRO_SLOTS_PER_MARKET
from app.models import Profile
from app.scoring import COMPLETION_FIELDS, compute_score_delta, compute_total_score, is_pro_effective, simulate_total_score
from app.slots import count_pro_slot_holders

from agent.tools import ToolContext, ToolDef, register_tool


def get_score_snapshot(ctx: ToolContext, tool_input: dict) -> dict:
    return compute_total_score(ctx.profile)


def get_upsell_pitch(ctx: ToolContext, tool_input: dict) -> dict:
    score = compute_total_score(ctx.profile)
    locked = {k: v for k, v in score["categories"].items() if v["locked"]}
    taken = count_pro_slot_holders(ctx.session, ctx.profile.category, ctx.profile.location)
    return {
        "unlock_points": score["unlock_points"],
        "locked_categories": locked,
        "pro_slots": {
            "taken": taken,
            "total": PRO_SLOTS_PER_MARKET,
            "remaining": max(0, PRO_SLOTS_PER_MARKET - taken),
        },
    }


def get_peer_benchmark(ctx: ToolContext, tool_input: dict) -> dict:
    profile = ctx.profile
    peers = list(
        ctx.session.exec(
            select(Profile).where(Profile.category == profile.category, Profile.location == profile.location)
        )
    )
    pros = [p for p in peers if is_pro_effective(p)]
    claimed = [p for p in peers if p.lifecycle_state in ("claimed", "pro")]
    rank_above = sum(1 for p in peers if p.search_rank_score > profile.search_rank_score)
    top_pro = max(pros, key=lambda p: p.search_rank_score, default=None)

    return {
        "market_profile_count": len(peers),
        "avg_pro_score": round(sum(p.search_rank_score for p in pros) / len(pros)) if pros else None,
        "avg_claimed_score": round(sum(p.search_rank_score for p in claimed) / len(claimed)) if claimed else None,
        "profiles_ranked_above_you": rank_above,
        "top_pro_in_market": (
            {"name": top_pro.name, "score": top_pro.search_rank_score} if top_pro and top_pro.id != profile.id else None
        ),
    }


def get_cost_of_inaction(ctx: ToolContext, tool_input: dict) -> dict:
    """Reframes data already available elsewhere — the real website health audit plus
    which categories are locked — as 'what's actively hurting you right now', for a more
    concrete pitch than points alone. No new data, no fabrication.
    """
    profile = ctx.profile
    score = compute_total_score(profile)
    locked = {k: v for k, v in score["categories"].items() if v["locked"]}
    return {
        "has_website": bool(profile.website_url),
        "website_issues_found": score["categories"]["web_analytics"]["opportunities"] if profile.website_url else [],
        "load_time_ms": profile.website_audit.get("load_time_ms") if profile.website_audit else None,
        "locked_categories": locked,
    }


def simulate_score_change(ctx: ToolContext, tool_input: dict) -> dict:
    # Only the 4 completion fields are meaningful "what if I added X" candidates for
    # `changes` — ignore anything else (e.g. an attempt to fake lifecycle_state) rather
    # than erroring, since this never writes anywhere and the model may pass extras.
    changes = {k: v for k, v in (tool_input.get("changes") or {}).items() if k in COMPLETION_FIELDS}
    applied = dict(changes)

    if tool_input.get("reply_all_reviews"):
        changes["reviews"] = [{**r, "reply": r.get("reply") or "placeholder"} for r in ctx.profile.reviews]
        applied["reply_all_reviews"] = True

    if tool_input.get("connect_all"):
        changes["connections"] = [{"platform_name": p, "is_connected": True} for p in CONNECTION_PLATFORMS]
        applied["connect_all"] = True

    current = compute_total_score(ctx.profile)
    hypothetical = simulate_total_score(ctx.profile, changes)
    return {
        "changes_applied": applied,
        "current_total": current["total"],
        "hypothetical_total": hypothetical["total"],
        "delta": hypothetical["total"] - current["total"],
    }


def get_score_trend(ctx: ToolContext, tool_input: dict) -> dict:
    days = int(tool_input.get("days", 7))
    session = ctx.session
    profile = ctx.profile

    delta = compute_score_delta(session, profile.id, profile.search_rank_score, days=days)

    peers = list(
        session.exec(
            select(Profile).where(
                Profile.category == profile.category,
                Profile.location == profile.location,
                Profile.id != profile.id,
            )
        )
    )
    past_profile_total = profile.search_rank_score - (delta or 0)
    passed_you = 0
    for peer in peers:
        peer_delta = compute_score_delta(session, peer.id, peer.search_rank_score, days=days)
        if peer_delta is None:
            continue
        past_peer_total = peer.search_rank_score - peer_delta
        if past_peer_total <= past_profile_total and peer.search_rank_score > profile.search_rank_score:
            passed_you += 1

    return {
        "days": days,
        "current_total": profile.search_rank_score,
        "delta": delta,
        "profiles_that_passed_you": passed_you,
    }


register_tool(
    ToolDef(
        name="get_score_snapshot",
        description="Get this profile's live, exact Search Rank Score breakdown by category. Call this before "
        "stating any score/points number.",
        input_schema={"type": "object", "properties": {}},
        handler=get_score_snapshot,
    )
)

register_tool(
    ToolDef(
        name="get_upsell_pitch",
        description="Get the real, live case for upgrading to Pro: exactly how many points are locked behind Pro, "
        "which categories, and this market's real Pro slot availability.",
        input_schema={"type": "object", "properties": {}},
        handler=get_upsell_pitch,
    )
)

register_tool(
    ToolDef(
        name="simulate_score_change",
        description="See the real point impact of a hypothetical change: filling in profile-completion fields "
        "(phone_number, license_number, website_url, bio) via `changes`, replying to every unreplied review via "
        "`reply_all_reviews`, and/or connecting every platform via `connect_all`. Combine any of these in one "
        "call. Purely a live simulation, never writes anything.",
        input_schema={
            "type": "object",
            "properties": {
                "changes": {
                    "type": "object",
                    "description": "Hypothetical field values to test, e.g. {\"website_url\": \"https://example.com\"}",
                },
                "reply_all_reviews": {"type": "boolean", "description": "Simulate replying to every unreplied review"},
                "connect_all": {"type": "boolean", "description": "Simulate connecting every platform"},
            },
        },
        handler=simulate_score_change,
        is_ui_action=True,
    )
)

register_tool(
    ToolDef(
        name="get_peer_benchmark",
        description="Get real aggregate stats for other profiles in this profile's exact category+location market "
        "(average Pro score, average claimed score, how many rank above this profile, and the real top-ranked "
        "Pro profile's name/score as social proof).",
        input_schema={"type": "object", "properties": {}},
        handler=get_peer_benchmark,
    )
)

register_tool(
    ToolDef(
        name="get_cost_of_inaction",
        description="Get what's currently hurting this profile's visibility because Pro is locked — real "
        "website issues already found (slow load time, missing contact info, etc.) that they can't see or fix "
        "without Pro. Use to frame the pitch around what's actively wrong right now, not just future gains.",
        input_schema={"type": "object", "properties": {}},
        handler=get_cost_of_inaction,
    )
)

register_tool(
    ToolDef(
        name="get_score_trend",
        description="Get this profile's real score change over the last N days, and how many market peers passed "
        "it in that time. Use this instead of guessing a 'since last week' number.",
        input_schema={
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Lookback window in days, default 7"}},
        },
        handler=get_score_trend,
    )
)
