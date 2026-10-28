"""Site keys: the public key a business's web page uses to load the widget. One key per site.

Format: wk_live_ or wk_test_, then 24 lowercase letters or digits (checked by the table in db/agent_schema.sql).
A key identifies the site, not a secret: it is visible in the page. Security comes from the allowed domains.
"""

import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def new_site_key(test: bool = False) -> str:
    """A new random site key. Test keys are for the demo and the test sites."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(24))
    return f"wk_{'test' if test else 'live'}_{body}"
