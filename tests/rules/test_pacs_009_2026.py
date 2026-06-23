import cbpr_rules as c

VALID = "tests/fixtures/pacs_009_2026_valid.xml"
INVALID = "tests/fixtures/pacs_009_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "pacs.009")
    assert result["valid"] is True
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "pacs.009")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.009:R5" in fired      # From BIC != Instructing Agent BIC
    assert "pacs.009:R10" in fired     # ServiceLevel code not G004
    assert "pacs.009:R11" in fired     # duplicate InstrForCdtrAgt code
    assert "pacs.009:R12" in fired     # InstrId starts with slash
    assert "pacs.009:R16" in fired     # commodity currency XAU
    assert "pacs.009:R28" in fired     # Dbtr FI Name without PostalAddress
    assert "pacs.009:R7" in fired      # BizMsgIdr does not carry GrpHdr MsgId
    assert "pacs.009:R22" in fired     # structured PstlAdr value duplicated in AdrLine


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "pacs.009")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r16 = by_rule["pacs.009:R16"]
    assert r16["line"] is not None
    assert r16["xpath"]
    assert "IntrBkSttlmAmt" in r16["xpath"]
