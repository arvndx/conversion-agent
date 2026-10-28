-- The conversion agent's own tables (local Postgres). The platform tables (exp_*, organizations, ...) are read-only
-- and are never changed here. Eight tables, consolidated from the earlier plan. Row-level security is on for every table.
-- Run with: psql "$DATABASE_URL" -f db/agent_schema.sql   (safe to run again)

-- A site is one widget on one domain. A business (customer) has one to four sites, one per domain, each with its own
-- site key. The sites of one business share the customer's resource_id (its bundles, its numbers and its leads).
CREATE TABLE IF NOT EXISTS conv_site (
  site_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  site_key        text NOT NULL UNIQUE CHECK (site_key ~ '^wk_(live|test)_[a-z0-9_]{8,40}$'),
  resource_id     text NOT NULL,                     -- the customer id the chat engine uses (the chat's bundles and sessions)
  domain          text NOT NULL,                     -- the one domain this key works on, for example example.com
  UNIQUE (resource_id, domain),
  organization_id uuid,                              -- platform organizations.id (read-only link, no foreign key)
  gcid            text NOT NULL,                     -- platform category, for example gcid:restaurant
  entity_type     text NOT NULL CHECK (entity_type IN ('location', 'professional')),
  display_name    text,
  plan            text,
  status          text NOT NULL DEFAULT 'trial' CHECK (status IN ('trial', 'active', 'paused', 'cancelled')),
  topics          jsonb NOT NULL DEFAULT '[]'::jsonb, -- the site's topics: {id, label, source: category|learned, added_at}
  topic_counts    jsonb NOT NULL DEFAULT '{}'::jsonb, -- chats per topic per day for this site: {"2026-10-23": {"menu": 8}}, last 90 days
  settings        jsonb NOT NULL DEFAULT '{}'::jsonb, -- agent switches, lead capture, handoff text, follow-up, tone, widget look per domain
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  updated_by      text
);

-- Everything the business tells the chatbot, in one place: the 13 fields, opening hours, links, offers, custom fields,
-- FAQ answers, and the questions the bot could not answer.
CREATE TABLE IF NOT EXISTS conv_knowledge (
  id           bigserial PRIMARY KEY,
  site_id      uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  kind         text NOT NULL CHECK (kind IN ('field', 'custom', 'faq', 'unanswered')),
  key          text,                                 -- field key (field), custom field name (custom); null for faq and unanswered
  label        text,
  value        text,                                 -- the value the chatbot uses
  value_json   jsonb,                                -- structured value, for example opening hours per day
  source       text CHECK (source IN ('database', 'web', 'manual', 'customer')),
  confirmed    boolean NOT NULL DEFAULT false,
  shared       boolean NOT NULL DEFAULT true,        -- may the chatbot use it
  web_value    text,                                 -- the web value the confirmed value was checked against
  question     text,                                 -- faq and unanswered
  answer       text,                                 -- faq
  asked_count  integer NOT NULL DEFAULT 1,           -- unanswered: how often it was asked
  status       text,                                 -- unanswered: open, answered or ignored
  updated_at   timestamptz NOT NULL DEFAULT now(),
  updated_by   text
);
CREATE UNIQUE INDEX IF NOT EXISTS conv_knowledge_field_key ON conv_knowledge (site_id, kind, key) WHERE kind IN ('field', 'custom');
CREATE INDEX IF NOT EXISTS conv_knowledge_by_site ON conv_knowledge (site_id, kind);

-- The menu: one row per dish, with its availability. Chef's specials are a flag.
CREATE TABLE IF NOT EXISTS conv_menu_item (
  id            bigserial PRIMARY KEY,
  site_id       uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  section       text NOT NULL,
  name          text NOT NULL,
  price         numeric(8, 2),
  vegetarian    boolean NOT NULL DEFAULT false,
  chef_special  boolean NOT NULL DEFAULT false,
  enabled       boolean NOT NULL DEFAULT true,
  days          smallint[] NOT NULL DEFAULT '{0,1,2,3,4,5,6}' CHECK (days <@ '{0,1,2,3,4,5,6}'::smallint[]),
  start_time    time,                                -- null: during opening hours
  end_time      time,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (site_id, name),
  CHECK ((start_time IS NULL) = (end_time IS NULL) AND (start_time IS NULL OR start_time < end_time))
);

-- A visitor on a site. The visitor id comes from the browser (only stored where consent allows it).
CREATE TABLE IF NOT EXISTS conv_visitor (
  site_id         uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  visitor_id      uuid NOT NULL,
  first_seen_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at    timestamptz NOT NULL DEFAULT now(),
  visits          integer NOT NULL DEFAULT 0,
  widget_seconds  integer NOT NULL DEFAULT 0,        -- totals, added up from the visitor's chats
  page_seconds    integer NOT NULL DEFAULT 0,
  abuse_strikes   integer NOT NULL DEFAULT 0,
  score           integer NOT NULL DEFAULT 0,
  location_city   text,
  location_country text,
  consent_notice_version text,
  expires_at      timestamptz NOT NULL DEFAULT (now() + interval '1 year'),  -- kept one year after the last visit
  PRIMARY KEY (site_id, visitor_id)
);

-- One visit to a site: from the first page load until 30 minutes with no activity. One row per visit, with or without
-- a chat. The page activity stays empty until page tracking is on for the visit (null means not tracked, not zero).
CREATE TABLE IF NOT EXISTS conv_activity (
  activity_id     uuid PRIMARY KEY,                -- the visit's id, from the browser
  site_id         uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  visitor_id      uuid,
  FOREIGN KEY (site_id, visitor_id) REFERENCES conv_visitor (site_id, visitor_id) ON DELETE SET NULL (visitor_id),
  domain          text NOT NULL,
  started_at      timestamptz NOT NULL DEFAULT now(),
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  ended_at        timestamptz,
  status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
  have_consent    boolean NOT NULL DEFAULT false,
  location_city   text,
  location_country text,
  referrer_host   text,
  utm             jsonb,
  pages_viewed    integer,                         -- page activity
  clicks          integer,
  time_on_site_seconds integer,
  widget_opens    integer,                         -- widget activity
  time_in_widget_seconds integer,
  expires_at      timestamptz NOT NULL DEFAULT (now() + interval '20 days')
);
CREATE INDEX IF NOT EXISTS conv_activity_by_site ON conv_activity (site_id, started_at DESC);
CREATE INDEX IF NOT EXISTS conv_activity_open ON conv_activity (last_activity_at) WHERE status = 'open';

-- One chat, inside one visit (activity_id is empty when the chat has no visit). Messages are kept about 20 days,
-- then removed by the cleanup job.
CREATE TABLE IF NOT EXISTS conv_session (
  session_id    uuid PRIMARY KEY,                -- the chat's id, from the browser
  site_id       uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  visitor_id    uuid,
  FOREIGN KEY (site_id, visitor_id) REFERENCES conv_visitor (site_id, visitor_id) ON DELETE SET NULL (visitor_id),
  activity_id   uuid REFERENCES conv_activity (activity_id) ON DELETE SET NULL,
  started_at    timestamptz NOT NULL DEFAULT now(),
  last_activity_at timestamptz,
  ended_at      timestamptz,
  domain        text NOT NULL,
  have_consent  boolean NOT NULL DEFAULT false,
  location_city text,
  location_country text,
  widget_seconds integer NOT NULL DEFAULT 0,
  abuse_strikes integer NOT NULL DEFAULT 0,
  session_score integer NOT NULL DEFAULT 0,
  metric_date   date,
  page_url      text,
  referrer_host text,
  utm           jsonb,                               -- campaign tags
  consent       text,
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed', 'incomplete', 'handed_over', 'blocked')),
  messages      jsonb NOT NULL DEFAULT '[]'::jsonb,  -- the chat's turns, as the chat engine writes them: [{request, response, event_time}]
  topic         text,                                -- the chat's first topic, a category topic id (for example menu)
  topic_counted_at timestamptz,                      -- set once the topic is added to the site's topic_counts
  summary       text,
  expires_at    timestamptz NOT NULL DEFAULT (now() + interval '20 days')
);
CREATE INDEX IF NOT EXISTS conv_session_by_site ON conv_session (site_id, started_at DESC);
CREATE INDEX IF NOT EXISTS conv_session_expiry ON conv_session (expires_at);
CREATE INDEX IF NOT EXISTS conv_activity_expiry ON conv_activity (expires_at);
CREATE INDEX IF NOT EXISTS conv_visitor_expiry ON conv_visitor (expires_at);

-- A lead: a visitor who left a name and contact, or a hot visitor, and what was asked and why they were passed on.
-- One widget per customer, so there is no assignment. The name, email and phone are the visitor's own details.
CREATE TABLE IF NOT EXISTS conv_lead (
  lead_id      uuid PRIMARY KEY,                -- the handover id (one per chat that handed over)
  site_id      uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  session_id   uuid REFERENCES conv_session (session_id) ON DELETE SET NULL,
  visitor_id   uuid,
  notifications jsonb NOT NULL DEFAULT '{"business_email": {"status": "pending"}}'::jsonb,
  kind         text NOT NULL DEFAULT 'lead' CHECK (kind IN ('lead', 'hot_visitor')),
  name         text,
  email        text,
  phone        text,
  question     text,
  reason       text CHECK (reason IN ('request_from_visitor', 'time_in_widget', 'unavailable_answer', 'confused_question', 'unsure_question')),
  summary      text,
  status       text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'closed')),
  created_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (kind = 'hot_visitor' OR name IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS conv_lead_by_site ON conv_lead (site_id, created_at DESC);

-- Every change made on the dashboard (who, when, what, before and after), one row per change.
CREATE TABLE IF NOT EXISTS conv_change_log (
  id            bigserial PRIMARY KEY,
  site_id       uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  changed_at    timestamptz NOT NULL DEFAULT now(),
  changed_by    text NOT NULL,
  page          text NOT NULL,
  area          text NOT NULL,
  target        text,
  action        text NOT NULL,
  summary       text NOT NULL,
  before_value  jsonb,
  after_value   jsonb,
  batch_id      uuid
);
CREATE INDEX IF NOT EXISTS conv_change_log_by_site ON conv_change_log (site_id, changed_at DESC);

-- A reply the visitor rated (thumbs up or down), with the reason when it was down. The chat is kept in conv_session.
CREATE TABLE IF NOT EXISTS conv_reply_feedback (
  id           bigserial PRIMARY KEY,
  site_id      uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  session_id   uuid REFERENCES conv_session (session_id) ON DELETE SET NULL,
  rated_at     timestamptz NOT NULL DEFAULT now(),
  rating       text NOT NULL CHECK (rating IN ('up', 'down')),
  reason       text CHECK (reason IN ('Wrong answer', 'Did not answer my question', 'Too long', 'Hard to understand', 'Other')),
  reason_note  text,                                -- the visitor's own words when the reason is Other
  topic        text,
  question     text,
  reply        text
);
CREATE INDEX IF NOT EXISTS conv_reply_feedback_by_site ON conv_reply_feedback (site_id, rated_at DESC);

-- Daily numbers for the dashboard charts. One row per site (domain) and day. Kept without expiry, so 30 and 90 day views stay correct.
CREATE TABLE IF NOT EXISTS conv_daily (
  site_id              uuid NOT NULL REFERENCES conv_site (site_id) ON DELETE CASCADE,
  day                  date NOT NULL,
  visitors             integer NOT NULL DEFAULT 0,
  chats                integer NOT NULL DEFAULT 0,
  leads                integer NOT NULL DEFAULT 0,
  hot_visitors         integer NOT NULL DEFAULT 0,
  questions_answered   integer NOT NULL DEFAULT 0,
  questions_unanswered integer NOT NULL DEFAULT 0,
  PRIMARY KEY (site_id, day)
);

-- Row-level security on for every table (owner connections still work; see the platform's rule for new tables).
ALTER TABLE conv_site ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_knowledge ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_menu_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_visitor ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_session ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_lead ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_change_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_reply_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE conv_activity ENABLE ROW LEVEL SECURITY;

-- Columns added after the first version (safe to run again on an existing database).
ALTER TABLE conv_site ADD COLUMN IF NOT EXISTS topics jsonb NOT NULL DEFAULT '[]'::jsonb;
