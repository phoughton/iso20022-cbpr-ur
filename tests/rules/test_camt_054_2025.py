import cbpr_rules as c


def test_valid_message_has_no_violations():
    result = c.validate_file("tests/fixtures/camt_054_2025_valid.xml", 2025, "camt.054")
    assert result["valid"] is True
    assert result["message_type"] == "camt.054"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file("tests/fixtures/camt_054_2025_invalid.xml", 2025, "camt.054")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "camt.054:R1" in fired       # BAH CopyDuplicate != document indicator
    assert "camt.054:R3" in fired       # BizMsgIdr does not carry GrpHdr/MsgId
    assert "camt.054:R4" in fired       # MsgDefIdr != Document message definition id
    assert "camt.054:R6" in fired       # wrong Business Service value
    assert "camt.054:R20" in fired      # InstructionId starts with slash
    assert "camt.054:VAL-CCY" in fired  # invalid currency XYZ
    assert "camt.054:VAL-BIC" in fired  # malformed account servicer BIC


def test_violations_carry_xpath_and_line():
    result = c.validate_file("tests/fixtures/camt_054_2025_invalid.xml", 2025, "camt.054")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    val_ccy = by_rule["camt.054:VAL-CCY"]
    assert val_ccy["line"] is not None
    assert val_ccy["xpath"]
    assert "Amt" in val_ccy["xpath"]
