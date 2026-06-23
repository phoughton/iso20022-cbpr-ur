import cbpr_rules as c
from tests.conftest import read_fixture


VALID = "tests/fixtures/pacs_008_2025_valid.xml"
INVALID = "tests/fixtures/pacs_008_2025_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2025, "pacs.008")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.008"
    assert result["violations"] == []
    assert result["rules_evaluated"] > 50


def test_message_type_auto_detected():
    result = c.validate_string(read_fixture("pacs_008_2025_valid.xml"), 2025)
    assert result["detected_message_type"] == "pacs.008"
    assert result["valid"] is True


def test_invalid_message_flags_newly_enforced_rules():
    result = c.validate_file(INVALID, 2025, "pacs.008")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # Promoted from advisory:
    # R6: MsgDefIdr (pacs.008.001.09) does not match Document namespace suffix
    assert "pacs.008:R6" in fired
    # R5: BizMsgIdr does not contain the GroupHeader MsgId
    assert "pacs.008:R5" in fired
    # R23: structured PostalAddress value duplicated in AddressLine
    assert "pacs.008:R23" in fired
    # R42: same-currency Instructed/Interbank amounts differ, no ChargesInformation
    assert "pacs.008:R42" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2025, "pacs.008")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r6 = by_rule["pacs.008:R6"]
    assert r6["line"] is not None
    assert r6["xpath"]
    assert r6["description"]


def test_promoted_rules_no_longer_advisory():
    result = c.validate_file(VALID, 2025, "pacs.008")
    adv = {a["rule_number"] for a in result["advisory"]}
    for promoted in ("pacs.008:R5", "pacs.008:R6", "pacs.008:R23",
                     "pacs.008:R42", "pacs.008:R44"):
        assert promoted not in adv
    # advisory still surfaces the rules we deliberately kept
    assert "pacs.008:R4" in adv
    assert "pacs.008:R43" in adv
    assert "pacs.008:R108" in adv
