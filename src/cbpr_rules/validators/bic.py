"""BIC validation (ISO 9362): 8 or 11 characters, structurally well-formed."""
from __future__ import annotations

import re

from ..reference.countries import ISO3166_ALPHA2

# 4 letters (institution) + 2 letters (country) + 2 alnum (location) + optional 3 alnum (branch)
_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def is_valid_bic(value: str) -> bool:
    """True if ``value`` is a structurally valid 8 or 11 character BIC."""
    if not value:
        return False
    bic = value.strip().upper()
    if not _BIC_RE.match(bic):
        return False
    if bic[4:6] not in ISO3166_ALPHA2:
        return False
    return True
