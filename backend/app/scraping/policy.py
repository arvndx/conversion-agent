"""Which sites the scraper reads.

Two lists, and one rule: a page is read only if `can_read` says so.

READABLE_PLATFORMS is the allowlist: the only named sites the agent reads from. A website that is not a
named platform (the owner's own site, a team page, anything `platform_for_url` does not recognise) is read
too, since those cannot be listed in advance. A named platform that is on neither list (YouTube, say) is not.

UNREADABLE_PLATFORMS is the skip list. Anonymous visitors get a sign-in or sign-up wall from these, so a read only costs proxy credits and up to a
minute of waiting. Their pages are not shown as cards in onboarding and are never fetched; the owner gives
the link themselves on the details step, and it still counts toward the score (Connections).

Zillow, Facebook and Google Business are NOT here: they gave real data in live runs, and when one is blocked
the source is simply marked "blocked". Add a platform key (as `platform_for_url` returns it) to skip it.
"""

READABLE_PLATFORMS = {
    "website": "Your website",
    "google_business_profile": "Google Business Profile",
    "facebook": "Facebook",
    "zillow": "Zillow",
    "yelp": "Yelp",
    "realtor_com": "Realtor.com",
    "homes_com": "Homes.com",
    "lendingtree": "LendingTree",
    "trusted_choice": "Trusted Choice",
    "healthgrades": "Healthgrades",
}

UNREADABLE_PLATFORMS = {
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "x": "X (Twitter)",
}


GENERIC = (None, "website", "other")  # an ordinary website: not a named platform


def is_unreadable(platform: str | None) -> bool:
    """On the skip list: no card, never fetched; the owner gives that link on the details step."""
    return platform in UNREADABLE_PLATFORMS


def can_read(platform: str | None) -> bool:
    if is_unreadable(platform):
        return False
    return platform in GENERIC or platform in READABLE_PLATFORMS


def refusal(platform: str | None) -> str:
    """Why a page is not read (for the owner and the agent)."""
    if is_unreadable(platform):
        return f"{UNREADABLE_PLATFORMS[platform]} pages are not read"
    return "that site is not on the list of sites we read"
