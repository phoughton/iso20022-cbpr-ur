import cbpr_rules as c


def test_valid_message_has_no_violations():
    result = c.validate_file("tests/fixtures/pain_001_2025_valid.xml", 2025, "pain.001")
    assert result["valid"] is True
    assert result["message_type"] == "pain.001"
    assert result["violations"] == []
    assert result["rules_evaluated"] > 20


def test_invalid_message_flags_expected_rules():
    result = c.validate_file("tests/fixtures/pain_001_2025_invalid.xml", 2025, "pain.001")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pain.001:R5" in fired       # wrong Business Service value
    assert "pain.001:R16" in fired      # Structured + Unstructured remittance together
    assert "pain.001:R23" in fired      # Debtor address: Country missing, AddressLine absent
    assert "pain.001:R64" in fired      # HOLD present with CHQB
    assert "pain.001:VAL-CCY" in fired  # invalid ISO 4217 currency
    assert "pain.001:R3" in fired       # MsgDefIdr != Document message-definition id
    assert "pain.001:R13" in fired      # structured TownName duplicated in AddressLine


def test_violations_carry_xpath_and_line():
    result = c.validate_file("tests/fixtures/pain_001_2025_invalid.xml", 2025, "pain.001")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    val_ccy = by_rule["pain.001:VAL-CCY"]
    assert val_ccy["line"] is not None
    assert val_ccy["xpath"]
    assert "InstdAmt" in val_ccy["xpath"]
