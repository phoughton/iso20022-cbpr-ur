"""Rule registry and the ``@rule`` / ``advisory`` authoring helpers.

Rule modules live under ``cbpr_rules.rules.y<year>.<msgtype>`` and register their
rules at import time via the decorators below. ``load_rules`` imports the right
module on demand and returns the rules for a (year, message type).
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, Dict, List, Tuple

from .models import Rule, Severity, Violation
from .validators import is_valid_iban

# (year, message_type) -> list[Rule]
_REGISTRY: Dict[Tuple[int, str], List[Rule]] = {}
_LOADED: set = set()
# module name -> import error message, for modules that failed to load
IMPORT_ERRORS: Dict[str, str] = {}


def _key(year: int, msgtype: str) -> Tuple[int, str]:
    return (int(year), msgtype)


def register(year: int, msgtype: str, rule: Rule) -> None:
    _REGISTRY.setdefault(_key(year, msgtype), []).append(rule)


def rule(
    msgtype: str,
    year: int,
    number: str,
    name: str,
    description: str,
    severity: Severity = Severity.VIOLATION,
) -> Callable:
    """Decorate a ``fn(msg, report)`` checker and register it.

    The wrapped function receives the ParsedMessage and a ``report`` callback.
    Call ``report(element, detail=None)`` for each finding; the element supplies
    the xpath and line number, and the rule supplies number/name/description.
    """
    rule_id = f"{msgtype}:{number}"

    def decorator(fn: Callable) -> Callable:
        def check(msg) -> List[Violation]:
            findings: List[Violation] = []

            def report(element=None, detail=None, severity_override=None):
                findings.append(
                    Violation(
                        rule_number=rule_id,
                        name=name,
                        description=description,
                        detail=detail or "",
                        found=msg.snippet_of(element) if element is not None else "",
                        xpath=msg.xpath_of(element) if element is not None else "",
                        line=msg.line_of(element) if element is not None else None,
                        severity=severity_override or severity,
                    )
                )

            fn(msg, report)
            return findings

        register(year, msgtype, Rule(rule_id, name, description, severity, check))
        return fn

    return decorator


def advisory(msgtype: str, year: int, number: str, name: str, description: str) -> None:
    """Register an advisory (non-mechanizable) rule, surfaced as guidance only."""
    rule_id = f"{msgtype}:{number}"
    register(year, msgtype, Rule(rule_id, name, description, Severity.INFO, check=None))


def _discover(year: int) -> None:
    """Import every rule module for a year so its rules register."""
    if year in _LOADED:
        return
    pkg_name = f"{__package__}.rules.y{year}"
    try:
        pkg = importlib.import_module(pkg_name)
    except ModuleNotFoundError:
        _LOADED.add(year)
        return
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_"):
            continue
        full = f"{pkg_name}.{mod.name}"
        try:
            importlib.import_module(full)
        except Exception as exc:  # a broken rule module must not break the rest
            IMPORT_ERRORS[full] = f"{type(exc).__name__}: {exc}"
    _LOADED.add(year)


_IBAN_DESC = "Every IBAN must be structurally valid and pass the ISO 7064 mod-97 check."


def _universal_rules(msgtype: str) -> List[Rule]:
    """Cross-cutting value validations applied to every message type.

    In ISO 20022 the ``<IBAN>`` element is always the self-validating
    ``IBAN2007Identifier`` datatype, so any IBAN anywhere in a message - Debtor,
    Creditor, Agent or Intermediary account - must pass the mod-97 check. A
    single document-wide scan therefore covers all message types correctly.
    """
    rule_id = f"{msgtype}:VAL-IBAN"

    def check(msg) -> List[Violation]:
        out: List[Violation] = []
        for el in msg.iter_local("IBAN"):
            val = msg.text_of(el)
            if val and not is_valid_iban(val):
                out.append(
                    Violation(
                        rule_number=rule_id,
                        name="CBPR_Valid_IBAN",
                        description=_IBAN_DESC,
                        detail=f"invalid IBAN: '{val}'",
                        found=msg.snippet_of(el),
                        xpath=msg.xpath_of(el),
                        line=msg.line_of(el),
                    )
                )
        return out

    return [Rule(rule_id, "CBPR_Valid_IBAN", _IBAN_DESC, Severity.VIOLATION, check)]


def load_rules(year: int, msgtype: str) -> List[Rule]:
    _discover(int(year))
    rules = list(_REGISTRY.get(_key(year, msgtype), []))
    rules.extend(_universal_rules(msgtype))
    return rules


def available_message_types(year: int) -> List[str]:
    _discover(int(year))
    return sorted({mt for (yr, mt) in _REGISTRY if yr == int(year)})
