"""CBPR+ SR2026 usage rules for pacs.009.001.08 COV (FinancialInstitutionCreditTransfer, cover).

Authored following the pacs.008 reference module: each rule is registered with
its source rule number, name and description, implemented either with a shared
combinator from ``helpers`` or a bespoke ``fn(msg, report)``.

Rule numbers/text are from the published usage guideline's Rules sheet; XML paths
are the short ISO 20022 tags from its Full_View / XML Path column.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    bic_presence_exclusive,
    business_msg_id_carries_group_id,
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

MT = "pacs.009_cov"
YEAR = 2026
ROOT = "/Document/FICdtTrf"
TX = ROOT + "/CdtTrfTxInf"
UND = TX + "/UndrlygCstmrCdtTrf"

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


def _agent_name_adr(number: str, fin_inst_path: str) -> None:
    reg(number, "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
        presence_together(fin_inst_path, "Nm", "PstlAdr"))


def _party_name_adr(number: str, party_path: str) -> None:
    reg(number, "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
        requires_if_present(party_path, "PstlAdr", "Nm"))


def _party_any_bic(number: str, party_path: str) -> None:
    reg(number, "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
        required_when_absent(party_path, "Id/OrgId/AnyBIC", ["Nm"]))


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


@rule(MT, YEAR, "R2", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the "Payment Type Information/InstructionPriority" if present.')
def _r2(msg, report):
    if msg.present("/AppHdr/Prty") and msg.present(TX + "/PmtTpInf/InstrPrty"):
        _values_match(msg, report, "/AppHdr/Prty", TX + "/PmtTpInf/InstrPrty",
                      "BAH Priority must equal InstructionPriority")


_TO_PAIR = ("/AppHdr/To/FIId/FinInstnId/BICFI", TX + "/InstdAgt/FinInstnId/BICFI",
            "To vs Instructed Agent")


@rule(MT, YEAR, "R3", "CBPR_To_Instructed_Agent_BIC_1_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC, except where BAH '
      "CopyDuplicate = COPY or = CODU")
def _r3(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    _values_match(msg, report, *_TO_PAIR)


@rule(MT, YEAR, "R4", "CBPR_To_Instructed_Agent_BIC_2_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r4(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    _values_match(msg, report, *_TO_PAIR)


@rule(MT, YEAR, "R5", "CBPR_From_Instructing_Agent_BIC_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC')
def _r5(msg, report):
    _values_match(msg, report, "/AppHdr/Fr/FIId/FinInstnId/BICFI",
                  TX + "/InstgAgt/FinInstnId/BICFI", "From vs Instructing Agent")


# R10: remittance mutually exclusive (under the underlying customer credit transfer)
reg("R10", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present.",
    mutually_exclusive(UND + "/RmtInf", ["Ustrd", "Strd"]))


reg("R11", "CBPR_GPI_ServiceLevel_Code_FormalRule",
    "The GPI ServiceLevel Code in pacs.009 COV must be 'G001'.",
    not_matching_pattern(TX + "/PmtTpInf/SvcLvl/Cd",
                         r"(G002|G003|G004|G005|G006|G007|G009)"))


@rule(MT, YEAR, "R12", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      'Each code can only be used once for element "Instruction For Creditor Agent".')
def _r12(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


reg("R13", "CBPR_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain "
    "two consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R15", "CBPR_End_To_End_Identification_FormalRule",
      "In the E2E identification, the below restrictions apply to the first 16 "
      'characters: - The first one and the 16th one cannot be "/" and - The '
      'string of 16 characters cannot contain "//"')
def _r15(msg, report):
    import re as _re
    pats = [_re.compile(p) for p in (r"/.*", r".{15}/.*", r".{0,14}//.*")]
    for node in msg.find(TX + "/PmtId/EndToEndId"):
        val = msg.text_of(node)
        if val and any(p.fullmatch(val) for p in pats):
            report(node, detail="EndToEndId first 16 characters violate slash restrictions")


reg("R17", "CBPR_Interbank_Settlement_Currency_FormalRule",
    "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
    "only used for commodities.",
    lambda msg, report: [
        report(el, detail=f"commodity currency '{ccy}' not allowed")
        for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy")
        if ccy in {"XAU", "XAG", "XPD", "XPT"}
    ])


# ---------------------------------------------------------------------------
# Agent name/address rules - cover (interbank) chain
# ---------------------------------------------------------------------------
_agent_name_adr("R22", TX + "/PrvsInstgAgt1/FinInstnId")
_agent_name_adr("R24", TX + "/PrvsInstgAgt2/FinInstnId")
_agent_name_adr("R25", TX + "/PrvsInstgAgt3/FinInstnId")
_agent_name_adr("R26", TX + "/IntrmyAgt1/FinInstnId")
_agent_name_adr("R27", TX + "/IntrmyAgt2/FinInstnId")
_agent_name_adr("R28", TX + "/IntrmyAgt3/FinInstnId")
_agent_name_adr("R29", TX + "/Dbtr/FinInstnId")
_agent_name_adr("R30", TX + "/DbtrAgt/FinInstnId")
_agent_name_adr("R31", TX + "/CdtrAgt/FinInstnId")
_agent_name_adr("R32", TX + "/Cdtr/FinInstnId")

# ---------------------------------------------------------------------------
# Underlying customer credit transfer - parties + agents
# ---------------------------------------------------------------------------
_party_name_adr("R33", UND + "/UltmtDbtr")
_party_name_adr("R37", UND + "/InitgPty")
_party_any_bic("R38", UND + "/Dbtr")
_party_name_adr("R43", UND + "/Dbtr")

_agent_name_adr("R44", UND + "/DbtrAgt/FinInstnId")
_agent_name_adr("R45", UND + "/PrvsInstgAgt1/FinInstnId")
_agent_name_adr("R46", UND + "/PrvsInstgAgt2/FinInstnId")
_agent_name_adr("R47", UND + "/PrvsInstgAgt3/FinInstnId")
_agent_name_adr("R48", UND + "/IntrmyAgt1/FinInstnId")
_agent_name_adr("R49", UND + "/IntrmyAgt2/FinInstnId")
_agent_name_adr("R50", UND + "/IntrmyAgt3/FinInstnId")
_agent_name_adr("R51", UND + "/CdtrAgt/FinInstnId")

_party_name_adr("R53", UND + "/Cdtr")
_party_any_bic("R54", UND + "/Cdtr")
_party_name_adr("R59", UND + "/UltmtCdtr")


# ---------------------------------------------------------------------------
# Algorithmic field validation (brief), for fields present in pacs.009 COV.
# ---------------------------------------------------------------------------
reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R6": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R9": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R14": ("CBPR_E2E_COV_TextualRule",
            "In the pacs.009 COV, the E2E identification should transport the instruction identification "
            "of the underlying pacs.008."),
    "R16": ("CBPR_UETR_COV_TextualRule",
            "In the pacs.009 COV, the UETR should transport the UETR of the underlying pacs.008."),
    "R18": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND ([Structured postal address with minimum Town Name and Country] OR [Hybrid postal "
            "address with minimum Town Name and Country]). It is recommended to also add the post code when available."),
    "R19": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND ([Structured postal address with minimum Town Name and "
            "Country] OR [Hybrid postal address with minimum Town Name and Country]). It is recommended to "
            "also add the post code when available."),
    "R20": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)"),
    "R21": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same "
            "country, the clearing code only may be used."),
    "R34": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available)]"),
    "R35": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) (that is "
            "within a country or for regions under same legislations - e.g. EEA)."),
    "R36": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available] AND (Identification: Private or Organisation)"),
    "R39": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country (+ recommended to add Post code "
            "when available)] OR [Hybrid postal address with minimum Town Name and Country (+ recommended to "
            "add Post code when available)] AND (Account Number OR Identification: Private or Organisation)."),
    "R41": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)"),
    "R42": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Debtor/Name is mandatory with either Debtor Account OR Debtor "
            "Identification (that is within a country or for regions under same legislations - e.g. EEA)."),
    "R55": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR "
            "Creditor Identification (that is within a country or for regions under same legislations - e.g. EEA)."),
    "R56": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country (+ recommended to add Post code "
            "when available)] OR [Hybrid postal address with minimum Town Name and Country (+ recommended to "
            "add Post code when available)) AND (Account Number OR Identification: Private or Organisation)."),
    "R57": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)"),
    "R58": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) (that is "
            "within a country or for regions under same legislations - e.g. EEA)."),
    "R60": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available)]. Other elements are optional, eg "
            "Identification: Private or Organisation)"),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)


# ---------------------------------------------------------------------------
# Promoted from advisory to enforced (mechanizable, conservative checks).
# ---------------------------------------------------------------------------
reg("R7", "CBPR_Business_Message_Identifier_FormalRule",
    "The Business Message Identifier is the unique identifier of the Business Message instance "
    "that is being transported with this header, as defined by the sending application or system. "
    "Must contain the Message Identification element from the Group Header of the underlying message, "
    "where available.",
    business_msg_id_carries_group_id())

reg("R8", "CBPR_Message_Definition_Identifier_FormalRule",
    "The Message Definition Identifier of the Business Message instance that is being transported "
    "with this header. In general, it must be formatted exactly as it appears in the namespace of "
    "the Business Message instance.",
    header_msg_def_id_matches())

reg("R23", "CBPR_Duplication_Postal_Address_FormalRule",
    "Data present in structured elements within the Postal Address must not, under any circumstances "
    "be repeated in AddressLine.",
    no_postal_address_duplication())

reg("R40", "CBPR_Debtor_BIC_Presence_FormalRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain "
    "optional) - However, in case of conflicting information, AnyBIC will always take precedence.",
    bic_presence_exclusive(UND + "/Dbtr"))

reg("R52", "CBPR_Creditor_BIC_Presence_FormalRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain "
    "optional) - However, in case of conflicting information, AnyBIC will always take precedence.",
    bic_presence_exclusive(UND + "/Cdtr"))

reg("R61", "CBPR_Structured_RemittanceInformation_FormalRule",
    "Structured can be repeated, however the total business data for all occurrences (excluding "
    "tags) must not exceed 9,000 characters.",
    structured_remittance_max_total(UND + "/RmtInf/Strd", 9000))
