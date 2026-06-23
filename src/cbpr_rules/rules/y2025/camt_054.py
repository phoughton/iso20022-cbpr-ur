"""CBPR+ SR2025 usage rules for camt.054.001.08 (BankToCustomerDebitCreditNotification).

Rules and text are taken from the published usage guideline's Rules sheet; XML
paths are the short ISO 20022 tags from its XML Path column. Formal rules are
implemented with shared combinators from ``helpers`` or bespoke ``fn(msg, report)``;
mechanizable textual rules are enforced, the rest are surfaced as advisories.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    business_msg_id_carries_group_id,
    code_in,
    each_value_valid,
    header_msg_def_id_matches,
    not_matching_pattern,
)

MT = "camt.054"
YEAR = 2025
ROOT = "/Document/BkToCstmrDbtCdtNtfctn"
NTFCTN = ROOT + "/Ntfctn"
ENTRY = NTFCTN + "/Ntry"
TX = ENTRY + "/NtryDtls/TxDtls"


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


# ---------------------------------------------------------------------------
# Formal rules
# ---------------------------------------------------------------------------

@rule(MT, YEAR, "R1", "CBPR_Copy_Duplicate_FormalRule",
      "If Copy Duplicate indicator is used in the Business Application Header, it "
      "must be identical to the Copy Duplicate indicator in the business document "
      "(if the latter is present).")
def _r1(msg, report):
    bah = msg.find("/AppHdr/CpyDplct")
    doc = msg.find(NTFCTN + "/CpyDplctInd")
    if not bah or not doc:
        return
    bah_vals = {msg.text_of(n) for n in bah}
    doc_vals = {msg.text_of(n) for n in doc}
    if bah_vals != doc_vals:
        report(bah[0], detail="BAH CopyDuplicate must equal Notification/CopyDuplicateIndicator")


reg("R20", "CBPR_Original_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/Refs/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


# ---------------------------------------------------------------------------
# Mechanizable textual rules (enforced)
# ---------------------------------------------------------------------------
reg("R6", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.03"]))

reg("R3", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business Message instance "
    "being transported with this header, as defined by the sending application or system.",
    business_msg_id_carries_group_id())

reg("R4", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance must in general be "
    "formatted exactly as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())


# ---------------------------------------------------------------------------
# Algorithmic field validations (brief), only for fields present in camt.054
# ---------------------------------------------------------------------------
reg("VAL-BIC", "CBPR_Valid_Account_Servicer_BIC",
    "Account Servicer BICFI must be a structurally valid BIC.",
    each_value_valid(NTFCTN + "/Acct/Svcr/FinInstnId/BICFI", is_valid_bic, "BIC"))


# ---------------------------------------------------------------------------
# Advisory textual / guideline rules (not mechanically enforceable)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R2": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, please refer to the CBPR Plus UHB."),
    "R5": ("CBPR_Business_Service_TextualRule",
           "This field may be used by SWIFT to support differentiated processing on SWIFT-administered "
           "services such as FINplus."),
    "R7": ("CBPR_Market_Practice_TextualRule",
           "This field may be used by SWIFT on SWIFT-administered services."),
    "R8": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the "
           "related message."),
    "R9": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R10": ("CBPR_Additional_Information_TextualRule",
            "May be used to indicate type of Notification. Where used, all transactions within the "
            "message are of the same type."),
    "R11": ("CBPR_Copy_Duplicate_Indicator_TextualRule",
            "If applicable, for Copy or Duplicate, the electronic sequence and legal sequence must be "
            "the same as the original report."),
    "R12": ("CBPR_Transaction_Summary_Guideline",
            "If used, Total Credit and/or Total Debit should at a minimum be provided if summary data "
            "is available."),
    "R13": ("CBPR_Domain_Proprietary_Recommendation_TextualRule",
            "BankTransactionCode/Domain/Code is the preferred option and should be used when possible."),
    "R14": ("CBPR_Amount_TextualRule",
            "Amount in the currency of the account reported. Note: this amount can be Zero."),
    "R15": ("CBPR_Reversal_Indicator_TextualRule",
            "Value is TRUE or FALSE. Should only be shown if TRUE."),
    "R16": ("CBPR_Booking_Date_TextualRule",
            "Mandatory when Status is booked, bilaterally determined when status is Pending or Information."),
    "R17": ("CBPR_Value_Date_TextualRule",
            "Mandatory when Status is booked, bilaterally determined when status is Pending or Information."),
    "R18": ("CBPR_Account_Servicer_Reference_Guideline",
            "When the same booked entry is reported in both the camt.052 or camt.054, the Account "
            "Servicer reference should be the same as reported in camt.053."),
    "R19": ("CBPR_Charges_TextualRule",
            "Charges applied to Entry level amount only for a batch booked amount."),
    "R21": ("CBPR_UETR_TextualRule",
            "If the underlying transaction contains/owns a UETR then it should be reported in the "
            "camt.054 message."),
    "R22": ("CBPR_Date_Guideline",
            "Recommendation is to use Actual Date."),
    "R23": ("CBPR_Bank_Transaction_Code_TextualRule",
            "Bank Transaction Code must be provided at entry level and may be provided at transaction "
            "detail level."),
    "R24": ("CBPR_Charges_TextualRule",
            "Charges against the amount reported at Entry level (single, batch or aggregate amount "
            "booking)."),
    "R25": ("CBPR_Bearer_Guideline",
            "Recommended to always be provided when charges are reported."),
    "R26": ("CBPR_Initiating_Party_TextualRule",
            "Party initiating the payment to an agent."),
    "R27": ("CBPR_Debtor_TextualRule",
            "For outward payments, report if different from account owner. For inward payments, report "
            "where available. When ReversalIndicator is TRUE, the Creditor and Debtor must be the same "
            "as the Creditor and Debtor of the original entry."),
    "R28": ("CBPR_Debtor_Account_TextualRule",
            "For inward payment, report where available. Recommendation: if IBAN is available populate "
            "the IBAN tag, else populate Other."),
    "R29": ("CBPR_Ultimate_Debtor_TextualRule",
            "When ReversalIndicator is TRUE, the Ultimate Creditor and Ultimate Debtor must be the same "
            "as the Ultimate Creditor and Ultimate Debtor of the original entry."),
    "R30": ("CBPR_Creditor_TextualRule",
            "For outward payment, report where available. When ReversalIndicator is TRUE, the Creditor "
            "and Debtor must be the same as the Creditor and Debtor of the original entry."),
    "R31": ("CBPR_Creditor_Account_TextualRule",
            "For outward payment, report where available. Recommendation: if IBAN is available populate "
            "the IBAN tag, else populate Other."),
    "R32": ("CBPR_Ultimate_Creditor_TextualRule",
            "When ReversalIndicator is TRUE, the Ultimate Creditor and Ultimate Debtor must be the same "
            "as the Ultimate Creditor and Ultimate Debtor of the original entry."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
