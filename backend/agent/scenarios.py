"""Scripted multi-turn sanity checks against the real agent (real API calls,
real DB). Not a strict pass/fail grader — prints full transcripts including
every tool call/result so a human (or a future Claude session) can spot-check
that stated numbers trace back to tool calls and that confirmations are
respected. Run after any prompt or tool change.

Usage:
    cd backend && .venv/bin/python -m agent.scenarios [--scenario NAME]
"""

import argparse
from datetime import datetime

from sqlmodel import Session, delete, select

from app import onboarding
from app.db import engine
from app.models import Category, CategoryService, Profile, ProfileLink, ProfileSource, Vertical

from agent.graph import delete_threads
from agent.models import AgentConversation, AgentToolInvocation
from agent.orchestrator import get_or_create_conversation, run_greeting, run_turn


def _fresh_conversation(session: Session, profile_id: int):
    """Delete any existing conversation for this profile so each scenario run
    starts clean, independent of what reset-demo/other testing left behind.
    """
    existing = session.exec(select(AgentConversation).where(AgentConversation.profile_id == profile_id)).first()
    if existing:
        session.exec(delete(AgentToolInvocation).where(AgentToolInvocation.conversation_id == existing.id))
        delete_threads([existing.id])
        session.exec(delete(AgentConversation).where(AgentConversation.id == existing.id))
        session.commit()
    return get_or_create_conversation(session, profile_id)


def _show(result):
    print(f"agent> {result['reply_text']}")
    for action in result["ui_actions"]:
        print(f"  [ui_action] {action['type']}: {action.get('input')} -> {action.get('result')}")


def _run(profile_id: int, route: str, turns: list[str]):
    with Session(engine) as session:
        profile = session.get(Profile, profile_id)
        conversation = _fresh_conversation(session, profile_id)
        page_context = {"route": route}

        print(f"\n{'=' * 70}\nScenario against {profile.name} ({profile.lifecycle_state}) at {route}\n{'=' * 70}")
        for turn in turns:
            print(f"\nyou> {turn}")
            _show(run_turn(session, profile, conversation, turn, page_context))

        session.refresh(conversation)
        print(f"\nfinal conversation outcome: {conversation.outcome}")


# --- onboarding scenarios -------------------------------------------------------------------------------
# These claim a demo professional directly (the OTP step is not what is being checked), then play the owner:
# the "owner" steps below record the same decisions the onboarding page records over REST, and the agent
# takes the turns in between. Run against a freshly reset database (`POST /api/reset-demo`).


def _claim(session: Session, profile_id: int) -> Profile:
    """The effect of a verified claim, without the email code: the verified details and the claimed state."""
    profile = session.get(Profile, profile_id)
    category = session.exec(select(Category).where(Category.name == profile.category)).one()
    vertical = session.get(Vertical, category.vertical_id)
    services = session.exec(select(CategoryService).where(CategoryService.category_id == category.id)).all()
    profile.vertical, profile.category_id = vertical.name, category.id
    profile.services = [s.key for s in services[:2]]
    profile.lifecycle_state, profile.claimed_at = "claimed", datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _onboarding(profile_id: int, steps: list, *, setup=None):
    """steps: strings are typed by the owner; callables take (session, profile) and record a decision."""
    with Session(engine) as session:
        profile = _claim(session, profile_id)
        conversation = _fresh_conversation(session, profile_id)
        page = {"route": f"/onboarding/{profile_id}"}
        print(f"\n{'=' * 70}\nOnboarding scenario: {profile.name} ({profile.category})\n{'=' * 70}")
        if setup:
            setup(session, profile)
        print("\n[arrives at onboarding]")
        _show(run_greeting(session, profile, conversation, page))
        for step in steps:
            if callable(step):
                step(session, profile)
                continue
            print(f"\nyou> {step}")
            _show(run_turn(session, profile, conversation, step, page))
            session.refresh(profile)
        print(f"\nstage: {onboarding.stage(session, profile)} | blockers: {onboarding.blockers(session, profile)}")


def _confirm(*hosts):
    def step(session, profile):
        for s in onboarding.state(session, profile)["sources"]:
            if s["status"] == "proposed":
                decision = "confirm" if any(h in s["host"] for h in hosts) else "deny"
                onboarding.decide(session, profile, s["id"], decision)
                print(f"[owner {decision}s {s['host']}]")
    return step


def _drop_known_urls(session, profile):
    for link in session.exec(select(ProfileLink).where(ProfileLink.profile_id == profile.id)).all():
        session.delete(link)
    profile.website_url = None
    session.add(profile)
    session.commit()
    print("[this person has no known URLs]")


def _answer_identity(is_mine: bool):
    def step(session, profile):
        for s in onboarding.state(session, profile)["sources"]:
            if s["status"] == "needs_identity":
                onboarding.confirm_identity(session, profile, s["id"], is_mine)
                print(f"[owner says {s['host']} {'is' if is_mine else 'is not'} theirs]")
    return step


def _wrong_person_page(session, profile):
    onboarding.start(session, profile)
    onboarding.skip_remaining_urls(session, profile)
    session.add(ProfileSource(profile_id=profile.id, url="https://www.example-team-page.test/our-people", status="needs_identity", name_validated=False,
                              raw_markdown="Our team. Meet our loan officers across the tri-state area.", extracted={"_page": {"title": "Our people"}}))
    session.commit()


def _two_pages_that_disagree(session, profile):
    """Two read pages with different titles, two licenses and two addresses: a conflict of each kind."""
    onboarding.start(session, profile)
    onboarding.skip_remaining_urls(session, profile)
    for url, extracted in (
        ("https://www.zillow.com/lender-profile/x/", {"title": "Senior Loan Officer", "license": ["NMLS # 209374", "NMLS # 777777"], "address": "197 Rt 18 South, East Brunswick, NJ 08816"}),
        ("https://www.facebook.com/x", {"title": "Loan Originator", "license": ["NMLS 209374"], "address": "55 Main Street, Edison, NJ 08817"}),
    ):
        session.add(ProfileSource(profile_id=profile.id, url=url, status="done", name_validated=True, extracted=extracted))
    session.commit()
    onboarding.merge(session, profile)


def _ready_to_finish(session, profile):
    """Known pages confirmed and merged, nothing left to settle: the owner only has to press finish."""
    onboarding.start(session, profile)
    for s in onboarding.state(session, profile)["sources"]:
        if s["host"] in ("facebook.com", "zillow.com"):
            onboarding.decide(session, profile, s["id"], "confirm")
            row = session.get(ProfileSource, s["id"])
            row.status, row.name_validated, row.extracted = "done", True, {"_page": {"title": s["host"]}, "title": "Mortgage Loan Originator"}
            session.add(row)
    session.commit()
    onboarding.skip_remaining_urls(session, profile)
    onboarding.merge(session, profile)


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
    "handoff_ineligible": lambda: _run(9, "/dashboard/9", ["Can I talk to a real human on your team?"]),
    # Onboarding (core1 Process 2). Profiles 39-46 are the demo professionals; reset the database first.
    "onboarding_confirm_urls": lambda: _onboarding(
        41, [_confirm("allstate", "google", "facebook"), "I've answered the cards for the pages I recognise."]
    ),
    "onboarding_no_urls_search": lambda: _onboarding(
        39, ["None of those were mine. Please search the web for my pages."], setup=_drop_known_urls
    ),
    "onboarding_name_mismatch": lambda: _onboarding(
        43, [_answer_identity(False), "No, that page is not mine."], setup=_wrong_person_page
    ),
    "onboarding_conflicts": lambda: _onboarding(
        43, ["Which one do you think is right? Just pick for me."], setup=_two_pages_that_disagree
    ),
    # Process 3: after onboarding, the point-valued steps and the real Pro before/after.
    "after_onboarding_plan": lambda: _onboarding(
        43, ["That all looks right — please finish.", "I accepted your drafts. Please finish now."], setup=_ready_to_finish
    ),
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
