"""Scripted multi-turn sanity checks against the real agent (real API calls,
real DB). Not a strict pass/fail grader — prints full transcripts including
every tool call/result so a human (or a future Claude session) can spot-check
that stated numbers trace back to tool calls and that confirmations are
respected. Run after any prompt or tool change.

Usage:
    cd backend && .venv/bin/python -m agent.scenarios [--scenario NAME]
"""

import argparse

from sqlmodel import Session, delete, select

from app.db import engine
from app.models import Profile

from agent.models import AgentConversation, AgentMessage, AgentToolInvocation
from agent.orchestrator import get_or_create_conversation, run_turn


def _fresh_conversation(session: Session, profile_id: int):
    """Delete any existing conversation for this profile so each scenario run
    starts clean, independent of what reset-demo/other testing left behind.
    """
    existing = session.exec(select(AgentConversation).where(AgentConversation.profile_id == profile_id)).first()
    if existing:
        session.exec(delete(AgentToolInvocation).where(AgentToolInvocation.conversation_id == existing.id))
        session.exec(delete(AgentMessage).where(AgentMessage.conversation_id == existing.id))
        session.exec(delete(AgentConversation).where(AgentConversation.id == existing.id))
        session.commit()
    return get_or_create_conversation(session, profile_id)


def _run(profile_id: int, route: str, turns: list[str]):
    with Session(engine) as session:
        profile = session.get(Profile, profile_id)
        conversation = _fresh_conversation(session, profile_id)
        page_context = {"route": route}

        print(f"\n{'=' * 70}\nScenario against {profile.name} ({profile.lifecycle_state}) at {route}\n{'=' * 70}")
        for turn in turns:
            print(f"\nyou> {turn}")
            result = run_turn(session, profile, conversation, turn, page_context)
            print(f"agent> {result['reply_text']}")
            for action in result["ui_actions"]:
                print(f"  [ui_action] {action['type']}: {action.get('input')} -> {action.get('result')}")

        session.refresh(conversation)
        print(f"\nfinal conversation outcome: {conversation.outcome}")


SCENARIOS = {
    "tour": lambda: _run(2, "/dashboard/2", ["What can you help me with?", "Why is my score low?"]),
    "upsell": lambda: _run(
        2, "/dashboard/2", ["What would upgrading to Pro actually get me?", "Are there any spots left in my market?"]
    ),
    "what_if": lambda: _run(2, "/dashboard/2", ["What if I added my website and license number?"]),
    "scarcity_full_market": lambda: _run(
        37, "/dashboard/37", ["I want to upgrade to Pro right now, yes I confirm."]
    ),
    "review_reply": lambda: _run(
        2, "/dashboard/2/manage", ["Do I have any reviews I haven't replied to? If so, draft a reply."]
    ),
    "claim_assist": lambda: _run(
        5,
        "/claim/5/details",
        ["I run Smile Bright Dental in Seattle. Can you help me find my business info?"],
    ),
    "handoff_ineligible": lambda: _run(9, "/dashboard/9", ["Can I talk to a real human on your team?"]),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), default=None)
    args = parser.parse_args()

    names = [args.scenario] if args.scenario else sorted(SCENARIOS.keys())
    for name in names:
        SCENARIOS[name]()


if __name__ == "__main__":
    main()
