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
