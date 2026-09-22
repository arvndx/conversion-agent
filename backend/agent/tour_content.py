"""Pre-computes real data AND pre-generates narration text for every tour step in one
shot, so stepping through the tour afterward is instant (no per-step model round-trip).

Data gathering is plain Python (direct calls into the same functions the live tools use
— zero LLM involvement, so it's effectively free). Narration is exactly one Claude call
covering all 7 steps at once, grounded strictly in that pre-gathered data.
"""

import json

from app.constants import CONNECTION_PLATFORMS
from app.scoring import COMPLETION_FIELDS, compute_total_score, simulate_total_score

from agent.config import AGENT_MODEL, get_client
from agent.tools import ToolContext
from agent.tools.retention_tools import get_active_offer
from agent.tools.review_tools import get_unreplied_reviews
from agent.tools.scarcity_tools import get_nearby_market_opportunities
from agent.tools.scoring_tools import get_cost_of_inaction, get_peer_benchmark, get_upsell_pitch
from agent.tools.ui_tools import preview_pro_card
from agent.tour_script import ROUTE_PATH_TEMPLATES, TOUR_STEPS

NARRATION_SYSTEM_PROMPT = """You write copy for a guided product tour inside ClearRank, a search-ranking \
dashboard for local service professionals. This text renders in a small callout anchored right next to the \
highlighted element on screen — not a chat message — so it must be genuinely crisp, not a paragraph.

You will be given real, already-computed data for 7 tour steps, in order. For EACH step, write ONE short \
sentence — max ~18 words — that states the single most important real number/fact given and, where relevant, \
what it means for them (e.g. "Reviews & Replies is your biggest category — 143 of 300 points earned so far."). \
No preamble ("Let's look at..."), no restating what a tour is, no closing transition line. Just the one \
concrete, useful sentence.
- Use the real numbers given exactly as given — never round differently, invent, or omit the headline fact.
- Never write two sentences. One only.

Call submit_tour_narrations exactly once with all 7 steps filled in, covering every id given: overview, \
reviews, profile_completion, connections, web_analytics, listings, wrap_up — in that order.
"""

_STEP_IDS = [s["id"] for s in TOUR_STEPS]

# A forced tool call, not free-text JSON parsing: Claude's raw prose-JSON output can drift
# into an invalid shape often enough to matter (missing comma, a step's id used as a nested
# key instead of a sibling field, etc.) — structured tool arguments don't have that failure
# mode, so this is the actual fix, not just a stricter prompt.
SUBMIT_NARRATIONS_TOOL = {
    "name": "submit_tour_narrations",
    "description": "Submit the written narration text for all 7 tour steps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": _STEP_IDS},
                        "text": {"type": "string"},
                    },
                    "required": ["id", "text"],
                },
                "minItems": len(_STEP_IDS),
                "maxItems": len(_STEP_IDS),
            }
        },
        "required": ["steps"],
    },
}


def _gather_step_data(ctx: ToolContext) -> dict:
    profile = ctx.profile
    current = compute_total_score(profile)

    missing_fields = [f for f in COMPLETION_FIELDS if not getattr(profile, f)]
    completion_hypo = (
        simulate_total_score(profile, {f: "provided" for f in missing_fields}) if missing_fields else None
    )

    unreplied = get_unreplied_reviews(ctx, {})["unreplied_reviews"]
    reviews_hypo = (
        simulate_total_score(
            profile, {"reviews": [{**r, "reply": r.get("reply") or "placeholder"} for r in profile.reviews]}
        )
        if unreplied
        else None
    )

    connections_hypo = simulate_total_score(
        profile, {"connections": [{"platform_name": p, "is_connected": True} for p in CONNECTION_PLATFORMS]}
    )

    return {
        "overview": current,
        "reviews": {
            "current_points": current["categories"]["reviews"],
            "unreplied_reviews": unreplied,
            "if_all_replied": {
                "reviews_category_points": reviews_hypo["categories"]["reviews"]["earned"] if reviews_hypo else None,
                "new_total": reviews_hypo["total"] if reviews_hypo else None,
            },
        },
        "profile_completion": {
            "current_points": current["categories"]["profile_completion"],
            "missing_fields": missing_fields,
            "if_completed": {
                "profile_completion_category_points": (
                    completion_hypo["categories"]["profile_completion"]["earned"] if completion_hypo else None
                ),
                "new_total": completion_hypo["total"] if completion_hypo else None,
            },
        },
        "connections": {
            "current_points": current["categories"]["connections"],
            "if_all_connected": {
                "connections_category_points": connections_hypo["categories"]["connections"]["earned"],
                "new_total": connections_hypo["total"],
            },
        },
        "web_analytics": {
            "upsell": get_upsell_pitch(ctx, {}),
            "preview": preview_pro_card(ctx, {}),
            "website_audit_findings": get_cost_of_inaction(ctx, {}),
        },
        "listings": {
            "current_points": current["categories"]["listings"],
        },
        "wrap_up": {
            "current_total": current["total"],
            "benchmark": get_peer_benchmark(ctx, {}),
            "preview": preview_pro_card(ctx, {}),
            "nearby_markets": get_nearby_market_opportunities(ctx, {}),
            "offer": get_active_offer(ctx, {}),
        },
    }


def _generate_narrations(data: dict) -> dict[str, str]:
    client = get_client()
    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=1500,
        system=NARRATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(data)}],
        tools=[SUBMIT_NARRATIONS_TOOL],
        tool_choice={"type": "tool", "name": "submit_tour_narrations"},
    )
    tool_use = next(block for block in response.content if block.type == "tool_use")
    # Schema-conformant tool input isn't unconditionally guaranteed — an occasional
    # malformed item shouldn't crash the whole tour. build_tour_steps already falls back
    # to generic per-step text for any id missing here, so skipping a bad item is safe.
    narrations = {}
    for item in tool_use.input.get("steps", []):
        if isinstance(item, dict) and "id" in item and "text" in item:
            narrations[item["id"]] = item["text"]
    return narrations


def _resolve_step_meta(step: dict, profile) -> dict:
    resolved = dict(step)
    resolved["route"] = ROUTE_PATH_TEMPLATES[step["route"]].format(id=profile.id)
    return resolved


def build_tour_steps(ctx: ToolContext) -> list[dict]:
    """The full, ready-to-display tour: real data gathered directly, narrations
    generated in one Claude call, merged with each step's static route/highlight
    metadata. Callers just index into this list — no further backend calls needed
    to advance from one step to the next.
    """
    data = _gather_step_data(ctx)
    narrations = _generate_narrations(data)

    unreplied = data["reviews"]["unreplied_reviews"]
    reviews_target = f"review-{unreplied[0]['review_id']}" if unreplied else "manage-reviews-section"

    steps = []
    for i, step in enumerate(TOUR_STEPS):
        meta = _resolve_step_meta(step, ctx.profile)
        if step["id"] == "reviews":
            meta["ui_target"] = reviews_target
        steps.append(
            {
                "step_number": i + 1,
                "total_steps": len(TOUR_STEPS),
                "id": meta["id"],
                "title": meta["title"],
                "ui_target": meta["ui_target"],
                "route": meta["route"],
                "text": narrations.get(step["id"]) or f"Let's take a look at {meta['title']}.",
            }
        )
    return steps
