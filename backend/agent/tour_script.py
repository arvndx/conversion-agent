"""The guided tour's fixed sequence — deterministic scaffolding, not something the
model improvises. Each stop names a real UI target and which tools supply the real
numbers for it; the model still writes the actual explanation, but never invents the
sequence or the target element.
"""

TOUR_STEPS = [
    {
        "id": "overview",
        "title": "Your Search Rank Score",
        "ui_target": "score-gauge",
        "route": "dashboard",
        "purpose": "Explain what the Search Rank Score is (0-850, 5 categories) and their current standing.",
        "data_tools": ["get_score_snapshot"],
    },
    {
        "id": "reviews",
        "title": "Reviews & Replies",
        "ui_target": "manage-reviews-section",  # overridden per-request to review-{id} if one is unreplied
        "route": "manage",
        "purpose": "On the real Manage page now — explain how replying to reviews raises this category. If "
        "there's an unreplied review (now visible on screen), quantify the real point impact of replying to it "
        "and offer to draft a reply.",
        "data_tools": ["get_score_snapshot", "get_unreplied_reviews", "simulate_score_change"],
    },
    {
        "id": "profile_completion",
        "title": "Profile Completion",
        "ui_target": "manage-profile-details",
        "route": "manage",
        "purpose": "Point at the real editable Profile Details fields now on screen — explain which are missing "
        "and the real point value of filling them in.",
        "data_tools": ["get_score_snapshot", "simulate_score_change"],
    },
    {
        "id": "connections",
        "title": "Connections",
        "ui_target": "manage-connections-section",
        "route": "manage",
        "purpose": "Point at the real Connections toggles now on screen — explain linking other platforms and "
        "the real point value.",
        "data_tools": ["get_score_snapshot", "simulate_score_change"],
    },
    {
        "id": "web_analytics",
        "title": "Website Health (Pro)",
        "ui_target": "manage-analytics-section",
        "route": "manage",
        "purpose": "Point at the real (locked) Website Health section now on screen — this is a real audit of "
        "their own website (load time, mobile-friendliness, visible contact info/hours, meta description), not "
        "listing traffic. If they have a website, mention what the audit actually found via get_cost_of_inaction; "
        "if they don't have one yet, say so plainly. State the real locked points, then use preview_pro_card to "
        "show the real rank move if they unlocked it.",
        "data_tools": ["get_upsell_pitch", "get_cost_of_inaction", "preview_pro_card"],
    },
    {
        "id": "listings",
        "title": "Listings (Pro)",
        "ui_target": "manage-listings-section",
        "route": "manage",
        "purpose": "Point at the real (locked) Listings section now on screen — explain syndication to "
        "Google/Yelp/Apple Maps/Voice Search and its real locked points.",
        "data_tools": ["get_upsell_pitch", "preview_pro_card"],
    },
    {
        "id": "wrap_up",
        "title": "Putting it together",
        "ui_target": "pricing-card",
        "route": "upgrade",
        "purpose": "Now on the real pricing page — summarize the full real opportunity (total locked points, "
        "real market rank as Pro, real slot scarcity, any active discount via get_active_offer) and ask if "
        "they'd like to start a trial, subscribe right here, or keep exploring.",
        "data_tools": ["get_peer_benchmark", "preview_pro_card", "get_nearby_market_opportunities", "get_active_offer"],
    },
]

# Suffixes resolved against the profile's own id — never let the model supply a raw path here.
ROUTE_PATH_TEMPLATES = {
    "dashboard": "/dashboard/{id}",
    "manage": "/dashboard/{id}/manage",
    "upgrade": "/dashboard/{id}/upgrade",
}
