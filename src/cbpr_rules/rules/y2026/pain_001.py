"""CBPR+ SR2026 usage rules for pain.001.001.09 (CustomerCreditTransferInitiation).

Authored against the published CBPR+ SR2026 usage guideline's Rules sheet.
Structure mirrors the reference module ``y2025/pacs_008``: a local ``reg`` helper
registers combinator-built checks, recurring agent/party shapes are factored into
small helpers, and cross-field / cross-schema logic is written as bespoke
``fn(msg, report)`` checks. XML paths are the short ISO 20022 tags.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    business_msg_id_carries_group_id,
    header_msg_def_id_matches,
    mutually_exclusive,
    no_postal_address_duplication,
    presence_together,
    requires_if_present,
    structured_remittance_max_total,
)

MT = "pain.001"
YEAR = 2026
ROOT = "/Document/CstmrCdtTrfInitn"
GRPHDR = ROOT + "/GrpHdr"
PMTINF = ROOT + "/PmtInf"
TX = PMTINF + "/CdtTrfTxInf"

# Repeated rule descriptions (identical across the locations they apply to).
D_AGENT_NAME_ADR = "Name and Address must always be present together."
D_PARTY_NAME_ADR = "If Postal Address is present then Name is mandatory."


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _agent_name_addr(number: str, fin_inst_path: str) -> None:
    """Agent FinInstnId: Name and PostalAddress present together."""
    reg(number, "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
        presence_together(fin_inst_path, "Nm", "PstlAdr"))


def _party_name_addr(number: str, party_path: str) -> None:
    """Party: if PostalAddress present then Name mandatory."""
    reg(number, "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
        requires_if_present(party_path, "PstlAdr", "Nm"))


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
    _values_match(msg, report, "/AppHdr/BizMsgIdr", GRPHDR + "/MsgId",
                  "BAH BusinessMessageIdentifier must equal GroupHeader MessageIdentification")


@rule(MT, YEAR, "R6", "CBPR_Instruction_for_Creditor_Agent1_FormalRule",
      'The code "HOLD" is not allowed if the code "CHQB" is present.')
def _r6(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "CHQB" in codes and "HOLD" in codes:
            report(tx, detail="HOLD not allowed when CHQB present")


@rule(MT, YEAR, "R7", "CBPR_Instruction_for_Creditor_Agent2_FormalRule",
      'The code "TELB" is not allowed if the code "PHOB" is present.')
def _r7(msg, report):
    for tx in msg.each(TX):
        codes = set(msg.values("InstrForCdtrAgt/Cd", tx))
        if "PHOB" in codes and "TELB" in codes:
            report(tx, detail="TELB not allowed when PHOB present")


@rule(MT, YEAR, "R8", "CBPR_MessageIdentification_PaymentInformationIdentification_FormalRule",
      "The Payment Information Identification must be the same as the Message "
      "Identification in the Group Header.")
def _r8(msg, report):
    msg_id_vals = {msg.text_of(n) for n in msg.find(GRPHDR + "/MsgId")}
    if not msg_id_vals:
        return
    for pmt in msg.each(PMTINF):
        for pid in msg.find("PmtInfId", pmt):
            if msg.text_of(pid) not in msg_id_vals:
                report(pid, detail="PaymentInformationIdentification must equal GroupHeader MessageIdentification")


# R10: InitiatingParty (Group Header)
_party_name_addr("R10", GRPHDR + "/InitgPty")

reg("R12", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present, not both "
    "together. Both may be absent.",
    mutually_exclusive(TX, ["RmtInf/Ustrd", "RmtInf/Strd"]))

# R13: Debtor (Payment Information)
_party_name_addr("R13", PMTINF + "/Dbtr")

# R15: DebtorAgent
_agent_name_addr("R15", PMTINF + "/DbtrAgt/FinInstnId")

# R18: UltimateDebtor (Payment Information)
_party_name_addr("R18", PMTINF + "/UltmtDbtr")


@rule(MT, YEAR, "R20", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      "Each code can only be used once for element Instruction For Creditor Agent.")
def _r20(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


# R22: UltimateDebtor (Transaction)
_party_name_addr("R22", TX + "/UltmtDbtr")

# R24-R26: Intermediary Agents 1/2/3
_agent_name_addr("R24", TX + "/IntrmyAgt1/FinInstnId")
_agent_name_addr("R25", TX + "/IntrmyAgt2/FinInstnId")
_agent_name_addr("R26", TX + "/IntrmyAgt3/FinInstnId")

# R27: CreditorAgent
_agent_name_addr("R27", TX + "/CdtrAgt/FinInstnId")

# R28: Creditor
_party_name_addr("R28", TX + "/Cdtr")

# R30: UltimateCreditor (Transaction)
_party_name_addr("R30", TX + "/UltmtCdtr")

# R32-R35: Structured remittance parties
_party_name_addr("R32", TX + "/RmtInf/Strd/Invcr")
_party_name_addr("R33", TX + "/RmtInf/Strd/Invcee")
_party_name_addr("R34", TX + "/RmtInf/Strd/GrnshmtRmt/Grnshee")
_party_name_addr("R35", TX + "/RmtInf/Strd/GrnshmtRmt/GrnshmtAdmstr")


# ---------------------------------------------------------------------------
# Algorithmic field validations (project brief) - only for fields present here
# ---------------------------------------------------------------------------
_BICFI_PATHS = [
    GRPHDR + "/FwdgAgt/FinInstnId/BICFI",
    PMTINF + "/DbtrAgt/FinInstnId/BICFI",
    PMTINF + "/ChrgsAcctAgt/FinInstnId/BICFI",
    TX + "/IntrmyAgt1/FinInstnId/BICFI",
    TX + "/IntrmyAgt2/FinInstnId/BICFI",
    TX + "/IntrmyAgt3/FinInstnId/BICFI",
    TX + "/CdtrAgt/FinInstnId/BICFI",
]

_CTRY_PATHS = [
    PMTINF + "/UltmtDbtr/PstlAdr/Ctry",
    PMTINF + "/Dbtr/PstlAdr/Ctry",
    PMTINF + "/DbtrAgt/FinInstnId/PstlAdr/Ctry",
    TX + "/UltmtDbtr/PstlAdr/Ctry",
    TX + "/IntrmyAgt1/FinInstnId/PstlAdr/Ctry",
    TX + "/IntrmyAgt2/FinInstnId/PstlAdr/Ctry",
    TX + "/IntrmyAgt3/FinInstnId/PstlAdr/Ctry",
    TX + "/CdtrAgt/FinInstnId/PstlAdr/Ctry",
    TX + "/Cdtr/PstlAdr/Ctry",
    TX + "/UltmtCdtr/PstlAdr/Ctry",
]


@rule(MT, YEAR, "VAL-BIC", "CBPR_Valid_Agent_BIC",
      "Every Financial Institution BICFI must be a structurally valid BIC.")
def _val_bic(msg, report):
    for path in _BICFI_PATHS:
        for node in msg.find(path):
            val = msg.text_of(node)
            if val and not is_valid_bic(val):
                report(node, detail=f"invalid BIC: '{val}'")


# ---------------------------------------------------------------------------
# Promoted from advisory: mechanizable header / address / remittance rules.
# Each combinator is conservative: it skips when its inputs are absent or
# ambiguous, so a previously-valid message can never be made to fail spuriously.
# ---------------------------------------------------------------------------
reg("R3", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header. It must contain "
    "the Message Identification element from the Group Header of the underlying "
    "message, where available (as is typically the case with pain messages).",
    business_msg_id_carries_group_id())

reg("R4", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance must be "
    "formatted exactly as it appears in the namespace of the Business Message "
    "instance.",
    header_msg_def_id_matches())

reg("R11", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances, be repeated in AddressLine.",
    no_postal_address_duplication())

reg("R31", "CBPR_Structured_RemittanceInformation_TextualRule",
    "Structured can be repeated, however the total business data for all "
    "occurrences (excluding tags) must not exceed 9,000 characters.",
    structured_remittance_max_total(TX + "/RmtInf/Strd", 9000))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R2": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R5": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R9": ("CBPR_Message_Identification_TextualRule",
           "Forwarding Agent should respect the Message ID provided by the Initiating Party of the pain.001 and pain.002."),
    "R14": ("CBPR_Account_Currency_TextualRule",
            "Recommended."),
    "R16": ("CBPR_Clearing_System_Member_Identification_TextualRule",
            "To be provided as second preference, unless BICFI, or Name and Address are provided as FI identification."),
    "R17": ("CBPR_Ultimate_Debtor_TextualRule",
            "Usage based on business need and bank service. If an ultimate debtor is involved in the payment, being "
            "different from the debtor, it must be provided. Required on Transaction Level, unless bilaterally determined."),
    "R19": ("CBPR_Country_Of_Residence_TextualRule",
            "Country of Residence (where the party physically lives) should be used only if different from "
            "PostalAddress/Country (country linked to the owner of the account used for contact purposes)."),
    "R21": ("CBPR_Instruction_Identification_TextualRule",
            "If provided, this Id is returned to the ordering party in account statement reporting."),
    "R23": ("CBPR_Country_Of_Residence_TextualRule",
            "Country of Residence (where the party physically lives) should be used only if different from "
            "PostalAdress/Country (country linked to the owner of the account used for contact purposes)."),
    "R29": ("CBPR_Ultimate_Creditor_TextualRule",
            "Based on business need and bank service. If an ultimate creditor is involved in the payment, being "
            "different from the creditor, it must be provided."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
