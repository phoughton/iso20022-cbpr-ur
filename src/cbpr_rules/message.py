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

import re
from contextlib import contextmanager
from typing import List, Optional

from .loader import local_name

_INDEX_RE = re.compile(r"\[\d+\]")


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
        self._rec: Optional[set] = None  # active path recorder, or None

    # -- path recording (for "which fields does a rule touch?") ----------
    @contextmanager
    def record(self):
        """Within this block, collect the normalized xpaths the queries touch."""
        prev = self._rec
        self._rec = set()
        try:
            yield self._rec
        finally:
            self._rec = prev

    def _normalize(self, xpath: str) -> str:
        """Strip positional ``[n]`` and re-root at /Document or /AppHdr."""
        xpath = _INDEX_RE.sub("", xpath)
        segs = xpath.strip("/").split("/")
        for anchor in ("Document", "AppHdr"):
            if anchor in segs:
                return "/" + "/".join(segs[segs.index(anchor):])
        return xpath

    def _record_elements(self, elements, attr: Optional[str] = None) -> None:
        if self._rec is None:
            return
        for el in elements:
            if not isinstance(el.tag, str):
                continue
            path = self._normalize(self.xpath_of(el))
            self._rec.add(path + "/@" + attr if attr else path)

    def _record_intent(self, segs: List[str], context) -> None:
        """Record the intended anchored path of a query, even if it matched nothing."""
        if self._rec is None or not segs:
            return
        head = segs[0]
        if head == "AppHdr" or head.startswith("BusinessApplicationHeader"):
            anchored = "/AppHdr/" + "/".join(segs[1:])
        elif head == "Document":
            anchored = "/Document/" + "/".join(segs[1:])
        elif context is not None:
            rest = segs[1:] if local_name(context) == head else segs
            base = self._normalize(self.xpath_of(context))
            anchored = base + ("/" + "/".join(rest) if rest else "")
        else:
            return
        self._rec.add(anchored.rstrip("/"))

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
            result = _descend([self.bah], segs[1:]) if self.bah is not None else []
        elif head == "Document":
            result = _descend([self.document], segs[1:]) if self.document is not None else []
        elif context is not None:  # relative to context
            rest = segs[1:] if local_name(context) == head else segs
            result = _descend([context], rest)
        else:
            result = []
        self._record_elements(result)
        self._record_intent(segs, context)
        return result

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
        nodes = self.find(path, context)
        self._record_elements(nodes, attr=attr)
        return [(el, el.get(attr)) for el in nodes]

    def iter_local(self, name: str, roots=None):
        """Yield every descendant (at any depth) with local tag ``name``.

        Scans the BAH and Document by default - used by cross-cutting checks
        that apply wherever an element occurs (e.g. every PostalAddress).
        """
        if self._rec is not None:
            self._rec.add(f"//{name}")  # wildcard intent (dropped if concrete paths found)
        if roots is None:
            roots = [r for r in (self.bah, self.document) if r is not None]
        for root in roots:
            if root is None:
                continue
            for el in root.iter():
                if local_name(el) == name:
                    self._record_elements([el])
                    yield el

    def iter_attr(self, attr: str):
        """Yield (element, value) for every element carrying ``attr`` anywhere.

        Cross-cutting equivalent of ``attr_nodes`` for attributes like ``@Ccy``.
        """
        for root in (self.bah, self.document):
            if root is None:
                continue
            for el in root.iter():
                if isinstance(el.tag, str) and el.get(attr) is not None:
                    self._record_elements([el], attr=attr)
                    yield el, el.get(attr)
