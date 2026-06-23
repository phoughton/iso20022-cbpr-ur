import cbpr_rules as c


VALID = "tests/fixtures/pacs_004_2025_valid.xml"
INVALID = "tests/fixtures/pacs_004_2025_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2025, "pacs.004")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.004"
    assert result["violations"] == []
    assert result["rules_evaluated"] > 40


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2025, "pacs.004")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # From/To BIC vs Instructing/Instructed Agent mismatch (From BIC differs)
    assert "pacs.004:R1" in fired
    # OriginalInterbankSettlementAmount + OrgnlTxRef/InterbankSettlementAmount both present
    assert "pacs.004:R12" in fired
    # OriginalMessageNameIdentification not an allowed value
    assert "pacs.004:R16" in fired
    # commodity currency XAU on OriginalInterbankSettlementAmount
    assert "pacs.004:R23" in fired
    # RtrChain Debtor party PostalAddress present but Name absent
    assert "pacs.004:R45" in fired
    # ReturnReason Originator AnyBIC absent and Name absent
    assert "pacs.004:R104" in fired
    # newly-enforced: RtrChain Creditor party has AnyBIC together with Name
    assert "pacs.004:R92" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2025, "pacs.004")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r23 = by_rule["pacs.004:R23"]
    assert r23["line"] is not None
    assert r23["xpath"]
    assert "OrgnlIntrBkSttlmAmt" in r23["xpath"]


def test_advisory_rules_surfaced():
    result = c.validate_file(VALID, 2025, "pacs.004")
    adv = {a["rule_number"] for a in result["advisory"]}
    assert "pacs.004:R3" in adv
