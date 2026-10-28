"""Connect a site key to its professional and build the bundles. A chat reads only Redis: the tables are read when a bundle or
the site map is missing, and written to.

1. A site key (conv_domains) names one professional and one domain. The domain must match and the site must be active.
   Redis keeps the map from each site key to {professional id, domain, status, category id} (site_<site key>), written when
   the business's bundle is built, so a request finds its business without reading the tables.

2. Each business uses two bundles, built from the conv_ tables (shared/bundle_tables.py):
     the category bundle   one per category, shared by every business in that category
     the customer bundle   one per business

   Every build is a new version. Redis keeps:
     bundle_current_customer_<professional id>   the number of the current customer version
     bundle_current_category_<category id>       the number of the current category version
     customer_professional_<id>_v<n>             the customer bundle, version n
     category_<category id>_v<n>                 the category bundle, version n
   A chat records the two versions it started with and keeps using them (pipeline/load_chat.py). A new build is used by
   new chats only. The old version stays OLD_VERSION_SECONDS after the build, so chats that are still running finish on it.
   Every version is kept BUNDLE_TTL_SECONDS (7 days) as a safety net.

   A build runs when a business's data changes (POST /bundles/rebuild, called by hand after a change in the tables, or
   from the dashboard after a change made there), and when a chat finds a bundle missing.

"""

import json

import psycopg
import redis

from shared.bundle_tables import load_category, load_customer
from shared.bundles import category_key, customer_key

RESOURCE_TYPE = "professional"
BUNDLE_TTL_SECONDS = 7 * 24 * 60 * 60   # every version is kept 7 days, as a safety net
OLD_VERSION_SECONDS = 2 * 60 * 60       # a replaced version stays 2 hours, for the chats that are still running


class UnknownSite(Exception):
    pass


def current_customer_key(professional_id: str) -> str:
    return f"bundle_current_customer_{professional_id}"


def current_category_key(category_id: str) -> str:
    return f"bundle_current_category_{category_id}"


def versioned_key(base: str, version: int) -> str:
    return f"{base}_v{version}"


def professional_for_site(conn: psycopg.Connection, site_key: str, domain: str) -> str:
    """The professional id for a site key. The domain must be the site's own domain."""
    row = conn.execute("select professional_id, domain, status from conv_domains where site_key = %s", (site_key,)).fetchone()
    if row is None:
        raise UnknownSite("unknown site key")
    professional_id, site_domain, status = row
    if status != "active":
        raise UnknownSite("site is paused")
    if domain != site_domain:
        raise UnknownSite("the domain does not match this site key")
    return str(professional_id)


def _category_id(conn: psycopg.Connection, professional_id: str) -> str:
    return conn.execute("select gcid from professionals where id = %s", (professional_id,)).fetchone()[0].split(":", 1)[1]


SITE_MISSING_SECONDS = 30   # a site key that is not in the tables is remembered this long, so guesses do not reach them


def site_map_key(site_key: str) -> str:
    return f"site_{site_key}"


def fill_site_map(conn: psycopg.Connection, client: redis.Redis, professional_id: str) -> None:
    """Write the site map entries of a business: one per site key, with its domain, status and the business's category. A site
    that is no longer the business's is removed."""
    category_id = _category_id(conn, professional_id)
    for site_key, domain, status in conn.execute(
            "select site_key, domain, status from conv_domains where professional_id = %s", (professional_id,)).fetchall():
        client.delete(f"site_missing_{site_key}")
        client.set(site_map_key(site_key), json.dumps({"professional_id": str(professional_id), "domain": domain, "status": status,
                                                         "category_id": category_id}))


def site_location(conn: psycopg.Connection, client: redis.Redis, site_key: str) -> dict | None:
    """The business behind a site key: {professional_id, domain, status, category_id}, or None for a key that is unknown. Read
    from Redis; the tables are read only when the map has no entry for the key (then the business's entries are written)."""
    raw = client.get(site_map_key(site_key))
    if raw:
        return json.loads(raw)
    if client.exists(f"site_missing_{site_key}"):
        return None
    row = conn.execute("select professional_id from conv_domains where site_key = %s", (site_key,)).fetchone()
    if row is None:
        client.set(f"site_missing_{site_key}", 1, ex=SITE_MISSING_SECONDS)
        return None
    fill_site_map(conn, client, str(row[0]))
    return json.loads(client.get(site_map_key(site_key)))


def _publish(client: redis.Redis, pointer: str, base: str, payload: dict) -> int:
    """Write a new version of a bundle and make it the current one. Returns the new version number."""
    previous = client.get(pointer)
    version = client.incr(pointer)
    while client.exists(versioned_key(base, version)):   # never reuse a number a running chat may still hold
        version = client.incr(pointer)
    client.set(versioned_key(base, version), json.dumps(payload, ensure_ascii=False), ex=BUNDLE_TTL_SECONDS)
    if previous:
        client.expire(versioned_key(base, int(previous)), OLD_VERSION_SECONDS)
    return version


def publish_customer(conn: psycopg.Connection, client: redis.Redis, professional_id: str) -> int:
    """Build the business's customer bundle from the tables, as a new version. Returns the version number."""
    customer = load_customer(conn, professional_id)
    fill_site_map(conn, client, professional_id)   # the site keys and their domains and status, for the chat's routing
    return _publish(client, current_customer_key(professional_id), customer_key(RESOURCE_TYPE, professional_id), customer)


def publish_category(conn: psycopg.Connection, client: redis.Redis, gcid: str) -> int:
    """Build the category bundle (shared by every business in the category), as a new version."""
    category = load_category(conn, gcid)
    category_id = gcid.split(":", 1)[1]
    return _publish(client, current_category_key(category_id), category_key(category_id), category)


def _current(client: redis.Redis, pointer: str) -> int | None:
    value = client.get(pointer)
    return int(value) if value else None


def ensure_bundles(conn: psycopg.Connection, client: redis.Redis, professional_id: str) -> tuple[int, int]:
    """The current versions (customer, category). A bundle that is missing is built now. Returns the two version numbers. When
    both bundles are in Redis nothing is read from the tables: the category comes from the customer bundle."""
    customer_version = _current(client, current_customer_key(professional_id))
    raw = client.get(versioned_key(customer_key(RESOURCE_TYPE, professional_id), customer_version)) if customer_version else None
    if raw is None:
        customer_version = publish_customer(conn, client, professional_id)
        raw = client.get(versioned_key(customer_key(RESOURCE_TYPE, professional_id), customer_version))
    category_id = json.loads(raw)["category_id"]
    category_version = _current(client, current_category_key(category_id))
    if category_version is None or not client.exists(versioned_key(category_key(category_id), category_version)):
        category_version = publish_category(conn, client, f"gcid:{category_id}")
    return customer_version, category_version


def load_into_cache(conn: psycopg.Connection, client: redis.Redis, professional_id: str) -> tuple[str, str]:
    """Build both bundles now, as new versions. Returns (resource_type, resource_id)."""
    publish_customer(conn, client, professional_id)
    publish_category(conn, client, f"gcid:{_category_id(conn, professional_id)}")
    return RESOURCE_TYPE, professional_id
