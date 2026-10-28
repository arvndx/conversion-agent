"""The dashboard's data, kept in the conv_ tables. The business is a professional (resource_id is its professional id).
Its sites are its domains (conv_domains). Every function takes the open connection, so a batch of changes is one
transaction: if one part is refused, nothing is kept.

Where the data lives:
  settings, hours, services, offers, the public phone and email  conv_professional_settings
  a field's switch (shared with the chat or not)                 conv_professional_settings.display_switches
  a special field (for example parking)                          conv_professional_settings.special_fields
  scraped web facts                                              conv_web_fact
  dishes, prices, availability, chef specials                    conv_menu, conv_professional_menu
  what visitors asked for, and where the answer goes             conv_question
  leads and hot visitors                                         conv_handover, conv_hot_visitor
  the change log                                                 conv_change_log
  the subscription (read only)                                   exp_entitlements (local copy of production)
"""

import json
import uuid

from psycopg.types.json import Jsonb

from shared.action_steps import is_link_key

SETTINGS_COLUMNS = {"timezone", "booking_enabled", "availability", "slot_minutes", "bookings_per_slot",
                    "hot_visitor_threshold", "notify_by", "response_hours", "handover_extra_fields", "current_offers",
                    "services", "opening_hours", "kill_switch", "public_phone", "public_email"}
# Predefined fields the customer can share with the chat. Each reads and writes one place.
FIELD_COLUMNS = {"opening_hours": "opening_hours", "services": "services", "offers": "current_offers",
                 "phone": "public_phone", "email": "public_email", "response_hours": "response_hours"}
FIELD_LABELS = {"opening_hours": "Opening hours", "services": "Services", "offers": "Current offers",
                "phone": "Phone", "email": "Email", "response_hours": "Response hours"}
SWITCHES_DEFAULT = "disable"


def _menu_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"dish:{name}"))


# ---- domains (the sites) ------------------------------------------------------------------------------------------

def sites(conn, pid: str) -> list[tuple]:
    return conn.execute("select domain, status, site_key from conv_domains where professional_id = %s order by domain",
                        (pid,)).fetchall()


def active_domains(conn, pid: str) -> list[str]:
    return [d for d, status, _ in sites(conn, pid) if status == "active"]


def set_domain_status(conn, pid: str, domain: str, status: str) -> None:
    if status not in ("active", "paused"):
        raise ValueError("status is active or paused")
    if conn.execute("update conv_domains set status = %s where professional_id = %s and domain = %s",
                    (status, pid, domain)).rowcount == 0:
        raise LookupError("no such domain")


def add_domain(conn, pid: str, domain: str, site_key: str) -> None:
    conn.execute("insert into conv_domains (site_key, professional_id, domain) values (%s, %s, %s)", (site_key, pid, domain))


def set_colours(conn, pid: str, domain: str, primary: str, accent: str) -> None:
    if conn.execute("update conv_domains set primary_color = %s, accent_color = %s where professional_id = %s and domain = %s",
                    (primary, accent, pid, domain)).rowcount == 0:
        raise LookupError("no such domain")


# ---- change log --------------------------------------------------------------------------------------------------

def log_change(conn, pid: str, *, who: str, page: str, area: str, action: str, summary: str, target: str | None = None,
               before=None, after=None, batch_id: str | None = None, domain: str | None = None) -> None:
    conn.execute(
        """insert into conv_change_log (professional_id, domain, changed_by, page, area, target, action, summary,
            before_value, after_value, batch_id) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (pid, domain, who, page, area, target, action, summary,
         Jsonb(before) if before is not None else None, Jsonb(after) if after is not None else None, batch_id))


def recent_changes(conn, pid: str, limit: int = 50) -> list[tuple]:
    return conn.execute(
        """select changed_at, changed_by, page, area, target, action, summary, before_value, after_value, batch_id
        from conv_change_log where professional_id = %s order by changed_at desc, change_id desc limit %s""",
        (pid, limit)).fetchall()


# ---- professional settings ---------------------------------------------------------------------------------------

def get_settings(conn, pid: str) -> dict:
    cur = conn.execute("select * from conv_professional_settings where professional_id = %s", (pid,))
    row = cur.fetchone()
    if row is None:
        raise LookupError("no settings for this professional")
    return dict(zip([d.name for d in cur.description], row))


def set_settings(conn, pid: str, **fields) -> None:
    unknown = set(fields) - SETTINGS_COLUMNS
    if unknown:
        raise ValueError(f"not a setting: {sorted(unknown)}")
    if not fields:
        return
    assignments = ", ".join(f"{column} = %s" for column in fields)
    values = [Jsonb(v) if isinstance(v, (dict, list)) and column not in ("services", "current_offers", "notify_by", "handover_extra_fields")
              else v for column, v in fields.items()]
    conn.execute(f"update conv_professional_settings set {assignments}, updated_at = now(), updated_by = 'dashboard' "
                 "where professional_id = %s", (*values, pid))


def switches(conn, pid: str) -> dict:
    return dict(get_settings(conn, pid)["display_switches"] or {})


def set_switch(conn, pid: str, key: str, value: str) -> None:
    if value not in ("enable", "disable"):
        raise ValueError("a switch is enable or disable")
    conn.execute("update conv_professional_settings set display_switches = display_switches || %s, updated_at = now() "
                 "where professional_id = %s", (Jsonb({key: value}), pid))


# ---- predefined fields (the knowledge page) ---------------------------------------------------------------------

def field_states(conn, pid: str) -> dict[str, dict]:
    """Each predefined field: its value, whether the chat may share it, and whether the customer has set it."""
    settings = get_settings(conn, pid)
    sw = settings["display_switches"] or {}
    out = {}
    for key, column in FIELD_COLUMNS.items():
        value = settings.get(column)
        out[key] = {"label": FIELD_LABELS[key], "value": value, "shared": sw.get(key, SWITCHES_DEFAULT) == "enable",
                    "set": bool(value)}
    return out


def save_field(conn, pid: str, key: str, *, value=None, shared: bool | None = None) -> None:
    if key not in FIELD_COLUMNS:
        raise ValueError("not a predefined field")
    if value is not None:
        column = FIELD_COLUMNS[key]
        if column in ("services", "current_offers"):
            value = list(value)
        set_settings(conn, pid, **{column: value})
    if shared is not None:
        set_switch(conn, pid, key, "enable" if shared else "disable")


def special_fields(conn, pid: str) -> dict:
    return dict(get_settings(conn, pid)["special_fields"] or {})


def save_special_field(conn, pid: str, key: str, value: str) -> None:
    conn.execute("update conv_professional_settings set special_fields = special_fields || %s, updated_at = now() "
                 "where professional_id = %s", (Jsonb({key: value}), pid))


# ---- web facts (scrape a page) ----------------------------------------------------------------------------------

def save_web_facts(conn, pid: str, domain: str, source_url: str, facts: dict[str, str]) -> None:
    for key, value in facts.items():
        conn.execute(
            """insert into conv_web_fact (professional_id, domain, key, value, source_url, web_value)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (professional_id, key) do update set value = excluded.value, source_url = excluded.source_url,
                web_value = excluded.web_value, scraped_at = now(), updated_at = now()""",
            (pid, domain, key, value, source_url, value))


def web_facts(conn, pid: str) -> list[tuple]:
    return conn.execute("""select key, value, source_url, scraped_at, confirmed, shared from conv_web_fact
        where professional_id = %s order by key""", (pid,)).fetchall()


def confirm_web_fact(conn, pid: str, key: str, *, shared: bool, who: str) -> None:
    if conn.execute("""update conv_web_fact set confirmed = true, shared = %s, confirmed_by = %s, confirmed_at = now(),
        updated_at = now() where professional_id = %s and key = %s""", (shared, who, pid, key)).rowcount == 0:
        raise LookupError("no such web fact")


# ---- menu ----------------------------------------------------------------------------------------------------------

def menu(conn, pid: str) -> list[dict]:
    rows = conn.execute("""select m.menu_id, m.name, m.section, m.description, pm.price, pm.availability, pm.chef_special
        from conv_menu m join conv_professional_menu pm on pm.menu_id = m.menu_id
        where pm.professional_id = %s order by m.section, m.name""", (pid,)).fetchall()
    return [{"menu_id": str(r[0]), "name": r[1], "section": r[2], "description": r[3],
             "price": float(r[4]) if r[4] is not None else None, "availability": r[5] or {}, "chef_special": r[6]}
            for r in rows]


def save_dish(conn, pid: str, name: str, *, section: str, price: float, availability: dict | None = None,
              chef_special: bool = False, description: str | None = None) -> None:
    menu_id = _menu_id(name)
    conn.execute("""insert into conv_menu (menu_id, name, section, description) values (%s, %s, %s, %s)
        on conflict (menu_id) do update set section = excluded.section, description = coalesce(excluded.description, conv_menu.description),
        updated_at = now()""", (menu_id, name, section, description))
    conn.execute("""insert into conv_professional_menu (professional_id, menu_id, price, availability, chef_special)
        values (%s, %s, %s, %s, %s) on conflict (professional_id, menu_id) do update set price = excluded.price,
        availability = excluded.availability, chef_special = excluded.chef_special, updated_at = now()""",
                 (pid, menu_id, price, Jsonb(availability or {}), chef_special))


def chef_specials(conn, pid: str) -> list[str]:
    return [d["name"] for d in menu(conn, pid) if d["chef_special"]]


# ---- what visitors asked for (insights) ------------------------------------------------------------------------

def insights(conn, pid: str) -> list[dict]:
    """Questions the chat could not answer, across the professional's domains, with where the answer goes."""
    rows = conn.execute("""select question_text, max(topic), sum(asked_count), bool_or(answered), max(suggested_target),
        max(confirmed_target), max(status), min(first_asked_at), max(last_asked_at), max(suggested_answer), max(suggested_key)
        from conv_question where professional_id = %s and not answered group by question_text
        order by sum(asked_count) desc""", (pid,)).fetchall()
    return [{"question": r[0], "topic": r[1], "asked": int(r[2]), "suggested_target": r[4], "confirmed_target": r[5],
             "status": r[6], "first_asked_at": r[7], "last_asked_at": r[8], "suggested_answer": r[9],
             "suggested_key": r[10]} for r in rows]


def confirm_insight(conn, pid: str, question: str, target: str, who: str) -> None:
    updated = conn.execute("""update conv_question set confirmed_target = %s, confirmed_by = %s, confirmed_at = now(),
        status = 'added', updated_at = now() where professional_id = %s and question_text = %s""",
                           (target, who, pid, question)).rowcount
    if updated == 0:
        raise LookupError("no such question")


# ---- leads and hot visitors ----------------------------------------------------------------------------------

# The predefined fields and the column each one is saved in. A list column takes the answer as one more item.
ANSWER_COLUMNS = {"phone": ("public_phone", "text"), "email": ("public_email", "text"),
                  "opening_hours": ("opening_hours", "json"), "response_hours": ("response_hours", "json"),
                  "services": ("services", "list"), "offers": ("current_offers", "list")}


def save_insight_answer(conn, pid: str, question: str, answer: str, key: str, who: str) -> dict:
    """Save the business's answer to an unanswered question. A predefined field (see ANSWER_COLUMNS) takes it in its column;
    any other key is saved as a custom field. The question row is kept, marked answered, with the answer and where it went
    (it expires 30 days after its last update, see pipeline/cleanup.py)."""
    text = " ".join(question.lower().split())[:300]
    answer = answer.strip()[:1000]
    if key not in ANSWER_COLUMNS and is_link_key(key):
        raise ValueError("a name ending in _link is kept for the business's links; use another name")
    if key in ANSWER_COLUMNS:
        column, kind = ANSWER_COLUMNS[key]
        if kind == "list":
            current = conn.execute(f"select {column} from conv_professional_settings where professional_id = %s", (pid,)).fetchone()[0]
            conn.execute(f"update conv_professional_settings set {column} = %s, updated_at = now() where professional_id = %s",
                         ((current or []) + [answer], pid))
        elif kind == "json":
            conn.execute(f"update conv_professional_settings set {column} = %s, updated_at = now() where professional_id = %s",
                         (Jsonb({"text": answer}), pid))
        else:
            conn.execute(f"update conv_professional_settings set {column} = %s, updated_at = now() where professional_id = %s",
                         (answer, pid))
        where = {"key": key, "label": FIELD_LABELS[key], "custom": False}
    else:
        conn.execute("""update conv_professional_settings set special_fields = special_fields || %s, updated_at = now()
            where professional_id = %s""", (Jsonb({key: answer}), pid))
        where = {"key": key, "label": key, "custom": True}
    conn.execute("""update conv_question set answered = true, status = 'added', answer_text = %s, answer_key = %s,
        answered_at = now(), updated_at = now() where professional_id = %s and question_text = %s""",
                 (answer, key, pid, text))
    return where


def set_suggested_answer(conn, pid: str, question: str, answer: str, key: str) -> None:
    """The AI's suggested answer and where it would go, kept on the question so it is made once."""
    conn.execute("""update conv_question set suggested_answer = %s, suggested_key = %s, updated_at = now()
        where professional_id = %s and question_text = %s""", (answer, key, pid, " ".join(question.lower().split())[:300]))


def leads(conn, pid: str, limit: int = 50) -> list[tuple]:
    return conn.execute("""select handover_id, name, email, phone, reason, action_key, question, summary, status,
        created_at, session_id from conv_handover where professional_id = %s order by created_at desc limit %s""",
                        (pid, limit)).fetchall()


def set_lead_status(conn, pid: str, handover_id: str, status: str) -> None:
    if status not in ("new", "contacted", "closed"):
        raise ValueError("status is new, contacted or closed")
    if conn.execute("update conv_handover set status = %s, updated_at = now() where professional_id = %s and handover_id = %s",
                    (status, pid, handover_id)).rowcount == 0:
        raise LookupError("no such lead")


def hot_visitors(conn, pid: str, limit: int = 50) -> list[tuple]:
    threshold = int(get_settings(conn, pid)["hot_visitor_threshold"])
    return conn.execute("""select h.visitor_id, h.domain, h.summary, h.city, h.state, h.first_hot_at, h.last_hot_at,
        v.score_72h, v.visits from conv_hot_visitor h join conv_visitor v using (professional_id, domain, visitor_id)
        where h.professional_id = %s and v.score_72h >= %s order by v.score_72h desc limit %s""",
                        (pid, threshold, limit)).fetchall()


def refresh_hot_visitors(conn, pid: str) -> int:
    """Add the visitors at or above the threshold to conv_hot_visitor, and keep their summary. Returns how many were added."""
    threshold = int(get_settings(conn, pid)["hot_visitor_threshold"])
    rows = conn.execute("""select domain, visitor_id, city, state, visit_summaries from conv_visitor
        where professional_id = %s and score_72h >= %s""", (pid, threshold)).fetchall()
    for domain, visitor_id, city, state, summaries in rows:
        summary = "; ".join(s.get("summary", "") for s in (summaries or []) if s.get("summary"))[:500] or None
        conn.execute("""insert into conv_hot_visitor (professional_id, domain, visitor_id, summary, city, state, first_hot_at,
            last_hot_at) values (%s, %s, %s, %s, %s, %s, now(), now())
            on conflict (professional_id, domain, visitor_id) do update set summary = excluded.summary,
            city = excluded.city, state = excluded.state, last_hot_at = now(), updated_at = now()""",
                     (pid, domain, visitor_id, summary, city, state))
    return len(rows)


# ---- replies and topics -------------------------------------------------------------------------------------

def reply_feedback(conn, pid: str, limit: int = 100) -> list[tuple]:
    return conn.execute("""select rated_at, domain, rating, reason, reason_note, topic, question, reply
        from conv_reply_feedback where professional_id = %s order by rated_at desc limit %s""", (pid, limit)).fetchall()


def topic_counts(conn, pid: str) -> list[tuple]:
    return conn.execute("""select domain, day, topic_counts from conv_daily where professional_id = %s
        order by day desc, domain""", (pid,)).fetchall()


# ---- subscription (read only: the entitlement copy) --------------------------------------------------------------

def subscription(conn, pid: str) -> list[tuple]:
    return conn.execute("""select e.product_key, e.state, e.expires_at from exp_entitlements e
        join professionals p on p.primary_org_id::text = e.subject_id where p.id = %s and e.subject_type = 'organization'
        order by e.product_key""", (pid,)).fetchall()


# ---- the people page (leads and hot visitors, with what the chat shows about each) -----------------------------

def people_leads(conn, pid: str, since) -> list[tuple]:
    """Leads (every request a visitor sent: bookings, handovers and the rest) in the period, with the chat and the visit each
    one came from. The last three columns say what the visitor asked for: its request type, its action and the extra fields."""
    return conn.execute("""select h.handover_id, h.name, h.email, h.phone, h.reason, h.question, h.summary, h.status,
        h.created_at, h.domain, h.city, h.state, a.time_in_widget_seconds, a.session_score, a.clicks,
        a.time_on_site_seconds, s.messages, h.request_type, h.action_key, h.extra_fields
        from conv_handover h
        left join conv_session s on s.session_id = h.session_id
        left join conv_activity a on a.activity_id = s.activity_id
        where h.professional_id = %s and h.created_at >= %s order by h.created_at desc""", (pid, since)).fetchall()


def latest_chat(conn, pid: str, domain: str, visitor_id) -> tuple:
    """The visitor's latest chat on this domain: (summary, messages). Empty when there is none."""
    row = conn.execute("""select s.messages, a.summary from conv_session s join conv_activity a using (activity_id)
        where a.professional_id = %s and a.domain = %s and a.visitor_id = %s order by a.started_at desc limit 1""",
                       (pid, domain, visitor_id)).fetchone()
    return (row[1], row[0]) if row else (None, [])


def people_hot(conn, pid: str, since, limit: int = 200) -> list[tuple]:
    """Visitors at or above the threshold, seen in the period, most recently seen first."""
    threshold = int(get_settings(conn, pid)["hot_visitor_threshold"])
    return conn.execute("""select v.visitor_id, v.domain, v.city, v.state, v.widget_seconds_total, v.score_72h, v.last_seen_at
        from conv_visitor v where v.professional_id = %s and v.score_72h >= %s and v.last_seen_at >= %s
        order by v.last_seen_at desc limit %s""", (pid, threshold, since, limit)).fetchall()


def replies_full(conn, pid: str, since) -> list[tuple]:
    return conn.execute("""select f.feedback_id, f.rated_at, f.rating, f.reason, f.reason_note, f.topic, f.question, f.reply,
        f.domain, s.messages from conv_reply_feedback f left join conv_session s on s.session_id = f.session_id
        where f.professional_id = %s and f.rated_at >= %s order by f.rated_at desc""", (pid, since)).fetchall()


def set_suggestion(conn, pid: str, question: str, target: str, by: str) -> None:
    """Record where the answer should go, for every domain's row of this question."""
    conn.execute("""update conv_question set suggested_target = %s, updated_at = now()
        where professional_id = %s and question_text = %s""", (f"{target}|{by}", pid, question))


def action_labels(conn, gcid: str) -> dict[str, str]:
    return dict(conn.execute("select action_key, action_name from conv_action where gcid = %s", (gcid,)).fetchall())


def special_field_definitions(conn, gcid: str) -> list[dict]:
    row = conn.execute("select special_field_definitions from conv_category_settings where gcid = %s", (gcid,)).fetchone()
    return list(row[0]) if row and row[0] else []


# ---- menu availability, chef specials, the menu link, the chat's contact switches ----------------------------

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def set_dish_availability(conn, pid: str, menu_id: str, *, enabled: bool, days: list[int], start: str | None,
                          end: str | None) -> None:
    """Days are 0 (Monday) to 6 (Sunday), stored as names. A dish that is off has enabled = false."""
    availability = {"enabled": enabled, "days": [WEEKDAY_NAMES[d] for d in days], "start": start, "end": end}
    if conn.execute("update conv_professional_menu set availability = %s, updated_at = now() where professional_id = %s and menu_id = %s",
                    (Jsonb(availability), pid, menu_id)).rowcount == 0:
        raise LookupError("no such dish")


def set_chef_specials(conn, pid: str, names: list[str]) -> None:
    conn.execute("""update conv_professional_menu pm set chef_special = (m.name = any(%s)), updated_at = now()
        from conv_menu m where m.menu_id = pm.menu_id and pm.professional_id = %s""", (names, pid))


def set_menu_link(conn, pid: str, gcid: str, url: str) -> None:
    save_special_field(conn, pid, "menu_link", url)   # the business's links are fields in special_fields


def menu_link(conn, pid: str) -> str | None:
    return special_fields(conn, pid).get("menu_link") or None


# ---- knowledge: where each predefined field is stored, and the customer's choices ------------------------------

FIELD_STORAGE = {"opening_hours": "opening_hours", "response_hours": "response_hours", "services": "services",
                 "offers": "current_offers", "phone": "public_phone", "email": "public_email"}
LIST_FIELDS = {"services", "offers"}
PAGE_KEY = "_page"


def field_value(conn, pid: str, key: str):
    """The value the chat uses for a predefined field, as text (None when not set)."""
    settings = get_settings(conn, pid)
    if key == "parking":
        return (settings["special_fields"] or {}).get("parking")
    value = settings.get(FIELD_STORAGE[key])
    if value in (None, "", [], {}):
        return None
    if key in LIST_FIELDS:
        return "; ".join(value) if key == "offers" else ", ".join(value)
    if isinstance(value, dict):
        return next(iter(value.values()), None)
    return value


def write_field_value(conn, pid: str, key: str, value: str) -> None:
    """Store the chosen value where the chat reads it."""
    if key == "parking":
        save_special_field(conn, pid, "parking", value)
    elif key in LIST_FIELDS:
        items = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
        set_settings(conn, pid, **{FIELD_STORAGE[key]: items})
    elif key in ("opening_hours", "response_hours"):
        set_settings(conn, pid, **{FIELD_STORAGE[key]: {"mon_fri": value}})
    else:
        set_settings(conn, pid, **{FIELD_STORAGE[key]: value})


def web_fact(conn, pid: str, key: str):
    """(value, confirmed, web_value_when_chosen) for a web fact, or None."""
    return conn.execute("select value, confirmed, web_value from conv_web_fact where professional_id = %s and key = %s",
                        (pid, key)).fetchone()


def scrape_page(conn, pid: str, domain: str, url: str, facts: dict[str, str]) -> None:
    """Keep the page's facts (as found) and when it was checked."""
    conn.execute("""insert into conv_web_fact (professional_id, domain, key, value, source_url, web_value, scraped_at)
        values (%s, %s, %s, %s, %s, %s, now())
        on conflict (professional_id, key) do update set value = excluded.value, source_url = excluded.source_url,
        web_value = excluded.web_value, scraped_at = now(), updated_at = now()""",
                 (pid, domain, PAGE_KEY, url, url, url))
    for key, value in facts.items():
        conn.execute("""insert into conv_web_fact (professional_id, domain, key, value, source_url, web_value, scraped_at)
            values (%s, %s, %s, %s, %s, %s, now())
            on conflict (professional_id, key) do update set value = excluded.value, source_url = excluded.source_url,
            web_value = excluded.web_value, scraped_at = now(), updated_at = now()""",
                     (pid, domain, key, value, url, value))


def page_check(conn, pid: str):
    """(url, checked_at) of the last web page check, or (None, None)."""
    row = conn.execute("select source_url, scraped_at from conv_web_fact where professional_id = %s and key = %s",
                       (pid, PAGE_KEY)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def mark_chosen(conn, pid: str, domain: str, key: str, web_value: str | None, who: str) -> None:
    """The customer chose this field's value. The web value it was chosen against is kept, so a later change shows as a conflict."""
    conn.execute("""insert into conv_web_fact (professional_id, domain, key, value, source_url, web_value, confirmed,
        confirmed_by, confirmed_at) values (%s, %s, %s, '', '', %s, true, %s, now())
        on conflict (professional_id, key) do update set confirmed = true, web_value = excluded.web_value,
        confirmed_by = excluded.confirmed_by, confirmed_at = now(), updated_at = now()""",
                 (pid, domain, key, web_value, who))


def unmark_chosen(conn, pid: str, key: str) -> None:
    conn.execute("update conv_web_fact set confirmed = false, web_value = null, updated_at = now() where professional_id = %s and key = %s",
                 (pid, key))


def custom_fields(conn, pid: str) -> list[tuple]:
    """Custom fields are the special fields that are not predefined (parking is predefined) and not a link (booking_link,
    menu_link, ... are the business's links, kept in the same place)."""
    values = special_fields(conn, pid)
    return [(k, v) for k, v in values.items() if k not in ("parking",) and not is_link_key(k)]


# ---- subscription, domains, colours and the widget switch -----------------------------------------------------

def org_of(conn, pid: str):
    row = conn.execute("select primary_org_id from professionals where id = %s", (pid,)).fetchone()
    return str(row[0]) if row and row[0] else None


def entitlement(conn, pid: str):
    """(state, term) of the conversion agent for the professional's office, or (None, None). Read from the local copy."""
    org = org_of(conn, pid)
    if org is None:
        return (None, None)
    row = conn.execute("""select state, config->>'term' from exp_entitlements where subject_type = 'organization'
        and subject_id = %s and product_key = 'conversion_agent' order by granted_at desc limit 1""", (org,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def set_entitlement(conn, pid: str, state: str, term: str) -> None:
    """Demo only: change the conversion agent entitlement in the local copy (production is changed by the platform)."""
    org = org_of(conn, pid)
    if org is None:
        raise LookupError("no office for this professional")
    updated = conn.execute("""update exp_entitlements set state = %s, config = jsonb_set(coalesce(config, '{}'::jsonb), '{term}', %s)
        where subject_type = 'organization' and subject_id = %s and product_key = 'conversion_agent'""",
                           (state, Jsonb(term), org)).rowcount
    if updated == 0:
        conn.execute("""insert into exp_entitlements (id, subject_type, subject_id, product_key, state, source, granted_by,
            granted_at, config) values (gen_random_uuid(), 'organization', %s, 'conversion_agent', %s, 'demo', 'dashboard',
            now(), %s)""", (org, state, Jsonb({"term": term})))


def set_domains(conn, pid: str, names: list[str], new_key) -> dict:
    """The professional's domains are exactly these: known ones come back, new ones get a site key, and a domain no longer
    listed is paused (its visits and chats stay)."""
    known = {d: (status, key) for d, status, key in sites(conn, pid)}
    for name in names:
        if name in known:
            conn.execute("update conv_domains set status = 'active' where professional_id = %s and domain = %s", (pid, name))
        else:
            conn.execute("insert into conv_domains (site_key, professional_id, domain, status) values (%s, %s, %s, 'active')",
                         (new_key(), pid, name))
    for name in known:
        if name not in names:
            conn.execute("update conv_domains set status = 'paused' where professional_id = %s and domain = %s", (pid, name))
    return {"added": [n for n in names if n not in known], "paused": [n for n in known if n not in names]}


def set_kill_switch(conn, pid: str, value: str, reason: str | None, who: str) -> None:
    if value not in ("none", "stop_new_chats", "stop_everything"):
        raise ValueError("the switch is none, stop_new_chats or stop_everything")
    conn.execute("""update conv_professional_settings set kill_switch = %s, kill_switch_reason = %s, kill_switch_by = %s,
        kill_switch_at = now(), updated_at = now() where professional_id = %s""", (value, reason, who, pid))


def domain_colours(conn, pid: str) -> dict[str, tuple[str, str]]:
    return {d: (p, a) for d, p, a in conn.execute("select domain, primary_color, accent_color from conv_domains where professional_id = %s", (pid,)).fetchall()}
