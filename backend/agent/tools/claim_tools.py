"""Suggested field values for the user to accept or edit (nothing is written by the model)."""

from agent.tools import ToolContext, ToolDef, register_tool


# The only fields the assistant may draft itself (core1: AI specialities and description; the serving area comes
# from the person's own location). Facts such as the year started, awards, achievements, a title, a license or an
# address are never drafted: they come from the owner's confirmed pages or from the owner.
DRAFTABLE_FIELDS = ("bio", "specialities", "service_area")


def propose_field_updates(ctx: ToolContext, tool_input: dict) -> dict:
    proposed = tool_input.get("fields") or {}
    fields = {k: v for k, v in proposed.items() if k in DRAFTABLE_FIELDS and isinstance(v, str) and v.strip()}
    refused = sorted(k for k in proposed if k not in fields)
    if not fields:
        return {"error": f"You can only draft {', '.join(DRAFTABLE_FIELDS)}. Anything else must come from their confirmed pages or from them."}
    out = {"fields": fields, "source_url": tool_input.get("source_url")}
    if refused:
        out["not_drafted"] = refused  # facts are never invented: ask the owner for these instead
    return out


register_tool(
    ToolDef(
        name="propose_field_updates",
        description="Suggest field values you drafted yourself for the user to accept or edit, in ONE call (the app shows each "
        "with its own accept/edit choice; nothing is written). Use it for the AI-drafted description (bio) and specialities. "
        "Only draft from facts you actually have (their name, category, location, services, title, company, confirmed details); "
        "never invent. Leave source_url out: these are your own drafts, not text read off a page. Valid keys: bio, specialities, "
        "service_area ONLY. Never draft a year started, awards, achievements, a title, a license or an address.",
        input_schema={
            "type": "object",
            "properties": {
                "fields": {"type": "object", "description": "Candidate field values, e.g. {\"service_area\": \"...\"}"},
                "source_url": {"type": "string"},
            },
            "required": ["fields"],
        },
        handler=propose_field_updates,
        is_ui_action=True,
    )
)
