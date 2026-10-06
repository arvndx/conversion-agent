import pytest

from agent.models import AgentConversation
from agent.tools import ToolContext
from agent.tools import upgrade_tools
from app.models import Profile
from tests.test_onboarding import claimed_profile


@pytest.fixture(autouse=True)
def fresh_db(seeded_db, mutates_db):
    yield


def ctx_for(session, profile):
    conversation = AgentConversation(profile_id=profile.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return ToolContext(session=session, profile=profile, conversation=conversation, page_context={})


def next_user_turn(ctx):
    ctx.conversation.turn_count += 1  # what the orchestrator does at the start of every turn


def state(session, p):
    session.expire_all()
    return session.get(Profile, p.id).lifecycle_state


def test_upgrade_needs_a_priced_proposal_and_a_yes_in_a_later_turn(session):
    p = claimed_profile(session)
    ctx = ctx_for(session, p)
    next_user_turn(ctx)  # turn 1: "please upgrade me to Pro now"
    asked = upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": True})  # even a model that sets confirmed=true
    assert asked["error"] == "needs_confirmation" and asked["monthly_price_usd"] > 0 and "offer" in asked
    assert state(session, p) == "claimed"
    again = upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": True})  # still the same turn: not consent
    assert again["error"] == "needs_confirmation" and state(session, p) == "claimed"
    next_user_turn(ctx)  # turn 2: the user answers "yes"
    done = upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": True})
    assert done["upgraded"] is True and state(session, p) == "pro"


def test_a_proposal_expires_and_cannot_be_reused(session):
    p = claimed_profile(session)
    ctx = ctx_for(session, p)
    next_user_turn(ctx)
    upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": False})  # proposed in turn 1
    for _ in range(upgrade_tools.PROPOSAL_TURNS + 1):
        next_user_turn(ctx)  # the conversation moves on
    stale = upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": True})
    assert stale["error"] == "needs_confirmation" and state(session, p) == "claimed"  # asked again, nothing happened


def test_a_trial_follows_the_same_two_steps_and_a_trial_proposal_does_not_unlock_an_upgrade(session):
    p = claimed_profile(session)
    ctx = ctx_for(session, p)
    next_user_turn(ctx)
    proposal = upgrade_tools.start_pro_trial(ctx, {"confirmed": True})
    assert proposal["error"] == "needs_confirmation" and proposal["trial_days"] == 7
    next_user_turn(ctx)
    assert upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": True})["error"] == "needs_confirmation"  # "yes" was to a trial
    assert state(session, p) == "claimed"
    next_user_turn(ctx)  # the upgrade is now the open proposal, so a trial must be proposed again before it can start
    assert upgrade_tools.start_pro_trial(ctx, {"confirmed": True})["error"] == "needs_confirmation"
    next_user_turn(ctx)
    trial = upgrade_tools.start_pro_trial(ctx, {"confirmed": True})
    assert trial["trial_started"] is True and state(session, p) == "claimed"  # a trial is not the pro state


def test_a_full_market_is_refused_straight_away_without_quoting_a_price(session):
    dentist = session.get(Profile, 37)  # San Francisco: all five Pro slots taken
    ctx = ctx_for(session, dentist)
    next_user_turn(ctx)
    out = upgrade_tools.confirm_and_upgrade_to_pro(ctx, {"confirmed": True})
    assert out["error"] == "upgrade_failed" and out["detail"]["error"] == "market_full"
    trial = upgrade_tools.start_pro_trial(ctx, {"confirmed": True})
    assert trial["error"] == "trial_failed"
