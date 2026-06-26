"""Command-line interface: ``cbpr-validate``."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
from typing import List, Optional

from . import __version__
from . import idgen
from .engine import (
    ValidationError,
    available,
    example_message,
    list_rules,
    validate_file,
    validate_string,
)


def _generate(args) -> List[str]:
    """Produce the ``--generate`` output lines (one id per --count)."""
    kind = args.generate
    out: List[str] = []
    for i in range(max(args.count, 1)):
        seed = f"{args.seed}:{i}" if args.count > 1 else args.seed
        if kind == "iban":
            if not args.country:
                raise ValueError("--generate iban requires --country (e.g. --country AT)")
            out.append(idgen.generate_iban(args.country, seed))
        elif kind == "lei":
            out.append(idgen.generate_lei(seed))
        elif kind == "bic":
            out.append(idgen.generate_bic(args.bank, args.country or "GB", args.branch, seed))
        elif kind in ("uuid", "uetr"):
            out.append(idgen.generate_uuid(idgen.deterministic_int(seed or str(i), 0, 2**63)))
        elif kind == "mid":
            out.append(idgen.generate_mid("CBPR", args.country or "GB", i + 1))
        elif kind == "text":
            out.append(idgen.deterministic_string(seed or "text", 16))
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cbpr-validate",
        description="Validate ISO 20022 CBPR+ XML against SWIFT usage rules.",
    )
    p.add_argument("file", nargs="?", help="XML file to validate (reads stdin if omitted).")
    p.add_argument("-y", "--year", type=int, required=False, help="Rule year, e.g. 2025 or 2026.")
    p.add_argument(
        "-t",
        "--type",
        dest="msgtype",
        help="Message type override, e.g. pacs.008 or pacs.008_stp "
        "(auto-detected from the Document namespace if omitted).",
    )
    p.add_argument(
        "--format",
        choices=("text", "compact", "json"),
        default="text",
        help="Output format: text (rich, default), compact (one finding per line, "
        "compiler-style — for tools/agents), or json (full machine-readable).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Alias for --format json.",
    )
    p.add_argument(
        "--xsd",
        action="append",
        metavar="PATH",
        help="Also schema-validate against this XSD (repeatable). Results are "
        "shown separately from usage rules. Auto-matched to the Document or AppHdr "
        "by the XSD's targetNamespace.",
    )
    p.add_argument(
        "--advisory",
        action="store_true",
        help="Also list the advisory (non-enforced) rules in full.",
    )
    p.add_argument(
        "--example",
        choices=("min", "max"),
        help="Print a bundled example message for --year/--type instead of validating: "
        "min (mandatory fields only) or max (every field populated). Both are XSD- and "
        "usage-rule-valid.",
    )
    p.add_argument(
        "--wrapper",
        default="Envelope",
        metavar="TAG",
        help="Root element tag wrapping the AppHdr+Document in --example output "
        "(default: Envelope).",
    )
    p.add_argument(
        "--generate",
        choices=("iban", "lei", "bic", "uuid", "uetr", "mid", "text"),
        help="Generate a deterministic, structurally-valid identifier and print it "
        "(use --seed/--country/--bank/--branch/--count to control output).",
    )
    p.add_argument("--seed", default="", help="Seed for --generate (same seed -> same output).")
    p.add_argument("--country", help="Country code for --generate iban/bic/mid (e.g. AT, GB).")
    p.add_argument("--bank", help="Bank code for --generate bic (4 letters, padded with X).")
    p.add_argument("--branch", default="XXX", help="Branch code for --generate bic (default XXX).")
    p.add_argument("--count", type=int, default=1, help="How many ids to generate (default 1).")
    p.add_argument(
        "--list",
        action="store_true",
        help="List the rules for --year/--type instead of validating.",
    )
    p.add_argument(
        "--enforced",
        action="store_true",
        help="List only the enforceable (mechanically-checked) rules for --year/--type; "
        "advisory rules are omitted. Implies --list.",
    )
    p.add_argument(
        "--list-types", action="store_true", help="List message types available for --year."
    )
    p.add_argument("--version", action="version", version=f"cbpr-validate {__version__}")
    return p


def _wrap(text: str, indent: str, width: int) -> List[str]:
    text = " ".join((text or "").split())
    if not text:
        return []
    return textwrap.wrap(
        text, width=width, initial_indent=indent, subsequent_indent=indent
    ) or [indent + text]


def _format_text(result: dict, show_advisory: bool = False) -> str:
    width = max(60, min(shutil.get_terminal_size((100, 24)).columns, 100))
    rule = "─" * width
    lines: List[str] = []
    status = "✓ VALID" if result["valid"] else "✗ INVALID"
    lines.append(
        f"{status}  {result['message_type']}  (rules year {result['year']}, "
        f"{result['rules_evaluated']} enforced rules evaluated)"
    )

    violations = result["violations"]
    if violations:
        lines.append("")
        lines.append(f"VIOLATIONS ({len(violations)})")
        lines.append(rule)
        for i, v in enumerate(violations, 1):
            if i > 1:
                lines.append("")
            sev = v["severity"].upper()
            loc = f"line {v['line']}" if v["line"] is not None else "line ?"
            lines.append(f"{i}. [{sev}] {v['rule_number']}  {v['name']}")
            lines.extend(_wrap(v["description"], "     ", width))
            if v.get("detail"):
                lines.extend(_wrap(f"Problem:  {v['detail']}", "     ", width))
            if v.get("found"):
                lines.extend(_wrap(f"Found:    {v['found']}", "     ", width))
            lines.append(f"     At:       {loc}  {v['xpath']}")
    elif result["valid"]:
        lines.append("No violations found.")

    advisory = result.get("advisory") or []
    if advisory:
        lines.append("")
        if show_advisory:
            lines.append(f"ADVISORY — not enforced ({len(advisory)})")
            lines.append(rule)
            for a in advisory:
                lines.append(f"• {a['rule_number']}  {a['name']}")
                lines.extend(_wrap(a["description"], "    ", width))
        else:
            lines.append(
                f"{len(advisory)} advisory rule(s) not enforced "
                f"(run with --advisory to list them)."
            )

    xsd = result.get("xsd")
    if xsd is not None:
        lines.append("")
        overall = "✓ SCHEMA-VALID" if xsd["schema_valid"] else "✗ SCHEMA-INVALID"
        lines.append(f"XSD SCHEMA VALIDATION  {overall}")
        lines.append(rule)
        for s in xsd["schemas"]:
            mark = "✓" if s["valid"] else "✗"
            tgt = s.get("validated_element") or "?"
            note = " [namespace mismatch]" if s.get("namespace_mismatch") else ""
            lines.append(f"{mark} {s['file']}  (validated {tgt}{note})")
            if s.get("load_error"):
                lines.extend(_wrap(f"Could not load schema: {s['load_error']}", "     ", width))
            for e in s["errors"]:
                loc = f"line {e['line']}" if e.get("line") is not None else "line ?"
                lines.extend(_wrap(f"{loc}: {e['message']}", "     ", width))
    return "\n".join(lines)


def _format_compact(result: dict, source: str) -> str:
    """One finding per line, compiler/linter-style, for tools and coding agents.

    ``<source>:<line>: <severity> [<rule>] <message> | at <xpath>`` per violation,
    followed by a single greppable ``VALID:``/``INVALID:`` summary line. Advisory
    (non-enforced) rules are omitted; use --json or text --advisory for those.
    """
    lines: List[str] = []
    for v in result["violations"]:
        line = v["line"] if v["line"] is not None else "?"
        message = " ".join((v.get("detail") or v["description"] or "").split())
        suffix = f" | at {v['xpath']}" if v.get("xpath") else ""
        lines.append(f"{source}:{line}: {v['severity']} [{v['rule_number']}] {message}{suffix}")

    xsd = result.get("xsd")
    schema_errors = 0
    if xsd is not None:
        for s in xsd["schemas"]:
            if s.get("load_error"):
                schema_errors += 1
                lines.append(f"{s['file']}: schema-error could not load schema: {s['load_error']}")
            for e in s["errors"]:
                schema_errors += 1
                eline = e["line"] if e.get("line") is not None else "?"
                msg = " ".join((e.get("message") or "").split())
                lines.append(f"{s['file']}:{eline}: schema-error {msg}")

    n = len(result["violations"])
    verdict = "VALID" if result["valid"] else "INVALID"
    parts = [f"{n} violation{'s' if n != 1 else ''}"]
    if xsd is not None:
        parts.append(f"{schema_errors} schema error{'s' if schema_errors != 1 else ''}")
    summary = f"{verdict}: {', '.join(parts)} ({result['rules_evaluated']} rules)"
    lines.append(summary)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list_types:
        if args.year is None:
            print("error: --year is required for --list-types", file=sys.stderr)
            return 2
        types = available(args.year)
        print(json.dumps(types) if args.json else "\n".join(types))
        return 0

    if args.generate:
        try:
            for line in _generate(args):
                print(line)
        except (ValueError, ValidationError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.example:
        if args.year is None or args.msgtype is None:
            print("error: --example requires --year and --type", file=sys.stderr)
            return 2
        try:
            print(example_message(args.year, args.msgtype, args.example, wrapper=args.wrapper))
        except ValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.list or args.enforced:
        if args.year is None or args.msgtype is None:
            print("error: --year and --type are required for --list", file=sys.stderr)
            return 2
        rules = list_rules(args.year, args.msgtype, enforced_only=args.enforced)
        if args.json:
            print(json.dumps(rules, indent=2))
        else:
            for r in rules:
                flag = "" if r["enforced"] else " (advisory)"
                print(f"{r['rule_number']} - {r['name']}{flag}")
        return 0

    if args.year is None:
        print("error: --year is required to validate", file=sys.stderr)
        return 2

    source = args.file or "<stdin>"
    try:
        if args.file:
            result = validate_file(args.file, args.year, args.msgtype, xsd=args.xsd)
        else:
            data = sys.stdin.read()
            result = validate_string(data, args.year, args.msgtype, xsd=args.xsd)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    fmt = "json" if args.json else args.format
    if fmt == "json":
        print(json.dumps(result, indent=2))
    elif fmt == "compact":
        print(_format_compact(result, source))
    else:
        print(_format_text(result, show_advisory=args.advisory))

    schema_ok = "xsd" not in result or result["xsd"]["schema_valid"]
    return 0 if (result["valid"] and schema_ok) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
