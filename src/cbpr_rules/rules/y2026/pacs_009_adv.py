"""CBPR+ SR2026 usage rules for pacs.009.001.08 ADV (FinancialInstitutionCreditTransfer, Advice).

Authored against the published usage guideline's Rules sheet. Each R-index is
registered with its real rule number, name token and description; formal rules
use shared combinators where the shape matches, bespoke ``fn(msg, report)`` for
cross-field / cross-schema logic. Textual rules are enforced where mechanizable,
otherwise surfaced as advisories.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_currency
from ...helpers import (
    not_matching_pattern,
    presence_together,
    header_msg_def_id_matches,
    business_msg_id_carries_group_id,
    no_postal_address_duplication,
)

MT = "pacs.009_adv"
YEAR = 2026
ROOT = "/Document/FICdtTrf"
TX = ROOT + "/CdtTrfTxInf"

D_AGENT_NAME_ADR = "Name and Address must always be present together."


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
# Bespoke cross-field / cross-schema rules
# ---------------------------------------------------------------------------
@rule(MT, YEAR, "R1", "CBPR_BusinessMessageIdentifier_FormalRule",
      "The Business Message Identifier must match the Message Identification in "
      "the Group Header.")
def _r1(msg, report):
    _values_match(msg, report, "/AppHdr/BizMsgIdr", ROOT + "/GrpHdr/MsgId",
                  "BusinessMessageIdentifier must equal GroupHeader/MessageIdentification")


@rule(MT, YEAR, "R2", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the "Payment Type Information/InstructionPriority" '
      "if present.")
def _r2(msg, report):
    if msg.present("/AppHdr/Prty") and msg.present(TX + "/PmtTpInf/InstrPrty"):
        _values_match(msg, report, "/AppHdr/Prty", TX + "/PmtTpInf/InstrPrty",
                      "BAH Priority must equal InstructionPriority")


@rule(MT, YEAR, "R3", "CBPR_To_Instructed_Agent_BIC_2_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r3(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    _values_match(msg, report, "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent")


@rule(MT, YEAR, "R4", "CBPR_To_Instructed_Agent_BIC_1_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC, except where BAH '
      "CopyDuplicate = COPY or = CODU")
def _r4(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    _values_match(msg, report, "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent")


@rule(MT, YEAR, "R5", "CBPR_From_Instructing_Agent_BIC_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC')
def _r5(msg, report):
    _values_match(msg, report, "/AppHdr/Fr/FIId/FinInstnId/BICFI",
                  TX + "/InstgAgt/FinInstnId/BICFI", "From vs Instructing Agent")


@rule(MT, YEAR, "R10", "CBPR_GPI_ServiceLevel_Code_FormalRule",
      "The GPI ServiceLevel Code in pacs.009 ADV must be 'G004'.")
def _r10(msg, report):
    for tx in msg.each(TX):
        if msg.absent("PmtTpInf/SvcLvl", tx):
            continue
        for code in msg.find("PmtTpInf/SvcLvl/Cd", tx):
            if msg.text_of(code) in {"G001", "G002", "G003", "G005", "G006", "G007", "G009"}:
                report(code, detail="ServiceLevel/Code must be 'G004'")


# Reimbursement agents (Group Header / Settlement Information): FinInstnId agents.
reg("R15", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(ROOT + "/GrpHdr/SttlmInf/InstgRmbrsmntAgt/FinInstnId", "Nm", "PstlAdr"))
reg("R17", "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
    presence_together(ROOT + "/GrpHdr/SttlmInf/InstdRmbrsmntAgt/FinInstnId", "Nm", "PstlAdr"))


@rule(MT, YEAR, "R18", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      "Each code can only be used once for element Instruction For Creditor Agent.")
def _r18(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


reg("R19", "CBPR_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain "
    "two consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R20", "CBPR_End_To_End_Identification_FormalRule",
      "In the E2E identification, the below restrictions apply to the first 16 "
      "characters: - The first one and the 16th one cannot be “/” and - "
      "The string of 16 characters cannot contain “//”")
def _r20(msg, report):
    import re as _re
    pats = [_re.compile(r"/.*"), _re.compile(r".{15}/.*"), _re.compile(r".{0,14}//.*")]
    for node in msg.find(TX + "/PmtId/EndToEndId"):
        val = msg.text_of(node)
        if val and any(p.fullmatch(val) for p in pats):
            report(node, detail="EndToEndIdentification matches a forbidden pattern")


reg("R21", "CBPR_Interbank_Settlement_Currency_FormalRule",
    "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
    "only used for commodities.",
    lambda msg, report: [
        report(el, detail=f"commodity currency '{ccy}' not allowed")
        for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy")
        if ccy in {"XAU", "XAG", "XPD", "XPT"}
    ])


# Transaction-chain agents / FI parties: Name + Postal Address presence-together.
_AGENT_NAME_ADR = {
    "R22": TX + "/PrvsInstgAgt1/FinInstnId",
    "R23": TX + "/PrvsInstgAgt2/FinInstnId",
    "R24": TX + "/PrvsInstgAgt3/FinInstnId",
    "R25": TX + "/IntrmyAgt1/FinInstnId",
    "R26": TX + "/IntrmyAgt2/FinInstnId",
    "R27": TX + "/IntrmyAgt3/FinInstnId",
    "R28": TX + "/Dbtr/FinInstnId",
    "R29": TX + "/DbtrAgt/FinInstnId",
    "R30": TX + "/CdtrAgt/FinInstnId",
    "R31": TX + "/Cdtr/FinInstnId",
}
for _num, _path in _AGENT_NAME_ADR.items():
    reg(_num, "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
        presence_together(_path, "Nm", "PstlAdr"))


# ---------------------------------------------------------------------------
# Algorithmic field validation (brief), only for fields present in pacs.009 ADV.
# ---------------------------------------------------------------------------
reg("VAL-CCY", "CBPR_Valid_Settlement_Currency",
    "Interbank Settlement Amount currency must be a valid ISO 4217 code.",
    lambda msg, report: [
        report(el, detail=f"invalid currency '{ccy}'")
        for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy")
        if ccy and not is_valid_currency(ccy)
    ])


@rule(MT, YEAR, "VAL-BIC", "CBPR_Valid_Agent_BIC",
      "Every Agent BICFI in the message must be a structurally valid BIC.")
def _val_bic(msg, report):
    paths = [
        "/AppHdr/Fr/FIId/FinInstnId/BICFI",
        "/AppHdr/To/FIId/FinInstnId/BICFI",
        ROOT + "/GrpHdr/SttlmInf/InstgRmbrsmntAgt/FinInstnId/BICFI",
        ROOT + "/GrpHdr/SttlmInf/InstdRmbrsmntAgt/FinInstnId/BICFI",
        TX + "/InstgAgt/FinInstnId/BICFI",
        TX + "/InstdAgt/FinInstnId/BICFI",
        TX + "/PrvsInstgAgt1/FinInstnId/BICFI",
        TX + "/PrvsInstgAgt2/FinInstnId/BICFI",
        TX + "/PrvsInstgAgt3/FinInstnId/BICFI",
        TX + "/IntrmyAgt1/FinInstnId/BICFI",
        TX + "/IntrmyAgt2/FinInstnId/BICFI",
        TX + "/IntrmyAgt3/FinInstnId/BICFI",
        TX + "/Dbtr/FinInstnId/BICFI",
        TX + "/DbtrAgt/FinInstnId/BICFI",
        TX + "/CdtrAgt/FinInstnId/BICFI",
        TX + "/Cdtr/FinInstnId/BICFI",
    ]
    for p in paths:
        for node in msg.find(p):
            val = msg.text_of(node)
            if val and not is_valid_bic(val):
                report(node, detail=f"invalid BIC: '{val}'")


# ---------------------------------------------------------------------------
# Promoted from advisory: mechanizable header / postal-address checks.
# ---------------------------------------------------------------------------
reg("R7", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the "
    "Business Message instance that is being transported with this header, "
    "as defined by the sending application or system. Must contain the "
    "Message Identification element from the Group Header.",
    business_msg_id_carries_group_id())

reg("R8", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance "
    "that is being transported with this header. In general, it must be "
    "formatted exactly as it appears in the namespace of the Business "
    "Message instance.",
    header_msg_def_id_matches())

reg("R16", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must "
    "not, under any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable).
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R6": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as "
           "in the BAH of the related message."),
    "R9": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business "
           "Service."),
    "R11": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND ([Structured postal address with minimum Town Name and "
            "Country] OR [Hybrid postal address with minimum Town Name and "
            "Country]). It is recommended to also add the post code when available."),
    "R12": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND ([Structured postal address "
            "with minimum Town Name and Country] OR [Hybrid postal address with "
            "minimum Town Name and Country]). It is recommended to also add the "
            "post code when available."),
    "R13": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)"),
    "R14": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are "
            "located within the same country, the clearing code only may be used."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
