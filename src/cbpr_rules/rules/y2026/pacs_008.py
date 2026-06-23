"""CBPR+ SR2026 usage rules for pacs.008.001.08 (FIToFICustomerCreditTransfer).

Rules, numbers, names and descriptions are taken from the published SR2026 usage
guideline's Rules sheet. Formal rules are implemented with shared combinators
from ``helpers`` where they match a known shape, or a bespoke ``fn(msg, report)``
for cross-field / cross-schema logic. Non-mechanizable textual rules are
registered as advisories.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_country, is_valid_currency
from ...helpers import (
    bic_presence_exclusive,
    business_msg_id_carries_group_id,
    charges_required_when_amounts_differ,
    code_in,
    each_value_valid,
    header_msg_def_id_matches,
    mutually_exclusive,
    no_postal_address_duplication,
    not_matching_pattern,
    presence_together,
    required_when_absent,
    requires_if_present,
    structured_remittance_max_total,
)

MT = "pacs.008"
YEAR = 2026
ROOT = "/Document/FIToFICstmrCdtTrf"
TX = ROOT + "/CdtTrfTxInf"

# Repeated rule descriptions (identical across the locations they apply to).
D_AGENT_NAME_ADR = "Name and Address must always be present together."
D_PARTY_NAME_ADR = "If Postal Address is present then Name is mandatory."
D_PARTY_ANY_BIC = (
    "If AnyBIC is absent then Name is mandatory and it is recommended to also "
    "provide the Postal Address."
)


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


# ---------------------------------------------------------------------------
# Bespoke cross-field / cross-schema rules
# ---------------------------------------------------------------------------

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


@rule(MT, YEAR, "R1", "CBPR_BusinessMessageIdentifier_FormalRule",
      "The Business Message Identifier must match the Message Identification in "
      "the Group Header.")
def _r1(msg, report):
    _values_match(msg, report, "/AppHdr/BizMsgIdr", ROOT + "/GrpHdr/MsgId",
                  "BusinessMessageIdentifier must equal GroupHeader MessageIdentification")


@rule(MT, YEAR, "R2", "CBPR_To_Instructed_Agent_BIC_1_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC, except where BAH '
      "CopyDuplicate = COPY or = CODU")
def _r2(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    _values_match(msg, report, "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI", "To BIC must equal Instructed Agent BIC")


@rule(MT, YEAR, "R3", "CBPR_To_Instructed_Agent_BIC_2_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r3(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    _values_match(msg, report, "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI", "To BIC must equal Instructed Agent BIC")


@rule(MT, YEAR, "R4", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the "Payment Type Information/InstructionPriority" '
      "if present.")
def _r4(msg, report):
    if msg.present("/AppHdr/Prty") and msg.present(TX + "/PmtTpInf/InstrPrty"):
        _values_match(msg, report, "/AppHdr/Prty", TX + "/PmtTpInf/InstrPrty",
                      "BAH Priority must equal InstructionPriority")


@rule(MT, YEAR, "R5", "CBPR_From_Instructing_Agent_BIC_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC')
def _r5(msg, report):
    _values_match(msg, report, "/AppHdr/Fr/FIId/FinInstnId/BICFI",
                  TX + "/InstgAgt/FinInstnId/BICFI", "From BIC must equal Instructing Agent BIC")


@rule(MT, YEAR, "R10", "CBPR_Instruction_for_Creditor_Agent2_FormalRule",
      'The code "TELB" is not allowed if the code "PHOB" is present.')
def _r10(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "PHOB" in codes and "TELB" in codes:
            report(tx, detail="TELB not allowed when PHOB present")


@rule(MT, YEAR, "R11", "CBPR_Instruction_for_Creditor_Agent1_FormalRule",
      'The code "HOLD" is not allowed if the code "CHQB" is present.')
def _r11(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "CHQB" in codes and "HOLD" in codes:
            report(tx, detail="HOLD not allowed when CHQB present")


# R12: agent name/address on each ChargesInformation/Agent
reg("R12", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/ChrgsInf/Agt/FinInstnId", "Nm", "PstlAdr"))


reg("R13", "CBPR_GPI_ServiceLevel_Code_FormalRule",
    "The GPI ServiceLevel Code in pacs.008 must be 'G001'.",
    not_matching_pattern(TX + "/PmtTpInf/SvcLvl/Cd",
                         r"(G002|G003|G004|G005|G006|G007|G009)"))


# Reimbursement agents (Group Header / Settlement Information)
reg("R19", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(ROOT + "/GrpHdr/SttlmInf/InstgRmbrsmntAgt/FinInstnId", "Nm", "PstlAdr"))
reg("R21", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(ROOT + "/GrpHdr/SttlmInf/InstdRmbrsmntAgt/FinInstnId", "Nm", "PstlAdr"))
reg("R22", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(ROOT + "/GrpHdr/SttlmInf/ThrdRmbrsmntAgt/FinInstnId", "Nm", "PstlAdr"))


@rule(MT, YEAR, "R23", "CBPR_DEBT_FormalRule",
      'If "Charge Bearer/DEBT" is present, then only one occurrence of '
      '"Charge Information" is allowed.')
def _r23(msg, report):
    for tx in msg.each(TX):
        if "DEBT" in msg.values("ChrgBr", tx) and len(msg.find("ChrgsInf", tx)) > 1:
            report(tx, detail="only one ChargesInformation allowed when ChargeBearer is DEBT")


reg("R24", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present.",
    mutually_exclusive(TX, ["RmtInf/Ustrd", "RmtInf/Strd"]))


@rule(MT, YEAR, "R25", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      "Each code can only be used once for element Instruction For Creditor Agent.")
def _r25(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


@rule(MT, YEAR, "R26", "CBPR_CRED_FormalRule",
      "Charge information is mandatory if CRED is present – if no charges are "
      'taken, Zero must be used in "Amount" (any agent in the payment chain).')
def _r26(msg, report):
    for tx in msg.each(TX):
        cb = msg.values("ChrgBr", tx)
        if cb and all(v == "CRED" for v in cb) and msg.absent("ChrgsInf", tx):
            report(tx, detail="ChargesInformation required when ChargeBearer is CRED")


reg("R27", "CBPR_Related_Remit_Info_Remit_Info_Mutually_Exclusive_FormalRule",
    "In the interbank space, Related Remittance Information and Remittance "
    "Information are mutually exclusive and all may be absent.",
    mutually_exclusive(TX, ["RltdRmtInf", "RmtInf"]))


reg("R28", "CBPR_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain "
    "two consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R31", "CBPR_Interbank_Settlement_Currency_FormalRule",
      "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
      "only used for commodities.")
def _r31(msg, report):
    for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy"):
        if ccy in {"XAU", "XAG", "XPD", "XPT"}:
            report(el, detail=f"commodity currency '{ccy}' not allowed")


# Transaction-chain agents (each: Name and PostalAddress present together)
reg("R35", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/PrvsInstgAgt1/FinInstnId", "Nm", "PstlAdr"))
reg("R36", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/PrvsInstgAgt2/FinInstnId", "Nm", "PstlAdr"))
reg("R37", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/PrvsInstgAgt3/FinInstnId", "Nm", "PstlAdr"))
reg("R38", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/IntrmyAgt1/FinInstnId", "Nm", "PstlAdr"))
reg("R39", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/IntrmyAgt2/FinInstnId", "Nm", "PstlAdr"))
reg("R40", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/IntrmyAgt3/FinInstnId", "Nm", "PstlAdr"))
reg("R52", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/DbtrAgt/FinInstnId", "Nm", "PstlAdr"))
reg("R53", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/CdtrAgt/FinInstnId", "Nm", "PstlAdr"))

# Parties: if PostalAddress present then Name mandatory
reg("R44", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(TX + "/UltmtDbtr", "PstlAdr", "Nm"))
reg("R45", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(TX + "/InitgPty", "PstlAdr", "Nm"))
reg("R48", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(TX + "/Dbtr", "PstlAdr", "Nm"))
reg("R56", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(TX + "/Cdtr", "PstlAdr", "Nm"))
reg("R60", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(TX + "/UltmtCdtr", "PstlAdr", "Nm"))

# Parties: if AnyBIC absent then Name mandatory
reg("R50", "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
    required_when_absent(TX + "/Dbtr", "Id/OrgId/AnyBIC", ["Nm"]))
reg("R55", "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
    required_when_absent(TX + "/Cdtr", "Id/OrgId/AnyBIC", ["Nm"]))


# ---------------------------------------------------------------------------
# Mechanizable textual rules
# ---------------------------------------------------------------------------
reg("R8", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted exactly "
    "as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())


# R7: Business Message Identifier must carry the Group Header MsgId (promoted).
reg("R7", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header, as defined by "
    "the sending application or system. Must contain the Message Identification "
    "element from the Group Header of the underlying message, where available.",
    business_msg_id_carries_group_id())


# R20: structured Postal Address data must not be repeated in AddressLine (promoted).
reg("R20", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())


# R47/R54: if AnyBIC present, Name and Postal Address are not allowed (promoted).
reg("R47", "CBPR_Debtor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other "
    "elements remain optional) - However, in case of conflicting information, "
    "AnyBIC will always take precedence.",
    bic_presence_exclusive(TX + "/Dbtr"))
reg("R54", "CBPR_Creditor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other "
    "elements remain optional) - However, in case of conflicting information, "
    "AnyBIC will always take precedence.",
    bic_presence_exclusive(TX + "/Cdtr"))


# R30/R33: charges mandatory when same-currency instructed/settlement amounts
# differ (DEBT_Rule_1) (promoted).
_D_DEBT_RULE_1 = (
    "If Instructed amount and Interbank Settlement amount are expressed in the "
    "same currency: if Charge Bearer/DEBT is used then charge information is only "
    "mandatory in case of prepaid charges (that is if interbank settlement amount "
    "is higher than instructed amount) and in that case zero amount is not "
    "allowed. This rule only applies when Interbank Settlement Amount and "
    "Instructed amount are expressed in the same currency.")
reg("R30", "CBPR_DEBT_Rule_1_TextualRule", _D_DEBT_RULE_1,
    charges_required_when_amounts_differ(TX, "InstdAmt", "IntrBkSttlmAmt", "ChrgsInf"))
reg("R33", "CBPR_DEBT_Rule_1_TextualRule", _D_DEBT_RULE_1,
    charges_required_when_amounts_differ(TX, "InstdAmt", "IntrBkSttlmAmt", "ChrgsInf"))


# R29: EndToEndIdentification, if present, must be non-empty (NOTPROVIDED ok) (promoted).
@rule(MT, YEAR, "R29", "CBPR_EndToEndIdentification_TextualRule",
      'If no EndToEndIdentification is provided by the Debtor, then the element '
      'must be populated with "NOTPROVIDED".')
def _r29(msg, report):
    for node in msg.find(TX + "/PmtId/EndToEndId"):
        if not msg.text_of(node):
            report(node, detail='EndToEndIdentification must not be empty (use "NOTPROVIDED" when not provided)')


reg("R63", "CBPR_Structured_RemittanceInformation_TextualRule",
    "Structured can be repeated, however the total business data for all "
    "occurrences (excluding tags) must not exceed 9,000 characters.",
    structured_remittance_max_total(TX + "/RmtInf/Strd", 9000))


# ---------------------------------------------------------------------------
# Algorithmic field validation required by the project brief
# ---------------------------------------------------------------------------
reg("VAL-CCY", "CBPR_Valid_Settlement_Currency",
    "Interbank Settlement Amount currency must be a valid ISO 4217 code.",
    lambda msg, report: [
        report(el, detail=f"invalid currency '{ccy}'")
        for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy")
        if ccy and not is_valid_currency(ccy)
    ])

reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Every BICFI in the message must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))

reg("VAL-CTRY", "CBPR_Valid_Country",
    "Every Country code must be a valid ISO 3166 code.",
    each_value_valid(TX + "/Dbtr/PstlAdr/Ctry", is_valid_country, "Country"))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R6": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R9": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R14": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND ([Structured postal address with minimum Town Name and Country] OR [Hybrid postal address with minimum Town Name and Country]). It is recommended to also add the post code when available."),
    "R15": ("CBPR_Agent_Point_To_Point_On_SWIFT_TextualRule",
            "If the transaction is exchanged on the SWIFT network (i.e. if the sender and receiver of the message are on SWIFT), then BIC is mandatory and other elements are optional, e.g. LEI."),
    "R16": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)"),
    "R17": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same country, the clearing code only may be used."),
    "R18": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND ([Structured postal address with minimum Town Name and Country] OR [Hybrid postal address with minimum Town Name and Country]). It is recommended to also add the post code when available."),
    "R32": ("CBPR_DEBT_Rule_2_TextualRule",
            "If Instructed amount and Interbank Settlement amount are not expressed in the same currency: If Charge Bearer/DEBT is used then charge information is only mandatory in case of prepaid charges (that is if interbank settlement amount is higher than instructed amount WHEN converted in the same currency) and in that case zero amount is not allowed. Otherwise Charge information is optional (both Agent and currency always need to be provided)."),
    "R34": ("CBPR_SHAR_TextualRule",
            "If deduct taken then Charge Information is mandatory. It is optional for initiator (not taking deduct)."),
    "R41": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) (that is within a country or for regions under same legislations). The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R42": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)]"),
    "R43": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country- it is recommended to add Post code when available] AND (Identification: Private or Organisation)"),
    "R46": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Debtor/ Name is mandatory with either Debtor Account OR Debtor Identification. The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R49": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)"),
    "R51": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country (+ recommended to add Post code when available)] OR [Hybrid postal address with minimum Town Name and Country (+ recommended to add Post code when available)] AND (Account Number OR Identification: Private or Organisation)"),
    "R57": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)"),
    "R58": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR Creditor Identification. The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R59": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country (+ recommended to add Post code when available)] OR [Hybrid postal address with minimum Town Name and Country (+ recommended to add Post code when available)) AND (Account Number OR Identification: Private or Organisation)"),
    "R61": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) (that is within a country or for regions under same legislations). The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R62": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)]. Other elements are optional, eg Identification: Private or Organisation)"),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
