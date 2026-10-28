"""How each action is completed for one business. The code picks the way; the agent only follows it.

An action's steps (conv_action.steps, in the category bundle as "actions") are tried in order, and the first one that is
possible for this business is used:
  booking   possible when the business has booking switched on
  details   possible when the business has at least one of the fields the step provides (a link, a fact) on record
  handover  always possible
"""

from shared.action_steps import collect_words, provided_keys
from tools.business_tools import field_value


def step_possible(step: dict, customer: dict) -> bool:
    route = step.get("route")
    if route == "booking":
        return bool(customer.get("booking_enabled"))
    if route == "details":
        return any(field_value(customer, key) is not None for key in provided_keys(step))
    return route == "handover"


def resolved_actions(category: dict, customer: dict) -> list[dict]:
    """Each enabled action of the category with the way it is completed for this business: the first possible step.
    {key, name, button, goal, route, tools, collect (words), provides (the fields on record)}."""
    resolved = []
    for action in category.get("actions") or []:
        step = next((s for s in action["steps"] if step_possible(s, customer)), None)
        if step is None:
            continue
        resolved.append({
            "key": action["key"], "name": action["name"], "button": action.get("button"), "goal": action["goal"],
            "route": step["route"], "tools": step["tools"], "collect": collect_words(step),
            "provides": [k for k in provided_keys(step) if field_value(customer, k) is not None],
        })
    return resolved
