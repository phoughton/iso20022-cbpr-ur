"""Optional XSD (schema) validation - a separate, second result set.

XSD files are **not** shipped with the package; the caller supplies a path (or
several). Each XSD is applied by matching its ``targetNamespace`` to the relevant
subtree of the message: the ``Document`` for a message schema, the ``AppHdr`` for
a head.001 schema. This is kept entirely separate from usage-rule validation.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from lxml import etree

from .loader import local_name


def _xsd_parser() -> "etree.XMLParser":
    return etree.XMLParser(no_network=True, resolve_entities=False)


def load_schema(xsd_path: str) -> Tuple[Optional["etree.XMLSchema"], Optional[str], Optional[str]]:
    """Load an XSD.

    Returns ``(schema, target_namespace, error)``. On failure ``schema`` is None
    and ``error`` carries a human-readable message; relative includes/imports are
    resolved by lxml relative to ``xsd_path``.
    """
    try:
        xsd_doc = etree.parse(xsd_path, _xsd_parser())
        target_ns = xsd_doc.getroot().get("targetNamespace")
        schema = etree.XMLSchema(xsd_doc)
        return schema, target_ns, None
    except Exception as exc:  # OSError, XMLSchemaParseError, XMLSyntaxError, ...
        return None, None, f"{type(exc).__name__}: {exc}"


def _pick_element(bah, doc, target_ns: Optional[str]):
    """Choose the subtree to validate by namespace, with a Document fallback."""
    doc_ns = etree.QName(doc).namespace if doc is not None else None
    bah_ns = etree.QName(bah).namespace if bah is not None else None
    if target_ns and target_ns == doc_ns:
        return doc, "Document", False
    if target_ns and target_ns == bah_ns:
        return bah, "AppHdr", False
    # No namespace match: validate the Document (or AppHdr) as a best effort.
    if doc is not None:
        return doc, "Document", True
    if bah is not None:
        return bah, "AppHdr", True
    return None, None, True


def _validate_one(tree, bah, doc, xsd_path: str) -> dict:
    schema, target_ns, load_error = load_schema(xsd_path)
    if schema is None:
        return {
            "file": xsd_path,
            "target_namespace": None,
            "validated_element": None,
            "valid": False,
            "errors": [],
            "load_error": load_error,
        }

    element, which, mismatch = _pick_element(bah, doc, target_ns)
    result = {
        "file": xsd_path,
        "target_namespace": target_ns,
        "validated_element": which or "root",
        "valid": False,
        "errors": [],
    }
    if mismatch:
        result["namespace_mismatch"] = True
    if element is None:
        result["errors"].append(
            {"message": "No Document or AppHdr element to validate.", "line": None, "xpath": ""}
        )
        return result

    is_valid = schema.validate(element)
    result["valid"] = bool(is_valid)
    for err in schema.error_log:
        result["errors"].append(
            {"message": err.message, "line": err.line, "xpath": err.path or ""}
        )
    return result


def validate_with_xsds(tree, bah, doc, xsd_paths: List[str]) -> dict:
    """Validate the message against one or more XSDs; return a separate result block."""
    schemas = [_validate_one(tree, bah, doc, p) for p in xsd_paths]
    return {
        "checked": True,
        "schema_valid": all(s["valid"] for s in schemas),
        "schemas": schemas,
    }
