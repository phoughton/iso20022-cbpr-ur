"""cbpr_rules - validate ISO 20022 CBPR+ XML messages against SWIFT usage rules.

This package is AI generated. See the README for details and caveats.
"""
from __future__ import annotations

__version__ = "0.1.2"

from .models import Rule, Severity, Violation
from .engine import validate_file, validate_string, list_rules, available

__all__ = [
    "__version__",
    "Rule",
    "Severity",
    "Violation",
    "validate_file",
    "validate_string",
    "list_rules",
    "available",
]
