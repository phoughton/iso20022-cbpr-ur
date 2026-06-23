"""Parse CBPR+ XML and locate the Business Application Header and Document.

The loader is deliberately tolerant of wrapper tags (``<RequestPayload>``,
``<DataPDU>``, ``<Saa:Envelope>`` ...): it finds the ``AppHdr`` (head.001) and
``Document`` elements wherever they sit in the tree, matching by *local name* so
namespace prefixes and versions never matter.
"""
from __future__ import annotations

from typing import Optional, Tuple

from lxml import etree


def local_name(el) -> Optional[str]:
    """Local (namespace-stripped) tag name of an element, or None for comments/PIs."""
    tag = el.tag
    if not isinstance(tag, str):
        return None
    return tag.rsplit("}", 1)[-1]


def _parser() -> "etree.XMLParser":
    # huge_tree for large messages; keep line numbers; never touch the network.
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
        remove_comments=False,
    )


def parse_file(path: str) -> "etree._ElementTree":
    return etree.parse(path, _parser())


def parse_string(xml: str) -> "etree._ElementTree":
    data = xml.encode("utf-8") if isinstance(xml, str) else xml
    root = etree.fromstring(data, _parser())
    return etree.ElementTree(root)


def locate(tree: "etree._ElementTree") -> Tuple[Optional["etree._Element"], Optional["etree._Element"]]:
    """Return (app_header, document) elements, found anywhere under the root."""
    root = tree.getroot()
    bah = None
    doc = None
    for el in root.iter():
        ln = local_name(el)
        if ln == "AppHdr" and bah is None:
            bah = el
        elif ln == "Document" and doc is None:
            doc = el
        if bah is not None and doc is not None:
            break
    return bah, doc


def detect_message_type(doc: Optional["etree._Element"]) -> Optional[str]:
    """Derive the base message type (e.g. ``pacs.008``) from the Document namespace.

    Note: business variants (STP/COV/ADV) share a base namespace and cannot be
    distinguished from the XML alone - callers select those explicitly.
    """
    if doc is None:
        return None
    qname = etree.QName(doc)
    ns = qname.namespace or ""
    marker = "tech:xsd:"
    if marker in ns:
        ident = ns.split(marker, 1)[1]  # e.g. pacs.008.001.08
    else:
        ident = ns.rsplit(":", 1)[-1]
    parts = ident.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"  # pacs.008
    return ident or None
