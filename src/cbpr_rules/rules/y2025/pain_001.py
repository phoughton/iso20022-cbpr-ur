"""CBPR+ SR2025 usage rules for pain.001.001.09 (CustomerCreditTransferInitiation).

Authored against the published usage guideline's Rules sheet. Rule numbers, names
and descriptions are taken verbatim from the sheet; XML paths are the short ISO
20022 tags from the Full_View / XML Path column. Structure mirrors the reference
module (``pacs_008``): combinator-built rules go through ``reg``/``_agent_block``/
``_party_block``; bespoke cross-field logic uses ``@rule`` directly.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_country, is_valid_currency, is_valid_lei
from ...helpers import (
    address_hybrid,
    address_lines_max_length,
    business_msg_id_carries_group_id,
    code_in,
    each_value_valid,
    header_msg_def_id_matches,
    mutually_exclusive,
    no_postal_address_duplication,
    required_when_absent,
    structured_remittance_max_total,
)

MT = "pain.001"
YEAR = 2025
ROOT = "/Document/CstmrCdtTrfInitn"
PMTINF = ROOT + "/PmtInf"
TX = PMTINF + "/CdtTrfTxInf"

# Repeated grace-period rule descriptions (identical across the locations).
D_GRACE_STRUCT = (
    "If Postal Address is used, and if Address Line is absent, then Town Name "
    "and Country must be present."
)
D_GRACE_HYBRID = (
    "If Address Line is present and any other Postal Address element(s) are "
    "present, then Town Name and Country are mandatory in Postal Address and a "
    "maximum of two occurrences of Address Line are allowed."
)
D_GRACE_UNSTRUCT = (
    "If Postal Address is present and if no other element than Address Line is "
    "present then every occurrence of Address Line must not exceed 35 characters."
)


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _grace_block(pstl_path: str, n_struct: str, n_hybrid: str, n_unstruct: str) -> None:
    """The three grace-period rules that recur for each postal address."""
    reg(n_struct, "CBPR_GracePeriod_Structured_FormalRule", D_GRACE_STRUCT,
        required_when_absent(pstl_path, "AdrLine", ["TwnNm", "Ctry"]))
    reg(n_hybrid, "CBPR_GracePeriod_Hybrid_FormalRule", D_GRACE_HYBRID,
        address_hybrid(pstl_path))
    reg(n_unstruct, "CBPR_GracePeriod_Unstructured_FormalRule", D_GRACE_UNSTRUCT,
        address_lines_max_length(pstl_path, 35))


# ---------------------------------------------------------------------------
# Formal rules
# ---------------------------------------------------------------------------
reg("R16", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present, not both "
    "together. Both may be absent.",
    mutually_exclusive(TX, ["RmtInf/Ustrd", "RmtInf/Strd"]))

# Debtor postal address (party level on Payment Information).
_grace_block(PMTINF + "/Dbtr/PstlAdr", "R23", "R24", "R25")
# Debtor Agent postal address.
_grace_block(PMTINF + "/DbtrAgt/FinInstnId/PstlAdr", "R31", "R32", "R33")
# Transaction-chain agents and parties (per CreditTransferTransactionInformation).
_grace_block(TX + "/IntrmyAgt1/FinInstnId/PstlAdr", "R46", "R47", "R48")
_grace_block(TX + "/IntrmyAgt2/FinInstnId/PstlAdr", "R50", "R51", "R52")
_grace_block(TX + "/IntrmyAgt3/FinInstnId/PstlAdr", "R53", "R54", "R55")
_grace_block(TX + "/CdtrAgt/FinInstnId/PstlAdr", "R56", "R57", "R58")
_grace_block(TX + "/Cdtr/PstlAdr", "R59", "R60", "R61")


@rule(MT, YEAR, "R64", "CBPR_Instruction_for_Creditor_Agent1_TextualRule",
      "If CHQB is present Then HOLD is not allowed Else HOLD is optional.")
def _r64(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "CHQB" in codes and "HOLD" in codes:
            report(tx, detail="HOLD not allowed when CHQB present")


@rule(MT, YEAR, "R65", "CBPR_Instruction_for_Creditor_Agent2_TextualRule",
      "If PHOB is present Then TELB is not allowed Else TELB is optional.")
def _r65(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "PHOB" in codes and "TELB" in codes:
            report(tx, detail="TELB not allowed when PHOB present")


# ---------------------------------------------------------------------------
# Mechanizable textual rule (fixed value)
# ---------------------------------------------------------------------------
reg("R5", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.03"]))

# ---------------------------------------------------------------------------
# Mechanizable rules promoted from advisory (cross-schema / cross-field).
# Each combinator is conservative: it no-ops when its inputs are absent, so a
# valid message can never be made to fail spuriously.
# ---------------------------------------------------------------------------
reg("R2", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header, as defined by "
    "the sending application or system.",
    business_msg_id_carries_group_id())

reg("R3", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted exactly "
    "as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

reg("R8", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header.",
    business_msg_id_carries_group_id())

reg("R13", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())

reg("R69", "CBPR_Structured_Remittance_Information_TextualRule",
    "Use of Structured Remittance Information must be bilaterally agreed. The "
    "total business data for all occurrences must not exceed 9,000 characters.",
    structured_remittance_max_total(TX + "/RmtInf/Strd", 9000))


# ---------------------------------------------------------------------------
# Algorithmic field validation (brief), only for fields present in pain.001.
# ---------------------------------------------------------------------------
reg("VAL-CCY", "CBPR_Valid_Instructed_Amount_Currency",
    "Instructed Amount currency must be a valid ISO 4217 code.",
    lambda msg, report: [
        report(el, detail=f"invalid currency '{ccy}'")
        for el, ccy in msg.attr_nodes(TX + "/Amt/InstdAmt", "Ccy")
        if ccy and not is_valid_currency(ccy)
    ])

reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Every Financial Institution BICFI must be a structurally valid BIC.",
    lambda msg, report: [
        report(node, detail=f"invalid BIC: '{msg.text_of(node)}'")
        for path in (
            PMTINF + "/DbtrAgt/FinInstnId/BICFI",
            TX + "/CdtrAgt/FinInstnId/BICFI",
            TX + "/IntrmyAgt1/FinInstnId/BICFI",
            TX + "/IntrmyAgt2/FinInstnId/BICFI",
            TX + "/IntrmyAgt3/FinInstnId/BICFI",
        )
        for node in msg.find(path)
        if msg.text_of(node) and not is_valid_bic(msg.text_of(node))
    ])

reg("VAL-LEI", "CBPR_Valid_LEI",
    "Every LEI must be a structurally valid ISO 17442 LEI.",
    lambda msg, report: [
        report(node, detail=f"invalid LEI: '{msg.text_of(node)}'")
        for path in (
            PMTINF + "/Dbtr/Id/OrgId/LEI",
            PMTINF + "/DbtrAgt/FinInstnId/LEI",
            TX + "/Cdtr/Id/OrgId/LEI",
            TX + "/CdtrAgt/FinInstnId/LEI",
        )
        for node in msg.find(path)
        if msg.text_of(node) and not is_valid_lei(msg.text_of(node))
    ])

reg("VAL-CTRY", "CBPR_Valid_Country",
    "Every Country must be a valid ISO 3166-1 alpha-2 code.",
    lambda msg, report: [
        report(node, detail=f"invalid country '{msg.text_of(node)}'")
        for path in (
            PMTINF + "/Dbtr/PstlAdr/Ctry",
            PMTINF + "/DbtrAgt/FinInstnId/PstlAdr/Ctry",
            TX + "/Cdtr/PstlAdr/Ctry",
            TX + "/CdtrAgt/FinInstnId/PstlAdr/Ctry",
            TX + "/IntrmyAgt1/FinInstnId/PstlAdr/Ctry",
            TX + "/IntrmyAgt2/FinInstnId/PstlAdr/Ctry",
            TX + "/IntrmyAgt3/FinInstnId/PstlAdr/Ctry",
        )
        for node in msg.find(path)
        if msg.text_of(node) and not is_valid_country(msg.text_of(node))
    ])


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R1": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, pls refer to the CBPR Plus UHB."),
    "R4": ("CBPR_Business_Service_TextualRule",
           "This field may be used by SWIFT to support differentiated processing on "
           "SWIFT-administered services such as FINplus."),
    "R6": ("CBPR_Market_Practice_TextualRule",
           "This field may be used by SWIFT on SWIFT-administered services. A "
           "user-specific value may be used, but please contact your Service Administrator."),
    "R7": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the "
           "BAH of the related message."),
    "R9": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R10": ("CGI_Message_Identification_TextualRule",
            "Forwarding Agent should respect the Message ID provided by the Initiating "
            "Party of the pain.001 and pain.002."),
    "R11": ("CGI_ISO_Date_Time_TextualRule",
            "Preferred representation is Local time with UTC offset format "
            "(YYYY-MM-DDThh:mm:ss.sss+/-hh:mm). Otherwise use UTC time format."),
    "R12": ("CBPR_Party_Name_TextualRule",
            "If Postal Address is provided, then Name is mandatory. Name without address "
            "is allowed."),
    "R14": ("CGI_Initiating_Party_Id_TextualRule",
            "Multiple IDs are allowed to support overpopulation. Can be used for "
            "dedicated bank services, e.g. reporting in the pain.002 or online authorisation."),
    "R15": ("CBPR_Forwarding_Agent_TextualRule",
            "If the Debtor Agent is not the receiver of the pain.001, the Initiating "
            "Party must populate the Forward Agent BIC."),
    "R17": ("CBPR_CHK_TextualRule",
            "Required in case of cheque relay payment."),
    "R18": ("CBPR_Payment_Type_Information_TextualRule",
            "Required on Transaction Level, unless bilaterally determined (bank value "
            "added service)."),
    "R19": ("CGI_Instruction_Priority_TextualRule",
            "Based on whether priority processing vs. normal processing is offered by the bank."),
    "R20": ("CBPR_ISO_Code_TextualRule",
            "Unless the country-specifics require a non-ISO code, preference is to provide Code."),
    "R21": ("CGI_ISO_Code_TextualRule",
            "Unless the country-specifics require a non-ISO code, preference is to provide Code."),
    "R22": ("CBPR_Party_Name_TextualRule", "Required"),
    "R26": ("CGI_Account_Currency_TextualRule", "Recommended."),
    "R27": ("CBPR_BIC_TextualRule", "Should be provided as the preferred option."),
    "R28": ("CBPR_Clearing_System_Member_Identification_TextualRule",
            "To be provided as second preference, unless BICFI, or Name and Address are "
            "provided as FI identification."),
    "R29": ("CBPR_Clearing_System_Id_TextualRule",
            "Required if Clearing System Identification is provided."),
    "R30": ("CBPR_Agent_Name_TextualRule",
            "To be provided, unless BICFI, or Member ID are provided as FI identification, "
            "and if Postal Address is used."),
    "R34": ("CBPR_Ultimate_Debtor_TextualRule",
            "Usage based on business need and bank service. If an ultimate debtor is "
            "involved in the payment, being different from the debtor, it must be provided."),
    "R35": ("CBPR_Country_Of_Residence_TextualRule",
            "Country of Residence (where the party physically lives) should be used only "
            "if different from PostalAdress/Country."),
    "R36": ("CBPR_Charge_Bearer_TextualRule",
            "Should be provided only on Transaction Level, unless bilaterally determined "
            "(bank value added service)."),
    "R37": ("CGI_Instruction_Identification_TextualRule",
            "If provided, this Id is returned to the ordering party in account statement reporting."),
    "R38": ("CBPR_Payment_Type_Information_TextualRul",
            "Required on Transaction Level, unless bilaterally determined (bank value "
            "added service)."),
    "R39": ("CBPR_Charge_Bearer_TextualRule",
            "Should be provided only on Transaction Level."),
    "R40": ("CBPR_Cheque_Number_TextualRule",
            "Required only for Customer Cheques."),
    "R41": ("CBPR_Cheque_From_TextualRule",
            "Populated only if info different from Debtor/Ultimate Debtor; assumes "
            "Ultimate Debtor takes precedence over Debtor if populated."),
    "R42": ("CBPR_Delivery_Method_TextualRule",
            "Populated to advise how cheque/draft is to be delivered."),
    "R43": ("CBPR_Deliver_To_TextualRule",
            "Populated only if info different from Creditor/Ultimate Creditor; assumes "
            "Ultimate Creditor takes precedence over Creditor if populated."),
    "R44": ("CBPR_Cheque_Maturity_Date_TextualRule",
            "If the instrument has a maturity date."),
    "R45": ("CGI_Ultimate_Debtor_TextualRule",
            "Usage based on business need and bank service. If an ultimate debtor is "
            "involved in the payment, being different from the debtor, it must be provided."),
    "R49": ("CBPR_BIC_TextualRule",
            "Recommended to be provided as the preferred option."),
    "R62": ("CBPR_CHK_Creditor_Account_TextualRule",
            "Creditor Account is not required for cheque payments."),
    "R63": ("CGI_Ultimate_Creditor_TextualRule",
            "Based on business need and bank service. If an ultimate creditor is involved "
            "in the payment, being different from the creditor, it must be provided."),
    "R66": ("CBPR_Instruction_For_Debtor_Agent_TextualRule",
            "Depending on local payment instrument and bilaterally determined bank service."),
    "R67": ("CBPR_Purpose_Guideline",
            "The preferred option is coded information."),
    "R68": ("CGI_Remittance_Location_Details_Postal_Address_TextualRule",
            "Optional, but not recommended to provide this unstructured address data "
            "(max. 1 occurrence with 70 char). If provided, it must not include Country."),
    "R70": ("CBPR_Issuer_TextualRule",
            "Value of 'ISO' reserved for ISO 11649 international creditor's reference (if "
            "used it must be bilaterally agreed)."),
    "R71": ("CBPR_Reference_TextualRule",
            "If Creditor Reference Information is used (bilateral agreement), Reference "
            "must be included."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
