# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
