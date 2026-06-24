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


def test_cli_compact_invalid(capsys):
    rc = cli.main(
        ["test_files/2025/cbprplus_pacs008_sample_dodgy_IBAN_and_bic_mismatch.xml",
         "--year", "2025", "--format", "compact"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    # one finding per line, compiler-style, with the offending value
    assert ":63: violation [pacs.008:VAL-IBAN]" in out
    assert "GB29NWBK60161331926818" in out
    # a single greppable verdict line, no XSD mention (no --xsd)
    summary = out.strip().splitlines()[-1]
    assert summary.startswith("INVALID:")
    assert "violations" in summary
    assert "schema" not in out


def test_cli_compact_valid(capsys):
    rc = cli.main(["tests/fixtures/mini_valid.xml", "--year", "2025", "--format", "compact"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip().startswith("VALID:")
    assert "XSD" not in out and "schema" not in out


def test_cli_compact_with_xsd(capsys):
    rc = cli.main(
        ["tests/fixtures/mini_invalid.xml", "--year", "2025", "--format", "compact",
         "--xsd", "tests/fixtures/mini.xsd"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "schema-error" in out
    assert "schema error" in out.strip().splitlines()[-1]


def test_cli_format_json_alias_matches_json_flag(capsys):
    cli.main(["tests/fixtures/pacs008_valid.xml", "--year", "2025", "--format", "json"])
    via_format = capsys.readouterr().out
    cli.main(["tests/fixtures/pacs008_valid.xml", "--year", "2025", "--json"])
    via_flag = capsys.readouterr().out
    assert via_format == via_flag
    assert json.loads(via_format)["message_type"] == "pacs.008"


def test_cli_xsd_json_includes_block(capsys):
    rc = cli.main(
        ["tests/fixtures/mini_valid.xml", "--year", "2025", "--xsd", "tests/fixtures/mini.xsd",
         "--json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["xsd"]["schema_valid"] is True
