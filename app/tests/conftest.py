"""Shared set-up for the tests. The chat reads its business and category bundles from Redis, so before the tests run the
bundles are built again from the local tables: a test never runs against a bundle built from older data."""

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL, redis_client
from pipeline.site_bundles import publish_category, publish_customer


@pytest.fixture(scope="session", autouse=True)
def fresh_bundles():
    client = redis_client()
    with psycopg.connect(DATABASE_URL) as conn:
        for (gcid,) in conn.execute("select gcid from conv_category_settings").fetchall():
            publish_category(conn, client, gcid)
        for (professional_id,) in conn.execute("select professional_id from conv_professional_settings").fetchall():
            publish_customer(conn, client, str(professional_id))
        conn.commit()
