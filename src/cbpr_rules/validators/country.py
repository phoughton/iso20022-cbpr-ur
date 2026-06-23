"""ISO 3166-1 alpha-2 country code validation."""
from __future__ import annotations

from ..reference.countries import ISO3166_ALPHA2


def is_valid_country(value: str) -> bool:
    """True if ``value`` is a recognised ISO 3166-1 alpha-2 country code."""
    if not value:
        return False
    return value.strip().upper() in ISO3166_ALPHA2
