"""A real website audit from the page we already fetched during onboarding.

The Website Health section scores five checks on the person's own site (core1: Pro-locked). Rather than
leave them empty for a freshly onboarded profile, they are read off the page itself: a meta description,
a mobile viewport, contact details, opening hours and the load time of a plain request. The load time is
only recorded when the page came back from a plain request; through a browser or proxy the timing says
nothing about the site, so it stays unknown (and unknown is never counted as fast).
"""

import re

from app.scraping.parse import ParsedPage

_HOURS_RE = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b[^\n]{0,40}?\d{1,2}(:\d{2})?\s*(am|pm)\b", re.I)


def website_audit(page: ParsedPage, *, load_time_ms: int | None) -> dict:
    """The keys the Website Health score reads (see app.scoring.compute_web_analytics_score)."""
    return {
        "has_meta_description": bool(page.meta_description),
        "mobile_friendly": page.has_viewport,
        "load_time_ms": load_time_ms,
        "has_contact_info": bool(page.phones or page.emails),
        "has_business_hours_listed": bool(page.json_ld_hours) or bool(_HOURS_RE.search(page.text)),
    }
