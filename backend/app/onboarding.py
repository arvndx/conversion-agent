"""Onboarding (core1.txt, Process 2): confirm URLs, scrape them in parallel, check the person, merge what
was found, resolve conflicts, finish.

This module holds the rules and the state; it makes no model calls itself. The onboarding agent (agent/)
decides what to do next and calls these functions through tools, and the UI records the user's choices
through the REST routes, which call the same functions. That is what makes the gates real rather than
prompt text:

* only URLs the user confirmed are ever scraped;
* a page's data is used only after the person's name is found on it (otherwise the user is asked "is this
  your profile?" and the data stays unused until they say yes);
* the details verified at claim time (name, email, phone, vertical, category, services) are never
  overwritten by scraped data;
* values that differ between sources, or from what we hold, are raised as conflicts and only applied
  once the user has chosen;
* onboarding cannot be completed with unresolved conflicts, pending identity checks or unscraped URLs.

Everything scraped is untrusted text from the open web: it is stripped of markup, length-capped and
URL-checked before it can reach a profile field.
"""

import copy
import difflib
import re
import threading
from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlmodel import Session, select

from app.category_config import config_for
from app.constants import CLAIMED_STATES
from app.models import Profile, ProfileConflict, ProfileLink, ProfileSource
from app.scoring import compute_total_score, recompute_and_save_score
from app.scraping.fetch import normalize_url
from app.scraping.parse import platform_for_url
from app.scraping.policy import UNREADABLE_PLATFORMS, can_read, is_unreadable, refusal
from app.scraping.runner import extract_confirmed, scrape_sources
from app.scraping.safety import check_public_url
from app.slots import simulate_rank

# --- Configuration ------------------------------------------------------------------------------------

VERIFIED_FIELDS = {"name", "email", "phone_number", "vertical", "category", "category_id", "services"}

# Scraped single values: extracted key -> (profile field, max length)
SINGLE_FIELDS = {
    "title": ("title", 120),
    "company_name": ("business_name", 150),
    "website_url": ("website_url", 500),
    "business_hours": ("business_timing", 200),
    "description": ("bio", 1500),
    "year_started": ("year_started", 4),
}
# Scraped lists, merged together rather than disputed: extracted key -> (profile field, joiner, max length)
LIST_FIELDS = {
    "awards": ("awards", "; ", 600),
    "achievements": ("achievements", "; ", 600),
    "service_area": ("service_area", ", ", 300),
    "specialities": ("specialities", ", ", 300),
}
ADDRESS_MAX = 250
LICENSE_MAX = 60
MIN_SIMILARITY = 0.88  # two values this alike are the same fact written differently

# What the agent may set by hand (AI drafts it accepted, or what the user typed): the category's basic fields.
FIELD_MAX = {
    "specialities": 300, "title": 120, "address": ADDRESS_MAX, "website_url": 500, "business_timing": 200,
    "bio": 1500, "awards": 600, "achievements": 600, "year_started": 4, "business_name": 150,
    "license_number": 200, "service_area": 300,
}

_extractor = None


def set_extractor(extractor) -> None:
    """Register the function that turns a page into fields (agent.extraction.extract_fields). Wired by
    main.py, so this module never imports the agent package."""
    global _extractor
    _extractor = extractor


# --- Cleaning untrusted text --------------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]*>")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(value, limit: int) -> str:
    """Plain text only: markup removed, whitespace collapsed, length capped."""
    text = _CONTROL.sub(" ", _TAGS.sub(" ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:limit]


_DAY_WORDS = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun|daily|weekdays?|weekends?|24 ?(hours|/7|hrs)|by appointment|(mo|tu|we|th|fr|sa|su)(?=\s*[-–,:]|\s+\d))", re.I)  # the last form is schema.org's "Mo-Fr 09:00-17:00"


def usable_hours(text: str) -> str:
    """Opening hours must name days or say 24 hours / by appointment. A live status label such as
    "Closed now" or "Opens 9 AM" (Google shows these beside the hours) says nothing about the hours."""
    return text if _DAY_WORDS.search(text) else ""


_DAY_NAMES = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*", re.I)


def partial_week(text: str) -> bool:
    """Google Business shows only one or two days of hours without a click ("Wednesday 8 am–8 pm"): that is
    a slice of the week, not the hours, and would only start a pointless disagreement with the full hours
    on the person's own site. A range such as "Mon-Fri" names two days but covers five, so it is not partial."""
    days = {m.group(1).lower() for m in _DAY_NAMES.finditer(text)}
    return 0 < len(days) < 3 and not re.search(r"[-–]\s*(mon|tue|wed|thu|fri|sat|sun)|\bto\b|daily|weekdays?|24 ?(hours|/7)", text, re.I)


def _items(value, limit: int) -> list[str]:
    values = value if isinstance(value, list) else ([value] if value else [])
    seen, out = set(), []
    for item in values:
        text = clean_text(item, limit)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"[,.#]", " ", str(text).lower())).replace("  ", " ").strip()


_ADDRESS_WORDS = {"suite": "ste", "street": "st", "avenue": "ave", "boulevard": "blvd", "road": "rd", "drive": "dr", "unit": "ste",
                  "parkway": "pkwy", "lane": "ln", "court": "ct", "place": "pl", "highway": "hwy", "north": "n", "south": "s", "east": "e", "west": "w"}


_UNIT = re.compile(r"^(suite|ste|unit|apt|apartment|floor|fl|#)\b", re.I)


def _norm_address(text: str) -> str:
    words = [_ADDRESS_WORDS.get(w, w) for w in _norm(str(text).replace("-", " ")).split() if w not in ("united", "states", "usa", "us")]
    return " ".join(words)


def _address_parts(text: str) -> tuple[str, set[str]]:
    """(street line, city words) of an address. Suite/unit parts, state names, zips and the country are
    dropped, so "1425 Artesia Blvd Suite 18, Gardena, CA 90248, United States" and "1425 Artesia Blvd,
    Gardena, California" reduce to the same thing."""
    parts = [p.strip() for p in str(text).split(",") if p.strip()]
    street = _norm_address(re.sub(r"\b(suite|ste|unit|apt|floor|fl)\b\.?\s*#?\w*|#\s*\w+", " ", parts[0], flags=re.I)) if parts else ""
    cities = {
        _norm_address(p) for p in parts[1:]
        if re.search(r"[A-Za-z]{3,}", p) and not _UNIT.match(p) and not re.fullmatch(r"[A-Z]{2}(\s+\d{5}(-\d{4})?)?", p.strip())
        and _norm_address(p) not in _US_STATES and not re.fullmatch(r"\d{5}(-\d{4})?", p.strip())
    }
    return street, cities


_US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas",
    "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
}


def _same_address(a: str, b: str) -> bool:
    street_a, cities_a = _address_parts(a)
    street_b, cities_b = _address_parts(b)
    if not street_a or not street_b:
        return False
    number_a, number_b = re.match(r"\d+", street_a), re.match(r"\d+", street_b)
    if number_a and number_b and number_a.group() != number_b.group():
        return False  # 1425 and 1427 are different buildings
    close = street_a == street_b or difflib.SequenceMatcher(None, street_a, street_b).ratio() >= 0.9
    return close and (not cities_a or not cities_b or bool(cities_a & cities_b))


_norm_address_marker = object()  # passed as `normalize` to compare two values as addresses


def _same(a: str, b: str, normalize=_norm) -> bool:
    if normalize is _norm_address_marker:
        return _same_address(a, b)
    na, nb = normalize(a), normalize(b)
    return bool(na) and (na == nb or difflib.SequenceMatcher(None, na, nb).ratio() >= MIN_SIMILARITY)


def _license_key(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) >= 4 else _norm(text)


def _norm_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}{'?' + parsed.query if parsed.query else ''}"


def _host(url: str) -> str:
    return (urlparse(url if "://" in url else f"https://{url}").hostname or url).removeprefix("www.")


def _year(value) -> str | None:
    match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    year = int(match.group()) if match else 0
    return str(year) if 1900 <= year <= datetime.utcnow().year else None


# --- Guards -------------------------------------------------------------------------------------------


def _require_active(profile: Profile) -> None:
    if profile.lifecycle_state not in CLAIMED_STATES:
        raise HTTPException(status_code=409, detail="Claim this profile before onboarding.")
    if profile.onboarding_completed_at is not None:
        raise HTTPException(status_code=409, detail="Onboarding is already complete.")


def _source(session: Session, profile: Profile, source_id: int) -> ProfileSource:
    source = session.get(ProfileSource, source_id)
    if source is None or source.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="That URL is not part of this profile's onboarding.")
    return source


def _label_options(profile: Profile) -> dict[str, str]:
    """label (lowercase) -> platform key, for the URL label dropdown: this category's slots plus the
    generic labels from its rules."""
    config = config_for(profile)
    labels = {s["label"].lower(): s["platform"] for s in config.url_slots}
    labels["website"] = "website"
    labels["personal website"] = "website"
    for label in config.rules.get("onboarding", {}).get("url_labels", []):
        platform = label.lower().replace(" profile", "").strip()
        labels.setdefault(label.lower(), {"personal": "website", "linkedin": "linkedin", "yelp": "yelp", "zillow": "zillow", "instagram": "instagram"}.get(platform, platform))
    return labels


def url_label_choices(profile: Profile) -> list[str]:
    """The labels offered when typing a URL. The never-read platforms (LinkedIn, ...) are left out: their
    links are asked for on the details step instead."""
    config = config_for(profile)
    labels = ["Website"] + [s["label"] for s in config.url_slots]
    labels += [l.title() for l in config.rules.get("onboarding", {}).get("url_labels", [])]
    options = _label_options(profile)
    return [l for l in dict.fromkeys(labels) if not is_unreadable(options.get(l.lower()))]


# --- URLs: known, searched, manual ----------------------------------------------------------------------


def start(session: Session, profile: Profile) -> int:
    """Turn the profile's known URLs (from our database) into sources waiting for the user's yes/no.
    Safe to call again: URLs that already have a source are left alone."""
    _require_active(profile)
    existing = {_norm_url(s.url) for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)).all()}
    links = session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all()
    if profile.website_url and not any(l.platform == "website" for l in links):
        link = ProfileLink(profile_id=profile.id, platform="website", url=profile.website_url, source="db")
        session.add(link)
        links.append(link)
    added = 0
    for link in links:
        if not can_read(link.platform) or not can_read(platform_for_url(link.url)):  # skip list: asked for on the details step; otherwise not on the allowlist
            continue
        if _norm_url(link.url) in existing or check_public_url(link.url):
            continue
        session.add(ProfileSource(profile_id=profile.id, url=link.url, platform=link.platform, label=link.label, status="proposed"))
        existing.add(_norm_url(link.url))
        added += 1
    session.commit()
    return added


def propose_candidates(session: Session, profile: Profile, candidates: list[dict]) -> dict:
    """URLs the agent found by searching, each with a confidence (0-100) and a suggested label. They wait
    for the user's choice like any other."""
    _require_active(profile)
    existing = {_norm_url(s.url) for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)).all()}
    added, skipped = [], []
    for c in candidates or []:
        url = str(c.get("url") or "").strip()
        reason = check_public_url(url)
        found_platform = platform_for_url(url)
        if reason:
            skipped.append({"url": url[:200], "reason": reason})
        elif is_unreadable(found_platform):  # never read: the link is kept (to confirm later), with no card
            kept = _keep_found_link(session, profile, found_platform, url)
            skipped.append({"url": url, "reason": refusal(found_platform) + ("; saved as a link for the owner to confirm" if kept else "; already have it")})
        elif not can_read(found_platform):
            skipped.append({"url": url, "reason": refusal(found_platform)})
        elif _norm_url(url) in existing:
            skipped.append({"url": url, "reason": "already listed"})
        else:
            try:
                confidence = max(0, min(100, int(c.get("confidence_percent", c.get("confidence", 0)))))
            except (TypeError, ValueError):
                confidence = 0
            platform = platform_for_url(url) or _label_options(profile).get(clean_text(c.get("label"), 40).lower())
            source = ProfileSource(profile_id=profile.id, url=url, platform=platform, label=clean_text(c.get("label"), 40) or None,
                                   status="proposed", confidence=confidence)
            session.add(source)
            existing.add(_norm_url(url))
            added.append(source)
    session.commit()
    for s in added:
        session.refresh(s)
    return {"added": [_source_row(s) for s in added], "skipped": skipped}


def _keep_found_link(session: Session, profile: Profile, platform: str, url: str) -> bool:
    """A never-read platform's link, found by the search: stored unconfirmed (the owner says yes to it in the
    app) unless we already hold a link for that platform. True when a new link was saved."""
    if any(l.platform == platform for l in session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all()):
        return False
    session.add(ProfileLink(profile_id=profile.id, platform=platform, url=url[:500], source="search", confirmed=False))
    return True


def add_manual(session: Session, profile: Profile, url: str, label: str | None) -> ProfileSource | None:
    """A URL the user typed in: it is already confirmed, since they supplied it. A never-read platform
    (LinkedIn, ...) is kept as a link that counts toward the score, with no page to read, so None comes back."""
    _require_active(profile)
    url = (url or "").strip()
    reason = check_public_url(url)
    if reason:
        raise HTTPException(status_code=400, detail=f"That address can't be used: {reason}.")
    label = clean_text(label, 40) or None
    platform = platform_for_url(url) or _label_options(profile).get((label or "").lower()) or "other"
    if is_unreadable(platform):
        set_link(session, profile, platform, url)
        return None
    if not can_read(platform):
        raise HTTPException(status_code=400, detail=f"We can't read pages from there: {refusal(platform)}.")
    existing = next((s for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)).all() if _norm_url(s.url) == _norm_url(url)), None)
    if existing is not None and existing.status in ("scraping", "done", "needs_identity"):
        raise HTTPException(status_code=409, detail="That address has already been read.")
    source = existing or ProfileSource(profile_id=profile.id, url=url)
    source.platform, source.label, source.status, source.confidence = platform, label, "confirmed", None
    session.add(source)
    _link(session, profile, source)
    session.commit()
    session.refresh(source)
    return source


def sync_links_to_score(session: Session, profile: Profile) -> dict[str, list[str]]:
    """Confirmed profile URLs count toward the score (core1): a social or Google page is a Connection, a
    directory page (Zillow, LendingTree, Yelp, ...) is a Listing. Only ever turns entries ON, so what the
    owner toggled on the Manage page is never undone; a rejected page stops counting at the next sync only
    for links that were never switched on. Returns the labels newly switched on, per section."""
    config = config_for(profile)
    owned = {
        l.platform for l in session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id, ProfileLink.confirmed == True)).all()  # noqa: E712
    }
    turned_on: dict[str, list[str]] = {"connections": [], "listings": []}

    connections = copy.deepcopy(profile.connections or [])
    for slot in config.slots("social"):
        if slot["platform"] not in owned:
            continue
        entry = next((c for c in connections if slot["label"] in (c.get("platform_name"), c.get("platform")) or c.get("platform") == slot["platform"]), None)
        if entry is None:
            connections.append({"platform_name": slot["label"], "is_connected": True})
            turned_on["connections"].append(slot["label"])
        elif not entry.get("is_connected"):
            entry["is_connected"] = True
            turned_on["connections"].append(slot["label"])

    listings = copy.deepcopy(profile.directory_listings or {})
    platforms = listings.setdefault("platforms", [])
    for slot in config.slots("directory"):
        if slot["platform"] not in owned:
            continue
        entry = next((p for p in platforms if slot["label"] in (p.get("name"), p.get("platform")) or p.get("platform") == slot["platform"]), None)
        if entry is None:
            platforms.append({"name": slot["label"], "is_published": True})
            turned_on["listings"].append(slot["label"])
        elif not entry.get("is_published"):
            entry["is_published"] = True
            turned_on["listings"].append(slot["label"])

    if turned_on["connections"]:
        profile.connections = connections  # reassigned so the JSON change is detected
    if turned_on["listings"]:
        profile.directory_listings = listings
    return turned_on


def set_link(session: Session, profile: Profile, platform: str, url: str | None) -> ProfileLink | None:
    """The owner's own link for a never-read platform (LinkedIn, Instagram, X), from the details step. It is
    not fetched; it counts toward Connections as soon as it is saved. An empty URL declines the link (the owner said it is not theirs): it stays on record so it is never asked about again."""
    _require_active(profile)
    if not is_unreadable(platform):
        raise HTTPException(status_code=400, detail="Only LinkedIn, Instagram and X links are entered this way.")
    label = UNREADABLE_PLATFORMS[platform]
    link = next((l for l in session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all() if l.platform == platform), None)
    url = (url or "").strip()
    if not url:  # "not mine": remembered as declined, so a later merge does not find it on a page and ask again
        if link is not None:
            link.confirmed, link.source = False, "declined"
            session.add(link)
            session.commit()
        return None
    url = normalize_url(url)[:500]
    reason = check_public_url(url)
    if reason:
        raise HTTPException(status_code=400, detail=f"That address can't be used: {reason}.")
    if platform_for_url(url) != platform:
        raise HTTPException(status_code=400, detail=f"That doesn't look like a {label} profile address.")
    if link is None:
        link = ProfileLink(profile_id=profile.id, platform=platform, url=url, source="user")
    link.url, link.confirmed, link.source = url, True, "user"
    session.add(link)
    sync_links_to_score(session, profile)
    session.add(profile)
    session.commit()
    session.refresh(link)
    return link


def apply_website_audit(session: Session, profile: Profile) -> bool:
    """Set the Website Health audit from the page of the profile's own website (the one the owner kept),
    when that page was read and shown to be theirs. Leaves the audit alone otherwise."""
    if not profile.website_url:
        return False
    host = _host(profile.website_url)
    for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id, ProfileSource.status == "done", ProfileSource.name_validated == True)).all():  # noqa: E712
        audit = (s.extracted or {}).get("_audit")
        if audit and _host(s.url) == host:
            profile.website_audit = audit
            return True
    return False


def _link(session: Session, profile: Profile, source: ProfileSource) -> None:
    link = next((l for l in session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all() if _norm_url(l.url) == _norm_url(source.url)), None)
    if link is None:
        link = ProfileLink(profile_id=profile.id, platform=source.platform or "other", url=source.url, label=source.label, source="user")
    link.confirmed = source.status in ("confirmed", "scraping", "done", "needs_identity")
    session.add(link)


def decide(session: Session, profile: Profile, source_id: int, decision: str, label: str | None = None) -> ProfileSource:
    """The user's yes/no on one URL ("this is my site" / "not my site")."""
    _require_active(profile)
    source = _source(session, profile, source_id)
    if decision not in ("confirm", "deny"):
        raise HTTPException(status_code=400, detail="Decision must be confirm or deny.")
    if source.status in ("scraping", "done", "needs_identity", "failed", "blocked"):
        raise HTTPException(status_code=409, detail="That address has already been read.")
    if label:
        source.label = clean_text(label, 40) or source.label
        source.platform = platform_for_url(source.url) or _label_options(profile).get(source.label.lower()) or source.platform
    source.status = "confirmed" if decision == "confirm" else "denied"
    session.add(source)
    _link(session, profile, source)
    session.commit()
    session.refresh(source)
    return source


def skip_remaining_urls(session: Session, profile: Profile) -> int:
    """"I don't have any of these": every URL still waiting for a decision is dropped."""
    _require_active(profile)
    pending = session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id, ProfileSource.status == "proposed")).all()
    for s in pending:
        s.status = "denied"
        session.add(s)
    session.commit()
    return len(pending)


# --- Scraping and the identity check -------------------------------------------------------------------


def _person(profile: Profile) -> dict:
    return {"name": profile.name, "phone": profile.phone_number, "email": profile.email}


SCRAPE_IN_BACKGROUND = True  # tests switch this off so a scrape finishes before the call returns


def _scrape_batch(profile_id: int, ids: list[int], person: dict, services: list[str]) -> None:
    try:
        scrape_sources(profile_id, ids, person=person, extractor=_extractor, services_options=services, from_status="scraping")
    except Exception as exc:  # noqa: BLE001 — a crashed batch must not leave rows "scraping" forever
        from sqlmodel import Session as _Session
        from app.db import engine
        with _Session(engine) as session:
            for sid in ids:
                row = session.get(ProfileSource, sid)
                if row is not None and row.status == "scraping":
                    row.status, row.phase, row.error = "failed", None, f"{type(exc).__name__}: {str(exc)[:160]}"
                    session.add(row)
            session.commit()


def start_scrape(session: Session, profile: Profile) -> list[ProfileSource]:
    """Begin reading every confirmed, not-yet-read URL. They are reserved at once (status "scraping"), so a
    second call while the first is still running only takes pages confirmed since; the reading itself goes on
    in the background and the page shows each one finishing. The agent's turn is free meanwhile (the owner can
    ask for more pages to be searched). Only confirmed URLs are ever taken."""
    _require_active(profile)
    sources = session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id, ProfileSource.status == "confirmed")).all()
    if not sources:
        return []
    for s in sources:
        s.status, s.phase, s.error = "scraping", "queued", None
        session.add(s)
    session.commit()
    ids, person = [s.id for s in sources], _person(profile)
    services = [x["name"] for x in config_for(profile).services]
    if SCRAPE_IN_BACKGROUND:
        threading.Thread(target=_scrape_batch, args=(profile.id, ids, person, services), daemon=True).start()
    else:
        _scrape_batch(profile.id, ids, person, services)
    for s in sources:
        session.refresh(s)
    return list(sources)


def scrape_confirmed(session: Session, profile: Profile) -> list[dict]:
    """Read every confirmed, not-yet-read URL in parallel and return their outcomes. Only confirmed URLs
    are passed on; the runner re-checks that, too."""
    _require_active(profile)
    sources = session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id, ProfileSource.status == "confirmed")).all()
    if not sources:
        return []
    services = [s["name"] for s in config_for(profile).services]
    return scrape_sources(profile.id, [s.id for s in sources], person=_person(profile), extractor=_extractor, services_options=services)


def confirm_identity(session: Session, profile: Profile, source_id: int, is_mine: bool) -> ProfileSource:
    """The name was not found on this page. "Yes, it's mine" lets its data be used; "no" drops it."""
    _require_active(profile)
    source = _source(session, profile, source_id)
    if source.status != "needs_identity":
        raise HTTPException(status_code=409, detail="That page is not waiting for an identity check.")
    if not is_mine:
        source.status = "denied"
        session.add(source)
        _link(session, profile, source)  # no longer a confirmed link
        session.commit()
        return source
    if _extractor is None:
        source.status, source.name_validated = "done", True
        session.add(source)
        session.commit()
    else:
        services = [s["name"] for s in config_for(profile).services]
        extract_confirmed(source.id, extractor=_extractor, services_options=services)
    session.expire_all()
    return session.get(ProfileSource, source_id)


# --- Merging what was found ----------------------------------------------------------------------------


def _scraped_sources(session: Session, profile: Profile) -> list[ProfileSource]:
    return [
        s for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id, ProfileSource.status == "done")).all()
        if s.name_validated
    ]


def _groups(candidates: list[tuple[str, str]], normalize=_norm) -> list[dict]:
    """Group (value, source) pairs whose values are the same fact; the first spelling is kept."""
    groups: list[dict] = []
    for value, source in candidates:
        for g in groups:
            if _same(g["value"], value, normalize):
                if source not in g["sources"]:
                    g["sources"].append(source)
                break
        else:
            groups.append({"value": value, "sources": [source]})
    return groups


def _open_conflict(session: Session, profile: Profile, field_key: str, kind: str, groups: list[dict]) -> ProfileConflict:
    conflict = ProfileConflict(profile_id=profile.id, field_key=field_key, kind=kind, options=groups)
    session.add(conflict)
    return conflict


def merge(session: Session, profile: Profile) -> dict:
    """Fold the validated, read pages into the profile: fill empty fields, merge lists, import profile
    links, and raise a conflict wherever values differ. Open conflicts are recomputed from scratch each
    time, so merging again after reading more pages stays consistent; fields the user already resolved
    are left alone."""
    _require_active(profile)
    sources = _scraped_sources(session, profile)
    resolved = {c.field_key for c in session.exec(select(ProfileConflict).where(ProfileConflict.profile_id == profile.id, ProfileConflict.status == "resolved")).all()}
    for old in session.exec(select(ProfileConflict).where(ProfileConflict.profile_id == profile.id, ProfileConflict.status == "open")).all():
        session.delete(old)
    session.flush()

    applied: dict[str, str] = {}
    conflicts: list[ProfileConflict] = []
    rules = config_for(profile).rules.get("onboarding", {})
    allowed = set(rules.get("conflict_fields", [])) - VERIFIED_FIELDS

    # single-value fields
    for key, (field, limit) in SINGLE_FIELDS.items():
        if field not in allowed or field in resolved:
            continue
        found = []
        for s in sources:
            raw = s.extracted.get(key)
            value = _year(raw) if field == "year_started" else clean_text(raw, limit)
            if field == "business_timing":
                value = usable_hours(value)
                if value and s.platform == "google_business_profile" and partial_week(value):
                    value = ""
            if value:
                found.append((value, _host(s.url)))
        _decide_single(profile, field, found, applied, conflicts, session)

    # primary address
    if "address" in allowed and "address" not in resolved:
        found = [(clean_text(s.extracted.get("address"), ADDRESS_MAX), _host(s.url)) for s in sources if s.extracted.get("address")]
        found = [(v, h) for v, h in found if v]
        groups = _groups(([(profile.address, "Your profile")] if profile.address else []) + found, _norm_address_marker)
        if found and len(groups) > 1:
            conflicts.append(_open_conflict(session, profile, "address", "address", groups))
        elif found and not profile.address:
            profile.address = groups[0]["value"]
            applied["address"] = profile.address

    # licenses: more than one is allowed, so differing ones ask "which is real, or are both?"
    if "license_number" in allowed and "license_number" not in resolved:
        current = _items(profile.license_number.split(",") if profile.license_number else [], LICENSE_MAX)
        found = [(lic, _host(s.url)) for s in sources for lic in _items(s.extracted.get("license"), LICENSE_MAX)]
        groups = _groups([(c, "Your profile") for c in current] + found, lambda t: _license_key(t))
        if found and len(groups) > 1:
            conflicts.append(_open_conflict(session, profile, "license_number", "license", groups))
        elif found and not current:
            profile.license_number = groups[0]["value"]
            applied["license_number"] = profile.license_number

    # lists are merged, never disputed
    for key, (field, joiner, limit) in LIST_FIELDS.items():
        if field not in allowed or field in resolved:
            continue
        existing = _items([p for p in (getattr(profile, field) or "").replace(";", ",").split(",")], limit)
        merged = list(existing)
        for s in sources:
            for item in _items(s.extracted.get(key), limit):
                if not any(_same(item, m) for m in merged):
                    merged.append(item)
        if len(merged) > len(existing):
            setattr(profile, field, joiner.join(merged)[: limit * 2])
            applied[field] = getattr(profile, field)

    links_added = _discover_links(session, profile, sources)
    sync_links_to_score(session, profile)
    apply_website_audit(session, profile)
    for s in sources:
        s.merged = True
        session.add(s)
    session.add(profile)
    session.commit()
    for c in conflicts:
        session.refresh(c)
    recompute_and_save_score(session, profile)
    return {
        "applied": applied,
        "conflicts": [{"id": c.id, "field": c.field_key, "kind": c.kind} for c in conflicts],
        "links_added": links_added,
    }


def _decide_single(profile, field, found, applied, conflicts, session) -> None:
    if not found:
        return
    current = getattr(profile, field, None)
    groups = _groups(([(str(current), "Your profile")] if current else []) + found)
    if len(groups) == 1:
        if not current:
            setattr(profile, field, groups[0]["value"])
            applied[field] = groups[0]["value"]
    else:
        conflicts.append(_open_conflict(session, profile, field, "pick_one", groups))


def _discover_links(session: Session, profile: Profile, sources: list[ProfileSource]) -> int:
    """Profile URLs the pages themselves link to (their LinkedIn, Facebook, ...). Kept unconfirmed: the
    user says which are theirs before anything is read from them."""
    slots = {s["platform"] for s in config_for(profile).url_slots}
    have = {l.platform for l in session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all()}
    added = 0
    for s in sources:
        found = dict((s.extracted.get("_page") or {}).get("links") or {})
        found.update({k: v for k, v in (s.extracted.get("links") or {}).items() if isinstance(v, str)})
        for platform, url in found.items():
            if platform in slots and platform not in have and not check_public_url(str(url)):
                session.add(ProfileLink(profile_id=profile.id, platform=platform, url=str(url)[:500], source="scrape", confirmed=False))
                have.add(platform)
                added += 1
    return added


# --- Resolving conflicts --------------------------------------------------------------------------------


def _conflict(session: Session, profile: Profile, conflict_id: int) -> ProfileConflict:
    conflict = session.get(ProfileConflict, conflict_id)
    if conflict is None or conflict.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="That conflict does not belong to this profile.")
    return conflict


def _option_value(conflict: ProfileConflict, index) -> str:
    try:
        return conflict.options[int(index)]["value"]
    except (TypeError, ValueError, IndexError, KeyError):
        raise HTTPException(status_code=400, detail="Choose one of the listed options.")


def resolve(session: Session, profile: Profile, conflict_id: int, resolution: dict) -> ProfileConflict:
    _require_active(profile)
    conflict = _conflict(session, profile, conflict_id)
    if conflict.status != "open":
        raise HTTPException(status_code=409, detail="That conflict is already resolved.")
    resolution = resolution or {}

    if conflict.kind == "license":
        keep = [_option_value(conflict, i) for i in resolution.get("keep") or []]
        keep += _items(resolution.get("manual"), LICENSE_MAX)
        if not keep:
            raise HTTPException(status_code=400, detail="Keep at least one license, or add yours.")
        profile.license_number = ", ".join(dict.fromkeys(keep))[:200]
    elif conflict.kind == "address":
        primary = resolution.get("primary")
        if isinstance(primary, dict):
            primary_value = clean_text(primary.get("manual"), ADDRESS_MAX)
        else:
            primary_value = _option_value(conflict, primary) if primary is not None else ""
        if not primary_value:
            raise HTTPException(status_code=400, detail="Choose your primary address, or type it in.")
        secondary = [_option_value(conflict, i) for i in resolution.get("secondary") or []]
        secondary += _items(resolution.get("manual_secondary"), ADDRESS_MAX)
        profile.address = primary_value
        profile.secondary_addresses = [{"address": a, "label": "secondary"} for a in dict.fromkeys(secondary) if a != primary_value]
    else:
        value = clean_text(resolution.get("value"), FIELD_MAX.get(conflict.field_key, 1500))
        if not value and resolution.get("choice") is not None:
            value = clean_text(_option_value(conflict, resolution["choice"]), 1500)
        if not value:
            raise HTTPException(status_code=400, detail="Choose one of the listed values, or type your own.")
        setattr(profile, conflict.field_key, value)

    conflict.status, conflict.resolution, conflict.resolved_at = "resolved", resolution, datetime.utcnow()
    session.add_all([conflict, profile])
    session.commit()
    recompute_and_save_score(session, profile)
    session.refresh(conflict)
    return conflict


# --- Fields, defaults, completion ----------------------------------------------------------------------


def update_fields(session: Session, profile: Profile, updates: dict) -> dict:
    """Set category fields by hand (an accepted AI draft, or typed in). Only the category's own basic
    fields; never the details verified at claim time."""
    _require_active(profile)
    allowed = {f["key"] for f in config_for(profile).basic_fields} - VERIFIED_FIELDS
    changed = {}
    for key, value in (updates or {}).items():
        if key in VERIFIED_FIELDS:
            raise HTTPException(status_code=400, detail=f"{key} was verified when you claimed this profile and can't be changed here.")
        if key not in allowed:
            raise HTTPException(status_code=400, detail=f"{key} is not a field for this category.")
        text = _year(value) if key == "year_started" else clean_text(value, FIELD_MAX.get(key, 600))
        if value not in (None, "") and not text:
            raise HTTPException(status_code=400, detail=f"{key} has an invalid value.")
        setattr(profile, key, text or None)
        changed[key] = text or None
    session.add(profile)
    session.commit()
    recompute_and_save_score(session, profile)
    return changed


def apply_defaults(session: Session, profile: Profile) -> dict:
    """Fill business hours with the category's default when nothing else supplied them (core1: "use
    default value for business timing")."""
    _require_active(profile)
    default = config_for(profile).rules.get("onboarding", {}).get("default_business_timing")
    if default and not profile.business_timing:
        profile.business_timing = default
        session.add(profile)
        session.commit()
        recompute_and_save_score(session, profile)
        return {"business_timing": default}
    return {}


_LOCATION = re.compile(r",\s*([A-Za-z][A-Za-z .'-]+),\s*([A-Z]{2})\b")


def derive_location(address: str | None) -> str | None:
    """"City, ST" from a street address ("1425 Artesia Blvd, Gardena, CA 90248")."""
    match = _LOCATION.search(address or "")
    return f"{match.group(1).strip()}, {match.group(2)}" if match else None


def blockers(session: Session, profile: Profile) -> list[str]:
    """Everything that still stops onboarding from being completed, in plain words."""
    sources = session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)).all()
    out = []
    if any(s.status == "proposed" for s in sources):
        out.append("Some web addresses are still waiting for your yes or no.")
    if any(s.status == "confirmed" for s in sources):
        out.append("Some confirmed web addresses have not been read yet.")
    if any(s.status == "scraping" for s in sources):
        out.append("Pages are still being read.")
    if any(s.status == "needs_identity" for s in sources):
        out.append("Some pages are waiting for you to confirm they are yours.")
    if any(s.status == "done" and s.name_validated and not s.merged for s in sources):
        out.append("What was found has not been merged into your profile yet.")
    if session.exec(select(ProfileConflict).where(ProfileConflict.profile_id == profile.id, ProfileConflict.status == "open")).first():
        out.append("Some conflicting details still need your choice.")
    missing = [f for f in config_for(profile).mandatory_fields if not _mandatory_present(profile, f)]
    if missing:
        out.append("Required details are missing: " + ", ".join(missing) + ".")
    return out


def _mandatory_present(profile: Profile, field: str) -> bool:
    return bool(profile.category_id if field == "category" else getattr(profile, field, None))


def complete(session: Session, profile: Profile) -> dict:
    """Finish onboarding and return the starting point for Process 3: the score, the rank, and what
    would raise the score."""
    _require_active(profile)
    problems = blockers(session, profile)
    if problems:
        raise HTTPException(status_code=409, detail={"code": "onboarding_blocked", "message": "Onboarding can't be completed yet.", "blockers": problems})
    if not profile.location:
        profile.location = derive_location(profile.address) or ""
    apply_defaults(session, profile)
    sync_links_to_score(session, profile)
    apply_website_audit(session, profile)
    profile.onboarding_completed_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    score = recompute_and_save_score(session, profile)
    rank = simulate_rank(session, profile, score["total"])
    return {"completed": True, "score": score, "rank_position": rank["rank_position"], "rank_total": rank["rank_total"], "location": profile.location}


# --- State for the UI and the agent ----------------------------------------------------------------------


# What a read page can show while the owner waits: [extracted key, label], most telling first.
_HIGHLIGHTS = [
    ("company_name", "Company"), ("title", "Title"), ("phone", "Phone"), ("email", "Email"), ("address", "Address"),
    ("business_hours", "Hours"), ("year_started", "Started"), ("license", "License"), ("services", "Services"),
    ("service_area", "Service area"), ("awards", "Awards"), ("website_url", "Website"),
]


def _highlights(extracted: dict, limit: int = 6) -> list[dict]:
    out = []
    for key, label in _HIGHLIGHTS:
        value = extracted.get(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if v)
        value = clean_text(value, 80)
        if value:
            out.append({"key": key, "label": label, "value": value})
        if len(out) >= limit:
            break
    return out


_DETAIL_LABELS = {
    "name": "Name", "company_name": "Company", "title": "Title", "phone": "Phone", "email": "Email", "address": "Address",
    "business_hours": "Hours", "year_started": "Started", "license": "License", "services": "Services", "service_area": "Service area",
    "awards": "Awards", "achievements": "Achievements", "website_url": "Website", "description": "About",
}


def _details(extracted: dict) -> list[dict]:
    """Everything a read page gave, for the "what did we find" dropdown (the same cleaned values the merge uses)."""
    out = []
    for key, value in extracted.items():
        if key.startswith("_") or key == "links":
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if v)
        value = clean_text(value, 400)
        if value:
            out.append({"key": key, "label": _DETAIL_LABELS.get(key) or key.replace("_", " ").capitalize(), "value": value})
    return out


def _source_row(s: ProfileSource) -> dict:
    extracted = s.extracted or {}
    row = {
        "id": s.id, "url": s.url, "host": _host(s.url), "platform": s.platform, "label": s.label, "status": s.status, "phase": s.phase,
        "confidence": s.confidence, "name_validated": s.name_validated, "error": s.error or extracted.get("_extraction_error"),
        "title": (extracted.get("_page") or {}).get("title"),
        "fields_found": [k for k in extracted if not k.startswith("_")],
    }
    if s.status == "done" and s.name_validated:
        row["highlights"] = _highlights(extracted)  # shown while the owner waits for the other pages
        row["details"] = _details(extracted)  # everything found, for the dropdown
    if s.status == "needs_identity":
        row["preview"] = re.sub(r"[#*_>`\[\]]", "", s.raw_markdown or "")[:240].strip()
    return row


def stage(session: Session, profile: Profile) -> str:
    if profile.onboarding_completed_at:
        return "completed"
    sources = session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)).all()
    statuses = {s.status for s in sources}
    if not sources:
        return "no_urls"
    if "proposed" in statuses:
        return "confirm_urls"
    if "scraping" in statuses:
        return "scraping"
    if "confirmed" in statuses:
        return "ready_to_scrape"
    if "needs_identity" in statuses:
        return "identity"
    if any(s.status == "done" and s.name_validated and not s.merged for s in sources):
        return "merge"
    if session.exec(select(ProfileConflict).where(ProfileConflict.profile_id == profile.id, ProfileConflict.status == "open")).first():
        return "conflicts"
    return "fields"


def state(session: Session, profile: Profile) -> dict:
    """Everything the onboarding UI shows and the agent decides from. Safe to poll."""
    config = config_for(profile)
    sources = session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id).order_by(ProfileSource.id)).all()
    conflicts = session.exec(select(ProfileConflict).where(ProfileConflict.profile_id == profile.id).order_by(ProfileConflict.id)).all()
    links = session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all()
    return {
        "profile_id": profile.id,
        "stage": stage(session, profile),
        "completed": profile.onboarding_completed_at is not None,
        "category": {"id": config.id, "name": config.name, "vertical": config.vertical},
        "url_labels": url_label_choices(profile),
        "sources": [_source_row(s) for s in sources],
        "links": [{"platform": l.platform, "url": l.url, "confirmed": l.confirmed, "source": l.source} for l in links],
        "link_only": [  # never read: the owner gives or confirms these on the details step
            {"platform": slot["platform"], "label": UNREADABLE_PLATFORMS[slot["platform"]],
             "url": link.url if link and link.source != "declined" else None,
             "confirmed": bool(link and link.confirmed), "found_on": link.source if link and link.source != "declined" else None}
            for slot in config.slots("social") if is_unreadable(slot["platform"])
            for link in [next((l for l in links if l.platform == slot["platform"]), None)]
        ],
        "conflicts": [
            {"id": c.id, "field": c.field_key, "kind": c.kind, "status": c.status, "options": c.options, "resolution": c.resolution}
            for c in conflicts
        ],
        "fields": [{"key": f["key"], "label": f["label"]} for f in config.basic_fields],
        "missing_fields": [f["key"] for f in config.basic_fields if not getattr(profile, f["key"], None)],
        "blockers": [] if profile.onboarding_completed_at else blockers(session, profile),
        "verified_fields": sorted(VERIFIED_FIELDS),
        "profile": {k: getattr(profile, k, None) for k in ("name", "title", "business_name", "address", "website_url", "business_timing", "bio",
                                                          "specialities", "awards", "achievements", "year_started", "license_number", "service_area", "location")},
    }


def summary_line(session: Session, profile: Profile) -> str:
    """One compact line for the agent's per-turn context."""
    s = state(session, profile)
    counts: dict[str, int] = {}
    for src in s["sources"]:
        counts[src["status"]] = counts.get(src["status"], 0) + 1
    open_conflicts = sum(1 for c in s["conflicts"] if c["status"] == "open")
    return (
        f"onboarding: stage={s['stage']}, sources={counts or 'none'}, open_conflicts={open_conflicts}, "
        f"missing_fields={len(s['missing_fields'])}, completed={s['completed']}"
    )
