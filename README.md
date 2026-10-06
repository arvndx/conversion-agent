# ClearRank

A local clone of an experience.com-style local-business directory (search, public profiles, a claim
flow, a dashboard with a category-specific "Search Rank Score," and a Pro upgrade path) — built as a
testbed for **Profile Pilot**, an embedded conversational agent that actually drives the product. After a
profile is claimed it **onboards** the owner (finds and reads their real web pages, checks they are theirs,
settles conflicts), then shows what would raise the score and the real before/after of going Pro, runs a
guided product tour, and drafts review replies.

Agents **claim** a profile from a search result ("Claim now") or with the header's "Claim a profile",
verify a 6-digit code (delivered to that person's mock mailbox, `/mailbox/<email>`), and afterwards
**sign in** with an email code. Owner pages (dashboard, manage, pricing, the agent) need that session;
unclaimed profiles and search stay public. With `DEMO_MODE=true` (the default) the sign-in page and the
"Viewing as" menu also offer ready-made demo accounts that skip the code.

## Quick start

**Database** (PostgreSQL 15+): create a role and database once. With Homebrew Postgres running:

```bash
psql -d postgres -c "CREATE ROLE clearrank LOGIN PASSWORD 'clearrank'" -c "CREATE DATABASE clearrank OWNER clearrank"
# or with Docker:
# docker run -d --name clearrank-pg -p 5432:5432 -e POSTGRES_USER=clearrank -e POSTGRES_PASSWORD=clearrank -e POSTGRES_DB=clearrank postgres:15
```

The default `DATABASE_URL` matches that role; override it in `backend/.env` for anything else.

**Backend** (FastAPI):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY (Langfuse keys are optional)
uvicorn app.main:app --reload --port 8000
```

**Frontend** (React + Vite), in a second terminal:

```bash
cd frontend
npm install
./node_modules/.bin/vite --port 5173   # `npm run dev` also works
```

Open **http://localhost:5173**. The tables are created and the database seeds itself automatically on first backend
startup — nothing else to run.

Without `ANTHROPIC_API_KEY` set, the rest of the app still works; every agent-backed
endpoint degrades to a clean `503` instead of failing the whole page.

## Tech stack

| | |
|---|---|
| Backend | FastAPI, SQLModel (SQLAlchemy) + PostgreSQL (psycopg 3, JSONB columns) |
| Agent | LangGraph 1.2 (`StateGraph`: model ⇄ tools) on `langchain-anthropic`; history in a Postgres checkpointer; optional Langfuse tracing |
| Agent web search | Claude's hosted `web_search` tool — no separate search API/key |
| Scraping | `httpx` → Playwright (headless Chromium) → proxied render, through an Oxylabs proxy when a site blocks us; `BeautifulSoup4` + `markdownify`; Claude structured extraction. Runs live in the backend and reads a page only after the owner confirms it's theirs |
| Frontend | React 19, React Router 7, Vite 8 — no UI framework, hand-rolled inline-styled components |
| Maps | Leaflet + OpenStreetMap tiles — real maps, no Maps API key/billing |
| Auth | Email-OTP sign-in, HttpOnly session cookie (mock mailbox instead of real email) |

## Project structure

```
backend/
  app/                    # the product — profiles, search, scoring, dashboard, pricing
    models.py               # Profile and friends (SQLModel tables)
    scoring.py               # Search Rank Score computation + what-if simulation
    suggestions.py            # real point-delta suggestions shown on the Manage page
    seed.py                    # deterministic demo data (same seed → same data every reset)
    routers/                    # search, profiles, taxonomy, claims, auth, mailbox, dashboard, manage, pricing, admin
    claims.py / auth.py         # claim rules + OTP, sessions (HttpOnly cookie), access guard
    onboarding.py               # onboarding state machine: URLs, scrape, identity, merge, conflicts, completion
    scraping/                   # live page fetch (direct -> browser via Oxylabs proxy -> proxied render request), parse, identity check
  agent/                  # Profile Pilot — isolated from app/, only main.py wires them together
    graph.py                  # the LangGraph agent graph, checkpointer, history load/reset
    orchestrator.py          # run_turn()/greeting/tour entry points, per-conversation locks
    prompts.py                 # system prompt + per-turn context block
    tour_content.py              # pre-generates all guided-tour steps in one batch call
    extraction.py                    # Claude structured extraction: page text -> profile fields
    tools/                          # scoring_tools, onboarding_tools, ui_tools, upgrade_tools, …

frontend/
  src/
    routes/                # one component per page (SearchPage, DashboardPage, OnboardingPage, SignInPage, …)
    components/agent/         # the floating assistant panel + guided-tour spotlight
    components/pilot/          # Profile Pilot's visual language: orb, typed-line card, action button, docked chat panel
    components/claim/          # the claim card (search result -> OTP)
    components/onboarding/      # onboarding scenes: URL cards, reading progress, identity, conflicts, fields, done
    styles/pilot.css            # assistant tokens + motion (adapted from the Nora design)
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
  handoff — all live in per-person mock mailboxes (`/mailbox/<email>`) and are never presented as real.

## Onboarding (after a profile is claimed)

The agent walks the new owner through onboarding at `/onboarding/<id>`. The loop is agent-driven, but
the rules are enforced in code (`app/onboarding.py`), so the agent cannot skip them:

1. **Confirm URLs.** The URLs we already hold (website, Google, Facebook, ...) are shown as cards; the
   user marks each *mine* or *not mine*. Nothing is fetched before that. If there is none, the agent
   searches by name + title + company (then name only) and shows candidates with a confidence; the user
   can also add URLs by hand with a label.
2. **Scrape in parallel.** Only confirmed URLs, all at once, live. Order: plain request -> headless
   browser (through the Oxylabs proxy when the site blocks us) -> proxied render request.
3. **Check it is them.** A page is used only if the person's full name is on it; otherwise the user is
   asked. A sign-in screen is reported as blocked, not asked about.
4. **Merge and resolve conflicts.** Empty fields are filled; verified fields (name, email, phone, vertical,
   category, services) are never overwritten; differing values become conflicts the user resolves (pick
   one; "which license is real, or both"; address as primary / secondary / not current / typed in).
5. **Finish.** AI drafts for specialities and description (accepted by the user), default business hours
   (Mon-Fri 9-6) when none were found, then `complete_onboarding`, which is refused while a conflict is
   open, and the first score and rank are computed.

The page (`/onboarding/<id>`) is driven by the server's state, not by the chat: it polls
`GET /api/onboarding/<id>` while the agent works and shows the scene for the current stage, with the agent's
conversation docked on the right. A click records the owner's decision over REST and then tells the agent
("I've answered the cards...") so it carries on. A refresh restores the chat and the agent's drafts from the
stored conversation. A claimed owner who hasn't finished is sent back here when they sign in.

Endpoints (`/api/onboarding/{profile_id}`, all owner-only): `GET` state; `POST /start`, `/sources`
(add a URL), `/sources/{id}/decision` (confirm / deny), `/sources/skip`, `/sources/{id}/identity`,
`/conflicts/{id}/resolve`, `/complete`; `PATCH /fields`. Scraping and merging have no endpoint on purpose: only the agent triggers them.
Agent tools: `get_onboarding_state`, `present_known_urls`, `present_url_candidates`,
`request_manual_urls`, `scrape_confirmed_sources`, `get_scrape_results`, `request_identity_confirmation`,
`merge_scraped_data`, `present_conflicts`, `apply_default_business_hours`, `complete_onboarding`.

Try the scraper alone: `cd backend && python -m app.scraping.cli <url> --name "Full Name"`.
Settings: `OXYLAB_USER`, `OXYLAB_PASSWORD`, `OXYLAB_HOST`, `OXYLAB_PORT` (see `backend/.env.example`);
without them, sites that block direct access stay "blocked".

## The Search Rank Score

The split is data, per category (the `category_score_sections` table); the formulas live in `app/scoring.py`.
Pro (or an active trial) unlocks the Pro-locked sections:

| Category | Common sections | Pro-locked | Max |
|---|---|---|---|
| Mortgage Loan Officer, Mortgage Lender, Real Estate Agent, Dentist | Reviews & Replies 300, Profile Completion 100, Connections 100 (= 500) | Website Health 250, Listings 100 | 850 |
| Insurance Agent | the same plus Listings 100 (= 600) | Website Health 250 | 850 |

Website Health is an audit of the profile's own website (meta description, mobile viewport, load time,
contact details, opening hours). For a profile onboarded from real pages it is read off the website the owner
kept; seeded demo accounts carry a synthetic audit. Profile Completion is the share of the category's basic
fields filled (equal weights unless a category sets them). Social and Google URLs the owner confirms count as
Connections; directory URLs (Zillow, Yelp, ...) count as Listings.

After onboarding the owner sees what would raise the score, with each step's exact points, and the real
before/after score and rank if they unlocked Pro (`GET /api/profiles/<id>/improvement-plan`, the agent tool
`get_improvement_plan`, and the final onboarding screen).

## Resetting demo data

The backend **drops and recreates every table, then reseeds, every time it starts** (all edits,
claims, emails and agent conversations are wiped), so each run begins from the same clean state and
schema changes never need a migration. Set `RESET_ON_STARTUP=false` in `backend/.env` to keep data
across restarts (tables are only created if missing). Note that `uvicorn --reload` restarts on every
code change, which resets too. To reset without restarting:

```bash
curl -X POST http://localhost:8000/api/reset-demo
```

The seed is deterministic (seeded RNG) and re-creates, with stable ids:

- the category taxonomy (4 verticals, 5 categories, services, per-category score split);
- 38 dentist profiles (the original demo set, now the fifth category), 238 profiles in all;
- **8 demo professionals** (ids 39-46, two each in Mortgage Loan Officer, Mortgage Lender, Real Estate
  Agent and Insurance Agent), seeded as *unclaimed* with only name, phone, company, title, services
  and their profile URLs (website, Google, Facebook, LinkedIn, ...). Everything else is left for
  claim + onboarding to scrape. Emails are synthetic (`@demo.clearrank.test`);
- 24 clearly fake peers (`@example.test`) in each demo professional's market, including enterprise
  profiles, so rank and "rank X to Y" Pro previews mean something.

## Testing

- `cd backend && python -m pytest` — 179 tests: taxonomy, scoring per category, demo data, claim and sign-in,
  the scraper, the onboarding service and agent tools, the improvement plan and the tour. They use a separate
  database so your dev data is untouched; create it once with
  `psql -d postgres -c "CREATE DATABASE clearrank_test OWNER clearrank"`.
- `python -m app.scraping.cli <url> --name "Full Name" [--phone ...] [--extract]` — live-test the scraper on
  one URL (fetch ladder, parsing, identity check, optional Claude extraction). Set `OXYLAB_USER`,
  `OXYLAB_PASSWORD`, `OXYLAB_HOST` and `OXYLAB_PORT` in `backend/.env` to route blocked sites through the
  Oxylabs proxy (without all four they are skipped); run `playwright install chromium` once.
- `python -m agent.debug_repl --profile-id 2` — terminal chat against the real agent, no
  frontend needed.
- `python -m agent.scenarios [--scenario NAME]` — scripted multi-turn conversations against the real model
  (tour, upsell, what-if, review reply, handoff, onboarding with confirm / search / name mismatch / conflicts,
  and the post-onboarding plan); read the transcripts for any stated number not backed by a tool call. Reset
  the database first (`POST /api/reset-demo`).
- No frontend test suite; UI changes were verified in a real browser with Playwright scripts used during
  development (not checked in as a suite).
