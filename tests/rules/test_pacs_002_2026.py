import cbpr_rules as c


def test_valid_message_has_no_violations():
    result = c.validate_file("tests/fixtures/pacs_002_2026_valid.xml", 2026, "pacs.002")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.002"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file("tests/fixtures/pacs_002_2026_invalid.xml", 2026, "pacs.002")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.002:R3" in fired   # BizMsgIdr != GrpHdr/MsgId
    assert "pacs.002:R4" in fired   # From BIC != Instructing Agent BIC
    assert "pacs.002:R9" in fired   # RJCT without StatusReason/Reason
    assert "pacs.002:R12" in fired  # bad OriginalMessageNameIdentification
    assert "pacs.002:R14" in fired  # OrgnlInstrId starts with slash
    assert "pacs.002:R20" in fired  # Originator without AnyBIC and without Name
    # Newly-enforced (promoted from advisory):
    assert "pacs.002:R6" in fired   # BizMsgIdr does not carry GrpHdr/MsgId
    assert "pacs.002:R7" in fired   # MsgDefIdr != Document definition id
    assert "pacs.002:R21" in fired  # structured TwnNm duplicated in AddressLine


def test_violations_carry_xpath_and_line():
    result = c.validate_file("tests/fixtures/pacs_002_2026_invalid.xml", 2026, "pacs.002")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r14 = by_rule["pacs.002:R14"]
    assert r14["line"] is not None
    assert r14["xpath"]
    assert "OrgnlInstrId" in r14["xpath"]
