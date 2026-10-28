"""Load the tools and the steps of the actions into the local database, from db/demo/tool_data.json.

  conv_tool    the tools the agent can use: name, description, inputs
  conv_action  per action: its goal, its request_type (the label saved on its requests), whether it is on, and its steps (the
               routes in order, each with its tools, what to collect from the visitor and what it provides). See
               shared/tool_checks.py for the shape. The "general" actions (gcid general) are the situations that end in a
               handover without a business button: a critical question, the AI being down, a reply that failed its checks,
               and a visitor who asks for a person.

An action the file does not list keeps no steps, and the checks report it. Run by seed_demo, or on its own on a database
that already has the conv_ tables (the run is repeatable):
  LOCAL_DATABASE_URL=postgresql://localhost:5432/conversion_agent PYTHONPATH=. .venv/bin/python -m db.demo.seed_actions
"""

import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from shared.tool_checks import check_database

DATA_FILE = Path(__file__).resolve().parent / "tool_data.json"


def load(conn: psycopg.Connection) -> tuple[int, int, int]:
    """Write the tools, the actions' steps, goals, request types and on/off state, and the general actions. Returns (tools,
    actions, general actions) written."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for tool in data["tools"]:
        conn.execute("""insert into conv_tool (name, description, inputs) values (%s, %s, %s)
            on conflict (name) do update set description = excluded.description, inputs = excluded.inputs, updated_at = now()""",
                     (tool["name"], tool["description"], Jsonb(tool["inputs"])))
    conn.execute("delete from conv_tool where name <> all(%s)", ([t["name"] for t in data["tools"]],))   # a tool the file no longer lists
    written = 0
    for gcid, actions in data["actions"].items():
        for key, action in actions.items():
            done = conn.execute("""update conv_action set steps = %s, enabled = %s, agent_goal = coalesce(%s, agent_goal),
                request_type = %s, updated_at = now() where gcid = %s and action_key = %s""",
                                (Jsonb(action["steps"]), action.get("enabled", True), action.get("goal"), action["request_type"],
                                 gcid, key))
            if done.rowcount != 1:
                raise SystemExit(f"{DATA_FILE.name} lists {gcid} / {key}, which is not in conv_action")
            written += 1
    for key, action in data["general_actions"].items():
        conn.execute("""insert into conv_action (gcid, action_key, source_entity_type, action_name, schema_action, agent_goal,
            steps, enabled, source, request_type) values ('general', %s, 'professional', %s, 'CommunicateAction', %s,
            %s, true, 'custom', %s)
            on conflict (gcid, action_key) do update set action_name = excluded.action_name, agent_goal = excluded.agent_goal,
            steps = excluded.steps, request_type = excluded.request_type, updated_at = now()""",
                     (key, action["action_name"], action["goal"], Jsonb(action["steps"]), action["request_type"]))
    return len(data["tools"]), written, len(data["general_actions"])


def main() -> None:
    with psycopg.connect(os.environ.get("LOCAL_DATABASE_URL", "postgresql://localhost:5432/conversion_agent")) as conn:
        tools, actions, general = load(conn)
        problems = check_database(conn)
        if problems:
            conn.rollback()
            raise SystemExit("not saved:\n" + "\n".join(problems))
        conn.commit()
    print(f"{tools} tools, {actions} actions and {general} general actions written")


if __name__ == "__main__":
    main()
