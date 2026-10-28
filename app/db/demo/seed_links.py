"""The demo businesses' links, in conv_professional_settings.special_fields under generic keys (booking_link, menu_link, ...).

Which keys a business can have comes from its category's actions: the fields a details step provides whose name ends in
_link (shared/action_steps.py). The commercial real estate demo business has no booking_link, so its booking action falls
back to a handover; the others have one.

seed_demo calls demo_links() for each demo business. On a database that was built before links moved here, run this module
once: it moves the rows of the old conv_professional_link table, adds the demo links, and drops that table:
  LOCAL_DATABASE_URL=postgresql://localhost:5432/conversion_agent PYTHONPATH=. .venv/bin/python -m db.demo.seed_links
"""

import os

import psycopg
from psycopg.types.json import Jsonb

from shared.action_steps import is_link_key, provided_keys, step_for

NO_BOOKING_LINK = {"gcid:commercial_real_estate_agency"}


def action_steps(conn, gcid: str) -> dict[str, list[dict]]:
    return {k: s for k, s in conn.execute("select action_key, steps from conv_action where gcid = %s and enabled and steps is not null",
                                          (gcid,)).fetchall()}


def link_keys(conn, gcid: str) -> list[str]:
    keys: list[str] = []
    for steps in action_steps(conn, gcid).values():
        for step in steps:
            keys += [k for k in provided_keys(step) if is_link_key(k) and k not in keys]
    return sorted(keys)


def demo_links(conn, gcid: str, domain: str) -> dict[str, str]:
    """{link key: url} for a demo business of the category, on its first domain."""
    keys = [k for k in link_keys(conn, gcid) if not (k == "booking_link" and gcid in NO_BOOKING_LINK)]
    return {k: f"https://{domain}/{k[:-len('_link')].replace('_', '-')}" for k in keys}


def set_links(conn, professional_id: str, links: dict[str, str], overwrite: bool = False) -> None:
    """Add the links to special_fields. A link the business already has is kept unless overwrite is set."""
    merged = "%s::jsonb || special_fields" if not overwrite else "special_fields || %s::jsonb"
    conn.execute(f"update conv_professional_settings set special_fields = {merged}, updated_at = now() where professional_id = %s",
                 (Jsonb(links), professional_id))


def move_old_rows(conn) -> int:
    """Move the rows of conv_professional_link into special_fields. A row whose action provides no link key is skipped."""
    if not conn.execute("select to_regclass('public.conv_professional_link')").fetchone()[0]:
        return 0
    moved = 0
    for pid, gcid, action_key, url in conn.execute("select professional_id, gcid, action_key, url from conv_professional_link").fetchall():
        details = step_for(action_steps(conn, gcid).get(action_key), "details")
        keys = [k for k in provided_keys(details) if is_link_key(k)] if details else []
        if keys:
            set_links(conn, str(pid), {keys[0]: url})
            moved += 1
    return moved


def main() -> None:
    with psycopg.connect(os.environ.get("LOCAL_DATABASE_URL", "postgresql://localhost:5432/conversion_agent")) as conn:
        moved = move_old_rows(conn)
        businesses = conn.execute("""select p.id, p.gcid, min(d.domain) from professionals p join conv_domains d on d.professional_id = p.id
            where d.domain like '%%.example' group by p.id, p.gcid""").fetchall()
        for pid, gcid, domain in businesses:
            set_links(conn, str(pid), demo_links(conn, gcid, domain))
        conn.execute("drop table if exists conv_professional_link")
        conn.commit()
    print(f"{moved} old links moved, demo links set for {len(businesses)} businesses, conv_professional_link dropped")


if __name__ == "__main__":
    main()
