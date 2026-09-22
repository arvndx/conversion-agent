from app.models import Profile

# Transparent and computable, not a black-box model — consistent with how every
# other "score" in this app works. The raw visit count is never shown to the
# model as a quotable number; only this boolean is.
HOT_LEAD_VISIT_THRESHOLD = 3


def is_hot_lead(profile: Profile) -> bool:
    return profile.pricing_page_visits >= HOT_LEAD_VISIT_THRESHOLD
