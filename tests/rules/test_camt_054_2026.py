import cbpr_rules as c

VALID = "tests/fixtures/camt_054_2026_valid.xml"
INVALID = "tests/fixtures/camt_054_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "camt.054")
    assert result["valid"] is True
    assert result["message_type"] == "camt.054"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "camt.054")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "camt.054:R2" in fired       # BizMsgIdr != GrpHdr/MsgId
    assert "camt.054:R4" in fired       # BizMsgIdr does not carry GrpHdr/MsgId (promoted)
    assert "camt.054:R5" in fired       # MsgDefIdr != Document definition id (promoted)
    assert "camt.054:R8" in fired       # PageNumber == 0
    assert "camt.054:R10" in fired      # Status BOOK with no BookingDate/ValueDate
    assert "camt.054:R13" in fired      # InstrId starts with a slash
    assert "camt.054:VAL-CCY" in fired  # invalid ISO 4217 currency


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "camt.054")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    ccy = by_rule["camt.054:VAL-CCY"]
    assert ccy["line"] is not None
    assert ccy["xpath"]
    assert "Amt" in ccy["xpath"]
