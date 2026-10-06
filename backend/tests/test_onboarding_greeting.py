import pytest

from agent import orchestrator
from agent.models import AgentConversation
from tests.test_onboarding import claimed_profile


@pytest.fixture(autouse=True)
def fresh_db(seeded_db, mutates_db):
    yield


class FakeGraph:
    """Stands in for the LangGraph agent: remembers how many turns it was asked to run."""

    def __init__(self):
        self.messages = []

    def get_state(self, config):
        return type("State", (), {"values": {"messages": list(self.messages)}})()

    def invoke(self, payload, config):
        self.messages.append(payload["messages"][0])
        return {"ui_actions": [], "detected_outcome": None, "reply_text": "Hi there"}


def test_the_onboarding_greeting_happens_once_however_many_times_the_page_opens(session, monkeypatch):
    graph = FakeGraph()
    monkeypatch.setattr(orchestrator, "build_graph", lambda ctx: graph)
    p = claimed_profile(session)
    conversation = AgentConversation(profile_id=p.id)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)

    page = {"route": f"/onboarding/{p.id}"}
    first = orchestrator.run_greeting(session, p, conversation, page)
    second = orchestrator.run_greeting(session, p, conversation, page)  # a reload while the first was still running
    assert first["reply_text"] == "Hi there" and second["reply_text"] is None and len(graph.messages) == 1

    # Greetings elsewhere are unchanged: the dashboard greets on each visit as before.
    elsewhere = orchestrator.run_greeting(session, p, conversation, {"route": f"/dashboard/{p.id}/manage"})
    assert elsewhere["reply_text"] == "Hi there" and len(graph.messages) == 2
