"""Command-line interface: ``cbpr-validate``."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
from typing import List, Optional

from . import __version__
from .engine import ValidationError, available, list_rules, validate_file, validate_string


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
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
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
        "--list",
        action="store_true",
        help="List the rules for --year/--type instead of validating.",
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


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list_types:
        if args.year is None:
            print("error: --year is required for --list-types", file=sys.stderr)
            return 2
        types = available(args.year)
        print(json.dumps(types) if args.json else "\n".join(types))
        return 0

    if args.list:
        if args.year is None or args.msgtype is None:
            print("error: --year and --type are required for --list", file=sys.stderr)
            return 2
        rules = list_rules(args.year, args.msgtype)
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

    try:
        if args.file:
            result = validate_file(args.file, args.year, args.msgtype, xsd=args.xsd)
        else:
            data = sys.stdin.read()
            result = validate_string(data, args.year, args.msgtype, xsd=args.xsd)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(_format_text(result, show_advisory=args.advisory))

    schema_ok = "xsd" not in result or result["xsd"]["schema_valid"]
    return 0 if (result["valid"] and schema_ok) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
