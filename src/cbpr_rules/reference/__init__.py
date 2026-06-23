"""Vendored ISO reference data (country and currency code lists).

Shipped as package data so validation never requires a network call. Sourced
from ISO 3166-1 alpha-2 and ISO 4217.
"""
from .countries import ISO3166_ALPHA2
from .currencies import ISO4217

__all__ = ["ISO3166_ALPHA2", "ISO4217"]
