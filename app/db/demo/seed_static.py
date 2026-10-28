"""Load the fixed replies and the new dialogue messages into the local database, from db/demo/static_data.json.

  conv_static_reply          the replies (10 or more per intent) for greetings, thanks, goodbye, apology, "are you a bot?" and
                             similar, under the shared gcid "general" (a category can add its own row for an intent to replace
                             it). The patterns are the whole messages that trigger an intent; the code triggers abuse_warning
                             and fallback_apology itself, so they have none.
  conv_category_settings     the messages for the request form (form_intro, request_sent, request_not_saved, ...) are added to
                             every category's other_messages

Run by seed_demo, or on its own on a database that already has the conv_ tables (the run is repeatable):
  LOCAL_DATABASE_URL=postgresql://localhost:5432/conversion_agent PYTHONPATH=. .venv/bin/python -m db.demo.seed_static
"""

import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from shared.tool_checks import check_database

DATA_FILE = Path(__file__).resolve().parent / "static_data.json"


def load(conn: psycopg.Connection) -> tuple[int, int]:
    """Write the shared replies and the messages. Returns (intents, categories updated)."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for intent, row in data["intents"].items():
        conn.execute("""insert into conv_static_reply (gcid, intent, patterns, replies) values ('general', %s, %s, %s)
            on conflict (gcid, intent) do update set patterns = excluded.patterns, replies = excluded.replies, updated_at = now()""",
                     (intent, row["patterns"], row["replies"]))
    done = conn.execute("update conv_category_settings set other_messages = other_messages || %s, updated_at = now()",
                        (Jsonb(data["messages"]),))
    return len(data["intents"]), done.rowcount


def main() -> None:
    with psycopg.connect(os.environ.get("LOCAL_DATABASE_URL", "postgresql://localhost:5432/conversion_agent")) as conn:
        intents, categories = load(conn)
        problems = check_database(conn)
        if problems:
            conn.rollback()
            raise SystemExit("not saved:\n" + "\n".join(problems))
        conn.commit()
    print(f"{intents} intents written; messages added to {categories} categories")


if __name__ == "__main__":
    main()
