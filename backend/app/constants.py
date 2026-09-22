CATEGORY_META = {
    "reviews": {"label": "Reviews & Replies", "max": 300, "color": "#22c55e"},
    "profile_completion": {"label": "Profile Completion", "max": 100, "color": "#a855f7"},
    "connections": {"label": "Connections", "max": 100, "color": "#14b8a6"},
    "web_analytics": {"label": "Website Health", "max": 250, "color": "#3b82f6"},
    "listings": {"label": "Listings", "max": 100, "color": "#f97316"},
}

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

CLAIMED_MAX_SCORE = 500
PRO_MAX_SCORE = 850

# Scarcity: only this many Pro subscriptions (real Pro or an active trial —
# both grant the same scoring boost) per (category, location) market.
PRO_SLOTS_PER_MARKET = 5

# Deliberately simple state-level grouping (not real geo-distance) so the agent
# can honestly compare "nearby" markets — sized to what this demo needs.
MARKET_REGIONS = {
    "Texas": ["Austin, TX", "Houston, TX"],
    "California": ["Los Angeles, CA", "San Francisco, CA"],
}
