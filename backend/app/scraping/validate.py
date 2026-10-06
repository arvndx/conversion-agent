"""Is this page about this person?

The old job counted a page as a match if *either* the first or the last name appeared anywhere in it,
which a directory page full of other people passes easily. Here the page must contain the full name
(first and last, close together, either order); a matching phone number or email adds confidence but
does not replace the name, because core1.txt says the agent's name must be validated first. A page
that fails goes back to the agent with "is this your profile?" instead of being used.
"""

import re
from dataclasses import dataclass, field

_PREFIXES = {"dr", "mr", "mrs", "ms", "prof"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "cma", "dds", "dmd", "md", "esq", "cpa", "team", "group", "nmls", "rmlo", "phd"}


@dataclass
class Validation:
    validated: bool
    name_match: bool = False
    phone_match: bool = False
    email_match: bool = False
    confidence: int = 0
    evidence: list[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "validated": self.validated, "confidence": self.confidence,
            "evidence": self.evidence, "reason": self.reason,
        }


def name_parts(full_name: str) -> tuple[str, str] | None:
    """(first, last) lowercase, ignoring honorifics, credentials and suffixes ("Dr. Chuck Tegano, CMA",
    "Jeff Tricoli Team"). A single-word name returns (word, "")."""
    base = (full_name or "").split(",")[0]
    tokens = [t for t in re.findall(r"[a-zA-Z'’\-]+", base.lower()) if t.strip("'’-")]
    tokens = [t for t in tokens if t not in _PREFIXES and t not in _SUFFIXES]
    if not tokens:
        return None
    return (tokens[0], tokens[-1] if len(tokens) > 1 else "")


def _name_in_text(first: str, last: str, text: str) -> bool:
    text = text.lower()
    if not last:
        return bool(re.search(rf"\b{re.escape(first)}\b", text))
    f, l = re.escape(first), re.escape(last)
    # "first last" (allowing a middle name or initial) or "last, first"
    return bool(re.search(rf"\b{f}\b(?:\W+\w+\.?){{0,2}}?\W+{l}\b", text) or re.search(rf"\b{l}\b,?\s+{f}\b", text))


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")[-10:]


def validate_identity(
    *,
    profile_name: str,
    page_text: str,
    json_ld_names: list[str] | None = None,
    profile_phone: str | None = None,
    profile_email: str | None = None,
    page_phones: list[str] | None = None,
    page_emails: list[str] | None = None,
) -> Validation:
    parts = name_parts(profile_name)
    if parts is None:
        return Validation(False, reason="no usable name to check")
    first, last = parts

    haystacks = [page_text or ""] + list(json_ld_names or [])
    name_match = any(_name_in_text(first, last, h) for h in haystacks)

    phone = _digits(profile_phone)
    phone_match = bool(phone) and phone in {_digits(p) for p in (page_phones or [])}
    email = (profile_email or "").lower()
    email_match = bool(email) and email in {e.lower() for e in (page_emails or [])}

    evidence = [label for label, hit in (("name", name_match), ("phone", phone_match), ("email", email_match)) if hit]
    confidence = (60 if name_match else 0) + (25 if phone_match else 0) + (15 if email_match else 0)
    if name_match:
        return Validation(True, name_match, phone_match, email_match, confidence, evidence, "full name found on the page")
    reason = "name not found on the page" + (" (but the phone or email matches)" if phone_match or email_match else "")
    return Validation(False, name_match, phone_match, email_match, confidence, evidence, reason)
