from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlmodel import select

from app.constants import (
    CATEGORY_META,
    CLAIMED_MAX_SCORE,
    CONNECTION_PLATFORMS,
    DIRECTORY_PLATFORMS,
    PRO_MAX_SCORE,
)

COMPLETION_FIELDS = [
    "phone_number",
    "license_number",
    "website_url",
    "bio",
    "service_area",
    "products_services",
    "specialities",
    "memberships",
    "year_started",
    "achievements",
    "hobbies",
]

# The exact set of fields compute_total_score's category functions read from a
# profile-like object. Used to build a detached shadow copy for what-if scoring
# (simulate_total_score) without touching the real ORM-tracked row.
SCORING_INPUT_FIELDS = [
    "reviews",
    "connections",
    "website_audit",
    "directory_listings",
    "lifecycle_state",
    "trial_ends_at",
    *COMPLETION_FIELDS,
]


def is_pro_effective(profile) -> bool:
    """True if `profile` currently gets Pro-tier benefits — either real Pro or
    an active trial. Shared by scoring, slot-capacity counting, and any route
    that gates a Pro-only action, so trial support never has to be special-cased
    in more than one place.
    """
    if profile.lifecycle_state == "pro":
        return True
    trial_ends_at = getattr(profile, "trial_ends_at", None)
    return bool(trial_ends_at and trial_ends_at > datetime.utcnow())


def compute_reviews_score(profile):
    reviews = profile.reviews
    if not reviews:
        return 0, ["Request your first review to start earning Reviews & Replies points"]

    total = len(reviews)
    replied = sum(1 for r in reviews if r.get("reply"))
    avg_rating = sum(r.get("rating", 0) for r in reviews) / total

    volume_score = min(total, 10) / 10 * 100
    rating_score = (avg_rating / 5) * 100
    reply_score = (replied / total) * 100

    points = round(volume_score + rating_score + reply_score)

    opportunities = []
    if replied < total:
        opportunities.append(f"Reply to {total - replied} unanswered review(s)")
    if total < 10:
        opportunities.append("Request more reviews to boost your volume score")
    if avg_rating < 5:
        opportunities.append("Improve service quality to raise your average rating")

    return points, opportunities


def compute_profile_completion_score(profile):
    filled = [f for f in COMPLETION_FIELDS if getattr(profile, f)]
    missing = [f for f in COMPLETION_FIELDS if not getattr(profile, f)]
    points = round(len(filled) / len(COMPLETION_FIELDS) * 100)

    labels = {
        "phone_number": "Add a phone number",
        "license_number": "Add your license number",
        "website_url": "Add your website",
        "bio": "Write your description",
        "service_area": "Add your primary serving area",
        "products_services": "List your products & services",
        "specialities": "Add your specialities",
        "memberships": "Add your professional memberships",
        "year_started": "Add the year you started",
        "achievements": "Add your achievements",
        "hobbies": "Add a personal touch with hobbies",
    }
    opportunities = [labels[f] for f in missing]

    return points, opportunities


def compute_connections_score(profile):
    connected = {c["platform_name"] for c in profile.connections if c.get("is_connected")}
    missing = [p for p in CONNECTION_PLATFORMS if p not in connected]
    points = round(len(connected) / len(CONNECTION_PLATFORMS) * 100)

    opportunities = [f"Connect {p}" for p in missing]

    return points, opportunities


WEBSITE_AUDIT_LOAD_TIME_THRESHOLD_MS = 2500
POINTS_PER_AUDIT_CHECK = 50  # 5 checks x 50 = 250, matching CATEGORY_META["web_analytics"]["max"]


def compute_web_analytics_score(profile):
    """A real audit of the professional's own website (not ClearRank listing traffic):
    does it have the basics a patient or search engine needs — a fast load time, mobile
    support, visible contact info and hours, a meta description for search snippets.
    """
    if not profile.website_url:
        return 0, ["Add your website so we can audit it for visibility issues"]

    audit = profile.website_audit
    points = 0
    opportunities = []

    if audit.get("has_meta_description"):
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append("Add a meta description to your website for better search snippets")

    if audit.get("mobile_friendly"):
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append("Make your website mobile-friendly — most patients search on their phone")

    load_time_ms = audit.get("load_time_ms")
    if load_time_ms is not None and load_time_ms <= WEBSITE_AUDIT_LOAD_TIME_THRESHOLD_MS:
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append(f"Speed up your website ({load_time_ms}ms load time) — slow pages lose visitors")

    if audit.get("has_contact_info"):
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append("Make sure your phone number and address are clearly listed on your website")

    if audit.get("has_business_hours_listed"):
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append("List your business hours clearly on your website")

    return points, opportunities


def compute_listings_score(profile):
    published = {
        p["name"] for p in profile.directory_listings.get("platforms", []) if p.get("is_published")
    }
    missing = [p for p in DIRECTORY_PLATFORMS if p not in published]
    points = round(len(published) / len(DIRECTORY_PLATFORMS) * 100)

    opportunities = [f"Publish your listing on {p}" for p in missing]

    return points, opportunities


def compute_total_score(profile):
    is_pro = is_pro_effective(profile)

    reviews_pts, reviews_opps = compute_reviews_score(profile)
    completion_pts, completion_opps = compute_profile_completion_score(profile)
    connections_pts, connections_opps = compute_connections_score(profile)
    web_pts, web_opps = compute_web_analytics_score(profile)
    listings_pts, listings_opps = compute_listings_score(profile)

    categories = {
        "reviews": {
            "label": CATEGORY_META["reviews"]["label"],
            "earned": reviews_pts,
            "max": CATEGORY_META["reviews"]["max"],
            "locked": False,
            "opportunities": reviews_opps,
        },
        "profile_completion": {
            "label": CATEGORY_META["profile_completion"]["label"],
            "earned": completion_pts,
            "max": CATEGORY_META["profile_completion"]["max"],
            "locked": False,
            "opportunities": completion_opps,
        },
        "connections": {
            "label": CATEGORY_META["connections"]["label"],
            "earned": connections_pts,
            "max": CATEGORY_META["connections"]["max"],
            "locked": False,
            "opportunities": connections_opps,
        },
        "web_analytics": {
            "label": CATEGORY_META["web_analytics"]["label"],
            "earned": web_pts,
            "max": CATEGORY_META["web_analytics"]["max"],
            "locked": not is_pro,
            "opportunities": web_opps,
        },
        "listings": {
            "label": CATEGORY_META["listings"]["label"],
            "earned": listings_pts,
            "max": CATEGORY_META["listings"]["max"],
            "locked": not is_pro,
            "opportunities": listings_opps,
        },
    }

    total = sum(c["earned"] for c in categories.values() if not c["locked"])
    unlock_points = sum(c["earned"] for c in categories.values() if c["locked"])
    max_possible = PRO_MAX_SCORE if is_pro else CLAIMED_MAX_SCORE

    return {
        "total": total,
        "max_possible": max_possible,
        "lifecycle_state": profile.lifecycle_state,
        "categories": categories,
        "unlock_points": unlock_points,
    }


def simulate_total_score(profile, overrides: dict):
    """Score a hypothetical version of `profile` with `overrides` applied, without
    touching the database or the real ORM-tracked object. Used for the what-if
    simulator, the nudge-email engine, and the Pro-card preview — one shared
    implementation so none of them can drift from how scoring actually works.
    """
    shadow = SimpleNamespace(**{field: getattr(profile, field) for field in SCORING_INPUT_FIELDS})
    for field, value in overrides.items():
        setattr(shadow, field, value)
    return compute_total_score(shadow)


def compute_score_delta(session, profile_id: int, current_total: int, days: int = 7) -> int | None:
    """Real score change over the last `days` days, from ScoreSnapshot history.
    Returns None if there's no snapshot old enough to compare against yet
    (e.g. a profile claimed less than `days` ago) rather than pretending 0.
    """
    from app.models import ScoreSnapshot  # local import: models.py doesn't import scoring.py

    cutoff = datetime.utcnow() - timedelta(days=days)
    snapshot = session.exec(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.profile_id == profile_id, ScoreSnapshot.recorded_at <= cutoff)
        .order_by(ScoreSnapshot.recorded_at.desc())
    ).first()
    if snapshot is None:
        return None
    return current_total - snapshot.total


def compute_onboarding_checklist(profile):
    connected = {c["platform_name"] for c in profile.connections if c.get("is_connected")}
    published = {
        p["name"] for p in profile.directory_listings.get("platforms", []) if p.get("is_published")
    }

    return [
        {"label": "Add a profile photo", "done": bool(profile.avatar_url)},
        {"label": "Verify your email", "done": profile.lifecycle_state != "unclaimed"},
        {"label": "Add phone number", "done": bool(profile.phone_number)},
        {"label": "Add license number", "done": bool(profile.license_number)},
        {"label": "Add website", "done": bool(profile.website_url)},
        {"label": "Write your bio", "done": bool(profile.bio)},
        {"label": "Connect Google Business Profile", "done": "Google Business Profile" in connected},
        {"label": "Connect Facebook", "done": "Facebook" in connected},
        {"label": "Connect LinkedIn", "done": "LinkedIn" in connected},
        {"label": "Reply to your first review", "done": any(r.get("reply") for r in profile.reviews)},
        {"label": "Request your first review", "done": len(profile.reviews) > 0},
        {"label": "Publish a directory listing", "done": len(published) > 0},
        {"label": "Complete your first article", "done": profile.articles_count > 0},
    ]


def recompute_and_save_score(session, profile):
    from app.models import ScoreSnapshot  # local import: models.py doesn't import scoring.py

    result = compute_total_score(profile)
    profile.search_rank_score = result["total"]

    if profile.reviews:
        profile.review_count = len(profile.reviews)
        profile.avg_rating = round(
            sum(r.get("rating", 0) for r in profile.reviews) / profile.review_count, 2
        )
    else:
        profile.review_count = 0
        profile.avg_rating = 0.0

    session.add(profile)
    session.commit()
    session.refresh(profile)

    session.add(
        ScoreSnapshot(profile_id=profile.id, total=result["total"], max_possible=result["max_possible"])
    )
    session.commit()

    return result
