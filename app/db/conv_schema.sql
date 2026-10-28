--
-- PostgreSQL database dump
--

\restrict JdKubmNgIhAAfSbkEL6bOjYuJK9qfHBhkA7pnvGFd6sciFiEmNrXpAa4bnr3XcP

-- Dumped from database version 15.14 (Homebrew)
-- Dumped by pg_dump version 15.14 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: conv_action; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_action (
    gcid text NOT NULL,
    action_key text NOT NULL,
    source_entity_type text NOT NULL,
    action_name text NOT NULL,
    schema_action text NOT NULL,
    agent_goal text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    profile_button text,
    steps jsonb,
    enabled boolean DEFAULT true NOT NULL,
    source text DEFAULT 'production'::text NOT NULL,
    request_type text,
    CONSTRAINT conv_action_source_check CHECK ((source = ANY (ARRAY['production'::text, 'custom'::text]))),
    CONSTRAINT conv_action_source_entity_type_check CHECK ((source_entity_type = ANY (ARRAY['professional'::text, 'location'::text]))),
    CONSTRAINT conv_action_steps_check CHECK (((steps IS NULL) OR ((jsonb_typeof(steps) = 'array'::text) AND (jsonb_array_length(steps) > 0))))
);


ALTER TABLE public.conv_action OWNER TO arravindseetharaman;

--
-- Name: COLUMN conv_action.request_type; Type: COMMENT; Schema: public; Owner: arravindseetharaman
--

COMMENT ON COLUMN public.conv_action.request_type IS 'The label saved on a request made through this action (for example table booking, appointment booking, business detail handover, direct handover). Shown in the dashboard Type filter.';


--
-- Name: conv_activity; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_activity (
    activity_id uuid NOT NULL,
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    visitor_id uuid NOT NULL,
    have_consent boolean NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    started_at timestamp with time zone NOT NULL,
    last_activity_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    city text,
    state text,
    clicks integer,
    time_on_site_seconds integer,
    widget_opens integer,
    time_in_widget_seconds integer,
    referrer_host text,
    utm jsonb,
    summary text,
    session_score integer DEFAULT 0 NOT NULL,
    abuse_strikes integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_activity_status_check CHECK ((status = ANY (ARRAY['open'::text, 'completed'::text, 'incomplete'::text, 'handed_over'::text, 'blocked'::text])))
);


ALTER TABLE public.conv_activity OWNER TO arravindseetharaman;

--
-- Name: conv_calendar_connection; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_calendar_connection (
    professional_id uuid NOT NULL,
    provider text DEFAULT 'google'::text NOT NULL,
    calendar_id text,
    account_email text,
    token_encrypted bytea,
    status text DEFAULT 'disconnected'::text NOT NULL,
    connected_at timestamp with time zone,
    last_checked_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_calendar_connection_status_check CHECK ((status = ANY (ARRAY['connected'::text, 'disconnected'::text])))
);


ALTER TABLE public.conv_calendar_connection OWNER TO arravindseetharaman;

--
-- Name: conv_category_settings; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_category_settings (
    gcid text NOT NULL,
    welcome_message text NOT NULL,
    teaser_text text NOT NULL,
    never_ask text[] DEFAULT '{}'::text[] NOT NULL,
    abuse_rules jsonb NOT NULL,
    scoring_rules jsonb NOT NULL,
    special_field_definitions jsonb DEFAULT '[]'::jsonb NOT NULL,
    other_messages jsonb DEFAULT '{}'::jsonb NOT NULL,
    handover_wait_seconds integer DEFAULT 300 NOT NULL,
    idle_close_minutes integer DEFAULT 10 NOT NULL,
    general_knowledge_allowed boolean DEFAULT false NOT NULL,
    guardrails_text text,
    abuse_blocklist text[],
    abuse_allowlist text[],
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    services text[] DEFAULT '{}'::text[] NOT NULL,
    compliance_rules text[] DEFAULT '{}'::text[] NOT NULL,
    prohibited_phrases text[] DEFAULT '{}'::text[] NOT NULL,
    required_disclaimers text[] DEFAULT '{}'::text[] NOT NULL,
    content_restrictions text[] DEFAULT '{}'::text[] NOT NULL
);


ALTER TABLE public.conv_category_settings OWNER TO arravindseetharaman;

--
-- Name: conv_change_log; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_change_log (
    change_id bigint NOT NULL,
    professional_id uuid NOT NULL,
    domain text,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by text NOT NULL,
    page text NOT NULL,
    area text NOT NULL,
    target text,
    action text NOT NULL,
    summary text NOT NULL,
    before_value jsonb,
    after_value jsonb,
    batch_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conv_change_log OWNER TO arravindseetharaman;

--
-- Name: conv_change_log_change_id_seq; Type: SEQUENCE; Schema: public; Owner: arravindseetharaman
--

CREATE SEQUENCE public.conv_change_log_change_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.conv_change_log_change_id_seq OWNER TO arravindseetharaman;

--
-- Name: conv_change_log_change_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: arravindseetharaman
--

ALTER SEQUENCE public.conv_change_log_change_id_seq OWNED BY public.conv_change_log.change_id;


--
-- Name: conv_critical_reply; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_critical_reply (
    gcid text NOT NULL,
    topic_id text NOT NULL,
    description text NOT NULL,
    examples jsonb DEFAULT '[]'::jsonb NOT NULL,
    reply text NOT NULL,
    action text DEFAULT 'handover'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conv_critical_reply OWNER TO arravindseetharaman;

--
-- Name: conv_daily; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_daily (
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    day date NOT NULL,
    visitors integer DEFAULT 0 NOT NULL,
    chats integer DEFAULT 0 NOT NULL,
    handovers integer DEFAULT 0 NOT NULL,
    hot_visitors integer DEFAULT 0 NOT NULL,
    bookings integer DEFAULT 0 NOT NULL,
    questions_answered integer DEFAULT 0 NOT NULL,
    questions_unanswered integer DEFAULT 0 NOT NULL,
    topic_counts jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conv_daily OWNER TO arravindseetharaman;

--
-- Name: conv_domains; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_domains (
    site_key text NOT NULL,
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    primary_color text DEFAULT '#7a2e1d'::text NOT NULL,
    accent_color text DEFAULT '#a2432b'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_domains_accent_color_check CHECK ((accent_color ~ '^#[0-9a-fA-F]{6}$'::text)),
    CONSTRAINT conv_domains_primary_color_check CHECK ((primary_color ~ '^#[0-9a-fA-F]{6}$'::text)),
    CONSTRAINT conv_domains_site_key_check CHECK ((site_key ~ '^wk_(live|test)_[a-z0-9]{8,40}$'::text)),
    CONSTRAINT conv_domains_status_check CHECK ((status = ANY (ARRAY['active'::text, 'paused'::text])))
);


ALTER TABLE public.conv_domains OWNER TO arravindseetharaman;

--
-- Name: conv_handover; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_handover (
    handover_id uuid NOT NULL,
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    session_id uuid,
    visitor_id uuid,
    name text NOT NULL,
    email text,
    phone text,
    reason text NOT NULL,
    question text NOT NULL,
    summary text,
    extra_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    city text,
    state text,
    status text DEFAULT 'new'::text NOT NULL,
    notified_by text[] DEFAULT '{}'::text[] NOT NULL,
    notified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    action_key text,
    request_type text DEFAULT 'direct handover'::text NOT NULL,
    CONSTRAINT conv_handover_check CHECK (((email IS NOT NULL) OR (phone IS NOT NULL))),
    CONSTRAINT conv_handover_reason_check CHECK ((reason = ANY (ARRAY['request_from_visitor'::text, 'critical_question'::text, 'unsure_question'::text, 'unavailable_answer'::text, 'time_in_widget'::text, 'system_fallback'::text]))),
    CONSTRAINT conv_handover_status_check CHECK ((status = ANY (ARRAY['new'::text, 'contacted'::text, 'closed'::text])))
);


ALTER TABLE public.conv_handover OWNER TO arravindseetharaman;

--
-- Name: COLUMN conv_handover.request_type; Type: COMMENT; Schema: public; Owner: arravindseetharaman
--

COMMENT ON COLUMN public.conv_handover.request_type IS 'What the visitor asked for, copied from conv_action.request_type of the action the form was opened for.';


--
-- Name: conv_hot_visitor; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_hot_visitor (
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    visitor_id uuid NOT NULL,
    summary text,
    city text,
    state text,
    first_hot_at timestamp with time zone NOT NULL,
    last_hot_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conv_hot_visitor OWNER TO arravindseetharaman;

--
-- Name: conv_log; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_log (
    log_id bigint NOT NULL,
    event_time timestamp with time zone DEFAULT now() NOT NULL,
    event_type text NOT NULL,
    actor_type text,
    actor_id text,
    professional_id uuid,
    domain text,
    session_id uuid,
    visitor_id uuid,
    result text,
    error_code text,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_log_actor_type_check CHECK ((actor_type = ANY (ARRAY['operator'::text, 'nora'::text, 'system'::text, 'visitor'::text]))),
    CONSTRAINT conv_log_event_type_check CHECK ((event_type = ANY (ARRAY['operator_action'::text, 'nora_api_call'::text, 'handover_email'::text, 'calendar_failure'::text, 'ai_failure'::text, 'consent_change'::text, 'block_or_rate_limit'::text]))),
    CONSTRAINT conv_log_result_check CHECK ((result = ANY (ARRAY['success'::text, 'failure'::text])))
);


ALTER TABLE public.conv_log OWNER TO arravindseetharaman;

--
-- Name: conv_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: arravindseetharaman
--

CREATE SEQUENCE public.conv_log_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.conv_log_log_id_seq OWNER TO arravindseetharaman;

--
-- Name: conv_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: arravindseetharaman
--

ALTER SEQUENCE public.conv_log_log_id_seq OWNED BY public.conv_log.log_id;


--
-- Name: conv_menu; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_menu (
    menu_id uuid NOT NULL,
    name text NOT NULL,
    section text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conv_menu OWNER TO arravindseetharaman;

--
-- Name: conv_professional_menu; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_professional_menu (
    professional_id uuid NOT NULL,
    menu_id uuid NOT NULL,
    price numeric(8,2) NOT NULL,
    availability jsonb DEFAULT '{}'::jsonb NOT NULL,
    chef_special boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_professional_menu_price_check CHECK ((price >= (0)::numeric))
);


ALTER TABLE public.conv_professional_menu OWNER TO arravindseetharaman;

--
-- Name: conv_professional_settings; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_professional_settings (
    professional_id uuid NOT NULL,
    timezone text NOT NULL,
    booking_enabled boolean DEFAULT false NOT NULL,
    availability jsonb DEFAULT '{}'::jsonb NOT NULL,
    slot_minutes smallint DEFAULT 15 NOT NULL,
    bookings_per_slot smallint DEFAULT 4 NOT NULL,
    hot_visitor_threshold smallint DEFAULT 60 NOT NULL,
    notify_by text[] DEFAULT '{email}'::text[] NOT NULL,
    display_switches jsonb DEFAULT '{}'::jsonb NOT NULL,
    services text[] DEFAULT '{}'::text[] NOT NULL,
    special_fields jsonb DEFAULT '{}'::jsonb NOT NULL,
    opening_hours jsonb DEFAULT '{}'::jsonb NOT NULL,
    response_hours jsonb DEFAULT '{}'::jsonb NOT NULL,
    current_offers text[] DEFAULT '{}'::text[] NOT NULL,
    handover_extra_fields text[] DEFAULT '{}'::text[] NOT NULL,
    kill_switch text DEFAULT 'none'::text NOT NULL,
    kill_switch_reason text,
    kill_switch_by text,
    kill_switch_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    public_phone text,
    public_email text,
    CONSTRAINT conv_professional_settings_bookings_per_slot_check CHECK ((bookings_per_slot > 0)),
    CONSTRAINT conv_professional_settings_kill_switch_check CHECK ((kill_switch = ANY (ARRAY['none'::text, 'stop_new_chats'::text, 'stop_everything'::text]))),
    CONSTRAINT conv_professional_settings_notify_by_check CHECK (((notify_by <@ ARRAY['phone'::text, 'email'::text]) AND (cardinality(notify_by) > 0))),
    CONSTRAINT conv_professional_settings_slot_minutes_check CHECK ((slot_minutes > 0))
);


ALTER TABLE public.conv_professional_settings OWNER TO arravindseetharaman;

--
-- Name: conv_question; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_question (
    question_id uuid NOT NULL,
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    question_text text NOT NULL,
    topic text,
    asked_count integer DEFAULT 1 NOT NULL,
    first_asked_at timestamp with time zone NOT NULL,
    last_asked_at timestamp with time zone NOT NULL,
    answered boolean DEFAULT false NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    suggested_target text,
    confirmed_target text,
    confirmed_by text,
    confirmed_at timestamp with time zone,
    suggested_answer text,
    suggested_key text,
    answer_text text,
    answer_key text,
    answered_at timestamp with time zone,
    CONSTRAINT conv_question_status_check CHECK ((status = ANY (ARRAY['open'::text, 'added'::text, 'ignored'::text])))
);


ALTER TABLE public.conv_question OWNER TO arravindseetharaman;

--
-- Name: conv_reply_feedback; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_reply_feedback (
    feedback_id bigint NOT NULL,
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    session_id uuid,
    rated_at timestamp with time zone DEFAULT now() NOT NULL,
    rating text NOT NULL,
    reason text,
    reason_note text,
    topic text,
    question text,
    reply text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_reply_feedback_rating_check CHECK ((rating = ANY (ARRAY['up'::text, 'down'::text]))),
    CONSTRAINT conv_reply_feedback_reason_check CHECK ((reason = ANY (ARRAY['wrong_answer'::text, 'did_not_answer'::text, 'too_long'::text, 'hard_to_understand'::text, 'other'::text])))
);


ALTER TABLE public.conv_reply_feedback OWNER TO arravindseetharaman;

--
-- Name: conv_reply_feedback_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: arravindseetharaman
--

CREATE SEQUENCE public.conv_reply_feedback_feedback_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.conv_reply_feedback_feedback_id_seq OWNER TO arravindseetharaman;

--
-- Name: conv_reply_feedback_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: arravindseetharaman
--

ALTER SEQUENCE public.conv_reply_feedback_feedback_id_seq OWNED BY public.conv_reply_feedback.feedback_id;


--
-- Name: conv_session; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_session (
    session_id uuid NOT NULL,
    activity_id uuid NOT NULL,
    messages jsonb DEFAULT '[]'::jsonb NOT NULL,
    topic text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    customer_version integer,
    category_version integer
);


ALTER TABLE public.conv_session OWNER TO arravindseetharaman;

--
-- Name: conv_static_reply; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_static_reply (
    gcid text NOT NULL,
    intent text NOT NULL,
    patterns text[] DEFAULT '{}'::text[] NOT NULL,
    replies text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_static_reply_intent_check CHECK ((intent ~ '^[a-z][a-z0-9_]*$'::text)),
    CONSTRAINT conv_static_reply_replies_check CHECK ((cardinality(replies) >= 10))
);


ALTER TABLE public.conv_static_reply OWNER TO arravindseetharaman;

--
-- Name: TABLE conv_static_reply; Type: COMMENT; Schema: public; Owner: arravindseetharaman
--

COMMENT ON TABLE public.conv_static_reply IS 'Fixed replies (10 or more per intent) for greetings, thanks, goodbye and similar. gcid = general is shared by every category; a category row with the same intent replaces it. patterns are the whole messages that trigger the intent; empty for intents the code triggers itself.';


--
-- Name: conv_tool; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_tool (
    name text NOT NULL,
    description text NOT NULL,
    inputs jsonb NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_tool_inputs_check CHECK ((jsonb_typeof(inputs) = 'object'::text)),
    CONSTRAINT conv_tool_name_check CHECK ((name ~ '^[a-z][a-z0-9_]*$'::text))
);


ALTER TABLE public.conv_tool OWNER TO arravindseetharaman;

--
-- Name: conv_visitor; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_visitor (
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    visitor_id uuid NOT NULL,
    have_consent boolean NOT NULL,
    consent_choice text,
    consent_at timestamp with time zone,
    consent_notice_version text,
    first_seen_at timestamp with time zone NOT NULL,
    last_seen_at timestamp with time zone NOT NULL,
    visits integer DEFAULT 0 NOT NULL,
    widget_seconds_total integer DEFAULT 0 NOT NULL,
    page_seconds_total integer DEFAULT 0 NOT NULL,
    score_72h integer DEFAULT 0 NOT NULL,
    city text,
    state text,
    blocked_until timestamp with time zone,
    block_count integer DEFAULT 0 NOT NULL,
    last_block_at timestamp with time zone,
    abuse_strikes integer DEFAULT 0 NOT NULL,
    visit_summaries jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conv_visitor_consent_choice_check CHECK ((consent_choice = ANY (ARRAY['accepted'::text, 'declined'::text, 'withdrawn'::text])))
);


ALTER TABLE public.conv_visitor OWNER TO arravindseetharaman;

--
-- Name: conv_web_fact; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.conv_web_fact (
    fact_id uuid DEFAULT gen_random_uuid() NOT NULL,
    professional_id uuid NOT NULL,
    domain text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    source_url text NOT NULL,
    web_value text,
    scraped_at timestamp with time zone DEFAULT now() NOT NULL,
    confirmed boolean DEFAULT false NOT NULL,
    shared boolean DEFAULT true NOT NULL,
    confirmed_by text,
    confirmed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conv_web_fact OWNER TO arravindseetharaman;

--
-- Name: exp_category_compliance; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.exp_category_compliance (
    gcid text NOT NULL,
    display_license_on_email boolean,
    license_display_format text,
    license_label text,
    required_disclaimers text[],
    content_restrictions text[],
    prohibited_phrases text[],
    required_disclosures text[],
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE public.exp_category_compliance OWNER TO arravindseetharaman;

--
-- Name: exp_category_knowledge; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.exp_category_knowledge (
    id uuid NOT NULL,
    gcid text NOT NULL,
    entity_type text NOT NULL,
    pricing_tier text NOT NULL,
    status text NOT NULL,
    exclusion_reason text,
    services jsonb,
    compliance_rules text[],
    expertise_signals jsonb,
    ai_agents jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    conversion_actions jsonb
);


ALTER TABLE public.exp_category_knowledge OWNER TO arravindseetharaman;

--
-- Name: exp_entitlements; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.exp_entitlements (
    id uuid NOT NULL,
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    product_key text NOT NULL,
    state text NOT NULL,
    source text,
    tokens_included integer,
    config jsonb,
    granted_by text,
    granted_at timestamp with time zone,
    expires_at timestamp with time zone
);


ALTER TABLE public.exp_entitlements OWNER TO arravindseetharaman;

--
-- Name: exp_entity; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.exp_entity (
    entity_id uuid NOT NULL,
    entity_type text NOT NULL,
    display_name text NOT NULL,
    slug text,
    status text NOT NULL,
    claim_state text NOT NULL,
    identity_keys jsonb NOT NULL,
    confidence numeric NOT NULL,
    merged_into uuid,
    source text,
    evidence jsonb,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    last_observed_at timestamp with time zone,
    last_verified_at timestamp with time zone,
    is_demo boolean NOT NULL,
    removal_reason text,
    removed_at timestamp with time zone,
    hydration text NOT NULL,
    attributes jsonb NOT NULL
);


ALTER TABLE public.exp_entity OWNER TO arravindseetharaman;

--
-- Name: organizations; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.organizations (
    id uuid NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    gcid text,
    entity_type text,
    address_street text,
    address_city text,
    address_state text,
    address_zip text,
    address_country text,
    parent_org_id uuid,
    claimed boolean,
    is_active boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    is_demo boolean NOT NULL,
    legal_name text,
    description text,
    short_description text,
    logo_url text,
    cover_photo_url text,
    website_url text,
    canonical_url text,
    is_single_pro_office boolean,
    phone text,
    email text,
    latitude numeric(9,6),
    longitude numeric(9,6),
    hierarchy_path text,
    hierarchy_depth smallint,
    gbp_place_id text,
    gbp_cid text,
    gbp_connected boolean,
    gbp_last_sync timestamp with time zone,
    schema_type text,
    wikidata_id text,
    same_as text[],
    search_rank_score smallint,
    score_updated_at timestamp with time zone,
    claimed_at timestamp with time zone,
    territory_id uuid,
    account_tier text
);


ALTER TABLE public.organizations OWNER TO arravindseetharaman;

--
-- Name: professionals; Type: TABLE; Schema: public; Owner: arravindseetharaman
--

CREATE TABLE public.professionals (
    id uuid NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    display_name text,
    slug text NOT NULL,
    gcid text,
    address_city text,
    address_state text,
    address_zip text,
    primary_org_id uuid,
    primary_license_number text,
    primary_license_type text,
    primary_license_state text,
    primary_license_verified boolean,
    user_id uuid,
    claimed boolean,
    is_active boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    is_demo boolean NOT NULL,
    headline text,
    bio text,
    short_bio text,
    photo_url text,
    cover_photo_url text,
    canonical_url text,
    job_title text,
    phone text,
    email text,
    website_url text,
    primary_license_verified_at timestamp with time zone,
    gbp_place_id text,
    gbp_connected boolean,
    gbp_last_sync timestamp with time zone,
    languages text[],
    markets_served text[],
    zip_codes_served text[],
    schema_type text,
    wikidata_id text,
    same_as text[],
    search_rank_score smallint,
    score_updated_at timestamp with time zone,
    local_rank smallint,
    local_rank_of smallint,
    local_rank_updated timestamp with time zone,
    claimed_at timestamp with time zone,
    claim_method text,
    claim_confidence smallint,
    compliance_complete boolean,
    compliance_score smallint,
    territory_id uuid,
    detail_url text,
    nodalized_at timestamp with time zone
);


ALTER TABLE public.professionals OWNER TO arravindseetharaman;

--
-- Name: conv_change_log change_id; Type: DEFAULT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_change_log ALTER COLUMN change_id SET DEFAULT nextval('public.conv_change_log_change_id_seq'::regclass);


--
-- Name: conv_log log_id; Type: DEFAULT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_log ALTER COLUMN log_id SET DEFAULT nextval('public.conv_log_log_id_seq'::regclass);


--
-- Name: conv_reply_feedback feedback_id; Type: DEFAULT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_reply_feedback ALTER COLUMN feedback_id SET DEFAULT nextval('public.conv_reply_feedback_feedback_id_seq'::regclass);


--
-- Name: conv_action conv_action_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_action
    ADD CONSTRAINT conv_action_pkey PRIMARY KEY (gcid, action_key);


--
-- Name: conv_activity conv_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_activity
    ADD CONSTRAINT conv_activity_pkey PRIMARY KEY (activity_id);


--
-- Name: conv_calendar_connection conv_calendar_connection_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_calendar_connection
    ADD CONSTRAINT conv_calendar_connection_pkey PRIMARY KEY (professional_id);


--
-- Name: conv_category_settings conv_category_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_category_settings
    ADD CONSTRAINT conv_category_settings_pkey PRIMARY KEY (gcid);


--
-- Name: conv_change_log conv_change_log_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_change_log
    ADD CONSTRAINT conv_change_log_pkey PRIMARY KEY (change_id);


--
-- Name: conv_critical_reply conv_critical_reply_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_critical_reply
    ADD CONSTRAINT conv_critical_reply_pkey PRIMARY KEY (gcid, topic_id);


--
-- Name: conv_daily conv_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_daily
    ADD CONSTRAINT conv_daily_pkey PRIMARY KEY (professional_id, domain, day);


--
-- Name: conv_domains conv_domains_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_domains
    ADD CONSTRAINT conv_domains_pkey PRIMARY KEY (site_key);


--
-- Name: conv_domains conv_domains_professional_id_domain_key; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_domains
    ADD CONSTRAINT conv_domains_professional_id_domain_key UNIQUE (professional_id, domain);


--
-- Name: conv_handover conv_handover_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_handover
    ADD CONSTRAINT conv_handover_pkey PRIMARY KEY (handover_id);


--
-- Name: conv_hot_visitor conv_hot_visitor_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_hot_visitor
    ADD CONSTRAINT conv_hot_visitor_pkey PRIMARY KEY (professional_id, domain, visitor_id);


--
-- Name: conv_log conv_log_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_log
    ADD CONSTRAINT conv_log_pkey PRIMARY KEY (log_id);


--
-- Name: conv_menu conv_menu_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_menu
    ADD CONSTRAINT conv_menu_pkey PRIMARY KEY (menu_id);


--
-- Name: conv_professional_menu conv_professional_menu_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_professional_menu
    ADD CONSTRAINT conv_professional_menu_pkey PRIMARY KEY (professional_id, menu_id);


--
-- Name: conv_professional_settings conv_professional_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_professional_settings
    ADD CONSTRAINT conv_professional_settings_pkey PRIMARY KEY (professional_id);


--
-- Name: conv_question conv_question_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_question
    ADD CONSTRAINT conv_question_pkey PRIMARY KEY (question_id);


--
-- Name: conv_question conv_question_professional_id_domain_question_text_key; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_question
    ADD CONSTRAINT conv_question_professional_id_domain_question_text_key UNIQUE (professional_id, domain, question_text);


--
-- Name: conv_reply_feedback conv_reply_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_reply_feedback
    ADD CONSTRAINT conv_reply_feedback_pkey PRIMARY KEY (feedback_id);


--
-- Name: conv_session conv_session_activity_id_key; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_session
    ADD CONSTRAINT conv_session_activity_id_key UNIQUE (activity_id);


--
-- Name: conv_session conv_session_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_session
    ADD CONSTRAINT conv_session_pkey PRIMARY KEY (session_id);


--
-- Name: conv_static_reply conv_static_reply_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_static_reply
    ADD CONSTRAINT conv_static_reply_pkey PRIMARY KEY (gcid, intent);


--
-- Name: conv_tool conv_tool_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_tool
    ADD CONSTRAINT conv_tool_pkey PRIMARY KEY (name);


--
-- Name: conv_visitor conv_visitor_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_visitor
    ADD CONSTRAINT conv_visitor_pkey PRIMARY KEY (professional_id, domain, visitor_id);


--
-- Name: conv_web_fact conv_web_fact_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_web_fact
    ADD CONSTRAINT conv_web_fact_pkey PRIMARY KEY (fact_id);


--
-- Name: conv_web_fact conv_web_fact_professional_id_key_key; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_web_fact
    ADD CONSTRAINT conv_web_fact_professional_id_key_key UNIQUE (professional_id, key);


--
-- Name: exp_category_compliance exp_category_compliance_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.exp_category_compliance
    ADD CONSTRAINT exp_category_compliance_pkey PRIMARY KEY (gcid);


--
-- Name: exp_category_knowledge exp_category_knowledge_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.exp_category_knowledge
    ADD CONSTRAINT exp_category_knowledge_pkey PRIMARY KEY (id);


--
-- Name: exp_entitlements exp_entitlements_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.exp_entitlements
    ADD CONSTRAINT exp_entitlements_pkey PRIMARY KEY (id);


--
-- Name: exp_entity exp_entity_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.exp_entity
    ADD CONSTRAINT exp_entity_pkey PRIMARY KEY (entity_id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: professionals professionals_pkey; Type: CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.professionals
    ADD CONSTRAINT professionals_pkey PRIMARY KEY (id);


--
-- Name: conv_activity_pro_started_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_activity_pro_started_idx ON public.conv_activity USING btree (professional_id, domain, started_at DESC);


--
-- Name: conv_activity_retention_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_activity_retention_idx ON public.conv_activity USING btree (updated_at);


--
-- Name: conv_activity_visitor_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_activity_visitor_idx ON public.conv_activity USING btree (professional_id, domain, visitor_id);


--
-- Name: conv_change_log_pro_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_change_log_pro_idx ON public.conv_change_log USING btree (professional_id, changed_at DESC);


--
-- Name: conv_daily_pro_day_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_daily_pro_day_idx ON public.conv_daily USING btree (professional_id, day);


--
-- Name: conv_handover_pro_status_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_handover_pro_status_idx ON public.conv_handover USING btree (professional_id, status, created_at DESC);


--
-- Name: conv_handover_session_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_handover_session_idx ON public.conv_handover USING btree (session_id);


--
-- Name: conv_hot_visitor_pro_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_hot_visitor_pro_idx ON public.conv_hot_visitor USING btree (professional_id, domain, last_hot_at DESC);


--
-- Name: conv_log_pro_time_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_log_pro_time_idx ON public.conv_log USING btree (professional_id, event_time DESC);


--
-- Name: conv_log_time_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_log_time_idx ON public.conv_log USING btree (event_time DESC);


--
-- Name: conv_question_pro_count_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_question_pro_count_idx ON public.conv_question USING btree (professional_id, domain, asked_count DESC);


--
-- Name: conv_reply_feedback_pro_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_reply_feedback_pro_idx ON public.conv_reply_feedback USING btree (professional_id, domain, rated_at DESC);


--
-- Name: conv_reply_feedback_session_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_reply_feedback_session_idx ON public.conv_reply_feedback USING btree (session_id);


--
-- Name: conv_session_retention_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_session_retention_idx ON public.conv_session USING btree (updated_at);


--
-- Name: conv_visitor_hot_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_visitor_hot_idx ON public.conv_visitor USING btree (professional_id, domain, score_72h DESC);


--
-- Name: conv_visitor_pro_seen_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_visitor_pro_seen_idx ON public.conv_visitor USING btree (professional_id, domain, last_seen_at DESC);


--
-- Name: conv_visitor_retention_idx; Type: INDEX; Schema: public; Owner: arravindseetharaman
--

CREATE INDEX conv_visitor_retention_idx ON public.conv_visitor USING btree (updated_at);


--
-- Name: conv_activity conv_activity_professional_id_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_activity
    ADD CONSTRAINT conv_activity_professional_id_domain_fkey FOREIGN KEY (professional_id, domain) REFERENCES public.conv_domains(professional_id, domain) ON DELETE CASCADE;


--
-- Name: conv_activity conv_activity_professional_id_domain_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_activity
    ADD CONSTRAINT conv_activity_professional_id_domain_visitor_id_fkey FOREIGN KEY (professional_id, domain, visitor_id) REFERENCES public.conv_visitor(professional_id, domain, visitor_id) ON DELETE CASCADE;


--
-- Name: conv_calendar_connection conv_calendar_connection_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_calendar_connection
    ADD CONSTRAINT conv_calendar_connection_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE CASCADE;


--
-- Name: conv_change_log conv_change_log_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_change_log
    ADD CONSTRAINT conv_change_log_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE CASCADE;


--
-- Name: conv_daily conv_daily_professional_id_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_daily
    ADD CONSTRAINT conv_daily_professional_id_domain_fkey FOREIGN KEY (professional_id, domain) REFERENCES public.conv_domains(professional_id, domain) ON DELETE CASCADE;


--
-- Name: conv_domains conv_domains_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_domains
    ADD CONSTRAINT conv_domains_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE CASCADE;


--
-- Name: conv_handover conv_handover_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_handover
    ADD CONSTRAINT conv_handover_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE CASCADE;


--
-- Name: conv_handover conv_handover_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_handover
    ADD CONSTRAINT conv_handover_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.conv_session(session_id) ON DELETE SET NULL;


--
-- Name: conv_hot_visitor conv_hot_visitor_professional_id_domain_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_hot_visitor
    ADD CONSTRAINT conv_hot_visitor_professional_id_domain_visitor_id_fkey FOREIGN KEY (professional_id, domain, visitor_id) REFERENCES public.conv_visitor(professional_id, domain, visitor_id) ON DELETE CASCADE;


--
-- Name: conv_log conv_log_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_log
    ADD CONSTRAINT conv_log_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE SET NULL;


--
-- Name: conv_professional_menu conv_professional_menu_menu_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_professional_menu
    ADD CONSTRAINT conv_professional_menu_menu_id_fkey FOREIGN KEY (menu_id) REFERENCES public.conv_menu(menu_id) ON DELETE CASCADE;


--
-- Name: conv_professional_menu conv_professional_menu_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_professional_menu
    ADD CONSTRAINT conv_professional_menu_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE CASCADE;


--
-- Name: conv_professional_settings conv_professional_settings_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_professional_settings
    ADD CONSTRAINT conv_professional_settings_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.professionals(id);


--
-- Name: conv_question conv_question_professional_id_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_question
    ADD CONSTRAINT conv_question_professional_id_domain_fkey FOREIGN KEY (professional_id, domain) REFERENCES public.conv_domains(professional_id, domain) ON DELETE CASCADE;


--
-- Name: conv_reply_feedback conv_reply_feedback_professional_id_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_reply_feedback
    ADD CONSTRAINT conv_reply_feedback_professional_id_domain_fkey FOREIGN KEY (professional_id, domain) REFERENCES public.conv_domains(professional_id, domain) ON DELETE CASCADE;


--
-- Name: conv_reply_feedback conv_reply_feedback_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_reply_feedback
    ADD CONSTRAINT conv_reply_feedback_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.conv_session(session_id) ON DELETE SET NULL;


--
-- Name: conv_session conv_session_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_session
    ADD CONSTRAINT conv_session_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.conv_activity(activity_id) ON DELETE CASCADE;


--
-- Name: conv_visitor conv_visitor_professional_id_domain_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_visitor
    ADD CONSTRAINT conv_visitor_professional_id_domain_fkey FOREIGN KEY (professional_id, domain) REFERENCES public.conv_domains(professional_id, domain) ON DELETE CASCADE;


--
-- Name: conv_web_fact conv_web_fact_professional_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: arravindseetharaman
--

ALTER TABLE ONLY public.conv_web_fact
    ADD CONSTRAINT conv_web_fact_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES public.conv_professional_settings(professional_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict JdKubmNgIhAAfSbkEL6bOjYuJK9qfHBhkA7pnvGFd6sciFiEmNrXpAa4bnr3XcP

