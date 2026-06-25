"""Validation engine and public API."""
from __future__ import annotations

from importlib import resources
from typing import List, Optional

from lxml import etree

from . import loader
from . import schema as _schema
from .message import ParsedMessage
from .models import Rule, Severity
from .registry import available_message_types, load_rules

_VARIANTS = ("min", "max")


class ValidationError(Exception):
    """Raised when a message cannot be validated (parse error, unknown type)."""


def _normalise_xsd(xsd) -> List[str]:
    if xsd is None:
        return []
    return [xsd] if isinstance(xsd, str) else list(xsd)


def _validate_tree(tree, year: int, msgtype: Optional[str], xsd=None) -> dict:
    bah, doc = loader.locate(tree)
    if doc is None and bah is None:
        raise ValidationError("No <Document> or <AppHdr> element found in the input.")

    detected = loader.detect_message_type(doc)
    if msgtype is None:
        msgtype = detected
        if msgtype is None:
            raise ValidationError(
                "Could not detect the message type; pass msgtype explicitly."
            )

    msg = ParsedMessage(tree, bah, doc, message_type=msgtype, year=year)
    rules: List[Rule] = load_rules(year, msgtype)

    violations = []
    advisory = []
    for r in rules:
        if r.enforced:
            violations.extend(v.to_dict() for v in r.run(msg))
        else:
            advisory.append(
                {
                    "rule_number": r.rule_number,
                    "name": r.name,
                    "description": r.description,
                }
            )

    has_hard = any(v["severity"] == Severity.VIOLATION.value for v in violations)
    result = {
        "valid": not has_hard,
        "message_type": msgtype,
        "detected_message_type": detected,
        "year": int(year),
        "rules_evaluated": sum(1 for r in rules if r.enforced),
        "violations": violations,
        "advisory": advisory,
    }

    xsd_paths = _normalise_xsd(xsd)
    if xsd_paths:
        result["xsd"] = _schema.validate_with_xsds(tree, bah, doc, xsd_paths)
    return result


def validate_file(path: str, year: int, msgtype: Optional[str] = None, xsd=None) -> dict:
    """Validate an XML file against usage rules (and optionally one or more XSDs).

    ``xsd`` may be a path or a list of paths to XSD files (not bundled with the
    package). When supplied, schema results are returned in a separate ``"xsd"``
    key; when omitted, no ``"xsd"`` key is present.
    """
    try:
        tree = loader.parse_file(path)
    except Exception as exc:  # lxml.etree.XMLSyntaxError and friends
        raise ValidationError(f"Could not parse XML: {exc}") from exc
    return _validate_tree(tree, year, msgtype, xsd)


def validate_string(xml: str, year: int, msgtype: Optional[str] = None, xsd=None) -> dict:
    """Validate an XML string against usage rules (and optionally one or more XSDs)."""
    try:
        tree = loader.parse_string(xml)
    except Exception as exc:
        raise ValidationError(f"Could not parse XML: {exc}") from exc
    return _validate_tree(tree, year, msgtype, xsd)


def list_rules(year: int, msgtype: str, enforced_only: bool = False) -> List[dict]:
    """Return metadata for the rules registered for a (year, message type).

    With ``enforced_only=True`` only the enforceable (mechanically-checked) rules
    are returned, omitting advisory/catalogue-only ones.
    """
    rules = [r.to_dict() for r in load_rules(year, msgtype)]
    if enforced_only:
        rules = [r for r in rules if r["enforced"]]
    return rules


def available(year: int) -> List[str]:
    """Message types with rules available for a given year."""
    return available_message_types(year)


def _example_resource(year: int, msgtype: str, variant: str):
    return (
        resources.files("cbpr_rules")
        .joinpath("examples", f"y{int(year)}", f"{msgtype}.{variant}.xml")
    )


def example_variants(year: int, msgtype: str) -> List[str]:
    """Which example variants ('min'/'max') are bundled for a (year, message type)."""
    return [v for v in _VARIANTS if _example_resource(year, msgtype, v).is_file()]


def example_message(
    year: int, msgtype: str, variant: str = "max", wrapper: str = "Envelope"
) -> str:
    """Return a bundled, pre-verified example message for a (year, message type).

    ``variant`` is 'min' (mandatory fields only) or 'max' (every field populated).
    Both are guaranteed to pass the usage rules (and the CBPR+ XSDs). ``wrapper``
    overrides the single root element tag (default ``Envelope``) that holds the
    ``AppHdr`` and ``Document``. Raises ``ValidationError`` if no such example.
    """
    if variant not in _VARIANTS:
        raise ValidationError(
            f"Unknown variant '{variant}'; choose one of {', '.join(_VARIANTS)}."
        )
    res = _example_resource(year, msgtype, variant)
    if not res.is_file():
        types = ", ".join(available(year)) or "(none)"
        raise ValidationError(
            f"No {variant} example for '{msgtype}' in {int(year)}. "
            f"Available message types: {types}."
        )
    text = res.read_text(encoding="utf-8")
    if wrapper and wrapper != "Envelope":
        root = etree.fromstring(text.encode("utf-8"))
        root.tag = wrapper
        text = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        ).decode("utf-8")
    return text
