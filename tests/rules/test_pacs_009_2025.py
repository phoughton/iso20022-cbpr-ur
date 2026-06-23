import cbpr_rules as c


def test_valid_message_has_no_violations():
    result = c.validate_file("tests/fixtures/pacs_009_2025_valid.xml", 2025, "pacs.009")
    assert result["valid"] is True
    assert result["message_type"] == "pacs.009"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file("tests/fixtures/pacs_009_2025_invalid.xml", 2025, "pacs.009")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # cross-schema BIC mismatch (CopyDuplicate absent -> R2 and R3)
    assert "pacs.009:R2" in fired
    assert "pacs.009:R3" in fired
    # instruction id slash pattern, commodity currency, business service value
    assert "pacs.009:R13" in fired
    assert "pacs.009:R20" in fired
    assert "pacs.009:R8" in fired
    # agent name present without postal address (PrvsInstgAgt1)
    assert "pacs.009:R25" in fired
    # newly enforced: MsgDefIdr does not match the Document namespace suffix
    assert "pacs.009:R6" in fired
    # newly enforced: structured postal value duplicated in an AddressLine
    assert "pacs.009:R28" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file("tests/fixtures/pacs_009_2025_invalid.xml", 2025, "pacs.009")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r20 = by_rule["pacs.009:R20"]
    assert r20["line"] is not None
    assert "IntrBkSttlmAmt" in r20["xpath"]
    assert r20["description"]
