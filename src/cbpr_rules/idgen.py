"""Deterministic, seedable ID generation using the Counting Strings algorithm.

Produces structurally valid identifiers (IBAN, LEI, BIC, UUID/UETR, message ids,
text) that pass this package's own validators. Pure standard library; the same
seed always yields the same output (no use of ``random`` or ``uuid``).

See ``additional_prompts/id_generation_spec.md`` for the specification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
UPPER_ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
UPPER_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(ALPHABET)
_INDEX = {c: i for i, c in enumerate(ALPHABET)}


# --------------------------------------------------------------------------- #
# Core: Counting Strings
# --------------------------------------------------------------------------- #
def counting_string(s: str) -> str:
    """Increment a base-62 counting string by one (with carry and growth)."""
    indices = [_INDEX.get(c, 0) for c in s] or [0]
    pos = len(indices) - 1
    while pos >= 0:
        indices[pos] += 1
        if indices[pos] >= _BASE:
            indices[pos] = 0
            pos -= 1
        else:
            break
    if pos < 0:
        indices.insert(0, 0)
    return "".join(ALPHABET[i] for i in indices)


def counting_sequence(seed: str, count: int) -> List[str]:
    """Return ``count`` successive counting strings starting at ``seed``."""
    out: List[str] = []
    current = seed if seed else "0"
    for _ in range(max(count, 0)):
        out.append(current)
        current = counting_string(current)
    return out


# --------------------------------------------------------------------------- #
# Seeded deterministic helpers
# --------------------------------------------------------------------------- #
def _seed_value(seed: str) -> int:
    """A large, stable non-negative integer derived from ``seed``."""
    value = 0
    for ch in (seed or "0"):
        value = value * 131 + _INDEX.get(ch, ord(ch) % _BASE) + 1
    return value


def deterministic_int(seed: str, lo: int, hi: int) -> int:
    """A stable integer in ``[lo, hi]`` derived from ``seed``."""
    if hi < lo:
        lo, hi = hi, lo
    span = hi - lo + 1
    return lo + (_seed_value(seed) % span)


def deterministic_choice(seed: str, items: Sequence) -> object:
    """Choose one item from ``items`` deterministically from ``seed``."""
    if not items:
        raise ValueError("cannot choose from an empty sequence")
    return items[deterministic_int(seed, 0, len(items) - 1)]


def deterministic_string(seed: str, length: int, charset: str = UPPER_ALNUM) -> str:
    """A stable string of ``length`` chars from ``charset``, derived from ``seed``."""
    if length <= 0:
        return ""
    if not charset:
        raise ValueError("charset must be non-empty")
    return "".join(
        charset[deterministic_int(f"{seed}:{i}", 0, len(charset) - 1)]
        for i in range(length)
    )


# --------------------------------------------------------------------------- #
# ISO 7064 mod-97 check digits (shared by IBAN and LEI)
# --------------------------------------------------------------------------- #
def _to_numeric(s: str) -> str:
    return "".join(str(ord(c) - 55) if c.isalpha() else c for c in s)


def _mod97_check_digits(body: str) -> str:
    """Two check digits so that ``body + check`` has mod-97 == 1 (ISO 7064)."""
    checksum = 98 - (int(_to_numeric(body)) % 97)
    return f"{checksum:02d}"


# --------------------------------------------------------------------------- #
# IBAN (ISO 13616)
# --------------------------------------------------------------------------- #
# (iban_length, [(segment_length, 'n'|'a'), ...]) — Greece uses GR (the spec's
# "EL" is the VAT prefix, not an ISO country code). Only structure + mod-97 is
# validated, so segment char-classes/lengths are what matter.
BBAN_SPECS = {
    "AT": (20, [(5, "n"), (11, "n")]),
    "BE": (16, [(3, "n"), (7, "n"), (2, "n")]),
    "BG": (22, [(4, "a"), (6, "n"), (8, "a")]),
    "HR": (21, [(7, "n"), (10, "n")]),
    "CY": (28, [(3, "n"), (5, "n"), (16, "a")]),
    "CZ": (24, [(4, "n"), (6, "n"), (10, "n")]),
    "DK": (18, [(4, "n"), (10, "n")]),
    "EE": (20, [(2, "n"), (2, "n"), (11, "n"), (1, "n")]),
    "FI": (18, [(6, "n"), (8, "n")]),
    "FR": (27, [(5, "n"), (5, "n"), (11, "a"), (2, "n")]),
    "DE": (22, [(8, "n"), (10, "n")]),
    "GB": (22, [(4, "a"), (6, "n"), (8, "n")]),  # not EU, but common in CBPR+ examples
    "GR": (27, [(3, "n"), (4, "n"), (16, "a")]),
    "HU": (28, [(3, "n"), (4, "n"), (1, "n"), (15, "n"), (1, "n")]),
    "IE": (22, [(4, "a"), (6, "n"), (8, "n")]),
    "IT": (27, [(1, "a"), (5, "n"), (5, "n"), (12, "a")]),
    "LV": (21, [(4, "a"), (13, "a")]),
    "LT": (20, [(5, "n"), (11, "n")]),
    "LU": (20, [(3, "n"), (13, "a")]),
    "MT": (31, [(4, "a"), (5, "n"), (18, "a")]),
    "NL": (18, [(4, "a"), (10, "n")]),
    "PL": (28, [(8, "n"), (16, "n")]),
    "PT": (25, [(4, "n"), (4, "n"), (11, "n"), (2, "n")]),
    "RO": (24, [(4, "a"), (16, "a")]),
    "SK": (24, [(4, "n"), (6, "n"), (10, "n")]),
    "SI": (19, [(5, "n"), (8, "n"), (2, "n")]),
    "ES": (24, [(4, "n"), (4, "n"), (2, "n"), (10, "n")]),
    "SE": (24, [(3, "n"), (16, "n"), (1, "n")]),
}


def iban_countries() -> List[str]:
    """Sorted list of country codes for which IBAN generation is supported."""
    return sorted(BBAN_SPECS)


def generate_iban(country: str, seed: str = "") -> str:
    """Generate a structurally valid IBAN with a correct ISO 7064 mod-97 check."""
    cc = (country or "").strip().upper()
    if cc not in BBAN_SPECS:
        raise ValueError(
            f"unsupported IBAN country '{country}'; supported: {', '.join(iban_countries())}"
        )
    _, segments = BBAN_SPECS[cc]
    bban = ""
    for i, (length, kind) in enumerate(segments):
        charset = DIGITS if kind == "n" else UPPER_ALNUM
        bban += deterministic_string(f"{seed}:{cc}:bban:{i}", length, charset)
    # ISO 13616: the check is computed over the rearranged BBAN + country + "00".
    check = _mod97_check_digits(bban + cc + "00")
    return cc + check + bban


# --------------------------------------------------------------------------- #
# LEI (ISO 17442)
# --------------------------------------------------------------------------- #
LOU_PREFIXES = [
    "529900", "549300", "213800", "254900", "969500",
    "391200", "097900", "315700", "875500", "485100",
]


def generate_lei(seed: str = "") -> str:
    """Generate a 20-char LEI with valid ISO 7064 mod-97-10 check digits."""
    prefix = deterministic_choice(f"{seed}:lou", LOU_PREFIXES)
    suffix = deterministic_string(f"{seed}:lei", 18 - len(prefix), UPPER_ALNUM)
    body = (prefix + suffix)[:18]
    return body + _mod97_check_digits(body + "00")


# --------------------------------------------------------------------------- #
# BIC (ISO 9362)
# --------------------------------------------------------------------------- #
def generate_bic(
    bank_code: Optional[str] = None,
    country: str = "GB",
    branch: str = "XXX",
    seed: str = "",
) -> str:
    """Generate a structurally valid BIC (8 or 11 chars).

    The institution code is 4 letters (this package's validator requires letters,
    not the XSD's looser alphanumeric); ``country`` must be a 2-letter code.
    """
    if bank_code:
        letters = "".join(c for c in bank_code.upper() if c.isalpha())
        bank = (letters + "XXXX")[:4]
    else:
        bank = deterministic_string(f"{seed}:bank", 4, UPPER_ALPHA)
    cc = (country or "GB").strip().upper()[:2]
    if len(cc) != 2 or not cc.isalpha():
        raise ValueError(f"invalid BIC country '{country}'")
    loc = deterministic_string(f"{seed}:loc", 2, UPPER_ALNUM)
    bic = bank + cc + loc
    if branch:
        bic += branch.upper()[:3].ljust(3, "X")
    return bic


# --------------------------------------------------------------------------- #
# UUID v4 / UETR (RFC 4122)
# --------------------------------------------------------------------------- #
def generate_uuid(counter: int = 0) -> str:
    """Deterministic RFC 4122 v4 UUID derived from an integer counter."""
    hexs = list(f"{int(counter) & ((1 << 128) - 1):032x}")
    hexs[12] = "4"  # version
    variant = (int(hexs[16], 16) & 0x3) | 0x8  # 10xx
    hexs[16] = f"{variant:x}"
    h = "".join(hexs)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def generate_uetr(counter: int = 0) -> str:
    """A UETR is exactly a UUID v4."""
    return generate_uuid(counter)


# --------------------------------------------------------------------------- #
# Message identifiers
# --------------------------------------------------------------------------- #
def generate_mid(prefix: str, country: str, counter: int) -> str:
    """``prefix + COUNTRY + zero-padded counter`` (e.g. ``CBPRGB000001``)."""
    cc = (country or "").strip().upper()[:2]
    return f"{prefix}{cc}{int(counter):06d}"


# --------------------------------------------------------------------------- #
# Date / time helpers (read the clock — not for deterministic example output)
# --------------------------------------------------------------------------- #
def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
