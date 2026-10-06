"""What would raise this profile's Search Rank Score, in points (core1 Process 3).

After onboarding the assistant goes through every field that earns points, including replies to
reviews, and says things like "reply to this review: +4", "add the year you started: +8", "your license
is empty: +8". Each number here comes from `simulate_total_score` with one targeted change, the same
what-if the Manage page badges and the nudge emails use, so none of it is invented. The Pro preview is
the real before/after score and market rank if Pro were on. Plain Python, no model involved.
"""

import copy

from sqlmodel import Session

from app.category_config import config_for
from app.models import Profile
from app.scoring import FIELD_ACTION_LABELS, compute_total_score, is_pro_effective, simulate_total_score
from app.slots import get_slot_status, simulate_rank

# Where each kind of step is done in the app (the page and the element the assistant can point at).
TARGETS = {
    "reply_review": ("manage", None),  # the element is review-<id>
    "fill_field": ("manage", "manage-profile-details"),
    "connect": ("manage", "manage-connections-section"),
    "publish_listing": ("manage", "manage-listings-section"),
}
KIND_ORDER = {"reply_review": 0, "fill_field": 1, "connect": 2, "publish_listing": 3}


def _item(kind: str, key: str, label: str, points: int, **extra) -> dict:
    route, target = TARGETS[kind]
    return {"kind": kind, "key": key, "label": label, "points": points, "route": route, "ui_target": target, **extra}


def _review_items(profile: Profile, current_total: int) -> list[dict]:
    items = []
    for review in profile.reviews or []:
        if review.get("reply"):
            continue
        replied = copy.deepcopy(profile.reviews)
        for r in replied:
            if r.get("id") == review.get("id"):
                r["reply"] = "placeholder reply, only used to measure the point swing"
        points = simulate_total_score(profile, {"reviews": replied})["total"] - current_total
        who = review.get("reviewer_name") or "a reviewer"
        items.append(_item("reply_review", f"review:{review.get('id')}", f"Reply to {who}'s review", points,
                           review_id=review.get("id"), ui_target=f"review-{review.get('id')}"))
    return items


def _field_items(profile: Profile, current_total: int) -> list[dict]:
    items = []
    for f in config_for(profile).basic_fields:
        if getattr(profile, f["key"], None):
            continue
        points = simulate_total_score(profile, {f["key"]: "placeholder"})["total"] - current_total
        items.append(_item("fill_field", f["key"], FIELD_ACTION_LABELS.get(f["key"], f"Add your {f['label'].lower()}"), points, field=f["key"]))
    return items


def _connection_items(profile: Profile, current_total: int) -> list[dict]:
    connections = profile.connections or []
    on = {v for c in connections if c.get("is_connected") for v in (c.get("platform_name"), c.get("platform")) if v}
    items = []
    for slot in config_for(profile).slots("social"):
        if slot["label"] in on or slot["platform"] in on:
            continue
        updated = [c for c in copy.deepcopy(connections) if c.get("platform_name") != slot["label"]]
        updated.append({"platform_name": slot["label"], "is_connected": True})
        points = simulate_total_score(profile, {"connections": updated})["total"] - current_total
        items.append(_item("connect", f"connect:{slot['platform']}", f"Connect {slot['label']}", points, platform=slot["label"]))
    return items


def _listing_items(profile: Profile, current_total: int, score: dict) -> list[dict]:
    if score["categories"].get("listings", {}).get("locked"):
        return []  # behind the paywall: it is part of the Pro preview, not a step they can take now
    listings = copy.deepcopy(profile.directory_listings or {})
    platforms = listings.get("platforms", [])
    published = {v for p in platforms if p.get("is_published") for v in (p.get("name"), p.get("platform")) if v}
    items = []
    for slot in config_for(profile).slots("directory"):
        if slot["label"] in published or slot["platform"] in published:
            continue
        updated = [p for p in copy.deepcopy(platforms) if p.get("name") != slot["label"]]
        updated.append({"name": slot["label"], "is_published": True})
        points = simulate_total_score(profile, {"directory_listings": {"platforms": updated}})["total"] - current_total
        items.append(_item("publish_listing", f"listing:{slot['platform']}", f"Publish your listing on {slot['label']}", points, platform=slot["label"]))
    return items


def _pro_preview(session: Session, profile: Profile, score: dict, rank: dict) -> dict:
    if is_pro_effective(profile):
        return {"available": False, "reason": "already_pro"}
    as_pro = simulate_total_score(profile, {"lifecycle_state": "pro"})
    as_pro_rank = simulate_rank(session, profile, as_pro["total"])
    locked = [{"key": k, "label": c["label"], "earned": c["earned"], "max": c["max"]} for k, c in score["categories"].items() if c["locked"]]
    slots = get_slot_status(session, profile)
    return {
        "available": bool(locked),
        "score_before": score["total"],
        "score_after": as_pro["total"],
        "points_gained": as_pro["total"] - score["total"],
        "max_before": score["max_possible"],
        "max_after": as_pro["max_possible"],
        "rank_before": rank["rank_position"],
        "rank_after": as_pro_rank["rank_position"],
        "rank_total": as_pro_rank["rank_total"],
        "locked_sections": locked,
        "slots": {"taken": slots["taken"], "total": slots["total"], "remaining": slots["remaining"], "is_full": slots["is_full"]},
    }


def build_improvement_plan(session: Session, profile: Profile) -> dict:
    score = compute_total_score(profile)
    rank = simulate_rank(session, profile, score["total"])
    items = (
        _review_items(profile, score["total"])
        + _field_items(profile, score["total"])
        + _connection_items(profile, score["total"])
        + _listing_items(profile, score["total"], score)
    )
    items = [i for i in items if i["points"] > 0]
    items.sort(key=lambda i: (-i["points"], KIND_ORDER[i["kind"]]))  # biggest win first; stable within a tie
    return {
        "score": {"total": score["total"], "max_possible": score["max_possible"], "category": score["category"]},
        "rank": rank,
        "items": items,
        "reachable_points": sum(i["points"] for i in items),
        "pro": _pro_preview(session, profile, score, rank),
    }
