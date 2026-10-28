-- Mock data for running the application (not real customers).
-- One location (Spice Garden, a restaurant), two domains, five visitors, five chats, two handovers.
-- Safe to run again: it removes the mock rows first.

BEGIN;

DELETE FROM handovers WHERE resource_id = 'loc_spice_garden_01';
DELETE FROM chat_sessions WHERE resource_id = 'loc_spice_garden_01';
DELETE FROM visitors WHERE resource_id = 'loc_spice_garden_01';
DELETE FROM conversion_subscription WHERE resource_id = 'loc_spice_garden_01';

-- The subscription: one location, active, two allowed domains (the two test sites).
INSERT INTO conversion_subscription (
    resource_type, resource_id, is_enabled, kill_switch, site_key, allowed_domains,
    plan, subscription_starts, subscription_ends, status)
VALUES (
    'tier_location', 'loc_spice_garden_01', true, 'none', 'wk_test_spice_garden_01',
    ARRAY['localhost:8001', 'localhost:8002'],
    'monthly', now() - interval '10 days', now() + interval '20 days', 'active');

-- Five visitors. Visitors 1 to 3 are on localhost:8001, visitors 4 and 5 on localhost:8002.
INSERT INTO visitors (
    visitor_id, domain, resource_id, resource_type, have_consent, name, email, phone,
    location_city, location_country, visit_count, widget_seconds_total, page_seconds_total,
    score_72h, score_events, status, handover_count, strike_count, consent_choice,
    consent_notice_version, consent_at, first_seen_at, last_seen_at, expires_at)
VALUES
  ('11111111-1111-4111-8111-111111111111', 'localhost:8001', 'loc_spice_garden_01', 'tier_location',
   true, NULL, NULL, NULL, 'Austin', 'US', 1, 95, 240,
   10, '[{"event": "opened_chat", "points": 10}]', 'visitor', 0, 0,
   'accepted', 'notice-v1', now() - interval '2 days',
   now() - interval '2 days', now() - interval '2 days', now() + interval '364 days'),
  ('22222222-2222-4222-8222-222222222222', 'localhost:8001', 'loc_spice_garden_01', 'tier_location',
   true, 'Asha Rao', 'asha@example.com', '+1 555 0100', 'Dallas', 'US', 2, 260, 420,
   40, '[{"event": "opened_chat", "points": 10}, {"event": "shared_contact", "points": 30}]',
   'lead', 1, 0, 'accepted', 'notice-v1', now() - interval '3 days',
   now() - interval '3 days', now() - interval '1 day', now() + interval '364 days'),
  ('33333333-3333-4333-8333-333333333333', 'localhost:8001', 'loc_spice_garden_01', 'tier_location',
   true, NULL, NULL, NULL, 'Toronto', 'CA', 3, 480, 600,
   65, '[{"event": "opened_chat", "points": 10}, {"event": "long_chat", "points": 15}, {"event": "booking_link_click", "points": 10}, {"event": "other_clickable", "points": 5}, {"event": "asked_for_person", "points": 15}]',
   'hot_visitor', 0, 0, 'accepted', 'notice-v1', now() - interval '5 days',
   now() - interval '5 days', now(), now() + interval '364 days'),
  ('44444444-4444-4444-8444-444444444444', 'localhost:8002', 'loc_spice_garden_01', 'tier_location',
   true, NULL, NULL, NULL, 'Austin', 'US', 1, 60, 90,
   15, '[{"event": "opened_chat", "points": 10}, {"event": "other_clickable", "points": 5}]',
   'visitor', 0, 0, 'accepted', 'notice-v1', now() - interval '1 day',
   now() - interval '1 day', now() - interval '1 day', now() + interval '364 days'),
  ('55555555-5555-4555-8555-555555555555', 'localhost:8002', 'loc_spice_garden_01', 'tier_location',
   true, 'Ben Carter', NULL, '+1 555 0111', 'Seattle', 'US', 2, 200, 300,
   55, '[{"event": "opened_chat", "points": 10}, {"event": "booking_link_click", "points": 10}, {"event": "shared_contact", "points": 30}, {"event": "other_clickable", "points": 5}]',
   'lead', 1, 0, 'accepted', 'notice-v1', now() - interval '4 days',
   now() - interval '4 days', now() - interval '6 hours', now() + interval '364 days');

-- Five chats, one per visitor. Each conversation is an array of turns, as in A49.
INSERT INTO chat_sessions (
    session_id, visitor_id, resource_type, resource_id, domain, have_consent, status,
    started_at, ended_at, last_activity_at, location_city, location_country,
    widget_seconds, page_seconds, conversation, session_score, summary, abuse_strikes,
    model, input_tokens, output_tokens, cost, metric_date, expires_at, updated_at)
VALUES
  ('a0000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111',
   'tier_location', 'loc_spice_garden_01', 'localhost:8001', true, 'completed',
   now() - interval '2 days', now() - interval '2 days' + interval '3 minutes',
   now() - interval '2 days' + interval '3 minutes', 'Austin', 'US', 95, 240,
   '[{"request": ["Do you have vegetarian options?"], "response": "Yes, we have several vegetarian dishes. Would you like to see the menu?", "event_time": "2026-10-17T10:00:00Z"}, {"request": ["Show me the menu"], "response": "Here is our full menu.", "event_time": "2026-10-17T10:01:00Z"}]',
   10, NULL, 0, 'sample-model', 900, 320, 0.004, (now() - interval '2 days')::date,
   now() - interval '2 days' + interval '3 minutes' + interval '20 days',
   now() - interval '2 days' + interval '3 minutes'),
  ('a0000000-0000-4000-8000-000000000002', '22222222-2222-4222-8222-222222222222',
   'tier_location', 'loc_spice_garden_01', 'localhost:8001', true, 'handed_over',
   now() - interval '1 day', now() - interval '1 day' + interval '6 minutes',
   now() - interval '1 day' + interval '6 minutes', 'Dallas', 'US', 260, 420,
   '[{"request": ["Can I book a table for four on Friday?"], "response": "We can pass this to the restaurant. Would you like to share your name and phone number?", "event_time": "2026-10-18T18:00:00Z"}, {"request": ["Asha Rao, asha@example.com, +1 555 0100"], "response": "Thank you. The restaurant will contact you soon.", "event_time": "2026-10-18T18:03:00Z"}]',
   40, 'Asks for a table for four on Friday. Asked to be contacted.', 0,
   'sample-model', 1200, 410, 0.006, (now() - interval '1 day')::date,
   now() - interval '1 day' + interval '6 minutes' + interval '20 days',
   now() - interval '1 day' + interval '6 minutes'),
  ('a0000000-0000-4000-8000-000000000003', '33333333-3333-4333-8333-333333333333',
   'tier_location', 'loc_spice_garden_01', 'localhost:8001', true, 'completed',
   now() - interval '5 days', now() - interval '5 days' + interval '8 minutes',
   now() - interval '5 days' + interval '8 minutes', 'Toronto', 'CA', 480, 600,
   '[{"request": ["What time do you open on Sunday?"], "response": "We open at noon on Sundays.", "event_time": "2026-10-14T12:00:00Z"}, {"request": ["Can I speak to a person?"], "response": "I can pass this to the restaurant.", "event_time": "2026-10-14T12:04:00Z"}]',
   65, NULL, 0, 'sample-model', 1100, 380, 0.005, (now() - interval '5 days')::date,
   now() - interval '5 days' + interval '8 minutes' + interval '20 days',
   now() - interval '5 days' + interval '8 minutes'),
  ('a0000000-0000-4000-8000-000000000004', '44444444-4444-4444-8444-444444444444',
   'tier_location', 'loc_spice_garden_01', 'localhost:8002', true, 'incomplete',
   now() - interval '1 day', now() - interval '1 day' + interval '2 minutes',
   now() - interval '1 day' + interval '2 minutes', 'Austin', 'US', 60, 90,
   '[{"request": ["Is there parking?"], "response": "Parking details are on our contact page.", "event_time": "2026-10-18T09:00:00Z"}]',
   15, NULL, 0, 'sample-model', 300, 90, 0.001, (now() - interval '1 day')::date,
   now() - interval '1 day' + interval '2 minutes' + interval '20 days',
   now() - interval '1 day' + interval '2 minutes'),
  ('a0000000-0000-4000-8000-000000000005', '55555555-5555-4555-8555-555555555555',
   'tier_location', 'loc_spice_garden_01', 'localhost:8002', true, 'handed_over',
   now() - interval '6 hours', now() - interval '6 hours' + interval '5 minutes',
   now() - interval '6 hours' + interval '5 minutes', 'Seattle', 'US', 200, 300,
   '[{"request": ["Do you do catering for 30 people?"], "response": "Catering is a separate service. Would you like to share your details so the team can contact you?", "event_time": "2026-10-19T04:00:00Z"}, {"request": ["Ben Carter, +1 555 0111"], "response": "Thank you, Ben. The team will contact you.", "event_time": "2026-10-19T04:04:00Z"}]',
   55, 'Asks about catering for 30 people. Asked to be contacted by phone.', 0,
   'sample-model', 1000, 360, 0.005, (now() - interval '6 hours')::date,
   now() - interval '6 hours' + interval '5 minutes' + interval '20 days',
   now() - interval '6 hours' + interval '5 minutes');

-- Two handovers, for the two leads. Each is written with a pending notification, then sent (A34, A52).
INSERT INTO handovers (
    handover_id, session_id, visitor_id, resource_type, resource_id, domain, name, email, phone,
    reason, ai_summary, conversation, status, notifications, expires_at, created_at, updated_at)
VALUES
  ('b0000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002',
   '22222222-2222-4222-8222-222222222222', 'tier_location', 'loc_spice_garden_01', 'localhost:8001',
   'Asha Rao', 'asha@example.com', '+1 555 0100',
   'Visitor asked to be contacted', 'Asks for a table for four on Friday. Asked to be contacted.',
   '[{"request": ["Can I book a table for four on Friday?"], "response": "We can pass this to the restaurant. Would you like to share your name and phone number?", "event_time": "2026-10-18T18:00:00Z"}, {"request": ["Asha Rao, asha@example.com, +1 555 0100"], "response": "Thank you. The restaurant will contact you soon.", "event_time": "2026-10-18T18:03:00Z"}]',
   'new', '{"business_email": {"status": "sent", "sent_at": "2026-10-18T18:04:00Z"}}',
   now() - interval '1 day' + interval '365 days', now() - interval '1 day', now() - interval '1 day'),
  ('b0000000-0000-4000-8000-000000000005', 'a0000000-0000-4000-8000-000000000005',
   '55555555-5555-4555-8555-555555555555', 'tier_location', 'loc_spice_garden_01', 'localhost:8002',
   'Ben Carter', NULL, '+1 555 0111',
   'Visitor asked for catering', 'Asks about catering for 30 people. Asked to be contacted by phone.',
   '[{"request": ["Do you do catering for 30 people?"], "response": "Catering is a separate service. Would you like to share your details so the team can contact you?", "event_time": "2026-10-19T04:00:00Z"}, {"request": ["Ben Carter, +1 555 0111"], "response": "Thank you, Ben. The team will contact you.", "event_time": "2026-10-19T04:04:00Z"}]',
   'new', '{"business_email": {"status": "pending"}}',
   now() - interval '6 hours' + interval '365 days', now() - interval '6 hours', now() - interval '6 hours');

COMMIT;
