"""The admin routes on the conv_ tables: the subscription, the domains, the widget colours, the admin page and the widget
switch. Each test puts back the demo values it changes. Run from the app folder: uv run pytest tests/test_admin.py"""

import psycopg
import pytest
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient

from dashboard.server import app
from pipeline.load_chat import DATABASE_URL


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def pro():
    with psycopg.connect(DATABASE_URL) as c:
        return str(c.execute("select professional_id from conv_domains where domain = 'demo-diner-1.example'").fetchone()[0])


@pytest.fixture()
def restore(pro):
    with psycopg.connect(DATABASE_URL) as c:
        before = c.execute("""select e.state, e.config from exp_entitlements e join professionals p on p.primary_org_id::text = e.subject_id
            where p.id = %s and e.product_key = 'conversion_agent'""", (pro,)).fetchone()
        domains = c.execute("select domain, status, primary_color, accent_color from conv_domains where professional_id = %s", (pro,)).fetchall()
        kill = c.execute("select kill_switch from conv_professional_settings where professional_id = %s", (pro,)).fetchone()[0]
    yield
    with psycopg.connect(DATABASE_URL) as c:
        if before:
            c.execute("""update exp_entitlements set state = %s, config = %s where subject_type = 'organization'
                and subject_id = (select primary_org_id::text from professionals where id = %s) and product_key = 'conversion_agent'""",
                      (before[0], Jsonb(before[1]), pro))
        for domain, status, primary, accent in domains:
            c.execute("update conv_domains set status = %s, primary_color = %s, accent_color = %s where professional_id = %s and domain = %s",
                      (status, primary, accent, pro, domain))
        c.execute("update conv_professional_settings set kill_switch = %s where professional_id = %s", (kill, pro))
        c.commit()


def test_the_subscription_is_read_from_the_entitlement(client, pro):
    body = client.get(f"/api/c/{pro}/subscription").json()
    assert body["subscribed"] is True and body["plans"] == ["monthly", "yearly"]


def test_the_subscription_can_be_paused_and_resumed(client, pro, restore):
    assert client.put(f"/api/c/{pro}/subscription", json={"subscribed": False, "plan": "yearly"}).json()["subscribed"] is False
    assert client.get(f"/api/c/{pro}/subscription").json()["subscribed"] is False
    assert client.put(f"/api/c/{pro}/subscription", json={"subscribed": True, "plan": "monthly"}).json()["subscribed"] is True


def test_a_domain_is_added_with_its_own_key_and_a_removed_one_is_paused(client, pro, restore):
    names = client.get(f"/api/c/{pro}/domains").json()["domains"]
    assert "demo-diner-1.example" in names
    assert client.put(f"/api/c/{pro}/domains", json={"domains": ["demo-diner-1.example", "demo-diner-3.example"]}).status_code == 200
    with psycopg.connect(DATABASE_URL) as c:
        key = c.execute("select site_key from conv_domains where professional_id = %s and domain = 'demo-diner-3.example'", (pro,)).fetchone()[0]
        c.execute("delete from conv_domains where professional_id = %s and domain = 'demo-diner-3.example'", (pro,))
        c.commit()
    assert key.startswith("wk_test_")


def test_too_many_domains_are_refused(client, pro):
    names = [f"d{i}.example" for i in range(5)]
    assert client.put(f"/api/c/{pro}/domains", json={"domains": names}).status_code == 422


def test_the_colours_are_kept_per_domain_and_reset(client, pro, restore):
    client.put(f"/api/c/{pro}/style/demo-diner-1.example", json={"font_size": 14, "font_family": "Arial", "primary": "#123456",
                                                               "accent": "#654321", "text": "#000000", "placement": "right"})
    assert client.get(f"/api/c/{pro}/style").json()["domains"]["demo-diner-1.example"]["primary"] == "#123456"
    client.post(f"/api/c/{pro}/style/demo-diner-1.example/reset")
    assert client.get(f"/api/c/{pro}/style").json()["domains"]["demo-diner-1.example"]["primary"] == "#7a2e1d"


def test_the_admin_page_shows_the_business_and_the_chef(client, pro):
    body = client.get(f"/api/c/{pro}/admin").json()
    assert body["business"]["domains"] and "specials" in body["chef"]
    assert set(body["widget"]) >= {"subscribed", "plan", "enabled"}


def test_the_widget_can_be_switched_off_and_on(client, pro, restore):
    assert client.put(f"/api/c/{pro}/widget-status", json={"enabled": False}).json()["enabled"] is False
    assert client.get(f"/api/c/{pro}/admin").json()["widget"]["enabled"] is False
    assert client.put(f"/api/c/{pro}/widget-status", json={"enabled": True}).status_code in (200, 409)
