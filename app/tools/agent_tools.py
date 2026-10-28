"""The tools the chat agent may call. The model chooses a tool; the code checks every value and does the work.

The tools offered to a business come from the category bundle: the conv_tool rows that the steps of the category's actions
name (pipeline/action_plan.py says which way each action is completed). The menu tools (search_menu, get_menu) are still
offered from here, to a business that has a menu.
Information tool (read only): get_business_info: a fact about the business, or one of its links (booking_link, ...).
Request tool: request_handoff opens the request form for an action in the widget (pipeline/forms.py). It saves nothing: the
visitor fills the form, and the code checks and saves it when they send it. The model writes nothing after it.

The business always comes from the bundles loaded for the chat, never from the model's arguments.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

import psycopg
import redis

from pipeline import forms
from pipeline.load_chat import session_key
from tools.business_tools import BUSINESS_FIELDS, call_tool, get_menu

LOOKUP_TOOLS = {"search_menu", "get_business_info"}
HANDOVER_REASONS = {"visitor_asked": "request_from_visitor", "not_on_record": "unavailable_answer",
                    "unsure": "unsure_question"}
GENERAL_CHOICE = "direct_handover"   # the general action the model may pick when no action of the business fits
MODEL_FIELD_KEYS = ("type", "description")   # what the model is told about a field; labels and formats are for the form


@dataclass
class AgentContext:
    client: redis.Redis
    conn: psycopg.Connection
    category: dict
    customer: dict
    session_id: str
    professional_id: str
    domain: str
    session: dict            # the chat's hash as it was at the start of this turn
    message: str             # the visitor's message for this turn
    now: datetime            # aware, UTC
    gaps: int = 0            # lookups that found nothing (the question may be one the business has to answer)
    tools_used: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)   # what the tools returned this turn: the evidence for the reply
    card: dict | None = None   # the request form the agent opened this turn

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.customer["timezone"])

    @property
    def today(self) -> date:
        return self.now.astimezone(self.zone).date()


def open_form(ctx: AgentContext, action_key: str, prefill=None, reason: str | None = None) -> dict:
    """Open the request form for an action. The visitor sees it in the widget; nothing is saved until they send it. The model
    may pick any action of the business, or direct_handover; the other general actions are opened by the code."""
    own = {a["key"] for a in ctx.category.get("actions") or []}
    form = None if action_key not in own | {GENERAL_CHOICE} else forms.form_for(ctx.category, ctx.customer, action_key, prefill if isinstance(prefill, dict) else None, ctx.today)
    if form is None:
        found = forms.resolve(ctx.category, ctx.customer, action_key)
        if found is not None and found[1]["route"] == "details":
            return {"ok": False, "error": "this action is completed with get_business_info (the link or the facts on record), "
                                          "not with a form"}
        return {"ok": False, "error": f"not an action of this business: {action_key}"}
    ctx.card = form
    ctx.client.hset(session_key(ctx.session_id), mapping={
        "handover_reason": HANDOVER_REASONS.get(reason or "", "request_from_visitor"),
        "handover_question": ctx.message})
    return {"ok": True, "form_opened": True, "request_type": form["request_type"]}


def _schema(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties or {}, "required": required or []}}


def _offered_names(category: dict) -> set[str]:
    """The tools the steps of the category's actions name."""
    return {name for action in category.get("actions") or [] for step in action["steps"] for name in step["tools"]}


def _for_model(spec):
    """A tool input as the model sees it: its type and its description (the form's labels and formats are not its business)."""
    if isinstance(spec, dict) and "properties" in spec:
        return {**{k: v for k, v in spec.items() if k in MODEL_FIELD_KEYS + ("enum",)},
                "properties": {k: _for_model(v) for k, v in spec["properties"].items()}, "type": "object"}
    return {k: v for k, v in spec.items() if k in MODEL_FIELD_KEYS + ("enum",)} if isinstance(spec, dict) else spec


def tool_schemas(category: dict, customer: dict) -> list[dict]:
    """The tools this business's chat may use: the conv_tool rows in the category bundle that the steps of its actions name
    (their descriptions and inputs come from the table), with the values only this business has filled in: the fields
    get_business_info may read, and the action keys. The menu tools are offered to a business that has a menu."""
    fields = sorted(set(BUSINESS_FIELDS) | set(customer.get("custom_fields") or {}))
    action_keys = [a["key"] for a in category.get("actions") or []] + (
        [GENERAL_CHOICE] if GENERAL_CHOICE in (category.get("general_actions") or {}) else [])
    offered = _offered_names(category)
    tools = []
    for row in category.get("tools") or []:
        if row["name"] not in offered:
            continue
        schema = json.loads(json.dumps(row["inputs"]))   # a copy: the values below are for this business only
        schema.setdefault("properties", {})
        schema.setdefault("required", [])
        props = schema["properties"]
        if row["name"] == "get_business_info" and "field" in props:
            props["field"]["enum"] = fields
        if row["name"] == "request_handoff" and "action_key" in props and action_keys:
            props["action_key"]["enum"] = action_keys
        schema["properties"] = {k: _for_model(v) for k, v in props.items()}
        tools.append({"name": row["name"], "description": row["description"], "input_schema": {"type": "object", **schema}})
    if customer.get("menu"):   # dishes and the menu are offered only where the business has a menu
        tools = [
            _schema("search_menu", "Find dishes by name, with price, chef's special and whether it is on offer now.",
                    {"query": {"type": "string", "description": "the dish or words the visitor used"}}, ["query"]),
            _schema("get_menu", "The whole menu, by section (dish names)."),
        ] + tools
    return tools


def _money(value):
    """Prices as text with two decimals (7.0 becomes "7.00"), everywhere in a tool result."""
    if isinstance(value, dict):
        return {k: (f"{v:.2f}" if k == "price" and isinstance(v, (int, float)) else _money(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_money(v) for v in value]
    return value


def run_tool(ctx: AgentContext, name: str, args: dict) -> dict:
    """Run one tool the model asked for. Bad arguments and errors come back as an error result, never a crash."""
    ctx.tools_used.append(name)
    args = args or {}
    try:
        result = _money(_run(ctx, name, args))
        if name in LOOKUP_TOOLS and isinstance(result, dict) and result.get("found") is False:
            ctx.gaps += 1
    except Exception as exc:  # the model reads the error and can try again
        result = {"ok": False, "error": f"the tool failed: {type(exc).__name__}"}
    ctx.results.append(result)   # what the reply may say comes from these (pipeline/verify.py)
    return result


def _run(ctx: AgentContext, name: str, args: dict) -> dict:
    """The tool's own work. Errors are caught by run_tool."""
    if name == "search_menu":
        return call_tool(ctx.category, ctx.customer, "search_menu", query=str(args.get("query", "")))
    if name == "get_menu":
        return get_menu(ctx.customer)
    if name == "get_business_info":
        return call_tool(ctx.category, ctx.customer, "get_business_info", field=str(args.get("field", "")))
    if name == "request_handoff":
        return open_form(ctx, str(args.get("action_key", "")), args.get("prefill"), args.get("reason"))
    return {"ok": False, "error": f"unknown tool: {name}"}
