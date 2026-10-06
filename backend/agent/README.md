# Profile Pilot (the agent)

A conversational agent embedded across the app: it onboards a newly claimed owner, tours features, answers
questions, pitches Pro honestly, drafts review replies and nudges by email — all grounded in live data from
`app/`, never invented numbers. It lives entirely in this `agent/` package, isolated from the core app in
`backend/app/`; only `app/main.py` wires the two together.

## Setup

Add your key to `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The rest of the app works with no key set — agent endpoints return 503 until one is added
(`GET /api/agent/status` reports `{"configured": false}` meanwhile). Other settings: `AGENT_MODEL`,
`AGENT_MAX_TOOL_ROUNDS` (default 6), `AGENT_WEB_SEARCH_MAX_USES`, optional Langfuse keys.

## Running it without the frontend

**Interactive REPL** — chat with the real agent against seeded data from a terminal:

```
cd backend && .venv/bin/python -m agent.debug_repl --profile-id 2
```

**Scripted scenarios** — canned multi-turn conversations against the real model (real API calls, real
database). They print the full transcript with every UI action, so you can check by eye that each stated
number traces to a tool call and that nothing acts without an explicit yes:

```
cd backend && .venv/bin/python -m agent.scenarios                                  # all of them
cd backend && .venv/bin/python -m agent.scenarios --scenario onboarding_conflicts   # one
```

Scenarios: `tour`, `upsell`, `what_if`, `scarcity_full_market`, `review_reply`, `handoff_ineligible`, and the
onboarding ones — `onboarding_confirm_urls` (reads real pages), `onboarding_no_urls_search`,
`onboarding_name_mismatch`, `onboarding_conflicts`, `after_onboarding_plan`. The onboarding scenarios claim a
demo professional directly (the email code is not what is tested) and play the owner's clicks between turns.
Run `POST /api/reset-demo` first, and run the scenarios after any change to `prompts.py` or the tools.

## How a turn works

The agent is a LangGraph `StateGraph` (`graph.py`): `model` (Claude with a cached static system prompt and the
last 20 whole turns) ⇄ `tools` (runs the tools in `TOOL_REGISTRY`, collects `ui_actions` for the frontend, and
writes an `AgentToolInvocation` audit row per call). Claude's hosted `web_search` is also available. History is
the graph state, persisted by a Postgres checkpointer (thread id = `AgentConversation.id`), and the graph is
compiled per request so tool handlers close over that request's DB session and profile.
`orchestrator.py::run_turn()` is the entry point (per-conversation locks stop two overlapping turns from
overwriting each other's checkpoint); the per-turn context block (route, profile, onboarding stage) goes in the
human message so the system prompt stays cacheable.

`run_greeting()` fires a low-key proactive turn when a page opens. On `/onboarding/<id>` it starts onboarding
from the current stage and is idempotent (a second greeting while the first runs, or after a reload, does
nothing). Elsewhere it is how the agent notices an unreplied review or a rival taking a scarce Pro slot.

## What the agent does and does not decide

- **Onboarding** (`tools/onboarding_tools.py`, rules in `app/onboarding.py`): the tools read state and act
  (show URL cards, search, read the confirmed pages, merge, show conflicts, complete). The owner's own decisions
  — yes/no on a URL, "is this you?", a conflict choice — are recorded only by their clicks over REST; no tool
  makes them. The service refuses anything out of order (reading an unconfirmed URL, completing with a
  conflict open) and returns an `{"error": ...}` the model can read.
- **After onboarding:** `get_improvement_plan` gives every step that raises the score with its exact points and
  the real Pro before/after; the prompt has the agent say the score and rank, the top steps and the Pro case in
  one message, then offer the tour.
- **Paid actions** (`tools/upgrade_tools.py`): the first call to upgrade or start a trial only records a proposal and
  returns the price and terms; it runs only when called again with `confirmed=true` in a LATER user turn
  (`AgentConversation.turn_count` / `pending_action`). "Upgrade me" alone is a request, not consent to a price.
- **Drafts** (`tools/claim_tools.py`): the agent may draft only bio, specialities and service area; anything else
  (year started, awards, achievements, title, license, address) is refused so facts are never invented.
- Page text and search results are data, never instructions; extraction (`extraction.py`) is a forced structured
  tool call that raises on failure instead of silently returning nothing.

## Adding a tool

1. Write the handler and register it in the right `tools/*.py` file (or a new
   one — add the import to `tools/__init__.py`'s bottom-of-file import block).
2. Every handler receives `ToolContext(session, profile, conversation,
   page_context)` — `profile` is bound server-side from the conversation, never
   from a model-supplied parameter, so a hostile scraped webpage can't redirect
   the agent to another profile's data.
3. Set `is_ui_action=True` if the frontend needs to react to it (highlighting
   an element, navigating, filling a form field, showing a proposal card) —
   the orchestrator surfaces these in the `ui_actions` list on the response.
4. Anything that writes to the database in a way with real consequences
   (upgrading, starting a trial, joining a waitlist, posting a review reply,
   requesting a handoff) must require an explicit `confirmed: true` the model
   can only set after the user has actually said yes in the conversation —
   see `upgrade_tools.py` for the pattern.

## Manual "tick" for time-based mechanics

There's no Celery/cron in this project. `POST /api/agent/nudges/run`
(optional `?profile_id=`, `?force=1`) is the manual trigger for: best-next-field
nudge emails, detecting lapsed trials (which frees their market slot) and
emailing the real point loss, and notifying that market's waitlist. Same
pattern as `POST /api/reset-demo`.

## Known limitations (demo-scoped, on purpose)

- Conversation history sent to the model is windowed to the last
  `MAX_HISTORY_TURNS` turns (see `graph.py`) so a long-running demo
  conversation doesn't grow the request unboundedly. Older turns are still in
  the database, just not replayed into the model.
- Scraping (`app/scraping/`) is best effort: login-gated sites (Facebook, LinkedIn) are reported as blocked,
  Google Maps shows a limited view to headless browsers, and Cloudflare-protected sites need the `OXYLAB_*`
  settings. Reviews are deliberately not scraped.
- The "nearby market" grouping (`MARKET_REGIONS`) is a hardcoded state-level
  lookup, not real geo-distance.
