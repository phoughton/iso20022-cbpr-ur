import cbpr_rules as c


def test_enforced_only_filters_advisory():
    full = c.list_rules(2025, "pacs.008")
    enforced = c.list_rules(2025, "pacs.008", enforced_only=True)
    assert enforced, "expected some enforceable rules"
    assert all(r["enforced"] is True for r in enforced)
    assert len(enforced) < len(full)  # at least one advisory rule was dropped
    assert any(r["enforced"] is False for r in full)
    enforced_numbers = {r["rule_number"] for r in enforced}
    advisory_numbers = {r["rule_number"] for r in full if not r["enforced"]}
    assert enforced_numbers.isdisjoint(advisory_numbers)


def test_default_is_unchanged():
    assert c.list_rules(2025, "pacs.008") == c.list_rules(2025, "pacs.008", enforced_only=False)
    # with_xpaths is opt-in: default dicts carry no "xpaths" key
    assert all("xpaths" not in r for r in c.list_rules(2025, "pacs.008"))


def test_with_xpaths_attaches_affected_fields():
    rules = {r["rule_number"]: r for r in
             c.list_rules(2025, "pacs.008", with_xpaths=True)}
    # every enforced rule has at least one affected path; advisory rules have none
    for r in rules.values():
        assert "xpaths" in r
        if r["enforced"]:
            assert r["xpaths"], r["rule_number"]
        else:
            assert r["xpaths"] == []
    # paths are anchored at /Document, /AppHdr, or a //Name wildcard
    for r in rules.values():
        for p in r["xpaths"]:
            assert p.startswith("/Document") or p.startswith("/AppHdr") or p.startswith("//")

    # universal IBAN rule -> the IBAN element (no instance in the example -> wildcard)
    assert "//IBAN" in rules["pacs.008:VAL-IBAN"]["xpaths"]
    # currency rule includes an @Ccy attribute target
    assert any(p.endswith("/@Ccy") for p in rules["pacs.008:VAL-CCY"]["xpaths"])
    # scoped BIC rule lists ONLY BICFI fields (disambiguation), not every agent field
    bic = rules["pacs.008:VAL-BIC"]["xpaths"]
    assert bic and all(p.endswith("/BICFI") for p in bic)


def test_with_xpaths_is_deterministic():
    a = c.list_rules(2025, "pacs.008", with_xpaths=True)
    b = c.list_rules(2025, "pacs.008", with_xpaths=True)
    assert a == b
