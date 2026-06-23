import cbpr_rules as c


VALID = "tests/fixtures/camt_052_2026_valid.xml"
INVALID = "tests/fixtures/camt_052_2026_invalid.xml"


def test_valid_message_has_no_violations():
    result = c.validate_file(VALID, 2026, "camt.052")
    assert result["valid"] is True
    assert result["message_type"] == "camt.052"
    assert result["violations"] == []


def test_invalid_message_flags_expected_rules():
    result = c.validate_file(INVALID, 2026, "camt.052")
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    assert "camt.052:R1" in fired   # BAH/Report CopyDuplicate mismatch
    assert "camt.052:R2" in fired   # BizMsgIdr != GroupHeader MsgId
    assert "camt.052:R7" in fired   # PageNumber == 0
    assert "camt.052:R9" in fired   # Owner PostalAddress without Name
    assert "camt.052:R13" in fired  # InstrId starts with slash
    # newly enforced (promoted from advisory)
    assert "camt.052:R4" in fired   # BizMsgIdr does not carry GroupHeader MsgId
    assert "camt.052:R12" in fired  # Interest total != sum of record amounts
    assert "camt.052:R16" in fired  # Interest total != sum of record amounts


def test_promoted_rules_no_longer_advisory():
    result = c.validate_file(VALID, 2026, "camt.052")
    adv = {a["rule_number"] for a in result["advisory"]}
    for promoted in ("camt.052:R4", "camt.052:R5", "camt.052:R12",
                     "camt.052:R16", "camt.052:R17"):
        assert promoted not in adv
    # rules that stay advisory
    assert "camt.052:R11" in adv  # Charges total = sum (bilateral context)
    assert "camt.052:R3" in adv   # Related BAH (no related message available)


def test_violations_carry_xpath_and_line():
    result = c.validate_file(INVALID, 2026, "camt.052")
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r7 = by_rule["camt.052:R7"]
    assert r7["line"] is not None
    assert r7["xpath"]
    assert "PgNb" in r7["xpath"]
