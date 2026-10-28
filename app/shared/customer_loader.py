"""Build a business's customer bundle (the chat engine's input) from the conversion agent's own tables, and publish it.

The customer bundle keeps the shape the chat engine already reads. Its facts come from conv_site and conv_knowledge.
publish_customer_bundle also writes the subscription row the engine checks (conversion_subscription), until the engine
reads the new tables directly.
"""

import json

import psycopg
import redis

from shared.bundles import customer_key


def _fact(rows: dict, key: str) -> str | None:
    value = rows.get(key)
    return value if value not in (None, "") else None


def load_customer(conn: psycopg.Connection, site_key: str, resource_type: str, port: int) -> dict:
    site = conn.execute("select site_id, resource_id, gcid, display_name, settings from conv_site where site_key = %s",
                        (site_key,)).fetchone()
    if site is None:
        raise KeyError(f"no site with key {site_key}")
    site_id, resource_id, gcid, display_name, settings = site
    settings = settings or {}
    # The business's allowed domains are the domains of all its sites (one site per domain).
    domains = [row[0] for row in conn.execute(
        "select domain from conv_site where resource_id = %s order by domain", (resource_id,)).fetchall()]
    rows = dict(conn.execute("select key, value from conv_knowledge where site_id = %s and kind = 'field'", (site_id,)).fetchall())
    first, _, last = (display_name or "").partition(" ")
    links = {k[len("link:"):]: v for k, v in rows.items() if k.startswith("link:")}
    hours = _fact(rows, "opening_hours") or ""
    mon_fri, _, sat_sun = hours.partition("; ")
    return {
        "bundle_type": "customer",
        "resource_id": resource_id,
        "resource_type": resource_type,
        "category_id": gcid.split(":", 1)[1],
        "display_name": {"first_name": first, "last_name": last},
        "public_contact": {"phone": _fact(rows, "phone") or "", "email": _fact(rows, "email") or ""},
        "primary_location": _fact(rows, "address") or "",
        "service_area": _fact(rows, "address") or "",
        "timezone": "America/New_York",
        "business_hours": {"mon_fri": mon_fri.replace("Mon–Fri ", ""), "sat_sun": sat_sun.replace("Sat–Sun ", "")},
        "weblink": f"https://localhost:{port}",
        "links": links,
        "menu": {},
        "services": [item.strip() for item in (_fact(rows, "services") or "").split(";") if item.strip()],
        "licences": _fact(rows, "licence"),
        "parking": _fact(rows, "parking"),
        "chef": settings.get("chef") or {},
        "chat_contact": settings.get("chat_contact") or {},
        "current_offers": [],
        "scoring_threshold": 60,
        "slot_minutes": 15,
        "bookings_per_slot": 4,
        "google_calendar_connected": False,
        "enabled": True,
        "kill_switch": "none",
        "allowed_domains": list(domains),
        "site_key": site_key,
    }


def publish_customer_bundle(conn: psycopg.Connection, client: redis.Redis, site_key: str, resource_type: str, port: int) -> dict:
    customer = load_customer(conn, site_key, resource_type, port)
    client.set(customer_key(resource_type, customer["resource_id"]), json.dumps(customer, ensure_ascii=False))
    conn.execute("delete from conversion_subscription where resource_type = %s and resource_id = %s",
                 (resource_type, customer["resource_id"]))
    conn.execute(
        """insert into conversion_subscription (resource_type, resource_id, is_enabled, kill_switch, site_key, allowed_domains,
           plan, subscription_starts, subscription_ends, status)
           values (%s, %s, true, 'none', %s, %s, 'monthly', now() - interval '10 days', now() + interval '365 days', 'active')""",
        (resource_type, customer["resource_id"], site_key, customer["allowed_domains"]),
    )
    return customer
