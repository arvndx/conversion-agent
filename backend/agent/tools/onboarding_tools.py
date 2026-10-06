"""The onboarding agent's tools (core1.txt, Process 2).

Each tool is a thin wrapper over app/onboarding.py, which owns the rules: only user-confirmed URLs are
scraped, a page's data is used only once the person's name is on it, verified details are never
overwritten, conflicts wait for the user's choice, and onboarding can't complete with anything
unresolved. The user's own decisions (yes/no on a URL, a typed URL, a conflict resolution) are recorded by
the UI through REST; these tools read that state and act on it, so the agent cannot make a decision for
the user. Scraped text is untrusted: tools return cleaned, structured fields, never page text.
"""

from fastapi import HTTPException
from sqlmodel import select

from app import onboarding
from app.category_config import config_for
from app.models import ProfileSource

from agent.tools import ToolContext, ToolDef, register_tool


def _guarded(fn):
    """A rule the service enforces comes back as {"error": ...} for the model to read and adapt to."""

    def run(ctx: ToolContext, tool_input: dict) -> dict:
        try:
            return fn(ctx, tool_input)
        except HTTPException as exc:
            detail = exc.detail
            return {"error": detail.get("message", "not allowed") if isinstance(detail, dict) else str(detail),
                    **({"blockers": detail["blockers"]} if isinstance(detail, dict) and "blockers" in detail else {})}

    return run


def _compact_source(s: dict) -> dict:
    return {k: s[k] for k in ("id", "host", "platform", "label", "status", "confidence", "name_validated", "error") if s.get(k) is not None}


def get_onboarding_state(ctx: ToolContext, tool_input: dict) -> dict:
    state = onboarding.state(ctx.session, ctx.profile)
    config = config_for(ctx.profile)
    return {
        "stage": state["stage"],
        "completed": state["completed"],
        "category": state["category"],
        "service_names": [s["name"] for s in config.services],
        "url_labels": state["url_labels"],
        "known_urls": [{"platform": l["platform"], "url": l["url"], "confirmed": l["confirmed"]} for l in state["links"]],
        "sources": [_compact_source(s) for s in state["sources"]],
        "open_conflicts": [{"id": c["id"], "field": c["field"], "kind": c["kind"]} for c in state["conflicts"] if c["status"] == "open"],
        "missing_fields": state["missing_fields"],
        "blockers": state["blockers"],
        "verified_already": state["verified_fields"],
    }


def present_known_urls(ctx: ToolContext, tool_input: dict) -> dict:
    """Turn the URLs we already hold into yes/no cards. The user answers each; this does not confirm any."""
    added = onboarding.start(ctx.session, ctx.profile)
    state = onboarding.state(ctx.session, ctx.profile)
    proposed = [_compact_source(s) for s in state["sources"] if s["status"] == "proposed"]
    return {"new_cards": added, "waiting_for_user": proposed}


def present_url_candidates(ctx: ToolContext, tool_input: dict) -> dict:
    out = onboarding.propose_candidates(ctx.session, ctx.profile, (tool_input.get("candidates") or [])[:8])
    return {"shown": [_compact_source(s) for s in out["added"]], "not_shown": out["skipped"]}


def request_manual_urls(ctx: ToolContext, tool_input: dict) -> dict:
    return {"labels": onboarding.url_label_choices(ctx.profile)}


def scrape_confirmed_sources(ctx: ToolContext, tool_input: dict) -> dict:
    started = onboarding.start_scrape(ctx.session, ctx.profile)
    if not started:
        return {"scraped": [], "note": "There are no confirmed web addresses waiting to be read."}
    if onboarding.SCRAPE_IN_BACKGROUND:
        return {
            "started": [onboarding._host(s.url) for s in started],
            "note": "Reading has started in the background and the app shows each page finishing. Say ONE short line and stop: do not "
                    "wait and do not call more tools. The app will message you when the pages are read.",
        }
    results = [onboarding._source_row(s) for s in started]  # finished before returning (tests)
    return {
        "scraped": [_compact_source(r) | {"fields_found": r["fields_found"]} for r in results],
        "needs_identity_check": [r["id"] for r in results if r["status"] == "needs_identity"],
        "unreachable": [{"id": r["id"], "reason": r["error"]} for r in results if r["status"] in ("failed", "blocked")],
    }


def get_scrape_results(ctx: ToolContext, tool_input: dict) -> dict:
    """What validated pages said, as structured fields. Pages that did not show the person's name are
    listed without their data."""
    state = onboarding.state(ctx.session, ctx.profile)
    pending_identity = [_compact_source(s) for s in state["sources"] if s["status"] == "needs_identity"]
    sources = ctx.session.exec(
        select(ProfileSource).where(ProfileSource.profile_id == ctx.profile.id, ProfileSource.status == "done", ProfileSource.name_validated == True)  # noqa: E712
    ).all()
    results = []
    for s in sources:
        fields = {k: v for k, v in (s.extracted or {}).items() if not k.startswith("_")}
        results.append({"id": s.id, "host": onboarding._host(s.url), "platform": s.platform, "fields": fields})
    return {"validated_pages": results, "waiting_for_identity_check": pending_identity}


def request_identity_confirmation(ctx: ToolContext, tool_input: dict) -> dict:
    source = ctx.session.get(ProfileSource, tool_input.get("source_id"))
    if source is None or source.profile_id != ctx.profile.id or source.status != "needs_identity":
        return {"error": "That page is not waiting for an identity check."}
    return {"source_id": source.id, "host": onboarding._host(source.url)}


def merge_scraped_data(ctx: ToolContext, tool_input: dict) -> dict:
    out = onboarding.merge(ctx.session, ctx.profile)
    return {
        "filled": {k: (v if len(str(v)) <= 120 else str(v)[:117] + "…") for k, v in out["applied"].items()},
        "conflicts": out["conflicts"],
        "other_profile_links_found": out["links_added"],
    }


def present_conflicts(ctx: ToolContext, tool_input: dict) -> dict:
    state = onboarding.state(ctx.session, ctx.profile)
    open_conflicts = [c for c in state["conflicts"] if c["status"] == "open"]
    return {"open": [{"id": c["id"], "field": c["field"], "kind": c["kind"],
                      "options": [{"value": o["value"], "seen_on": o["sources"]} for o in c["options"]]} for c in open_conflicts]}


def apply_default_business_hours(ctx: ToolContext, tool_input: dict) -> dict:
    applied = onboarding.apply_defaults(ctx.session, ctx.profile)
    return {"applied": applied} if applied else {"note": "Business hours are already filled in."}


def complete_onboarding(ctx: ToolContext, tool_input: dict) -> dict:
    out = onboarding.complete(ctx.session, ctx.profile)
    return {"completed": True, "score": out["score"]["total"], "max_possible": out["score"]["max_possible"],
            "rank_position": out["rank_position"], "rank_total": out["rank_total"], "location": out["location"],
            "section_points": {k: {"earned": v["earned"], "max": v["max"], "locked": v["locked"]} for k, v in out["score"]["categories"].items()}}


def _register(name, description, handler, schema=None, ui=False):
    register_tool(ToolDef(
        name=name, description=description,
        input_schema=schema or {"type": "object", "properties": {}},
        handler=_guarded(handler), is_ui_action=ui,
    ))


_register("get_onboarding_state",
          "Where onboarding stands: the stage, the category's service names and URL labels, known URLs, each page's status, open "
          "conflicts, fields still missing and what blocks completion. Call this first, and again whenever the user acts.",
          get_onboarding_state)
_register("present_known_urls",
          "Show the user yes/no cards for the web addresses we already hold for them (website, Google Business, Facebook, ...). "
          "The user confirms each one; you never confirm for them.", present_known_urls, ui=True)
_register("present_url_candidates",
          "Show the user web addresses you found by searching, each with your honest confidence_percent (0-100) that it is THEM and a "
          "label such as 'personal website', 'Yelp profile', 'Zillow profile'. Only real URLs "
          "from your search results; never invent or pad. Up to 8.",
          present_url_candidates, ui=True, schema={
              "type": "object",
              "properties": {"candidates": {"type": "array", "items": {"type": "object", "properties": {
                  "url": {"type": "string"}, "label": {"type": "string"},
                  "confidence_percent": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["url", "label", "confidence_percent"]}}},
              "required": ["candidates"]})
_register("request_manual_urls",
          "Ask the user to type in their profile URLs themselves, each with a label from a dropdown. Use when nothing is known and "
          "your search found nothing, or they say none of the candidates are theirs.", request_manual_urls, ui=True)
_register("scrape_confirmed_sources",
          "Read every web address the user has confirmed, all at once. Takes up to a minute; the app shows live progress. Only confirmed "
          "addresses are read, so call it once the user has finished confirming. It starts the reading in the background and returns at once.", scrape_confirmed_sources)
_register("get_scrape_results",
          "What the pages that showed the user's name said, as structured fields. Pages without their name are listed without data.",
          get_scrape_results)
_register("request_identity_confirmation",
          "A page did not show the user's name. Ask them 'is this your profile?'. Its data stays unused until they say yes.",
          request_identity_confirmation, ui=True,
          schema={"type": "object", "properties": {"source_id": {"type": "integer"}}, "required": ["source_id"]})
_register("merge_scraped_data",
          "Fold what the validated pages said into the profile: fills empty fields and raises a conflict wherever "
          "values differ. Never changes the verified details (name, email, phone, vertical, category, services).", merge_scraped_data)
_register("present_conflicts",
          "Show the user each conflict to resolve (license: which is real or keep both; address: primary / secondary / not current; "
          "others: pick one). They choose; you never do.", present_conflicts, ui=True)
_register("apply_default_business_hours",
          "Fill business hours with the category's default if nothing else supplied them.", apply_default_business_hours)
_register("complete_onboarding",
          "Finish onboarding. Refused (with the reasons) while anything is unresolved. On success returns the real score, rank and per-section "
          "points to tell the user.", complete_onboarding, ui=True)
