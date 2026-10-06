# Legacy generic platform lists. Each category now defines its own social and directory URL slots
# (Category.url_slots); these are only the fallback for a profile with no category row, and what the
# seed uses to label generated Connections.
DIRECTORY_PLATFORMS = [
    "Google Business Profile",
    "Yelp",
    "Facebook",
    "Apple Maps",
    "Voice Search",
]

CONNECTION_PLATFORMS = [
    "Google Business Profile",
    "Facebook",
    "LinkedIn",
    "Instagram",
    "Twitter/X",
]


# Scarcity: only this many Pro subscriptions (real Pro or an active trial —
# both grant the same scoring boost) per (category, location) market.
PRO_SLOTS_PER_MARKET = 5

# Deliberately simple state-level grouping (not real geo-distance) so the agent
# can honestly compare "nearby" markets — sized to what this demo needs.
MARKET_REGIONS = {
    "Texas": ["Austin, TX", "Houston, TX"],
    "California": ["Los Angeles, CA", "San Francisco, CA"],
}


# Profile lifecycle ("profile status" in core1.txt). `enterprise` gets Pro benefits but is set only by
# seed/admin: no checkout path and it never takes a Pro slot in a market.
LIFECYCLE_STATES = ("unclaimed", "claimed", "pro", "enterprise")
CLAIMED_STATES = ("claimed", "pro", "enterprise")
PRO_STATES = ("pro", "enterprise")

# Score section keys (stored per category in category_score_sections). `web_analytics` is the
# "Website Health" section; the key is kept so existing code and the UI keep working.
SCORE_SECTIONS = ("reviews", "profile_completion", "connections", "web_analytics", "listings")
