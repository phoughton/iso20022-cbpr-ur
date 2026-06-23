"""ParsedMessage - namespace-agnostic path access over a CBPR+ message.

Rules are authored against the short ISO 20022 XML-tag paths exactly as they
appear in the published usage guideline's "XML Path" column, e.g.::

    /AppHdr/Fr/FIId/FinInstnId/BICFI
    /Document/FIToFICstmrCdtTrf/CdtTrfTxInf/PmtTpInf/InstrPrty

Paths are matched segment-by-segment by *local name*, so namespaces, prefixes
and wrapper tags are irrelevant. A path beginning with ``AppHdr`` is anchored at
the Business Application Header; one beginning with ``Document`` at the Document.
Any other path is treated as relative to a ``context`` element (used inside
"for each" iterations); a leading segment equal to the context's own name is
consumed so relative paths can restate the context name, matching the source
pseudo-code convention.
"""
from __future__ import annotations

from typing import List, Optional

from .loader import local_name


def _split(path: str) -> List[str]:
    return [s for s in (seg.strip() for seg in path.strip().strip("/").split("/")) if s]


def _children_named(el, name: str) -> List["object"]:
    out = []
    for child in el:
        if local_name(child) == name:
            out.append(child)
    return out


def _descend(elements: List["object"], segs: List[str]) -> List["object"]:
    current = list(elements)
    for seg in segs:
        nxt: List[object] = []
        for el in current:
            nxt.extend(_children_named(el, seg))
        current = nxt
        if not current:
            break
    return current


class ParsedMessage:
    """A parsed CBPR+ message exposing the BAH and Document for rule checks."""

    def __init__(self, tree, bah, document, message_type=None, year=None):
        self._tree = tree
        self.bah = bah
        self.document = document
        self.message_type = message_type
        self.year = year

    # -- element metadata ------------------------------------------------
    def xpath_of(self, el) -> str:
        """A readable local-name xpath, e.g. ``/Document/.../IntrBkSttlmAmt``.

        Positional ``[n]`` is added only where same-named siblings exist, so
        paths stay clean but remain unambiguous for repeated elements.
        """
        if el is None:
            return ""
        steps = []
        node = el
        while node is not None and isinstance(node.tag, str):
            name = local_name(node)
            parent = node.getparent()
            if parent is not None:
                same = [c for c in parent if local_name(c) == name]
                if len(same) > 1:
                    name = f"{name}[{same.index(node) + 1}]"
            steps.append(name)
            node = parent
        return "/" + "/".join(reversed(steps))

    def line_of(self, el) -> Optional[int]:
        if el is None:
            return None
        return getattr(el, "sourceline", None)

    @staticmethod
    def text_of(el) -> str:
        if el is None:
            return ""
        return (el.text or "").strip()

    def snippet_of(self, el, limit: int = 160) -> str:
        """A short, namespace-stripped view of the offending element.

        Leaf elements render as ``<Tag attr="v">text</Tag>``; container
        elements render as ``<Tag> containing {Child1, Child2, ...}`` so the
        user can see what the file actually has at that location.
        """
        if el is None or not isinstance(el.tag, str):
            return ""
        name = local_name(el)
        attrs = " ".join(
            f'{k.rsplit("}", 1)[-1]}="{v}"' for k, v in el.attrib.items()
        )
        head = name + (" " + attrs if attrs else "")
        children = [local_name(c) for c in el if isinstance(c.tag, str)]
        if children:
            shown = ", ".join(children[:8]) + (", ..." if len(children) > 8 else "")
            out = f"<{head}> containing {{{shown}}}"
        else:
            text = self.text_of(el)
            out = f"<{head}>{text}</{name}>"
        return out if len(out) <= limit else out[: limit - 1] + "…"

    # -- path queries ----------------------------------------------------
    def find(self, path: str, context=None) -> List["object"]:
        """Return all elements matching ``path`` (anchored or relative)."""
        segs = _split(path)
        if not segs:
            return [context] if context is not None else []
        head = segs[0]
        if head == "AppHdr" or head.startswith("BusinessApplicationHeader"):
            return _descend([self.bah], segs[1:]) if self.bah is not None else []
        if head == "Document":
            return _descend([self.document], segs[1:]) if self.document is not None else []
        # relative to context
        if context is not None:
            if local_name(context) == head:
                return _descend([context], segs[1:])
            return _descend([context], segs)
        return []

    def each(self, path: str, context=None) -> List["object"]:
        """Iteration helper - same as find(), named for "for each [path]" rules."""
        return self.find(path, context)

    def first(self, path: str, context=None):
        matches = self.find(path, context)
        return matches[0] if matches else None

    def present(self, path: str, context=None) -> bool:
        return bool(self.find(path, context))

    def absent(self, path: str, context=None) -> bool:
        return not self.present(path, context)

    def values(self, path: str, context=None) -> List[str]:
        """Stripped text content of every element matching ``path``."""
        return [self.text_of(el) for el in self.find(path, context)]

    def attr_nodes(self, path: str, attr: str, context=None):
        """(element, attribute value) for every element matching ``path``.

        Used for XML attributes such as the currency on an amount (``@Ccy``).
        """
        return [(el, el.get(attr)) for el in self.find(path, context)]

    def iter_local(self, name: str, roots=None):
        """Yield every descendant (at any depth) with local tag ``name``.

        Scans the BAH and Document by default - used by cross-cutting checks
        that apply wherever an element occurs (e.g. every PostalAddress).
        """
        if roots is None:
            roots = [r for r in (self.bah, self.document) if r is not None]
        for root in roots:
            if root is None:
                continue
            for el in root.iter():
                if local_name(el) == name:
                    yield el
