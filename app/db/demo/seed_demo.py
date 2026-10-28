"""Build the local demo database for the conversion agent, from scratch.

What it does, in order (into an EMPTY local database):
  1. applies db/conv_schema.sql (the conv_ tables and the copies of the production tables)
  2. copies the rows of the five categories from production (read only): categories, compliance, offices,
     professionals and their entitlements. Only the needed columns are copied, and only the rows of these categories.
  3. loads the demo inputs: actions (with the tools and the steps of each action, from db/demo/tool_data.json), category
     settings, critical replies, demo customers (professionals), their domains, links, menu and the entitlement rows
  4. loads the demo outputs: one visit, chat, handover, booking, hot visitor, question, daily totals, feedback, log

Usage (run from the app folder):
  LOCAL_DATABASE_URL=postgresql://localhost:5432/conv_demo \
  PLATFORM_READ_URL=postgresql://<read-only role>@<production host>/postgres \
  .venv/bin/python -m db.demo.seed_demo

Nothing is written to production. The local database must not hold any conv_ tables yet.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from db.demo.seed_actions import load as load_tools_and_actions
from db.demo.seed_static import load as load_static_replies
from db.demo.seed_links import demo_links, set_links
from shared.category_bundle import build_category_bundle, GENERIC
from shared.site_keys import new_site_key
from shared.tool_checks import check_database

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE.parent / "conv_schema.sql"
CATEGORIES = {
    "gcid:mortgage_lender": "mortgage_lender",
    "gcid:mortgage_broker": "mortgage_broker",
    "gcid:health_insurance_agency": "health_insurance_agency",
    "gcid:commercial_real_estate_agency": "commercial_real_estate_agency",
    "gcid:american_restaurant": "restaurant",
}
SOURCE = {g: ("location" if g in ("gcid:commercial_real_estate_agency", "gcid:american_restaurant") else "professional")
          for g in CATEGORIES}
PRODUCTION_TABLES = {
    "exp_category_knowledge": ["id", "gcid", "entity_type", "pricing_tier", "status", "exclusion_reason", "services",
                               "compliance_rules", "expertise_signals", "ai_agents", "created_at", "updated_at",
                               "conversion_actions"],
    "exp_category_compliance": ["gcid", "display_license_on_email", "license_display_format", "license_label",
                                "required_disclaimers", "content_restrictions", "prohibited_phrases",
                                "required_disclosures", "created_at", "updated_at"],
    "exp_entitlements": None,
    "exp_entity": None,
    "organizations": None,
    "professionals": None,
}
DEMO_SETTINGS_DEFAULTS = {"slot_minutes": 15, "bookings_per_slot": 4, "hot_visitor_threshold": 60}
DEMO = [
    dict(key="lender", gcid="gcid:mortgage_lender", org="Demo Lending Co - Main Office", first="Demo", last="Loan Officer",
         booking=True, tz="America/Chicago", offers=["Free first consultation"], notify=["email"],
         domains=["demo-lender-1.example", "demo-lender-2.example"]),
    dict(key="broker", gcid="gcid:mortgage_broker", existing="22222222-0000-4000-8000-000000000001", booking=False,
         tz="America/Denver", offers=[], notify=["email"], domains=["broker-demo-1.example", "broker-demo-2.example"]),
    dict(key="health", gcid="gcid:health_insurance_agency", org="Demo Health Plans - Main Office", first="Demo",
         last="Health Agent", booking=True, tz="America/New_York", offers=[], notify=["email"],
         domains=["demo-health-1.example", "demo-health-2.example"]),
    dict(key="cre", gcid="gcid:commercial_real_estate_agency", org="Demo Commercial Realty - Main Office", first="Demo",
         last="Commercial Agent", booking=False, tz="America/Los_Angeles", offers=[], notify=["email"],
         domains=["demo-commercial-1.example", "demo-commercial-2.example"]),
    dict(key="diner", gcid="gcid:american_restaurant", org="Demo Diner - Main", first="Demo", last="Chef Owner",
         booking=True, tz="America/Chicago", offers=[], notify=["email", "phone"],
         domains=["demo-diner-1.example", "demo-diner-2.example"]),
]
DISHES = [("Smash Burger", "Mains", 11.50, True), ("Chicken Sandwich", "Mains", 10.00, False),
          ("Caesar Salad", "Starters", 7.00, False), ("Onion Rings", "Starters", 4.50, False),
          ("Milkshake", "Desserts", 5.50, True), ("Apple Pie", "Desserts", 4.00, False)]
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
EXTRA_NEVER = ["social security number", "bank account number", "income", "credit score"]
DIALOGUE_MESSAGES = {
    "ask_day": "Which day would you like? For example 2026-10-28.",
    "ask_day_retry": "I did not catch the day. Please give a date such as 2026-10-28.",
    "no_free_times": "There are no free times on that day. Which other day would you like?",
    "pick_time": "These times are free: {times}. Which one would you like?",
    "ask_time_retry": "Please pick one of the times: {times}.",
    "ask_extra": "Please tell me the {field}.",
    "ask_booking_name": "What name should the booking be under?",
    "ask_booking_contact": "What email address or phone number can we reach you on?",
    "booking_contact_retry": "Please give an email address or a phone number.",
    "slot_full": "That time has just filled up.",
    "booking_confirmed": "Your booking is confirmed for {when}.",
    "handover_question_prompt": "Before I pass this on, could you explain your query?",
    "critical_handover_follow": "Would you like to share your name, an email or phone number, and your query so the team can contact you?",
    "handover_reply": "I'll pass this to the team, and they will contact you soon.",
    "ask_name_retry": "A first name or a nickname is enough. What name should I use?",
    "handover_name_declined": "No problem. I can't pass your details on without a name{contact}. What else can I help you with?",
    "handover_not_saved": "I couldn't pass that on just now, so nothing was sent. Please try again in a moment. What else can I help you with?",
}


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "conversion-agent-demo:" + name))


def copy_production(local, platform_url: str) -> None:
    """Step 2: the needed rows and columns of the six production tables, read only."""
    platform = psycopg.connect(platform_url, connect_timeout=15,
                               options="-c default_transaction_read_only=on -c statement_timeout=120000")
    gcids = list(CATEGORIES)
    org_ids = {r[0] for r in platform.execute("select id::text from organizations where gcid = any(%s)", (gcids,)).fetchall()}
    prof_ids = {r[0] for r in platform.execute("select id::text from professionals where gcid = any(%s)", (gcids,)).fetchall()}
    frontier = set(org_ids)
    while frontier:
        parents = {r[0] for r in platform.execute(
            "select parent_org_id::text from organizations where id::text = any(%s) and parent_org_id is not null",
            (list(frontier),)).fetchall()} - org_ids
        org_ids |= parents
        frontier = parents
    selections = {
        "exp_category_knowledge": ("gcid = any(%s)", [gcids]),
        "exp_category_compliance": ("gcid = any(%s)", [gcids]),
        "exp_entitlements": ("subject_id = any(%s)", [sorted(org_ids)]),
        "exp_entity": ("identity_keys->>'organization_id' = any(%s) or identity_keys->>'professional_id' = any(%s)",
                       [sorted(org_ids), sorted(prof_ids)]),
        "organizations": ("id::text = any(%s)", [sorted(org_ids)]),
        "professionals": ("id::text = any(%s)", [sorted(prof_ids)]),
    }
    for table, wanted in PRODUCTION_TABLES.items():
        cols = [r[0] for r in platform.execute(
            "select a.attname from pg_attribute a where a.attrelid = %s::regclass and a.attnum > 0 and not a.attisdropped "
            "and a.attgenerated = '' order by a.attnum", (f"public.{table}",)).fetchall()]
        cols = [c for c in cols if wanted is None or c in wanted]
        defs = [r for r in platform.execute(
            "select a.attname, format_type(a.atttypid, a.atttypmod) from pg_attribute a where a.attrelid = %s::regclass "
            "and a.attname = any(%s) order by a.attnum", (f"public.{table}", cols)).fetchall()]
        local.execute(sql.SQL("drop table if exists public.{t} cascade").format(t=sql.Identifier(table)))
        local.execute(sql.SQL("create table public.{t} ({d})").format(
            t=sql.Identifier(table), d=sql.SQL(", ").join(sql.SQL("{} {}").format(sql.Identifier(n), sql.SQL(t)) for n, t in defs)))
        where, params = selections[table]
        col_list = sql.SQL(", ").join(sql.Identifier(n) for n, _ in defs)
        export = sql.SQL("copy (select {c} from public.{t} where {w}) to stdout").format(
            c=col_list, t=sql.Identifier(table), w=sql.SQL(where))
        load = sql.SQL("copy public.{t} ({c}) from stdin").format(t=sql.Identifier(table), c=col_list)
        with platform.cursor().copy(export, params) as src, local.cursor().copy(load) as dst:
            for chunk in src:
                dst.write(chunk)
        print(f"  {table}: {local.execute(sql.SQL('select count(*) from public.{t}').format(t=sql.Identifier(table))).fetchone()[0]} rows")
    local.commit()
    platform.close()


def load_inputs(conn) -> None:
    """Step 3: the demo inputs."""
    cats = {}
    services_by_gcid = {}
    for gcid, slug in CATEGORIES.items():
        entity = SOURCE[gcid]
        rows = conn.execute("select a from exp_category_knowledge k, jsonb_array_elements(k.conversion_actions) a "
                            "where k.gcid = %s and k.entity_type = %s", (gcid, entity)).fetchall()
        for (a,) in rows:
            schema = a.get("schema_action") or ""
            conn.execute("""insert into conv_action (gcid, action_key, source_entity_type, action_name, schema_action,
                agent_goal, profile_button) values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (gcid, action_key) do nothing""",
                         (gcid, a["key"], entity, a.get("label") or a["key"], schema, a.get("agent_goal"), a.get("profile_button")))
        bundle = build_category_bundle(slug) if slug != "restaurant" else None
        if bundle:
            msgs, teaser, never = bundle["message_texts"], bundle["teaser_text"], bundle["never_ask"]
            abuse, scoring, critical = bundle["abuse_rules"], bundle["scoring_rules"], bundle["critical_topics"]
        else:
            msgs, teaser = dict(GENERIC["message_texts"]), GENERIC["teaser_text"]
            never = GENERIC["never_ask"] + EXTRA_NEVER
            abuse, scoring, critical = GENERIC["abuse_rules"], GENERIC["scoring_rules"], GENERIC["critical_topics"]
        services_row = conn.execute("select services, compliance_rules from exp_category_knowledge where gcid = %s and entity_type = %s",
                                    (gcid, entity)).fetchone()
        comp = conn.execute("select prohibited_phrases, required_disclaimers, content_restrictions from exp_category_compliance "
                            "where gcid = %s", (gcid,)).fetchone()
        services = [s if isinstance(s, str) else s.get("name", "") for s in (services_row[0] or [])] if services_row else []
        services_by_gcid[gcid] = services
        other = {**msgs, **DIALOGUE_MESSAGES}
        special = ([{"key": "parking", "description": "Whether guests can park at the business.", "value_type": "choice",
                     "allowed": ["available", "not_available"]}] if gcid == "gcid:american_restaurant" else [])
        conn.execute("""insert into conv_category_settings (gcid, welcome_message, teaser_text, never_ask, abuse_rules,
            scoring_rules, special_field_definitions, other_messages, handover_wait_seconds, idle_close_minutes,
            general_knowledge_allowed, services, compliance_rules, prohibited_phrases, required_disclaimers,
            content_restrictions, updated_by) values (%s, %s, %s, %s, %s, %s, %s, %s, 300, 10, false, %s, %s, %s, %s, %s, 'demo')
            on conflict (gcid) do nothing""",
                     (gcid, "I'm an AI assistant. How can I help you?", teaser, never, Jsonb(abuse), Jsonb(scoring),
                      Jsonb(special), Jsonb(other), services, (services_row[1] or []) if services_row else [],
                      comp[0] or [], comp[1] or [], comp[2] or []))
        for t in critical:
            conn.execute("""insert into conv_critical_reply (gcid, topic_id, description, examples, reply, action)
                values (%s, %s, %s, %s, %s, %s) on conflict do nothing""",
                         (gcid, t["id"], t["description"], Jsonb(t.get("examples", [])), t["reply"], t.get("action", "handover")))
        cats[gcid] = True
    load_tools_and_actions(conn)   # the tools and the steps of the actions (db/demo/tool_data.json)
    load_static_replies(conn)   # the fixed replies and the request form messages (db/demo/static_data.json)
    for d in DEMO:
        if d.get("existing"):
            pid = d["existing"]
        else:
            pid, org = uid("pro-" + d["key"]), uid("org-" + d["key"])
            conn.execute("""insert into organizations (id, name, slug, gcid, entity_type, is_demo, is_active, address_street,
                address_city, address_state) values (%s, %s, %s, %s, 'office', true, true, '100 Demo Street', 'Demo City', 'IL')""", (org, d["org"], "demo-" + d["key"] + "-office", d["gcid"]))
            conn.execute("""insert into professionals (id, first_name, last_name, display_name, slug, gcid, primary_org_id,
                is_demo, is_active, claimed) values (%s, %s, %s, %s, %s, %s, %s, true, true, false)""",
                         (pid, d["first"], d["last"], f"{d['first']} {d['last']}", "demo-" + d["key"], d["gcid"], org))
        org = conn.execute("select primary_org_id from professionals where id = %s", (pid,)).fetchone()[0]
        conn.execute("""insert into exp_entitlements (id, subject_type, subject_id, product_key, state, source, granted_by,
            granted_at, expires_at, config) values (%s, 'organization', %s, 'conversion_agent', 'active', 'demo', 'demo',
            now(), now() + interval '1 year', '{}')""", (uid("ent-" + d["key"]), str(org)))
        availability = ({"mon": [["09:00", "17:00"]], "tue": [["09:00", "17:00"]], "wed": [["09:00", "17:00"]],
                         "thu": [["09:00", "17:00"]], "fri": [["09:00", "17:00"]], "sat": [["10:00", "14:00"]]}
                        if d["booking"] else {})
        special = {"parking": "available"} if d["gcid"] == "gcid:american_restaurant" else {}
        conn.execute("""insert into conv_professional_settings (professional_id, timezone, booking_enabled, availability, services,
            special_fields, opening_hours, response_hours, current_offers, notify_by, display_switches, public_phone, public_email,
            updated_by) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'demo') on conflict (professional_id) do nothing""",
                     (pid, d["tz"], d["booking"], Jsonb(availability), services_by_gcid[d["gcid"]], Jsonb(special),
                      Jsonb({"mon_fri": "09:00-17:00", "sat": "10:00-14:00", "sun": "closed"}), Jsonb({"mon_fri": "09:00-17:00"}),
                      d["offers"], d["notify"], Jsonb({"phone": "enable", "email": "disable", "booking_link": "enable"}),
                      f"+1 555 010{DEMO.index(d) + 1}", f"{d['key']}-demo@demo.example"))
        for dom in d["domains"]:
            conn.execute("insert into conv_domains (site_key, professional_id, domain) values (%s, %s, %s) on conflict do nothing",
                         (new_site_key(test=True), pid, dom))
        set_links(conn, pid, demo_links(conn, d["gcid"], d["domains"][0]))   # booking_link, menu_link, ... in special_fields
        if d["key"] == "diner":
            for name, section, price, chef in DISHES:
                conn.execute("insert into conv_menu (menu_id, name, section) values (%s, %s, %s) on conflict do nothing",
                             (uid("dish-" + name), name, section))
                conn.execute("""insert into conv_professional_menu (professional_id, menu_id, price, availability, chef_special)
                    values (%s, %s, %s, %s, %s) on conflict do nothing""",
                             (pid, uid("dish-" + name), price, Jsonb({"enabled": True, "days": WEEKDAYS}), chef))
    conn.commit()


def load_outputs(conn) -> None:
    """Step 4: one visit, chat, handovers, booking and daily totals, for the first demo customer with a booking."""
    pid, domain = conn.execute("select professional_id, domain from conv_domains where domain = 'demo-diner-1.example'").fetchone()
    visitor, activity, chat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    conn.execute("""insert into conv_visitor (professional_id, domain, visitor_id, have_consent, consent_choice, consent_at,
        consent_notice_version, first_seen_at, last_seen_at, visits, city, state, widget_seconds_total, score_72h, visit_summaries)
        values (%s, %s, %s, true, 'accepted', %s, 'v1', %s, %s, 1, 'Chicago', 'IL', 210, 45, %s)""",
                 (pid, domain, visitor, now, now, now, Jsonb([{"at": now.isoformat(), "activity_id": str(activity),
                                                                "domain": domain, "summary": "Asked about the menu and a booking"}])))
    conn.execute("""insert into conv_activity (activity_id, professional_id, domain, visitor_id, have_consent, status, started_at,
        last_activity_at, ended_at, city, state, clicks, time_on_site_seconds, widget_opens, time_in_widget_seconds, summary,
        session_score, abuse_strikes) values (%s, %s, %s, %s, true, 'handed_over', %s, %s, %s, 'Chicago', 'IL', 5, 410, 1, 210,
        'Asked about the menu and a booking, then handed over', 45, 0)""", (activity, pid, domain, visitor, now, now, now))
    conn.execute("insert into conv_session (session_id, activity_id, messages, topic) values (%s, %s, %s::jsonb, 'dish_search')",
                 (chat, activity, Jsonb([{"request": ["How much is the smash burger?"], "response": "Smash Burger (11.50) - chef's special",
                                          "event_time": now.isoformat()}])))
    conn.execute("""insert into conv_handover (handover_id, professional_id, domain, session_id, visitor_id, name, email, phone,
        reason, action_key, request_type, question, summary, extra_fields, city, state, status, notified_by)
        values (%s, %s, %s, %s, %s, 'Jane Demo', 'jane.demo@example.com', '+1 555 0100', 'critical_question', null,
        'critical handover', 'What rate for a 30-year loan?', 'Asked for a 30-year rate: critical topic', '{}', 'Chicago', 'IL', 'new', '{email}')""",
                 (uid("handover-critical"), pid, domain, chat, visitor))
    conn.execute("""insert into conv_handover (handover_id, professional_id, domain, session_id, visitor_id, name, email, phone,
        reason, action_key, request_type, question, summary, extra_fields, city, state, status, notified_by)
        values (%s, %s, %s, %s, %s, 'Jane Demo', 'jane.demo@example.com', '+1 555 0100', 'request_from_visitor', 'request_rate_quote',
        'direct handover', 'Please send me a rate quote for a 30-year loan.', 'Pressed Request a rate quote', '{}', 'Chicago', 'IL', 'new', '{email}')""",
                 (uid("handover-quote"), pid, domain, chat, visitor))
    conn.execute("""insert into conv_handover (handover_id, professional_id, domain, session_id, visitor_id, name, email, phone,
        reason, action_key, request_type, question, summary, extra_fields, city, state, status, notified_by)
        values (%s, %s, %s, %s, %s, 'Jane Demo', 'jane.demo@example.com', '+1 555 0100', 'request_from_visitor',
        'schedule_consultation', 'appointment booking', 'I would like a consultation next week.',
        'Asked to schedule a consultation', %s, 'Chicago', 'IL', 'new', '{email}')""",
                 (uid("handover-appointment"), pid, domain, chat, visitor, Jsonb({"preferred_time": "any afternoon"})))
    conn.execute("""insert into conv_hot_visitor (professional_id, domain, visitor_id, summary, city, state, first_hot_at, last_hot_at)
        values (%s, %s, %s, 'Asked about a 30-year loan and a rate quote', 'Chicago', 'IL', %s, %s)""", (pid, domain, visitor, now, now))
    conn.execute("""insert into conv_question (question_id, professional_id, domain, question_text, topic, asked_count, first_asked_at,
        last_asked_at, answered, status) values (%s, %s, %s, 'is there free parking', 'parking', 9, %s, %s, false, 'open')""",
                 (uuid.uuid4(), pid, domain, now - timedelta(days=4), now))
    conn.execute("""insert into conv_daily (professional_id, domain, day, visitors, chats, handovers, hot_visitors, bookings,
        questions_answered, questions_unanswered, topic_counts) values (%s, %s, %s, 1, 1, 3, 1, 0, 4, 1, %s)""",
                 (pid, domain, now.date(), Jsonb({"dish_search": 1})))
    conn.execute("""insert into conv_reply_feedback (professional_id, domain, session_id, rating, reason, topic, question, reply)
        values (%s, %s, %s, 'down', 'did_not_answer', 'pre-approval', 'What rate for a 30-year loan?',
        'Rates depend on your details, so I cannot quote one here.')""", (pid, domain, chat))
    conn.execute("""insert into conv_change_log (professional_id, domain, changed_by, page, area, target, action, summary,
        before_value, after_value, batch_id) values (%s, %s, 'demo.seed', 'admin', 'booking', 'booking_enabled', 'changed',
        'Turned booking on', %s, %s, 'seed-1')""", (pid, domain, Jsonb(False), Jsonb(True)))
    conn.execute("""insert into conv_log (event_type, actor_type, professional_id, domain, result, error_code, details)
        values ('calendar_failure', 'system', %s, %s, 'failure', 'not_connected', %s)""", (pid, domain, Jsonb({"calendar": "primary"})))
    conn.commit()


def flush_bundles() -> None:
    """The chat keeps the business bundles in Redis. After a rebuild they hold the old data, so they are removed and the
    chat builds them from the new tables on the next chat."""
    import redis
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    for pattern in ("customer_professional_*", "category_*", "bundle_current_*"):
        for key in client.scan_iter(pattern):
            client.delete(key)


def main() -> None:
    local_url = os.environ.get("LOCAL_DATABASE_URL", "postgresql://localhost:5432/conversion_agent")
    platform_url = os.environ.get("PLATFORM_READ_URL")
    if not platform_url:
        raise SystemExit("Set PLATFORM_READ_URL (a read-only connection to the platform database).")
    conn = psycopg.connect(local_url, connect_timeout=5)
    existing = conn.execute("select count(*) from information_schema.tables where table_schema = 'public' and table_name like 'conv\\_%'").fetchone()[0]
    if existing:
        raise SystemExit("The local database already has conv_ tables. Use an empty database.")
    print("1. applying the schema")
    # pg_dump adds psql-only lines (\restrict, \unrestrict); psycopg cannot run them, so they are dropped
    schema = "\n".join(line for line in SCHEMA_FILE.read_text(encoding="utf-8").splitlines() if not line.startswith("\\"))
    conn.execute(schema)
    # the dump sets search_path to empty for this session; the loaders use unqualified table names
    conn.execute("select set_config('search_path', 'public', false)")
    conn.commit()
    print("2. copying the production rows (read only)")
    copy_production(conn, platform_url)
    print("3. loading the demo inputs")
    load_inputs(conn)
    problems = check_database(conn)
    if problems:
        raise SystemExit("the tools and actions have problems:\n" + "\n".join(problems))
    print("4. loading the demo outputs")
    load_outputs(conn)
    conn.close()
    flush_bundles()
    print("done")


if __name__ == "__main__":
    main()
