# Plan: "ClearRank" prototype — a minimal demo scaffold whose real purpose is the conversion agent

## Context

This supersedes the earlier draft of this plan. Two things changed after review:

1. **The scaffold itself doesn't matter — the conversion agent is the actual point.** Your real goal is to build agents that make a *real* visitor interactive and walk them from unclaimed → claimed → pro. Everything else (search page, profile pages, dashboard) only exists to give that agent something to act on. So this plan now deliberately minimizes the scaffold and puts the design effort into the agent.
2. **Radically simplified infra, since this is a throwaway demo, not a product:** FastAPI (not Django), SQLite (not Postgres), no authentication/authorization at all, no Celery, and exactly 5 fixed dummy profiles (3 unclaimed, 1 claimed, 1 pro) instead of generated bulk data. A separate "mock inbox" page replaces real email entirely.

**Why no Celery:** Celery exists to keep slow/background work off the request path — async email sending, recomputing scores across many rows, scheduled jobs. None of that applies here: there's no real email (the mock inbox page replaces it), and recomputing a score for 5 rows is microseconds. It would be pure overhead. If you ever want fire-and-forget behavior later, FastAPI's built-in `BackgroundTasks` covers it with no extra infrastructure.

**Why no auth:** you asked for none, explicitly. Concretely this means: claiming a profile requires no password, and the "manage profile" page is just a plain, unprotected route (`/profile/{id}/manage`) — anyone with the link can view/edit it. That's fine for a local, single-user demo; call it out again before this goes anywhere public.

**Conversion agent = both, per your answer:** a scripted, deterministic guided tour (tooltips/highlights) drives the default path through claim → pro, **plus** an AI chat widget (Claude-powered) available throughout for the visitor to ask questions, grounded in that profile's real, live score/rank data.

**Why one table (plus one small log table):** you asked for a single/minimum table holding all basic details for this process. Below is a consolidated `profiles` table using a few JSON columns for the flexible sub-data (reviews, connections, listing, analytics) instead of separate child tables. One note on provenance: I didn't carry any field names from the schema you pasted alongside this request into this design — it's original and sized to exactly what a 5-row demo needs, for the same decoupling reason noted above.

---

## Stack

- **Backend:** FastAPI + SQLModel (SQLAlchemy + Pydantic in one, pairs naturally with FastAPI) + SQLite (`clearrank.db`, a single file — easy to reset between demos).
- **Frontend:** Jinja2 server-rendered templates + vanilla JS (no build step, no React) — matches "the application isn't important." Two small JS libraries via CDN: **driver.js** for the scripted guided tour, and a hand-rolled ~100-line chat widget for the AI agent (no framework needed for a single floating chat box).
- **AI agent:** Anthropic API (`anthropic` Python SDK), model `claude-sonnet-5` (swap to `claude-haiku-4-5-20251001` if you want faster/cheaper responses — quality difference is unlikely to matter much for this). Requires an `ANTHROPIC_API_KEY` environment variable.
- **No auth, no Celery, no Postgres, no Docker** — a single `uvicorn` process and a SQLite file is the entire runtime.

---

## Data & scoring (unchanged business rules, simplified implementation)

Still the 5-category, 0–850 Search Rank Score: Reviews & Replies (300), Profile Completion (100), Connections (100) — earnable once claimed — plus Web Analytics (250) and Listings (100), pro-only. Claimed caps at 500, pro caps at 850.

Instead of the earlier normalized "config + computed" table design (overkill for 5 rows), scoring is just plain Python functions in `scoring.py`:
```
compute_reviews_score(profile) -> (points, [opportunity notes])
compute_profile_completion_score(profile) -> (points, [opportunity notes])
compute_connections_score(profile) -> (points, [opportunity notes])
compute_web_analytics_score(profile) -> (points, [opportunity notes])   # always computed, even pre-pro
compute_listings_score(profile) -> (points, [opportunity notes])       # always computed, even pre-pro
compute_total_score(profile) -> {total, max_possible, categories: {...earned, max, locked, opportunities}}
```
Same honesty rule as before: web_analytics/listings are always computed even for a claimed (non-pro) profile — just excluded from the total and shown "locked" — so "upgrading unlocks exactly N points" is always a real number pulled live, never a hardcoded marketing claim. `recompute_and_save_score(profile)` writes the denormalized `search_rank_score` column (used for sort order) and is called synchronously after every mutation — trivial cost at 5 rows.

**5 fixed seed profiles, same category + location** (e.g. all "Dentist, Austin TX") so the search results page directly demonstrates ranking competition, which is the whole product's premise:
1. **Pro** — "Dr. Sarah Chen": fully filled out (phone, license, website, bio), several replied 5-star reviews, connections made, listing published, solid analytics → scores near the top (~800/850).
2. **Claimed** — "Dr. Michael Torres": has phone/bio but missing license/website, a couple of unreplied reviews, only 1 connection → deliberately mid-low within its 500 cap (~260/500) — room to visibly grow even before Pro is on the table.
3–5. **Unclaimed** — "Dr. Amara Okafor," "Dr. James Whitfield," "Dr. Linda Park": minimal scraped-looking data only (name, category, location, email), score locked at 0. They still show up in search (per your original spec — scraping alone gets you listed), just ranked last — which is itself the hook: *listed, but invisible.*

Ranking result: Pro (800) > Claimed (260) > three Unclaimed (0, 0, 0) — a clean, legible demo of "claim to get on the board, upgrade to pull ahead."

Seeding is idempotent (drop-and-recreate the 5 rows), exposed later via a `/reset-demo` route so you can replay the demo repeatedly without manually resetting the DB.

---

## The conversion agent (the actual point of this build)

**Scripted guided tour (driver.js), auto-triggered at each lifecycle transition via a query-param flag set on redirect:**
- *On an unclaimed profile page:* highlight the profile info → highlight "Search Rank Score: 0 — not ranking" → highlight the "Claim this profile" button, explaining what claiming unlocks.
- *On the mock inbox, right after clicking "Claim this profile":* highlight the new email → highlight the claim link inside it.
- *On the manage page, right after claiming (`?justClaimed=1`):* highlight the live score breakdown → highlight the two locked categories → highlight "Upgrade to Pro," explaining what it unlocks.
- *On the manage page, right after upgrading (`?justUpgraded=1`):* celebrate the unlocked categories and the new total → link back to the public search page to see the improved rank in place.
A persistent "Take the tour" button allows manually replaying any sequence.

**AI chat widget, available on profile + manage pages:** a small floating bubble. `POST /api/chat` takes `{profile_id, message, history}`; the server re-fetches that profile's *live* `compute_total_score()` output and lifecycle state on every call and builds a fresh system prompt around it (e.g. "This visitor is looking at an unclaimed profile with 0 score... if claimed, they could earn up to 500... reviews are unreplied... etc."), instructing Claude to act as a friendly, honest growth assistant — nudge toward the next lifecycle step, but never state a number that isn't in the live data it was just given. No server-side session: the browser holds the transcript (a JS array / localStorage) and resends it each turn, consistent with "no auth."

---

## Build roadmap

| Phase | Goal |
|---|---|
| 0 | FastAPI + SQLite scaffold, base template, driver.js included |
| 1 | Models, scoring functions, idempotent seed script (5 fixed profiles) |
| 2 | Public search page + profile detail pages |
| 3 | Mock email inbox + claim flow (no auth) |
| 4 | Manage page: edit profile, score breakdown, mock Pro upgrade |
| 5 | **Conversion agent: guided tour + AI chat widget** (flagship phase) |
| 6 | Polish: `/reset-demo` route, light styling pass |

---

## How to use this

1. New empty directory, fresh agent session rooted there.
2. Paste **Product Overview** once, then each **Phase N** prompt in order — verify each phase's "Definition of done" before moving on.
3. You'll need an `ANTHROPIC_API_KEY` before Phase 5.
4. Find/replace "ClearRank" with your real name if you want.

---

## Copy-paste prompts

### Product Overview (paste once, first)

```
We're building ClearRank, a tiny demo prototype of a reputation/listing platform
for service professionals. The real goal of this build is NOT the CRUD app - it's
a "conversion agent" feature that interactively walks a real visitor through a
profile lifecycle. The rest of the app is minimal scaffolding to support that.

Lifecycle: unclaimed (scraped/seeded, publicly listed, score locked at 0) ->
claimed (verified ownership via a MOCK email flow - no real email, no auth/login
at all) -> pro (mocked "upgrade" toggle, no real payment).

Search Rank Score: 0-850, five categories: Reviews & Replies (300), Profile
Completion (100), Connections (100) - earnable once claimed - plus Web Analytics
(250) and Listings (100), pro-only. Claimed caps at 500, pro caps at 850. A
locked (pro-only) category should still be computed live even for a claimed
profile - just excluded from the total - so "upgrading unlocks N points" is
always a real, live number, never a hardcoded claim.

Exactly 5 fixed dummy profiles, all the same category+location so they compete
in the same search results: 3 unclaimed (score 0), 1 claimed (mid score, room to
grow), 1 pro (near-max score). No bulk/random data generation needed.

Stack: FastAPI + SQLModel + SQLite (single file). Jinja2 templates + vanilla JS,
no frontend framework, no build step. NO authentication/authorization anywhere -
routes like the profile "manage" page are plain, unprotected URLs. NO Celery -
compute everything synchronously, it's 5 rows. A "mock inbox" page replaces real
email entirely - claim emails are just DB rows rendered as a fake inbox UI. Data
model is deliberately just one `profiles` table (JSON columns for reviews,
connections, listing, analytics - not child tables) plus one small
`mock_emails` log table. Nothing else.

The flagship feature: a conversion agent with two parts - (1) a scripted,
deterministic guided tour (driver.js) that auto-highlights the next action at
each lifecycle transition, and (2) an AI chat widget (Anthropic Claude API) on
profile/manage pages that a visitor can ask questions to, grounded in that
profile's real live score data, nudging them toward the next lifecycle step
honestly (never inventing numbers).

We'll build this in phases; I'll give you one phase at a time. Confirm you
understand, then wait for Phase 0.
```

### Phase 0 — Scaffolding

```
Phase 0: FastAPI + SQLite scaffold for ClearRank.

- FastAPI app, SQLModel against a local SQLite file (clearrank.db).
- Jinja2Templates for server-rendered pages, a static/ folder for CSS/JS.
- Base template with a simple nav (Search, Mock Inbox), driver.js included via
  CDN <script> tag in the base template (don't wire up any tour steps yet -
  that's Phase 5).
- A health-check route (GET /health).

Definition of done: `uvicorn main:app --reload` boots, a bare page renders with
the nav and driver.js loaded (check browser console for no errors).
```

### Phase 1 — Models, scoring, seed data

```
Phase 1: data models, scoring engine, and fixed seed data for ClearRank.

Models (SQLModel) - deliberately just ONE main table plus one small log table,
no foreign-key child tables at all:

- Profile (the single table holding all basic details for this process): id,
  name, category, location, email, lifecycle_state (unclaimed/claimed/pro),
  phone_number (nullable), license_number (nullable), website_url (nullable),
  bio (nullable), search_rank_score (int, default 0), created_at, updated_at -
  plus these JSON columns holding everything else instead of separate tables:
    - reviews: JSON list of {reviewer_name, rating (1-5), body, reply
      (nullable - null means unreplied)}
    - connections: JSON list of {platform_name, is_connected (bool)}
    - listing: JSON object {business_name, address, is_published (bool)}
    - analytics: JSON object {profile_views, search_impressions,
      website_clicks} (only meaningfully populated for the pro profile)
  Default every JSON column to an empty list/dict, never null, so scoring code
  never has to null-check them.
- MockEmail (kept separate - it's a log of outbound messages, not a profile
  detail): id, to_email, subject, body_html, profile_id FK, created_at,
  is_opened (bool).

scoring.py - plain functions, no ORM tables for score data:
- compute_reviews_score, compute_profile_completion_score,
  compute_connections_score, compute_web_analytics_score,
  compute_listings_score - each takes a Profile and reads its
  reviews/connections/listing/analytics JSON fields directly (no joins needed)
  to return (points_earned, [human-readable opportunity strings for anything
  unsatisfied]).
- compute_total_score(profile) -> dict with total, max_possible (500 if claimed,
  850 if pro, 0 if unclaimed), and a per-category breakdown (earned, max,
  locked: bool, opportunities: list[str]). web_analytics/listings are ALWAYS
  computed (even for a claimed profile) but excluded from the total and marked
  locked=True until pro.
- recompute_and_save_score(profile) - calls compute_total_score, writes
  profile.search_rank_score = total, commits. Call this synchronously after any
  mutation to a profile or its reviews/connections/listing.

Idempotent seed script (a CLI command or a startup check if the DB is empty)
that deletes and recreates exactly these 5 profiles, all in the same
category="Dentist", location="Austin, TX" so they compete in one search result
set (reviews/connections/listing/analytics populate the JSON fields on each
row directly):
1. Pro: "Dr. Sarah Chen" - phone/license/website/bio filled in, 4-5 reviews
   mostly replied and highly rated, 2-3 connections, a published listing,
   healthy analytics numbers. Should land near ~800/850 after scoring.
2. Claimed: "Dr. Michael Torres" - phone + bio filled in, license/website
   blank, 3 reviews with at least one unreplied, only 1 connection, no
   listing. Should land around ~200-300/500 - deliberately mid-low, with
   clear room to grow.
3-5. Unclaimed: "Dr. Amara Okafor", "Dr. James Whitfield", "Dr. Linda Park" -
   name/category/location/email only, nothing else. lifecycle_state=unclaimed.

After inserting, call recompute_and_save_score on all 5 (unclaimed ones will
correctly resolve to 0).

Definition of done: seeding produces exactly 5 profiles with search_rank_score
values matching the intended order (pro > claimed > the three unclaimed at 0).
```

### Phase 2 — Public search + profile pages

```
Phase 2: public pages for ClearRank.

- GET /  or  /search - lists all profiles ordered by search_rank_score
  descending (a simple category/location text filter in the UI is fine
  cosmetically, but with only 5 rows in one market it won't do much - don't
  over-build it). Show name, category, location, average rating, and score
  (or "Not yet ranked" for unclaimed/score 0) per row.
- GET /profile/{id} - profile detail page: name, category, location, bio (if
  present), reviews list. If unclaimed: show a "Claim this profile" button and
  a visible "Search Rank Score: 0 - unclaimed profiles don't rank" note. If
  claimed/pro: show the current score total (not the full breakdown - that's
  the manage page) and a "Manage this profile" link (plain URL, no auth).

Definition of done: all 5 seeded profiles are visible and correctly ordered on
the search page; each profile page renders correctly for its lifecycle state.
```

### Phase 3 — Mock inbox + claim flow

```
Phase 3: the mock email inbox and claim flow for ClearRank (no real email, no
auth).

- Clicking "Claim this profile" on an unclaimed profile's page creates a
  MockEmail row (to_email = that profile's email, a subject like "Claim your
  ClearRank profile", a body containing a "Claim Now" link to
  /claim/{profile_id}/confirm) and redirects to /inbox.
- GET /inbox - lists all MockEmail rows (newest first), showing to_email,
  subject, and a timestamp. Clicking one marks it opened and shows the full
  rendered body (with the working "Claim Now" link/button inside it).
- GET /claim/{profile_id}/confirm - flips that profile's lifecycle_state to
  "claimed", calls recompute_and_save_score, and redirects to
  /profile/{id}/manage?justClaimed=1 (the query param is for Phase 5's tour -
  just pass it through for now, no tour logic yet).

Definition of done: starting from an unclaimed profile page, clicking Claim ->
opening the email in /inbox -> clicking Claim Now flips that profile to claimed
and lands on its (not-yet-built) manage page URL without error.
```

### Phase 4 — Manage page

```
Phase 4: the profile "manage" page for ClearRank (no auth - a plain,
unprotected route).

GET/POST /profile/{id}/manage (claimed or pro profiles only - unclaimed
profiles hitting this route should redirect back to their public page):
- Editable fields: phone_number, license_number, website_url, bio. Saving
  triggers recompute_and_save_score.
- Connections: list of platform_name/is_connected toggles, read from and
  written back to the profile's `connections` JSON field directly (a fixed
  small set like Google Business Profile, Facebook, LinkedIn is fine);
  toggling one triggers recompute.
- Listing: business_name/address fields + is_published toggle, stored in the
  profile's `listing` JSON field - if the profile isn't pro yet, show this
  section locked/grayed with an "Upgrade to Pro to unlock Listings" note
  instead of the real controls.
- Web analytics numbers: read from the profile's `analytics` JSON field; shown
  if pro; locked/grayed with an upsell note if claimed-but-not-pro.
- Full score breakdown: compute_total_score(profile) rendered as a per-category
  list (earned/max), pro-only categories visibly marked "locked" with their
  real computed-but-unused point value shown (e.g. "Web Analytics: 0/250 -
  unlocks with Pro") when not yet pro.
- A "Upgrade to Pro" button (mock, no payment): flips lifecycle_state to
  "pro", recomputes, redirects back to this same page with ?justUpgraded=1.

Definition of done: the claimed seed profile shows a real ~200-300/500 score
with two locked categories and correct opportunity notes; clicking Upgrade to
Pro immediately unlocks all 5 categories and raises the total.
```

### Phase 5 — Conversion agent (flagship phase)

```
Phase 5: the conversion agent for ClearRank - a scripted guided tour plus an AI
chat widget. This is the actual point of the whole build; give it real effort.

PART A - Scripted guided tour (driver.js, already loaded from Phase 0):
- On an unclaimed profile page: a tour highlighting the profile info, then the
  "Search Rank Score: 0" note, then the "Claim this profile" button, with
  copy explaining claiming unlocks ranking. Auto-start once per profile (e.g.
  track via localStorage) but also offer a persistent "Take the tour" button
  to replay it.
- On /inbox, when arriving right after clicking Claim: highlight the new
  unread email, then (once opened) the "Claim Now" button inside it.
- On the manage page when the URL has ?justClaimed=1: a tour highlighting the
  live score breakdown, then specifically the locked categories, then the
  "Upgrade to Pro" button, explaining what upgrading unlocks using the ACTUAL
  numbers already rendered on the page (don't hardcode copy that could drift
  from the real values).
- On the manage page when the URL has ?justUpgraded=1: a short celebratory
  tour over the now-unlocked categories and the new total, ending with a link
  back to the public search page to see the improved rank in place.

PART B - AI chat widget (Anthropic Claude API):
- A small floating chat bubble (vanilla JS, no framework) present on profile
  detail pages and the manage page.
- POST /api/chat - request body {profile_id, message, history: [{role,
  content}, ...]}. On the server: look up the profile, call
  compute_total_score(profile) fresh (live, not cached), and build a system
  prompt along these lines: "You are a friendly, honest growth assistant for
  ClearRank. This visitor is looking at [profile name]'s [unclaimed/claimed/
  pro] profile. Current score: [total]/[max_possible]. [Per-category
  breakdown]. [List of real open opportunities from compute_total_score].
  Help the visitor understand their situation and nudge them toward
  [claiming / upgrading to Pro] as the relevant next step - but you must
  never state a number, rank, or fact that isn't given to you here; if asked
  something you don't have data for, say so honestly instead of guessing."
  Call the Anthropic API (model claude-sonnet-5; anthropic Python SDK; read
  ANTHROPIC_API_KEY from the environment) with that system prompt + the
  passed-in history + the new message, return the reply.
- Client-side: keep the conversation history in a JS variable (or
  localStorage, keyed by profile_id) and resend the full history each turn -
  no server-side session, consistent with having no auth.

Definition of done: visiting an unclaimed profile auto-starts its tour end to
end; completing the claim -> upgrade flow shows the right tour at each step
using real on-page numbers; the chat widget answers questions about a
profile's actual current score/rank and correctly nudges toward the right
next action without inventing any numbers.
```

### Phase 6 — Polish

```
Phase 6: polish pass for ClearRank.

- POST /reset-demo - re-runs the Phase 1 seed script (delete + recreate the 5
  fixed profiles) so the demo can be replayed repeatedly without manually
  touching the database. Link it from the nav, maybe behind a confirm prompt.
- A light CSS pass so the search results, profile, inbox, and manage pages
  look coherent (doesn't need to be fancy - legible and consistent is enough).

Definition of done: clicking Reset Demo restores all 5 profiles to their
original state and scores, ready to demo again from a clean unclaimed state.
```

---

## Verification (for you, at each phase)

- Phase 0: app boots, base page renders, driver.js loads with no console errors.
- Phase 1: seeding produces exactly 5 profiles with the expected score ordering (spot-check the arithmetic against the point budget yourself).
- Phase 2: all 5 show up correctly ranked on the search page; each profile page matches its lifecycle state.
- Phase 3: claim a profile end-to-end via the mock inbox; confirm it flips to claimed and rescoring happened.
- Phase 4: edit fields / toggle a connection on the claimed profile and confirm the score changes; upgrade to Pro and confirm all 5 categories unlock.
- Phase 5: **the important one** - actually click through the tour on a fresh unclaimed profile, then talk to the chat widget and ask it things like "why is my score low" and "what happens if I upgrade" - confirm its answers match the real numbers on the page.
- Phase 6: hit Reset Demo and confirm you're back to a clean, replayable starting state.
