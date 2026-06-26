# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0]

### Added
- Deterministic **ID generation** library (`cbpr_rules.idgen`, "Counting Strings"
  algorithm — no `random`/`uuid`): `generate_iban`, `generate_lei`, `generate_bic`,
  `generate_uuid`/`generate_uetr`, `generate_mid`, plus `counting_string`/
  `counting_sequence` and seeded helpers. Every id is structurally valid and passes
  the package's own validators; same seed → same output. New CLI
  `cbpr-validate --generate {iban,lei,bic,uuid,uetr,mid,text}` (with
  `--seed/--country/--bank/--branch/--count`). The bundled example messages now
  source their identifiers from this library (seeded per example).

## [0.4.0]

### Added
- List only the **enforceable** rules for a year + message type:
  `list_rules(year, msgtype, enforced_only=True)` in the API and
  `cbpr-validate --enforced --year … --type …` on the CLI (advisory rules omitted;
  composes with `--json`).

## [0.3.0]

### Added
- Bundled **example messages**: a minimum and a maximum variant for every
  supported message type, each pre-verified to pass the usage rules and the
  CBPR+ XSDs. New API `example_message(year, msgtype, variant="max",
  wrapper="Envelope")` and `example_variants(year, msgtype)`, and CLI
  `--example {min,max}` (with `--wrapper TAG`). Data is fictitious/anonymised.

## [0.2.0]

### Added
- `--format {text,compact,json}` CLI option. The new `compact` format prints one
  finding per line, compiler/linter-style (`file:line: severity [rule] message | at
  xpath`) with a stable `VALID:`/`INVALID:` summary line — easy for tools and coding
  agents to parse. `--json` is now an alias for `--format json`; the default rich
  text output is unchanged.

## [0.1.3]

### Changed
- Country (`VAL-CTRY`) and currency (`VAL-CCY`) validation are now single universal
  rules, like IBAN/LEI. `VAL-CTRY` checks every `<Ctry>` element; `VAL-CCY` checks
  every `Ccy` attribute and `<Ccy>` element, document-wide, for all message types.
  This closes gaps where country was unvalidated (e.g. pacs.008 2025, the pacs.009
  family) and currency was unvalidated (pacs.002 2025), and replaces the ~13
  per-module `VAL-CTRY` and ~19 per-module `VAL-CCY` rules.

## [0.1.2]

### Changed
- LEI validation is now a single universal `VAL-LEI` rule (every `<LEI>` element,
  all message types), replacing the per-module `VAL-LEI` checks that were missing
  for several message types (e.g. pacs.008 2025) and scoped to specific party
  paths where present. Malformed LEIs in any party position are now caught
  consistently. `VAL-IBAN` and `VAL-LEI` share one document-wide implementation.

## [0.1.1]

### Fixed
- IBAN values are now actually validated. The `is_valid_iban` algorithm existed
  but was wired into no rule, so malformed IBANs passed silently. A universal
  `VAL-IBAN` check now validates every `<IBAN>` element (mod-97 / ISO 7064)
  across all message types.

### Added
- Initial package: validation engine, wrapper-tolerant loader, public API
  (`validate_file`, `validate_string`, `list_rules`, `available`), and the
  `cbpr-validate` CLI (text + JSON output).
- Algorithmic validators: IBAN, LEI, BIC, ISO 3166-1 country, ISO 4217 currency.
- CBPR+ SR2025 / SR2026 usage rules per message type.
- Violations report `detail` (why this instance failed) and `found` (the
  offending XML); the CLI wraps output and summarises advisory rules unless
  `--advisory` is passed.
- Promoted mechanizable textual rules from advisory to enforced: header↔message
  consistency (`MsgDefIdr`, `BizMsgIdr`), Postal Address / AddressLine
  duplication, `AnyBIC` presence exclusivity, Structured Remittance length, and
  conditional charge / amount-sum checks. Contextual rules (referring to a
  related/underlying message, network, jurisdiction, or recommendation) remain
  advisory.
- Optional XSD schema validation: pass `xsd=` (a path or list) to
  `validate_file`/`validate_string`, or `--xsd PATH` (repeatable) on the CLI. XSDs
  are auto-matched to the Document or AppHdr by `targetNamespace` and reported in a
  separate `xsd` result block / CLI section. XSD files are not bundled. The CLI
  exit code is non-zero on usage-rule OR schema failure.
