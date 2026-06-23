import cbpr_rules as c


VALID = "tests/fixtures/pacs_004_2026_valid.xml"
INVALID = "tests/fixtures/pacs_004_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "pacs.004")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.004"
    assert result["violations"] == []
    assert result["rules_evaluated"] > 40


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "pacs.004")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # From-BIC vs Instructing Agent mismatch
    assert "pacs.004:R4" in fired
    # OriginalInterbankSettlementAmount + OrgnlTxRef/InterbankSettlementAmount both present
    assert "pacs.004:R10" in fired
    # OriginalMessageNameIdentification not an allowed value
    assert "pacs.004:R13" in fired
    # commodity currency XAU on OriginalInterbankSettlementAmount
    assert "pacs.004:R20" in fired
    # Debtor party PostalAddress present but Name absent
    assert "pacs.004:R36" in fired
    # Originator AnyBIC absent and Name absent
    assert "pacs.004:R63" in fired
    # Newly enforced: Debtor AnyBIC present together with PostalAddress
    assert "pacs.004:R40" in fired
    # Newly enforced: detectable partial return missing AdditionalInformation = "PART"
    assert "pacs.004:R61" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "pacs.004")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r20 = by_rule["pacs.004:R20"]
    assert r20["line"] is not None
    assert r20["xpath"]
    assert "OrgnlIntrBkSttlmAmt" in r20["xpath"]


def test_advisory_rules_surfaced():
    result = c.validate_file(VALID, 2026, "pacs.004")
    adv = {a["rule_number"] for a in result["advisory"]}
    assert "pacs.004:R5" in adv
