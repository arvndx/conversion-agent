"""Tests for connecting a site key to its professional and loading its bundles. They use the local database and Redis.

Run from the app folder: uv run pytest tests/test_site_bundles.py
"""

import json

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL, redis_client
from pipeline.site_bundles import (UnknownSite, current_category_key, current_customer_key, load_into_cache,
                                   professional_for_site, versioned_key)
from shared.bundles import category_key, customer_key


@pytest.fixture()
def conn():
    with psycopg.connect(DATABASE_URL) as c:
        yield c


@pytest.fixture()
def site(conn):
    row = conn.execute("select site_key, professional_id, domain from conv_domains where status = 'active' order by domain limit 1").fetchone()
    return row


def test_site_key_resolves_to_its_professional(conn, site):
    site_key, professional_id, domain = site
    assert professional_for_site(conn, site_key, domain) == str(professional_id)


def test_wrong_domain_is_refused(conn, site):
    site_key, _, _ = site
    with pytest.raises(UnknownSite, match="domain"):
        professional_for_site(conn, site_key, "not-my-site.example")


def test_unknown_site_key_is_refused(conn):
    with pytest.raises(UnknownSite, match="unknown"):
        professional_for_site(conn, "wk_test_doesnotexist0001", "x.example")


def test_bundles_are_loaded_into_redis_in_the_chat_format(conn, site):
    _, professional_id, _ = site
    client = redis_client()
    resource_type, resource_id = load_into_cache(conn, client, str(professional_id))
    # a build is a new version: the pointer names the current one
    customer_version = int(client.get(current_customer_key(resource_id)))
    customer = json.loads(client.get(versioned_key(customer_key(resource_type, resource_id), customer_version)))
    assert customer["allowed_domains"]
    assert customer["enabled"] in (True, False)
    category_version = int(client.get(current_category_key(customer["category_id"])))
    category = json.loads(client.get(versioned_key(category_key(customer["category_id"]), category_version)))
    assert category["actions"] and category["critical_topics"] is not None
