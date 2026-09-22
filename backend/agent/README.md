# ClearRank Conversion Agent

A conversational agent embedded across the app that tours features, answers
questions, pitches Pro honestly, helps unclaimed users through claiming, drafts
review replies, and nudges users by email — all grounded in live data from
`app/`, never invented numbers. Lives entirely in this `agent/` package,
isolated from the core CRUD app in `backend/app/`.

## Setup

Add your key to `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The rest of the app works with no key set — only agent endpoints 503 until
one is added (`GET /api/agent/status` reports `{"configured": false}` in the
meantime).

## Running it without the frontend

**Interactive REPL** — chat with the real agent against real seeded data from
a terminal:

```
cd backend && .venv/bin/python -m agent.debug_repl --profile-id 2
```

**Scripted scenarios** — a handful of canned multi-turn conversations that
exercise the main flows (tour, upsell, what-if simulation, a full market
refusing an upgrade, review-reply drafting, claim-assist, and an ineligible
handoff request). Prints the full transcript including every tool call and
result, so you can verify by eye that every stated number traces back to a
tool call and that nothing acts without explicit confirmation:

```
cd backend && .venv/bin/python -m agent.scenarios                    # all of them
cd backend && .venv/bin/python -m agent.scenarios --scenario upsell   # just one
```

Run this after any change to `prompts.py` or the tools.

## How a turn works

`orchestrator.py::run_turn()` — a manual loop over `client.messages.create`
(not the Anthropic SDK's Tool Runner, which doesn't expose its message history
and has gaps around `pause_turn`; a manual loop keeps everything replayable).
Each round: call the API with the full tool set (Claude's hosted `web_search`
plus every tool in `TOOL_REGISTRY`), persist the raw response verbatim, run any
custom tool calls, persist results, loop until there are none left. Every
message — including tool calls and results — is stored in `AgentMessage`, so a
conversation can be fully replayed or inspected later via
`GET /api/agent/conversations/{profile_id}`.

`run_greeting()` fires a low-key proactive turn the first time a profile's
conversation sees a given route (tracked in `AgentConversation.greeted_routes`)
— this is how the agent notices an unreplied review or a competitor taking a
scarce Pro slot without the user asking.

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
  `MAX_HISTORY_TURNS` turns (see `orchestrator.py`) so a long-running demo
  conversation doesn't grow the request unboundedly. Older turns are still in
  the database, just not replayed into the model.
- `fetch_and_extract_website`'s phone/hours extraction is regex/heuristic, not
  a real HTML-structure-aware parser — fine for a demo, would need real
  business-listing parsing logic for production use.
- The "nearby market" grouping (`MARKET_REGIONS`) is a hardcoded state-level
  lookup, not real geo-distance.
