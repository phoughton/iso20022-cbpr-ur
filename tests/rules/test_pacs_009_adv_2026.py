import cbpr_rules as c

VALID = "tests/fixtures/pacs_009_adv_2026_valid.xml"
INVALID = "tests/fixtures/pacs_009_adv_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "pacs.009_adv")
    assert result["valid"] is True
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "pacs.009_adv")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.009_adv:R5" in fired      # From BIC != Instructing Agent BIC
    assert "pacs.009_adv:R10" in fired     # ServiceLevel code not G004
    assert "pacs.009_adv:R18" in fired     # duplicate InstrForCdtrAgt code
    assert "pacs.009_adv:R19" in fired     # InstrId starts with slash
    assert "pacs.009_adv:R21" in fired     # commodity currency XAU
    assert "pacs.009_adv:R28" in fired     # Dbtr FI Name without PostalAddress
    assert "pacs.009_adv:R7" in fired      # BizMsgIdr does not carry GrpHdr/MsgId
    assert "pacs.009_adv:R8" in fired      # MsgDefIdr does not match namespace def id


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "pacs.009_adv")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r21 = by_rule["pacs.009_adv:R21"]
    assert r21["line"] is not None
    assert r21["xpath"]
    assert "IntrBkSttlmAmt" in r21["xpath"]
