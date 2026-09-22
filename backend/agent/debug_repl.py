"""Terminal chat against the real agent, no frontend needed.

Usage:
    cd backend && .venv/bin/python -m agent.debug_repl --profile-id 2 [--route /dashboard/2]
"""

import argparse

from sqlmodel import Session

from app.db import engine
from app.models import Profile

from agent.orchestrator import get_or_create_conversation, run_turn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-id", type=int, required=True)
    parser.add_argument("--route", type=str, default="/dashboard/{id}")
    args = parser.parse_args()

    with Session(engine) as session:
        profile = session.get(Profile, args.profile_id)
        if profile is None:
            print(f"No profile with id {args.profile_id}")
            return

        conversation = get_or_create_conversation(session, profile.id)
        route = args.route.format(id=profile.id)
        page_context = {"route": route}

        print(f"Chatting as {profile.name} ({profile.lifecycle_state}) — conversation #{conversation.id}")
        print("Type a message, or 'quit' to exit.\n")

        while True:
            try:
                user_text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_text:
                continue
            if user_text.lower() in ("quit", "exit"):
                break

            result = run_turn(session, profile, conversation, user_text, page_context)
            print(f"agent> {result['reply_text']}")
            if result["ui_actions"]:
                for action in result["ui_actions"]:
                    print(f"  [ui_action] {action['type']}: {action.get('input')} -> {action.get('result')}")
            print()


if __name__ == "__main__":
    main()
