from datetime import datetime, timedelta

from sqlmodel import select

from app.constants import MARKET_REGIONS, PRO_SLOTS_PER_MARKET
from app.models import MarketEvent, Profile
from app.routers.manage import perform_join_waitlist
from app.slots import count_pro_slot_holders, has_open_slot

from agent.tools import ToolContext, ToolDef, register_tool

RECENT_EVENT_WINDOW_DAYS = 3


def get_nearby_market_opportunities(ctx: ToolContext, tool_input: dict) -> dict:
    profile = ctx.profile
    region = next((name for name, locations in MARKET_REGIONS.items() if profile.location in locations), None)
    if region is None:
        return {"region": None, "nearby_markets": []}

    nearby = []
    for location in MARKET_REGIONS[region]:
        if location == profile.location:
            continue
        taken = count_pro_slot_holders(ctx.session, profile.category, location)
        nearby.append(
            {
                "location": location,
                "pro_slots_taken": taken,
                "pro_slots_total": PRO_SLOTS_PER_MARKET,
                "pro_slots_remaining": max(0, PRO_SLOTS_PER_MARKET - taken),
            }
        )
    return {"region": region, "nearby_markets": nearby}


def join_pro_waitlist(ctx: ToolContext, tool_input: dict) -> dict:
    if not tool_input.get("confirmed"):
        return {"error": "not_confirmed", "message": "Ask the user to explicitly confirm before calling this again."}
    if has_open_slot(ctx.session, ctx.profile.category, ctx.profile.location):
        return {"error": "market_not_full", "message": "This market has an open slot — upgrade directly instead."}
    return perform_join_waitlist(ctx.session, ctx.profile)


def get_recent_market_events(ctx: ToolContext, tool_input: dict) -> dict:
    """Real, recent competitive activity in this profile's own market — someone
    else taking a scarce Pro slot. Excludes this profile's own actions.
    """
    cutoff = datetime.utcnow() - timedelta(days=RECENT_EVENT_WINDOW_DAYS)
    events = ctx.session.exec(
        select(MarketEvent)
        .where(
            MarketEvent.category == ctx.profile.category,
            MarketEvent.location == ctx.profile.location,
            MarketEvent.created_at >= cutoff,
            MarketEvent.profile_id != ctx.profile.id,
        )
        .order_by(MarketEvent.created_at.desc())
    ).all()

    results = []
    for event in events:
        other = ctx.session.get(Profile, event.profile_id)
        results.append(
            {
                "event_type": event.event_type,
                "profile_name": other.name if other else "A competitor",
                "created_at": str(event.created_at),
            }
        )
    return {"events": results}


register_tool(
    ToolDef(
        name="get_recent_market_events",
        description="Check for real, recent competitive activity in this profile's own market (another profile "
        "going Pro or starting a trial in the last few days) — a real, honest reason for urgency, not manufactured.",
        input_schema={"type": "object", "properties": {}},
        handler=get_recent_market_events,
    )
)

register_tool(
    ToolDef(
        name="join_pro_waitlist",
        description="Join this profile's market's Pro waitlist. Only call this when the market is actually full "
        "and the user has explicitly confirmed (confirmed=true).",
        input_schema={
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
        },
        handler=join_pro_waitlist,
    )
)

register_tool(
    ToolDef(
        name="get_nearby_market_opportunities",
        description="Get real Pro slot availability in markets near this profile's own (same category, same "
        "region). Use this only if the profile's service area plausibly extends beyond its home market.",
        input_schema={"type": "object", "properties": {}},
        handler=get_nearby_market_opportunities,
    )
)
