import cbpr_rules as c

VALID = "tests/fixtures/pacs_008_stp_2026_valid.xml"
INVALID = "tests/fixtures/pacs_008_stp_2026_invalid.xml"
MT = "pacs.008_stp"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, MT)
    assert result["valid"] is True
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, MT)
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # BizMsgIdr != GroupHeader MsgId
    assert "pacs.008_stp:R1" in fired
    # Promoted: BizMsgIdr does not carry GroupHeader MsgId
    assert "pacs.008_stp:R7" in fired
    # Promoted: MsgDefIdr does not match Document message definition
    assert "pacs.008_stp:R8" in fired
    # Promoted: structured PostalAddress value duplicated in AddressLine
    assert "pacs.008_stp:R29" in fired
    # Promoted: Debtor AnyBIC present together with Name/PostalAddress
    assert "pacs.008_stp:R35" in fired
    # From BIC != Instructing Agent BIC
    assert "pacs.008_stp:R5" in fired
    # GPI ServiceLevel code G002 forbidden
    assert "pacs.008_stp:R10" in fired
    # InstructionIdentification starts with a slash
    assert "pacs.008_stp:R19" in fired
    # commodity currency XAU not allowed
    assert "pacs.008_stp:R21" in fired
    # Debtor PostalAddress present but Name absent
    assert "pacs.008_stp:R31" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, MT)
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r21 = by_rule["pacs.008_stp:R21"]
    assert r21["line"] is not None
    assert r21["xpath"]
    assert "IntrBkSttlmAmt" in r21["xpath"]
