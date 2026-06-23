import cbpr_rules as c

MT = "pacs.009_cov"
VALID = "tests/fixtures/pacs_009_cov_2025_valid.xml"
INVALID = "tests/fixtures/pacs_009_cov_2025_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2025, MT)
    assert result["valid"] is True
    assert result["message_type"] == MT
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2025, MT)
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # Business Service value wrong
    assert f"{MT}:R8" in fired
    # InstructionId starts with a slash
    assert f"{MT}:R14" in fired
    # Commodity currency XAU on the interbank settlement amount
    assert f"{MT}:R20" in fired
    # From BIC does not match Instructing Agent BIC (CopyDuplicate absent -> R2 and R3)
    assert f"{MT}:R2" in fired
    assert f"{MT}:R3" in fired
    # Underlying remittance: Unstructured and Structured mutually exclusive
    assert f"{MT}:R12" in fired
    # Underlying Debtor has neither AnyBIC nor Name
    assert f"{MT}:R72" in fired
    # Newly enforced: underlying Creditor has AnyBIC together with Name/PostalAddress
    assert f"{MT}:R118" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2025, MT)
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r20 = by_rule[f"{MT}:R20"]
    assert r20["line"] is not None
    assert r20["xpath"]
    assert "IntrBkSttlmAmt" in r20["xpath"]
    assert r20["description"]
