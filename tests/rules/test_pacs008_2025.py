import cbpr_rules as c
from tests.conftest import read_fixture


def test_valid_message_has_no_violations():
    result = c.validate_file("tests/fixtures/pacs008_valid.xml", 2025)
    assert result["valid"] is True
    assert result["message_type"] == "pacs.008"
    assert result["violations"] == []
    assert result["rules_evaluated"] > 50


def test_message_type_auto_detected():
    result = c.validate_string(read_fixture("pacs008_valid.xml"), 2025)
    assert result["detected_message_type"] == "pacs.008"
    assert result["valid"] is True


def test_invalid_message_flags_expected_rules():
    result = c.validate_file("tests/fixtures/pacs008_invalid.xml", 2025)
    assert result["valid"] is False
    fired = {v["rule_number"] for v in result["violations"]}
    # cross-schema BIC mismatch (CopyDuplicate absent)
    assert "pacs.008:R2" in fired
    assert "pacs.008:R3" in fired
    # code exclusion, slash pattern, commodity currency, business service
    assert "pacs.008:R13" in fired
    assert "pacs.008:R38" in fired
    assert "pacs.008:R41" in fired
    assert "pacs.008:R8" in fired
    # party name/address + any-bic + grace period
    assert "pacs.008:R82" in fired
    assert "pacs.008:R81" in fired
    assert "pacs.008:R84" in fired


def test_violations_carry_xpath_and_line():
    result = c.validate_file("tests/fixtures/pacs008_invalid.xml", 2025)
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    r41 = by_rule["pacs.008:R41"]
    assert r41["line"] is not None
    assert "IntrBkSttlmAmt" in r41["xpath"]
    assert r41["description"]


def test_advisory_rules_surfaced_but_not_failing():
    result = c.validate_file("tests/fixtures/pacs008_valid.xml", 2025)
    assert result["advisory"]  # non-empty
    adv_numbers = {a["rule_number"] for a in result["advisory"]}
    assert "pacs.008:R4" in adv_numbers


def test_wrapper_tolerance_alternative_envelope():
    # Re-wrap the same message in a different envelope; result must be identical.
    xml = read_fixture("pacs008_valid.xml")
    inner = xml.split("?>", 1)[1]
    rewrapped = '<?xml version="1.0"?>\n<DataPDU><Body>' + inner + "</Body></DataPDU>"
    result = c.validate_string(rewrapped, 2025)
    assert result["valid"] is True
