import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
AGENT_MAX_TOOL_ROUNDS = int(os.environ.get("AGENT_MAX_TOOL_ROUNDS", "6"))
AGENT_WEB_SEARCH_MAX_USES = int(os.environ.get("AGENT_WEB_SEARCH_MAX_USES", "3"))
AGENT_HTTP_TIMEOUT_SECONDS = float(os.environ.get("AGENT_HTTP_TIMEOUT_SECONDS", "8"))


class AgentNotConfiguredError(Exception):
    """Raised when a live Anthropic call is attempted with no API key set."""


_client = None


def get_client():
    global _client
    if not ANTHROPIC_API_KEY:
        raise AgentNotConfiguredError("ANTHROPIC_API_KEY is not set")
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def is_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)
