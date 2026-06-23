import cbpr_rules as c

VALID = "tests/fixtures/pacs_008_2026_valid.xml"
INVALID = "tests/fixtures/pacs_008_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "pacs.008")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.008"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "pacs.008")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # From/Instructing and To/Instructed BIC mismatches
    assert "pacs.008:R5" in fired
    assert "pacs.008:R3" in fired
    # InstrId slash pattern, commodity currency, MsgDefIdr code, code exclusion
    assert "pacs.008:R28" in fired
    assert "pacs.008:R31" in fired
    assert "pacs.008:R8" in fired
    assert "pacs.008:R11" in fired
    # Debtor postal address without name + AnyBIC absent without name
    assert "pacs.008:R48" in fired
    assert "pacs.008:R50" in fired
    # Newly-enforced promotions: BizMsgIdr no longer carries GrpHdr MsgId (R7);
    # Creditor has AnyBIC together with Name (R54).
    assert "pacs.008:R7" in fired
    assert "pacs.008:R54" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "pacs.008")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r31 = by_rule["pacs.008:R31"]
    assert r31["line"] is not None
    assert r31["xpath"]
    assert "IntrBkSttlmAmt" in r31["xpath"]
