"""Self-tests for the Counting Strings ID generation library (spec section 9)."""
import re

import pytest

from cbpr_rules import idgen as g
from cbpr_rules.validators import is_valid_bic, is_valid_iban, is_valid_lei

BIC_XSD = re.compile(r"[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


# ---- Counting strings ----
def test_counting_string_increment_and_carry():
    assert g.counting_string("0") == "1"
    assert g.counting_string("9") == "A"
    assert g.counting_string("Z") == "a"
    assert g.counting_string("z") == "00"          # single char wraps and grows
    assert g.counting_string("0z") == "10"         # carry into next position
    assert g.counting_string("zz") == "000"


def test_counting_sequence_length_and_progress():
    seq = g.counting_sequence("0", 5)
    assert seq == ["0", "1", "2", "3", "4"]
    assert len(g.counting_sequence("A", 100)) == 100


# ---- IBAN: one per country, mod-97 + length ----
@pytest.mark.parametrize("country", g.iban_countries())
def test_generate_iban_valid(country):
    iban = g.generate_iban(country, seed="example001")
    assert is_valid_iban(iban)
    assert len(iban) == g.BBAN_SPECS[country][0]
    assert iban[:2] == country


def test_generate_iban_unknown_country():
    with pytest.raises(ValueError):
        g.generate_iban("ZZ", seed="x")


# ---- LEI ----
def test_generate_lei_check_digits():
    for seed in ("a", "b", "c"):
        lei = g.generate_lei(seed)
        assert is_valid_lei(lei)
        assert len(lei) == 20


# ---- BIC ----
def test_generate_bic_valid_and_xsd():
    b = g.generate_bic(bank_code="JSBP", country="GB", seed="x")
    assert b.startswith("JSBPGB")
    assert is_valid_bic(b) and BIC_XSD.match(b)
    assert is_valid_bic(g.generate_bic(country="US", seed="y"))


# ---- UUID / UETR ----
def test_generate_uuid_is_v4():
    for ctr in (0, 1, 12345, 2**63):
        u = g.generate_uuid(ctr)
        assert UUID_RE.match(u), u
        assert u[14] == "4"  # version nibble
    assert g.generate_uetr(7) == g.generate_uuid(7)


# ---- MID ----
def test_generate_mid_format():
    assert g.generate_mid("CBPR", "GB", 1) == "CBPRGB000001"


# ---- Determinism ----
def test_deterministic_same_seed_same_output():
    assert g.generate_iban("DE", "s1") == g.generate_iban("DE", "s1")
    assert g.generate_lei("s1") == g.generate_lei("s1")
    assert g.generate_iban("DE", "s1") != g.generate_iban("DE", "s2")
    assert g.deterministic_int("k", 0, 9) == g.deterministic_int("k", 0, 9)
    assert 0 <= g.deterministic_int("anything", 0, 9) <= 9
