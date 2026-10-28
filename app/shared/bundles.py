"""Load the bundles into Redis, under the keys agreed in the plan.

    category_<category_id>                          the category bundle (shared by a category)
    customer_<resource_type>_<resource_id>          the customer bundle (one per location)

Run from the app folder:
    uv run python -m shared.bundles
"""

import json
import os
from pathlib import Path

import redis

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
CATEGORY_FILE = SAMPLES_DIR / "restaurant_category.json"
CUSTOMER_FILE = SAMPLES_DIR / "spice_garden_customer.json"


def category_key(category_id: str) -> str:
    return f"category_{category_id}"


def customer_key(resource_type: str, resource_id: str) -> str:
    return f"customer_{resource_type}_{resource_id}"


def bundle_keys(category: dict, customer: dict) -> tuple[str, str]:
    return (
        category_key(category["category_id"]),
        customer_key(customer["resource_type"], customer["resource_id"]),
    )


def load_bundles(client: redis.Redis) -> dict[str, str]:
    """Write both bundles to Redis. Returns the keys written."""
    category = json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))
    customer = json.loads(CUSTOMER_FILE.read_text(encoding="utf-8"))
    cat_key, cust_key = bundle_keys(category, customer)
    client.set(cat_key, json.dumps(category, ensure_ascii=False))
    client.set(cust_key, json.dumps(customer, ensure_ascii=False))
    return {"category": cat_key, "customer": cust_key}


def main() -> None:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(url, decode_responses=True)
    written = load_bundles(client)
    for kind, key in written.items():
        print(f"{kind}: {key} ({len(client.get(key))} bytes)")


if __name__ == "__main__":
    main()
