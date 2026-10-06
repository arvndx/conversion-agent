# ClearRank — project plan

[README.md](README.md) covers setup and day-to-day use; [backend/agent/README.md](backend/agent/README.md) covers
the agent. This file records what was decided, what was built and what is still open.

**Source of truth: [core1.txt](core1.txt)** (the product idea). [process1.mov](process1.mov) and
[process1.txt](process1.txt) are UI reference only (the Nora demo); `existing_backend.md`,
`existing_frontend.md` and `target_process.md` are background. Where they disagree with `core1.txt`
(OAuth sign-in, graph, competition, work agreement, Focus), `core1.txt` wins and those stay out.

## What the product does (core1.txt)

ClearRank is a local-business directory with a Search Rank Score (SRS), where **Profile Pilot**, an embedded
agent, drives three processes from a per-category rules table in Postgres:

1. **Claiming.** From a search result ("Claim now") or the header's "Claim a profile" for someone not in the
   database. A card with name, email, vertical, category, services and phone; the name can be edited and
   *either* phone *or* email (not both); vertical → category → multi-select services; a 6-digit code goes to
   that person's mock mailbox; entering it claims the profile and signs them in.
2. **Onboarding.** The owner confirms known URLs (or the agent searches by name + title + company, or they add
   URLs by hand); all confirmed URLs are read in parallel; each page must show the person's name; conflicts are
   resolved at the end (license, address, other fields); AI-drafted specialities and description, default
   business hours; the result is written to the profile.
3. **SRS.** The score and market rank, point-valued steps (reply to a review, fill a missing field, connect a
   platform), a real before/after Pro preview, then the guided tour.

## Roadmap (all phases done)

- [x] 0. Plan recorded here.
- [x] 1. **Taxonomy + data model.** Verticals, categories, services, per-category score sections, profile links,
      scraped sources, conflicts, claims, OTP codes, sessions; `enterprise` status; schema dropped and recreated
      on every reset (no Alembic).
- [x] 2. **Data-driven scoring.** `app/scoring.py` reads each category's sections and field weights from tables;
      the hard-coded 5 sections / 500 / 850 are gone.
- [x] 3. **Demo data.** The 8 demo professionals (ids 39–46, two per core1 category, public details only,
      synthetic `@demo.clearrank.test` emails), 24 clearly fake peers per demo market so rank means something,
      the original 38 dentists kept as a fifth category.
- [x] 4. **Auth + claim.** Email-OTP sign-in, HttpOnly session cookie, owner routes return 401/403, per-person
      mailbox pages, keyword search, claim card, "Claim a profile". Nothing is applied until the code is verified.
- [x] 5. **Scraper** (`backend/app/scraping/`, live inside the backend, no Airflow). Plain request → headless
      browser through the Oxylabs proxy → proxied render request (`X-Oxylabs-Render`). SSRF checks, sign-in
      screens reported as blocked, name validation, and a website audit read off the page. Oxylabs verified:
      AnnieMac (Cloudflare) loads through `proxy-browser`.
- [x] 6. **Onboarding service + agent tools + `/api/onboarding/*`** (`app/onboarding.py`,
      `agent/tools/onboarding_tools.py`, `agent/extraction.py`). Gates enforced in code (below).
- [x] 7. **Onboarding screens** (`routes/OnboardingPage.jsx`, `components/onboarding/`): URL cards, manual adder,
      live reading progress, "is this you?" cards, license / address / pick-one conflict cards, field review with
      the agent's drafts, done screen; next to a docked agent chat.
- [x] 8. **Process 3** (`app/improvement.py`): every step that would raise the score with its exact points, the
      real Pro before/after score and rank, shown on the done screen and spoken by the agent; the tour adapts
      to the category. Confirmed URLs now count toward Connections and Listings.
- [x] 9. **Tests + docs.** 179 pytest tests; an end-to-end browser pass over every flow (below); agent scenarios for onboarding and the post-onboarding plan; this
      file, the README and the agent README brought up to date.

## Decisions

| Topic | Decision |
|---|---|
| Scope | `core1.txt` only: no graph, competition/map scan, battle plan, work agreement, Focus |
| Login | Email-OTP sign-in + signed HttpOnly session cookie |
| OTP delivery | Mock mailbox, one page per person (`/mailbox/<email>`) |
| Scraping | Live: Oxylabs proxy (`OXYLAB_USER/PASSWORD/HOST/PORT`, as the v2-gamification job) + Playwright + BeautifulSoup + markdownify |
| Seed | Dentists kept as a fifth category; 8 demo profiles (2 per core1 category) + clearly fake peers per market |
| Category prefill | Pre-select vertical only; the owner picks category (single) and services (multi) |
| `enterprise` | Pro benefits, set by seed/admin only, no slot limit, no purchase path |
| Reviews | **Not scraped for now (owner decision, Oct 2026).** Reviews & Replies uses the profile's existing reviews. Later: Google Places API (max 5 reviews per place) or a connected Google Business Profile |
| Orchestration | Fully agent-driven LangGraph tool loop; gates enforced in code, not in the prompt |
| Guard rails | Category `rules` JSON holds only what core1 states |
| Score mapping | Social/Google URLs → Connections; category directory URLs → Listings; formulas unchanged |
| Schema changes | Drop and recreate on every reset; `RESET_ON_STARTUP` defaults to true |

## Search Rank Score

The split is data, per category (`category_score_sections`); the formulas live in `app/scoring.py`.

| Category | Common | Pro-locked | Max |
|---|---|---|---|
| Mortgage Loan Officer, Mortgage Lender, Real Estate Agent | Reviews 300 + Profile Completion 100 + Connections 100 = 500 | Website Health 250 + Listings 100 | 850 |
| Insurance Agent | the same + **Listings 100** = 600 | Website Health 250 | 850 |
| Dentist (assumed, core1 gives none) | as mortgage | as mortgage | 850 |

- **Reviews & Replies:** volume (to 10) + average rating + reply rate, 100 each, scaled to the section max.
- **Profile Completion:** share of the category's basic fields filled, weighted per field (equal by default;
  the weights are in `categories.basic_fields` and can be tuned).
- **Connections:** share of the category's social/Google URL slots connected. **Listings:** share of its
  directory slots (Zillow, LendingTree, Realtor.com, Homes.com, Trusted Choice, Yelp, ...) published.
- **Website Health:** five checks on the person's own site (meta description, mobile viewport, load time,
  contact details, opening hours), 50 each.

Locked sections are still computed, so "unlocking Pro adds N points" is always a real number.
`simulate_total_score` scores a hypothetical copy of a profile; the what-if tool, the nudge emails, the
suggestion badges, the improvement plan, the tour data and the Pro preview all share it.

## Onboarding design

State lives in the database (`profile_sources`, `profile_links`, `profile_conflicts`); `app/onboarding.py` owns
the rules, and the REST routes only record the owner's decisions. Scraping and merging have no route: only the
agent's tools start them.

- Only URLs the owner confirmed are ever read. A page's data is used only once the person's full name is on it
  (otherwise `needs_identity`, until they say it is theirs). Verified details (name, email, phone, vertical,
  category, services) are never overwritten. Differing values become conflicts the owner resolves; completion
  is refused while anything is pending. Scraped text is cleaned (tags stripped, length-capped).
- A confirmed social/Google page marks that Connection as connected; a confirmed directory page marks that
  Listing as published (only ever switched on). A page the owner rejects stops counting.
- The website the owner kept supplies the Website Health audit (read from that page; load time only when the
  page came back from a plain request).
- The agent's tool-call loop is capped (`AGENT_MAX_TOOL_ROUNDS`, default 6); the onboarding greeting is idempotent.

## Process 3 (after onboarding)

`GET /api/profiles/{id}/improvement-plan` and the agent tool `get_improvement_plan` return every step that would
raise the score, biggest first, each with its exact points (reply to a review, fill a missing field, connect a
platform, publish a listing when it is not Pro-locked) and the real Pro before/after (score, market rank, what it
unlocks, remaining Pro slots). The done screen shows them; the agent, in one message after `complete_onboarding`,
gives the score and rank, the top steps with their points and the Pro case, then offers the tour. The Manage page
lists the category's scored fields so each step has somewhere to be done.

## Architecture

```
backend/
  app/      the product: models, scoring, improvement, onboarding, claims, auth, slots, pricing, routers/*
    scraping/   fetch (ladder + Oxylabs), parse, validate, audit, runner, safety, cli
  agent/    Profile Pilot, isolated from app/ (only app/main.py wires them together)
  tests/    pytest, against a separate database
frontend/
  src/routes/            Search, ProfileDetail, SignIn, Mailbox, Onboarding, Dashboard, Manage, Pricing
  src/components/        agent (widget, tour), pilot (assistant look), claim (claim card), onboarding (scenes)
```

**Stack:** FastAPI + SQLModel + PostgreSQL 15 (psycopg 3, JSONB); LangGraph 1.2 `StateGraph` (model ⇄ tools) on
`langchain-anthropic` with a Postgres checkpointer and optional Langfuse; Claude's hosted `web_search`;
Playwright + httpx + BeautifulSoup + markdownify; React 19, React Router 7, Vite; Leaflet maps; one Docker image.

**Data model:** `Profile` (wide, JSON columns for reviews, connections, directory listings, website audit) plus
`Vertical`, `Category` (+ services, score sections, URL slots, rules), `ProfileLink`, `ProfileSource`,
`ProfileConflict`, `Claim`, `OtpCode`, `AuthSession`, `MockEmail`, `ScoreSnapshot`, `ProSlotWaitlist`,
`MarketEvent`, `ExecutiveHandoffRequest`, and the agent tables `AgentConversation` and `AgentToolInvocation`.
History lives in the LangGraph checkpointer.

**Seed (deterministic, 238 profiles):** 38 dentists in four markets (San Francisco has all five Pro slots taken:
the "full market" case), the 8 demo professionals (unclaimed, with only their public basics and profile URLs),
and 24 fake peers (`@example.test`, including enterprise) in each demo market. Seeded claimed / Pro / enterprise
accounts count as already onboarded; a profile claimed at run time starts onboarding.

## Profile Pilot (the agent)

**Graph** (`agent/graph.py`): `model` (Claude with a cached static system prompt + the last 20 whole turns) and
`tools` (runs the registry tools, collects `ui_actions`, writes `AgentToolInvocation` audit rows). History is the
graph state in a Postgres checkpointer (thread id = conversation id). The graph is compiled per request so tool
handlers close over that request's session and profile; `agent/orchestrator.py` holds the entry points and the
per-conversation locks.

**Tools (36)**, in `agent/tools/`: onboarding (11: `get_onboarding_state`, `present_known_urls`,
`present_url_candidates`, `request_manual_urls`, `scrape_confirmed_sources`, `get_scrape_results`,
`request_identity_confirmation`, `merge_scraped_data`, `present_conflicts`, `apply_default_business_hours`,
`complete_onboarding`); scoring and pitch (7, including `get_improvement_plan`); `propose_field_updates`;
reviews (2); upgrade (2, need `confirmed=true`); market (3); retention (3); UI actions (`highlight_ui`,
`navigate_to`, `preview_pro_card`, `celebrate`); tour and doubt (3).

**Guided tour:** 7 fixed steps (overview, reviews, profile completion, connections, website health, listings,
wrap-up). Data is gathered in plain Python, one forced tool call writes all the narration, stepping costs no model
calls. A section is marked "(Pro)" only where it is locked for the category (so Listings is not, for insurance).

**Doubt protocol:** three unresolved attempts on one topic escalate to a simulated specialist.
**Time-based mechanics** (`agent/nudges.py`): templated emails for nudges, trial expiry and waitlist, triggered
manually via `POST /api/agent/nudges/run`.

### Non-negotiable rules (enforced in code where possible)
1. The agent never states a number it did not get from a tool call in this conversation.
2. Proposing is free; committing (upgrade, trial, waitlist, form fill, review reply) needs an explicit yes.
3. The agent cannot make the owner's decisions: URL answers, identity answers and conflict choices are recorded
   only by the owner's own clicks.
4. Scarcity is real: slot limits are enforced server-side, urgency is never manufactured.
5. Discounts are capped and computed server-side; handoff eligibility reaches the model only as a boolean.
6. Everything mocked is labelled as mocked (OTP emails, review-reply sending, executive handoff).
7. Paid actions are two-step and enforced in code: the first upgrade / trial call only records a proposal and
   returns the price; it runs only when called again after a "yes" in a later user turn (`agent/tools/upgrade_tools.py`).
8. The assistant drafts only bio, specialities and service area; facts (year started, awards, achievements, title,
   license, address) come from the owner's confirmed pages or from the owner (`agent/tools/claim_tools.py`).

## Verification

- `cd backend && python -m pytest` (179 tests: taxonomy, scoring, demo data, claim + auth, scraper, onboarding
  service and tools, improvement plan, tour, greeting). Uses the separate `clearrank_test` database.
- Agent scenarios against the real model: `python -m agent.scenarios [--scenario NAME]` (tour, upsell, what-if,
  full market, review reply, handoff, onboarding with confirm / search / name mismatch / conflicts, and the
  post-onboarding plan). Reset the database first; check that every stated number traces to a tool call.
- End-to-end browser pass (Playwright, real UI + API), all green on a clean database: public pages, redirects and
  API access control (36 checks); claim from a search card and for a new profile, edit rules, wrong / resent /
  reused codes, per-person mailboxes (30); onboarding on live pages (Antonio Atoche, Chuck Tegano through Oxylabs)
  and controlled identity / conflict / manual-URL states; dashboard, Manage edits, connections, review replies and
  AI drafting (28); the 7-step tour and chat numbers (13); pricing, trial, discount tiers, listings, the
  full-market waitlist (25); sign-in / sign-out, unfinished-owner guard, mailbox escaping, nudges (23); the
  Insurance category end to end (9); phone-width layouts (14). Live scraping was kept to one or two profiles.
- Scraper by hand: `python -m app.scraping.cli <url> --name "Full Name"`.

## Known gaps and next steps

1. **Reviews.** Not scraped (decision above). Without them new profiles have no reviews, so Reviews & Replies
   stays at what the seed gave. Next: Google Places API (≤5 reviews; check Google's terms on storing them) or a
   connected Google Business Profile.
2. **Website audit** is read from the one page we fetched. Load time is only measured on a plain request (a
   browser/proxy render is not a fair timing), so it can stay "unknown". A fuller audit (several pages, real
   speed tests) is not built.
3. **Assumptions:** the dentist score split and the equal field weights are mine, not core1's; both are table data.
4. **Pro purchase** is simulated; slot checks are check-then-write (a row lock per market would close the race).
5. **Open destructive endpoints:** `/api/reset-demo` and `/api/agent/nudges/run` have no protection; gate them
   before any public deploy. `DEMO_MODE` (default on) adds no-code demo sign-in; turn it off where real data lives.
6. **Claim card lets the email be edited** (the rule as written), so whoever edits it receives the code; the name
   check during onboarding is the only extra guard.
7. **Prompt-injection surface:** scraped pages feed the extraction model. Mitigated by the gates above and the
   owner's confirmations; paid actions need a priced proposal and a later "yes" (rule 7).
8. **Sites that need a login** (Facebook, LinkedIn) are reported as blocked; Google Maps shows a limited view to
   headless browsers. Cloudflare-protected sites need the `OXYLAB_*` settings.
9. **Model ID:** `AGENT_MODEL` defaults to `claude-sonnet-5` in `agent/config.py`; `.env` overrides it.
10. **Migrations:** the schema is `create_all` + drop/recreate; adopt Alembic before keeping data across versions.
11. **Mailbox pages are public by design** (`/mailbox/<email>` stands in for real email, so anyone who knows an
    address can read its codes). Fine for a demo; replace with real email before real accounts exist.
12. **Unauthenticated agent chat on unclaimed profiles** has no rate limit; add one before a public deploy.


## Onboarding experience update (Oct 2026)
- **Reading is non-blocking.** `scrape_confirmed_sources` reserves the confirmed pages (status `scraping`, phase `queued`) and reads them in a
  background thread; the agent's turn ends at once. Phases (`opening` / `reading` / `extracting`) are stored per source, and a finished page
  shows the details it gave (`highlights`). The page polls while anything is reading and tells the agent "My pages have been read" once.
- **Search while reading.** The owner can ask for more pages, confirm them, and confirm LinkedIn / Instagram / X links without waiting; the page shows
  what is being searched ("<name> · <title> in <location>"), never an invented count.
- **Sites policy** (`app/scraping/policy.py`): an allowlist of readable platforms plus any ordinary website, and a skip list (LinkedIn, Instagram, X) that is
  never fetched. Skip-list links found by search or on the person's pages are stored unconfirmed; the owner confirms them (counts toward Connections).
- **Clean finish.** When nothing waits on the owner (no cards, identity checks, conflicts or blockers), the agent completes onboarding without a details
  review; bio and specialities are then suggested from Manage. If blockers remain, the details form is shown as before.
- Google Business hours that cover only one or two days are ignored (they are today's slice, not the week).

## One-question-at-a-time onboarding (Oct 2026)
- The onboarding screen shows ONE thing at a time and never needs scrolling: a page question (one page per screen), then, once reading has
  started, a question per link to a site we do not read (LinkedIn / Instagram / X; "not mine" is remembered as declined), then identity checks and
  conflicts one at a time. Anything waiting on the owner always comes before the reading board; the board (compact rows, live stage per page,
  the details each page gave) shows only when nothing is waiting.
- The first screen's last step offers "Read these pages" and "Looking for more of your pages" side by side.
- The agent's latest words are shown on the main screen above the question (short, 1-2 sentences); the chat panel is for the owner's own questions.
- Finishing saves directly over REST (about 15 ms) instead of through an agent turn; the results screen is a set of graphic slides (score ring,
  rank dots, point bars, Pro before/after) with the agent's summary beside them.
- Reading starts by itself the moment the last page card is answered (`POST /api/onboarding/{id}/read`, background thread; only confirmed pages are taken),
  so there is no "read these pages" step. The board then offers "Looking for more details from the internet" and "Add a webpage manually", and each read
  page has a dropdown with everything found on it (`details`).
