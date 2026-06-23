"""Reusable check builders for the recurring CBPR+ rule patterns.

Each builder returns a ``check(msg, report)`` function, so it can be registered
directly with the ``@rule`` decorator::

    rule("pacs.008", 2025, "R20", NAME, DESC)(
        presence_together(BASE, "Nm", "PstlAdr")
    )

Hand-authored rules with bespoke logic just define ``fn(msg, report)`` directly
and use the query methods on ParsedMessage. These builders cover the common
templated patterns ("if X present then Y", "A must equal B", length/code lists)
so they need only be written once.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable, Optional, Sequence

from lxml import etree


def presence_together(base_path: str, a: str, b: str) -> Callable:
    """``a`` and ``b`` (relative to each ``base_path``) must be present together."""

    def check(msg, report):
        for ctx in msg.each(base_path):
            has_a = msg.present(a, ctx)
            has_b = msg.present(b, ctx)
            if has_a != has_b:
                report(ctx, detail=f"{a} and {b} must be present together")

    return check


def requires_if_present(base_path: str, trigger: str, required: str) -> Callable:
    """If ``trigger`` is present (per ``base_path``), ``required`` must be present."""

    def check(msg, report):
        for ctx in msg.each(base_path):
            if msg.present(trigger, ctx) and msg.absent(required, ctx):
                report(ctx, detail=f"{required} required when {trigger} is present")

    return check


def required_when_absent(
    base_path: str, absent_path: str, required: Sequence[str], mode: str = "all"
) -> Callable:
    """When ``absent_path`` is absent, ``required`` paths must be present.

    ``mode="all"`` (default): every path in ``required`` must be present.
    ``mode="any"``: at least one of ``required`` must be present.
    """

    def check(msg, report):
        for ctx in msg.each(base_path):
            if not msg.absent(absent_path, ctx):
                continue
            present = [p for p in required if msg.present(p, ctx)]
            ok = bool(present) if mode == "any" else len(present) == len(required)
            if not ok:
                joiner = " or " if mode == "any" else " and "
                report(ctx, detail=f"{joiner.join(required)} required when {absent_path} is absent")

    return check


def required_when_present(
    base_path: str, present_path: str, required: Sequence[str], mode: str = "all"
) -> Callable:
    """When ``present_path`` is present, ``required`` paths must be present too."""

    def check(msg, report):
        for ctx in msg.each(base_path):
            if not msg.present(present_path, ctx):
                continue
            found = [p for p in required if msg.present(p, ctx)]
            ok = bool(found) if mode == "any" else len(found) == len(required)
            if not ok:
                joiner = " or " if mode == "any" else " and "
                report(ctx, detail=f"{joiner.join(required)} required when {present_path} is present")

    return check


def mutually_exclusive(base_path: str, paths: Sequence[str]) -> Callable:
    """At most one of ``paths`` (relative to ``base_path``) may be present."""

    def check(msg, report):
        for ctx in msg.each(base_path):
            present = [p for p in paths if msg.present(p, ctx)]
            if len(present) > 1:
                report(ctx, detail=f"mutually exclusive: {', '.join(present)}")

    return check


def forbidden_when_present(base_path: str, forbidden: str, when: str) -> Callable:
    """``forbidden`` must not be present when ``when`` is present."""

    def check(msg, report):
        for ctx in msg.each(base_path):
            if msg.present(when, ctx) and msg.present(forbidden, ctx):
                report(ctx, detail=f"{forbidden} cannot be present when {when} is present")

    return check


def value_not_in(path: str, forbidden_values: Iterable[str]) -> Callable:
    """No occurrence of ``path`` may hold a value in ``forbidden_values``."""
    forbidden = set(forbidden_values)

    def check(msg, report):
        for node in msg.find(path):
            val = msg.text_of(node)
            if val in forbidden:
                report(node, detail=f"'{val}' is not allowed")

    return check


def not_matching_pattern(path: str, pattern: str) -> Callable:
    """Every occurrence of ``path`` must NOT match ``pattern`` (a forbidden regex)."""
    import re as _re

    rx = _re.compile(pattern)

    def check(msg, report):
        for node in msg.find(path):
            val = msg.text_of(node)
            if val and rx.fullmatch(val):
                report(node, detail="value matches a forbidden pattern")

    return check


# Structured PostalAddress components (short ISO tags), excluding AddressLine.
ADDRESS_COMPONENTS = (
    "Dept", "SubDept", "StrtNm", "BldgNb", "BldgNm", "Flr", "PstBx", "Room",
    "PstCd", "TwnNm", "TwnLctnNm", "DstrctNm", "CtrySubDvsn", "Ctry",
)


def address_lines_max_length(postal_path: str, limit: int = 35) -> Callable:
    """CBPR+ "unstructured address" rule.

    When a postal address uses only AddressLine (every structured component
    absent), each AddressLine must not exceed ``limit`` characters.
    """

    def check(msg, report):
        for adr in msg.each(postal_path):
            if msg.absent("AdrLine", adr):
                continue
            if any(msg.present(s, adr) for s in ADDRESS_COMPONENTS):
                continue
            for line in msg.find("AdrLine", adr):
                if len(msg.text_of(line)) > limit:
                    report(line, detail=f"AddressLine exceeds {limit} characters")

    return check


def address_hybrid(postal_path: str) -> Callable:
    """CBPR+ "hybrid address" rule.

    When AddressLine and any structured component are both present, TownName and
    Country are mandatory.
    """

    def check(msg, report):
        for adr in msg.each(postal_path):
            if msg.absent("AdrLine", adr):
                continue
            if not any(msg.present(s, adr) for s in ADDRESS_COMPONENTS):
                continue
            if not (msg.present("TwnNm", adr) and msg.present("Ctry", adr)):
                report(adr, detail="TownName and Country required for a hybrid address")

    return check


def same_value(
    path_a: str,
    path_b: str,
    unless_path: Optional[str] = None,
    unless_values: Sequence[str] = (),
) -> Callable:
    """Every occurrence of ``path_a`` must equal every occurrence of ``path_b``.

    Skipped when ``unless_path`` has any value in ``unless_values`` (e.g. a
    CopyDuplicate of COPY/CODU). Both anchored (absolute) paths.
    """

    def check(msg, report):
        if unless_path is not None and unless_values:
            if any(v in set(unless_values) for v in msg.values(unless_path)):
                return
        a_nodes = msg.find(path_a)
        b_vals = {msg.text_of(n) for n in msg.find(path_b)}
        a_vals = {msg.text_of(n) for n in a_nodes}
        if not a_nodes or not b_vals:
            return
        if a_vals != b_vals:
            target = a_nodes[0]
            report(target, detail=f"{path_a} must equal {path_b}")

    return check


def max_length(path: str, limit: int) -> Callable:
    """Every occurrence of ``path`` must not exceed ``limit`` characters."""

    def check(msg, report):
        for node in msg.find(path):
            if len(msg.text_of(node)) > limit:
                report(node, detail=f"exceeds {limit} characters")

    return check


def code_in(path: str, allowed: Iterable[str]) -> Callable:
    """Every occurrence of ``path`` must hold a value within ``allowed``."""
    allowed_set = set(allowed)

    def check(msg, report):
        for node in msg.find(path):
            val = msg.text_of(node)
            if val and val not in allowed_set:
                report(node, detail=f"'{val}' not in allowed code list")

    return check


def must_be_absent(path: str) -> Callable:
    """``path`` must not be present (element removed by the usage guideline)."""

    def check(msg, report):
        for node in msg.find(path):
            report(node, detail="element must not be used")

    return check


def each_value_valid(path: str, validator: Callable[[str], bool], label: str) -> Callable:
    """Every non-empty value at ``path`` must satisfy ``validator`` (e.g. IBAN/BIC)."""

    def check(msg, report):
        for node in msg.find(path):
            val = msg.text_of(node)
            if val and not validator(val):
                report(node, detail=f"invalid {label}: '{val}'")

    return check


# ---------------------------------------------------------------------------
# Cross-cutting checks promoted from advisory rules (Tier A / Tier B).
# Each is conservative: it skips when its inputs are absent or ambiguous, so a
# previously-valid message can never be made to fail spuriously.
# ---------------------------------------------------------------------------

def header_msg_def_id_matches() -> Callable:
    """``/AppHdr/MsgDefIdr``, if present, must equal the Document's definition id.

    The expected id is the namespace suffix of the ``<Document>`` element, e.g.
    ``pacs.009.001.08``. Cross-schema (BAH vs Document); skips if either absent.
    """

    def check(msg, report):
        if msg.bah is None or msg.document is None:
            return
        nodes = msg.find("/AppHdr/MsgDefIdr")
        if not nodes:
            return
        ns = etree.QName(msg.document).namespace or ""
        marker = "tech:xsd:"
        expected = ns.split(marker, 1)[1] if marker in ns else None
        val = msg.text_of(nodes[0])
        if expected and val and val != expected:
            report(nodes[0], detail=f"MsgDefIdr '{val}' does not match the message definition '{expected}'")

    return check


def business_msg_id_carries_group_id() -> Callable:
    """``/AppHdr/BizMsgIdr`` must contain the Document's ``GrpHdr/MsgId`` when present."""

    def check(msg, report):
        if msg.bah is None or msg.document is None:
            return
        bmi = msg.find("/AppHdr/BizMsgIdr")
        if not bmi:
            return
        msgid = None
        for grp in msg.iter_local("GrpHdr"):
            kids = msg.find("MsgId", grp)
            if kids:
                msgid = msg.text_of(kids[0])
                break
        if not msgid:
            return
        if msgid not in msg.text_of(bmi[0]):
            report(bmi[0], detail=f"BizMsgIdr should carry the GroupHeader MsgId '{msgid}'")

    return check


def _token_contained(value: str, line: str) -> bool:
    """True if ``value`` equals ``line`` or appears token-bounded within it."""
    if value == line:
        return True
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", line) is not None


def no_postal_address_duplication(min_len: int = 3) -> Callable:
    """No structured Postal Address value may be repeated inside an AddressLine.

    Scans every ``PstlAdr`` in the message. Conservative: only flags structured
    values of at least ``min_len`` characters that appear as a whole AddressLine
    or as a token-bounded substring of one.
    """

    def check(msg, report):
        for adr in msg.iter_local("PstlAdr"):
            lines = [msg.text_of(line) for line in msg.find("AdrLine", adr)]
            if not lines:
                continue
            for comp in ADDRESS_COMPONENTS:
                for node in msg.find(comp, adr):
                    val = msg.text_of(node)
                    if len(val) < min_len:
                        continue
                    if any(_token_contained(val, line) for line in lines):
                        report(node, detail=f"structured value '{val}' is duplicated in AddressLine")

    return check


def bic_presence_exclusive(party_path: str) -> Callable:
    """For a party: if ``Id/OrgId/AnyBIC`` is present, ``Nm`` and ``PstlAdr`` are not allowed."""

    def check(msg, report):
        for party in msg.each(party_path):
            if msg.present("Id/OrgId/AnyBIC", party) and (
                msg.present("Nm", party) or msg.present("PstlAdr", party)
            ):
                report(party, detail="Name/PostalAddress not allowed when AnyBIC is present")

    return check


def structured_remittance_max_total(path: str, limit: int = 9000) -> Callable:
    """Total text (excluding tags) of all Structured Remittance occurrences ≤ ``limit``."""

    def check(msg, report):
        nodes = msg.find(path)
        if not nodes:
            return
        total = sum(
            len("".join(t.strip() for t in node.itertext())) for node in nodes
        )
        if total > limit:
            report(nodes[0], detail=f"structured remittance total {total} exceeds {limit} characters")

    return check


def charges_required_when_amounts_differ(
    base_path: str, instructed_amt: str, settlement_amt: str, charges: str
) -> Callable:
    """If instructed & settlement amounts share a currency and differ, charges are mandatory.

    All sub-paths are relative to each ``base_path`` (e.g. the transaction).
    Skips unless both amounts are present with the same ``@Ccy`` and parse cleanly.
    """

    def check(msg, report):
        for ctx in msg.each(base_path):
            inst = msg.find(instructed_amt, ctx)
            sett = msg.find(settlement_amt, ctx)
            if not inst or not sett:
                continue
            i_ccy, s_ccy = inst[0].get("Ccy"), sett[0].get("Ccy")
            if not i_ccy or i_ccy != s_ccy:
                continue
            try:
                iv = Decimal(msg.text_of(inst[0]))
                sv = Decimal(msg.text_of(sett[0]))
            except (InvalidOperation, ValueError):
                continue
            if iv != sv and msg.absent(charges, ctx):
                report(ctx, detail="ChargesInformation is mandatory when instructed and settlement amounts differ in the same currency")

    return check


def amount_equals_sum(total_path: str, parts_path: str, tolerance: str = "0.01") -> Callable:
    """``total_path`` amount must equal the sum of ``parts_path`` amounts (same currency)."""
    tol = Decimal(tolerance)

    def check(msg, report):
        totals = msg.find(total_path)
        parts = msg.find(parts_path)
        if not totals or not parts:
            return
        ccys = {n.get("Ccy") for n in [totals[0], *parts] if n.get("Ccy")}
        if len(ccys) > 1:
            return
        try:
            total = Decimal(msg.text_of(totals[0]))
            summed = sum((Decimal(msg.text_of(p)) for p in parts), Decimal("0"))
        except (InvalidOperation, ValueError):
            return
        if abs(total - summed) > tol:
            report(totals[0], detail=f"total {total} does not equal the sum of records {summed}")

    return check
