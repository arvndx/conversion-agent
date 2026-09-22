from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Profile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    category: str
    location: str
    email: str
    lifecycle_state: str = "unclaimed"  # unclaimed | claimed | pro

    # Always-visible business facts (present even on scraped/unclaimed rows)
    phone_number: str | None = None
    business_name: str | None = None
    address: str | None = None
    business_hours: dict = Field(default_factory=dict, sa_column=Column(JSON))
    avatar_url: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Claim-gated / scoring-input fields
    license_number: str | None = None
    website_url: str | None = None
    bio: str | None = None
    reviews: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    connections: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    directory_listings: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Website health audit — has_meta_description, mobile_friendly, load_time_ms,
    # has_contact_info, has_business_hours_listed. Empty dict if no website_url yet.
    website_audit: dict = Field(default_factory=dict, sa_column=Column(JSON))

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

    # Claim verification (in-progress state, cleared once claimed)
    pending_otp: str | None = None
    otp_verified: bool = False

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
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MockEmail(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    to_email: str
    subject: str
    body_html: str
    profile_id: int = Field(foreign_key="profile.id")
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
