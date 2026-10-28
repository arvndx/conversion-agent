# Conversion Agent: input and output schema

Local database `conversion_agent`, generated 2026-10-25. Sample rows are demo data, except the copied production tables, which show counts and columns only.

## Input tables

### `conv_professional_settings`

One row per professional: booking, availability, slots, notifications, display switches, services, special fields, hours, offers, handover extras and the kill switch.

Rows: 6

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `professional_id` | uuid | no |  |
| `timezone` | text | no |  |
| `booking_enabled` | boolean | no | false |
| `availability` | jsonb | no | '{}'::jsonb |
| `slot_minutes` | smallint | no | 15 |
| `bookings_per_slot` | smallint | no | 4 |
| `hot_visitor_threshold` | smallint | no | 60 |
| `notify_by` | text[] | no | '{email}'::text[] |
| `display_switches` | jsonb | no | '{}'::jsonb |
| `services` | text[] | no | '{}'::text[] |
| `special_fields` | jsonb | no | '{}'::jsonb |
| `opening_hours` | jsonb | no | '{}'::jsonb |
| `response_hours` | jsonb | no | '{}'::jsonb |
| `current_offers` | text[] | no | '{}'::text[] |
| `handover_extra_fields` | text[] | no | '{}'::text[] |
| `kill_switch` | text | no | 'none'::text |
| `kill_switch_reason` | text | yes |  |
| `kill_switch_by` | text | yes |  |
| `kill_switch_at` | timestamp with time zone | yes |  |
| `updated_at` | timestamp with time zone | no | now() |
| `updated_by` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `public_phone` | text | yes |  |
| `public_email` | text | yes |  |

Constraints:
- check: `CHECK ((bookings_per_slot > 0))`
- check: `CHECK ((kill_switch = ANY (ARRAY['none'::text, 'stop_new_chats'::text, 'stop_everything'::text])))`
- check: `CHECK (((notify_by <@ ARRAY['phone'::text, 'email'::text]) AND (cardinality(notify_by) > 0)))`
- check: `CHECK ((slot_minutes > 0))`
- foreign key: `FOREIGN KEY (professional_id) REFERENCES professionals(id)`
- primary key: `PRIMARY KEY (professional_id)`

Demo data:

| professional_id | timezone | booking_enabled | availability | slot_minutes | bookings_per_slot | hot_visitor_threshold | notify_by | display_switches | services | special_fields | opening_hours | response_hours | current_offers | handover_extra_fields | kill_switch | kill_switch_reason | kill_switch_by | kill_switch_at | updated_at | updated_by | created_at | public_phone | public_email |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 483dc8e7-3f03-5fbb-878b-77ee433ed0b3 | America/Chicago | True | {"fri": [["09:00", "17:00"]], "mon": [["09:00", "17:00"]], "sat": [["10:00", "14:00"]], "thu": [["09:00", "... | 15 | 4 | 60 | ["email", "phone"] | {"email": "disable", "phone": "enable", "booking_link": "enable"} | ["dine-in service", "takeout orders", "catering and private events"] | {"parking": "available"} | {"sat": "10:00-14:00", "sun": "closed", "mon_fri": "09:00-17:00"} | {"mon_fri": "09:00-17:00"} | [] | [] | none |  |  |  | 2026-10-25T10:32+05:30 | demo | 2026-10-25T11:41+05:30 | +1 555 0101 | american-restaurant-1@demo.example |
| 90d1fb82-bced-5771-9aae-958565161949 | America/Los_Angeles | False | {} | 15 | 4 | 60 | ["email"] | {"email": "disable", "phone": "enable", "booking_link": "enable"} | ["office space leasing and sales", "retail space leasing and tenant mix advisory", "industrial and warehous... | {} | {"sat": "10:00-14:00", "sun": "closed", "mon_fri": "09:00-17:00"} | {"mon_fri": "09:00-17:00"} | [] | [] | none |  |  |  | 2026-10-25T10:32+05:30 | demo | 2026-10-25T11:41+05:30 | +1 555 0102 | commercial-real-estate-agency-2@demo.example |

### `conv_domains`

The sites of a professional. Each domain has its own site key and widget colours.

Rows: 12

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `site_key` | text | no |  |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `status` | text | no | 'active'::text |
| `primary_color` | text | no | '#7a2e1d'::text |
| `accent_color` | text | no | '#a2432b'::text |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((accent_color ~ '^#[0-9a-fA-F]{6}$'::text))`
- check: `CHECK ((primary_color ~ '^#[0-9a-fA-F]{6}$'::text))`
- check: `CHECK ((site_key ~ '^wk_(live|test)_[a-z0-9]{8,40}$'::text))`
- check: `CHECK ((status = ANY (ARRAY['active'::text, 'paused'::text])))`
- foreign key: `FOREIGN KEY (professional_id) REFERENCES conv_professional_settings(professional_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (site_key)`
- unique: `UNIQUE (professional_id, domain)`

Demo data:

| site_key | professional_id | domain | status | primary_color | accent_color | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| wk_test_czm7mavmtqo9y60g8uj9tptw | e5e4ebed-f138-5cc2-a554-967272decabd | demo-lender-1.example | active | #7a2e1d | #a2432b | 2026-10-25T10:32+05:30 | 2026-10-25T11:41+05:30 |
| wk_test_afemvx8b61sg087gc0rojcqx | e5e4ebed-f138-5cc2-a554-967272decabd | demo-lender-2.example | active | #7a2e1d | #a2432b | 2026-10-25T10:32+05:30 | 2026-10-25T11:41+05:30 |

### Links (no `conv_professional_link` table any more)

A business's links are fields in `conv_professional_settings.special_fields`, under generic names that end in `_link`:
`booking_link`, `order_link`, `menu_link`, `subscribe_link`, `apply_link`, `status_link`, `listings_link`, `info_link`. Which links
an action uses is named in its details step (`provides`, see `conv_action.steps`). The dashboard keeps these names out of the
custom fields.

### `conv_action`

Every conversion action per category. `steps` (jsonb, ordered) is how the agent completes it: each step is a route (`booking`,
`details` or `handover`) with the tools it uses (rows of `conv_tool`), what it collects from the visitor (`collect`) and, for a
details step, which business fields it gives (`provides`). `enabled` switches an action off without deleting it. (The older
columns `routes`, `collect_fields` and `show_fields` were dropped with the classic chat engine.)

`collect` is a list of entries, each stored in the table: a field `{"key": "name", "required": true}` (a field that is not a
standard one also has `type` and `description`), or an either group `{"any_of": ["phone", "email"]}` (at least one is
required). `request_type` is the label saved on every request made through the action (for example `table booking`,
`appointment booking`, `business detail handover`, `direct handover`). The rows with `gcid = 'general'` are the handovers no
business button starts: `critical_handover`, `ai_down_handover`, `fallback_handover`, `direct_handover`; every category
bundle carries them as `general_actions`.

Rows: 32 (28 category actions and 4 general actions)

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `gcid` | text | no |  |
| `action_key` | text | no |  |
| `source_entity_type` | text | no |  |
| `action_name` | text | no |  |
| `schema_action` | text | no |  |
| `agent_goal` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |
| `profile_button` | text | yes |  |
| `steps` | jsonb | yes |  |
| `enabled` | boolean | no | true |
| `source` | text | no | 'production'::text |
| `request_type` | text | yes |  |

Constraints:
- check: `CHECK ((source_entity_type = ANY (ARRAY['professional'::text, 'location'::text])))`
- primary key: `PRIMARY KEY (gcid, action_key)`

Demo data:

| gcid | action_key | action_name | profile_button | request_type | steps (routes) |
| --- | --- | --- | --- | --- | --- |
| gcid:american_restaurant | book_reservation | Reserve a Table | Book a Table | table booking | booking, details, handover |
| gcid:american_restaurant | view_menu | Browse Our Menu | See Our Menu | business detail handover | details, handover |
| gcid:mortgage_broker | get_prequalified | Get pre-qualified | Get Pre-Qualified | direct handover | handover |
| general | ai_down_handover | Chat assistant unavailable |  | ai down handover | handover |

### `conv_tool`

The tools the agent can use: name, description and inputs. The code has one handler per tool name. An action's steps name the
tools they use, and a business is offered the tools its category's actions name. `request_handoff` opens the request form (a
card in the widget); the form's fields come from the action's `collect`, and the standard fields are defined once in this
row's inputs.

Rows: 2 (`get_business_info`, `request_handoff`). `request_handoff` also defines the standard form fields (label, format, why we ask) under `prefill`.

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `name` | text | no |  |
| `description` | text | no |  |
| `inputs` | jsonb | no |  |
| `enabled` | boolean | no | true |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((jsonb_typeof(inputs) = 'object'::text))`
- check: `CHECK ((name ~ '^[a-z][a-z0-9_]*$'::text))`
- primary key: `PRIMARY KEY (name)`

### `conv_static_reply`

The fixed replies for greetings, thanks, goodbye, apology, "are you a bot?" and similar, so these messages need no model call.
`gcid = 'general'` rows are shared by every category; a row of a category with the same `intent` replaces the shared one in that
category's bundle (`static_replies`). `patterns` are the whole messages (lower case words, no punctuation) that trigger the
intent; the code triggers `abuse_warning` and `fallback_apology` itself, so they have none. Replies may use `{customer_name}` and
`{category}`.

Rows: 13 (all `general`: greeting, how_are_you, ai_identity, thanks, goodbye, acknowledgement, apology, just_browsing, social,
privacy, unclear, abuse_warning, fallback_apology)

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `gcid` | text | no |  |
| `intent` | text | no |  |
| `patterns` | text[] | no | '{}'::text[] |
| `replies` | text[] | no |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((cardinality(replies) >= 10))`
- check: `CHECK ((intent ~ '^[a-z][a-z0-9_]*$'::text))`
- primary key: `PRIMARY KEY (gcid, intent)`

### `conv_category_settings`

Category rules: welcome, teaser, never-ask list, abuse rules, scoring rules, special field definitions, messages and handover timing.

Rows: 5

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `gcid` | text | no |  |
| `welcome_message` | text | no |  |
| `teaser_text` | text | no |  |
| `never_ask` | text[] | no | '{}'::text[] |
| `abuse_rules` | jsonb | no |  |
| `scoring_rules` | jsonb | no |  |
| `special_field_definitions` | jsonb | no | '[]'::jsonb |
| `other_messages` | jsonb | no | '{}'::jsonb |
| `handover_wait_seconds` | integer | no | 300 |
| `idle_close_minutes` | integer | no | 10 |
| `general_knowledge_allowed` | boolean | no | false |
| `guardrails_text` | text | yes |  |
| `abuse_blocklist` | text[] | yes |  |
| `abuse_allowlist` | text[] | yes |  |
| `updated_at` | timestamp with time zone | no | now() |
| `updated_by` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `services` | text[] | no | '{}'::text[] |
| `compliance_rules` | text[] | no | '{}'::text[] |
| `prohibited_phrases` | text[] | no | '{}'::text[] |
| `required_disclaimers` | text[] | no | '{}'::text[] |
| `content_restrictions` | text[] | no | '{}'::text[] |

Constraints:
- primary key: `PRIMARY KEY (gcid)`

Demo data:

| gcid | welcome_message | teaser_text | never_ask | abuse_rules | scoring_rules | special_field_definitions | other_messages | handover_wait_seconds | idle_close_minutes | general_knowledge_allowed | guardrails_text | abuse_blocklist | abuse_allowlist | updated_at | updated_by | created_at | services | compliance_rules | prohibited_phrases | required_disclaimers | content_restrictions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gcid:mortgage_lender | I'm an AI assistant. How can I help you? | Hi, I'm an AI assistant for {customer_name}. I'm here to help you. | ["payment card numbers", "passwords", "social security number", "bank account number", "income", "credit sc... | {"block_scope": "browser_flag_and_session", "block_on_strike": 3, "block_minutes_test": 3, "warning_on_stri... | [{"event": "active_over_4_minutes", "points": 15, "limit_per_session": 1}, {"event": "booking_link_click", ... | [] | {"ai_busy": "Our chatbot is busy with multiple sessions. So I'm capturing your query and conveying it with ... | 300 | 10 | False |  |  |  | 2026-10-25T10:32+05:30 | demo | 2026-10-25T11:41+05:30 | ["conventional purchase mortgage origination", "FHA insured home loans", "VA guaranteed mortgage loans", "U... | ["Truth in Lending Act Regulation Z disclosure requirements", "Real Estate Settlement Procedures Act Regula... | ["guaranteed approval", "no credit check required", "lowest rates guaranteed", "pre-approved with no income... | ["NMLS company ID and individual originator NMLS IDs must be disclosed on all advertising and communication... | ["All rate advertisements must include APR per Regulation Z Trigger Terms rules", "Representative example r... |
| gcid:mortgage_broker | I'm an AI assistant. How can I help you? | Hi, I'm an AI assistant for {customer_name}. I'm here to help you. | ["payment card numbers", "passwords", "social security number", "bank account number", "income", "credit sc... | {"block_scope": "browser_flag_and_session", "block_on_strike": 3, "block_minutes_test": 3, "warning_on_stri... | [{"event": "active_over_4_minutes", "points": 15, "limit_per_session": 1}, {"event": "booking_link_click", ... | [] | {"ai_busy": "Our chatbot is busy with multiple sessions. So I'm capturing your query and conveying it with ... | 300 | 10 | False |  |  |  | 2026-10-25T10:32+05:30 | demo | 2026-10-25T11:41+05:30 | ["FHA purchase loans", "VA loans for veterans", "conventional purchase loans", "jumbo loans", "refinance ra... | ["NMLS license required — display on all advertising and communications", "Equal Housing Lender disclosure ... | ["guaranteed approval", "guaranteed lowest rate", "we will match any rate guaranteed", "no income verificat... | ["NMLS # [number] displayed on all advertising, websites, and business cards per SAFE Act", "Equal Housing ... | ["All rate and payment advertising must comply with Regulation Z (Truth in Lending Act) triggering terms", ... |

### `conv_critical_reply`

Critical topics per category, each with the fixed approved reply.

Rows: 8

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `gcid` | text | no |  |
| `topic_id` | text | no |  |
| `description` | text | no |  |
| `examples` | jsonb | no | '[]'::jsonb |
| `reply` | text | no |  |
| `action` | text | no | 'handover'::text |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- primary key: `PRIMARY KEY (gcid, topic_id)`

Demo data:

| gcid | topic_id | description | examples | reply | action | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gcid:mortgage_lender | rate_quote | a mortgage rate, APR, payment or quote for a loan | ["what rate would I get on a 30 year loan?", "what's the APR for a refinance?"] | Rates and payments depend on your details and change often, so I can't quote one here. Shall I pass your qu... | handover | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |
| gcid:mortgage_lender | approval_question | whether the visitor will be approved, or a guarantee of a loan or rate | ["will I be approved with a 600 credit score?", "can you guarantee my loan approval?"] | I can't say whether you'll be approved. A loan officer can review your details with you. Shall I pass this on? | handover | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |

### `conv_calendar_connection`

The Google Calendar connection of a professional. Status only until a calendar is connected.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `professional_id` | uuid | no |  |
| `provider` | text | no | 'google'::text |
| `calendar_id` | text | yes |  |
| `account_email` | text | yes |  |
| `token_encrypted` | bytea | yes |  |
| `status` | text | no | 'disconnected'::text |
| `connected_at` | timestamp with time zone | yes |  |
| `last_checked_at` | timestamp with time zone | yes |  |
| `last_error` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((status = ANY (ARRAY['connected'::text, 'disconnected'::text])))`
- foreign key: `FOREIGN KEY (professional_id) REFERENCES conv_professional_settings(professional_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (professional_id)`

Demo data:

| professional_id | provider | calendar_id | account_email | token_encrypted | status | connected_at | last_checked_at | last_error | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | google | primary | [your calendar email] |  | disconnected |  |  |  | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |

### `conv_menu`

General menu: dish names and sections.

Rows: 6

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `menu_id` | uuid | no |  |
| `name` | text | no |  |
| `section` | text | no |  |
| `description` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- primary key: `PRIMARY KEY (menu_id)`

Demo data:

| menu_id | name | section | description | created_at | updated_at |
| --- | --- | --- | --- | --- | --- |
| 29570c01-5e96-55b0-8915-eca0deb91a74 | Smash Burger | Mains |  | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |
| c313fb7b-c1d6-555d-b5a0-0d365e672398 | Chicken Sandwich | Mains |  | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |

### `conv_professional_menu`

A professional's price, availability and chef special for each dish.

Rows: 6

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `professional_id` | uuid | no |  |
| `menu_id` | uuid | no |  |
| `price` | numeric(8,2) | no |  |
| `availability` | jsonb | no | '{}'::jsonb |
| `chef_special` | boolean | no | false |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((price >= (0)::numeric))`
- foreign key: `FOREIGN KEY (menu_id) REFERENCES conv_menu(menu_id) ON DELETE CASCADE`
- foreign key: `FOREIGN KEY (professional_id) REFERENCES conv_professional_settings(professional_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (professional_id, menu_id)`

Demo data:

| professional_id | menu_id | price | availability | chef_special | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- |
| 483dc8e7-3f03-5fbb-878b-77ee433ed0b3 | 29570c01-5e96-55b0-8915-eca0deb91a74 | 11.50 | {"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]} | True | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |
| 483dc8e7-3f03-5fbb-878b-77ee433ed0b3 | c313fb7b-c1d6-555d-b5a0-0d365e672398 | 10.00 | {"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]} | False | 2026-10-25T11:41+05:30 | 2026-10-25T11:41+05:30 |

## Output tables

### `conv_visitor`

One row per professional, domain and visitor. Holds consent, aggregated totals, score, location, blocks and a summary per visit. Kept 1 year.

Rows: 2

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `visitor_id` | uuid | no |  |
| `have_consent` | boolean | no |  |
| `consent_choice` | text | yes |  |
| `consent_at` | timestamp with time zone | yes |  |
| `consent_notice_version` | text | yes |  |
| `first_seen_at` | timestamp with time zone | no |  |
| `last_seen_at` | timestamp with time zone | no |  |
| `visits` | integer | no | 0 |
| `widget_seconds_total` | integer | no | 0 |
| `page_seconds_total` | integer | no | 0 |
| `score_72h` | integer | no | 0 |
| `city` | text | yes |  |
| `state` | text | yes |  |
| `blocked_until` | timestamp with time zone | yes |  |
| `block_count` | integer | no | 0 |
| `last_block_at` | timestamp with time zone | yes |  |
| `abuse_strikes` | integer | no | 0 |
| `visit_summaries` | jsonb | no | '[]'::jsonb |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((consent_choice = ANY (ARRAY['accepted'::text, 'declined'::text, 'withdrawn'::text])))`
- foreign key: `FOREIGN KEY (professional_id, domain) REFERENCES conv_domains(professional_id, domain) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (professional_id, domain, visitor_id)`

Demo data:

| professional_id | domain | visitor_id | have_consent | consent_choice | consent_at | consent_notice_version | first_seen_at | last_seen_at | visits | widget_seconds_total | page_seconds_total | score_72h | city | state | blocked_until | block_count | last_block_at | abuse_strikes | visit_summaries | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | 758693b4-c0e9-47a2-9733-a50b7803303c | True | accepted | 2026-10-20T14:44+05:30 | v1 | 2026-10-20T14:44+05:30 | 2026-10-25T15:25+05:30 | 2 | 210 | 410 | 75 | Chicago | IL |  | 0 |  | 0 | [{"at": "2026-10-25T09:20:00Z", "domain": "arravind-demo-1.example", "summary": "Asked about pre-approval, ... | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |
| 483dc8e7-3f03-5fbb-878b-77ee433ed0b3 | demo-diner-1.example | d9d2352e-6084-4b64-b140-8db37b17f888 | False |  |  |  | 2026-10-25T17:30+05:30 | 2026-10-25T17:30+05:30 | 1 | 0 | 60 | 10 | Chicago | IL |  | 0 |  | 0 | [{"at": "2026-10-25T12:00:00Z", "domain": "demo-diner-1.example", "summary": "Viewed the menu, no chat", "a... | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_activity`

One row per visit, with the chat outcome status, location and summary. Kept 20 days.

Rows: 2

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `activity_id` | uuid | no |  |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `visitor_id` | uuid | no |  |
| `have_consent` | boolean | no |  |
| `status` | text | no | 'open'::text |
| `started_at` | timestamp with time zone | no |  |
| `last_activity_at` | timestamp with time zone | no |  |
| `ended_at` | timestamp with time zone | yes |  |
| `city` | text | yes |  |
| `state` | text | yes |  |
| `clicks` | integer | yes |  |
| `time_on_site_seconds` | integer | yes |  |
| `widget_opens` | integer | yes |  |
| `time_in_widget_seconds` | integer | yes |  |
| `referrer_host` | text | yes |  |
| `utm` | jsonb | yes |  |
| `summary` | text | yes |  |
| `session_score` | integer | no | 0 |
| `abuse_strikes` | integer | no | 0 |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((status = ANY (ARRAY['open'::text, 'completed'::text, 'incomplete'::text, 'handed_over'::text, 'blocked'::text])))`
- foreign key: `FOREIGN KEY (professional_id, domain) REFERENCES conv_domains(professional_id, domain) ON DELETE CASCADE`
- foreign key: `FOREIGN KEY (professional_id, domain, visitor_id) REFERENCES conv_visitor(professional_id, domain, visitor_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (activity_id)`

Demo data:

| activity_id | professional_id | domain | visitor_id | have_consent | status | started_at | last_activity_at | ended_at | city | state | clicks | time_on_site_seconds | widget_opens | time_in_widget_seconds | referrer_host | utm | summary | session_score | abuse_strikes | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 9d567502-1f30-49dd-ac03-c23d1991f279 | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | 758693b4-c0e9-47a2-9733-a50b7803303c | True | handed_over | 2026-10-25T14:50+05:30 | 2026-10-25T15:01+05:30 | 2026-10-25T15:01+05:30 | Chicago | IL | 5 | 410 | 1 | 210 | google.com | {"utm_source": "ads"} | Asked about pre-approval, gave name and email, handed over | 45 | 0 | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |
| 0911977a-cff2-493a-be87-e375bbc97a91 | 483dc8e7-3f03-5fbb-878b-77ee433ed0b3 | demo-diner-1.example | d9d2352e-6084-4b64-b140-8db37b17f888 | False | completed | 2026-10-25T17:30+05:30 | 2026-10-25T17:31+05:30 | 2026-10-25T17:31+05:30 | Chicago | IL | 2 | 60 | 0 | 0 |  |  | Viewed the menu, no chat | 10 | 0 | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_session`

One chat per visit: the messages and the topic. Kept 20 days with its visit.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `session_id` | uuid | no |  |
| `activity_id` | uuid | no |  |
| `messages` | jsonb | no | '[]'::jsonb |
| `topic` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- foreign key: `FOREIGN KEY (activity_id) REFERENCES conv_activity(activity_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (session_id)`
- unique: `UNIQUE (activity_id)`

Demo data:

| session_id | activity_id | messages | topic | created_at | updated_at |
| --- | --- | --- | --- | --- | --- |
| ad9c4e02-2fae-4c71-a267-5261587156df | 9d567502-1f30-49dd-ac03-c23d1991f279 | [{"request": "Do you do pre-approval?", "response": "Yes, I can start that with you.", "event_time": "2026-... | pre-approval | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_handover`

Every request a visitor sent through a request form: name, contact, query, extra fields, request type, action and reason. A
booking is a lead too: it differs only by its request type. Kept 1 year.

Rows: 2

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `handover_id` | uuid | no |  |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `session_id` | uuid | yes |  |
| `visitor_id` | uuid | yes |  |
| `name` | text | no |  |
| `email` | text | yes |  |
| `phone` | text | yes |  |
| `reason` | text | no |  |
| `question` | text | no |  |
| `summary` | text | yes |  |
| `extra_fields` | jsonb | no | '{}'::jsonb |
| `city` | text | yes |  |
| `state` | text | yes |  |
| `status` | text | no | 'new'::text |
| `notified_by` | text[] | no | '{}'::text[] |
| `notified_at` | timestamp with time zone | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |
| `action_key` | text | yes |  |
| `request_type` | text | no | 'direct handover'::text |

`request_type` is copied from `conv_action.request_type` of the action the form was opened for. `reason` is the technical
cause (critical_question, system_fallback, ...), `request_type` is what the visitor asked for.

Constraints:
- check: `CHECK (((email IS NOT NULL) OR (phone IS NOT NULL)))`
- check: `CHECK ((reason = ANY (ARRAY['request_from_visitor'::text, 'critical_question'::text, 'unsure_question'::text, 'unavailable_answer'::text, 'time_in_widget'::text, 'system_fallback'::text])))`
- check: `CHECK ((status = ANY (ARRAY['new'::text, 'contacted'::text, 'closed'::text])))`
- foreign key: `FOREIGN KEY (professional_id) REFERENCES conv_professional_settings(professional_id) ON DELETE CASCADE`
- foreign key: `FOREIGN KEY (session_id) REFERENCES conv_session(session_id) ON DELETE SET NULL`
- primary key: `PRIMARY KEY (handover_id)`

Demo data:

| handover_id | professional_id | domain | session_id | visitor_id | name | email | phone | reason | question | summary | extra_fields | city | state | status | notified_by | notified_at | created_at | updated_at | action_key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6d22a7bc-78f6-49c9-8c18-3c63b79fe544 | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | ad9c4e02-2fae-4c71-a267-5261587156df | 758693b4-c0e9-47a2-9733-a50b7803303c | Jane Demo | jane.demo@example.com | +1 555 0100 | critical_question | What rate for a 30-year loan? | Asked for a 30-year rate: critical topic, handed over for a broker to answer | {"loan_amount": "350000"} | Chicago | IL | new | ["email"] | 2026-10-25T15:03+05:30 | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |  |
| adad2a3b-1821-4749-bbd4-d4680daf963f | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | ad9c4e02-2fae-4c71-a267-5261587156df | 758693b4-c0e9-47a2-9733-a50b7803303c | Jane Demo | jane.demo@example.com | +1 555 0100 | request_from_visitor | Please send me a rate quote for a 30-year loan. | Pressed Request a rate quote; wants a 30-year quote | {} | Chicago | IL | new | ["email"] | 2026-10-25T15:06+05:30 | 2026-10-25T12:02+05:30 | 2026-10-25T12:02+05:30 | request_rate_quote |

### `conv_hot_visitor`

Visitors whose score is at or above the professional's threshold, with their summary.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `visitor_id` | uuid | no |  |
| `summary` | text | yes |  |
| `city` | text | yes |  |
| `state` | text | yes |  |
| `first_hot_at` | timestamp with time zone | no |  |
| `last_hot_at` | timestamp with time zone | no |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- foreign key: `FOREIGN KEY (professional_id, domain, visitor_id) REFERENCES conv_visitor(professional_id, domain, visitor_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (professional_id, domain, visitor_id)`

Demo data:

| professional_id | domain | visitor_id | summary | city | state | first_hot_at | last_hot_at | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | 758693b4-c0e9-47a2-9733-a50b7803303c | 4 visits, 210 s in chat, asked about pre-approval | Chicago | IL | 2026-10-24T16:30+05:30 | 2026-10-25T15:25+05:30 | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_question`

Unanswered and missed questions per domain, with how often they were asked. No expiry.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `question_id` | uuid | no |  |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `question_text` | text | no |  |
| `topic` | text | yes |  |
| `asked_count` | integer | no | 1 |
| `first_asked_at` | timestamp with time zone | no |  |
| `last_asked_at` | timestamp with time zone | no |  |
| `answered` | boolean | no | false |
| `status` | text | no | 'open'::text |
| `suggested_action_key` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((status = ANY (ARRAY['open'::text, 'added'::text, 'ignored'::text])))`
- foreign key: `FOREIGN KEY (professional_id, domain) REFERENCES conv_domains(professional_id, domain) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (question_id)`
- unique: `UNIQUE (professional_id, domain, question_text)`

Demo data:

| question_id | professional_id | domain | question_text | topic | asked_count | first_asked_at | last_asked_at | answered | status | suggested_action_key | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5050abd9-2df5-49d6-ada4-d66e52c8940b | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | do you offer 15 year fixed loans | loan_programs | 3 | 2026-10-21T15:30+05:30 | 2026-10-25T15:10+05:30 | False | open |  | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_daily`

Daily totals per professional and domain, with topic counts. No expiry.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `day` | date | no |  |
| `visitors` | integer | no | 0 |
| `chats` | integer | no | 0 |
| `handovers` | integer | no | 0 |
| `hot_visitors` | integer | no | 0 |
| `bookings` | integer | no | 0 |
| `questions_answered` | integer | no | 0 |
| `questions_unanswered` | integer | no | 0 |
| `topic_counts` | jsonb | no | '{}'::jsonb |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- foreign key: `FOREIGN KEY (professional_id, domain) REFERENCES conv_domains(professional_id, domain) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (professional_id, domain, day)`

Demo data:

| professional_id | domain | day | visitors | chats | handovers | hot_visitors | bookings | questions_answered | questions_unanswered | topic_counts | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | 2026-10-25 | 1 | 1 | 1 | 1 | 1 | 4 | 1 | {"pre-approval": 1} | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_reply_feedback`

A thumbs up or down on a reply, with the reason and the question. No expiry.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `feedback_id` | bigint | no | nextval('conv_reply_feedback_feedback_id_seq'::regclass) |
| `professional_id` | uuid | no |  |
| `domain` | text | no |  |
| `session_id` | uuid | yes |  |
| `rated_at` | timestamp with time zone | no | now() |
| `rating` | text | no |  |
| `reason` | text | yes |  |
| `reason_note` | text | yes |  |
| `topic` | text | yes |  |
| `question` | text | yes |  |
| `reply` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((rating = ANY (ARRAY['up'::text, 'down'::text])))`
- check: `CHECK ((reason = ANY (ARRAY['wrong_answer'::text, 'did_not_answer'::text, 'too_long'::text, 'hard_to_understand'::text, 'other'::text])))`
- foreign key: `FOREIGN KEY (professional_id, domain) REFERENCES conv_domains(professional_id, domain) ON DELETE CASCADE`
- foreign key: `FOREIGN KEY (session_id) REFERENCES conv_session(session_id) ON DELETE SET NULL`
- primary key: `PRIMARY KEY (feedback_id)`

Demo data:

| feedback_id | professional_id | domain | session_id | rated_at | rating | reason | reason_note | topic | question | reply | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | ad9c4e02-2fae-4c71-a267-5261587156df | 2026-10-25T11:22+05:30 | down | did_not_answer |  | pre-approval | What rate for a 30-year loan? | Rates depend on your details, so I cannot quote one here. | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_log`

System events: calendar, email, AI and consent events. Kept 1 year.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `log_id` | bigint | no | nextval('conv_log_log_id_seq'::regclass) |
| `event_time` | timestamp with time zone | no | now() |
| `event_type` | text | no |  |
| `actor_type` | text | yes |  |
| `actor_id` | text | yes |  |
| `professional_id` | uuid | yes |  |
| `domain` | text | yes |  |
| `session_id` | uuid | yes |  |
| `visitor_id` | uuid | yes |  |
| `result` | text | yes |  |
| `error_code` | text | yes |  |
| `details` | jsonb | no | '{}'::jsonb |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- check: `CHECK ((actor_type = ANY (ARRAY['operator'::text, 'nora'::text, 'system'::text, 'visitor'::text])))`
- check: `CHECK ((event_type = ANY (ARRAY['operator_action'::text, 'nora_api_call'::text, 'handover_email'::text, 'calendar_failure'::text, 'ai_failure'::text, 'consent_change'::text, 'block_or_rate_limit'::text])))`
- check: `CHECK ((result = ANY (ARRAY['success'::text, 'failure'::text])))`
- foreign key: `FOREIGN KEY (professional_id) REFERENCES conv_professional_settings(professional_id) ON DELETE SET NULL`
- primary key: `PRIMARY KEY (log_id)`

Demo data:

| log_id | event_time | event_type | actor_type | actor_id | professional_id | domain | session_id | visitor_id | result | error_code | details | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-25T11:22+05:30 | calendar_failure | system |  | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example |  |  | failure | not_connected | {"calendar": "primary"} | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

### `conv_change_log`

Audit trail of every dashboard change, with before and after values. Kept 1 year.

Rows: 1

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `change_id` | bigint | no | nextval('conv_change_log_change_id_seq'::regclass) |
| `professional_id` | uuid | no |  |
| `domain` | text | yes |  |
| `changed_at` | timestamp with time zone | no | now() |
| `changed_by` | text | no |  |
| `page` | text | no |  |
| `area` | text | no |  |
| `target` | text | yes |  |
| `action` | text | no |  |
| `summary` | text | no |  |
| `before_value` | jsonb | yes |  |
| `after_value` | jsonb | yes |  |
| `batch_id` | text | yes |  |
| `created_at` | timestamp with time zone | no | now() |
| `updated_at` | timestamp with time zone | no | now() |

Constraints:
- foreign key: `FOREIGN KEY (professional_id) REFERENCES conv_professional_settings(professional_id) ON DELETE CASCADE`
- primary key: `PRIMARY KEY (change_id)`

Demo data:

| change_id | professional_id | domain | changed_at | changed_by | page | area | target | action | summary | before_value | after_value | batch_id | created_at | updated_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ac1161ab-bea2-4ba1-baa5-87f4ee7b48d5 | arravind-demo-1.example | 2026-10-25T11:22+05:30 | demo.operator | admin | booking | booking_enabled | changed | Turned booking on | False | True | save-1 | 2026-10-25T11:22+05:30 | 2026-10-25T11:22+05:30 |

## Copied from production

### `exp_category_knowledge`

Copied from production (read only). Columns trimmed to those the widget uses. Five categories only.

Rows: 8

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `id` | uuid | no |  |
| `gcid` | text | no |  |
| `entity_type` | text | no |  |
| `pricing_tier` | text | no |  |
| `status` | text | no |  |
| `exclusion_reason` | text | yes |  |
| `services` | jsonb | yes |  |
| `compliance_rules` | text[] | yes |  |
| `expertise_signals` | jsonb | yes |  |
| `ai_agents` | jsonb | yes |  |
| `created_at` | timestamp with time zone | yes |  |
| `updated_at` | timestamp with time zone | yes |  |
| `conversion_actions` | jsonb | yes |  |

Constraints:
- primary key: `PRIMARY KEY (id)`

### `exp_category_compliance`

Copied from production (read only). Columns trimmed to those the widget uses. Five categories only.

Rows: 5

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `gcid` | text | no |  |
| `display_license_on_email` | boolean | yes |  |
| `license_display_format` | text | yes |  |
| `license_label` | text | yes |  |
| `required_disclaimers` | text[] | yes |  |
| `content_restrictions` | text[] | yes |  |
| `prohibited_phrases` | text[] | yes |  |
| `required_disclosures` | text[] | yes |  |
| `created_at` | timestamp with time zone | yes |  |
| `updated_at` | timestamp with time zone | yes |  |

Constraints:
- primary key: `PRIMARY KEY (gcid)`

### `exp_entitlements`

Copied from production (read only). Products per organization; the local copy adds conversion_agent rows for demo offices.

Rows: 10

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `id` | uuid | no |  |
| `subject_type` | text | no |  |
| `subject_id` | text | no |  |
| `product_key` | text | no |  |
| `state` | text | no |  |
| `source` | text | yes |  |
| `tokens_included` | integer | yes |  |
| `config` | jsonb | yes |  |
| `granted_by` | text | yes |  |
| `granted_at` | timestamp with time zone | yes |  |
| `expires_at` | timestamp with time zone | yes |  |

Constraints:
- primary key: `PRIMARY KEY (id)`

### `exp_entity`

Copied from production (read only). No rows for these five categories.

Rows: 0

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `entity_id` | uuid | no |  |
| `entity_type` | text | no |  |
| `display_name` | text | no |  |
| `slug` | text | yes |  |
| `status` | text | no |  |
| `claim_state` | text | no |  |
| `identity_keys` | jsonb | no |  |
| `confidence` | numeric | no |  |
| `merged_into` | uuid | yes |  |
| `source` | text | yes |  |
| `evidence` | jsonb | yes |  |
| `created_at` | timestamp with time zone | no |  |
| `updated_at` | timestamp with time zone | no |  |
| `last_observed_at` | timestamp with time zone | yes |  |
| `last_verified_at` | timestamp with time zone | yes |  |
| `is_demo` | boolean | no |  |
| `removal_reason` | text | yes |  |
| `removed_at` | timestamp with time zone | yes |  |
| `hydration` | text | no |  |
| `attributes` | jsonb | no |  |

Constraints:
- primary key: `PRIMARY KEY (entity_id)`

### `organizations`

Copied from production (read only), all columns. Five categories only, plus local demo offices.

Rows: 14

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `id` | uuid | no |  |
| `name` | text | no |  |
| `slug` | text | no |  |
| `gcid` | text | yes |  |
| `entity_type` | text | yes |  |
| `address_street` | text | yes |  |
| `address_city` | text | yes |  |
| `address_state` | text | yes |  |
| `address_zip` | text | yes |  |
| `address_country` | text | yes |  |
| `parent_org_id` | uuid | yes |  |
| `claimed` | boolean | yes |  |
| `is_active` | boolean | yes |  |
| `created_at` | timestamp with time zone | yes |  |
| `updated_at` | timestamp with time zone | yes |  |
| `is_demo` | boolean | no |  |
| `legal_name` | text | yes |  |
| `description` | text | yes |  |
| `short_description` | text | yes |  |
| `logo_url` | text | yes |  |
| `cover_photo_url` | text | yes |  |
| `website_url` | text | yes |  |
| `canonical_url` | text | yes |  |
| `is_single_pro_office` | boolean | yes |  |
| `phone` | text | yes |  |
| `email` | text | yes |  |
| `latitude` | numeric(9,6) | yes |  |
| `longitude` | numeric(9,6) | yes |  |
| `hierarchy_path` | text | yes |  |
| `hierarchy_depth` | smallint | yes |  |
| `gbp_place_id` | text | yes |  |
| `gbp_cid` | text | yes |  |
| `gbp_connected` | boolean | yes |  |
| `gbp_last_sync` | timestamp with time zone | yes |  |
| `schema_type` | text | yes |  |
| `wikidata_id` | text | yes |  |
| `same_as` | text[] | yes |  |
| `search_rank_score` | smallint | yes |  |
| `score_updated_at` | timestamp with time zone | yes |  |
| `claimed_at` | timestamp with time zone | yes |  |
| `territory_id` | uuid | yes |  |
| `account_tier` | text | yes |  |

Constraints:
- primary key: `PRIMARY KEY (id)`

### `professionals`

Copied from production (read only), all columns. Five categories only, plus local demo professionals.

Rows: 13

| Column | Data type | Nullable | Default |
| --- | --- | --- | --- |
| `id` | uuid | no |  |
| `first_name` | text | no |  |
| `last_name` | text | no |  |
| `display_name` | text | yes |  |
| `slug` | text | no |  |
| `gcid` | text | yes |  |
| `address_city` | text | yes |  |
| `address_state` | text | yes |  |
| `address_zip` | text | yes |  |
| `primary_org_id` | uuid | yes |  |
| `primary_license_number` | text | yes |  |
| `primary_license_type` | text | yes |  |
| `primary_license_state` | text | yes |  |
| `primary_license_verified` | boolean | yes |  |
| `user_id` | uuid | yes |  |
| `claimed` | boolean | yes |  |
| `is_active` | boolean | yes |  |
| `created_at` | timestamp with time zone | yes |  |
| `updated_at` | timestamp with time zone | yes |  |
| `is_demo` | boolean | no |  |
| `headline` | text | yes |  |
| `bio` | text | yes |  |
| `short_bio` | text | yes |  |
| `photo_url` | text | yes |  |
| `cover_photo_url` | text | yes |  |
| `canonical_url` | text | yes |  |
| `job_title` | text | yes |  |
| `phone` | text | yes |  |
| `email` | text | yes |  |
| `website_url` | text | yes |  |
| `primary_license_verified_at` | timestamp with time zone | yes |  |
| `gbp_place_id` | text | yes |  |
| `gbp_connected` | boolean | yes |  |
| `gbp_last_sync` | timestamp with time zone | yes |  |
| `languages` | text[] | yes |  |
| `markets_served` | text[] | yes |  |
| `zip_codes_served` | text[] | yes |  |
| `schema_type` | text | yes |  |
| `wikidata_id` | text | yes |  |
| `same_as` | text[] | yes |  |
| `search_rank_score` | smallint | yes |  |
| `score_updated_at` | timestamp with time zone | yes |  |
| `local_rank` | smallint | yes |  |
| `local_rank_of` | smallint | yes |  |
| `local_rank_updated` | timestamp with time zone | yes |  |
| `claimed_at` | timestamp with time zone | yes |  |
| `claim_method` | text | yes |  |
| `claim_confidence` | smallint | yes |  |
| `compliance_complete` | boolean | yes |  |
| `compliance_score` | smallint | yes |  |
| `territory_id` | uuid | yes |  |
| `detail_url` | text | yes |  |
| `nodalized_at` | timestamp with time zone | yes |  |

Constraints:
- primary key: `PRIMARY KEY (id)`
