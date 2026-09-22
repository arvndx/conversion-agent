# ClearRank

A local, no-auth clone of an experience.com-style local-business directory (search, public
profiles, a claim flow, a dashboard with a "Search Rank Score," and a Pro upgrade path) —
built as a testbed for **Profile Pilot**, an embedded conversational agent that actually
drives the product: it finds and verifies a business's real details during claim, runs a
guided product tour, makes an honest case for upgrading to Pro, and drafts review replies.

There's no login. The profile ID in the URL *is* the identity — this is a demo, not a
real multi-tenant app.

## Quick start

**Backend** (FastAPI + SQLite):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend** (React + Vite), in a second terminal:

```bash
cd frontend
npm install
./node_modules/.bin/vite --port 5173   # `npm run dev` also works
```

Open **http://localhost:5173**. The database seeds itself automatically on first backend
startup — nothing else to run.

Without `ANTHROPIC_API_KEY` set, the rest of the app still works; every agent-backed
endpoint degrades to a clean `503` instead of failing the whole page.

## Tech stack

| | |
|---|---|
| Backend | FastAPI, SQLModel (SQLAlchemy) + SQLite, Anthropic Python SDK |
| Agent web search | Claude's hosted `web_search` tool — no separate search API/key |
| Scraping | `httpx` + `BeautifulSoup4` (plain code, no LLM) — fetches a page only after the user confirms it's theirs |
| Frontend | React 19, React Router 7, Vite 8 — no UI framework, hand-rolled inline-styled components |
| Maps | Leaflet + OpenStreetMap tiles — real maps, no Maps API key/billing |
| Auth | None by design |

## Project structure

```
backend/
  app/                    # the product — profiles, search, scoring, dashboard, pricing
    models.py               # Profile and friends (SQLModel tables)
    scoring.py               # Search Rank Score computation + what-if simulation
    suggestions.py            # real point-delta suggestions shown on the Manage page
    seed.py                    # deterministic demo data (same seed → same data every reset)
    routers/                    # search, profiles, dashboard, manage, pricing, inbox, admin
  agent/                  # Profile Pilot — isolated from app/, only main.py wires them together
    orchestrator.py          # run_turn() — the manual Claude tool-calling loop
    prompts.py                 # system prompt + per-turn context block
    tour_content.py              # pre-generates all guided-tour steps in one batch call
    webextract.py                  # deterministic page fetch/parse for claim-assist
    tools/                          # scoring_tools, claim_tools, ui_tools, upgrade_tools, …
  clearrank.db            # SQLite file (gitignored) — delete + restart to reset schema

frontend/
  src/
    routes/                # one component per page (SearchPage, DashboardPage, ClaimDetailsPage, …)
    components/agent/         # the floating assistant panel + guided-tour spotlight
    components/manage/          # Manage-page sections + suggestion cards
    context/                       # AgentUIBridgeContext (page ↔ agent), AgentPanelContext (panel layout)
```

## Core ideas

- **The agent never states a number it didn't just look up.** The context block built into
  every turn is deliberately non-numeric; every score, rank, or point value the agent says
  out loud has to come from a tool call earlier in that same turn.
- **Proposing is free, committing needs a real "yes."** Upgrading to Pro, starting a trial,
  filling a claim-form field, posting a review reply — the agent can always suggest, never
  apply, without the user's explicit confirmation in that turn.
- **Scarcity is real, not decorative.** Each (category, location) market has exactly 5 Pro
  slots (`PRO_SLOTS_PER_MARKET`), enforced server-side for both the UI's Upgrade button and
  the agent's own tool — a full market is genuinely refused and offered a waitlist instead.
- **Everything mocked is labeled as mocked.** OTP emails, review-reply "sending," executive
  handoff — all live in a mock inbox (`/inbox`) and are never presented as real.

## The Search Rank Score

Claimed profiles score out of 500; Pro (or an active trial) unlocks two more categories for
850:

| Category | Points | Locked until Pro? |
|---|---|---|
| Reviews & Replies | 300 | No |
| Profile Completion | 100 | No |
| Connections | 100 | No |
| Website Health | 250 | Yes |
| Listings | 100 | Yes |

Website Health is a real (seeded) audit of the profile's own website — load time, mobile
friendliness, meta description, contact info, business hours — not traffic/click metrics.

## Resetting demo data

```bash
curl -X POST http://localhost:8000/api/reset-demo
```

Re-seeds every profile from `seed.py` and clears all agent conversation history. Seeding is
deterministic (seeded RNG), so the same profile always gets the same reviews, scores, and
audit results across resets.

## Testing

- `python -m agent.debug_repl --profile-id 2` — terminal chat against the real agent, no
  frontend needed.
- `python -m agent.scenarios` — scripted multi-turn conversations that flag any stated
  number not backed by a tool call.
- No frontend test suite; UI changes are verified by hand in a browser (Playwright scripts
  used ad hoc during development, not checked in as a suite).
