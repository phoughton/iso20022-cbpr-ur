"""CBPR+ SR2026 usage rules for camt.052.001.08 (BankToCustomerAccountReport).

Rules and text are taken from the published usage guideline's Rules sheet; XML
paths are the short ISO 20022 tags translated from its Full_View column. The
module mirrors the reference module ``y2025/pacs_008`` - combinator-built rules
go through the local ``reg`` helper; cross-field / bespoke logic is a plain
``fn(msg, report)`` registered with ``@rule``.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import (
    is_valid_bic,
    is_valid_country,
    is_valid_currency,
)
from ...helpers import (
    amount_equals_sum,
    business_msg_id_carries_group_id,
    each_value_valid,
    header_msg_def_id_matches,
    not_matching_pattern,
    requires_if_present,
    structured_remittance_max_total,
    value_not_in,
)

MT = "camt.052"
YEAR = 2026
ROOT = "/Document/BkToCstmrAcctRpt"
RPT = ROOT + "/Rpt"
TXDTLS = RPT + "/Ntry/NtryDtls/TxDtls"
INTRST = TXDTLS + "/Intrst"
RMTINF_STRD = TXDTLS + "/RmtInf/Strd"


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


# ---------------------------------------------------------------------------
# Formal rules
# ---------------------------------------------------------------------------

@rule(MT, YEAR, "R1", "CBPR_Copy_Duplicate_FormalRule",
      "If Copy Duplicate indicator is used in the Business Application Header, "
      "it must be identical to the Copy Duplicate indicator in the business "
      "document (if the latter is present).")
def _r1(msg, report):
    bah = msg.find("/AppHdr/CpyDplct")
    doc = msg.find(RPT + "/CpyDplctInd")
    if not bah or not doc:
        return
    bah_vals = {msg.text_of(n) for n in bah}
    doc_vals = {msg.text_of(n) for n in doc}
    if bah_vals != doc_vals:
        report(bah[0], detail="BAH CopyDuplicate must equal Report CopyDuplicateIndicator")


@rule(MT, YEAR, "R2", "CBPR_BusinessMessageIdentifier_FormalRule",
      "The Business Message Identifier must match the Message Identification in "
      "the Group Header.")
def _r2(msg, report):
    bah = msg.find("/AppHdr/BizMsgIdr")
    grp = msg.find(ROOT + "/GrpHdr/MsgId")
    if not bah or not grp:
        return
    if {msg.text_of(n) for n in bah} != {msg.text_of(n) for n in grp}:
        report(bah[0], detail="BusinessMessageIdentifier must equal GroupHeader MessageIdentification")


reg("R7", "CBPR_PageNumber_FormalRule",
    "The page number must be greater than zero (>0).",
    value_not_in(RPT + "/RptPgntn/PgNb", ["0", "00", "000", "0000", "00000"]))


reg("R9", "CBPR_Party_Name_Postal_Address_FormalRule",
    "If Postal Address is present then Name is mandatory.",
    requires_if_present(RPT + "/Acct/Ownr", "PstlAdr", "Nm"))


reg("R13", "CBPR_Original_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain "
    "two consecutive slashes '//'.",
    not_matching_pattern(TXDTLS + "/Refs/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


# ---------------------------------------------------------------------------
# Algorithmic field validations (brief), for fields present in camt.052
# ---------------------------------------------------------------------------
reg("VAL-CCY", "CBPR_Valid_Balance_Currency",
    "Balance Amount currency must be a valid ISO 4217 code.",
    lambda msg, report: [
        report(el, detail=f"invalid currency '{ccy}'")
        for el, ccy in msg.attr_nodes(RPT + "/Bal/Amt", "Ccy")
        if ccy and not is_valid_currency(ccy)
    ])

reg("VAL-BIC", "CBPR_Valid_Account_Servicer_BIC",
    "Account Servicer BICFI must be a structurally valid BIC.",
    each_value_valid(RPT + "/Acct/Svcr/FinInstnId/BICFI", is_valid_bic, "BIC"))

reg("VAL-CTRY", "CBPR_Valid_Account_Owner_Country",
    "Account Owner Postal Address Country must be a valid ISO 3166 code.",
    each_value_valid(RPT + "/Acct/Ownr/PstlAdr/Ctry", is_valid_country, "Country"))


# ---------------------------------------------------------------------------
# Mechanizable textual rules promoted from advisory to enforced.
# Each promoted check is conservative (skips when inputs are absent/ambiguous),
# so a previously-valid message can never be made to fail spuriously.
# ---------------------------------------------------------------------------

# R4: BizMsgIdr must carry the underlying GroupHeader MessageIdentification.
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

# R5: MsgDefIdr must match the Document message-definition id (namespace suffix).
reg("R5", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted "
    "exactly as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

# R12 / R16: Total Interest And Tax Amount must equal the sum of record amounts.
reg("R12", "CBPR_Interest_TextualRule",
    "Total Charges And Tax Amount must equal the sum of the individual record "
    "amounts.",
    amount_equals_sum(INTRST + "/TtlIntrstAndTaxAmt", INTRST + "/Rcrd/Amt"))

reg("R16", "CBPR_Interest_TextualRule",
    "Total Charges And Tax Amount must equal the sum of the individual recode "
    "amounts",
    amount_equals_sum(INTRST + "/TtlIntrstAndTaxAmt", INTRST + "/Rcrd/Amt"))

# R17: Structured Remittance, when repeated, must not exceed 9,000 characters
# in total (excluding tags). The bilateral-agreement clause remains guidance.
reg("R17", "CBPR_Remittance_Rules_TextualRule",
    "1. Use of Structured Remittance must be bilaterally or multilaterally "
    "agreed 2. Structured Remittance can be repeated, however the total "
    "business data for all occurrences (excluding tags) must not exceed 9,000 "
    "characters.",
    structured_remittance_max_total(RMTINF_STRD, 9000))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R3": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information "
           "as in the BAH of the related message."),
    "R6": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element "
           "Business Service."),
    "R8": ("CBPR_Copy_Duplicate_Indicator_TextualRule",
           "If Applicable, for Copy or Duplicate, the electronic sequence and "
           "legal sequence must be the same as the original report."),
    "R10": ("CBPR_Intraday_Balance_Recommendation_TextualRule",
            "As increased local regulations are requesting that intraday "
            "balance positioning be provided by the account servicing "
            "institutions and not be calculated by the account owner, every "
            "camt.052 message which include Entry <Ntry> items, Intraday "
            "Booked (ITBD ) and IntraDay Available (ITAV) balances should be "
            "sent."),
    "R11": ("CBPR_Charges_TextualRule",
            "Total Charges And Tax Amount must equal the sum of the individual "
            "record amounts."),
    "R14": ("CBPR_UETR_TextualRule",
            "If the underlying transaction contains/owns a UETR then it should "
            "be reported in the camt.052 message."),
    "R15": ("CBPR_Charges_TextualRule",
            "Total Charges And Tax Amount must equal the sum of the individual "
            "recode amounts"),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
