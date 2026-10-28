"""The reason a lead was passed on, stored as one of the fixed values in conv_lead.reason."""

REASONS = ("request_from_visitor", "time_in_widget", "unavailable_answer", "confused_question", "unsure_question")


def lead_reason(text: str | None) -> str:
    """Map the reason the chat recorded to one of the fixed values. Anything unclear is a request from the visitor."""
    lowered = (text or "").lower()
    if "unsure" in lowered:
        return "unsure_question"
    if "confus" in lowered:
        return "confused_question"
    if "unavailable" in lowered or "not know" in lowered or "could not answer" in lowered or "couldn't answer" in lowered:
        return "unavailable_answer"
    if "time" in lowered or "longer" in lowered:
        return "time_in_widget"
    return "request_from_visitor"
