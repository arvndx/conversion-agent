"""Build the category bundle and the professional's (customer) bundle from the conv_ tables.

The chat code reads the same shapes that shared/category_bundle.py and shared/customer_loader.py produce from the old
files. This module builds those shapes from the tables, so the chat reads the new schema.

Category bundle  <- conv_category_settings, conv_action (the steps of each action and its request_type), conv_tool (the tools
                    those steps name), conv_critical_reply, the general actions (conv_action, gcid general) and the fixed
                    replies (conv_static_reply: the shared "general" rows, replaced by the category's own row for an intent)
Customer bundle  <- conv_professional_settings (its links are fields in special_fields: booking_link, menu_link, ...),
                    conv_domains, conv_calendar_connection, professionals, organizations, exp_entitlements (local copies
                    of production)

Phone and email shown in the chat are the demo values in conv_professional_settings (public_phone, public_email), not the
production values.
"""

import datetime

import json

from pipeline.widget_settings import DEFAULT_STYLE
from shared.action_steps import extras_of, links_for_actions
from shared.category_bundle import GENERIC

# The lookups tools/business_tools.call_tool may run. The tools the agent is offered are the conv_tool rows in "tools" below.
ALLOWED_TOOLS = ["get_business_info", "search_menu"]
GENERAL = "general"   # the gcid of the actions and fixed replies every category shares


def load_category(conn, gcid: str) -> dict:
    s = conn.execute("""select welcome_message, teaser_text, never_ask, abuse_rules, scoring_rules, other_messages,
        handover_wait_seconds, idle_close_minutes, general_knowledge_allowed, guardrails_text, abuse_blocklist,
        abuse_allowlist, services, compliance_rules, prohibited_phrases, required_disclaimers, content_restrictions
        from conv_category_settings where gcid = %s""", (gcid,)).fetchone()
    if s is None:
        raise KeyError(f"no category settings for {gcid}")
    (welcome, teaser, never_ask, abuse, scoring, messages, wait, idle, general, guardrails, blocklist, allowlist,
     services, compliance_rules, prohibited, disclaimers, restrictions) = s
    actions = [dict(zip(["action_key", "action_name", "agent_goal", "profile_button", "steps", "request_type"], r))
               for r in conn.execute(
        """select action_key, action_name, agent_goal, profile_button, steps, request_type
           from conv_action where gcid = %s and enabled order by action_key""", (gcid,)).fetchall()]
    step_actions = [{"key": a["action_key"], "name": a["action_name"], "goal": a["agent_goal"] or a["action_name"],
                     "button": a["profile_button"], "steps": a["steps"], "request_type": a["request_type"]}
                    for a in actions if a["steps"]]
    critical = [{"id": r[0], "description": r[1], "examples": r[2], "reply": r[3], "action": r[4]} for r in conn.execute(
        "select topic_id, description, examples, reply, action from conv_critical_reply where gcid = %s order by topic_id",
        (gcid,)).fetchall()]
    # The actions that can go to a link, details or a booking come first; the handover-only actions follow. Five at most.
    ordered = sorted((a for a in actions if a["steps"]), key=lambda a: a["steps"][0]["route"] == "handover")
    default_questions = [a["profile_button"] or a["action_name"] for a in ordered][:5] or ["Contact us"]
    quick_actions = [{"key": a["action_key"], "label": a["profile_button"] or a["action_name"]} for a in ordered][:5]
    return {
        "bundle_type": "category", "category_id": gcid.split(":", 1)[1], "gcid": gcid,
        "note": "Built from the conv_ tables.",
        "default_questions": default_questions,
        "quick_actions": quick_actions,   # the buttons under the chat: the key goes back with a click, no model is called
        "critical_topics": critical,
        "general_knowledge_allowed": general,
        "handover_triggers": GENERIC["handover_triggers"],
        "handover_extra_fields": [],
        "never_ask": never_ask,
        "guardrails_text": guardrails or None,
        "teaser_text": teaser,
        "message_texts": dict(messages),
        "abuse_check": {"method": "profanity_library", "library": "better-profanity",
                        "blocklist": blocklist or [], "allowlist": allowlist or []},
        "abuse_rules": abuse,
        "scoring_rules": scoring,
        "idle_close_minutes": idle,
        "defaults": {"slot_minutes": 15, "bookings_per_slot": 4},
        "allowed_tools": ALLOWED_TOOLS,
        "actions": step_actions,   # each enabled action: key, name, goal, button, steps, request_type
        "general_actions": load_general_actions(conn),   # the handovers no business button starts (critical, AI down, ...)
        "static_replies": load_static_replies(conn, gcid),   # {intent: {"patterns", "replies"}}
        "tools": load_tools(conn, step_actions),   # the conv_tool rows the steps name, with the category's extra inputs
        "compliance": {"prohibited_phrases": prohibited or [], "required_disclaimers": disclaimers or [],
                       "content_restrictions": restrictions or []},
        "compliance_rules": compliance_rules or [],
        "services": services or [],
    }


def load_general_actions(conn) -> dict[str, dict]:
    """The enabled actions every category shares (gcid general): {action_key: {key, name, goal, steps, request_type}}."""
    return {k: {"key": k, "name": name, "goal": goal, "steps": steps, "request_type": request_type}
            for k, name, goal, steps, request_type in conn.execute(
                """select action_key, action_name, agent_goal, steps, request_type from conv_action
                   where gcid = %s and enabled and steps is not null order by action_key""", (GENERAL,)).fetchall()}


def load_static_replies(conn, gcid: str) -> dict[str, dict]:
    """The fixed replies for this category: the shared rows, with the category's own row replacing one for the same intent."""
    merged = {}
    for intent, patterns, replies in conn.execute(
            """select intent, patterns, replies from conv_static_reply where gcid in (%s, %s)
               order by (gcid = %s) desc""", (GENERAL, gcid, GENERAL)).fetchall():   # the shared rows first, then the category's
        merged[intent] = {"patterns": list(patterns), "replies": list(replies)}
    return merged


def load_tools(conn, actions: list[dict]) -> list[dict]:
    """The enabled conv_tool rows that the steps of these actions name: {name, description, inputs}. The extra fields a step
    collects ({"key", "type", "description"}) are added as inputs to the last tool of that step, the one that does the work
    (book in a booking step, request_handoff in a handover step); standard fields (name, phone, ...) are already inputs."""
    named: list[str] = []
    extras: dict[str, dict[str, dict]] = {}
    for action in actions:
        for step in action["steps"]:
            for name in step.get("tools") or []:
                if name not in named:
                    named.append(name)
            if step.get("tools"):
                for extra in extras_of(step):
                    extras.setdefault(step["tools"][-1], {})[extra["key"]] = {"type": extra["type"],
                                                                              "description": extra["description"]}
    if not named:
        return []
    rows = {name: (description, inputs) for name, description, inputs in conn.execute(
        "select name, description, inputs from conv_tool where enabled and name = any(%s)", (named,)).fetchall()}
    tools = []
    for name in named:
        if name not in rows:
            continue
        description, inputs = rows[name]
        inputs = json.loads(json.dumps(inputs))   # a copy: the extras are added to this bundle's tool only
        inputs.setdefault("properties", {}).update(extras.get(name, {}))
        tools.append({"name": name, "description": description, "inputs": inputs})
    return tools


def load_menu(conn, professional_id: str) -> tuple[dict, list[str], str | None]:
    """The professional's dishes grouped by section, the chef's specials, and the menu link (the view_menu action's link)."""
    rows = conn.execute("""select m.name, m.section, pm.price, pm.chef_special, pm.availability
        from conv_menu m join conv_professional_menu pm on pm.menu_id = m.menu_id
        where pm.professional_id = %s order by m.section, m.name""", (professional_id,)).fetchall()
    menu: dict[str, list[dict]] = {}
    specials = []
    for name, section, price, chef, availability in rows:
        menu.setdefault(section, []).append({"name": name, "price": float(price) if price is not None else None,
                                             "chef_special": bool(chef), "availability": availability or {}})
        if chef:
            specials.append(name)
    link = conn.execute("select special_fields->>'menu_link' from conv_professional_settings where professional_id = %s",
                        (professional_id,)).fetchone()
    return menu, specials, (link[0] if link and link[0] else None)


def load_customer(conn, professional_id: str) -> dict:
    s = conn.execute("""select p.gcid, p.first_name, p.last_name, p.address_city, p.address_state, p.address_zip,
        p.primary_org_id, o.address_street, s.timezone, s.opening_hours, s.services, s.special_fields, s.display_switches,
        s.kill_switch, s.hot_visitor_threshold, s.slot_minutes, s.bookings_per_slot, s.booking_enabled,
        s.handover_extra_fields, s.public_phone, s.public_email, s.availability, s.current_offers, s.response_hours
        from conv_professional_settings s join professionals p on p.id = s.professional_id
        left join organizations o on o.id = p.primary_org_id
        where s.professional_id = %s""", (professional_id,)).fetchone()
    if s is None:
        raise KeyError(f"no settings for professional {professional_id}")
    (gcid, first, last, city, state, zip_code, org_id, street, tz, hours, services, special, switches, kill,
     threshold, slot, per_slot, booking, extra, phone, email, availability, offers, response_hours) = s
    sites = conn.execute("select domain, primary_color, accent_color from conv_domains where professional_id = %s and status = 'active' "
                         "order by domain", (professional_id,)).fetchall()
    domains = [r[0] for r in sites]
    theme = {d: {"primary": primary or DEFAULT_STYLE["primary"], "accent": accent or DEFAULT_STYLE["accent"]} for d, primary, accent in sites}
    category_actions = [{"key": k, "steps": steps} for k, steps in conn.execute(
        "select action_key, steps from conv_action where gcid = %s and enabled and steps is not null", (gcid,)).fetchall()]
    links = links_for_actions(category_actions, special or {})   # {action_key: url}, from the link fields in special_fields
    menu, specials, menu_url = load_menu(conn, professional_id)
    cal = conn.execute("select status from conv_calendar_connection where professional_id = %s", (professional_id,)).fetchone()
    ent = conn.execute("""select 1 from exp_entitlements where subject_type = 'organization' and subject_id = %s
        and product_key = 'conversion_agent' and state = 'active' and (expires_at is null or expires_at > now())""",
                       (str(org_id),)).fetchone() if org_id else None
    address = ", ".join(x for x in [street, city, state, zip_code] if x) if street else ", ".join(x for x in [city, state, zip_code] if x)
    switches = switches or {}
    return {
        "bundle_type": "customer", "resource_id": str(professional_id), "resource_type": "professional",
        "category_id": gcid.split(":", 1)[1], "gcid": gcid,
        "display_name": {"first_name": first or "", "last_name": last or ""},
        "public_contact": {"phone": phone or "", "email": email or ""},
        "primary_location": address,
        "service_area": address,
        "timezone": tz,
        "business_hours": hours or {},
        "weblink": "",
        "links": links,
        "menu": menu,
        "custom_fields": dict(special or {}),   # the business's own fields (name: value), added from the insights
        "offers": offers or [],
        "response_hours": response_hours or {},
        "services": services or [],
        "licences": None,
        "parking": (special or {}).get("parking"),
        "chef": {"specials": specials, "menu_url": menu_url},
        "chat_contact": {"phone": switches.get("phone") == "enable", "email": switches.get("email") == "enable"},
        "page_tracking": switches.get("page_tracking") == "enable",   # the widget may send page activity
        "theme": theme,   # the widget colours of each active domain: {domain: {"primary", "accent"}}
        "current_offers": [],
        "scoring_threshold": threshold,
        "slot_minutes": slot,
        "bookings_per_slot": per_slot,
        "booking_enabled": booking,
        "availability": availability or {},
        "google_calendar_connected": bool(cal and cal[0] == "connected"),
        "enabled": ent is not None and kill != "stop_everything",
        "kill_switch": kill,
        "allowed_domains": domains,
        "handover_extra_fields": extra or [],
        "site_key": None,
    }
