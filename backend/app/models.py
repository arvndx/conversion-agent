from datetime import datetime

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Profile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    category: str
    location: str
    email: str
    lifecycle_state: str = "unclaimed"  # unclaimed | claimed | pro | enterprise (see constants.LIFECYCLE_STATES)

    # Always-visible business facts (present even on scraped/unclaimed rows)
    phone_number: str | None = None
    business_name: str | None = None
    address: str | None = None
    business_hours: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    avatar_url: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Category-driven fields: the category row holds this profile's rules, services and score split.
    vertical: str | None = None
    category_id: int | None = Field(default=None, foreign_key="category.id", index=True)
    services: list[str] = Field(default_factory=list, sa_column=Column(JSONB))  # keys from category_service
    secondary_addresses: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    claimed_at: datetime | None = None
    onboarding_completed_at: datetime | None = None

    # Claim-gated / scoring-input fields
    license_number: str | None = None
    website_url: str | None = None
    bio: str | None = None
    reviews: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    connections: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    directory_listings: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    # Website health audit — has_meta_description, mobile_friendly, load_time_ms,
    # has_contact_info, has_business_hours_listed. Empty dict if no website_url yet.
    website_audit: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    # Extra descriptive fields collected on the claim-details form
    title: str | None = None
    service_area: str | None = None  # "Primary Serving Area" in the UI
    business_timing: str | None = None
    awards: str | None = None
    products_services: str | None = None
    specialities: str | None = None
    memberships: str | None = None
    year_started: str | None = None
    achievements: str | None = None
    hobbies: str | None = None

    # Pro trial — an active trial grants the same scoring boost as real Pro
    # (see scoring.py::_is_pro_effective) and occupies a real market slot.
    trial_ends_at: datetime | None = None

    # Dedup marker for agent/nudges.py's various outreach emails
    last_nudge_sent_at: datetime | None = None

    # Pricing-page visit tracking, drives both the retention discount and lead scoring
    pricing_page_visits: int = 0
    last_pricing_page_visit_at: datetime | None = None
    active_discount_percent: int | None = None
    discount_code: str | None = None
    discount_expires_at: datetime | None = None

    # Denormalized, recomputed together
    search_rank_score: int = 0
    avg_rating: float = 0.0
    review_count: int = 0

    # Decorative dashboard-only stats — NOT part of the 850-point score
    authority_score: int = 0
    articles_count: int = 0
    answers_count: int = 0
    top_5_percent: bool = False
    view_count: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})


class MockEmail(SQLModel, table=True):
    """A mock email. Nothing is sent: it is shown on that address's own mailbox page. `body_html` is
    built by the code that writes it, with every dynamic value HTML-escaped."""

    id: int | None = Field(default=None, primary_key=True)
    to_email: str = Field(index=True)
    subject: str
    body_html: str
    profile_id: int | None = Field(default=None, foreign_key="profile.id")  # none while a new profile is being claimed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_opened: bool = False


class ScoreSnapshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    total: int
    max_possible: int
    recorded_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ProSlotWaitlist(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    category: str
    location: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    notified_at: datetime | None = None


class MarketEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category: str
    location: str
    event_type: str  # "profile_went_pro" | "trial_started"
    profile_id: int = Field(foreign_key="profile.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ExecutiveHandoffRequest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    reason: str
    status: str = "pending"  # pending | contacted | resolved
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Category taxonomy (vertical -> category -> services) and per-category rules ------------------


class Vertical(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    name: str


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    vertical_id: int = Field(foreign_key="vertical.id", index=True)
    key: str = Field(unique=True, index=True)
    name: str = Field(index=True)
    # Profile fields the claim requires, e.g. ["name", "email", "phone_number", "vertical", "category", "services"]
    mandatory_fields: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Fields that make up Profile Completion: [{"key": "license_number", "label": "License", "weight": 1}]
    basic_fields: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    # Profile URL slots: [{"platform": "zillow", "label": "Zillow", "kind": "social" | "directory"}]
    url_slots: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))
    # General rules / guard rails read by the claim flow, validators and the agent
    rules: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    is_active: bool = True


class CategoryService(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    key: str
    name: str
    sort_order: int = 0


class CategoryScoreSection(SQLModel, table=True):
    """One row per (category, score section): its max points and whether it unlocks only with Pro."""

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    section: str  # one of constants.SCORE_SECTIONS
    label: str
    max_points: int
    is_pro_only: bool = False
    sort_order: int = 0


# --- Claim, sign-in and onboarding ------------------------------------------------------------------


class ProfileLink(SQLModel, table=True):
    """A profile URL on one platform (website, Google Business, LinkedIn, Zillow, ...)."""

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    platform: str  # a url_slots platform key, or "website"
    url: str
    label: str | None = None  # e.g. "personal profile"
    confirmed: bool = False
    source: str = "db"  # db | user | search | scrape
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProfileSource(SQLModel, table=True):
    """One scrape of one URL during onboarding."""

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    url: str
    platform: str | None = None
    label: str | None = None
    # proposed | confirmed | denied | scraping | done | failed | blocked | needs_identity
    status: str = "proposed"
    phase: str | None = None  # while scraping: queued | opening | reading | extracting (for the live progress)
    confidence: int | None = None  # 0-100, for URLs found by search
    name_validated: bool | None = None
    merged: bool = False  # its data has been folded into the profile (or raised as conflicts)
    extracted: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    raw_markdown: str | None = Field(default=None, sa_column=Column(Text))
    error: str | None = None
    fetched_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})


class ProfileConflict(SQLModel, table=True):
    """Differing values for one field across scraped sources, awaiting the agent's choice."""

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    field_key: str
    kind: str = "pick_one"  # pick_one | license (which is real, or keep both) | address (primary / secondary / not current)
    options: list[dict] = Field(default_factory=list, sa_column=Column(JSONB))  # [{"value": ..., "sources": [url]}]
    status: str = "open"  # open | resolved
    resolution: dict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None


class Claim(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    profile_id: int | None = Field(default=None, foreign_key="profile.id", index=True)  # set on verify for new profiles
    method: str  # search_card | new_profile
    status: str = "pending"  # pending | verified | rejected
    email: str
    phone: str | None = None
    # What the agent entered on the claim card; applied to the profile only once the OTP is verified.
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: datetime | None = None
    evidence: dict = Field(default_factory=dict, sa_column=Column(JSONB))


class OtpCode(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    purpose: str  # claim | login
    profile_id: int | None = Field(default=None, foreign_key="profile.id")
    claim_id: int | None = Field(default=None, foreign_key="claim.id", index=True)
    code_hash: str
    expires_at: datetime
    attempts: int = 0
    consumed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuthSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
