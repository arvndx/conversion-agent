"""The test dashboard (plan A1): one set of pages per customer, with no login.

Each customer has its own URL: /c/<resource_id>. The API only returns that one customer's data, so a page never
shows another customer's details. The numbers and visits come from the conv_ tables.
Every page reads the conversion agent's tables (conv_*). The demo data is in the local database.

Run from the app folder:
    .venv/bin/uvicorn dashboard.server:app --port 8010
"""

import contextvars
from contextlib import contextmanager
import copy
import hashlib
import json
import re
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from pipeline.load_chat import connect, load_bundles, redis_client
from pipeline.site_bundles import publish_customer
from shared.bundle_tables import load_customer
from pipeline.topics import label_for
from pipeline.classify import ROUTE_MODEL, _json_from, call_model
from dashboard import store
from pipeline import widget_settings
from pipeline.widget_settings import DEFAULT_STYLE, HEX, get_theme
from shared.bundles import customer_key
from shared.site_keys import new_site_key

HERE = Path(__file__).resolve().parent
PAGES = {name: HERE / f"{name}.html" for name in ("index", "people", "replies", "admin")}
DAYS = 90
RESOURCE_TYPE = "professional"

MAX_DOMAINS = 4                          # a customer can have one to four domains
DOMAIN_NAME = re.compile(r"^(localhost|[a-z0-9-]+(\.[a-z0-9-]+)+)(:[0-9]{2,5})?$")   # localhost:port is for the test sites
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)
PROFILE_HOST = "experience.example"      # our experience profile page (demo)
FONT_SIZES = list(range(8, 17))
FONT_FAMILIES = ["Arial", "Times New Roman", "Georgia", "Verdana", "Helvetica", "Trebuchet MS"]
FEEDBACK_REASONS = ["Wrong answer", "Did not answer my question", "Too long", "Hard to understand", "Other"]
# The state below is kept in memory (demo). Production keeps it in the input database and Redis.
app = FastAPI(title="Conversion Agent dashboard (test, mock numbers)")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
# The demo widget (the demo website on another port) asks the same answer engine as the Playground.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8001", "http://127.0.0.1:8001",
                                                  "http://localhost:8002", "http://127.0.0.1:8002"],
                   allow_methods=["POST"], allow_headers=["Content-Type"])


class Colours(BaseModel):
    primary: str
    accent: str


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _norm(value) -> str:
    return re.sub(r"[\s–—-]+", " ", str(value or "")).strip().lower()


CURRENT_USER = "customer (demo: no sign-in yet)"   # who made a change; the sign-in fills this in later
BATCH_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("batch_id", default=None)


CONN: contextvars.ContextVar = contextvars.ContextVar("conn", default=None)


@contextmanager
def _db():
    """The connection for one step: the batch's own while a batch is saving (so a refused part undoes the whole batch),
    otherwise a new connection that is committed when the step is done."""
    current = CONN.get()
    if current is not None:
        yield current
    else:
        with connect() as conn:
            yield conn


def _log(resource_id: str, *, area: str, action: str, summary: str, target: str | None = None,
         before=None, after=None, page: str = "admin") -> None:
    """Save one change to the change log: what changed, where, when, who, and the values before and after."""
    with _db() as conn:
        store.log_change(conn, resource_id, who=CURRENT_USER, page=page, area=area, action=action, summary=summary,
                         target=target, before=before, after=after, batch_id=BATCH_ID.get())
        if CONN.get() is None:   # inside a knowledge batch the bundle is published after the batch commits
            publish_customer(conn, redis_client(), resource_id)   # a new customer bundle version: new chats use the change


def _customer(resource_id: str) -> dict:
    """The one customer this URL is for (a professional). Its domains are its sites; the name, the hot-visitor threshold
    and the kill switch come from the tables."""
    with connect() as conn:
        sites = _sites(conn, resource_id)
        if not sites:
            raise HTTPException(status_code=404, detail="no such customer")
        domains = [site["domain"] for site in sites]
        theme = {d: get_theme(conn, RESOURCE_TYPE, resource_id, d) for d in domains}
        settings = store.get_settings(conn, resource_id)
        name = conn.execute("select display_name from professionals where id = %s", (resource_id,)).fetchone()[0]
    status = "active" if any(site["status"] == "active" for site in sites) else sites[0]["status"]
    kill = settings["kill_switch"] or "none"
    enabled = sites[0]["plan"] == "active" and kill != "stop_everything"
    return {
        "resource_id": resource_id, "enabled": enabled, "kill_switch": kill, "domains": domains,
        "plan": sites[0]["plan"], "status": status, "name": name or resource_id,
        "threshold": int(settings["hot_visitor_threshold"]), "theme": theme,
    }


def _category(resource_id: str) -> tuple[dict, dict]:
    """The category bundle and the customer bundle, built from the tables (shared/bundle_tables.py)."""
    from shared.bundle_tables import load_category, load_customer
    with connect() as conn:
        gcid = conn.execute("select gcid from professionals where id = %s", (resource_id,)).fetchone()
        if gcid is None:
            raise HTTPException(status_code=404, detail="no such customer")
        return load_category(conn, gcid[0]), load_customer(conn, resource_id)


# ---- pages -------------------------------------------------------------------------------------------------------

def _page(name: str) -> FileResponse:
    return FileResponse(PAGES[name], media_type="text/html")


@app.get("/c/{resource_id}")
def page(resource_id: str) -> FileResponse:
    _customer(resource_id)  # 404 for an unknown customer
    return _page("index")


@app.get("/c/{resource_id}/people")
def people_page(resource_id: str) -> FileResponse:
    _customer(resource_id)
    return _page("people")


@app.get("/c/{resource_id}/replies")
def replies_page(resource_id: str) -> FileResponse:
    _customer(resource_id)
    return _page("replies")


@app.get("/c/{resource_id}/admin")
def admin_page(resource_id: str) -> FileResponse:
    _customer(resource_id)
    return _page("admin")


@app.get("/c/{resource_id}/leads")
def leads_redirect(resource_id: str) -> RedirectResponse:
    # The leads list is the first tab of the leads and hot visitors page.
    _customer(resource_id)
    return RedirectResponse(url=f"/c/{resource_id}/people", status_code=307)


# ---- overview and leads ------------------------------------------------------------------------------------------

@app.get("/api/c/{resource_id}/dashboard")
def dashboard(resource_id: str) -> dict:
    customer = _customer(resource_id)
    public = {k: customer[k] for k in ("resource_id", "name", "enabled", "kill_switch", "plan", "status", "domains")}
    public["theme"] = customer["theme"]
    return {"customer": public, "daily": _daily(resource_id, customer["domains"])}


# How a handover reason is stored (leads.reason) and how the pages show it.
REASON_LABEL = {
    "request_from_visitor": "Request from visitor",
    "time_in_widget": "Spent more time in widget",
    "unavailable_answer": "Unavailable or unknown answer",
    "confused_question": "Confused question",
    "unsure_question": "Unsure question",
}


def _since() -> datetime:
    """The start of the period the pages show (the last DAYS days)."""
    return datetime.now(timezone.utc) - timedelta(days=DAYS)


def _daily(resource_id: str, domains: list[str]) -> list[dict]:
    """One row per day for the period, with each domain's numbers. A day with no numbers shows zeros."""
    first = datetime.now(timezone.utc).date() - timedelta(days=DAYS - 1)
    with connect() as conn:
        rows = conn.execute(
            "SELECT d.domain, d.day, d.visitors, d.chats, d.handovers, d.hot_visitors FROM conv_daily d "
            "WHERE d.professional_id = %s AND d.day >= %s",
            (resource_id, first)).fetchall()
    found: dict = {}
    for domain, day, visitors, chats, leads, hot in rows:
        found.setdefault(day, {})[domain] = {"visitors": visitors, "chats": chats, "leads": leads, "hot": hot}
    empty = {"visitors": 0, "chats": 0, "leads": 0, "hot": 0}
    return [{"date": (first + timedelta(days=i)).isoformat(),
             "domains": {d: found.get(first + timedelta(days=i), {}).get(d, dict(empty)) for d in domains}}
            for i in range(DAYS)]


def _turns(messages) -> list[dict]:
    """A chat as the pages show it: one line for each visitor message and each reply, in order."""
    lines = []
    for turn in messages or []:
        for text in turn.get("request") or []:
            lines.append({"who": "visitor", "text": text, "at": turn.get("event_time")})
        if turn.get("response"):
            lines.append({"who": "bot", "text": turn["response"], "at": turn.get("event_time")})
    return lines


def _predefined_key(category: dict, text: str) -> str | None:
    """The predefined field this text names (by key or by label), or None when it is a custom field."""
    want = _slug(text)
    for key, label in store.FIELD_LABELS.items():
        if want in (_slug(key), _slug(label)):
            return key
    return None


SUGGEST_SYSTEM = (
    "A business's chatbot could not answer a visitor's question. Decide where the business should add the answer. "
    'Reply with JSON only, in this form: {"tab": "menu" | "defaults" | "custom", "key": "...", "name": "..."}. '
    "Use menu when the question is about a dish or the menu. Use defaults when it is about one of the predefined "
    "fields listed, and give that field's key. Use custom for anything else, and give a short name for it."
)


def _rule_suggestion(card_text: str, field: str, category: dict) -> dict:
    """Used only when the model is not available: the menu for dishes, a predefined field when one matches, else custom."""
    if re.search(r"menu|dish|burger|pizza|biryani|starter|drink", card_text, re.I) or field in ("menu", "dish_search"):
        return {"tab": "menu", "key": None}
    key = _predefined_key(category, field)
    if key:
        return {"tab": "defaults", "key": key}
    return {"tab": "custom", "key": field}


def _suggest_target(card_text: str, field: str, category: dict) -> dict:
    """Where the answer should be added. The model decides; the keyword rule is the fallback, and the card says which one decided."""
    options = "; ".join(f"{key} ({label})" for key, label in store.FIELD_LABELS.items())
    try:
        data = _json_from(call_model(ROUTE_MODEL, SUGGEST_SYSTEM,
                                     f"Visitor question: {card_text}\nPredefined fields: {options}"))
        tab = data.get("tab")
        if tab == "menu":
            out = {"tab": "menu", "key": None}
        elif tab == "defaults" and _predefined_key(category, str(data.get("key", ""))):
            out = {"tab": "defaults", "key": _predefined_key(category, str(data["key"]))}
        elif tab == "custom" and str(data.get("name", "")).strip():
            out = {"tab": "custom", "key": " ".join(str(data["name"]).split())[:40]}
        else:
            raise ValueError("the model answered with no usable destination")
        return {**out, "by": "llm"}
    except Exception:
        return {**_rule_suggestion(card_text, field, category), "by": "rule"}


def _to_target(tab: str, key: str | None) -> str:
    return "menu" if tab == "menu" else f"{'defaults' if tab == 'defaults' else 'custom'}:{key}"


def _from_target(target: str) -> dict:
    if target == "menu":
        return {"tab": "menu", "key": None}
    tab, _, key = target.partition(":")
    return {"tab": "defaults" if tab == "defaults" else "custom", "key": key}


SUGGEST_ANSWER_SYSTEM = """You help a business answer a question its website chat could not answer.
Use ONLY the business facts you are given. If they do not answer the question, return an empty answer. Do not invent prices,
times, policies or availability.
Return JSON only, with two keys:
  "answer": one or two plain sentences the chat can say to the visitor, or "" if the facts do not answer it.
  "key": the field the answer belongs to. Use one of: phone, email, opening_hours, response_hours, services, offers.
         If none of these fits, a new short field name of two to four words (for example "kids menu")."""


def _business_facts(conn, resource_id: str) -> dict:
    """The facts the AI may use to suggest an answer: the business's own data, nothing else."""
    customer = load_customer(conn, resource_id)
    return {"name": f'{customer["display_name"]["first_name"]} {customer["display_name"]["last_name"]}',
            "category": customer["category_id"].replace("_", " "), "opening_hours": customer.get("business_hours"),
            "phone": customer["public_contact"]["phone"], "email": customer["public_contact"]["email"],
            "services": customer.get("services"), "offers": customer.get("offers"),
            "response_hours": customer.get("response_hours"), "parking": customer.get("parking"),
            "custom_fields": customer.get("custom_fields"),
            "menu_dishes": [d["name"] for dishes in (customer.get("menu") or {}).values() for d in dishes]}


def _suggest_answer(card_text: str, facts: dict, category: dict) -> dict:
    """The AI's suggested answer and the field it belongs to. From the business's facts only; empty when they do not answer."""
    try:
        data = _json_from(call_model(ROUTE_MODEL, SUGGEST_ANSWER_SYSTEM,
                                     f"Question: {card_text}\nBusiness facts: {json.dumps(facts, ensure_ascii=False, default=str)}"))
        answer = str(data.get("answer") or "").strip()[:1000]
        key = " ".join(str(data.get("key") or "").split())[:40] or " ".join(card_text.split()[:3])[:40]
        return {"answer": answer, "key": key, "by": "llm"}
    except Exception:
        return {"answer": "", "key": " ".join(card_text.split()[:3])[:40], "by": "rule"}


@app.get("/api/c/{resource_id}/insights")
def insight_cards(resource_id: str) -> dict:
    """The questions the chat could not answer, each with a suggested answer and the field it would be saved in. The
    suggestion is made once per question; the business can change it and save it."""
    _customer(resource_id)
    category, _ = _category(resource_id)
    cards = []
    with _db() as conn:
        facts = None
        for row in store.insights(conn, resource_id):
            # A suggestion from the keyword rule (the model was unavailable) is tried again, so the card gets the model's.
            if row["suggested_answer"] is None or row["suggested_target"] is None or row["suggested_target"].endswith("|rule"):
                facts = facts or _business_facts(conn, resource_id)
                suggestion = _suggest_answer(row["question"], facts, category)
                tab = "defaults" if suggestion["key"] in store.ANSWER_COLUMNS else "custom"
                target = _to_target(tab, suggestion["key"])
                store.set_suggestion(conn, resource_id, row["question"], target, suggestion["by"])
                store.set_suggested_answer(conn, resource_id, row["question"], suggestion["answer"], suggestion["key"])
                row = {**row, "suggested_answer": suggestion["answer"], "suggested_key": suggestion["key"],
                       "suggested_target": f"{target}|{suggestion['by']}"}
            target, by = row["suggested_target"].split("|", 1) if "|" in row["suggested_target"] else (row["suggested_target"], "llm")
            confirmed = _from_target(row["confirmed_target"]) if row["confirmed_target"] else None
            cards.append({"text": row["question"], "count": row["asked"], "suggested": _from_target(target),
                          "suggested_by": by, "confirmed": confirmed, "target": confirmed or _from_target(target),
                          "suggested_answer": row["suggested_answer"] or "", "suggested_key": row["suggested_key"] or "",
                          "predefined": [{"key": k, "label": v} for k, v in store.FIELD_LABELS.items()]})
    fields = [{"key": k, "label": v} for k, v in store.FIELD_LABELS.items()]
    return {"period_days": 30, "cards": cards, "fields": fields}


class InsightAnswerIn(BaseModel):
    text: str           # the visitor's question, as on the card
    answer: str
    key: str            # a predefined field (phone, email, opening_hours, response_hours, services, offers) or a new field name


@app.put("/api/c/{resource_id}/insights/answer")
def answer_insight(resource_id: str, body: InsightAnswerIn) -> dict:
    """Save the business's answer. A predefined field takes it in its column; any other name becomes a custom field. The
    question stays in the list, marked answered, and the customer bundle is published as a new version."""
    _customer(resource_id)
    question = " ".join(body.text.split())
    answer = body.answer.strip()
    key = " ".join(body.key.split())
    if not 2 <= len(question) <= 300:
        raise HTTPException(status_code=422, detail="the question is missing")
    if not 2 <= len(answer) <= 1000:
        raise HTTPException(status_code=422, detail="the answer needs 2 to 1000 characters")
    if key not in store.ANSWER_COLUMNS and not 2 <= len(key) <= 40:
        raise HTTPException(status_code=422, detail="the field name needs 2 to 40 characters")
    with _db() as conn:
        try:
            where = store.save_insight_answer(conn, resource_id, question, answer, key, CURRENT_USER)
        except ValueError as error:   # for example a field name that is kept for the business's links
            raise HTTPException(status_code=422, detail=str(error))
    _log(resource_id, area="insights", target=question, action="answered", page="overview",
         summary=f'Answer for "{question}" saved to {where["label"]}', after={"key": key, "answer": answer[:200]})
    return {"text": question, "saved": True, "key": key, "label": where["label"], "custom": where["custom"]}


class InsightConfirmIn(BaseModel):
    text: str
    tab: str            # menu, defaults or custom
    key: str | None = None


def _where(tab: str, key: str | None) -> str:
    return {"menu": "Menu", "defaults": f"Default fields: {key}", "custom": f"Custom fields: {key}"}[tab]


@app.put("/api/c/{resource_id}/insights/confirm")
def confirm_insight(resource_id: str, body: InsightConfirmIn) -> dict:
    """The business confirms where a question's answer goes. Saved to the change history."""
    _customer(resource_id)
    category, _ = _category(resource_id)
    if body.tab not in ("menu", "defaults", "custom"):
        raise HTTPException(status_code=422, detail="choose the Menu, a Default field or a Custom field")
    key = None
    if body.tab == "defaults":
        key = _predefined_key(category, body.key or "")
        if key is None:
            raise HTTPException(status_code=422, detail="choose one of the default fields")
    elif body.tab == "custom":
        key = " ".join((body.key or "").split())
        if not 2 <= len(key) <= 40:
            raise HTTPException(status_code=422, detail="the custom field needs a name of 2 to 40 characters")
        if _predefined_key(category, key):
            raise HTTPException(status_code=422, detail=f'"{key}" is already a predefined field. Choose it under Default fields.')
    target = _to_target(body.tab, key)
    with _db() as conn:
        before = conn.execute("select confirmed_target from conv_question where professional_id = %s and question_text = %s limit 1",
                              (resource_id, body.text)).fetchone()
        try:
            store.confirm_insight(conn, resource_id, body.text, target, CURRENT_USER)
        except LookupError:
            raise HTTPException(status_code=404, detail="no such card")
    previous = _from_target(before[0]) if before and before[0] else None
    if previous != {"tab": body.tab, "key": key}:
        _log(resource_id, area="insights", target=body.text, action="confirmed", page="overview",
             summary=f'Where to add "{body.text}": {_where(body.tab, key)}',
             before=previous, after={"tab": body.tab, "key": key})
    return {"text": body.text, "target": {"tab": body.tab, "key": key}}


@app.get("/api/c/{resource_id}/feedback")
def feedback(resource_id: str) -> dict:
    """The topics visitors asked about, per day and domain (conv_daily.topic_counts). Labels come from the actions."""
    customer = _customer(resource_id)
    category, _ = _category(resource_id)
    with connect() as conn:
        rows = store.topic_counts(conn, resource_id)
        labels_by_key = store.action_labels(conn, category["gcid"])
    name = lambda topic_id: labels_by_key.get(topic_id) or topic_id.replace("_", " ").capitalize()  # noqa: E731
    counts: dict[str, dict] = {}
    for domain, day, per_topic in rows:
        counts.setdefault(domain, {})[day.isoformat()] = per_topic or {}
    labels = sorted({name(t) for per_domain in counts.values() for per_day in per_domain.values() for t in per_day})
    first = datetime.now(timezone.utc).date() - timedelta(days=DAYS - 1)
    daily = []
    for i in range(DAYS):
        day = (first + timedelta(days=i)).isoformat()
        domains = {}
        for domain in customer["domains"]:
            per_topic = counts.get(domain, {}).get(day, {})
            shown = {name(t): n for t, n in per_topic.items()}
            domains[domain] = {"topics": shown | {label: 0 for label in labels if label not in shown}}
        daily.append({"date": day, "domains": domains})
    return {"topics": labels, "reasons": FEEDBACK_REASONS, "daily": daily}


LEAD_REASON_LABEL = {
    "request_from_visitor": "Asked for it", "critical_question": "Critical question",
    "unsure_question": "Unclear question", "unavailable_answer": "Not on record", "time_in_widget": "Long chat",
    "system_fallback": "System fallback",
}


@app.get("/api/c/{resource_id}/people")
def people(resource_id: str) -> dict:
    """Leads (handovers) with name, contact, status, query, reason, and the chat; and hot visitors (score at or above
    the threshold)."""
    customer = _customer(resource_id)
    with connect() as conn:
        leads = store.people_leads(conn, resource_id, _since())
        hot = store.people_hot(conn, resource_id, _since())
        gcid = conn.execute("select gcid from professionals where id = %s", (resource_id,)).fetchone()[0]
        actions = {**store.action_labels(conn, "general"), **store.action_labels(conn, gcid)}   # action key -> its name
        hot_rows = []
        for visitor_id, domain, city, state, seconds, score, seen in hot:
            summary, messages = store.latest_chat(conn, resource_id, domain, visitor_id)
            hot_rows.append({"id": str(visitor_id), "domain": domain, "location": ", ".join(x for x in [city, state] if x),
                             "seconds_chat": seconds or 0, "score": score, "seen": seen.isoformat(),
                             "chatted": messages is not None and len(messages or []) > 0,
                             "summary": summary or "", "conversation": _turns(messages)})
    return {
        "threshold": customer["threshold"],
        "leads": [{
            "id": str(r[0]), "name": r[1], "email": r[2] or "", "phone": r[3] or "", "question": r[5] or "",
            "reason": LEAD_REASON_LABEL.get(r[4], ""), "summary": r[6] or "", "status": r[7], "when": r[8].isoformat(),
            "domain": r[9], "location": ", ".join(x for x in [r[10], r[11]] if x), "seconds_chat": r[12] or 0,
            "score": r[13] or 0, "conversation": _turns(r[16]), "pages": None, "clicks": r[14],
            "seconds_site": r[15], "request_type": r[17], "action": actions.get(r[18], r[18] or ""), "extra": r[19] or {},
        } for r in leads],
        "hot": hot_rows,
    }


class LeadStatusIn(BaseModel):
    status: str


@app.put("/api/c/{resource_id}/leads/{lead_id}/status")
def set_lead_status(resource_id: str, lead_id: str, body: LeadStatusIn) -> dict:
    """Set a lead's status (new, contacted or closed). Saved to the change history."""
    _customer(resource_id)
    try:
        UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="no such lead")
    with connect() as conn:
        before = conn.execute("select name, status from conv_handover where professional_id = %s and handover_id = %s",
                              (resource_id, lead_id)).fetchone()
        if before is None:
            raise HTTPException(status_code=404, detail="no such lead")
        try:
            store.set_lead_status(conn, resource_id, lead_id, body.status)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        conn.commit()
    name, old = before
    _log(resource_id, area="leads", target=lead_id, action="status_changed", page="leads",
         summary=f"{name}: status {old} → {body.status}", before={"status": old}, after={"status": body.status})
    return {"id": lead_id, "status": body.status}


# ---- replies -----------------------------------------------------------------------------------------------------

@app.get("/api/c/{resource_id}/replies")
def replies(resource_id: str) -> dict:
    """Replies the visitors rated (thumbs up or down), with the reason when down and the whole chat around each one."""
    _customer(resource_id)
    with connect() as conn:
        rows = store.replies_full(conn, resource_id, _since())
    items = []
    for r in rows:
        reason = f"Other: {r[4]}" if r[3] == "other" and r[4] else FEEDBACK_LABEL.get(r[3] or "", "")
        items.append({"id": str(r[0]), "domain": r[8], "when": r[1].isoformat(), "question": r[6] or "",
                      "reply": r[7] or "", "topic": r[5] or "", "feedback": "up" if r[2] == "up" else "down",
                      "reason": reason, "conversation": _turns(r[9])})
    return {"replies": items}


FEEDBACK_LABEL = {"wrong_answer": "Wrong answer", "did_not_answer": "Did not answer my question", "too_long": "Too long",
                  "hard_to_understand": "Hard to understand", "other": "Other"}


@app.get("/api/c/{resource_id}/changes")
def changes(resource_id: str) -> dict:
    """The saved change history for this customer, newest first (the last 50)."""
    _customer(resource_id)
    with _db() as conn:
        rows = store.recent_changes(conn, resource_id)
    return {"changes": [{"at": r[0].isoformat(), "who": r[1], "page": r[2], "area": r[3], "target": r[4], "action": r[5],
                         "summary": r[6], "before": r[7], "after": r[8], "batch": str(r[9]) if r[9] else None}
                        for r in rows]}


def _default_domains(resource_id: str) -> list[str]:
    """The domain of the business's own web page (its website from the platform copy), when it has one."""
    with connect() as conn:
        row = conn.execute("select website_url from professionals where id = %s", (resource_id,)).fetchone()
    host = urlparse(row[0] or "").netloc if row else ""
    return [host] if host else []


# ---- admin: subscription, domains and widget look (kept on the sites: one site per domain) -----------------------

def _sites(conn, resource_id: str, cancelled: bool = False) -> list[dict]:
    """The customer's domains (conv_domains). The plan is the conversion agent entitlement (read only)."""
    rows = conn.execute(
        """select d.domain, d.site_key, d.status, p.gcid, p.display_name,
           (select e.state from exp_entitlements e join professionals pr on pr.primary_org_id::text = e.subject_id
            where pr.id = d.professional_id and e.product_key = 'conversion_agent' limit 1)
           from conv_domains d join professionals p on p.id = d.professional_id
           where d.professional_id = %s order by d.domain""", (resource_id,)).fetchall()
    return [{"site_id": None, "domain": r[0], "site_key": r[1], "status": r[2], "plan": r[5] or "none", "gcid": r[3],
             "entity_type": "professional", "display_name": r[4], "settings": {}} for r in rows]


def _set_bundle(resource_id: str, **fields) -> None:
    """The chat reloads the professional's bundles on every request (see api/chat_api.py), so there is nothing to write."""
    return None


@app.get("/api/c/{resource_id}/subscription")
def subscription(resource_id: str) -> dict:
    _customer(resource_id)
    with _db() as conn:
        state, term = store.entitlement(conn, resource_id)
    return {"subscribed": state == "active", "plan": term or "monthly", "plans": ["monthly", "yearly"]}


class SubscriptionIn(BaseModel):
    subscribed: bool
    plan: str = "monthly"


@app.put("/api/c/{resource_id}/subscription")
def set_subscription(resource_id: str, body: SubscriptionIn) -> dict:
    """Subscribed means the conversion agent is active for the office (the chat runs). Demo: the local copy changes."""
    _customer(resource_id)
    if body.plan not in ("monthly", "yearly"):
        raise HTTPException(status_code=422, detail="choose a plan")
    with _db() as conn:
        before = store.entitlement(conn, resource_id)
        try:
            store.set_entitlement(conn, resource_id, "active" if body.subscribed else "cancelled", body.plan)
        except LookupError:
            raise HTTPException(status_code=404, detail="no office for this customer")
    _log(resource_id, area="subscription", action="subscribed" if body.subscribed else "unsubscribed",
         summary=("Subscribed" if body.subscribed else "Cancelled the subscription") + f" ({body.plan})",
         before={"state": before[0], "plan": before[1]}, after={"subscribed": body.subscribed, "plan": body.plan})
    return {"subscribed": body.subscribed, "plan": body.plan}


@app.get("/api/c/{resource_id}/domains")
def domains(resource_id: str) -> dict:
    _customer(resource_id)
    with _db() as conn:
        names = [d for d, status, _ in store.sites(conn, resource_id) if status == "active"]
    return {"domains": names, "max": MAX_DOMAINS, "defaults": _default_domains(resource_id)}


class DomainsIn(BaseModel):
    domains: list[str]


@app.put("/api/c/{resource_id}/domains")
def set_domains(resource_id: str, body: DomainsIn) -> dict:
    """Each domain is its own site with its own key. A domain no longer listed is paused (its visits and chats stay)."""
    _customer(resource_id)
    names = [d.strip().lower() for d in body.domains if d.strip()]
    if not 1 <= len(names) <= MAX_DOMAINS:
        raise HTTPException(status_code=422, detail=f"add one to {MAX_DOMAINS} domains")
    if len(set(names)) != len(names):
        raise HTTPException(status_code=422, detail="each domain can be listed once")
    if any(not DOMAIN_NAME.match(n) for n in names):
        raise HTTPException(status_code=422, detail="write the domain name only, for example spicegarden.example")
    with _db() as conn:
        before = store.active_domains(conn, resource_id)
        store.set_domains(conn, resource_id, names, lambda: new_site_key(test=True))
    _log(resource_id, area="domains", action="changed", summary="Domains set to " + ", ".join(names),
         before={"domains": before}, after={"domains": names})
    return {"domains": names}


@app.get("/api/c/{resource_id}/style")
def style(resource_id: str) -> dict:
    """The widget colours per domain. Font and placement are not stored yet: the defaults are shown."""
    _customer(resource_id)
    with _db() as conn:
        colours = store.domain_colours(conn, resource_id)
    per = {d: {**DEFAULT_STYLE, "primary": p, "accent": a} for d, (p, a) in colours.items()}
    return {"domains": per, "defaults": DEFAULT_STYLE, "font_sizes": FONT_SIZES, "font_families": FONT_FAMILIES}


class StyleIn(BaseModel):
    font_size: int
    font_family: str
    primary: str
    accent: str
    text: str
    placement: str


@app.put("/api/c/{resource_id}/style/{domain}")
def set_style(resource_id: str, domain: str, body: StyleIn) -> dict:
    _customer(resource_id)
    if body.font_size not in FONT_SIZES or body.font_family not in FONT_FAMILIES:
        raise HTTPException(status_code=422, detail="choose a font size and a font from the list")
    if body.placement not in ("left", "right"):
        raise HTTPException(status_code=422, detail="placement is left or right")
    if not all(HEX.match(c) for c in (body.primary, body.accent, body.text)):
        raise HTTPException(status_code=422, detail="colours must be #RRGGBB")
    with _db() as conn:
        if domain not in store.active_domains(conn, resource_id):
            raise HTTPException(status_code=404, detail="not one of this customer's domains")
        before = widget_settings.get_style(conn, resource_id, domain)
        after = widget_settings.set_style(conn, resource_id, domain, body.model_dump())
    _log(resource_id, area="widget_look", action="changed", target=domain, summary=f"Widget look changed on {domain}",
         before=before, after=body.model_dump())
    return after


@app.post("/api/c/{resource_id}/style/{domain}/reset")
def reset_style(resource_id: str, domain: str) -> dict:
    _customer(resource_id)
    with _db() as conn:
        before = widget_settings.get_style(conn, resource_id, domain)
        widget_settings.reset_style(conn, resource_id, domain)
    _log(resource_id, area="widget_look", action="reset", target=domain, summary=f"Widget look reset on {domain}",
         before=before, after=DEFAULT_STYLE)
    return DEFAULT_STYLE


@app.get("/api/c/{resource_id}/admin")
def admin(resource_id: str) -> dict:
    """The business details, the widget switch and the chef's specials for the admin page."""
    customer = _customer(resource_id)
    category, cust = _category(resource_id)
    name = customer["name"]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    chef = _chef(resource_id)
    with _db() as conn:
        settings = store.get_settings(conn, resource_id)
    hours = settings.get("opening_hours") or {}
    return {
        "business": {
            "name": name,
            "web_page": _default_domains(resource_id)[0] if _default_domains(resource_id) else "",
            "experience_profile": f"https://experience.example/profiles/{slug}",
            "address": cust.get("primary_location", ""),
            "phone": settings.get("public_phone") or "",
            "email": settings.get("public_email") or "",
            "timezone": settings.get("timezone", ""),
            "domains": customer["domains"],
            "hours": hours.get("mon_fri", "") if isinstance(hours, dict) else "",
        },
        "widget": {
            "subscribed": customer["status"] == "active",
            "plan": customer["plan"],
            "enabled": customer["enabled"],
        },
        "chef": {
            "dishes": sorted(d["name"] for d in _menu_dishes(resource_id, cust)),
            "specials": chef.get("specials", []),
            "menu_url": chef.get("menu_url") or "",
        },
    }


class WidgetStatusIn(BaseModel):
    enabled: bool


@app.put("/api/c/{resource_id}/widget-status")
def set_widget_status(resource_id: str, body: WidgetStatusIn) -> dict:
    """The widget goes on only after the chef's specials are chosen and every conflict is resolved."""
    customer = _customer(resource_id)
    if body.enabled:
        category, cust = _category(resource_id)
        if _menu_dishes(resource_id, cust) and len(_chef(resource_id).get("specials", [])) < 2:
            raise HTTPException(status_code=409, detail="choose the chef's specials on the Menu tab first")
        conflicts = sum(1 for row in _knowledge_rows(resource_id, cust, category) if row["status"] == "conflict")
        if conflicts:
            raise HTTPException(status_code=409, detail=f"resolve the {conflicts} conflict(s) on the Get data tab first")
    before = customer["enabled"]
    with _db() as conn:
        store.set_kill_switch(conn, resource_id, "none" if body.enabled else "stop_everything",
                              None if body.enabled else "switched off on the dashboard", CURRENT_USER)
    _log(resource_id, area="widget_status", action="turned_on" if body.enabled else "turned_off",
         summary="Widget turned " + ("on" if body.enabled else "off"), before={"enabled": before},
         after={"enabled": body.enabled})
    return {"enabled": body.enabled}


class ChefSpecials(BaseModel):
    specials: list[str]
    menu_url: str


def _chef(resource_id: str) -> dict:
    """The chef's specials and the full menu link (the specials are the menu's chef flags; the link is the view menu link)."""
    with _db() as conn:
        return {"specials": store.chef_specials(conn, resource_id), "menu_url": store.menu_link(conn, resource_id)}


@app.put("/api/c/{resource_id}/chef-specials")
def set_chef_specials(resource_id: str, body: ChefSpecials) -> dict:
    """Two or three chef's specials, each a dish on the menu, and the link to the full menu."""
    _customer(resource_id)
    _, cust = _category(resource_id)
    dishes = {d["name"] for d in _menu_dishes(resource_id, cust)}
    picks = [x.strip() for x in body.specials if x.strip()]
    if not 2 <= len(picks) <= 3:
        raise HTTPException(status_code=422, detail="choose two or three chef's specials")
    if len(set(picks)) != len(picks) or not set(picks) <= dishes:
        raise HTTPException(status_code=422, detail="each special must be a different dish on the menu")
    if not body.menu_url.startswith("https://"):
        raise HTTPException(status_code=422, detail="the full menu link must start with https://")
    before = _chef(resource_id)
    value = {"specials": picks, "menu_url": body.menu_url.strip()}
    with _db() as conn:
        store.set_chef_specials(conn, resource_id, picks)
        store.set_menu_link(conn, resource_id, cust["gcid"], value["menu_url"])
    _log(resource_id, area="menu", target="chef_specials", action="changed",
         summary="Chef's specials: " + ", ".join(picks), before=before, after=value)
    return value


class ChatContactIn(BaseModel):
    phone: bool
    email: bool


@app.get("/api/c/{resource_id}/chat-contact")
def chat_contact(resource_id: str) -> dict:
    """Whether the chat may show the business's phone and email (the display switches)."""
    _customer(resource_id)
    with _db() as conn:
        sw = store.switches(conn, resource_id)
    return {"phone": sw.get("phone") == "enable", "email": sw.get("email") == "enable"}


@app.put("/api/c/{resource_id}/chat-contact")
def set_chat_contact(resource_id: str, body: ChatContactIn) -> dict:
    """Switch on or off the phone and the email in the chat. Off: the chat hands the visitor over instead."""
    _customer(resource_id)
    before = chat_contact(resource_id)
    value = {"phone": body.phone, "email": body.email}
    with _db() as conn:
        store.set_switch(conn, resource_id, "phone", "enable" if body.phone else "disable")
        store.set_switch(conn, resource_id, "email", "enable" if body.email else "disable")
    _log(resource_id, area="chat_contact", action="changed",
         summary=f"Chat contact: phone {'on' if body.phone else 'off'}, email {'on' if body.email else 'off'}",
         before=before, after=value)
    return value


# ---- admin: menu availability -------------------------------------------------------------------------------------

def _menu_dishes(resource_id: str, cust: dict) -> list[dict]:
    """Every dish on the menu (conv_menu with the professional's price), with its id (the menu id)."""
    with _db() as conn:
        rows = store.menu(conn, resource_id)
    return [{"id": d["menu_id"], "name": d["name"], "section": d["section"], "price": d["price"],
             "vegetarian": False, "chef_special": d["chef_special"], "availability": d["availability"]} for d in rows]


def _dishes(resource_id: str, cust: dict) -> list[dict]:
    """Every dish with its availability: on, every day, unless the availability says otherwise."""
    out = []
    for dish in _menu_dishes(resource_id, cust):
        av = dish["availability"] or {}
        days = [WEEKDAYS.index(d) for d in av.get("days", WEEKDAYS) if d in WEEKDAYS]
        out.append({"id": dish["id"], "name": dish["name"], "section": (dish["section"] or "other").capitalize(),
                    "price": dish["price"], "vegetarian": False, "chef_special": dish["chef_special"],
                    "enabled": av.get("enabled", True), "days": days, "start": av.get("start"), "end": av.get("end")})
    return out


WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _opening_times(cust: dict) -> tuple[str, str]:
    """The opening and closing time on weekdays, from the business hours."""
    m = re.match(r"^\s*(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", cust.get("business_hours", {}).get("mon_fri", ""))
    return (m.group(1), m.group(2)) if m else ("11:00", "22:00")


@app.get("/api/c/{resource_id}/menu")
def menu(resource_id: str) -> dict:
    _customer(resource_id)
    _, cust = _category(resource_id)
    hours = cust.get("business_hours", {})
    open_from, open_to = _opening_times(cust)
    return {"dishes": _dishes(resource_id, cust), "open_from": open_from, "open_to": open_to,
            "hours": f"Mon–Fri {hours.get('mon_fri', '')}; Sat–Sun {hours.get('sat_sun', '')}" if hours else ""}


class DishIn(BaseModel):
    enabled: bool
    days: list[int]          # 0 = Monday ... 6 = Sunday
    start: str | None = None  # HH:MM, or None for the opening hours
    end: str | None = None


def _do_dish(resource_id: str, dish_id: str, body: DishIn) -> dict:
    _customer(resource_id)
    _, cust = _category(resource_id)
    dish = next((d for d in _dishes(resource_id, cust) if d["id"] == dish_id), None)
    if dish is None:
        raise HTTPException(status_code=404, detail="no such dish on the menu")
    days = sorted(set(body.days))
    if not days or any(d not in range(7) for d in days):
        raise HTTPException(status_code=422, detail="choose at least one day")
    if (body.start is None) != (body.end is None):
        raise HTTPException(status_code=422, detail="give both a start and an end time, or neither")
    for t in (body.start, body.end):
        if t is not None and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t):
            raise HTTPException(status_code=422, detail="times look like 11:30")
    if body.start is not None and body.start >= body.end:
        raise HTTPException(status_code=422, detail="the end time must be after the start time")
    with _db() as conn:
        store.set_dish_availability(conn, resource_id, dish_id, enabled=body.enabled, days=days, start=body.start, end=body.end)
    if body.enabled and not dish["enabled"]:
        action = "turned_on"
    elif dish["enabled"] and not body.enabled:
        action = "turned_off"
    else:
        action = "timing_changed"
    wording = {"turned_on": "turned on for the menu", "turned_off": "turned off for the menu",
               "timing_changed": "availability changed"}[action]
    _log(resource_id, area="menu", target=dish_id, action=action, summary=f"{dish['name']}: {wording}",
         before={k: dish[k] for k in ("enabled", "days", "start", "end")},
         after={"enabled": body.enabled, "days": days, "start": body.start, "end": body.end})
    return next(d for d in _dishes(resource_id, cust) if d["id"] == dish_id)


@app.put("/api/c/{resource_id}/menu/{dish_id}")
def set_dish(resource_id: str, dish_id: str, body: DishIn) -> dict:
    return _do_dish(resource_id, dish_id, body)


class NewDishIn(BaseModel):
    name: str
    section: str = "other"
    price: float | None = None
    vegetarian: bool = False


def _do_add_dish(resource_id: str, body: NewDishIn) -> dict:
    """Add a dish to the menu. It is available every day during opening hours until its timing is changed."""
    _customer(resource_id)
    _, cust = _category(resource_id)
    name = " ".join(body.name.split())
    if not 2 <= len(name) <= 60:
        raise HTTPException(status_code=422, detail="the dish name needs 2 to 60 characters")
    section = " ".join(body.section.split()).lower() or "other"
    if len(section) > 40:
        raise HTTPException(status_code=422, detail="the section name is too long (40 characters at most)")
    if body.price is not None and not 0 <= body.price <= 999:
        raise HTTPException(status_code=422, detail="the price must be between 0 and 999")
    if name.lower() in {d["name"].lower() for d in _menu_dishes(resource_id, cust)}:
        raise HTTPException(status_code=422, detail=f'"{name}" is already on the menu')
    with _db() as conn:
        store.save_dish(conn, resource_id, name, section=section, price=body.price or 0.0,
                        availability={"enabled": True, "days": WEEKDAYS, "start": None, "end": None})
    _log(resource_id, area="menu", target=name, action="added", summary=f"Dish added: {name} ({section})",
         after={"name": name, "section": section, "price": body.price})
    return next(d for d in _dishes(resource_id, cust) if d["name"] == name)


@app.post("/api/c/{resource_id}/menu")
def add_dish(resource_id: str, body: NewDishIn) -> dict:
    return _do_add_dish(resource_id, body)


KNOWLEDGE_LABELS = {**store.FIELD_LABELS, "parking": "Parking"}
KNOWLEDGE_ORDER = ["opening_hours", "response_hours", "services", "offers", "phone", "email", "parking"]


def _predefined_key(category: dict, text: str) -> str | None:
    """The predefined field this text names (by key or by label), or None when it is a custom field."""
    want = _slug(text)
    for key, label in KNOWLEDGE_LABELS.items():
        if want in (_slug(key), _slug(label)):
            return key
    return None


def _knowledge_rows(resource_id: str, cust: dict, category: dict) -> list[dict]:
    """One row per predefined field. The value in use is the stored value. A web value that differs from it is a conflict
    until the customer chooses; a chosen value is kept until the web value changes again."""
    rows = []
    with _db() as conn:
        for key in KNOWLEDGE_ORDER:
            db = store.field_value(conn, resource_id, key)
            fact = store.web_fact(conn, resource_id, key)
            web = fact[0] if fact and fact[0] and fact[0] != "" else None
            chosen, chosen_web = (fact[1], fact[2]) if fact else (False, None)
            shared = store.switches(conn, resource_id).get(key, "enable") == "enable"
            if chosen:
                status = "chosen" if _norm(chosen_web) == _norm(web) else "conflict"
                value = db
            elif db and web and _norm(db) != _norm(web):
                status, value = "conflict", None
            elif db:
                status, value = "database", db
            elif web:
                status, value = "web_only", web
            else:
                status, value = "missing", None
            rows.append({"key": key, "label": KNOWLEDGE_LABELS[key], "database": db, "scraped": web, "value": value,
                         "source": "database" if status in ("database", "chosen") and db else ("scraped" if status == "web_only" else None),
                         "status": status, "enabled": shared, "manual": None})
    return rows


def _valid_manual(key: str, value: str) -> str | None:
    if key == "email" and not EMAIL.match(value):
        return "The email address does not look right."
    if key == "phone" and len(re.sub(r"\D", "", value)) < 7:
        return "The phone number needs at least 7 digits."
    return None


@app.get("/api/c/{resource_id}/knowledge")
def knowledge(resource_id: str) -> dict:
    customer = _customer(resource_id)
    category, cust = _category(resource_id)
    rows = _knowledge_rows(resource_id, cust, category)
    with _db() as conn:
        url, checked = store.page_check(conn, resource_id)
    scrape = {"url": url or cust.get("weblink", ""), "checked_at": checked.isoformat() if checked else None}
    return {"fields": rows, "conflicts": sum(1 for r in rows if r["status"] == "conflict"),
            "scrape": scrape, "customer": customer["name"]}


class ScrapeIn(BaseModel):
    url: str


PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HOURS_PATTERN = re.compile(r"(Mon(?:day)?\s*[-–]\s*Fri(?:day)?[^<\n]{0,40}?\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", re.I)


def fetch_page(url: str) -> str:
    """The page's HTML (the first 500 KB). Used by the scrape; the tests replace it."""
    import urllib.request
    request = urllib.request.Request(url, headers={"User-Agent": "ConversionAgentCheck/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read(500_000).decode("utf-8", errors="replace")


def facts_from_page(html: str) -> dict[str, str]:
    """The phone, the email and the opening hours the page shows, when it shows them."""
    facts = {}
    text = re.sub(r"<[^>]+>", " ", html)
    if (match := EMAIL_PATTERN.search(text)):
        facts["email"] = match.group(0)
    for candidate in PHONE_PATTERN.findall(text):
        if len(re.sub(r"\D", "", candidate)) >= 7:
            facts["phone"] = " ".join(candidate.split())
            break
    if (match := HOURS_PATTERN.search(text)):
        facts["opening_hours"] = " ".join(match.group(1).split())
    return facts


@app.post("/api/c/{resource_id}/scrape")
def scrape_page(resource_id: str, body: ScrapeIn) -> dict:
    """Check the customer's web page: find the phone, email and opening hours it shows, and keep them. Conflicts with the
    stored values come back, and the customer chooses which one to use."""
    _customer(resource_id)
    url = body.url.strip()
    if not url.startswith("https://") or " " in url:
        raise HTTPException(status_code=422, detail="the web page link must start with https://")
    try:
        html = fetch_page(url)
    except Exception:
        raise HTTPException(status_code=502, detail="the web page could not be read")
    facts = facts_from_page(html)
    category, cust = _category(resource_id)
    with _db() as conn:
        domain = store.active_domains(conn, resource_id)[0]
        store.scrape_page(conn, resource_id, domain, url, facts)
    checked = datetime.now(timezone.utc).isoformat()
    rows = _knowledge_rows(resource_id, cust, category)
    conflicts = sum(1 for r in rows if r["status"] == "conflict")
    _log(resource_id, area="knowledge", target="web_page", action="checked",
         summary=f"Web page checked: {len(facts)} fact(s) found, {conflicts} conflict(s) to resolve",
         after={"url": url, "conflicts": conflicts})
    return {"url": url, "checked_at": checked, "found": len(facts), "conflicts": conflicts}


class ChoiceIn(BaseModel):
    source: str                # database, scraped or manual
    manual: str | None = None


def _do_choose(resource_id: str, key: str, body: ChoiceIn) -> dict:
    """Confirm which value a field uses, or type it by hand. Returns the row and whether the database differs."""
    _customer(resource_id)
    category, cust = _category(resource_id)
    rows = {r["key"]: r for r in _knowledge_rows(resource_id, cust, category)}
    if key not in rows:
        raise HTTPException(status_code=404, detail="no such field")
    row = rows[key]
    if body.source not in ("database", "scraped", "manual"):
        raise HTTPException(status_code=422, detail="choose the database, the web page or enter it by hand")
    if body.source == "database" and not row["database"]:
        raise HTTPException(status_code=422, detail="the database has no value for this field")
    if body.source == "scraped" and not row["scraped"]:
        raise HTTPException(status_code=422, detail="the web page has no value for this field")
    manual = (body.manual or "").strip()
    if body.source == "manual":
        if not manual:
            raise HTTPException(status_code=422, detail=f"write the {row['label'].lower()}")
        problem = _valid_manual(key, manual)
        if problem:
            raise HTTPException(status_code=422, detail=problem)
    chosen_value = {"database": row["database"], "scraped": row["scraped"], "manual": manual}[body.source]
    with _db() as conn:
        domain = store.active_domains(conn, resource_id)[0]
        if body.source != "database":
            store.write_field_value(conn, resource_id, key, chosen_value)
        store.mark_chosen(conn, resource_id, domain, key, row["scraped"], CURRENT_USER)
    _log(resource_id, area="knowledge", target=key, action="confirmed",
         summary=f"{row['label']}: now uses the {body.source} value",
         before={"value": row["value"]}, after={"source": body.source, "value": chosen_value})
    updated = next(r for r in _knowledge_rows(resource_id, cust, category) if r["key"] == key)
    return {**updated, "database_differs": body.source == "manual" and bool(row["database"]) and
            _norm(row["database"]) != _norm(manual)}


@app.put("/api/c/{resource_id}/knowledge/{key}/choice")
def choose_value(resource_id: str, key: str, body: ChoiceIn) -> dict:
    return _do_choose(resource_id, key, body)


class ShareIn(BaseModel):
    enabled: bool


def _do_share(resource_id: str, key: str, body: ShareIn) -> dict:
    """Share a field with the chatbot, or keep it back (the field's switch)."""
    _customer(resource_id)
    if key not in KNOWLEDGE_LABELS:
        raise HTTPException(status_code=404, detail="no such field")
    label = KNOWLEDGE_LABELS[key]
    with _db() as conn:
        was = store.switches(conn, resource_id).get(key, "enable") == "enable"
        store.set_switch(conn, resource_id, key, "enable" if body.enabled else "disable")
    _log(resource_id, area="knowledge", target=key, action="shared" if body.enabled else "kept_back",
         summary=f"{label}: " + ("shared with the chatbot" if body.enabled else "not shared with the chatbot"),
         before={"shared": was}, after={"shared": body.enabled})
    return {"key": key, "enabled": body.enabled}


@app.put("/api/c/{resource_id}/knowledge/{key}")
def set_share(resource_id: str, key: str, body: ShareIn) -> dict:
    return _do_share(resource_id, key, body)


class CustomIn(BaseModel):
    key: str
    value: str


def _custom_items(resource_id: str) -> list[tuple[str, str]]:
    with _db() as conn:
        return [(k, v) for k, v in store.custom_fields(conn, resource_id)]


@app.get("/api/c/{resource_id}/custom-fields")
def custom_fields(resource_id: str) -> dict:
    _customer(resource_id)
    return {"fields": [{"key": k, "value": v} for k, v in _custom_items(resource_id)]}


def _do_custom(resource_id: str, body: CustomIn) -> dict:
    """Add a field the business has and the predefined list does not. Kept with the special fields."""
    _customer(resource_id)
    category, _ = _category(resource_id)
    key = " ".join(body.key.split())
    value = body.value.strip()
    if not 2 <= len(key) <= 40 or not re.match(r"^[A-Za-z0-9 ()'&/-]+$", key):
        raise HTTPException(status_code=422, detail="the name needs 2 to 40 letters or numbers")
    if not value:
        raise HTTPException(status_code=422, detail="write the value")
    if len(value) > 300:
        raise HTTPException(status_code=422, detail="the value is too long (300 characters at most)")
    predefined = _predefined_key(category, key)
    if predefined:
        raise HTTPException(status_code=422, detail=f'"{key}" is already a predefined field. '
                                                    f'Use "{KNOWLEDGE_LABELS[predefined]}" in Default fields instead.')
    saved = dict(_custom_items(resource_id))
    action = "updated" if key in saved else "added"
    previous = {"value": saved[key]} if key in saved else None
    with _db() as conn:
        store.save_special_field(conn, resource_id, key, value)
    _log(resource_id, area="custom_fields", target=key, action=action, summary=f"Custom field {action}: {key}",
         before=previous, after={"value": value})
    return {"fields": [{"key": k, "value": v} for k, v in _custom_items(resource_id)]}


@app.put("/api/c/{resource_id}/custom-fields")
def save_custom_field(resource_id: str, body: CustomIn) -> dict:
    return _do_custom(resource_id, body)


class KnowledgeBatch(BaseModel):
    """Everything changed in the Knowledge section, saved with its one Save button."""
    new_dishes: list[NewDishIn] = []
    dishes: dict[str, DishIn] = {}
    choices: dict[str, ChoiceIn] = {}
    share: dict[str, ShareIn] = {}
    custom_fields: list[CustomIn] = []
    chef: ChefSpecials | None = None


@app.put("/api/c/{resource_id}/knowledge-batch")
def save_knowledge_batch(resource_id: str, body: KnowledgeBatch) -> dict:
    """Apply every change in one transaction. If one part is refused, nothing is kept and no change is logged."""
    _customer(resource_id)
    batch_id = str(uuid4())
    token = BATCH_ID.set(batch_id)
    differs = []
    try:
        with connect() as conn:
            conn_token = CONN.set(conn)
            try:
                for dish in body.new_dishes:
                    _do_add_dish(resource_id, dish)
                for dish_id, dish in body.dishes.items():
                    _do_dish(resource_id, dish_id, dish)
                for key, choice in body.choices.items():
                    row = _do_choose(resource_id, key, choice)
                    if row["database_differs"]:
                        differs.append(row["label"])
                for key, share in body.share.items():
                    _do_share(resource_id, key, share)
                for field in body.custom_fields:
                    _do_custom(resource_id, field)
                if body.chef is not None:
                    set_chef_specials(resource_id, body.chef)
            finally:
                CONN.reset(conn_token)
            saved = conn.execute("SELECT count(*) FROM conv_change_log WHERE batch_id = %s", (batch_id,)).fetchone()[0]
            conn.commit()
            publish_customer(conn, redis_client(), resource_id)   # after the commit: the bundle matches the saved data
    finally:
        BATCH_ID.reset(token)
    return {"saved": True, "batch": batch_id, "changes": saved, "database_differs": differs}


# ---- admin: change log, the health check -------------------------------------------------------------------------

@app.get("/api/c/{resource_id}/playground")
def playground_facts(resource_id: str) -> dict:
    """What the chatbot can use right now (the shared values), and the widget's own setup."""
    customer = _customer(resource_id)
    category, cust = _category(resource_id)
    rows = _knowledge_rows(resource_id, cust, category)
    return {
        "facts": [{"label": r["label"], "value": r["value"]} for r in rows if r["value"] and r["enabled"]],
        "widget": {"title": customer["name"],
                   "teaser": category.get("teaser_text", "").replace("{customer_name}", customer["name"]),
                   "default_questions": category.get("default_questions", [])},
    }


class PlaygroundIn(BaseModel):
    message: str


@app.post("/api/c/{resource_id}/playground")
def playground(resource_id: str, body: PlaygroundIn) -> dict:
    """Try the real chat with a visitor question: the same pipeline the widget uses. The chat it makes is kept like any
    other test chat, under its own visit."""
    from pipeline.turn import handle_message
    _customer(resource_id)
    question = " ".join(body.message.split())
    if not 1 <= len(question) <= 300:
        raise HTTPException(status_code=422, detail="write a question of up to 300 characters")
    with _db() as conn:
        domain = store.active_domains(conn, resource_id)[0]
    session_id, activity_id = str(uuid4()), str(uuid4())
    with connect() as conn:
        outcome = handle_message(redis_client(), conn, session_id, "professional", resource_id, domain, text=question,
                                 consent=False, activity_id=activity_id)
        conn.commit()
    return {"answer": outcome.reply or "", "state": outcome.state, "session_id": session_id}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "data": "mock numbers"}
