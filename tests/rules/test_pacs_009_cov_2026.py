import cbpr_rules as c

MT = "pacs.009_cov"
VALID = "tests/fixtures/pacs_009_cov_2026_valid.xml"
INVALID = "tests/fixtures/pacs_009_cov_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, MT)
    assert result["valid"] is True
    assert result["message_type"] == MT
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, MT)
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # BusinessMessageIdentifier does not match GroupHeader MessageIdentification
    assert f"{MT}:R1" in fired
    # From BIC does not match Instructing Agent BIC
    assert f"{MT}:R5" in fired
    # InstructionId starts with a slash
    assert f"{MT}:R13" in fired
    # Commodity currency XAU on the interbank settlement amount
    assert f"{MT}:R17" in fired
    # Underlying remittance: Unstructured and Structured mutually exclusive
    assert f"{MT}:R10" in fired
    # Underlying Creditor has neither AnyBIC nor Name
    assert f"{MT}:R54" in fired
    # BusinessMessageIdentifier does not carry the GroupHeader MsgId (promoted)
    assert f"{MT}:R7" in fired
    # Underlying Debtor structured PstlAdr value duplicated in AddressLine (promoted)
    assert f"{MT}:R23" in fired
    # Underlying Debtor AnyBIC present together with Name/PostalAddress (promoted)
    assert f"{MT}:R40" in fired


def test_promoted_rules_are_enforced_not_advisory():
    result = c.validate_file(VALID, 2026, MT)
    adv = {a["rule_number"] for a in result["advisory"]}
    for promoted in ("R7", "R8", "R23", "R40", "R52", "R61"):
        assert f"{MT}:{promoted}" not in adv


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, MT)
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r17 = by_rule[f"{MT}:R17"]
    assert r17["line"] is not None
    assert r17["xpath"]
    assert "IntrBkSttlmAmt" in r17["xpath"]
    assert r17["description"]
