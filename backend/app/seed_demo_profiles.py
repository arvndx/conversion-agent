"""Demo profiles for the four core1.txt categories.

1. DEMO_PROFILES: eight real professionals (two per category) whose public experience.com pages were
   supplied as demo data. They are seeded as *unclaimed*, holding only what a scraping team would
   plausibly have: name, phone, company, title, services and the profile URLs. Everything else
   (hours, address, description, awards, license, year started, service area, specialities) is left
   empty on purpose, for the claim and onboarding flow to find by scraping those URLs.
   `reference` records what each public page shows, for tests and for checking scrape results; it is
   not written to the database. Emails are synthetic (@demo.clearrank.test); no real email is stored.
2. build_peers(): clearly fake peer profiles (fake names, @example.test emails, 555 phone numbers) in
   each demo profile's market, so ranks and "rank X to Y" Pro previews mean something. A mix of
   unclaimed, claimed, Pro and enterprise (enterprise takes no Pro slot, so the market never fills).
"""

import random

from app.models import Profile, ProfileLink
from app.seed_taxonomy import _slug as service_key

# --- The eight demo professionals ---------------------------------------------------------------------

DEMO_PROFILES = [
    {
        "name": "Antonio Atoche",
        "category": "Real Estate Agent",
        "location": "Gardena, CA",
        "company": "Antonio Atoche, Broker",
        "title": "Broker Associate",
        "phone": "(310) 345-1513",
        "website": "https://antonioatoche.com",
        "services": ["Residential real estate", "Lots and land", "Vacation homes", "Foreclosure sales"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJAa-d6mG1woARbZy08zOnW8o",
            "facebook": "https://facebook.com/276135922430088",
            "linkedin": "https://www.linkedin.com/in/antonioatoche/",
            "x": "https://twitter.com/antonioatoche",
            "instagram": "https://www.instagram.com/antonioatoche",
            "zillow": "https://www.zillow.com/profile/Antonio%20Atoche/",
        },
        "reference": {"license": "00953056", "year_started": 1987, "awards": "100% Club at Remax", "rating": 4.97, "review_count": 379},
    },
    {
        "name": "Jeff Tricoli Team",
        "category": "Real Estate Agent",
        "location": "West Palm Beach, FL",
        "company": "Keller Williams Realty",
        "title": "Real Estate Broker Associate",
        "phone": "(561) 220-4300",
        "website": "https://TricoliTeam.com",
        "services": ["Residential real estate"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJjwyokAsp2YgRgHX6-x9C75s",
            "facebook": "https://facebook.com/105992025701579",
            "linkedin": "https://www.linkedin.com/in/jefftricoli/",
            "x": "https://twitter.com/realtypalmbeach",
            "instagram": "https://www.instagram.com/tricoliteam",
            "zillow": "https://www.zillow.com/profile/TheTricoliTeam/",
            "realtor_com": "https://www.realtor.com/realestateagents/56966b5789a68901006bd0f3",
        },
        "reference": {"license": "BK3082942", "year_started": 2004, "awards": "2022 #1 Luxury Group; 2023 #1 Real Estate Group", "rating": 4.97, "review_count": 2654},
    },
    {
        "name": "Ryan Davis",
        "category": "Insurance Agent",
        "location": "West Jordan, UT",
        "company": "Allstate Insurance Company",
        "title": "Allstate Insurance Agent",
        "phone": "(801) 280-7115",
        "website": "https://agents.allstate.com/ryan-davis-west-jordan-ut.html",
        "services": ["Auto insurance", "Life insurance"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJP1mxOtiPUocRdEqDyE5jcCk",
            "facebook": "https://facebook.com/113384630522277",
        },
        "reference": {"license": "Property and Casualty License", "year_started": 2020, "awards": "2X Honor Ring, National Conference Champion", "rating": 4.72, "review_count": 437},
    },
    {
        "name": "David Worley",
        "category": "Insurance Agent",
        "location": "McKinney, TX",
        "company": "Allstate Insurance Company",
        "title": "Allstate Insurance Agent",
        "phone": "(469) 214-7311",
        "website": "https://agents.allstate.com/david-worley-mckinney-tx.html",
        "services": ["Auto insurance", "Property insurance"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJDVtKTrQTTIYRFEhGLN7B_B8",
        },
        "reference": {"license": "Texas Property & Casualty; Texas Life & Health", "year_started": 2009, "awards": "Topper Club", "rating": 4.86, "review_count": 407},
    },
    {
        "name": "Chuck Tegano",
        "category": "Mortgage Loan Officer",
        "location": "East Brunswick, NJ",
        "company": "AnnieMac Home Mortgage",
        "title": "Mortgage Loan Originator",
        "phone": "(732) 317-0735",
        "website": "https://annie-mac.com/lo/chucktegano",
        "services": ["FHA home loan", "VA home loan", "Jumbo loan", "Mortgage refinance"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJ____NJXFw4kRQV_7UbPmuFI",
            "facebook": "https://facebook.com/843612875668522",
            "linkedin": "https://www.linkedin.com/in/chucktegano/",
            "x": "https://twitter.com/chucktegano",
            "instagram": "https://www.instagram.com/chucktegano",
            "zillow": "https://www.zillow.com/lender-profile/chucktegano",
        },
        "reference": {"license": "NMLS # 209374", "year_started": 2005, "awards": "Top 1% in Customer Satisfaction in the Country", "rating": 4.98, "review_count": 875},
    },
    {
        "name": "Jennifer Ballheimer",
        "category": "Mortgage Loan Officer",
        "location": "Memphis, TN",
        "company": "Mortgage Financial Services",
        "title": "Regional Production Manager",
        "phone": "(501) 472-8109",
        "website": "https://jballheimer.mortgagefinancial.com/",
        "services": ["FHA home loan", "VA home loan", "Jumbo loan", "Mortgage refinance", "Down payment assistance"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJgXLmcd_Ltm4RHtg7ybHu9DY",
            "facebook": "https://facebook.com/1389204367984858",
            "linkedin": "https://www.linkedin.com/in/jennifer-ballheimer-25181b1a7",
            "x": "https://twitter.com/mortgageprojenn",
            "instagram": "https://www.instagram.com/mortgageprojenn",
            "zillow": "https://www.zillow.com/lender-profile/jballheimer",
        },
        "reference": {"license": "RMLO NMLS 143750", "year_started": 2004, "awards": "1st Place Winner in Customer Satisfaction 2019", "rating": 4.98, "review_count": 2268},
    },
    {
        "name": "Jonathan Sweat",
        "category": "Mortgage Lender",
        "location": "Roanoke, VA",
        "company": "Integrity Home Mortgage Corporation",
        "title": "Branch Manager",
        "phone": "(540) 314-8843",
        "website": "https://www.jonathansweat.com",
        "services": ["FHA home loan", "VA home loan", "Jumbo loan", "Mortgage refinance", "Fixed rate mortgage"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJQQUMHM0NTYgRHPkKf0UwJJc",
            "facebook": "https://facebook.com/523686151013499",
            "linkedin": "https://www.linkedin.com/in/c-jonathan-sweat/",
            "x": "https://twitter.com/CashDaddySweat",
            "instagram": "https://www.instagram.com/thelegacyteamihmc",
            "zillow": "https://www.zillow.com/lender-profile/Jonathan%20Sweat/",
        },
        "reference": {"license": "NMLS #308553", "year_started": 1996, "awards": "Best of Roanoke", "rating": 4.91, "review_count": 550},
    },
    {
        "name": "Melissa Tippey",
        "category": "Mortgage Lender",
        "location": "Salem, OR",
        "company": "Guild Mortgage",
        "title": "Senior Loan Officer",
        "phone": "(503) 881-4401",
        "website": "https://tippeysapp.com",
        "services": ["FHA home loan", "VA home loan", "Jumbo loan", "Non-QM", "Fixed rate mortgage"],
        "links": {
            "google_business_profile": "https://www.google.com/maps/place/?q=place_id:ChIJj_Pq8mAHwFQRozvcUCDNAwo",
            "facebook": "https://facebook.com/166828414121554",
            "linkedin": "https://www.linkedin.com/in/melissa-tippey-1406b760/",
            "x": "https://twitter.com/MelissaTippey",
            "instagram": "https://www.instagram.com/melissa.tippey",
            "zillow": "https://www.zillow.com/lender-profile/melissatippey",
        },
        "reference": {"license": "NMLS# 1034387", "year_started": 2011, "awards": "RESILIENCE", "rating": 4.97, "review_count": 383},
    },
]

DEMO_EMAIL_DOMAIN = "demo.clearrank.test"

# Sample reviews for the demo profiles (the public pages hold hundreds; a handful of generic ones are
# enough for the score and the reply flow).
_DEMO_REVIEWS = {
    "Mortgage": [
        (5, "Made the whole loan process painless and kept us updated every step."),
        (5, "Fast, clear and honest about our options. Closed on time."),
        (4, "Knowledgeable and responsive, would recommend."),
        (5, "Explained everything in plain language. Great rate too."),
        (3, "Good outcome, communication could have been quicker at times."),
    ],
    "Real Estate": [
        (5, "Sold our home quickly and for more than we expected."),
        (5, "Patient with first-time buyers and great negotiator."),
        (4, "Professional, knows the area well."),
        (5, "Always available and on top of every detail."),
        (3, "Solid agent, showings took a while to schedule."),
    ],
    "Insurance": [
        (5, "Found us better coverage for less. Very helpful."),
        (5, "Quick to respond when we needed to file a claim."),
        (4, "Friendly and explains the policy clearly."),
        (5, "Reviewed all our policies and saved us money."),
        (3, "Good service, a few unreturned calls."),
    ],
}

# --- Fake peers -----------------------------------------------------------------------------------------

FIRST_NAMES = [
    "Avery", "Blake", "Cameron", "Dana", "Emery", "Finley", "Gray", "Harper", "Indigo", "Jules",
    "Kai", "Logan", "Marlow", "Noel", "Oakley", "Parker", "Quincy", "Remy", "Sasha", "Tatum",
    "Umber", "Vale", "Wren", "Xan", "Yael", "Zion",
]
LAST_NAMES = [
    "Ashford", "Bellamy", "Calloway", "Draper", "Ellison", "Fairbanks", "Garrison", "Hartwell",
    "Ingram", "Jennings", "Kingsley", "Langford", "Montgomery", "Northcott", "Oakes", "Prescott",
    "Quillen", "Radcliffe", "Sterling", "Thornton", "Underwood", "Vaughn", "Whitaker", "Yardley",
]
COMPANY_SUFFIX = {
    "Mortgage Loan Officer": ["Home Loans", "Mortgage Group", "Lending"],
    "Mortgage Lender": ["Mortgage Corp", "Funding", "Lending Partners"],
    "Real Estate Agent": ["Realty", "Real Estate Group", "Homes"],
    "Insurance Agent": ["Insurance Agency", "Insurance Group", "Coverage Partners"],
}
PEER_TITLES = {
    "Mortgage Loan Officer": ["Mortgage Loan Officer", "Senior Loan Officer"],
    "Mortgage Lender": ["Mortgage Lender", "Branch Manager"],
    "Real Estate Agent": ["Real Estate Agent", "Broker Associate"],
    "Insurance Agent": ["Insurance Agent", "Agency Owner"],
}
STATE_AREA_CODES = {"CA": "310", "FL": "561", "UT": "801", "TX": "469", "NJ": "732", "TN": "901", "VA": "540", "OR": "503"}
BASIC_VALUES = {
    "specialities": "First-time clients, referrals",
    "awards": "Regional top producer",
    "achievements": "Hundreds of satisfied clients",
    "year_started": "2012",
    "service_area": "Local area and surrounding cities",
    "business_timing": "Monday–Friday, 9 AM – 6 PM",
}

# Peers per market, as (state, count): the demo profile's own unclaimed record is not counted.
PEER_TIERS = (["enterprise"] * 4) + (["pro"] * 3) + (["claimed"] * 11) + (["unclaimed"] * 6)


def _vertical_reviews(vertical: str) -> list[tuple[int, str]]:
    return _DEMO_REVIEWS[vertical]


def demo_reviews(rng: random.Random, vertical: str, count: int, reply_rate: float) -> list[dict]:
    reviews = []
    pool = _vertical_reviews(vertical)
    for _ in range(count):
        rating, body = rng.choice(pool)
        first, last = rng.choice(FIRST_NAMES), rng.choice("ABCDEFGHJKLMNPRSTW")
        reply = f"Thank you, {first}! We appreciate your feedback." if rng.random() < reply_rate else None
        reviews.append({"reviewer_name": f"{first} {last}.", "rating": rating, "body": body, "reply": reply})
    return reviews


def _slug(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")


def build_demo_profiles(categories: dict, verticals: dict) -> tuple[list[Profile], list[list[tuple[str, str]]]]:
    """The eight real demo professionals as thin unclaimed records, plus each one's (platform, url) links.

    `categories` maps category name -> Category row (with `.services` resolved by the caller via
    `service_keys`), `verticals` maps vertical id -> name.
    """
    profiles, links = [], []
    for i, spec in enumerate(DEMO_PROFILES):
        category = categories[spec["category"]]
        rng = random.Random(f"demo-{spec['name']}")
        profile = Profile(
            name=spec["name"],
            category=spec["category"],
            category_id=category.id,
            vertical=verticals[category.vertical_id],
            location=spec["location"],
            email=f"{_slug(spec['name'])}@{DEMO_EMAIL_DOMAIN}",
            lifecycle_state="unclaimed",
            phone_number=spec["phone"],
            business_name=spec["company"],
            title=spec["title"],
            website_url=spec["website"],
            services=[service_key(s) for s in spec["services"]],
            avatar_url=f"/avatars/avatar-{i % 5 + 1}.svg",
            reviews=demo_reviews(rng, verticals[category.vertical_id], rng.randint(4, 6), reply_rate=0.0),
            view_count=rng.randint(40, 120),
        )
        profiles.append(profile)
        links.append([("website", spec["website"])] + list(spec["links"].items()))
    return profiles, links


def build_peers(categories: dict, verticals: dict, make_connections, make_audit, directory_for) -> list[Profile]:
    """Fake peers in each demo market (category + location), see the module docstring."""
    peers = []
    for spec in DEMO_PROFILES:
        category = categories[spec["category"]]
        vertical = verticals[category.vertical_id]
        state = spec["location"].split(",")[-1].strip()
        city = spec["location"].split(",")[0].strip()
        rng = random.Random(f"peers-{spec['category']}-{spec['location']}")
        names = [(f, l) for f in FIRST_NAMES for l in LAST_NAMES]
        rng.shuffle(names)
        for n, tier in enumerate(PEER_TIERS):
            first, last = names[n]
            business = f"{last} {rng.choice(COMPANY_SUFFIX[spec['category']])}"
            peers.append(
                _peer(rng, category, vertical, spec, city, state, f"{first} {last}", business, tier, n, make_connections, make_audit, directory_for)
            )
    return peers


def _peer(rng, category, vertical, spec, city, state, name, business, tier, n, make_connections, make_audit, directory_for):
    basic_keys = [f["key"] for f in category.basic_fields]
    fill_odds = {"enterprise": 0.9, "pro": 0.85, "claimed": 0.45, "unclaimed": 0.0}[tier]
    values = {}
    for key in basic_keys:
        if rng.random() < fill_odds:
            values[key] = BASIC_VALUES.get(key)
    values["business_name"] = business
    values["title"] = rng.choice(PEER_TITLES[spec["category"]])
    website = f"https://{_slug(business)}.example.test" if rng.random() < {"enterprise": 1, "pro": 1, "claimed": 0.5, "unclaimed": 0}[tier] else None
    if "license_number" in basic_keys and rng.random() < fill_odds:
        values["license_number"] = f"LIC-{rng.randint(100000, 999999)}"
    if "address" in basic_keys and rng.random() < fill_odds:
        values["address"] = f"{rng.randint(100, 9999)} Main St, {spec['location']}"
    if "bio" in basic_keys and rng.random() < fill_odds:
        values["bio"] = f"{name} serves clients in {city}."
    review_count = {"enterprise": rng.randint(8, 12), "pro": rng.randint(7, 11), "claimed": rng.randint(2, 7), "unclaimed": rng.randint(0, 3)}[tier]
    reviews = demo_reviews(rng, vertical, review_count, reply_rate={"enterprise": 0.9, "pro": 0.8, "claimed": 0.4, "unclaimed": 0.0}[tier])
    connected = {"enterprise": 5, "pro": 4, "claimed": rng.randint(0, 3), "unclaimed": 0}[tier]
    directory = directory_for(category, {"enterprise": 1.0, "pro": 0.75, "claimed": 0.0, "unclaimed": 0.0}[tier])
    return Profile(
        name=name,
        category=spec["category"],
        category_id=category.id,
        vertical=vertical,
        location=spec["location"],
        email=f"{_slug(name)}@example.test",
        lifecycle_state=tier,
        phone_number=f"({STATE_AREA_CODES.get(state, '555')}) 555-{rng.randint(100, 199):04d}",
        website_url=website,
        website_audit=make_audit(rng, website) if tier != "unclaimed" else {},
        reviews=reviews,
        connections=make_connections(rng, connected) if tier != "unclaimed" else [],
        directory_listings=directory,
        avatar_url=f"/avatars/avatar-{n % 5 + 1}.svg",
        authority_score=rng.randint(5, 60),
        view_count=rng.randint(30, 900),
        **{k: v for k, v in values.items() if v is not None},
    )


def link_rows(profile_id: int, pairs: list[tuple[str, str]]) -> list[ProfileLink]:
    return [ProfileLink(profile_id=profile_id, platform=platform, url=url, confirmed=False, source="db") for platform, url in pairs]
