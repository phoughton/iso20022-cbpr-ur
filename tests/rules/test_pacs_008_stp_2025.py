"""Tests for the CBPR+ SR2025 pacs.008 STP usage-rule module."""
import os

import cbpr_rules

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")
VALID = os.path.join(FIXTURES, "pacs_008_stp_2025_valid.xml")
INVALID = os.path.join(FIXTURES, "pacs_008_stp_2025_invalid.xml")


def test_valid_message_has_no_violations():
    result = cbpr_rules.validate_file(VALID, 2025, "pacs.008_stp")
    assert result["valid"] is True
    assert result["violations"] == []


def test_invalid_message_fires_targeted_rules():
    result = cbpr_rules.validate_file(INVALID, 2025, "pacs.008_stp")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    for expected in (
        "pacs.008_stp:R2",
        "pacs.008_stp:R8",
        "pacs.008_stp:R12",
        "pacs.008_stp:R20",
        "pacs.008_stp:R21",
        "pacs.008_stp:R40",
        # newly-enforced: Debtor AnyBIC present together with Name/PostalAddress
        "pacs.008_stp:R36",
    ):
        assert expected in fired, f"expected {expected} in {fired}"


def test_violations_carry_location():
    result = cbpr_rules.validate_file(INVALID, 2025, "pacs.008_stp")
    assert result["violations"]
    some = result["violations"][0]
    assert some["line"] is not None
    assert any(v["xpath"] for v in result["violations"])


def test_rule_catalog_complete():
    rules = cbpr_rules.list_rules(2025, "pacs.008_stp")
    numbers = {r["rule_number"].split(":", 1)[1] for r in rules}
    # Every R-index from the Rules sheet plus the VAL-* algorithmic checks.
    for n in [f"R{i}" for i in range(1, 52)]:
        assert n in numbers, f"missing {n}"
    assert {"VAL-CCY", "VAL-BIC", "VAL-CTRY"} <= numbers
