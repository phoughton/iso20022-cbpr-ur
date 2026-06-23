import cbpr_rules as c

VALID = "tests/fixtures/pain_001_2026_valid.xml"
INVALID = "tests/fixtures/pain_001_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "pain.001")
    assert result["valid"] is True
    assert result["message_type"] == "pain.001"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "pain.001")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # BizMsgIdr != GroupHeader MsgId (R1 formal); BizMsgIdr does not carry MsgId (R3 promoted)
    assert "pain.001:R1" in fired
    assert "pain.001:R3" in fired
    # Structured TownName duplicated in AddressLine (R11 promoted)
    assert "pain.001:R11" in fired
    # PaymentInformationIdentification != MsgId
    assert "pain.001:R8" in fired
    # HOLD not allowed when CHQB present
    assert "pain.001:R6" in fired
    # Debtor PostalAddress present without Name
    assert "pain.001:R13" in fired
    # DebtorAgent Name present without PostalAddress
    assert "pain.001:R15" in fired
    # Structurally invalid BIC
    assert "pain.001:VAL-BIC" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "pain.001")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r1 = by_rule["pain.001:R1"]
    assert r1["line"] is not None
    assert r1["xpath"]
