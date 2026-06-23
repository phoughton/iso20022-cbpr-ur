"""The universal VAL-IBAN rule: every <IBAN> must pass the mod-97 check.

Regression test for the bug where ``is_valid_iban`` existed but was wired into
no rule, so malformed IBANs passed silently for every message type.
"""
import cbpr_rules as c

# Contains a structurally-invalid IBAN (GB29NWBK60161331926818) alongside a
# valid one (DE29100100100987654321).
DODGY = "test_files/2025/cbprplus_pacs008_sample_dodgy_IBAN_and_bic_mismatch.xml"
CLEAN = "tests/fixtures/pacs008_valid.xml"


def test_invalid_iban_is_flagged():
    result = c.validate_file(DODGY, 2025, "pacs.008")
    assert result["valid"] is False
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    assert "pacs.008:VAL-IBAN" in by_rule
    finding = by_rule["pacs.008:VAL-IBAN"]
    assert "GB29NWBK60161331926818" in finding["found"]
    assert finding["line"] is not None
    assert "IBAN" in finding["xpath"]


def test_valid_message_has_no_iban_violation():
    result = c.validate_file(CLEAN, 2025, "pacs.008")
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.008:VAL-IBAN" not in fired


def test_iban_rule_is_universal_across_message_types():
    # Registered for every message type, not just pacs.008.
    for year, msgtype in [(2025, "camt.054"), (2026, "pacs.009"), (2025, "pain.001")]:
        numbers = {r["rule_number"] for r in c.list_rules(year, msgtype)}
        assert f"{msgtype}:VAL-IBAN" in numbers
