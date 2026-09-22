import random
from datetime import datetime, timedelta

from sqlmodel import Session, delete

from app.constants import CONNECTION_PLATFORMS, DIRECTORY_PLATFORMS
from app.db import engine
from app.models import MockEmail, Profile, ProSlotWaitlist, ScoreSnapshot
from app.scoring import recompute_and_save_score

CATEGORY = "Dentist"
LOCATION = "Austin, TX"

def _build_profiles():
    return [
        Profile(
            name="Dr. Sarah Chen",
            category=CATEGORY,
            location=LOCATION,
            email="sarah.chen@example.com",
            lifecycle_state="pro",
            avatar_url="/avatars/avatar-1.svg",
            phone_number="(512) 555-0142",
            business_name="Sarah Chen Family Dentistry",
            address="1400 Barton Springs Rd, Austin, TX",
            business_hours={
                "Monday": "8:00 AM - 5:00 PM",
                "Tuesday": "8:00 AM - 5:00 PM",
                "Wednesday": "8:00 AM - 5:00 PM",
                "Thursday": "8:00 AM - 5:00 PM",
                "Friday": "8:00 AM - 1:00 PM",
                "Saturday": "Closed",
                "Sunday": "Closed",
            },
            tags=["Family Dentistry", "Cosmetic Dentistry"],
            license_number="TX-DDS-88213",
            website_url="https://sarahchendental.example.com",
            bio=(
                "Dr. Sarah Chen, DDS is a family and cosmetic dentist serving Austin, TX for "
                "over 12 years. She specializes in preventive care, whitening, and Invisalign."
            ),
            reviews=[
                {"reviewer_name": "Maria G.", "rating": 5, "body": "Best dentist in Austin!", "reply": "Thank you Maria!"},
                {"reviewer_name": "Tom H.", "rating": 5, "body": "Painless and professional.", "reply": "So glad to hear it, Tom!"},
                {"reviewer_name": "Priya S.", "rating": 5, "body": "Great with kids too.", "reply": "Thanks Priya!"},
                {"reviewer_name": "Alan W.", "rating": 5, "body": "Very thorough exam.", "reply": "Appreciate the kind words, Alan!"},
                {"reviewer_name": "Jenna R.", "rating": 4, "body": "Good experience overall.", "reply": "Thanks for the feedback, Jenna!"},
            ],
            connections=[
                {"platform_name": "Google Business Profile", "is_connected": True},
                {"platform_name": "Facebook", "is_connected": True},
                {"platform_name": "LinkedIn", "is_connected": True},
                {"platform_name": "Instagram", "is_connected": True},
                {"platform_name": "Twitter/X", "is_connected": True},
            ],
            directory_listings={
                "platforms": [
                    {"name": "Google Business Profile", "is_published": True},
                    {"name": "Yelp", "is_published": True},
                    {"name": "Facebook", "is_published": True},
                    {"name": "Apple Maps", "is_published": True},
                    {"name": "Voice Search", "is_published": True},
                ]
            },
            website_audit={
                "has_meta_description": True,
                "mobile_friendly": True,
                "load_time_ms": 1400,
                "has_contact_info": True,
                "has_business_hours_listed": True,
            },
            authority_score=72,
            articles_count=5,
            answers_count=12,
            top_5_percent=True,
            view_count=1240,
        ),
        Profile(
            name="Dr. Michael Torres",
            category=CATEGORY,
            location=LOCATION,
            email="michael.torres@example.com",
            lifecycle_state="claimed",
            avatar_url="/avatars/avatar-2.svg",
            phone_number="(512) 555-0198",
            business_name="Michael Torres Dental Care",
            address="900 Congress Ave, Austin, TX",
            business_hours={
                "Monday": "9:00 AM - 5:00 PM",
                "Tuesday": "9:00 AM - 5:00 PM",
                "Wednesday": "9:00 AM - 5:00 PM",
                "Thursday": "9:00 AM - 5:00 PM",
                "Friday": "Closed",
                "Saturday": "Closed",
                "Sunday": "Closed",
            },
            tags=["General Dentistry"],
            license_number=None,
            website_url=None,
            bio="Dr. Michael Torres, DDS provides general dentistry services in downtown Austin.",
            reviews=[
                {"reviewer_name": "Ken L.", "rating": 5, "body": "Quick and easy visit.", "reply": "Thanks Ken!"},
                {"reviewer_name": "Dana P.", "rating": 4, "body": "Friendly staff.", "reply": "Appreciate it, Dana!"},
                {"reviewer_name": "Omar F.", "rating": 3, "body": "Long wait time but decent care.", "reply": None},
            ],
            connections=[
                {"platform_name": "Google Business Profile", "is_connected": True},
                {"platform_name": "Facebook", "is_connected": False},
                {"platform_name": "LinkedIn", "is_connected": False},
                {"platform_name": "Instagram", "is_connected": False},
                {"platform_name": "Twitter/X", "is_connected": False},
            ],
            directory_listings={"platforms": []},
            # website_audit defaults to {} — he has no website_url yet to audit.
            authority_score=18,
            articles_count=1,
            answers_count=2,
            top_5_percent=False,
            view_count=310,
        ),
        Profile(
            name="Dr. Amara Okafor",
            category=CATEGORY,
            location=LOCATION,
            email="amara.okafor@example.com",
            lifecycle_state="unclaimed",
            avatar_url="/avatars/avatar-3.svg",
            phone_number="(512) 555-0176",
            business_name="Amara Okafor Dental",
            address="200 E 6th St, Austin, TX",
            reviews=[
                {"reviewer_name": "Rita M.", "rating": 5, "body": "Great cleaning, very gentle.", "reply": None},
                {"reviewer_name": "Sam K.", "rating": 4, "body": "Solid checkup, friendly front desk.", "reply": None},
                {"reviewer_name": "Nora J.", "rating": 5, "body": "Highly recommend for families.", "reply": None},
                {"reviewer_name": "Evan T.", "rating": 4, "body": "Good experience, a bit of a wait.", "reply": None},
                {"reviewer_name": "Lily P.", "rating": 5, "body": "Best dental visit in years.", "reply": None},
                {"reviewer_name": "Marcus D.", "rating": 4, "body": "Professional and thorough.", "reply": None},
            ],
            view_count=62,
        ),
        Profile(
            name="Dr. James Whitfield",
            category=CATEGORY,
            location=LOCATION,
            email="james.whitfield@example.com",
            lifecycle_state="unclaimed",
            avatar_url="/avatars/avatar-4.svg",
            phone_number="(512) 555-0134",
            business_name="Whitfield Dental Group",
            address="3500 Guadalupe St, Austin, TX",
            reviews=[
                {"reviewer_name": "Grace H.", "rating": 4, "body": "Decent visit, nothing fancy.", "reply": None},
                {"reviewer_name": "Paul R.", "rating": 3, "body": "Long wait but okay care.", "reply": None},
                {"reviewer_name": "Ivy C.", "rating": 4, "body": "Friendly hygienist.", "reply": None},
            ],
            view_count=48,
        ),
        Profile(
            name="Dr. Linda Park",
            category=CATEGORY,
            location=LOCATION,
            email="linda.park@example.com",
            lifecycle_state="unclaimed",
            avatar_url="/avatars/avatar-5.svg",
            phone_number="(512) 555-0119",
            business_name="Linda Park DDS",
            address="1100 S Lamar Blvd, Austin, TX",
            reviews=[
                {"reviewer_name": "Owen B.", "rating": 3, "body": "Average experience overall.", "reply": None},
            ],
            view_count=39,
        ),
        # Two unclaimed profiles backed by real, live websites (not *.example.com
        # placeholders) — for testing the claim-assist agent's actual web_search +
        # fetch_and_extract_website flow against genuine scraped content. Deliberately
        # leave website_url/title/bio/business_timing/service_area/awards empty even
        # though the real site has all of this — that's exactly what claim-assist is
        # supposed to go find and propose.
        Profile(
            name="Amber Ernst",
            category="Mortgage Loan Officer",
            location="Davenport, IA",
            email="amber.ernst@nafinc.com",
            lifecycle_state="unclaimed",
            business_name="Amber Ernst Team - New American Funding",
            tags=["Mortgage Loans", "Home Loans"],
            reviews=[
                {
                    "reviewer_name": "Austin J.",
                    "rating": 5,
                    "body": "Very responsive and did everything it took to get us to the closing table.",
                    "reply": None,
                },
                {
                    "reviewer_name": "Valerie M.",
                    "rating": 5,
                    "body": "Excellent communication. Professional knowledge. Personable and polite.",
                    "reply": None,
                },
                {
                    "reviewer_name": "Sean L T.",
                    "rating": 5,
                    "body": "Work really hard — even when you think things aren't possible, they make it happen.",
                    "reply": None,
                },
            ],
            view_count=44,
        ),
        Profile(
            name="Dr. Ria Sahara",
            category=CATEGORY,
            location="Newnan, GA",
            email="office@newnandental.com",
            lifecycle_state="unclaimed",
            business_name="Gentle Dentistry of Newnan, PC",
            address="37-G Calumet Pkwy #201, Newnan, GA 30263",
            tags=["Family Dentistry", "Cosmetic Dentistry", "Preventative Dentistry"],
            reviews=[
                {"reviewer_name": "Marcus T.", "rating": 5, "body": "Best dentist in Coweta County, very gentle.", "reply": None},
                {"reviewer_name": "Priya D.", "rating": 4, "body": "Friendly staff, clean office.", "reply": None},
            ],
            view_count=31,
        ),
    ]


# --- Generated profiles: more variety for search/ranking without hand-authoring every field ---

REVIEWER_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Jamie", "Drew",
    "Reese", "Skyler", "Avery", "Quinn", "Rowan", "Elliot", "Hayden", "Peyton",
    "Charlie", "Emerson", "Kendall", "Sage",
]
REVIEWER_LAST_INITIALS = list("ABCDEFGHJKLMNPRSTW")

REVIEW_BODIES_BY_RATING = {
    5: [
        "Absolutely wonderful experience, highly recommend!",
        "Best dental visit I've had in years.",
        "Incredibly gentle and professional.",
        "Loved the friendly staff and clean office.",
        "Top-notch care from start to finish.",
    ],
    4: [
        "Very good visit, minor wait but worth it.",
        "Solid checkup, friendly staff.",
        "Professional and thorough overall.",
        "Good experience, would come back.",
        "Nice office, helpful team.",
    ],
    3: [
        "Decent service, nothing special.",
        "Average experience, okay care.",
        "It was fine, a bit of a wait.",
        "Reasonable visit overall.",
    ],
}

BUSINESS_STREETS = [
    "Manor Rd", "Burnet Rd", "South First St", "Airport Blvd", "MLK Jr Blvd",
    "Riverside Dr", "William Cannon Dr", "Anderson Ln", "Slaughter Ln",
    "Parmer Ln", "Bee Caves Rd", "Menchaca Rd",
]

HOUSTON = "Houston, TX"
LOS_ANGELES = "Los Angeles, CA"
SAN_FRANCISCO = "San Francisco, CA"

# (name, business_name, lifecycle_state, seed) — seed determines category+location below
GENERATED_TIERS = [
    ("Dr. Elena Vasquez", "Vasquez Modern Dentistry", "pro", 101),
    ("Dr. Marcus Bell", "Bell Dental Associates", "pro", 102),
    ("Dr. Priya Nair", "Nair Family Dentistry", "claimed", 201),
    ("Dr. Robert Kim", "Kim Dental Studio", "claimed", 202),
    ("Dr. Fatima Haddad", "Haddad Dental Care", "claimed", 203),
    ("Dr. Steven Wallace", "Wallace Dentistry", "claimed", 204),
    ("Dr. Angela Brooks", "Brooks Family Dental", "claimed", 205),
    ("Dr. Trevor Nguyen", "Nguyen Dental Clinic", "unclaimed", 301),
    ("Dr. Rachel Simmons", "Simmons Dental Group", "unclaimed", 302),
    ("Dr. Hassan Ali", "Ali Family Dentistry", "unclaimed", 303),
    ("Dr. Megan Foster", "Foster Dental Care", "unclaimed", 304),
    ("Dr. Diego Ramirez", "Ramirez Dentistry", "unclaimed", 305),
]

# Houston: 4 of 5 Pro slots taken — "only 1 left, grab it"
HOUSTON_TIERS = [
    ("Dr. Olivia Martinez", "Martinez Family Dental", "pro", 401),
    ("Dr. Benjamin Clark", "Clark Dental Group", "pro", 402),
    ("Dr. Sophia Turner", "Turner Dentistry", "pro", 403),
    ("Dr. Nathan Reyes", "Reyes Dental Care", "pro", 404),
    ("Dr. Grace Coleman", "Coleman Family Dentistry", "claimed", 405),
    ("Dr. Victor Alvarez", "Alvarez Dental Studio", "claimed", 406),
    ("Dr. Chloe Bennett", "Bennett Dental Clinic", "unclaimed", 407),
]

# Los Angeles: 3 of 5 Pro slots taken — "2 more slots"
LOS_ANGELES_TIERS = [
    ("Dr. Isabella Rossi", "Rossi Dental Arts", "pro", 501),
    ("Dr. Ethan Walsh", "Walsh Family Dentistry", "pro", 502),
    ("Dr. Amara Singh", "Singh Dental Group", "pro", 503),
    ("Dr. Lucas Ferreira", "Ferreira Dental Care", "claimed", 504),
    ("Dr. Naomi Sato", "Sato Dentistry LA", "claimed", 505),
    ("Dr. Marcus Delgado", "Delgado Family Dental", "unclaimed", 506),
    ("Dr. Ruby Patel", "Patel Dental Studio", "unclaimed", 507),
]

# San Francisco: 5 of 5 Pro slots taken — FULL, demos hard-block + waitlist
SAN_FRANCISCO_TIERS = [
    ("Dr. Julian Wong", "Wong Dental Innovations", "pro", 601),
    ("Dr. Stella Whitmore", "Whitmore Family Dentistry", "pro", 602),
    ("Dr. Adrian Costa", "Costa Dental Group", "pro", 603),
    ("Dr. Vivian Choi", "Choi Dentistry", "pro", 604),
    ("Dr. Miles Anderson", "Anderson Family Dental", "pro", 605),
    ("Dr. Zoe Fitzgerald", "Fitzgerald Dental Care", "claimed", 606),
    ("Dr. Oscar Nakamura", "Nakamura Dental Clinic", "unclaimed", 607),
]


def _make_reviews(rng, count, rating_choices, reply_rate):
    reviews = []
    for _ in range(count):
        rating = rng.choice(rating_choices)
        first = rng.choice(REVIEWER_FIRST_NAMES)
        reviewer_name = f"{first} {rng.choice(REVIEWER_LAST_INITIALS)}."
        body = rng.choice(REVIEW_BODIES_BY_RATING[rating])
        replied = rng.random() < reply_rate
        reply = f"Thank you, {first}! We appreciate your feedback." if replied else None
        reviews.append({"reviewer_name": reviewer_name, "rating": rating, "body": body, "reply": reply})
    return reviews


def _make_connections(rng, count):
    chosen = rng.sample(CONNECTION_PLATFORMS, k=count)
    return [{"platform_name": p, "is_connected": p in chosen} for p in CONNECTION_PLATFORMS]


def _make_website_audit(rng, website_url):
    """A deterministic, honest stand-in for what a real site audit would find — no
    website_url means nothing to audit yet, same as a real audit would report."""
    if not website_url:
        return {}
    return {
        "has_meta_description": rng.random() < 0.6,
        "mobile_friendly": rng.random() < 0.65,
        "load_time_ms": rng.randint(900, 4500),
        "has_contact_info": rng.random() < 0.75,
        "has_business_hours_listed": rng.random() < 0.5,
    }


def _make_directory_listings(rng, count):
    chosen = rng.sample(DIRECTORY_PLATFORMS, k=count)
    return {"platforms": [{"name": p, "is_published": p in chosen} for p in DIRECTORY_PLATFORMS]}


AREA_CODES = {
    LOCATION: "512",
    HOUSTON: "713",
    LOS_ANGELES: "213",
    SAN_FRANCISCO: "415",
}
STATE_ABBR = {
    LOCATION: "TX",
    HOUSTON: "TX",
    LOS_ANGELES: "CA",
    SAN_FRANCISCO: "CA",
}


def _build_generated_profile(name, business_name, lifecycle_state, seed, category=CATEGORY, location=LOCATION):
    rng = random.Random(seed)
    first_last = name.replace("Dr. ", "").lower().split(" ")
    email = f"{first_last[0]}.{first_last[-1]}@example.com"
    address = f"{rng.randint(100, 9900)} {rng.choice(BUSINESS_STREETS)}, {location}"
    area_code = AREA_CODES[location]
    state = STATE_ABBR[location]
    phone_number = f"({area_code}) 555-{rng.randint(200, 999):04d}"

    if lifecycle_state == "pro":
        reviews = _make_reviews(rng, rng.randint(5, 8), [5, 5, 4, 5], reply_rate=1.0)
        connections = _make_connections(rng, rng.randint(3, 5))
        listings = _make_directory_listings(rng, rng.randint(3, 5))
        phone_number_val, license_number, website_url, bio = (
            phone_number,
            f"{state}-DDS-{rng.randint(10000, 99999)}",
            f"https://{first_last[-1]}dental.example.com",
            f"{name}, DDS provides comprehensive dental care in {location} with a focus on patient comfort.",
        )
        website_audit = _make_website_audit(rng, website_url)
        authority_score, articles_count, answers_count = rng.randint(55, 80), rng.randint(2, 6), rng.randint(5, 14)
        top_5_percent = rng.random() < 0.5
        view_count = rng.randint(800, 1500)
    elif lifecycle_state == "claimed":
        reviews = _make_reviews(rng, rng.randint(2, 5), [3, 4, 4, 5], reply_rate=rng.uniform(0.3, 0.7))
        connected_count = rng.randint(0, 2)
        connections = _make_connections(rng, connected_count)
        listings = {"platforms": []}
        phone_number_val = phone_number
        license_number = f"{state}-DDS-{rng.randint(10000, 99999)}" if rng.random() < 0.4 else None
        website_url = f"https://{first_last[-1]}dental.example.com" if rng.random() < 0.4 else None
        website_audit = _make_website_audit(rng, website_url)
        bio = f"{name}, DDS offers general dentistry services in {location}." if rng.random() < 0.8 else None
        authority_score, articles_count, answers_count = rng.randint(5, 25), rng.randint(0, 2), rng.randint(0, 4)
        top_5_percent = False
        view_count = rng.randint(150, 400)
    else:  # unclaimed
        has_reviews = rng.random() < 0.7
        reviews = _make_reviews(rng, rng.randint(1, 5), [3, 4, 5], reply_rate=0.0) if has_reviews else []
        connections = []
        listings = {"platforms": []}
        phone_number_val = phone_number if rng.random() < 0.6 else None
        license_number = None
        website_url = None
        website_audit = {}
        bio = None
        authority_score, articles_count, answers_count = 0, 0, 0
        top_5_percent = False
        view_count = rng.randint(15, 90)

    return Profile(
        name=name,
        category=category,
        location=location,
        email=email,
        lifecycle_state=lifecycle_state,
        phone_number=phone_number_val,
        business_name=business_name,
        address=address,
        tags=["General Dentistry"],
        license_number=license_number,
        website_url=website_url,
        bio=bio,
        reviews=reviews,
        connections=connections,
        directory_listings=listings,
        website_audit=website_audit,
        authority_score=authority_score,
        articles_count=articles_count,
        answers_count=answers_count,
        top_5_percent=top_5_percent,
        view_count=view_count,
    )


def _build_generated_profiles():
    return [
        _build_generated_profile(*args)
        for args in GENERATED_TIERS
    ] + [
        _build_generated_profile(*args, category=CATEGORY, location=HOUSTON)
        for args in HOUSTON_TIERS
    ] + [
        _build_generated_profile(*args, category=CATEGORY, location=LOS_ANGELES)
        for args in LOS_ANGELES_TIERS
    ] + [
        _build_generated_profile(*args, category=CATEGORY, location=SAN_FRANCISCO)
        for args in SAN_FRANCISCO_TIERS
    ]


def _assign_review_ids(profile):
    for i, review in enumerate(profile.reviews):
        review["id"] = f"r{i}"
    profile.reviews = list(profile.reviews)  # reassign so the JSON column change is detected


def _backfill_score_history(session, profile, current_total, max_possible):
    # Deterministic per-profile synthetic history so "since last week" has real
    # data immediately after a fresh seed, without needing days to actually pass.
    rng = random.Random(f"history-{profile.id}")
    total = current_total
    for days_ago in (14, 10, 7, 3):
        drop = rng.randint(0, min(20, total)) if total > 0 else 0
        total = max(0, total - drop)
        session.add(
            ScoreSnapshot(
                profile_id=profile.id,
                total=total,
                max_possible=max_possible,
                recorded_at=datetime.utcnow() - timedelta(days=days_ago),
            )
        )
    session.commit()


def seed_demo():
    with Session(engine) as session:
        session.exec(delete(ScoreSnapshot))
        session.exec(delete(ProSlotWaitlist))
        session.exec(delete(MockEmail))
        session.exec(delete(Profile))
        session.commit()

        profiles = _build_profiles() + _build_generated_profiles()
        for profile in profiles:
            _assign_review_ids(profile)
        session.add_all(profiles)
        session.commit()

        for profile in profiles:
            session.refresh(profile)
            result = recompute_and_save_score(session, profile)
            _backfill_score_history(session, profile, result["total"], result["max_possible"])


if __name__ == "__main__":
    seed_demo()
    print("Seeded 38 demo profiles across 4 markets.")
