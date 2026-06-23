import json

from cbpr_rules import cli


def test_cli_valid_returns_zero(capsys):
    rc = cli.main(["tests/fixtures/pacs008_valid.xml", "--year", "2025"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "VALID" in out


def test_cli_invalid_returns_one(capsys):
    rc = cli.main(["tests/fixtures/pacs008_invalid.xml", "--year", "2025"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "INVALID" in out
    assert "pacs.008:R41" in out


def test_cli_json_output(capsys):
    rc = cli.main(["tests/fixtures/pacs008_valid.xml", "--year", "2025", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["valid"] is True
    assert payload["message_type"] == "pacs.008"


def test_cli_list_types(capsys):
    rc = cli.main(["--year", "2025", "--list-types"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "pacs.008" in out


def test_cli_missing_year_errors(capsys):
    rc = cli.main(["tests/fixtures/pacs008_valid.xml"])
    assert rc == 2


def test_cli_xsd_valid_exits_zero(capsys):
    rc = cli.main(
        ["tests/fixtures/mini_valid.xml", "--year", "2025", "--xsd", "tests/fixtures/mini.xsd"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "XSD SCHEMA VALIDATION" in out
    assert "SCHEMA-VALID" in out


def test_cli_xsd_invalid_exits_one(capsys):
    rc = cli.main(
        ["tests/fixtures/mini_invalid.xml", "--year", "2025", "--xsd", "tests/fixtures/mini.xsd"]
    )
    out = capsys.readouterr().out
    assert rc == 1  # usage rules pass but schema fails -> non-zero
    assert "SCHEMA-INVALID" in out


def test_cli_without_xsd_has_no_xsd_section(capsys):
    rc = cli.main(["tests/fixtures/mini_valid.xml", "--year", "2025"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "XSD" not in out


def test_cli_xsd_json_includes_block(capsys):
    rc = cli.main(
        ["tests/fixtures/mini_valid.xml", "--year", "2025", "--xsd", "tests/fixtures/mini.xsd",
         "--json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["xsd"]["schema_valid"] is True
