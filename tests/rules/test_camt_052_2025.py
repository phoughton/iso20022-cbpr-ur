import cbpr_rules as c


def test_valid_message_has_no_violations():
    result = c.validate_file("tests/fixtures/camt_052_2025_valid.xml", 2025, "camt.052")
    assert result["valid"] is True
    assert result["message_type"] == "camt.052"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file("tests/fixtures/camt_052_2025_invalid.xml", 2025, "camt.052")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "camt.052:R1" in fired      # BAH vs Report CopyDuplicate mismatch
    assert "camt.052:R6" in fired      # wrong Business Service value
    assert "camt.052:R12" in fired     # PostalAddress present without Name
    assert "camt.052:R17" in fired     # InstructionIdentification slash pattern
    assert "camt.052:VAL-CCY" in fired  # invalid ISO 4217 currency
    # Newly-enforced (promoted) rules:
    assert "camt.052:R3" in fired      # BizMsgIdr does not carry GrpHdr/MsgId
    assert "camt.052:R4" in fired      # MsgDefIdr mismatches Document namespace id
    assert "camt.052:R16" in fired     # Interest total != sum of record amounts


def test_violations_carry_xpath_and_line():
    result = c.validate_file("tests/fixtures/camt_052_2025_invalid.xml", 2025, "camt.052")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r17 = by_rule["camt.052:R17"]
    assert r17["line"] is not None
    assert r17["xpath"]
    assert "InstrId" in r17["xpath"]
