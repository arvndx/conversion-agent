"""Seed for the vertical -> category -> services taxonomy and each category's rules and score split.

The lists below come from core1.txt (the product idea). The production taxonomy has 4000+
categories; this seeds the four core1 defines plus Dentist, which ClearRank already had.
Everything here is data, so adding a category means adding a row, not changing code.
"""

from sqlmodel import Session

from app.models import Category, CategoryScoreSection, CategoryService, Vertical

MANDATORY_FIELDS = ["name", "email", "phone_number", "vertical", "category", "services"]

# core1.txt "basic fields". Each is a Profile column; `weight` splits the Profile Completion points
# (equal by default, tune per category). core1's "primary address" -> address, "business hours" ->
# business_timing (the free-text hours the claim form collects), "company_name" -> business_name,
# "description" -> bio, "license" -> license_number.
BASIC_FIELDS = [
    ("specialities", "Specialities"),
    ("title", "Title"),
    ("address", "Primary address"),
    ("website_url", "Website"),
    ("business_timing", "Business hours"),
    ("bio", "Description"),
    ("awards", "Awards"),
    ("achievements", "Achievements"),
    ("year_started", "Year started"),
    ("business_name", "Company name"),
    ("license_number", "License"),
    ("service_area", "Service area"),
]

# Social / Google URLs count toward Connections; directory URLs count toward Listings.
SOCIAL_SLOTS = [
    ("google_business_profile", "Google Business Profile"),
    ("facebook", "Facebook"),
    ("linkedin", "LinkedIn"),
    ("x", "Twitter/X"),
    ("instagram", "Instagram"),
]

# Rules read by the claim flow, the onboarding agent and validators. Only what core1.txt states.
BASE_RULES = {
    "claim": {
        # Name can be edited, plus either phone or email, never both.
        "editable_fields": ["name"],
        "edit_one_of": ["phone_number", "email"],
        "otp_channel": "email",
        "prefill_vertical_only": True,
    },
    "onboarding": {
        "confirm_each_url": True,
        "parallel_scrape": True,
        "validate_name_before_use": True,
        "search_fallback_order": ["name+title+company_name", "name"],
        "url_labels": ["personal profile", "linkedin profile", "yelp profile", "zillow profile", "instagram profile"],
        "resolve_conflicts_at_end": True,
        "conflict_fields": [f for f, _ in BASIC_FIELDS] + ["services"],
        "multi_value_fields": {"license_number": "choose which is real, or keep both", "address": "primary / secondary / not current / add manually"},
        "default_business_timing": "Monday–Friday, 9 AM – 6 PM",
        "ai_drafts": ["specialities", "bio"],
        "verified_before_onboarding": ["name", "email", "phone_number", "vertical", "category", "services"],
    },
}

# Score split. The formulas live in app/scoring.py; only the composition is data.
STANDARD_SECTIONS = [
    # (section, label, max_points, is_pro_only)
    ("reviews", "Reviews & Replies", 300, False),
    ("profile_completion", "Profile Completion", 100, False),
    ("connections", "Connections", 100, False),
    ("web_analytics", "Website Health", 250, True),
    ("listings", "Listings", 100, True),
]
# core1: Insurance Agent has Listings in the common section; only Website Health is Pro-locked.
INSURANCE_SECTIONS = [
    ("reviews", "Reviews & Replies", 300, False),
    ("profile_completion", "Profile Completion", 100, False),
    ("connections", "Connections", 100, False),
    ("listings", "Listings", 100, False),
    ("web_analytics", "Website Health", 250, True),
]

# (vertical key, vertical name) and the categories inside each.
VERTICALS = [
    ("mortgage", "Mortgage"),
    ("real_estate", "Real Estate"),
    ("insurance", "Insurance"),
    ("healthcare", "Healthcare"),
]

CATEGORIES = [
    {
        "vertical": "mortgage",
        "key": "mortgage_loan_officer",
        "name": "Mortgage Loan Officer",
        "directory_slots": [("zillow", "Zillow lender directory"), ("lendingtree", "LendingTree")],
        "sections": STANDARD_SECTIONS,
        "services": ["FHA home loan", "VA home loan", "Jumbo loan", "Mortgage refinance", "Down payment assistance"],
    },
    {
        "vertical": "mortgage",
        "key": "mortgage_lender",
        "name": "Mortgage Lender",
        "directory_slots": [("zillow", "Zillow lender directory"), ("lendingtree", "LendingTree")],
        "sections": STANDARD_SECTIONS,
        "services": [
            "FHA home loan", "VA home loan", "Jumbo loan", "Mortgage refinance",
            "Non-QM", "Bridge loan", "Construction loan", "Fixed rate mortgage",
        ],
    },
    {
        "vertical": "real_estate",
        "key": "real_estate_agent",
        "name": "Real Estate Agent",
        "directory_slots": [("zillow", "Zillow"), ("realtor_com", "Realtor.com"), ("homes_com", "Homes.com")],
        "sections": STANDARD_SECTIONS,
        "services": [
            "Residential real estate", "Commercial real estate", "Lots and land", "Vacation homes", "Foreclosure sales",
        ],
    },
    {
        "vertical": "insurance",
        "key": "insurance_agent",
        "name": "Insurance Agent",
        "directory_slots": [("trusted_choice", "Trusted Choice (independent agents)"), ("yelp", "Yelp")],
        "sections": INSURANCE_SECTIONS,
        "services": [
            "Life insurance", "Health insurance", "Auto insurance", "Pet insurance", "Property insurance", "Boat insurance",
        ],
    },
    {
        # Not in core1.txt: kept from the original ClearRank. Directory slots and the (standard) score
        # split are assumptions; services are the original claim form's quick-picks.
        "vertical": "healthcare",
        "key": "dentist",
        "name": "Dentist",
        "directory_slots": [("yelp", "Yelp"), ("healthgrades", "Healthgrades")],
        "sections": STANDARD_SECTIONS,
        "services": [
            "Teeth whitening", "Invisalign", "Dental implants", "Root canals", "Crowns & bridges",
            "Veneers", "Emergency dentistry", "Pediatric dentistry", "Cleanings & exams",
        ],
    },
]


def _slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")


def seed_taxonomy(session: Session) -> None:
    """Insert verticals, categories, services and score sections. Run on an empty taxonomy."""
    vertical_ids = {}
    for key, name in VERTICALS:
        vertical = Vertical(key=key, name=name)
        session.add(vertical)
        session.flush()
        vertical_ids[key] = vertical.id

    for spec in CATEGORIES:
        category = Category(
            vertical_id=vertical_ids[spec["vertical"]],
            key=spec["key"],
            name=spec["name"],
            mandatory_fields=list(MANDATORY_FIELDS),
            basic_fields=[{"key": k, "label": label, "weight": 1} for k, label in BASIC_FIELDS],
            url_slots=[{"platform": p, "label": label, "kind": "social"} for p, label in SOCIAL_SLOTS]
            + [{"platform": p, "label": label, "kind": "directory"} for p, label in spec["directory_slots"]],
            rules=BASE_RULES,
        )
        session.add(category)
        session.flush()

        for order, service in enumerate(spec["services"]):
            session.add(CategoryService(category_id=category.id, key=_slug(service), name=service, sort_order=order))
        for order, (section, label, max_points, is_pro_only) in enumerate(spec["sections"]):
            session.add(
                CategoryScoreSection(
                    category_id=category.id, section=section, label=label,
                    max_points=max_points, is_pro_only=is_pro_only, sort_order=order,
                )
            )
    session.commit()
