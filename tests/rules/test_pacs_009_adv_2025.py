import cbpr_rules as c

VALID = "tests/fixtures/pacs_009_adv_2025_valid.xml"
INVALID = "tests/fixtures/pacs_009_adv_2025_invalid.xml"
MT = "pacs.009_adv"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2025, MT)
    assert result["valid"] is True
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2025, MT)
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.009_adv:R8" in fired    # wrong Business Service value
    assert "pacs.009_adv:R3" in fired    # From BIC != Instructing Agent BIC (no CopyDuplicate)
    assert "pacs.009_adv:R26" in fired   # InstrId starts with a slash
    assert "pacs.009_adv:R31" in fired   # commodity currency XAU
    assert "pacs.009_adv:R68" in fired   # Cdtr Name present without Postal Address
    assert "pacs.009_adv:R6" in fired    # MsgDefIdr does not match Document namespace
    assert "pacs.009_adv:R20" in fired   # structured PstlAdr value duplicated in AddressLine


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2025, MT)
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r31 = by_rule["pacs.009_adv:R31"]
    assert r31["line"] is not None
    assert r31["xpath"]
    assert "IntrBkSttlmAmt" in r31["xpath"]
