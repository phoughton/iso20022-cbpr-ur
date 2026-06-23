import cbpr_rules as c

VALID = "tests/fixtures/pacs_002_2025_valid.xml"
INVALID = "tests/fixtures/pacs_002_2025_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2025, "pacs.002")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.002"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2025, "pacs.002")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.002:R2" in fired      # From/To BIC mismatch (CopyDuplicate absent)
    assert "pacs.002:R7" in fired      # Business Service must be swift.cbprplus.03
    assert "pacs.002:R12" in fired     # RJCT requires StatusReasonInformation/Reason
    assert "pacs.002:R15" in fired     # OriginalInstructionIdentification slash pattern
    assert "pacs.002:R20" in fired     # PostalAddress present but Name absent
    assert "pacs.002:VAL-BIC" in fired  # invalid instructing agent BIC
    assert "pacs.002:R5" in fired      # MsgDefIdr does not match Document namespace


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2025, "pacs.002")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r15 = by_rule["pacs.002:R15"]
    assert r15["line"] is not None
    assert r15["xpath"]
    assert "OrgnlInstrId" in r15["xpath"]
