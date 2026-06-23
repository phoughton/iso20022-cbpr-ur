"""CBPR+ SR2025 usage rules for pacs.008.001.08 (FIToFICustomerCreditTransfer).

Reference module: this is the template the other (year, message type) modules
follow. Each rule is registered explicitly with its source rule number, name and
description, and implemented either with a shared combinator from ``helpers`` or
a bespoke ``fn(msg, report)`` for cross-field / cross-schema logic.

Rule numbers and text are taken from the published usage guideline's Rules sheet;
XML paths are the short ISO 20022 tags from its Full_View / XML Path column.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    address_hybrid,
    address_lines_max_length,
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
    same_value,
)

MT = "pacs.008"
YEAR = 2025
ROOT = "/Document/FIToFICstmrCdtTrf"
TX = ROOT + "/CdtTrfTxInf"

# Repeated rule descriptions (identical across the locations they apply to).
D_AGENT_NAME_ADR = "Name and Address must always be present together."
D_PARTY_NAME_ADR = "If Postal Address is present then Name is mandatory."
D_PARTY_ANY_BIC = (
    "If AnyBIC is absent then Name is mandatory and it is recommended to also "
    "provide the Postal Address."
)
D_GRACE_STRUCT = (
    "If Postal Address is used, and if Address Line is absent, then Town Name "
    "and Country must be present."
)
D_GRACE_HYBRID = (
    "If Address Line is present and any other Postal Address element(s) are "
    "present, then Town Name and Country are mandatory."
)
D_GRACE_UNSTRUCT = (
    "If Postal Address is present and if no other element than Address Line is "
    "present then every occurrence of Address Line must not exceed 35 characters."
)


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _agent_block(prefix: str, fin_inst_path: str, n_name, n_struct, n_hybrid, n_unstruct) -> None:
    """The four rules that recur for each agent: Name+Address + grace period."""
    pstl = fin_inst_path + "/PstlAdr"
    reg(n_name, "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
        presence_together(fin_inst_path, "Nm", "PstlAdr"))
    reg(n_struct, "CBPR_GracePeriod_Structured_FormalRule", D_GRACE_STRUCT,
        required_when_absent(pstl, "AdrLine", ["TwnNm", "Ctry"]))
    reg(n_hybrid, "CBPR_GracePeriod_Hybrid_FormalRule", D_GRACE_HYBRID,
        address_hybrid(pstl))
    reg(n_unstruct, "CBPR_GracePeriod_Unstructured_FormalRule", D_GRACE_UNSTRUCT,
        address_lines_max_length(pstl, 35))


def _party_block(party_path: str, n_name_adr: str, n_struct=None, n_hybrid=None, n_unstruct=None) -> None:
    reg(n_name_adr, "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
        requires_if_present(party_path, "PstlAdr", "Nm"))
    if n_struct:
        pstl = party_path + "/PstlAdr"
        reg(n_struct, "CBPR_GracePeriod_Structured_FormalRule", D_GRACE_STRUCT,
            required_when_absent(pstl, "AdrLine", ["TwnNm", "Ctry"]))
        reg(n_hybrid, "CBPR_GracePeriod_Hybrid_FormalRule", D_GRACE_HYBRID,
            address_hybrid(pstl))
        reg(n_unstruct, "CBPR_GracePeriod_Unstructured_FormalRule", D_GRACE_UNSTRUCT,
            address_lines_max_length(pstl, 35))


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
        a_show = ", ".join(sorted(a_vals)) or "(empty)"
        b_show = ", ".join(sorted(b_vals)) or "(empty)"
        report(a_nodes[0], detail=f"{label}: {a_show} != {b_show}")


@rule(MT, YEAR, "R1", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the Payment Type Information/InstructionPriority if present.')
def _r1(msg, report):
    if msg.present("/AppHdr/Prty") and msg.present(TX + "/PmtTpInf/InstrPrty"):
        _values_match(msg, report, "/AppHdr/Prty", TX + "/PmtTpInf/InstrPrty",
                      "BAH Priority must equal InstructionPriority")


_BIC_PAIRS = [
    ("/AppHdr/Fr/FIId/FinInstnId/BICFI", TX + "/InstgAgt/FinInstnId/BICFI", "From vs Instructing Agent"),
    ("/AppHdr/To/FIId/FinInstnId/BICFI", TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent"),
]


@rule(MT, YEAR, "R2", "CBPR_From_To_Instructing_Instructed_Agent_BIC_1_FormalRule",
      'BAH "From"/"To" BIC must match Instructing/Instructed Agent BIC, except '
      "where BAH CopyDuplicate = COPY or CODU.")
def _r2(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R3", "CBPR_From_To_Instructing_Instructed_Agent_BIC_2_FormalRule",
      'BAH "From"/"To" BIC must match Instructing/Instructed Agent BIC if '
      "CopyDuplicate is absent.")
def _r3(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


# R12: agent name/address on each ChargesInformation/Agent
reg("R12", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(TX + "/ChrgsInf/Agt/FinInstnId", "Nm", "PstlAdr"))


@rule(MT, YEAR, "R13", "CBPR_Instruction_for_Creditor_Agent1_FormalRule",
      'The code "HOLD" is not allowed if the code "CHQB" is present.')
def _r13(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "CHQB" in codes and "HOLD" in codes:
            report(tx, detail="HOLD not allowed when CHQB present")


@rule(MT, YEAR, "R14", "CBPR_Instruction_for_Creditor_Agent2_FormalRule",
      'The code "TELB" is not allowed if the code "PHOB" is present.')
def _r14(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "PHOB" in codes and "TELB" in codes:
            report(tx, detail="TELB not allowed when PHOB present")


# Reimbursement agents (Group Header / Settlement Information)
_agent_block("InstgRmbrsmntAgt", ROOT + "/GrpHdr/SttlmInf/InstgRmbrsmntAgt/FinInstnId",
             "R20", "R21", "R22", "R24")
_agent_block("InstdRmbrsmntAgt", ROOT + "/GrpHdr/SttlmInf/InstdRmbrsmntAgt/FinInstnId",
             "R25", "R26", "R27", "R28")
_agent_block("ThrdRmbrsmntAgt", ROOT + "/GrpHdr/SttlmInf/ThrdRmbrsmntAgt/FinInstnId",
             "R29", "R30", "R31", "R32")


reg("R33", "CBPR_Related_Remit_Info_Remit_Info_Mutually_Exclusive_FormalRule",
    "In the interbank space, Related Remittance Information and Remittance "
    "Information are mutually exclusive and all may be absent.",
    mutually_exclusive(TX, ["RltdRmtInf", "RmtInf"]))

reg("R34", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present.",
    mutually_exclusive(TX, ["RmtInf/Ustrd", "RmtInf/Strd"]))


@rule(MT, YEAR, "R35", "CBPR_CRED_FormalRule",
      "Charge information is mandatory if CRED is present - if no charges are "
      'taken, Zero must be used in "Amount" (any agent in the payment chain).')
def _r35(msg, report):
    for tx in msg.each(TX):
        cb = msg.values("ChrgBr", tx)
        if cb and all(v == "CRED" for v in cb) and msg.absent("ChrgsInf", tx):
            report(tx, detail="ChargesInformation required when ChargeBearer is CRED")


@rule(MT, YEAR, "R36", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      "Each code can only be used once for element Instruction For Creditor Agent.")
def _r36(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


@rule(MT, YEAR, "R37", "CBPR_DEBT_FormalRule",
      'If "Charge Bearer/DEBT" is present, then only one occurrence of '
      '"Charge Information" is allowed.')
def _r37(msg, report):
    for tx in msg.each(TX):
        if "DEBT" in msg.values("ChrgBr", tx) and len(msg.find("ChrgsInf", tx)) > 1:
            report(tx, detail="only one ChargesInformation allowed when ChargeBearer is DEBT")


reg("R38", "CBPR_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R41", "CBPR_Interbank_Settlement_Currency_FormalRule",
      "The codes XAU, XAG, XPD and XPT are not allowed, as these codes are only "
      "used for commodities.")
def _r41(msg, report):
    for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy"):
        if ccy in {"XAU", "XAG", "XPD", "XPT"}:
            report(el, detail=f"commodity currency '{ccy}' not allowed")


# Charges agent + transaction-chain agents (each: name/address + grace period)
_agent_block("ChrgsInfAgt", TX + "/ChrgsInf/Agt/FinInstnId", "R12b", "R46", "R47", "R48")
_agent_block("PrvsInstgAgt1", TX + "/PrvsInstgAgt1/FinInstnId", "R49", "R50", "R51", "R52")
_agent_block("PrvsInstgAgt2", TX + "/PrvsInstgAgt2/FinInstnId", "R53", "R54", "R55", "R56")
_agent_block("PrvsInstgAgt3", TX + "/PrvsInstgAgt3/FinInstnId", "R57", "R58", "R59", "R60")
_agent_block("IntrmyAgt1", TX + "/IntrmyAgt1/FinInstnId", "R61", "R62", "R63", "R64")
_agent_block("IntrmyAgt2", TX + "/IntrmyAgt2/FinInstnId", "R65", "R66", "R67", "R68")
_agent_block("IntrmyAgt3", TX + "/IntrmyAgt3/FinInstnId", "R69", "R70", "R71", "R72")
_agent_block("DbtrAgt", TX + "/DbtrAgt/FinInstnId", "R87", "R88", "R89", "R90")
_agent_block("CdtrAgt", TX + "/CdtrAgt/FinInstnId", "R91", "R92", "R93", "R94")

# Parties
_party_block(TX + "/UltmtDbtr", "R76")
_party_block(TX + "/InitgPty", "R77")
_party_block(TX + "/Dbtr", "R82", "R84", "R85", "R86")
_party_block(TX + "/Cdtr", "R99", "R101", "R102", "R103")
_party_block(TX + "/UltmtCdtr", "R106")


def _party_any_bic(number: str, party: str) -> None:
    reg(number, "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
        required_when_absent(party, "Id/OrgId/AnyBIC", ["Nm"]))


_party_any_bic("R81", TX + "/Dbtr")
_party_any_bic("R95", TX + "/Cdtr")


def _bic_presence(number: str, party: str) -> None:
    desc = ("If AnyBIC is present, then Name and Postal Address are not allowed "
            "(other elements remain optional).")
    reg(number, "CBPR_Party_BIC_Presence_TextualRule", desc, bic_presence_exclusive(party))


_bic_presence("R83", TX + "/Dbtr")
_bic_presence("R100", TX + "/Cdtr")


# ---------------------------------------------------------------------------
# Mechanizable textual rules + algorithmic field validation
# ---------------------------------------------------------------------------
reg("R8", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.03"]))

# Promoted from advisory: mechanizable header / address / charges rules.
reg("R5", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance. It must contain the Message Identification element from "
    "the Group Header of the underlying message, where available.",
    business_msg_id_carries_group_id())

reg("R6", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance must be "
    "formatted exactly as it appears in the namespace of the Business Message.",
    header_msg_def_id_matches())

reg("R23", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances, be repeated in AddressLine.",
    no_postal_address_duplication())

# CBPR_DEBT_Rule_1: same-currency Instructed/Interbank amounts - charges are
# mandatory when the two amounts differ (prepaid charges). Conservative: only
# fires when both amounts are present in the same currency and differ.
reg("R42", "CBPR_DEBT_Rule_1_TextualRule",
    "If Instructed amount and Interbank Settlement amount are expressed in the "
    "same currency and differ, charge information is mandatory.",
    charges_required_when_amounts_differ(TX, "InstdAmt", "IntrBkSttlmAmt", "ChrgsInf"))

reg("R44", "CBPR_DEBT_Rule_1_TextualRule",
    "If Instructed amount and Interbank Settlement amount are expressed in the "
    "same currency and differ, Charge Information is mandatory.",
    charges_required_when_amounts_differ(TX, "InstdAmt", "IntrBkSttlmAmt", "ChrgsInf"))

# Specific validations required by the brief (algorithmic), applied to the
# fields where these data types appear in pacs.008.
reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R4": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, please refer to the CBPR Plus UHB."),
    "R7": ("CBPR_Business_Service_TextualRule",
           "Business Service may be used by SWIFT to support differentiated processing."),
    "R9": ("CBPR_Market_Practice_TextualRule",
           "Market Practice may be used by SWIFT on SWIFT-administered services."),
    "R10": ("CBPR_Related_Business_Application_Header_TextualRule",
            "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R11": ("CBPR_Related_BAH_Business_Service_TextualRule",
            "If related BAH is present, it should transport the element Business Service."),
    "R15": ("CBPR_Agent_National_only_TextualRule",
            "When all agents are in the same country, the clearing code only may be used."),
    "R16": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)."),
    "R17": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND postal address with minimum Town Name and Country)."),
    "R18": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND postal address with minimum Town Name and Country."),
    "R19": ("CBPR_Agent_Point_To_Point_On_SWIFT_TextualRule",
            "If the transaction is exchanged on the SWIFT network, then BIC is mandatory."),
    "R39": ("CBPR_Local_Instrument_Guideline", "The preferred option is coded information."),
    "R40": ("CBPR_Category_Purpose_Guideline", "The preferred option is coded information."),
    "R43": ("CBPR_DEBT_Rule_2_TextualRule",
            "Different-currency Instructed/Interbank amounts: if ChargeBearer/DEBT, charge information rules apply."),
    "R45": ("CBPR_SHAR_TextualRule",
            "If deduct is taken then Charge Information is mandatory."),
    "R73": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "Jurisdictional transactions: Name and/or Identification."),
    "R74": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND structured/hybrid postal address with minimum Town Name and Country."),
    "R75": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND structured/hybrid postal address with minimum Town Name and Country."),
    "R78": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "Jurisdictional transactions: Debtor Name with Account or Identification."),
    "R79": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND postal address (Unstructured / Structured / Hybrid with Town Name and Country)."),
    "R80": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R96": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
            "Jurisdictional transactions: Creditor Name with Account or Identification."),
    "R97": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R98": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND postal address (Unstructured / Structured / Hybrid with Town Name and Country)."),
    "R104": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
             "Jurisdictional transactions: Name and/or Identification."),
    "R105": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
             "Name AND structured/hybrid postal address with minimum Town Name and Country."),
    "R107": ("CBPR_Purpose_Guideline", "The preferred option is coded information."),
    "R108": ("CBPR_Remittance_Rules_TextualRule",
             "Use of Structured Remittance must be bilaterally or multilaterally agreed."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
