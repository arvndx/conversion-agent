"""The chat API (A82): the widget's way into the pipeline. It runs as its own process.

Endpoints:
  POST /chat/message  a visitor's message, or a click on a quick question (action_key). Returns the reply if the quiet period
                      has passed, or "waiting". A reply may carry a card: the request form to show.
  POST /chat/form     the visitor sent the request form. No model is called: the values are checked, the request is saved and
                      confirmed in the table, and the reply says so. Wrong values come back as errors by field.
  POST /chat/poll     asks whether the waiting turn is ready (the widget calls this every second while waiting).
  POST /chat/close    the visitor closed the widget (A79 b).
  block_token         sent back by the widget on every request, once the browser is blocked (A73, A83).
  GET  /health        a check that the API is up.

The site key identifies one site (one domain of a business, A40). The domain sent must be that site's domain; the
pipeline checks the business's allowed domains at every turn (step 0). A new chat gets its session ID from the server.
"""

import os
import time
import uuid

import psycopg
import redis
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from pipeline.close_chat import close_by_visitor
from pipeline.load_chat import DATABASE_URL, REDIS_URL, connect, load_bundles, session_key
from pipeline.site_bundles import ensure_bundles, publish_category, publish_customer, site_location
from shared.bundles import customer_key
from pipeline.activity import record_activity
from pipeline.turn import TurnOutcome, fill, handle_form, handle_message
from pipeline.widget_settings import DEFAULT_STYLE

FEEDBACK_REASONS = {"Wrong answer": "wrong_answer", "Did not answer my question": "did_not_answer",
                    "Too long": "too_long", "Hard to understand": "hard_to_understand", "Other": "other"}

# The test sites: the demo sites, and the business pages (one port per test business, 8101 to 8108).
TEST_SITE_ORIGINS = ["http://localhost:8001", "http://localhost:8002"] + [f"http://localhost:{port}" for port in range(8101, 8109)]


def _as_uuid(value: str | None) -> str | None:
    # The database stores these as uuids, so a value that is not one would fail the whole batch (A81).
    if value in (None, ""):
        return value
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError("must be a uuid")


class FeedbackIn(BaseModel):
    site_key: str
    domain: str
    session_id: str | None = None
    rating: str                       # "up" or "down"
    reason: str | None = None         # one of the reply reasons, when down
    reason_note: str | None = None    # the visitor's words, when the reason is Other
    reply: str
    question: str | None = None

    _uuids = field_validator("session_id")(_as_uuid)


REPLY_REASONS = ["Wrong answer", "Did not answer my question", "Too long", "Hard to understand", "Other"]


class ActivityIn(BaseModel):
    site_key: str
    domain: str
    activity_id: str
    events: list[dict] = []

    _uuids = field_validator("activity_id")(_as_uuid)


class MessageIn(BaseModel):
    site_key: str
    domain: str
    text: str
    msg_id: str | None = None
    session_id: str | None = None
    consent: bool = True
    visitor_id: str | None = None
    location: str | None = None
    activity_id: str | None = None
    block_token: str | None = None
    action_key: str | None = None   # set when the visitor clicked a quick question; text is then the button's label

    _uuids = field_validator("session_id", "visitor_id", "activity_id")(_as_uuid)


class FormIn(BaseModel):
    site_key: str
    domain: str
    session_id: str
    action_key: str
    values: dict = {}
    consent: bool = True
    visitor_id: str | None = None
    location: str | None = None
    activity_id: str | None = None
    block_token: str | None = None

    _uuids = field_validator("session_id", "visitor_id", "activity_id")(_as_uuid)


class PollIn(BaseModel):
    site_key: str
    domain: str
    session_id: str
    block_token: str | None = None

    _uuids = field_validator("session_id")(_as_uuid)


class CloseIn(BaseModel):
    site_key: str
    domain: str
    session_id: str

    _uuids = field_validator("session_id")(_as_uuid)


CHAT_UNAVAILABLE = "This chat isn't available right now."
FORM_SITE_LIMIT = 60      # request forms one site may send in a minute
BUSY_TEXT = "Too many requests right now. Please try again in a minute."


def _reply(session_id: str, outcome: TurnOutcome) -> dict:
    # A refused turn, or a block, shows the visitor the same fixed text. The reason stays on the server.
    reply = CHAT_UNAVAILABLE if outcome.state in ("stopped", "blocked") else outcome.reply
    return {
        "session_id": session_id,
        "state": outcome.state,
        "reply": reply,
        "block_token": outcome.block_token,
        "card": outcome.card,
        "errors": outcome.errors,
    }


def create_app(redis_client: redis.Redis | None = None, connect_fn=None, origins: list[str] | None = None) -> FastAPI:
    r = redis_client or redis.Redis.from_url(REDIS_URL, decode_responses=True)
    open_connection = connect_fn or (lambda: psycopg.connect(DATABASE_URL))
    app = FastAPI(title="Conversion Agent chat API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins is not None else TEST_SITE_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def site_for(conn, site_key: str) -> tuple[str, str]:
        # The site key names one professional and one domain: read from Redis (the tables only when the map has no entry).
        site = site_location(conn, r, site_key)
        if site is None or site["status"] != "active":
            raise HTTPException(status_code=404, detail="unknown site key")
        return site["professional_id"], site["domain"]

    def location_for(conn, site_key: str) -> tuple[str, str, str]:
        professional_id, domain = site_for(conn, site_key)
        ensure_bundles(conn, r, professional_id)   # built once, then kept until a change to the data clears them
        return "professional", professional_id, domain

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    class RebuildIn(BaseModel):
        professional_id: str | None = None
        category: str | None = None   # the category, as a gcid (gcid:american_restaurant) or without the gcid: prefix

    @app.post("/bundles/rebuild")
    def rebuild(body: RebuildIn, x_bundle_token: str | None = Header(default=None)) -> dict:
        """Build a new version of a business's customer bundle, and/or of a category bundle, from the tables. Called by
        hand after a change made straight in the tables. New chats use the new version; running chats finish on theirs.
        When the BUNDLE_API_TOKEN setting is set, the request must send it in the X-Bundle-Token header."""
        token = os.environ.get("BUNDLE_API_TOKEN")
        if token and x_bundle_token != token:
            raise HTTPException(status_code=401, detail="bundle token missing or wrong")
        if not (body.professional_id or body.category):
            raise HTTPException(status_code=422, detail="give a professional_id, a category, or both")
        result = {}
        with open_connection() as conn:
            if body.professional_id:
                try:
                    uuid.UUID(body.professional_id)
                except ValueError:
                    raise HTTPException(status_code=422, detail="professional_id is not an id")
                result["customer_version"] = publish_customer(conn, r, body.professional_id)
            if body.category:
                gcid = body.category if body.category.startswith("gcid:") else f"gcid:{body.category}"
                if conn.execute("select 1 from conv_category_settings where gcid = %s", (gcid,)).fetchone() is None:
                    raise HTTPException(status_code=422, detail=f"no such category: {gcid}")
                result["category_version"] = publish_category(conn, r, gcid)
            conn.commit()
        return result

    @app.get("/chat/config")
    def config(site_key: str, domain: str) -> dict:
        # What the widget shows before a chat: the teaser, the title and the default questions (A84). From the bundles,
        # so the widget needs no text of its own. A domain that is not allowed gets nothing.
        with open_connection() as conn:
            resource_type, resource_id, site_domain = location_for(conn, site_key)
            if domain != site_domain:
                raise HTTPException(status_code=403, detail="domain not allowed")
        bundles = load_bundles(r, resource_type, resource_id)
        customer, category = bundles.customer, bundles.category
        if domain not in customer.get("allowed_domains", []):
            raise HTTPException(status_code=403, detail="domain not allowed")
        theme = (customer.get("theme") or {}).get(domain) or {"primary": DEFAULT_STYLE["primary"], "accent": DEFAULT_STYLE["accent"]}
        enabled = bool(customer.get("enabled")) and customer.get("kill_switch") == "none"
        return {
            "enabled": enabled,
            "title": fill("{customer_name}", customer, category),
            "teaser": fill(category["teaser_text"], customer, category),
            "default_questions": category.get("default_questions", []),
            "quick_actions": category.get("quick_actions", []),
            "theme": theme,
        }

    @app.post("/chat/feedback")
    def feedback(body: FeedbackIn) -> dict:
        # A thumbs up or down on one reply. Kept with no expiry (conv_reply_feedback).
        if body.rating not in ("up", "down"):
            raise HTTPException(status_code=422, detail="the rating is up or down")
        reason = FEEDBACK_REASONS.get(body.reason) if body.rating == "down" else None
        if body.rating == "down" and reason is None and body.reason:
            reason = "other"
        with open_connection() as conn:
            professional_id, site_domain = site_for(conn, body.site_key)
            if body.domain != site_domain:
                return {"saved": False}
            session = body.session_id if body.session_id and conn.execute(
                "SELECT 1 FROM conv_session WHERE session_id = %s", (body.session_id,)).fetchone() else None
            topic = conn.execute("SELECT topic FROM conv_session WHERE session_id = %s", (session,)).fetchone()[0] \
                if session else None
            conn.execute(
                "INSERT INTO conv_reply_feedback (professional_id, domain, session_id, rating, reason, reason_note, topic, question, reply) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (professional_id, site_domain, session, body.rating, reason,
                 (body.reason_note or "")[:300] or None if reason == "other" else None,
                 topic, (body.question or "")[:500] or None, body.reply[:2000]),
            )
            conn.commit()
        return {"saved": True}

    @app.post("/activity")
    def activity(body: ActivityIn) -> dict:
        # The widget's page activity. Stored only where the professional has page tracking switched on.
        with open_connection() as conn:
            professional_id, site_domain = site_for(conn, body.site_key)
            ensure_bundles(conn, r, professional_id)
            tracking = load_bundles(r, "professional", professional_id).customer.get("page_tracking")   # from the bundle
            if body.domain != site_domain or not tracking:
                return {"visit": "not_tracked"}
            result = record_activity(conn, professional_id, body.domain, body.activity_id, body.events)
            conn.commit()
        return {"visit": result}

    @app.post("/chat/message")
    def message(body: MessageIn) -> dict:
        session_id = body.session_id or str(uuid.uuid4())
        with open_connection() as conn:
            resource_type, resource_id, site_domain = location_for(conn, body.site_key)
            if body.domain != site_domain:
                return _reply(session_id, TurnOutcome(state="stopped"))
            outcome = handle_message(
                r, conn, session_id, resource_type, resource_id, body.domain,
                text=body.text, msg_id=body.msg_id, consent=body.consent,
                visitor_id=body.visitor_id or "", location=body.location or "",
                activity_id=body.activity_id or "",
                block_token=body.block_token, action_key=body.action_key,
            )
            conn.commit()
        return _reply(session_id, outcome)

    @app.post("/chat/form")
    def form(body: FormIn) -> dict:
        # The request form, sent by the visitor. A site may send only so many a minute, so a script cannot flood a business.
        with open_connection() as conn:
            resource_type, resource_id, site_domain = location_for(conn, body.site_key)
            if body.domain != site_domain:
                return _reply(body.session_id, TurnOutcome(state="stopped"))
            window = f"form_rate:{body.site_key}:{int(time.time() // 60)}"
            if r.incr(window) > FORM_SITE_LIMIT:
                r.expire(window, 120)
                return _reply(body.session_id, TurnOutcome(state="reply", reply=BUSY_TEXT))
            r.expire(window, 120)
            outcome = handle_form(
                r, conn, open_connection, body.session_id, resource_type, resource_id, body.domain, body.action_key,
                body.values, consent=body.consent, visitor_id=body.visitor_id or "", location=body.location or "",
                activity_id=body.activity_id or "", block_token=body.block_token,
            )
            conn.commit()
        return _reply(body.session_id, outcome)

    @app.post("/chat/poll")
    def poll(body: PollIn) -> dict:
        with open_connection() as conn:
            resource_type, resource_id, site_domain = location_for(conn, body.site_key)
            if body.domain != site_domain:
                return _reply(body.session_id, TurnOutcome(state="stopped"))
            outcome = handle_message(
                r, conn, body.session_id, resource_type, resource_id, body.domain,
                block_token=body.block_token,
            )
            conn.commit()
        return _reply(body.session_id, outcome)

    @app.post("/chat/close")
    def close(body: CloseIn) -> dict:
        session = r.hgetall(session_key(body.session_id))
        if not session:
            raise HTTPException(status_code=404, detail="unknown chat")
        if session.get("domain") != body.domain:
            raise HTTPException(status_code=403, detail="chat belongs to another domain")
        closed = close_by_visitor(r, body.session_id)
        return {"session_id": body.session_id, "closed": closed}

    return app


app = create_app()
