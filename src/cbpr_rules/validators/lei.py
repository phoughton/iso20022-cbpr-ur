"""LEI validation (ISO 17442): 20 alphanumeric chars with an ISO 7064 mod-97-10 check."""
from __future__ import annotations

import re

_LEI_RE = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def is_valid_lei(value: str) -> bool:
    """True if ``value`` is a 20-char LEI with a valid mod-97-10 check digit pair."""
    if not value:
        return False
    lei = value.strip().upper()
    if not _LEI_RE.match(lei):
        return False
    digits = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in lei)
    return int(digits) % 97 == 1
