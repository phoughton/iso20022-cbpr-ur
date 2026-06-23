"""Universal datatype rules applied to every message type: VAL-IBAN and VAL-LEI.

Regression tests for the bug class where a validator (``is_valid_iban``,
``is_valid_lei``) existed but was wired in inconsistently - IBAN into no rule at
all, LEI only into some message types and only on specific party paths - so
malformed values passed silently. Both are now single document-wide rules.
"""
import cbpr_rules as c

# Contains a structurally-invalid IBAN (GB29NWBK60161331926818) alongside a
# valid one (DE29100100100987654321).
DODGY = "test_files/2025/cbprplus_pacs008_sample_dodgy_IBAN_and_bic_mismatch.xml"
CLEAN = "tests/fixtures/pacs008_valid.xml"

# An invalid LEI on a non-agent party (Debtor org) and a second on an
# intermediary agent - positions older per-module rules did not all cover.
_LEI_XML = """<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
 <FIToFICstmrCdtTrf><CdtTrfTxInf>
  <Dbtr><Id><OrgId><LEI>THIS_IS_NOT_A_LEI</LEI></OrgId></Id></Dbtr>
  <IntrmyAgt1><FinInstnId><LEI>BADLEI</LEI></FinInstnId></IntrmyAgt1>
 </CdtTrfTxInf></FIToFICstmrCdtTrf></Document>"""


def test_invalid_iban_is_flagged():
    result = c.validate_file(DODGY, 2025, "pacs.008")
    assert result["valid"] is False
    by_rule = {v["rule_number"]: v for v in result["violations"]}
    assert "pacs.008:VAL-IBAN" in by_rule
    finding = by_rule["pacs.008:VAL-IBAN"]
    assert "GB29NWBK60161331926818" in finding["found"]
    assert finding["line"] is not None
    assert "IBAN" in finding["xpath"]


def test_valid_message_has_no_iban_violation():
    result = c.validate_file(CLEAN, 2025, "pacs.008")
    fired = {v["rule_number"] for v in result["violations"]}
    assert "pacs.008:VAL-IBAN" not in fired


def test_invalid_lei_flagged_in_any_position_both_years():
    # pacs.008 2025 had no LEI rule at all before; both years now catch every
    # <LEI>, in any party position, exactly once (no duplicate reporting).
    for year in (2025, 2026):
        result = c.validate_string(_LEI_XML, year, "pacs.008")
        lei = [v for v in result["violations"] if v["rule_number"] == "pacs.008:VAL-LEI"]
        found = sorted(v["found"] for v in lei)
        assert found == ["<LEI>BADLEI</LEI>", "<LEI>THIS_IS_NOT_A_LEI</LEI>"], (year, found)


def test_universal_rules_present_for_every_message_type():
    for year in (2025, 2026):
        for msgtype in c.available(year):
            numbers = {r["rule_number"] for r in c.list_rules(year, msgtype)}
            assert f"{msgtype}:VAL-IBAN" in numbers, (year, msgtype)
            assert f"{msgtype}:VAL-LEI" in numbers, (year, msgtype)
