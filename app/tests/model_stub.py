"""A stand-in for the model, for the tests that go through the chat API. The safety check and the agent are replaced, so a test
decides what the model says and counts how often it is called. Nothing here calls the real model."""

from types import SimpleNamespace

from pipeline import agent as chat_agent
from pipeline.classify import SafetyResult


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(name, args, block_id="tool_1"):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=args)


def response(*blocks):
    stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


class ScriptedModel:
    """The agent's model: returns the scripted answers in order (the last one repeats), and records every call."""

    def __init__(self, answers=None):
        self.answers = list(answers or [response(text_block("Noted, thank you."))])
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


class Safety:
    """The safety check: returns the same result each time (ordinary by default), or None, and counts the calls."""

    def __init__(self, result=None):
        self.result = result if result is not None else SafetyResult("no", None, False)
        self.calls = []

    def __call__(self, category, message, client=None):
        self.calls.append(message)
        return self.result


def install(monkeypatch, answers=None, safety=None) -> tuple[ScriptedModel, Safety]:
    """Replace the safety check and the agent's model. Returns (model, safety) so a test can read the calls."""
    model = ScriptedModel(answers)
    check = Safety(safety)
    monkeypatch.setattr(chat_agent, "safety_check", check)
    monkeypatch.setattr(chat_agent, "_default_client", lambda: model)
    return model, check


class NoModel(ScriptedModel):
    """A model that must never be called: any call fails the test."""

    def _create(self, **kwargs):
        raise AssertionError("the model was called")


def install_no_model(monkeypatch):
    """The click, the form and the fixed replies make no model call: neither the safety check nor the agent may run."""
    def forbidden(*args, **kwargs):
        raise AssertionError("the safety check was called")
    monkeypatch.setattr(chat_agent, "safety_check", forbidden)
    monkeypatch.setattr(chat_agent, "_default_client", lambda: NoModel())
