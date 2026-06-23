"""CBPR+ SR2025 usage rules for pacs.009.001.08 (FinancialInstitutionCreditTransfer).

Authored against the published usage guideline's Rules sheet. Every R-index is
registered with its real rule number, name and description; formal rules use the
shared combinators from ``helpers`` where the shape matches, and bespoke
``fn(msg, report)`` functions for cross-field / cross-schema logic.

Note: in pacs.009 the Debtor and Creditor are financial institutions, so their
Name/PostalAddress follow the *agent* (present-together) rule via FinInstnId.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    address_hybrid,
    address_lines_max_length,
    business_msg_id_carries_group_id,
    code_in,
    each_value_valid,
    header_msg_def_id_matches,
    no_postal_address_duplication,
    not_matching_pattern,
    presence_together,
    required_when_absent,
)

MT = "pacs.009"
YEAR = 2025
ROOT = "/Document/FICdtTrf"
TX = ROOT + "/CdtTrfTxInf"

# Repeated rule descriptions (identical across the locations they apply to).
D_AGENT_NAME_ADR = "Name and Address must always be present together."
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


def _agent_block(fin_inst_path: str, n_name, n_struct, n_hybrid, n_unstruct) -> None:
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


@rule(MT, YEAR, "R1", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the "Payment Type Information/InstructionPriority" '
      "if present.")
def _r1(msg, report):
    if msg.present("/AppHdr/Prty") and msg.present(TX + "/PmtTpInf/InstrPrty"):
        _values_match(msg, report, "/AppHdr/Prty", TX + "/PmtTpInf/InstrPrty",
                      "BAH Priority must equal InstructionPriority")


_BIC_PAIRS = [
    ("/AppHdr/Fr/FIId/FinInstnId/BICFI", TX + "/InstgAgt/FinInstnId/BICFI", "From vs Instructing Agent"),
    ("/AppHdr/To/FIId/FinInstnId/BICFI", TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent"),
]


@rule(MT, YEAR, "R2", "CBPR_From_To_Instructing_Instructed_Agent_BIC_1_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC, except where BAH '
      'CopyDuplicate = COPY or = CODU. BAH "To" BIC must match "Instructed Agent" '
      "BIC, except where BAH CopyDuplicate = COPY or = CODU.")
def _r2(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R3", "CBPR_From_To_Instructing_Instructed_Agent_BIC_2_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC if CopyDuplicate is '
      'absent. BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is '
      "absent.")
def _r3(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R12", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      'Each code can only be used once for element "Instruction For Creditor Agent".')
def _r12(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


reg("R13", "CBPR_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R15", "CBPR_End_To_End_Identification_FormalRule",
      "For the E2E identification, the below restrictions apply to the first 16 "
      "characters: - The first one and the 16th one cannot be '/' and - The "
      "string of 16 characters cannot contain '//'.")
def _r15(msg, report):
    import re as _re
    pats = [_re.compile(r"/.*"), _re.compile(r".{15}/.*"), _re.compile(r".{0,14}//.*")]
    for node in msg.find(TX + "/PmtId/EndToEndId"):
        val = msg.text_of(node)
        if val and any(p.fullmatch(val) for p in pats):
            report(node, detail="EndToEndId violates first-16-character slash restrictions")


@rule(MT, YEAR, "R20", "CBPR_Interbank_Settlement_Currency_FormalRule",
      "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
      "only used for commodities.")
def _r20(msg, report):
    for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy"):
        if ccy in {"XAU", "XAG", "XPD", "XPT"}:
            report(el, detail=f"commodity currency '{ccy}' not allowed")


# Transaction-chain agents (each: name/address + grace period).
# In pacs.009 Debtor and Creditor are financial institutions (FinInstnId), so
# they follow the agent present-together rule.
_agent_block(TX + "/PrvsInstgAgt1/FinInstnId", "R25", "R26", "R27", "R29")
_agent_block(TX + "/PrvsInstgAgt2/FinInstnId", "R30", "R31", "R32", "R33")
_agent_block(TX + "/PrvsInstgAgt3/FinInstnId", "R34", "R35", "R36", "R37")
_agent_block(TX + "/IntrmyAgt1/FinInstnId", "R38", "R39", "R40", "R41")
_agent_block(TX + "/IntrmyAgt2/FinInstnId", "R42", "R43", "R44", "R45")
_agent_block(TX + "/IntrmyAgt3/FinInstnId", "R46", "R47", "R48", "R49")
_agent_block(TX + "/Dbtr/FinInstnId", "R50", "R51", "R52", "R53")
_agent_block(TX + "/DbtrAgt/FinInstnId", "R54", "R55", "R56", "R57")
_agent_block(TX + "/CdtrAgt/FinInstnId", "R58", "R59", "R60", "R61")
_agent_block(TX + "/Cdtr/FinInstnId", "R62", "R63", "R64", "R65")


# ---------------------------------------------------------------------------
# Mechanizable textual rules + algorithmic field validation
# ---------------------------------------------------------------------------
reg("R8", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.03"]))

# Cross-schema BAH vs Document identity checks (promoted from advisory; each
# combinator is conservative and skips when its inputs are absent).
reg("R5", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business Message "
    "instance that is being transported with this header, as defined by the sending "
    "application or system. Must contain the Message Identification element from the "
    "Group Header of the underlying message, where available.",
    business_msg_id_carries_group_id())

reg("R6", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is being "
    "transported with this header. In general, it must be formatted exactly as it "
    "appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

reg("R28", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, under "
    "any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())

# Algorithmic validations required by the brief, for fields present in pacs.009.
reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R4": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, pls refer to the CBPR Plus UHB."),
    "R7": ("CBPR_Business_Service_TextualRule",
           "This field may be used by SWIFT to support differentiated processing on "
           "SWIFT-administered services such as FINplus."),
    "R9": ("CBPR_Market_Practice_TextualRule",
           "This field may be used by SWIFT on SWIFT-administered services. For a description "
           "of reserved values, please refer to the Service Description for your service."),
    "R10": ("CBPR_Related_Business_Application_Header_TextualRule",
            "If used, the Related BAH must transport the exact same information as in the BAH "
            "of the related message."),
    "R11": ("CBPR_Related_BAH_Business_Service_TextualRule",
            "If related BAH is present, it should transport the element Business Service."),
    "R14": ("CBPR_E2E_CORE_TextualRule",
            "In the pacs.009 CORE, the E2E identification is provided by the Debtor (Agent)."),
    "R16": ("CBPR_E2E_CORE_ADV_TextualRule",
            "If pacs.009CORE is used to cover pacs.009ADV, the E2E identification should "
            "transport the instruction identification of the underlying pacs.009 ADV."),
    "R17": ("CBPR_UETR_TextualRule",
            "If the pacs.009 is used to settle a pacs.009 Advice, the UETR should transport "
            "the UETR of the underlying pacs.009 Advice."),
    "R18": ("CBPR_Local_Instrument_Guideline",
            "The preferred option is coded information."),
    "R19": ("CBPR_Category_Purpose_Guideline",
            "The preferred option is coded information."),
    "R21": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are located "
            "within the same country, the clearing code only may be used."),
    "R22": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)."),
    "R23": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND (Unstructured postal address OR "
            "[Structured postal address with minimum Town Name and Country] OR [Hybrid "
            "postal address with minimum Town Name and Country])."),
    "R24": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND (Unstructured OR [Structured postal address with minimum Town Name and "
            "Country] OR [Hybrid postal address with minimum Town Name and Country])."),
    "R66": ("CBPR_Instruction_Information_TextualRule",
            "If the pacs.009 is used to settle a pacs.009 Advice, the last available "
            "occurrence (of the element Instruction For Creditor Agent/Instruction "
            "Information) preceded by /UDLC/ must be used to capture the /UDLC/ (Underlying "
            "Creditor) provided in the pacs.009 Advice."),
    "R67": ("CBPR_Purpose_Guideline",
            "The preferred option is coded information."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
