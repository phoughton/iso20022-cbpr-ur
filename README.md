# cbpr-usage-rules

Validate **ISO 20022 CBPR+** XML messages (the SWIFT cross-border payments
profile) against the **Usage / Business Rules** that apply on top of the XSD
schemas. These are the rules that the schema alone cannot express: cross-field
constraints, cross-schema checks between the Business Application Header (BAH)
and the message Document, conditional presence, code-list restrictions, and
field-format algorithms (IBAN, LEI, BIC, country, currency).

Rules are versioned per year (currently **2025** and **2026**) and organised by
message type (pacs.008, pacs.009 and its COV/ADV variants, pacs.002, pacs.004,
pain.001, camt.052, camt.054, and the STP variants).

> **This package is AI generated.** The rule logic was derived, with review,
> from the published CBPR+ usage-guideline spreadsheets. Treat it as an aid, not
> as a substitute for the official SWIFT specifications. Verify against the
> source material before relying on results in production.

---

## Installation

```bash
pip install cbpr-usage-rules
```

Requires Python 3.9+ and depends only on `lxml`.

---

## Quick start

### As a library

```python
import cbpr_rules

result = cbpr_rules.validate_file("payment.xml", year=2025)

if result["valid"]:
    print("Compliant")
else:
    for v in result["violations"]:
        print(f"{v['rule_number']}  line {v['line']}  {v['xpath']}")
        print(f"    {v['description']}")
```

`validate_string` is the same but takes XML text:

```python
result = cbpr_rules.validate_string(xml_text, year=2026)
```

### From the command line

```bash
# Human-readable (default). Exit code is non-zero if there are violations.
cbpr-validate payment.xml --year 2025

# JSON output
cbpr-validate payment.xml --year 2025 --json

# Read from stdin
cat payment.xml | cbpr-validate --year 2026

# Also list the advisory (non-enforced) rules in full
cbpr-validate payment.xml --year 2025 --advisory

# Additionally schema-validate against an XSD (repeatable, results shown separately)
cbpr-validate payment.xml --year 2025 --xsd pacs.008.001.08.xsd
```

Each reported violation shows the rule, **why** this instance failed (`Problem:`),
the **offending XML** from your file (`Found:`), and its line + xpath (`At:`).
Advisory rules are summarised as a count by default; pass `--advisory` to list them.

---

## The result object

Both `validate_file` and `validate_string` return a dictionary:

```python
{
  "valid": False,                     # True only if there are no VIOLATION-severity findings
  "message_type": "pacs.008",         # the rule set that was applied
  "detected_message_type": "pacs.008",# auto-detected from the Document namespace
  "year": 2025,
  "rules_evaluated": 86,
  "violations": [
    {
      "rule_number": "pacs.008:R41",   # unique within the message type
      "name": "CBPR_Interbank_Settlement_Currency_FormalRule",
      "description": "The codes XAU, XAG, XPD and XPT are not allowed ...",
      "detail": "commodity currency 'XAU' not allowed",  # why this instance was flagged
      "found": "<IntrBkSttlmAmt Ccy=\"XAU\">1000.00</IntrBkSttlmAmt>",  # the offending XML
      "xpath": "/RequestPayload/Document/FIToFICstmrCdtTrf/CdtTrfTxInf/IntrBkSttlmAmt",
      "line": 39,                      # 1-based line in the source XML
      "severity": "violation"
    }
  ],
  "advisory": [                        # textual guidance that cannot be mechanically enforced
    {"rule_number": "pacs.008:R4", "name": "...", "description": "..."}
  ]
}
```

Every violation carries the four required pieces of information: the **xpath**,
the **line number**, a **description**, and a **unique rule number**.

---

## Mid-level usage

### Choosing the year

Pass `year=2025` or `year=2026`. Rule loading is per-year and lazy — only the
requested year's modules are imported. You can validate against more than one
year in the same process simply by calling with different `year` values.

### Message type detection and variants

The message type is auto-detected from the `<Document>` namespace, so you
normally don't pass it. Business variants that share a base namespace — **STP**
(pacs.008/pacs.009), **COV** and **ADV** (pacs.009) — cannot be told apart from
the XML alone, so select them explicitly when you want their stricter rule sets:

```python
cbpr_rules.validate_file("cover.xml", year=2025, msgtype="pacs.009_cov")
```

```bash
cbpr-validate cover.xml --year 2025 --type pacs.009_cov
```

### Wrapper tags

Messages arrive inside different envelopes (`<RequestPayload>`, `<DataPDU>`,
SWIFT SAA wrappers, and so on). The validator locates the `AppHdr` and
`Document` elements wherever they sit in the tree and ignores the surrounding
wrapper, so the same input validates identically regardless of envelope. Element
matching is by local name, so namespace prefixes never matter.

### Severity

- `violation` — a usage rule is broken; this makes `valid` false.
- `info` — advisory guidance surfaced for awareness; it never fails validation
  and appears in the separate `advisory` list (textual rules that cannot be
  mechanically checked).

---

## In-depth usage

### Discovering the rule set

```python
cbpr_rules.available(2025)              # -> ['camt.052', 'pacs.008', ...]
cbpr_rules.list_rules(2025, "pacs.008") # -> [{rule_number, name, description, severity, enforced}, ...]
```

```bash
cbpr-validate --year 2025 --list-types
cbpr-validate --year 2025 --type pacs.008 --list
```

### Algorithmic field validation

Beyond the published rules, the following formats are validated with their
standard algorithms wherever the corresponding fields appear:

| Field    | Standard            | Check                                   |
|----------|---------------------|-----------------------------------------|
| IBAN     | ISO 13616           | structure + mod-97 check digits         |
| LEI      | ISO 17442           | structure + ISO 7064 mod-97-10 check    |
| BIC      | ISO 9362            | 8/11-char structure + valid country     |
| Country  | ISO 3166-1 alpha-2  | membership                              |
| Currency | ISO 4217            | membership                              |

The reference code lists are vendored, so validation never makes a network call.

Some of these check-digit algorithms and reference code lists were derived from
Wikipedia (e.g. [IBAN](https://en.wikipedia.org/wiki/International_Bank_Account_Number),
[LEI](https://en.wikipedia.org/wiki/Legal_Entity_Identifier), and the
[ISO 3166 country codes](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes)).
Verify against the authoritative ISO/registry sources before relying on them in
production.

### Optional XSD schema validation

You can additionally validate a message against one or more **XSD schemas** as a
*separate* second result set. XSD files are **not** bundled with the package —
supply your own path(s):

```python
result = cbpr_rules.validate_file("payment.xml", year=2025, xsd="pacs.008.001.08.xsd")
# or several:  xsd=["head.001.001.02.xsd", "pacs.008.001.08.xsd"]
```

```bash
cbpr-validate payment.xml --year 2025 --xsd pacs.008.001.08.xsd
```

Each XSD is auto-matched by its `targetNamespace`: a message schema validates the
`Document`, a head.001 schema validates the `AppHdr`. When (and only when) an XSD
is supplied, the result gains a separate top-level `xsd` block, and the CLI prints
a distinct **XSD SCHEMA VALIDATION** section:

```python
"xsd": {
  "checked": True,
  "schema_valid": False,                 # all supplied schemas passed?
  "schemas": [
    {
      "file": "pacs.008.001.08.xsd",
      "target_namespace": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
      "validated_element": "Document",   # or "AppHdr" / "root"
      "valid": False,
      "errors": [{"message": "...", "line": 82, "xpath": "/Document/.../CdtrAgt"}]
    }
  ]
}
```

Usage-rule results and schema results stay separate: the top-level `valid` reflects
only the usage rules, while schema validity is `xsd.schema_valid`. The **CLI exit
code is non-zero if either** the usage rules or the schema fail. With no `--xsd`,
nothing about XSD appears in the output.

### Handling errors

`validate_file` / `validate_string` raise `cbpr_rules.engine.ValidationError`
for unparseable XML or when the message type cannot be determined and was not
supplied. The CLI turns these into a message on stderr and exit code 2.

### CLI exit codes

| Code | Meaning                          |
|------|----------------------------------|
| 0    | Valid (no violations)            |
| 1    | Invalid (one or more violations) |
| 2    | Usage error / could not validate |

---

## How the rules are organised

Each `(year, message type)` has a hand-authored Python module under
`cbpr_rules/rules/y<year>/`. Rules are built from a small library of reusable
combinators (presence, conditional presence, mutual exclusion, value matching,
length, code lists, address grace-period rules) plus bespoke functions for
cross-field and cross-schema logic. The XSD files in the source material are
informational only and are not reimplemented here.

### Enforced vs advisory

Every published rule is registered. A rule is **enforced** (can produce a
violation) when it can be checked deterministically from the message alone —
this includes the formal pseudo-code rules and the mechanizable textual rules,
such as:

- header ↔ message consistency (`MsgDefIdr` matches the Document definition;
  `BizMsgIdr` carries the GroupHeader `MsgId`);
- no structured Postal Address value duplicated in an `AddressLine`;
- `AnyBIC` present ⇒ `Name`/`PostalAddress` not allowed;
- Structured Remittance ≤ 9,000 characters;
- charge rules where instructed and settlement amounts share a currency and
  differ, and amount-total-equals-sum checks.

A rule stays **advisory** (`severity: info`, surfaced as guidance, never failing
validation) when it cannot be verified from the message in isolation — for
example anything that refers to a *related or underlying message* not present
(`Original_*`, related-BAH, COV/ADV UETR/E2E), depends on the SWIFT network or a
jurisdiction, or expresses a recommendation / bilaterally-agreed practice.
Checks are deliberately **conservative**: each skips when its inputs are absent
or ambiguous, so a compliant message is never failed spuriously.

## Licence

MIT — see [LICENSE](LICENSE).
