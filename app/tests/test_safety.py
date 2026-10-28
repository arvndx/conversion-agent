"""The safety check (pipeline/classify.py): the prompt, the parser and the one retry. The model is replaced by a fake client.
Run from the app folder: uv run pytest tests/test_safety.py"""

import json
import pathlib
from types import SimpleNamespace

import pytest

from pipeline.classify import ClassifyError, SAFETY_MODEL, _checked, build_safety_prompt, parse_safety

CATEGORY_FILE = pathlib.Path(__file__).resolve().parent.parent / "shared/samples/restaurant_category.json"


@pytest.fixture(scope="module")
def category():
    return json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))


def answer(**fields) -> str:
    base = {"critical": "no", "critical_topic": None, "abusive": False}
    base.update(fields)
    return json.dumps(base)


class SequenceClient:
    """Gives the safety call a list of answers in turn (an Exception in the list is raised), and counts the calls."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), 0
        self.messages = self

    def create(self, model, system, messages, **kwargs):
        assert system[0]["cache_control"] == {"type": "ephemeral"}, "the system prompt must be marked for caching"
        self.calls += 1
        item = self.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=item)])


def check(category, client, message="hello"):
    system, user = build_safety_prompt(category, message)
    return _checked(SAFETY_MODEL, system, user, parse_safety, category, client)


def test_a_good_answer_is_parsed(category):
    result = parse_safety(answer(), category)
    assert (result.critical, result.critical_topic, result.abusive) == ("no", None, False)


def test_an_emergency_names_its_critical_topic(category):
    topic = category["critical_topics"][0]["id"]
    result = parse_safety(answer(critical="yes", critical_topic=topic), category)
    assert result.critical == "yes" and result.critical_topic == topic


def test_code_fenced_json_is_accepted(category):
    assert parse_safety("```json\n" + answer(abusive=True) + "\n```", category).abusive is True


@pytest.mark.parametrize("bad", [
    answer(critical="maybe"),
    answer(critical="yes", critical_topic=None),
    answer(critical="yes", critical_topic="not_a_topic"),
    answer(abusive="maybe"),
    "not json at all",
    "[1, 2]",
])
def test_a_bad_answer_is_refused(category, bad):
    with pytest.raises(ClassifyError):
        parse_safety(bad, category)


def test_the_prompt_uses_the_raw_message_and_the_critical_topics(category):
    system, user = build_safety_prompt(category, "my chest hurts")
    assert "medical_emergency" in system
    assert "Not critical, even though they use the same words" in system
    assert "my chest hurts" in user


def test_one_badly_formatted_answer_is_retried_once(category):
    client = SequenceClient(["Sure, here you go!", answer()])
    assert check(category, client).critical == "no"
    assert client.calls == 2


def test_two_badly_formatted_answers_fail(category):
    client = SequenceClient(["not json", "still not json"])
    with pytest.raises(ClassifyError):
        check(category, client)
    assert client.calls == 2


def test_an_api_error_is_not_retried(category):
    client = SequenceClient([RuntimeError("timeout")])
    with pytest.raises(RuntimeError):
        check(category, client)
    assert client.calls == 1
