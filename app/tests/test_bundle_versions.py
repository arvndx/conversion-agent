"""Bundle versions: each business has a customer bundle and a category bundle; a rebuild is a new version; a chat keeps
the versions it started with; the API rebuilds on request. Each test removes what it made.
Run from the app folder: uv run pytest tests/test_bundle_versions.py"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.chat_api import create_app
from pipeline import site_bundles
from pipeline.load_chat import DATABASE_URL, BundleMissing, connect, load_bundles, redis_client
from shared.bundles import customer_key

DINER = "483dc8e7-3f03-5fbb-878b-77ee433ed0b3"
CATEGORY = "gcid:american_restaurant"


@pytest.fixture()
def client():
    return redis_client()


@pytest.fixture()
def marked(monkeypatch):
    """Make the next customer build carry a marker, so the tests can tell the versions apart."""
    marker = uuid.uuid4().hex
    real = site_bundles.load_customer

    def with_marker(conn, pid):
        bundle = real(conn, pid)
        bundle["test_marker"] = marker
        return bundle

    monkeypatch.setattr(site_bundles, "load_customer", with_marker)
    yield marker
    monkeypatch.undo()
    with psycopg.connect(DATABASE_URL) as conn:
        site_bundles.publish_customer(conn, redis_client(), DINER)   # the business's bundle goes back to the real data


def test_the_first_build_creates_both_bundles(client):
    with psycopg.connect(DATABASE_URL) as conn:
        customer_v, category_v = site_bundles.ensure_bundles(conn, client, DINER)
    assert client.exists(site_bundles.versioned_key(customer_key("professional", DINER), customer_v))
    assert client.exists(site_bundles.versioned_key(site_bundles.category_key(CATEGORY.split(":")[1]), category_v))


def test_a_new_build_is_used_by_new_chats_and_a_running_chat_keeps_its_version(client, marked):
    with psycopg.connect(DATABASE_URL) as conn:
        old = site_bundles.ensure_bundles(conn, client, DINER)
        old_bundles = load_bundles(client, "professional", DINER)
        assert old_bundles.versions == old
        new_customer = site_bundles.publish_customer(conn, client, DINER)
    assert new_customer > old[0]
    assert load_bundles(client, "professional", DINER).customer["test_marker"] == marked         # new chats: new version
    pinned = load_bundles(client, "professional", DINER, pinned=old)
    assert "test_marker" not in pinned.customer                                                   # running chat: old version
    assert pinned.versions == old


def test_the_replaced_version_expires_after_two_hours(client, marked):
    with psycopg.connect(DATABASE_URL) as conn:
        old = site_bundles.ensure_bundles(conn, client, DINER)
        site_bundles.publish_customer(conn, client, DINER)
    ttl = client.ttl(site_bundles.versioned_key(customer_key("professional", DINER), old[0]))
    assert 0 < ttl <= site_bundles.OLD_VERSION_SECONDS


def test_a_chat_whose_version_expired_moves_to_the_current_version(client, marked):
    with psycopg.connect(DATABASE_URL) as conn:
        old = site_bundles.ensure_bundles(conn, client, DINER)
        site_bundles.publish_customer(conn, client, DINER)
    client.delete(site_bundles.versioned_key(customer_key("professional", DINER), old[0]))
    moved = load_bundles(client, "professional", DINER, pinned=old)
    assert moved.customer["test_marker"] == marked
    assert moved.versions[0] > old[0]


def test_a_missing_bundle_is_built_by_the_next_chat(client):
    with psycopg.connect(DATABASE_URL) as conn:
        site_bundles.ensure_bundles(conn, client, DINER)
        client.delete(site_bundles.current_customer_key(DINER))
        site_bundles.ensure_bundles(conn, client, DINER)
    assert load_bundles(client, "professional", DINER).customer["resource_id"] == DINER


def test_the_rebuild_api_builds_a_new_version_and_refuses_bad_input(client):
    api = TestClient(create_app(redis_client=client, connect_fn=connect))
    with psycopg.connect(DATABASE_URL) as conn:
        before = site_bundles.ensure_bundles(conn, client, DINER)
    response = api.post("/bundles/rebuild", json={"professional_id": DINER, "category": CATEGORY})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customer_version"] > before[0]
    assert body["category_version"] > before[1]
    assert api.post("/bundles/rebuild", json={}).status_code == 422
    assert api.post("/bundles/rebuild", json={"professional_id": "not-an-id"}).status_code == 422
    assert api.post("/bundles/rebuild", json={"category": "restaurant"}).status_code == 422


def test_the_rebuild_api_needs_the_token_when_one_is_set(client, monkeypatch):
    monkeypatch.setenv("BUNDLE_API_TOKEN", "secret-for-test")
    api = TestClient(create_app(redis_client=client, connect_fn=connect))
    assert api.post("/bundles/rebuild", json={"professional_id": DINER}).status_code == 401
    assert api.post("/bundles/rebuild", json={"professional_id": DINER},
                    headers={"X-Bundle-Token": "secret-for-test"}).status_code == 200


def test_a_share_toggle_in_the_dashboard_publishes_a_new_customer_version(client):
    from dashboard.server import app as dashboard_app
    api = TestClient(dashboard_app)
    with psycopg.connect(DATABASE_URL) as conn:
        before, _ = site_bundles.ensure_bundles(conn, client, DINER)
    response = api.put(f"/api/c/{DINER}/knowledge/phone", json={"enabled": False})
    assert response.status_code == 200, response.text
    assert int(client.get(site_bundles.current_customer_key(DINER))) > before
    api.put(f"/api/c/{DINER}/knowledge/phone", json={"enabled": True})   # back as it was
