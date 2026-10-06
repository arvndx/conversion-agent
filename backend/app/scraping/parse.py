"""Turn fetched HTML into clean text/markdown plus the structured bits a page already declares
(JSON-LD, meta tags, contact details, links to other platforms). No LLM here.

Ported from the existing job: script/style stripping and whitespace collapsing, the phone and email
patterns (including `mailto:` links), meta description / title / language, JSON-LD opening hours, and
the anchor-matching social/Google-link finder, extended to the platforms this app scores.
"""

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from markdownify import markdownify

PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# platform key (matches Category.url_slots) -> substrings that identify a link to that platform
PLATFORM_HOSTS = {
    "google_business_profile": ("business.google.com", "g.page", "google.com/maps", "maps.app.goo", "search.google.com/local"),
    "facebook": ("facebook.com",),
    "linkedin": ("linkedin.com/in", "linkedin.com/company"),
    "instagram": ("instagram.com",),
    "x": ("twitter.com", "x.com/"),
    "youtube": ("youtube.com", "youtu.be"),
    "zillow": ("zillow.com",),
    "yelp": ("yelp.com/biz",),
    "realtor_com": ("realtor.com",),
    "homes_com": ("homes.com",),
    "lendingtree": ("lendingtree.com",),
    "trusted_choice": ("trustedchoice.com",),
    "healthgrades": ("healthgrades.com",),
}
_SKIP_LINK_PREFIXES = ("javascript:", "mailto:", "tel:", "#")


def platform_for_url(url: str) -> str | None:
    """Which known platform a URL belongs to, if any (used to label URLs the agent finds or adds)."""
    lowered = url.lower()
    for platform, hosts in PLATFORM_HOSTS.items():
        if any(host in lowered for host in hosts):
            return platform
    return None


@dataclass
class ParsedPage:
    url: str
    title: str | None = None
    meta_description: str | None = None
    language: str | None = None
    text: str = ""
    markdown: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    links: dict[str, str] = field(default_factory=dict)  # platform -> first matching href
    json_ld: list[dict] = field(default_factory=list)
    json_ld_hours: list[str] = field(default_factory=list)
    json_ld_names: list[str] = field(default_factory=list)
    login_wall: bool = False  # the page is a sign-in screen, not the profile
    has_viewport: bool = False  # declares a mobile viewport (the usual sign a site is built for phones)


def _collapse(text: str) -> str:
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def _flatten_json_ld(data) -> list[dict]:
    if isinstance(data, list):
        return [item for entry in data for item in _flatten_json_ld(entry)]
    if isinstance(data, dict):
        if "@graph" in data:
            return _flatten_json_ld(data["@graph"])
        return [data]
    return []


def _json_ld(soup: BeautifulSoup) -> list[dict]:
    items = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            items.extend(_flatten_json_ld(json.loads(script.string or script.get_text() or "")))
        except (json.JSONDecodeError, TypeError):
            continue  # one malformed block must not lose the page
    return items


def _hours_from(item: dict) -> list[str]:
    hours = item.get("openingHours")
    if isinstance(hours, str):
        return [hours]
    if isinstance(hours, list):
        return [h for h in hours if isinstance(h, str)]
    specs = item.get("openingHoursSpecification")
    out = []
    for spec in specs if isinstance(specs, list) else ([specs] if isinstance(specs, dict) else []):
        days = spec.get("dayOfWeek")
        days = ", ".join(days) if isinstance(days, list) else days
        if days and spec.get("opens") and spec.get("closes"):
            out.append(f"{days} {spec['opens']}-{spec['closes']}")
    return out


def _find_links(soup: BeautifulSoup) -> dict[str, str]:
    links: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.lower().startswith(_SKIP_LINK_PREFIXES):
            continue
        platform = platform_for_url(href)
        if platform and platform not in links:
            links[platform] = href
    return links


# Social sites show a sign-in wall instead of a profile to anonymous visitors. Such a page links to the
# login / sign-up form and has hardly any text of its own.
_LOGIN_HREF_RE = re.compile(r"/(login|signup|signin|authwall|uas/login|checkpoint)\b|[?&]next=", re.I)
_LOGIN_WORDS_RE = re.compile(r"\b(log ?in|sign ?in|sign ?up|join now|agree\s*&\s*join|create (new )?account)\b", re.I)
LOGIN_WALL_MAX_WORDS = 400


def looks_like_login_wall(soup: BeautifulSoup, text: str) -> bool:
    if len(text.split()) > LOGIN_WALL_MAX_WORDS:
        return False
    linked = any(_LOGIN_HREF_RE.search(a["href"]) for a in soup.find_all("a", href=True))
    forms = any(_LOGIN_HREF_RE.search(f.get("action", "")) for f in soup.find_all("form"))
    return linked or forms or len(_LOGIN_WORDS_RE.findall(text)) >= 2


def parse_html(html: str, url: str = "") -> ParsedPage:
    soup = BeautifulSoup(html or "", "html.parser")

    page = ParsedPage(url=url)
    page.title = soup.title.string.strip() if soup.title and soup.title.string else None
    description = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    page.meta_description = (description.get("content") or "").strip() or None if description else None
    page.language = soup.html.get("lang") if soup.html else None
    page.has_viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}) is not None

    page.json_ld = _json_ld(soup)
    for item in page.json_ld:
        page.json_ld_hours.extend(_hours_from(item))
        if isinstance(item.get("name"), str):
            page.json_ld_names.append(item["name"])

    # Links and mailto emails are read before scripts/styles are removed.
    page.links = _find_links(soup)
    emails: set[str] = set()
    for a in soup.find_all("a", href=True):
        if "mailto:" in a["href"]:
            emails.update(EMAIL_RE.findall(a["href"]))

    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    page.text = _collapse(soup.get_text(" "))  # a space between elements, so neighbouring text never fuses into one 'word'
    page.login_wall = looks_like_login_wall(soup, page.text)
    emails.update(email.lower() for email in EMAIL_RE.findall(page.text))
    page.emails = sorted({e.lower() for e in emails})
    page.phones = sorted({re.sub(r"\D", "", p) for p in PHONE_RE.findall(page.text)})

    body = soup.body or soup
    page.markdown = re.sub(r"\n{3,}", "\n\n", markdownify(str(body), heading_style="ATX", strip=["img"])).strip()
    return page
