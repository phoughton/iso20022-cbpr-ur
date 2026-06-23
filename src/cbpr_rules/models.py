"""Core data models: Severity, Violation, Rule."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .message import ParsedMessage


class Severity(str, Enum):
    """How serious a finding is.

    VIOLATION - a usage rule is broken; the message is not compliant.
    INFO      - advisory guidance surfaced for awareness, not a hard breach.
    """

    VIOLATION = "violation"
    INFO = "info"


@dataclass(frozen=True)
class Violation:
    """A single rule finding against a message."""

    rule_number: str
    name: str
    description: str
    xpath: str = ""
    line: Optional[int] = None
    severity: Severity = Severity.VIOLATION
    # Why it was flagged (rule-specific) and the offending XML at that location.
    detail: str = ""
    found: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_number": self.rule_number,
            "name": self.name,
            "description": self.description,
            "detail": self.detail,
            "found": self.found,
            "xpath": self.xpath,
            "line": self.line,
            "severity": self.severity.value,
        }


# A rule check receives the parsed message and a ``report`` callback and emits
# findings by calling ``report(element, detail=None)``.
CheckFn = Callable[["ParsedMessage", Callable], None]


@dataclass
class Rule:
    """A single usage rule for one (year, message type)."""

    rule_number: str
    name: str
    description: str
    severity: Severity = Severity.VIOLATION
    # When None the rule is advisory/catalog-only: it cannot be mechanically
    # checked, so it is surfaced as guidance rather than evaluated.
    check: Optional[Callable[["ParsedMessage"], List[Violation]]] = None

    @property
    def enforced(self) -> bool:
        return self.check is not None

    def run(self, msg: "ParsedMessage") -> List[Violation]:
        if self.check is None:
            return []
        return self.check(msg)

    def to_dict(self) -> dict:
        return {
            "rule_number": self.rule_number,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "enforced": self.enforced,
        }
