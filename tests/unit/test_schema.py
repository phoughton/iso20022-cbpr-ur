import cbpr_rules as c

XSD = "tests/fixtures/mini.xsd"


def test_no_xsd_means_no_xsd_key():
    result = c.validate_file("tests/fixtures/mini_valid.xml", 2025)
    assert "xsd" not in result


def test_xsd_valid_document():
    result = c.validate_file("tests/fixtures/mini_valid.xml", 2025, xsd=XSD)
    assert result["xsd"]["checked"] is True
    assert result["xsd"]["schema_valid"] is True
    s = result["xsd"]["schemas"][0]
    assert s["validated_element"] == "Document"
    assert s["target_namespace"] == "urn:test:mini"
    assert s["errors"] == []


def test_xsd_invalid_document_reports_error_with_line():
    result = c.validate_file("tests/fixtures/mini_invalid.xml", 2025, xsd=XSD)
    # usage rules unaffected (unknown type -> no rules); schema result is separate
    assert result["xsd"]["schema_valid"] is False
    s = result["xsd"]["schemas"][0]
    assert s["valid"] is False
    assert len(s["errors"]) >= 1
    assert s["errors"][0]["line"] is not None
    assert "Bad" in s["errors"][0]["message"]


def test_xsd_load_error_is_surfaced_not_raised():
    result = c.validate_file("tests/fixtures/mini_valid.xml", 2025, xsd="does_not_exist.xsd")
    assert result["xsd"]["schema_valid"] is False
    assert result["xsd"]["schemas"][0]["load_error"]


def test_multiple_xsds_each_reported():
    result = c.validate_file(
        "tests/fixtures/mini_valid.xml", 2025, xsd=[XSD, "does_not_exist.xsd"]
    )
    schemas = result["xsd"]["schemas"]
    assert len(schemas) == 2
    assert schemas[0]["valid"] is True
    assert schemas[1]["valid"] is False
    assert result["xsd"]["schema_valid"] is False  # one failed
