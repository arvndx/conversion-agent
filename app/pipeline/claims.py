"""Replies that say an action was done when it was not: "I've sent your request", "your table is booked".

The model can write such a sentence on its own. It may say a request was passed on only when the request is saved in
conv_handover, and it may never say something is booked or confirmed: the visitor sends a request form, and the business
contacts them (pipeline/verify.py checks every reply with these patterns).
"""

import re

SENT = re.compile(
    r"\b(?:i|we)(?:'ve|\s+have)\s+(?:just\s+|now\s+|already\s+)?(?:sent|passed|forwarded|submitted|notified|emailed|informed)\b"
    r"|\b(?:has|have)\s+been\s+(?:sent|passed|forwarded|submitted|received)\b",
    re.IGNORECASE)
BOOKED = re.compile(
    r"\b(?:i|we)(?:'ve|\s+have)\s+(?:just\s+|now\s+|already\s+)?(?:booked|reserved|scheduled|confirmed)\b"
    r"|\b(?:is|are|been)\s+(?:now\s+|all\s+)?(?:booked|reserved|scheduled)\b"
    r"|\bbooking\s+(?:is|has\s+been)\s+confirmed\b"
    r"|\bbooking\s+(?:id|reference|number)\s*(?:is|:)",
    re.IGNORECASE)
