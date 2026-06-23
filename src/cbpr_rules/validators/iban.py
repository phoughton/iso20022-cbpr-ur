"""IBAN validation (ISO 13616) via the mod-97 check (ISO 7064)."""
from __future__ import annotations

import re

from ..reference.countries import ISO3166_ALPHA2

_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$")


def is_valid_iban(value: str) -> bool:
    """True if ``value`` is a structurally valid IBAN with a correct check."""
    if not value:
        return False
    iban = value.replace(" ", "").replace("\t", "").upper()
    # Length per ISO 13616: 4 (country+check) .. 34 max.
    if not (5 <= len(iban) <= 34):
        return False
    if not _IBAN_RE.match(iban):
        return False
    if iban[:2] not in ISO3166_ALPHA2:
        return False
    # Move the first four characters to the end, then convert letters to digits.
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    return int(digits) % 97 == 1
