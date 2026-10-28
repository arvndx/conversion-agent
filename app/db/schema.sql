-- Output database for the Conversion Agent (A40 to A53).
-- Eight tables. Every table with a time limit has expires_at, set from updated_at plus the TTL (A35).
-- A minute job deletes rows whose expires_at has passed.

CREATE TABLE IF NOT EXISTS conversion_subscription (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type         text NOT NULL,
    resource_id           text NOT NULL,
    is_enabled            boolean NOT NULL DEFAULT false,
    kill_switch           text NOT NULL DEFAULT 'none'
                          CHECK (kill_switch IN ('none', 'stop_new_chats', 'stop_everything')),
    kill_switch_reason    text,
    kill_switch_by        text,
    kill_switch_at        timestamptz,
    site_key              text NOT NULL UNIQUE,
    allowed_domains       text[] NOT NULL DEFAULT '{}',
    plan                  text NOT NULL CHECK (plan IN ('monthly', 'yearly')),
    subscription_starts   timestamptz NOT NULL,
    subscription_ends     timestamptz NOT NULL,
    status                text NOT NULL CHECK (status IN ('trial', 'active', 'cancelled', 'expired')),
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (resource_id, subscription_starts)
);

CREATE TABLE IF NOT EXISTS google_connection (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type           text NOT NULL,
    resource_id             text NOT NULL,
    provider                text NOT NULL DEFAULT 'google',
    google_account_email    text,
    calendar_id             text,
    refresh_token_encrypted bytea,
    scopes                  text,
    status                  text NOT NULL CHECK (status IN ('connected', 'disconnected')),
    connected_at            timestamptz,
    disconnected_at         timestamptz,
    last_checked_at         timestamptz,
    last_error              text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS google_connection_resource ON google_connection (resource_id);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id          uuid PRIMARY KEY,
    visitor_id          uuid,
    resource_type       text NOT NULL,
    resource_id         text NOT NULL,
    domain              text NOT NULL,
    have_consent        boolean NOT NULL,
    status              text NOT NULL CHECK (status IN ('open', 'completed', 'incomplete', 'handed_over', 'abusive')),
    started_at          timestamptz NOT NULL,
    ended_at            timestamptz,
    last_activity_at    timestamptz NOT NULL,
    location_city       text,
    location_country    text,
    widget_seconds      integer NOT NULL DEFAULT 0,
    page_seconds        integer,
    widget_actions      jsonb NOT NULL DEFAULT '[]',
    page_actions        jsonb,
    conversation        jsonb NOT NULL DEFAULT '[]',
    session_score       integer NOT NULL DEFAULT 0,
    summary             text,
    abuse_strikes       integer NOT NULL DEFAULT 0,
    model               text,
    input_tokens        integer NOT NULL DEFAULT 0,
    output_tokens       integer NOT NULL DEFAULT 0,
    cost                numeric(12, 6) NOT NULL DEFAULT 0,
    metric_date         date NOT NULL,
    expires_at          timestamptz NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_sessions_expires ON chat_sessions (expires_at);
CREATE INDEX IF NOT EXISTS chat_sessions_resource_started ON chat_sessions (resource_id, started_at);

CREATE TABLE IF NOT EXISTS visitors (
    visitor_id                uuid NOT NULL,
    domain                    text NOT NULL,
    resource_id               text NOT NULL,
    resource_type            text NOT NULL,
    have_consent              boolean NOT NULL DEFAULT true,
    name                      text,
    email                     text,
    phone                     text,
    location_city             text,
    location_country          text,
    visit_count               integer NOT NULL DEFAULT 0,
    widget_seconds_total      integer NOT NULL DEFAULT 0,
    page_seconds_total        integer NOT NULL DEFAULT 0,
    score_72h                 integer NOT NULL DEFAULT 0,
    score_events              jsonb NOT NULL DEFAULT '[]',
    status                    text NOT NULL DEFAULT 'visitor'
                              CHECK (status IN ('visitor', 'hot_visitor', 'lead')),
    handover_count            integer NOT NULL DEFAULT 0,
    strike_count              integer NOT NULL DEFAULT 0,
    block_count               integer NOT NULL DEFAULT 0,
    last_block_at             timestamptz,
    consent_choice            text CHECK (consent_choice IN ('accepted', 'declined', 'withdrawn')),
    consent_notice_version    text,
    consent_at                timestamptz,
    ai_tokens_total           integer NOT NULL DEFAULT 0,
    ai_cost_total             numeric(12, 6) NOT NULL DEFAULT 0,
    first_seen_at             timestamptz NOT NULL,
    last_seen_at              timestamptz NOT NULL,
    expires_at                timestamptz NOT NULL,
    created_at                timestamptz NOT NULL DEFAULT now(),
    updated_at                timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (visitor_id, domain, resource_id)
);
CREATE INDEX IF NOT EXISTS visitors_expires ON visitors (expires_at);
CREATE INDEX IF NOT EXISTS visitors_resource_status ON visitors (resource_id, domain, status);

CREATE TABLE IF NOT EXISTS handovers (
    handover_id     uuid PRIMARY KEY,
    session_id      uuid NOT NULL REFERENCES chat_sessions (session_id),
    visitor_id      uuid,
    resource_type   text NOT NULL,
    resource_id     text NOT NULL,
    domain          text NOT NULL,
    name            text NOT NULL,
    email           text,
    phone           text,
    CHECK (email IS NOT NULL OR phone IS NOT NULL),
    reason          text NOT NULL,
    ai_summary      text,
    conversation    jsonb NOT NULL DEFAULT '[]',
    status          text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'closed')),
    extra_fields    jsonb,
    notifications   jsonb NOT NULL DEFAULT '{}',
    expires_at      timestamptz NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS handovers_expires ON handovers (expires_at);
CREATE INDEX IF NOT EXISTS handovers_resource_status ON handovers (resource_id, status, created_at);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id        uuid PRIMARY KEY,
    session_id        uuid REFERENCES chat_sessions (session_id),
    visitor_id        uuid,
    resource_type     text NOT NULL,
    resource_id       text NOT NULL,
    domain            text NOT NULL,
    slot_start        timestamptz NOT NULL,
    slot_end          timestamptz NOT NULL,
    name              text NOT NULL,
    email             text,
    phone             text,
    status            text NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    google_event_id   text,
    notifications     jsonb NOT NULL DEFAULT '{}',
    expires_at        timestamptz NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bookings_expires ON bookings (expires_at);
CREATE INDEX IF NOT EXISTS bookings_resource_slot ON bookings (resource_id, slot_start);

CREATE TABLE IF NOT EXISTS daily_stats (
    metric_date           date NOT NULL,
    resource_id           text NOT NULL,
    domain                text NOT NULL,
    resource_type         text NOT NULL,
    visits                integer NOT NULL DEFAULT 0,
    chats                 integer NOT NULL DEFAULT 0,
    unique_visitors       integer NOT NULL DEFAULT 0,
    leads                 integer NOT NULL DEFAULT 0,
    hot_visitors          integer NOT NULL DEFAULT 0,
    handovers             integer NOT NULL DEFAULT 0,
    bookings              integer NOT NULL DEFAULT 0,
    completed             integer NOT NULL DEFAULT 0,
    incomplete            integer NOT NULL DEFAULT 0,
    abusive               integer NOT NULL DEFAULT 0,
    link_clicks           integer NOT NULL DEFAULT 0,
    widget_seconds_total  integer NOT NULL DEFAULT 0,
    page_seconds_total    integer NOT NULL DEFAULT 0,
    ai_tokens             integer NOT NULL DEFAULT 0,
    ai_cost               numeric(12, 6) NOT NULL DEFAULT 0,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metric_date, resource_id, domain)
);

CREATE TABLE IF NOT EXISTS logs (
    log_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time    timestamptz NOT NULL DEFAULT now(),
    event_type    text NOT NULL CHECK (event_type IN (
                    'operator_action', 'nora_api_call', 'handover_email', 'calendar_failure',
                    'ai_failure', 'consent_change', 'block_or_rate_limit')),
    actor_type    text CHECK (actor_type IN ('operator', 'nora', 'system', 'visitor')),
    actor_id      text,
    resource_type text,
    resource_id   text,
    domain        text,
    session_id    uuid,
    visitor_id    uuid,
    result        text CHECK (result IN ('success', 'failure')),
    error_code    text,
    details       jsonb NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz
);
CREATE INDEX IF NOT EXISTS logs_type_time ON logs (event_type, event_time);
CREATE INDEX IF NOT EXISTS logs_resource_time ON logs (resource_id, event_time);

-- Widget colours for each domain of a customer (A84, dashboard widget settings). One row per customer and domain.
CREATE TABLE IF NOT EXISTS widget_settings (
  resource_type text NOT NULL,
  resource_id   text NOT NULL,
  domain        text NOT NULL,
  primary_color text NOT NULL DEFAULT '#7a2e1d' CHECK (primary_color ~ '^#[0-9a-fA-F]{6}$'),
  accent_color  text NOT NULL DEFAULT '#a2432b' CHECK (accent_color ~ '^#[0-9a-fA-F]{6}$'),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (resource_type, resource_id, domain)
);

-- Every change made on the dashboard (the admin page and the leads list), kept for the audit trail. There is
-- no expiry on this table. Changes saved together with one Save share a batch_id, so a refused batch leaves no rows.
CREATE TABLE IF NOT EXISTS dashboard_changes (
  id            bigserial PRIMARY KEY,
  resource_type text NOT NULL,
  resource_id   text NOT NULL,
  changed_at    timestamptz NOT NULL DEFAULT now(),
  changed_by    text NOT NULL,                 -- who made the change (the sign-in fills this in later)
  page          text NOT NULL,                 -- admin, leads
  area          text NOT NULL,                 -- subscription, domains, widget_look, widget_status, knowledge, menu, custom_fields, leads
  target        text,                          -- the field key, dish id, domain or lead id the change is about
  action        text NOT NULL,                 -- changed, confirmed, shared, added, turned_on, status_changed, ...
  summary       text NOT NULL,                 -- one readable line
  before_value  jsonb,
  after_value   jsonb,
  batch_id      text                           -- the Save that made the change, when several were saved together
);
CREATE INDEX IF NOT EXISTS dashboard_changes_by_resource ON dashboard_changes (resource_type, resource_id, changed_at DESC);

-- Where each "What visitors asked for" card should be added: the destination is suggested when the card is first
-- created (by the model, or a keyword rule if the model is unavailable), then confirmed by the business.
CREATE TABLE IF NOT EXISTS insight_targets (
  resource_type text NOT NULL,
  resource_id   text NOT NULL,
  card_text     text NOT NULL,
  suggested_tab text NOT NULL,      -- menu, defaults or custom
  suggested_key text,               -- the predefined field key, or the custom field name
  suggested_by  text NOT NULL,      -- llm or rule
  suggested_at  timestamptz NOT NULL DEFAULT now(),
  confirmed_tab text,
  confirmed_key text,
  confirmed_by  text,
  confirmed_at  timestamptz,
  PRIMARY KEY (resource_type, resource_id, card_text)
);
