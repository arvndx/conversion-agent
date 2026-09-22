"""Plain server-side fetch + parse of a candidate business webpage. No LLM
involved here — this is deterministic code the model calls as a tool, and its
output is treated as untrusted page content by the caller (see claim_tools.py).
"""

import re

import httpx
from bs4 import BeautifulSoup

from agent.config import AGENT_HTTP_TIMEOUT_SECONDS

MAX_PAGE_BYTES = 2 * 1024 * 1024  # 2MB cap
PHONE_RE = re.compile(r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
HOURS_KEYWORDS = ("hours", "monday", "mon-fri", "open", "closed")


def fetch_and_extract(url: str) -> dict:
    try:
        with httpx.Client(timeout=AGENT_HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "ClearRankBot/1.0"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"error": f"could not fetch {url}: {exc}"}

    content = response.content[:MAX_PAGE_BYTES]
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    phone_match = PHONE_RE.search(text)
    hours_snippet = next(
        (
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if any(keyword in sentence.lower() for keyword in HOURS_KEYWORDS)
        ),
        None,
    )

    meta_description = None
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_description = meta_tag["content"].strip()

    title = soup.title.string.strip() if soup.title and soup.title.string else None

    return {
        "url": url,
        "title": title,
        "candidate_phone_number": phone_match.group(0) if phone_match else None,
        "candidate_business_hours_text": hours_snippet[:300] if hours_snippet else None,
        "candidate_bio": meta_description or (text[:300] if text else None),
        "raw_text_excerpt": text[:1500],
    }
