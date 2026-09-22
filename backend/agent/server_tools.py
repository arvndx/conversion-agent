from agent.config import AGENT_WEB_SEARCH_MAX_USES

# Anthropic-hosted (server-side) tool — resolved by Claude itself, not by our code.
# See https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": AGENT_WEB_SEARCH_MAX_USES,
}
