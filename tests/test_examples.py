"""Bundled min/max example messages must stay valid, distinct, and complete."""
import glob
import os

import pytest
from lxml import etree

import cbpr_rules as c
from cbpr_rules import schema as _schema, loader as _loader

YEARS = (2025, 2026)
VARIANTS = ("min", "max")
REPO = os.path.dirname(os.path.dirname(__file__))
RAW = os.path.join(REPO, "raw_rules_files")

_COMBOS = [(y, mt, v) for y in YEARS for mt in c.available(y) for v in VARIANTS]


def _count_elements(xml):
    return sum(1 for _ in etree.fromstring(xml.encode()).iter() if isinstance(_.tag, str))


@pytest.mark.parametrize("year,msgtype,variant", _COMBOS)
def test_every_example_is_usage_valid(year, msgtype, variant):
    xml = c.example_message(year, msgtype, variant)
    result = c.validate_string(xml, year, msgtype)
    assert result["valid"] is True, (year, msgtype, variant, result["violations"][:3])
    assert result["violations"] == []


@pytest.mark.parametrize("year,msgtype", [(y, mt) for y in YEARS for mt in c.available(y)])
def test_max_is_richer_than_min(year, msgtype):
    assert _count_elements(c.example_message(year, msgtype, "max")) > \
        _count_elements(c.example_message(year, msgtype, "min"))


def _enriched_xsds(year, msgtype):
    doc = glob.glob(os.path.join(RAW, str(year), msgtype, "*iso15enriched.xsd"))
    hdr = glob.glob(os.path.join(RAW, str(year), "head.001", "*.xsd"))
    return (doc + hdr) if doc and hdr else None


@pytest.mark.skipif(not os.path.isdir(RAW), reason="source XSDs not present (gitignored)")
@pytest.mark.parametrize("year,msgtype,variant", _COMBOS)
def test_every_example_is_xsd_valid(year, msgtype, variant):
    xsds = _enriched_xsds(year, msgtype)
    if not xsds:
        pytest.skip(f"no XSD for {msgtype} {year}")
    xml = c.example_message(year, msgtype, variant)
    tree = _loader.parse_string(xml)
    bah, doc = _loader.locate(tree)
    sch = _schema.validate_with_xsds(tree, bah, doc, xsds)
    assert sch["schema_valid"], (year, msgtype, variant, sch["schemas"])


def _existing_sample_texts():
    out = []
    for pat in ("test_files/**/*.xml", "tests/fixtures/*.xml"):
        for p in glob.glob(os.path.join(REPO, pat), recursive=True):
            with open(p, encoding="utf-8") as f:
                out.append("".join(f.read().split()))
    return out


def _identifiers(xml):
    root = etree.fromstring(xml.encode())
    out = {"BICFI": [], "IBAN": [], "LEI": []}
    for el in root.iter():
        ln = el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""
        if ln in out and el.text:
            out[ln].append(el.text.strip())
    return out


def test_examples_are_synthetic_and_valid():
    from cbpr_rules.validators import is_valid_bic, is_valid_iban, is_valid_lei

    existing = _existing_sample_texts()
    validators = {"BICFI": is_valid_bic, "IBAN": is_valid_iban, "LEI": is_valid_lei}
    seen_any = False
    for year in YEARS:
        for msgtype in c.available(year):
            for variant in VARIANTS:
                xml = c.example_message(year, msgtype, variant)
                # No example reproduces an on-disk sample.
                assert "".join(xml.split()) not in existing, (year, msgtype, variant)
                for kind, values in _identifiers(xml).items():
                    for v in values:
                        seen_any = True
                        # Generated identifiers are valid and appear in no real sample.
                        assert validators[kind](v), (year, msgtype, variant, kind, v)
                        assert not any(v in t for t in existing), (kind, v)
    assert seen_any  # examples actually contain generated identifiers


def test_unknown_example_raises():
    with pytest.raises(c.engine.ValidationError):
        c.example_message(2025, "pacs.008", "tiny")
    with pytest.raises(c.engine.ValidationError):
        c.example_message(2025, "pacs.999", "max")


def test_custom_wrapper_still_valid():
    xml = c.example_message(2025, "pacs.008", "max", wrapper="BusinessMessage")
    assert "<BusinessMessage>" in xml
    assert c.validate_string(xml, 2025, "pacs.008")["valid"]
