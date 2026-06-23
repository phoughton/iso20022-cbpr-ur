"""ISO 4217 currency code validation."""
from __future__ import annotations

from ..reference.currencies import ISO4217


def is_valid_currency(value: str) -> bool:
    """True if ``value`` is a recognised ISO 4217 currency code."""
    if not value:
        return False
    return value.strip().upper() in ISO4217
