"""Build the category bundle the chat engine reads, from one category's platform data (exp_category_knowledge and
exp_category_compliance, copied to shared/categories/<slug>.json).

Each conversion action becomes one topic:
  - a capture action (asks, contacts, quotes, registers) hands over to the business and collects the visitor's details;
  - every other action (view, order, buy, subscribe, schedule, reserve, ...) gives the business's link for it, or hands
    over when the business has no link for it.
The generic wording (teaser, messages, abuse and scoring rules) is shared by all categories and comes from the
restaurant sample. The critical topics (questions a bot must not answer itself) are set per category below.
"""

import json
from pathlib import Path

from shared.bundles import SAMPLES_DIR

CATEGORY_DIR = Path(__file__).resolve().parent / "categories"
GENERIC = json.loads((SAMPLES_DIR / "restaurant_category.json").read_text(encoding="utf-8"))

# The schema.org action types that collect the visitor's details (a lead), rather than sending the visitor to a link.
CAPTURE_ACTIONS = {
    "CommunicateAction", "ContactAction", "AskAction", "RequestAction", "RequestQuoteAction", "RequestQuote",
    "QuoteAction", "RegisterAction", "MessageAction", "CallAction", "SendAction", "CheckAction",
}

# Questions the chatbot must never answer itself (rates, quotes, returns). Each gets a fixed, approved reply.
CRITICAL_TOPICS = {
    "mortgage_broker": [
        ("rate_quote", "a mortgage rate, APR, payment or quote for a loan",
         "Rates and payments depend on your details and change often, so I can't quote one here. Shall I pass your question to the team?"),
        ("approval_question", "whether the visitor will be approved, or a guarantee of a loan or rate",
         "I can't say whether you'll be approved. A broker can review your details with you. Shall I pass this on?"),
    ],
    "mortgage_lender": [
        ("rate_quote", "a mortgage rate, APR, payment or quote for a loan",
         "Rates and payments depend on your details and change often, so I can't quote one here. Shall I pass your question to the team?"),
        ("approval_question", "whether the visitor will be approved, or a guarantee of a loan or rate",
         "I can't say whether you'll be approved. A loan officer can review your details with you. Shall I pass this on?"),
    ],
    "health_insurance_agency": [
        ("plan_quote", "a premium or price for a health plan, or whether the visitor is eligible for a plan or subsidy",
         "Plan prices and eligibility depend on your details, so I can't give them here. Shall I pass your question to an agent?"),
    ],
    "commercial_real_estate_agency": [
        ("valuation_question", "the value of a property, a return on investment, or a guaranteed outcome",
         "I can't value a property or promise a return here. An agent can look at the details with you. Shall I pass this on?"),
    ],
}

# What a visitor might type for each critical question (the topic description is not a visitor message).
CRITICAL_EXAMPLES = {
    "mortgage_broker": {
        "rate_quote": ["what rate would I get on a 30 year loan?", "what's the APR for a refinance?"],
        "approval_question": ["will I be approved with a 600 credit score?", "can you guarantee my loan approval?"],
    },
    "mortgage_lender": {
        "rate_quote": ["what rate would I get on a 30 year loan?", "what's the APR for a refinance?"],
        "approval_question": ["will I be approved with a 600 credit score?", "can you guarantee my loan approval?"],
    },
    "health_insurance_agency": {
        "plan_quote": ["how much is the premium for a family health plan?", "am I eligible for a marketplace subsidy?"],
    },
    "commercial_real_estate_agency": {
        "valuation_question": ["what is this building worth?", "guarantee me a 10% return on this property"],
    },
}


def _neutral_messages() -> dict:
    """The generic wording with no restaurant words left in it, so it reads correctly for any category."""
    texts = {}
    for key, text in GENERIC["message_texts"].items():
        texts[key] = text.replace("the restaurant", "{customer_name}").replace("the restaurant's", "{customer_name}'s").replace("restaurant", "{customer_name}")
    texts["critical_handover_follow"] = "Would you like to share your name and an email or phone number so {customer_name} can contact you?"
    return texts


def action_route(schema_action: str) -> str:
    return "capture" if schema_action in CAPTURE_ACTIONS else "link"


def _label(action: dict) -> str:
    return action.get("label") or action["key"].replace("_", " ").capitalize()


def build_category_bundle(slug: str) -> dict:
    raw = json.loads((CATEGORY_DIR / f"{slug}.json").read_text(encoding="utf-8"))
    topics = []
    default_questions = []
    for action in raw["conversion_actions"]:
        key, label = action["key"], _label(action)
        examples = [label] + ([action["profile_button"]] if action.get("profile_button") else [])
        description = action.get("agent_goal") or label   # 1,400 actions have no goal yet: the label is used
        if action_route(action.get("schema_action", "")) != "capture":
            description += (". Use only when the visitor asks for this specific action. Questions about parking, "
                            "directions, hours or other details are not this topic")
        if action_route(action.get("schema_action", "")) == "capture":
            topics.append({"id": key, "description": description, "action": "handover", "examples": examples})
        else:
            topics.append({"id": key, "description": description, "action": "tool", "tool": "get_conversion_link",
                           "field": key, "examples": examples})
        if len(default_questions) < 5:
            default_questions.append(action.get("profile_button") or label)

    services = [s.get("name") if isinstance(s, dict) else str(s) for s in (raw.get("services") or [])]
    services = [s for s in services if s]
    if services:
        topics.append({"id": "services", "description": "the services the business offers", "action": "tool",
                       "tool": "get_services", "examples": services[:3]})
    topics += [
        {"id": "contact", "description": "the phone number, email or address of the business", "action": "tool",
         "tool": "get_business_info", "field": "phone", "examples": ["what's your phone number", "where are you based"]},
        {"id": "hours", "description": "when the business is open", "action": "tool",
         "tool": "get_business_info", "field": "opening_hours", "examples": ["what time do you open", "are you open on Sunday"]},
    ]

    critical = [{"id": tid, "description": desc, "reply": reply, "action": "handover",
                 "examples": CRITICAL_EXAMPLES.get(slug, {}).get(tid, [desc])}
                for tid, desc, reply in CRITICAL_TOPICS.get(slug, [])]
    comp = raw.get("_compliance") or {}
    return {
        "bundle_type": "category",
        "category_id": slug,
        "gcid": raw["gcid"],
        "note": "Built from exp_category_knowledge and exp_category_compliance (copied locally, read-only source).",
        "default_questions": default_questions or ["Contact us"],
        "topics": topics,
        "critical_topics": critical,
        "general_knowledge_allowed": False,
        "handover_triggers": GENERIC["handover_triggers"],
        "handover_extra_fields": [],
        "never_ask": GENERIC["never_ask"] + ["social security number", "bank account number", "income", "credit score"],
        "guardrails_text": GENERIC["guardrails_text"],
        "teaser_text": GENERIC["teaser_text"],
        "message_texts": _neutral_messages(),
        "abuse_check": GENERIC["abuse_check"],
        "abuse_rules": GENERIC["abuse_rules"],
        "scoring_rules": GENERIC["scoring_rules"],
        "idle_close_minutes": GENERIC["idle_close_minutes"],
        "defaults": GENERIC["defaults"],
        "tools": [
            {"name": "get_business_info", "args": ["field"]},
            {"name": "get_conversion_link", "args": ["action_key"]},
            {"name": "get_services", "args": []},
            {"name": "request_handoff", "args": ["name", "email", "phone", "conversation", "question"]},
        ],
        "compliance": {
            "prohibited_phrases": comp.get("prohibited_phrases") or [],
            "required_disclaimers": comp.get("required_disclaimers") or [],
            "content_restrictions": comp.get("content_restrictions") or [],
        },
        "compliance_rules": raw.get("compliance_rules") or [],
        "services": services,
    }
