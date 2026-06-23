from cbpr_rules.validators import (
    is_valid_bic,
    is_valid_country,
    is_valid_currency,
    is_valid_iban,
    is_valid_lei,
)


def test_iban_valid():
    assert is_valid_iban("GB82 WEST 1234 5698 7654 32")
    assert is_valid_iban("DE89370400440532013000")


def test_iban_invalid():
    assert not is_valid_iban("GB00WEST12345698765432")  # bad check digits
    assert not is_valid_iban("ZZ82WEST12345698765432")  # bad country
    assert not is_valid_iban("")
    assert not is_valid_iban("GB82")


def test_lei_valid():
    assert is_valid_lei("529900T8BM49AURSDO55")


def test_lei_invalid():
    assert not is_valid_lei("529900T8BM49AURSDO50")  # wrong check digits
    assert not is_valid_lei("TOOSHORT")


def test_bic():
    assert is_valid_bic("DEUTDEFF")
    assert is_valid_bic("DEUTDEFF500")
    assert not is_valid_bic("DEUTXXFF")  # XX not a country
    assert not is_valid_bic("DEUT")


def test_country():
    assert is_valid_country("GB")
    assert is_valid_country("de")  # case-insensitive
    assert not is_valid_country("XX")


def test_currency():
    assert is_valid_currency("EUR")
    assert is_valid_currency("usd")
    assert not is_valid_currency("ZZZ")
