"""CBPR+ SR2026 usage rules for camt.054.001.08 (BankToCustomerDebitCreditNotification).

Rule numbers, names and descriptions are taken from the published usage
guideline's Rules sheet; XML paths are the short ISO 20022 tags from its
Full_View / XML Path column. The module mirrors the reference module
``cbpr_rules.rules.y2025.pacs_008``: combinator-built checks are registered via
the local ``reg`` helper, cross-field / bespoke logic is written as
``fn(msg, report)`` and decorated with ``@rule``, and non-mechanizable textual
rules are surfaced via ``advisory``.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_country, is_valid_currency, is_valid_lei
from ...helpers import (
    business_msg_id_carries_group_id,
    each_value_valid,
    header_msg_def_id_matches,
    not_matching_pattern,
    value_not_in,
)

MT = "camt.054"
YEAR = 2026
ROOT = "/Document/BkToCstmrDbtCdtNtfctn"
NTFCTN = ROOT + "/Ntfctn"
ENTRY = NTFCTN + "/Ntry"


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _values_match(msg, report, path_a, path_b, label):
    a_nodes = msg.find(path_a)
    if not a_nodes:
        return
    b_vals = {msg.text_of(n) for n in msg.find(path_b)}
    if not b_vals:
        return
    a_vals = {msg.text_of(n) for n in a_nodes}
    if a_vals != b_vals:
        report(a_nodes[0], detail=label)


# ---------------------------------------------------------------------------
# Formal rules
# ---------------------------------------------------------------------------

@rule(MT, YEAR, "R1", "CBPR_Copy_Duplicate_FormalRule",
      "If Copy Duplicate indicator is used in the Business Application Header, it "
      "must be identical to the Copy Duplicate indicator in the business document "
      "(if the latter is present).")
def _r1(msg, report):
    bah = "/AppHdr/CpyDplct"
    doc = NTFCTN + "/CpyDplctInd"
    if msg.present(bah) and msg.present(doc):
        _values_match(msg, report, bah, doc,
                      "BAH CopyDuplicate must equal Notification CopyDuplicateIndicator")


@rule(MT, YEAR, "R2", "CBPR_BusinessMessageIdentifier_FormalRule",
      "The Business Message Identifier must match the Message Identification in "
      "the Group Header.")
def _r2(msg, report):
    _values_match(msg, report, "/AppHdr/BizMsgIdr", ROOT + "/GrpHdr/MsgId",
                  "BusinessMessageIdentifier must equal GroupHeader MessageIdentification")


reg("R8", "CBPR_PageNumber_FormalRule",
    "The page number must be greater than zero (>0).",
    value_not_in(NTFCTN + "/NtfctnPgntn/PgNb",
                 ["0", "00", "000", "0000", "00000"]))


@rule(MT, YEAR, "R10", "CBPR_BookingDate_ValueDate_FormalRule",
      "Either the BookingDate or the ValueDate, or both, must be present when the "
      "Status is 'BOOK'.")
def _r10(msg, report):
    for entry in msg.each(ENTRY):
        codes = msg.values("Sts/Cd", entry)
        if not codes or not all(c == "BOOK" for c in codes):
            continue
        if msg.absent("BookgDt", entry) and msg.absent("ValDt", entry):
            report(entry, detail="BookingDate or ValueDate required when Status is BOOK")


reg("R13", "CBPR_Original_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(ENTRY + "/NtryDtls/TxDtls/Refs/InstrId",
                         r"(/.*)|(.*/)|(.*//.*)"))


# ---------------------------------------------------------------------------
# Algorithmic field validation (brief-required VAL-* checks), applied to the
# fields where these data types appear in camt.054.
# ---------------------------------------------------------------------------
reg("VAL-CCY", "CBPR_Valid_Entry_Amount_Currency",
    "Entry Amount currency must be a valid ISO 4217 code.",
    lambda msg, report: [
        report(el, detail=f"invalid currency '{ccy}'")
        for el, ccy in msg.attr_nodes(ENTRY + "/Amt", "Ccy")
        if ccy and not is_valid_currency(ccy)
    ])

reg("VAL-BIC", "CBPR_Valid_Account_Servicer_BIC",
    "Account Servicer BICFI must be a structurally valid BIC.",
    each_value_valid(NTFCTN + "/Acct/Svcr/FinInstnId/BICFI", is_valid_bic, "BIC"))

reg("VAL-LEI", "CBPR_Valid_Account_Servicer_LEI",
    "Account Servicer LEI must be a structurally valid ISO 17442 LEI.",
    each_value_valid(NTFCTN + "/Acct/Svcr/FinInstnId/LEI", is_valid_lei, "LEI"))

reg("VAL-CTRY", "CBPR_Valid_Account_Servicer_Country",
    "Account Servicer postal address Country must be a valid ISO 3166 code.",
    each_value_valid(NTFCTN + "/Acct/Svcr/FinInstnId/PstlAdr/Ctry",
                     is_valid_country, "country"))


# ---------------------------------------------------------------------------
# Mechanizable textual rules promoted from advisory to enforced. Both are
# conservative cross-schema (BAH vs Document) combinators that skip when the
# BAH, Document, or the inspected element is absent.
# ---------------------------------------------------------------------------
reg("R4", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header, as defined by "
    "the sending application or system. Must contain the Message Identification "
    "element from the Group Header of the underlying message, where available "
    "(as is typically the case with pacs, pain, and camt messages, for example). "
    "If Message Identification is not available in the underlying message, then "
    "this element must contain the unique identifier of the Business Message "
    "instance.",
    business_msg_id_carries_group_id())

reg("R5", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted exactly "
    "as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R3": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as "
           "in the BAH of the related message."),
    "R6": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business "
           "Service."),
    "R7": ("CBPR_Additional_Information_TextualRule",
           "May be used to indicate type of Notification. Where this is used, all "
           "transactions within this message are of the same type. Codes are for "
           "example: /LBOX/ - Lock box /BULK/ - Bulk reporting (batch transaction "
           "with underlying transactions) /RTRN/ - Return report /CRED/ - "
           "Notification with Credit entries ONLY. /CRED/ will be provided by the "
           "Bank to the Corporate in case of Instant Payment receivable."),
    "R9": ("CBPR_Copy_Duplicate_Indicator_TextualRule",
           "If Applicable, for Copy or Duplicate, the electronic sequence and "
           "legal sequence must be the same as the original report."),
    "R11": ("CBPR_Reversal_Indicator_TextualRule",
            "Value is TRUE or FALSE. Should only be shown if TRUE."),
    "R12": ("CBPR_Charges_TextualRule",
            "Charges applied to Entry level amount only for a batch booked "
            "amount. When batch booked Entry has underlying transactions and "
            "charges are applicable, Entry level AmountDetails is used for "
            "totaling the underlying transaction amounts and charges."),
    "R14": ("CBPR_UETR_TextualRule",
            "If the underlying transaction contains/owns a UETR then it should be "
            "reported in the camt.054 message."),
    "R15": ("CBPR_Charges_TextualRule",
            "Charges against the amount reported at Entry level (single, batch or "
            "aggregate amount booking). When batch booked Entry has underlying "
            "transactions with charges, the charges will be shown against each "
            "entry detail amount."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
