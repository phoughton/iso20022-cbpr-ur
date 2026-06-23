"""CBPR+ SR2025 usage rules for camt.052.001.08 (BankToCustomerAccountReport).

Rule numbers, names and descriptions are taken from the published usage
guideline's Rules sheet; XML paths are the short ISO 20022 tags from its
Full_View / XML Path column. Formal rules are implemented with shared
combinators from ``helpers`` (or bespoke ``fn(msg, report)`` where the shape is
cross-schema); mechanizable textual rules are enforced; the remaining textual
rules are surfaced as advisory guidance. Algorithmic field validations
(VAL-*) are added for the data types that occur in this message.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_country, is_valid_currency
from ...helpers import (
    amount_equals_sum,
    business_msg_id_carries_group_id,
    each_value_valid,
    header_msg_def_id_matches,
    not_matching_pattern,
    requires_if_present,
    same_value,
)

MT = "camt.052"
YEAR = 2025
ROOT = "/Document/BkToCstmrAcctRpt"
RPT = ROOT + "/Rpt"


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


# ---------------------------------------------------------------------------
# Formal rules
# ---------------------------------------------------------------------------

reg("R1", "CBPR_Copy_Duplicate_FormalRule",
    "If Copy Duplicate indicator is used in the Business Application Header, it "
    "must be identical to the Copy Duplicate indicator in the business document "
    "(if the latter is present).",
    same_value("/AppHdr/CpyDplct", RPT + "/CpyDplctInd"))

reg("R12", "CBPR_Party_Name_Postal_Address_FormalRule",
    "If Postal Address is present then Name is mandatory.",
    requires_if_present(RPT + "/Acct/Ownr", "PstlAdr", "Nm"))

reg("R17", "CBPR_Original_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(RPT + "/Ntry/NtryDtls/TxDtls/Refs/InstrId",
                         r"(/.*)|(.*/)|(.*//.*)"))


# ---------------------------------------------------------------------------
# Mechanizable textual rule (enforced)
# ---------------------------------------------------------------------------

reg("R6", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.03" must be used.',
    lambda msg, report: [
        report(node, detail=f"BizSvc must be 'swift.cbprplus.03', found '{val}'")
        for node in msg.find("/AppHdr/BizSvc")
        for val in [msg.text_of(node)]
        if val and val != "swift.cbprplus.03"
    ])

# Header consistency between the Business Application Header and the Document.
reg("R3", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business Message "
    "instance that is being transported with this header, as defined by the sending "
    "application or system.",
    business_msg_id_carries_group_id())

reg("R4", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance must be formatted "
    "exactly as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

# Interest: total must equal the sum of the per-record amounts (Entry level).
_INTRST_TTL = RPT + "/Ntry/Intrst/TtlIntrstAndTaxAmt"
_INTRST_RCRD = RPT + "/Ntry/Intrst/Rcrd/Amt"

reg("R16", "CBPR_Interest_TextualRule",
    "Total Charges And Tax Amount must equal the sum of the individual record amounts.",
    amount_equals_sum(_INTRST_TTL, _INTRST_RCRD))

reg("R20", "CBPR_Interest_TextualRule",
    "Total Charges And Tax Amount must equal the sum of the individual record amounts.",
    amount_equals_sum(_INTRST_TTL, _INTRST_RCRD))


# ---------------------------------------------------------------------------
# Algorithmic field validation (VAL-*), only for data types present here.
# ---------------------------------------------------------------------------

# Every FinInstnId/BICFI anywhere in the report (Account Servicer + related agents)
_BIC_PATHS = (
    RPT + "/Acct/Svcr/FinInstnId/BICFI",
    RPT + "/Ntry/Chrgs/Rcrd/Agt/FinInstnId/BICFI",
    RPT + "/Ntry/NtryDtls/TxDtls/Chrgs/Rcrd/Agt/FinInstnId/BICFI",
)


def _val_bic(msg, report):
    for p in _BIC_PATHS:
        for node in msg.find(p):
            val = msg.text_of(node)
            if val and not is_valid_bic(val):
                report(node, detail=f"invalid BIC: '{val}'")


reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Every FinInstitution BICFI must be a structurally valid ISO 9362 BIC.",
    _val_bic)


def _val_ctry(msg, report):
    for node in msg.find(RPT + "/Acct/Svcr/FinInstnId/PstlAdr/Ctry"):
        val = msg.text_of(node)
        if val and not is_valid_country(val):
            report(node, detail=f"invalid country '{val}'")
    for node in msg.find(RPT + "/Acct/Ownr/PstlAdr/Ctry"):
        val = msg.text_of(node)
        if val and not is_valid_country(val):
            report(node, detail=f"invalid country '{val}'")


reg("VAL-CTRY", "CBPR_Valid_Country",
    "Every PostalAddress Country must be a valid ISO 3166 alpha-2 code.",
    _val_ctry)


def _val_ccy(msg, report):
    for p in (RPT + "/Bal/Amt", RPT + "/Ntry/Amt"):
        for el, ccy in msg.attr_nodes(p, "Ccy"):
            if ccy and not is_valid_currency(ccy):
                report(el, detail=f"invalid currency '{ccy}'")


reg("VAL-CCY", "CBPR_Valid_Amount_Currency",
    "Balance and Entry amount currency must be a valid ISO 4217 code.",
    _val_ccy)


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R2": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, pls refer to the CBPR Plus UHB."),
    "R5": ("CBPR_Business_Service_TextualRule",
           "This field may be used by SWIFT to support differentiated processing on "
           "SWIFT-administered services such as FINplus."),
    "R7": ("CBPR_Market_Practice_TextualRule",
           "This field may be used by SWIFT on SWIFT-administered services. A user-specific value "
           "may be used, but please contact your Service Administrator."),
    "R8": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of "
           "the related message."),
    "R9": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R10": ("CBPR_Electronic_Sequence_Number_TextualRule",
            "For intra-day report: sequential number of the report, assigned by the account "
            "servicer, increased incrementally by 1 for each report sent electronically."),
    "R11": ("CBPR_Copy_Duplicate_Indicator_TextualRule",
            "If applicable, for Copy or Duplicate, the electronic sequence and legal sequence "
            "must be the same as the original report."),
    "R13": ("CBPR_Intraday_Balance_Recommendation_TextualRule",
            "Every camt.052 message which includes Entry items should include Intraday Booked "
            "(ITBD) and Intraday Available (ITAV) balances."),
    "R14": ("CBPR_Domain_Proprietary_Recommendation_TextualRule",
            "BankTransactionCode/Domain/Code is the preferred option and should be used when "
            "possible."),
    "R15": ("CBPR_Charges_TextualRule",
            "Total Charges And Tax Amount must equal the sum of the individual record amounts."),
    "R18": ("CBPR_UETR_TextualRule",
            "If the underlying transaction contains/owns a UETR then it should be reported in the "
            "camt.052 message."),
    "R19": ("CBPR_Charges_TextualRule",
            "Total Charges And Tax Amount must equal the sum of the individual record amounts."),
    "R21": ("CBPR_Initiating_Party_TextualRule",
            "Party initiating the payment to an agent. In the payment context this can be the "
            "debtor, the creditor, or a party that initiates the payment on their behalf."),
    "R22": ("CBPR_Debtor_TextualRule",
            "For outward payments, report if different from account owner. For inward payments, "
            "report where available. When ReversalIndicator is TRUE, the Creditor and Debtor must "
            "be the same as the Creditor and Debtor of the original entry."),
    "R23": ("CBPR_Debtor_Account_TextualRule",
            "For inward payment, report where available. Conditional on the country regulatory "
            "requirement. If IBAN is available populate the IBAN tag, else populate Other."),
    "R24": ("CBPR_Ultimate_Debtor_TextualRule",
            "When ReversalIndicator is TRUE, the Ultimate Creditor and Ultimate Debtor must be the "
            "same as the Ultimate Creditor and Ultimate Debtor of the original entry."),
    "R25": ("CBPR_Creditor_TextualRule",
            "For outward payment, report where available. When ReversalIndicator is TRUE, the "
            "Creditor and Debtor must be the same as the Creditor and Debtor of the original entry."),
    "R26": ("CBPR_Creditor_Account_TextualRule",
            "For outward payment, report where available. If IBAN is available populate the IBAN "
            "tag, else populate Other."),
    "R27": ("CBPR_Ultimate_Creditor_TextualRule",
            "Ultimate party to which an amount of money is due. When ReversalIndicator is TRUE, "
            "the Ultimate Creditor and Ultimate Debtor must be the same as in the original entry."),
    "R28": ("CBPR_Debtor_Agent_TextualRule",
            "One of the following must be provided - BIC or Clearing System Member or Name. When "
            "ReversalIndicator is TRUE, the Creditor Agent and Debtor Agent must be the same as "
            "the Creditor Agent and Debtor Agent of the original entry."),
    "R29": ("CBPR_Creditor_Agent_TextualRule",
            "When ReversalIndicator is TRUE, the Creditor Agent and Debtor Agent must be the same "
            "as the Creditor Agent and Debtor Agent of the original entry."),
    "R30": ("CBPR_Remittance_Rules_TextualRule",
            "Use of Structured Remittance must be bilaterally or multilaterally agreed. Structured "
            "Remittance can be repeated, however the total business data for all occurrences "
            "(excluding tags) must not exceed 9,000 characters."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
