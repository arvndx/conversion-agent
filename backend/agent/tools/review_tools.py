from agent.tools import ToolContext, ToolDef, register_tool


def get_unreplied_reviews(ctx: ToolContext, tool_input: dict) -> dict:
    unreplied = [
        {"review_id": r["id"], "reviewer_name": r["reviewer_name"], "rating": r["rating"], "body": r["body"]}
        for r in ctx.profile.reviews
        if not r.get("reply")
    ]
    return {"unreplied_reviews": unreplied}


def propose_review_reply(ctx: ToolContext, tool_input: dict) -> dict:
    review_id = tool_input.get("review_id")
    draft_text = tool_input.get("draft_text", "")
    if not any(r["id"] == review_id for r in ctx.profile.reviews):
        return {"error": f"no review with id '{review_id}' on this profile"}
    return {"review_id": review_id, "draft_text": draft_text}


register_tool(
    ToolDef(
        name="get_unreplied_reviews",
        description="Get this profile's reviews that don't have a reply yet, with their review_id, reviewer, "
        "rating, and text. Use this to proactively notice and offer to help with unreplied reviews.",
        input_schema={"type": "object", "properties": {}},
        handler=get_unreplied_reviews,
    )
)

register_tool(
    ToolDef(
        name="propose_review_reply",
        description="Surface a drafted reply to a specific review for the user to review, edit, and send "
        "themselves. Never posts the reply — only the user's own Send action does that. If you already "
        "proposed a draft for this review_id earlier in the conversation, write different wording this time.",
        input_schema={
            "type": "object",
            "properties": {
                "review_id": {"type": "string", "description": "The review's id, from get_unreplied_reviews"},
                "draft_text": {"type": "string", "description": "Your drafted reply text"},
            },
            "required": ["review_id", "draft_text"],
        },
        handler=propose_review_reply,
        is_ui_action=True,
    )
)
