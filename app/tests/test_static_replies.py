"""Fixed replies (pipeline/static_replies.py): a whole message that is a greeting, thanks, goodbye, apology or "are you a bot?" gets
one of ten or more replies, with no model call. A message that says more goes on to the safety check and the agent.
Run from the app folder: uv run pytest tests/test_static_replies.py"""

import uuid

import psycopg
import pytest

from pipeline import static_replies
from pipeline.load_chat import DATABASE_URL, redis_client, session_key
from shared.bundle_tables import load_category
from shared.tool_checks import MATCHED_INTENTS, TRIGGERED_INTENTS

CATEGORIES = ["gcid:american_restaurant", "gcid:commercial_real_estate_agency", "gcid:health_insurance_agency",
              "gcid:mortgage_broker", "gcid:mortgage_lender"]


@pytest.fixture(scope="module")
def bundles():
    with psycopg.connect(DATABASE_URL) as conn:
        return {g: load_category(conn, g)["static_replies"] for g in CATEGORIES}


@pytest.fixture()
def sid():
    session_id, client = str(uuid.uuid4()), redis_client()
    yield session_id
    client.delete(session_key(session_id))


STATIC = {"greeting": {"patterns": ["hi", "hello", "good morning"], "replies": ["Hello!", "Hi there!"]},
          "thanks": {"patterns": ["thanks", "thank you"], "replies": ["You're welcome!"]},
          "ai_identity": {"patterns": ["are you a bot", "whats your name"], "replies": ["I'm an AI."]},
          "acknowledgement": {"patterns": ["ok", "sounds good"], "replies": ["Great."]},
          "abuse_warning": {"patterns": [], "replies": ["Please be respectful."]}}


@pytest.mark.parametrize("text, intent", [
    ("hi", "greeting"), ("Hello!", "greeting"), ("  GOOD MORNING  ", "greeting"), ("hi there", "greeting"),
    ("Hello, bot!", "greeting"), ("hello again please", "greeting"), ("thanks!!", "thanks"), ("Thank you.", "thanks"),
    ("Are you a bot?", "ai_identity"), ("what's your name", "ai_identity"), ("What’s your name?", "ai_identity"),
])
def test_a_whole_message_that_is_a_known_phrase_is_matched(text, intent):
    assert static_replies.match(text, STATIC) == intent


@pytest.mark.parametrize("text", [
    "hi, can you quote me a rate", "thanks, and what are your hours", "hello I want to book a table", "buy", "hii", "",
    "!!!", "hi hi hi hi hi hi hi hi hi", "are you a bot or can I talk to the broker", "good morning team please there again",
])
def test_a_message_that_says_more_is_not_matched(text):
    assert static_replies.match(text, STATIC) is None


def test_an_intent_the_code_triggers_itself_is_never_matched_from_a_message():
    assert static_replies.match("Please be respectful.", STATIC) is None


def test_an_answer_to_a_question_is_left_to_the_agent():
    assert static_replies.match("ok", STATIC) == "acknowledgement"
    assert static_replies.match("ok", STATIC, after_question=True) is None
    assert static_replies.match("hi", STATIC, after_question=True) == "greeting"   # a greeting is still a greeting
    assert static_replies.asked_a_question({"conversation": '[{"request": ["a"], "response": "Which day works?"}]'}) is True
    assert static_replies.asked_a_question({"conversation": '[{"request": ["a"], "response": "We open at 9."}]'}) is False
    assert static_replies.asked_a_question({}) is False


def test_the_same_reply_is_not_given_twice_in_a_row(sid):
    client = redis_client()
    seen = [static_replies.pick(client, sid, "greeting", STATIC) for _ in range(12)]
    assert set(seen) == {"Hello!", "Hi there!"} and all(a != b for a, b in zip(seen, seen[1:]))


def test_a_single_reply_is_given_again_and_an_unknown_intent_gives_none(sid):
    client = redis_client()
    assert [static_replies.pick(client, sid, "thanks", STATIC) for _ in range(3)] == ["You're welcome!"] * 3
    assert static_replies.pick(client, sid, "no_such_intent", STATIC) is None


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_every_category_has_ten_or_more_replies_for_every_intent(bundles, gcid):
    replies = bundles[gcid]
    assert set(MATCHED_INTENTS + TRIGGERED_INTENTS) <= set(replies)
    assert all(len(row["replies"]) >= 10 for row in replies.values())
    assert all(row["patterns"] for intent, row in replies.items() if intent in MATCHED_INTENTS)


@pytest.mark.parametrize("gcid", CATEGORIES)
def test_the_patterns_of_a_category_match_their_own_intent_and_no_other(bundles, gcid):
    replies = bundles[gcid]
    for intent in MATCHED_INTENTS:
        for phrase in replies[intent]["patterns"]:
            assert static_replies.match(phrase, replies) == intent, phrase
            assert static_replies.match(phrase.upper() + "!", replies) == intent, phrase


@pytest.mark.parametrize("text, intent", [
    ("hi", "greeting"), ("thank you so much", "thanks"), ("bye", "goodbye"), ("are you a human?", "ai_identity"),
    ("sorry about that", "apology"), ("how are you", "how_are_you"), ("is this chat recorded", "privacy"),
    ("just browsing", "just_browsing"), ("what do you mean", "unclear"),
])
def test_everyday_messages_get_the_right_intent_in_every_category(bundles, text, intent):
    assert all(static_replies.match(text, replies) == intent for replies in bundles.values())


def test_a_message_about_the_business_is_never_a_fixed_reply(bundles):
    for text in ["do you have vegetarian options", "what are your hours", "I want to book a table", "can I talk to a person",
                 "what is today's rate", "how much is the burger", "yes", "no", "yes please"]:
        assert all(static_replies.match(text, replies) is None for replies in bundles.values()), text


def test_the_replies_name_the_business_only_through_the_placeholders(bundles):
    for replies in bundles.values():
        for row in replies.values():
            for reply in row["replies"]:
                assert "{" not in reply.replace("{customer_name}", "").replace("{category}", "")
