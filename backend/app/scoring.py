from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlmodel import select

from app.category_config import NATIVE_SECTION_MAX, CategoryConfig, all_configs, config_for
from app.constants import CONNECTION_PLATFORMS, DIRECTORY_PLATFORMS, PRO_STATES

# Friendly "what to do" text for the common Profile Completion fields. Any other field falls back to
# "Add your <label>".
FIELD_ACTION_LABELS = {
    "phone_number": "Add a phone number",
    "license_number": "Add your license number",
    "website_url": "Add your website",
    "bio": "Write your description",
    "service_area": "Add your primary serving area",
    "specialities": "Add your specialities",
    "year_started": "Add the year you started",
    "achievements": "Add your achievements",
    "awards": "Add your awards",
    "title": "Add your title",
    "address": "Add your primary address",
    "business_timing": "Add your business hours",
    "business_name": "Add your company name",
    "products_services": "List your products & services",
    "memberships": "Add your professional memberships",
    "hobbies": "Add a personal touch with hobbies",
}

# Profile attributes every score reads, whatever the category. Each category's Profile Completion
# fields are added on top (see scoring_input_fields).
SCORING_BASE_FIELDS = [
    "reviews",
    "connections",
    "website_audit",
    "directory_listings",
    "lifecycle_state",
    "trial_ends_at",
    "category_id",
    "category",
    "website_url",
]


def scoring_input_fields() -> list[str]:
    """The exact set of attributes the scoring functions read from a profile-like object. Used to
    build a detached shadow copy for what-if scoring (simulate_total_score) without touching the
    real ORM-tracked row."""
    fields = list(SCORING_BASE_FIELDS)
    for config in all_configs():
        for key in config.completion_field_keys:
            if key not in fields:
                fields.append(key)
    return fields


def completion_field_keys(profile) -> list[str]:
    """The Profile Completion fields for this profile's category."""
    return config_for(profile).completion_field_keys


def is_pro_effective(profile) -> bool:
    """True if `profile` currently gets Pro-tier benefits: real Pro, enterprise, or an active trial.
    Shared by scoring, slot-capacity counting, and any route that gates a Pro-only action, so trial
    support never has to be special-cased in more than one place.
    """
    if profile.lifecycle_state in PRO_STATES:
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


def compute_profile_completion_score(profile, config: CategoryConfig | None = None):
    """Share of the category's basic fields that are filled, weighted per field (equal by default)."""
    config = config or config_for(profile)
    fields = config.basic_fields
    total_weight = sum(f.get("weight", 1) for f in fields) or 1
    filled_weight = sum(f.get("weight", 1) for f in fields if getattr(profile, f["key"], None))
    points = round(filled_weight / total_weight * 100)

    opportunities = [
        FIELD_ACTION_LABELS.get(f["key"], f"Add your {f.get('label', f['key']).lower()}")
        for f in fields
        if not getattr(profile, f["key"], None)
    ]
    return points, opportunities


def field_points(profile, field_key: str) -> int:
    """Points the profile would gain in the Profile Completion section by filling `field_key`, from the
    category weights (so it needs no placeholder value). 0 if already filled or the field isn't part
    of the category's completion."""
    config = config_for(profile)
    fields = config.basic_fields
    total_weight = sum(f.get("weight", 1) for f in fields) or 1
    weight = next((f.get("weight", 1) for f in fields if f["key"] == field_key), 0)
    if not weight or getattr(profile, field_key, None):
        return 0
    return round(weight / total_weight * config.sections["profile_completion"].max_points)


def _slot_names(slots: list[dict], fallback: list[str]) -> list[tuple[str, str]]:
    """(platform key, label) for each slot; the legacy generic list when a category defines none."""
    if slots:
        return [(s["platform"], s["label"]) for s in slots]
    return [(name, name) for name in fallback]


def compute_connections_score(profile, config: CategoryConfig | None = None):
    """Share of the category's social/Google URL slots the profile has connected."""
    config = config or config_for(profile)
    slots = _slot_names(config.slots("social"), CONNECTION_PLATFORMS)
    connected = set()
    for c in profile.connections:
        if c.get("is_connected"):
            connected.update(v for v in (c.get("platform_name"), c.get("platform")) if v)
    missing = [label for key, label in slots if key not in connected and label not in connected]
    points = round((len(slots) - len(missing)) / len(slots) * 100)
    return points, [f"Connect {label}" for label in missing]


WEBSITE_AUDIT_LOAD_TIME_THRESHOLD_MS = 2500
POINTS_PER_AUDIT_CHECK = 50  # 5 checks x 50 = 250, matching NATIVE_SECTION_MAX["web_analytics"]


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
        opportunities.append("Make your website mobile-friendly — most visitors search on their phone")

    load_time_ms = audit.get("load_time_ms")
    if load_time_ms is not None and load_time_ms <= WEBSITE_AUDIT_LOAD_TIME_THRESHOLD_MS:
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append(
            f"Speed up your website ({load_time_ms}ms load time) — slow pages lose visitors"
            if load_time_ms is not None
            else "We could not measure your website's load time yet"
        )

    if audit.get("has_contact_info"):
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append("Make sure your phone number and address are clearly listed on your website")

    if audit.get("has_business_hours_listed"):
        points += POINTS_PER_AUDIT_CHECK
    else:
        opportunities.append("List your business hours clearly on your website")

    return points, opportunities


def compute_listings_score(profile, config: CategoryConfig | None = None):
    """Share of the category's directory URL slots (Zillow, LendingTree, Yelp, ...) that are published."""
    config = config or config_for(profile)
    slots = _slot_names(config.slots("directory"), DIRECTORY_PLATFORMS)
    published = set()
    for p in profile.directory_listings.get("platforms", []):
        if p.get("is_published"):
            published.update(v for v in (p.get("name"), p.get("platform")) if v)
    missing = [label for key, label in slots if key not in published and label not in published]
    points = round((len(slots) - len(missing)) / len(slots) * 100)
    return points, [f"Publish your listing on {label}" for label in missing]


def compute_total_score(profile):
    config = config_for(profile)
    is_pro = is_pro_effective(profile)

    native = {
        "reviews": lambda: compute_reviews_score(profile),
        "profile_completion": lambda: compute_profile_completion_score(profile, config),
        "connections": lambda: compute_connections_score(profile, config),
        "web_analytics": lambda: compute_web_analytics_score(profile),
        "listings": lambda: compute_listings_score(profile, config),
    }

    categories = {}
    for section in config.ordered_sections:
        native_points, opportunities = native[section.key]()
        # The formula yields points on the section's native scale; scale to this category's maximum.
        earned = round(native_points * section.max_points / NATIVE_SECTION_MAX[section.key])
        categories[section.key] = {
            "label": section.label,
            "earned": earned,
            "max": section.max_points,
            "locked": section.is_pro_only and not is_pro,
            "opportunities": opportunities,
        }

    total = sum(c["earned"] for c in categories.values() if not c["locked"])
    unlock_points = sum(c["earned"] for c in categories.values() if c["locked"])
    locked_max = sum(c["max"] for c in categories.values() if c["locked"])

    return {
        "total": total,
        "max_possible": config.pro_max if is_pro else config.common_max,
        "pro_max": config.pro_max,
        "lifecycle_state": profile.lifecycle_state,
        "category": config.name,
        "section_order": [s.key for s in config.ordered_sections],
        "categories": categories,
        "unlock_points": unlock_points,
        "locked_max": locked_max,
    }


def simulate_total_score(profile, overrides: dict):
    """Score a hypothetical version of `profile` with `overrides` applied, without
    touching the database or the real ORM-tracked object. Used for the what-if
    simulator, the nudge-email engine, and the Pro-card preview — one shared
    implementation so none of them can drift from how scoring actually works.
    """
    shadow = SimpleNamespace(**{field: getattr(profile, field, None) for field in scoring_input_fields()})
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
