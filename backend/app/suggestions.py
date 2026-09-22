"""Computes the Manage page's post-tour suggestion badges — one concrete, real next
action per section, each with an honest point value (and rank preview where relevant)
derived the same way the what-if simulator and nudge emails already do: simulate_total_score
with a targeted override, never an invented number. Plain Python, no LLM involved.
"""

import copy

from sqlmodel import Session

from app.models import Profile
from app.scoring import compute_total_score, is_pro_effective, simulate_total_score
from app.slots import simulate_rank


def _unreplied_reviews(profile: Profile) -> list[dict]:
    return [r for r in profile.reviews if not r.get("reply")]


def _reviews_suggestion(profile: Profile, current_total: int) -> dict:
    unreplied = _unreplied_reviews(profile)
    if not unreplied:
        return {"available": False}

    items = []
    for target in unreplied:
        new_reviews = copy.deepcopy(profile.reviews)
        for r in new_reviews:
            if r.get("id") == target.get("id"):
                r["reply"] = "placeholder reply, only used to measure the point swing"
                break
        hypothetical = simulate_total_score(profile, {"reviews": new_reviews})
        items.append(
            {
                "review_id": target.get("id"),
                "reviewer_name": target.get("reviewer_name"),
                "review_body": target.get("body"),
                "points": hypothetical["total"] - current_total,
            }
        )
    return {"available": True, "items": items}


def _profile_completion_suggestion(profile: Profile, current_total: int) -> dict:
    if profile.license_number:
        return {"available": False}
    hypothetical = simulate_total_score(profile, {"license_number": "placeholder"})
    return {
        "available": True,
        "field": "license_number",
        "label": "Add your license number",
        "points": hypothetical["total"] - current_total,
    }


def _connections_suggestion(profile: Profile, current_total: int) -> dict:
    connections = profile.connections or []
    if any(c["platform_name"] == "Facebook" and c.get("is_connected") for c in connections):
        return {"available": False}

    new_connections = copy.deepcopy(connections)
    for c in new_connections:
        if c["platform_name"] == "Facebook":
            c["is_connected"] = True
            break
    else:
        new_connections.append({"platform_name": "Facebook", "is_connected": True})
    hypothetical = simulate_total_score(profile, {"connections": new_connections})
    return {
        "available": True,
        "platform": "Facebook",
        "points": hypothetical["total"] - current_total,
    }


def _web_analytics_suggestion(session: Session, profile: Profile, current: dict, current_rank: int) -> dict:
    category = current["categories"]["web_analytics"]
    if not category["locked"] or category["earned"] <= 0:
        return {"available": False}

    hypothetical_total = current["total"] + category["earned"]
    rank = simulate_rank(session, profile, hypothetical_total)
    return {
        "available": True,
        "points": category["earned"],
        "rank_from": current_rank,
        "rank_to": rank["rank_position"],
        "rank_total": rank["rank_total"],
    }


def _listings_suggestion(profile: Profile, current_total: int) -> dict:
    # Only actionable once Pro-effective — the toggle itself is hidden behind the paywall
    # for everyone else, so suggesting it earlier would point at a button that doesn't exist.
    if not is_pro_effective(profile):
        return {"available": False}

    platforms = (profile.directory_listings or {}).get("platforms", [])
    if any(p["name"] == "Google Business Profile" and p.get("is_published") for p in platforms):
        return {"available": False}

    new_platforms = copy.deepcopy(platforms)
    for p in new_platforms:
        if p["name"] == "Google Business Profile":
            p["is_published"] = True
            break
    else:
        new_platforms.append({"name": "Google Business Profile", "is_published": True})
    hypothetical = simulate_total_score(profile, {"directory_listings": {"platforms": new_platforms}})
    return {
        "available": True,
        "platform": "Google Business Profile",
        "points": hypothetical["total"] - current_total,
    }


def _total_unlock_suggestion(session: Session, profile: Profile, current: dict, current_rank: int) -> dict:
    if current["unlock_points"] <= 0:
        return {"available": False}

    hypothetical_total = current["total"] + current["unlock_points"]
    rank = simulate_rank(session, profile, hypothetical_total)
    return {
        "available": True,
        "points": current["unlock_points"],
        "rank_from": current_rank,
        "rank_to": rank["rank_position"],
        "rank_total": rank["rank_total"],
    }


def build_suggestions(session: Session, profile: Profile) -> dict:
    current = compute_total_score(profile)
    current_total = current["total"]
    current_rank = simulate_rank(session, profile, current_total)["rank_position"]

    return {
        "reviews": _reviews_suggestion(profile, current_total),
        "profile_completion": _profile_completion_suggestion(profile, current_total),
        "connections": _connections_suggestion(profile, current_total),
        "web_analytics": _web_analytics_suggestion(session, profile, current, current_rank),
        "listings": _listings_suggestion(profile, current_total),
        "total_unlock": _total_unlock_suggestion(session, profile, current, current_rank),
    }
