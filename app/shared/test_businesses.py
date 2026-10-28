"""Test businesses for the four test categories: two per category, one with all its links and one with some.
Their rows go into the conversion agent's own tables (conv_site, conv_knowledge), and the chat engine's bundle is built
from those rows (shared/customer_loader.py). Run from the app folder: uv run python -m shared.test_businesses
"""

import json

import psycopg
import redis
from psycopg.types.json import Jsonb

from pipeline.topics import category_topics
from shared.bundles import category_key
from shared.category_bundle import build_category_bundle
from shared.customer_loader import publish_customer_bundle

LOCAL_DB = "postgresql://localhost:5432/conversion_agent"
REDIS_URL = "redis://localhost:6379/0"
RESOURCE_TYPE = "tier_location"

KEYS = ['wk_test_0fpnik3c3v7biwf6ikrr97jf', 'wk_test_lw8pufnno6hlnf3r0jvxuncf', 'wk_test_3s6joijsayxq837saul80nhw', 'wk_test_2iuiz076ik9m3a23j4k8710c', 'wk_test_nnkmz6t7fbrpq6d7usnezqvn', 'wk_test_ldk0lzb051az8hphfkz088vq', 'wk_test_9ubc60d4w5gnal0h34pfgnrx', 'wk_test_gyv52h74z18z0e2irsvygpz5']

BUSINESSES = [
    {"slug": "mortgage_broker", "site_key": KEYS[0], "name": "Harbor Mortgage Brokers", "port": 8101,
     "phone": "+1 555 0101", "email": "hello@harbormortgage.example", "address": "41 Harbor Way, Boston, MA",
     "hours": {"mon_fri": "09:00-18:00", "sat_sun": "10:00-14:00"}, "licence": "NMLS 1100201", "links": "all",
     "parking": "Free street parking on Harbor Way, and a car park at the end of the block",
     "programs": ["Purchase loans", "Refinancing"]},
    {"slug": "mortgage_broker", "site_key": KEYS[1], "name": "Pine Street Mortgage", "port": 8102,
     "phone": "+1 555 0102", "email": "info@pinemortgage.example", "address": "7 Pine Street, Denver, CO",
     "hours": {"mon_fri": "08:30-17:30", "sat_sun": "closed"}, "licence": "NMLS 1100202", "links": "some"},
    {"slug": "mortgage_lender", "site_key": KEYS[2], "name": "Summit Home Lending", "port": 8103,
     "phone": "+1 555 0103", "email": "loans@summitlending.example", "address": "900 Summit Ave, Austin, TX",
     "hours": {"mon_fri": "09:00-17:00", "sat_sun": "closed"}, "licence": "NMLS 1100203", "links": "all",
     "parking": "Car park for branch visitors, two hours free, then paid",
     "programs": ["30-year fixed", "15-year fixed", "FHA", "VA", "Jumbo"]},
    {"slug": "mortgage_lender", "site_key": KEYS[3], "name": "Lakeside Loans", "port": 8104,
     "phone": "+1 555 0104", "email": "hello@lakesideloans.example", "address": "22 Lakeside Dr, Chicago, IL",
     "hours": {"mon_fri": "09:00-19:00", "sat_sun": "10:00-15:00"}, "licence": "NMLS 1100204", "links": "some"},
    {"slug": "health_insurance_agency", "site_key": KEYS[4], "name": "Clearview Health Insurance", "port": 8105,
     "phone": "+1 555 0105", "email": "agents@clearviewhealth.example", "address": "5 Clearview Plaza, Phoenix, AZ",
     "hours": {"mon_fri": "08:00-18:00", "sat_sun": "09:00-13:00"}, "licence": "AZ Producer 778812", "links": "all"},
    {"slug": "health_insurance_agency", "site_key": KEYS[5], "name": "Oak Benefits Agency", "port": 8106,
     "phone": "+1 555 0106", "email": "hello@oakbenefits.example", "address": "88 Oak Lane, Nashville, TN",
     "hours": {"mon_fri": "09:00-17:00", "sat_sun": "closed"}, "licence": "TN Producer 554410", "links": "some"},
    {"slug": "commercial_real_estate_agency", "site_key": KEYS[6], "name": "Northgate Commercial Realty", "port": 8107,
     "phone": "+1 555 0107", "email": "deals@northgatecre.example", "address": "300 Northgate Blvd, Seattle, WA",
     "hours": {"mon_fri": "09:00-18:00", "sat_sun": "closed"}, "licence": "WA Broker 90321", "links": "all"},
    {"slug": "commercial_real_estate_agency", "site_key": KEYS[7], "name": "Riverside Property Group", "port": 8108,
     "phone": "+1 555 0108", "email": "info@riversideproperty.example", "address": "14 Riverside Rd, Portland, OR",
     "hours": {"mon_fri": "08:30-17:00", "sat_sun": "closed"}, "licence": "OR Broker 201877", "links": "some"},
]


def resource_id_for(business: dict) -> str:
    """The customer id the chat engine uses for this business (the same id the customer bundle is stored under)."""
    return f"site_{business['site_key'][-8:]}"


def link_keys(slug: str) -> list[str]:
    """The conversion actions of the category that send the visitor to a link (not the ones that collect details)."""
    return [t["id"] for t in build_category_bundle(slug)["topics"] if t.get("tool") == "get_conversion_link"]


def rows_for(business: dict) -> list[tuple]:
    """(kind, key, label, value) rows for conv_knowledge: the business facts, its licence and its links."""
    rows = [
        ("field", "full_name", "Full name", business["name"]),
        ("field", "phone", "Contact number", business["phone"]),
        ("field", "email", "Email", business["email"]),
        ("field", "address", "Address", business["address"]),
        ("field", "opening_hours", "Opening hours",
         f"Mon–Fri {business['hours']['mon_fri']}; Sat–Sun {business['hours']['sat_sun']}"),
        ("field", "licence", "Licence", business["licence"]),
    ]
    if business.get("parking"):
        rows.append(("field", "parking", "Parking", business["parking"]))
    if business.get("programs"):
        rows.append(("field", "services", "Loan programs and services", "; ".join(business["programs"])))
    keys = link_keys(business["slug"])
    chosen = keys if business["links"] == "all" else keys[: len(keys) // 2]
    for key in chosen:
        rows.append(("field", f"link:{key}", f"Link for {key.replace('_', ' ')}",
                     f"https://{business['slug'].replace('_', '-')}-{business['port']}.example/{key}"))
    return rows


PAGE_PORTS = (8101, 8103, 8105, 8107)   # one business per category, with a page (sites/business_pages.py)


def seed_restaurant_demo(conn: psycopg.Connection) -> None:
    """The restaurant demo (Spice Garden): one site per domain, the demo website on ports 8001 and 8002."""
    conn.execute("update conv_site set topics = %s where resource_id = 'loc_spice_garden_01'",
                 (Jsonb(category_topics("restaurant")),))
    for key, domain in (("wk_test_spice_garden_01", "localhost:8001"), ("wk_test_spice_garden_02", "localhost:8002")):
        conn.execute(
            """insert into conv_site (site_key, resource_id, gcid, entity_type, domain, display_name, status, settings)
               values (%s, 'loc_spice_garden_01', 'gcid:restaurant', 'location', %s, 'Spice Garden', 'active',
                       '{"page_tracking": "on"}'::jsonb)
               on conflict (site_key) do update set domain = excluded.domain, status = 'active',
                 settings = excluded.settings""",
            (key, domain))


def seed(conn: psycopg.Connection, client: redis.Redis) -> list[str]:
    seed_restaurant_demo(conn)
    done = []
    for business in BUSINESSES:
        conn.execute(
            """insert into conv_site (site_key, resource_id, gcid, entity_type, domain, display_name, status)
               values (%s, %s, %s, 'location', %s, %s, 'active')
               on conflict (site_key) do update set display_name = excluded.display_name,
                 domain = excluded.domain, status = 'active'""",
            (business["site_key"], resource_id_for(business), f"gcid:{business['slug']}",
             f"localhost:{business['port']}", business["name"]),
        )
        site_id = conn.execute("select site_id from conv_site where site_key = %s", (business["site_key"],)).fetchone()[0]
        conn.execute("update conv_site set topics = %s where site_id = %s",
                     (Jsonb(category_topics(business["slug"])), site_id))
        if business["port"] in PAGE_PORTS:   # the four business pages: the chat may show the phone and email
            conn.execute("update conv_site set settings = settings || %s where site_id = %s",
                         (Jsonb({"chat_contact": {"phone": True, "email": True}}), site_id))
        conn.execute("delete from conv_knowledge where site_id = %s and kind = 'field'", (site_id,))
        for kind, key, label, value in rows_for(business):
            conn.execute(
                "insert into conv_knowledge (site_id, kind, key, label, value, source, confirmed, updated_by) "
                "values (%s, %s, %s, %s, %s, 'manual', true, 'test seed')",
                (site_id, kind, key, label, value),
            )
        publish_customer_bundle(conn, client, business["site_key"], RESOURCE_TYPE, business["port"])
        done.append(business["site_key"])
    for slug in sorted({b["slug"] for b in BUSINESSES}):
        client.set(category_key(slug), json.dumps(build_category_bundle(slug), ensure_ascii=False))
    return done


if __name__ == "__main__":
    with psycopg.connect(LOCAL_DB) as conn:
        keys = seed(conn, redis.Redis.from_url(REDIS_URL, decode_responses=True))
        conn.commit()
    print("seeded", len(keys), "test businesses")
