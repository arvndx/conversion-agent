"""Fixed replies, chosen before any model call.

A visitor's whole message ("hi", "thanks!", "are you a bot?", "bye") is matched against the patterns of the category's fixed
replies (conv_static_reply, in the category bundle as static_replies). A match gets one of the intent's ten or more replies at
random, never the one used last time in this chat. A message that says more than the pattern ("hi, can you quote me a rate")
is not a match and goes on to the safety check and the agent.

The code also asks for a reply by intent where no visitor phrase triggers it: the warning for an abusive message
(abuse_warning) and the apology before a handover offer (fallback_apology).
"""

import json
import random
import re

from pipeline.load_chat import session_key

FILLERS = {"there", "again", "please", "pls", "bot", "assistant", "team"}   # words that may sit around a pattern
MAX_FILLERS = 2
MAX_WORDS = 8
# An answer to a question the assistant just asked ("ok", "sounds good") belongs to the agent, which knows the question.
ANSWER_SENSITIVE = {"acknowledgement"}


def normalise(text: str) -> str:
    """Lower case, apostrophes dropped, every other mark a space: "What's up?!" gives "whats up"."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower().replace("'", "").replace("’", "")).split())


def _index(static_replies: dict) -> dict[str, str]:
    return {phrase: intent for intent, row in static_replies.items() for phrase in row.get("patterns") or []}


def match(message: str, static_replies: dict, after_question: bool = False) -> str | None:
    """The intent whose pattern is this whole message (with up to two filler words around it), or None."""
    words = normalise(message).split()
    if not words or len(words) > MAX_WORDS:
        return None
    index = _index(static_replies)
    for start in range(0, MAX_FILLERS + 1):
        for end in range(0, MAX_FILLERS + 1 - start):
            kept = words[start:len(words) - end]
            if not kept or any(w not in FILLERS for w in words[:start] + words[len(words) - end:]):
                continue
            intent = index.get(" ".join(kept))
            if intent and not (after_question and intent in ANSWER_SENSITIVE):
                return intent
    return None


def pick(client, session_id: str, intent: str, static_replies: dict) -> str | None:
    """One reply for the intent, different from the one used last in this chat. None when the category has none."""
    replies = (static_replies.get(intent) or {}).get("replies") or []
    if not replies:
        return None
    field = f"static_last_{intent}"
    last = client.hget(session_key(session_id), field)
    choices = [i for i in range(len(replies)) if str(i) != last] or list(range(len(replies)))
    index = random.choice(choices)
    client.hset(session_key(session_id), field, index)
    return replies[index]


def asked_a_question(session: dict) -> bool:
    """The assistant's last reply in this chat ended with a question."""
    turns = json.loads(session.get("conversation") or "[]")
    return bool(turns) and (turns[-1].get("response") or "").rstrip().endswith("?")
