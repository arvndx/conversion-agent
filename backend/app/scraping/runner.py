"""Scrape several confirmed URLs for one profile at the same time, live, inside the request.

Each URL is one `ProfileSource` row. The row's `status` moves proposed/confirmed -> scraping ->
done | failed | blocked | needs_identity and is committed at every step, so the UI can poll the
sources while the scrape is still running. Pages run in parallel (a semaphore bounds how many are in
flight, since each browser fallback is a Chromium process).

A page is only *used* once the person's name is found on it (see validate.py). A page that fails the
check is kept (text stored) with status `needs_identity`: no fields are extracted from it until the
agent confirms "this is my profile", at which point `extract_confirmed` runs the extraction on the
stored text without fetching again.
"""

import asyncio
import os
from datetime import datetime
from typing import Callable

from sqlmodel import Session, select

from app.db import engine
from app.models import ProfileSource
from app.scraping.audit import website_audit
from app.scraping.fetch import fetch_page
from app.scraping.parse import parse_html, platform_for_url
from app.scraping.policy import can_read, refusal
from app.scraping.validate import validate_identity

CONCURRENCY = int(os.environ.get("SCRAPE_CONCURRENCY", "4"))
MAX_STORED_MARKDOWN = 60000
LOGIN_WALL_PLATFORMS = ("google_business_profile", "facebook")  # sign-in screens for anonymous visitors (the always-walled platforms are never fetched: see policy.py)

# extractor(markdown, url=..., platform=..., services_options=...) -> dict
Extractor = Callable[..., dict]


def _db_safe(value):
    """Postgres text and JSONB columns cannot hold NUL characters, which real pages sometimes contain;
    one would otherwise fail the whole save and lose the source."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {_db_safe(k): _db_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_db_safe(v) for v in value]
    return value


def _update(source_id: int, **fields) -> None:
    """Commit a change to one source row (its own short session: safe from any thread)."""
    fields = {k: _db_safe(v) for k, v in fields.items()}
    if fields.get("status") not in (None, "scraping"):
        fields.setdefault("phase", None)  # a finished source has no phase
    with Session(engine) as session:
        source = session.get(ProfileSource, source_id)
        for key, value in fields.items():
            setattr(source, key, value)
        session.add(source)
        session.commit()


async def _scrape_one(
    source_id: int,
    url: str,
    platform: str | None,
    person: dict,
    extractor: Extractor | None,
    services_options: list[str],
    slots: asyncio.Semaphore,
) -> None:
    async with slots:
        await asyncio.to_thread(_update, source_id, status="scraping", phase="opening", error=None)
        platform = platform or platform_for_url(url)
        if not can_read(platform):  # never fetched, whatever asked for it
            await asyncio.to_thread(_update, source_id, status="blocked", error=refusal(platform), fetched_at=datetime.utcnow())
            return

        result = await fetch_page(url)
        if not result.ok:
            status = "blocked" if result.blocked else "failed"
            await asyncio.to_thread(
                _update, source_id, status=status, error=result.error or "blocked by the site", fetched_at=datetime.utcnow()
            )
            return

        await asyncio.to_thread(_update, source_id, phase="reading")
        page = parse_html(result.html, url)
        if not page.text.strip():  # nothing readable came back (a bot check that renders blank): there is no page to confirm
            await asyncio.to_thread(
                _update, source_id, status="blocked", error="the page came back empty (the site may block automated reading)",
                fetched_at=datetime.utcnow(),
            )
            return
        validation = validate_identity(
            profile_name=person["name"],
            page_text=page.text,
            json_ld_names=page.json_ld_names,
            profile_phone=person.get("phone"),
            profile_email=person.get("email"),
            page_phones=page.phones,
            page_emails=page.emails,
        )
        # What the page declares itself needs no model; the model fills in the rest from the text.
        facts = {
            "_validation": validation.as_dict(),
            "_page": {"title": page.title, "via": result.via, "links": page.links, "emails": page.emails,
                      "phones": page.phones, "json_ld_hours": page.json_ld_hours},
        }
        if platform in (None, "website"):  # the person's own site: keep what the page tells us about its health
            facts["_audit"] = website_audit(page, load_time_ms=result.elapsed_ms if result.via == "direct" else None)
        common = dict(
            platform=platform, name_validated=validation.validated, fetched_at=datetime.utcnow(),
            raw_markdown=page.markdown[:MAX_STORED_MARKDOWN],
        )
        if not validation.validated:
            if page.login_wall and platform in LOGIN_WALL_PLATFORMS:  # a sign-in screen has no profile to confirm, so do not ask the user about it
                await asyncio.to_thread(
                    _update, source_id, status="blocked", error="the site asks for a login to show this page",
                    extracted=facts, **common,
                )
                return
            await asyncio.to_thread(_update, source_id, status="needs_identity", extracted=facts, **common)
            return

        if extractor is not None:
            await asyncio.to_thread(_update, source_id, phase="extracting")
            try:
                fields = await asyncio.to_thread(
                    extractor, page.markdown, url=url, platform=platform, services_options=services_options,
                )
                facts.update(fields)
            except Exception as exc:  # noqa: BLE001 — keep the page; say why nothing was extracted
                facts["_extraction_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        await asyncio.to_thread(_update, source_id, status="done", extracted=facts, **common)


async def _run(person: dict, rows: list[tuple[int, str, str | None]], extractor, services_options) -> None:
    slots = asyncio.Semaphore(CONCURRENCY)
    await asyncio.gather(
        *(_scrape_one(sid, url, platform, person, extractor, services_options, slots) for sid, url, platform in rows)
    )


def scrape_sources(
    profile_id: int,
    source_ids: list[int],
    *,
    person: dict,
    extractor: Extractor | None = None,
    services_options: list[str] | None = None,
    from_status: str = "confirmed",
) -> list[dict]:
    """Scrape the given sources in parallel and return their final summaries. `from_status` is the status
    they must have: "confirmed" normally, "scraping" when the caller already marked them as taken (so two
    overlapping batches never read the same page twice).

    `person` is {"name", "phone", "email"} for the identity check. Only sources that belong to
    `profile_id` and that the user confirmed are scraped, whatever ids are passed in."""
    with Session(engine) as session:
        sources = session.exec(
            select(ProfileSource).where(
                ProfileSource.profile_id == profile_id,
                ProfileSource.id.in_(source_ids),
                ProfileSource.status == from_status,  # only what the user said yes to (or what the caller reserved)
            )
        ).all()
        rows = [(s.id, s.url, s.platform) for s in sources]

    if rows:
        asyncio.run(_run(person, rows, extractor, services_options or []))
    return source_summaries(profile_id, [r[0] for r in rows])


def extract_confirmed(source_id: int, *, extractor: Extractor, services_options: list[str] | None = None) -> None:
    """The agent confirmed a `needs_identity` page really is theirs: extract from the stored text."""
    with Session(engine) as session:
        source = session.get(ProfileSource, source_id)
        markdown, url, platform, facts = source.raw_markdown or "", source.url, source.platform, dict(source.extracted or {})
    try:
        facts.update(extractor(markdown, url=url, platform=platform, services_options=services_options or []))
    except Exception as exc:  # noqa: BLE001
        facts["_extraction_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    facts.setdefault("_validation", {})["confirmed_by_user"] = True
    _update(source_id, status="done", name_validated=True, extracted=facts)


def source_summaries(profile_id: int, source_ids: list[int] | None = None) -> list[dict]:
    with Session(engine) as session:
        query = select(ProfileSource).where(ProfileSource.profile_id == profile_id)
        if source_ids is not None:
            query = query.where(ProfileSource.id.in_(source_ids))
        return [
            {
                "id": s.id, "url": s.url, "platform": s.platform, "label": s.label, "status": s.status,
                "name_validated": s.name_validated, "error": s.error or (s.extracted or {}).get("_extraction_error"),
                "fields_found": [k for k in (s.extracted or {}) if not k.startswith("_")],
            }
            for s in session.exec(query.order_by(ProfileSource.id)).all()
        ]
