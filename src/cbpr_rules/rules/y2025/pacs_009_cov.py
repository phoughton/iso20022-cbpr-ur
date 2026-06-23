"""CBPR+ SR2025 usage rules for pacs.009.001.08 COV (FinancialInstitutionCreditTransfer, cover).

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
    address_hybrid,
    address_lines_max_length,
    bic_presence_exclusive,
    business_msg_id_carries_group_id,
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

MT = "pacs.009_cov"
YEAR = 2025
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


def _party_grace_block(party_path: str, n_struct, n_hybrid, n_unstruct) -> None:
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
        report(a_nodes[0], detail=label)


@rule(MT, YEAR, "R1", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the "Payment Type Information/InstructionPriority" if present.')
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
      'BIC, except where BAH CopyDuplicate = COPY or = CODU.')
def _r2(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R3", "CBPR_From_To_Instructing_Instructed_Agent_BIC_2_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC if CopyDuplicate is '
      'absent. BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r3(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


# R12: remittance mutually exclusive (under the underlying customer credit transfer)
reg("R12", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present.",
    mutually_exclusive(UND + "/RmtInf", ["Ustrd", "Strd"]))


@rule(MT, YEAR, "R13", "CBPR_Instruction_For_Creditor_Presence_Code_FormalRule",
      'Each code can only be used once for element "Instruction For Creditor Agent".')
def _r13(msg, report):
    for tx in msg.each(TX):
        codes = msg.values("InstrForCdtrAgt/Cd", tx)
        if len(codes) != len(set(codes)):
            report(tx, detail="duplicate InstructionForCreditorAgent code")


reg("R14", "CBPR_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R16", "CBPR_End_To_End_Identification_FormalRule",
      "In the E2E identification, the below restrictions apply to the first 16 "
      'characters: - The first one and the 16th one cannot be "/" and - The '
      'string of 16 characters cannot contain "//"')
def _r16(msg, report):
    import re as _re
    pats = [_re.compile(p) for p in (r"/.*", r".{15}/.*", r".{0,14}//.*")]
    for node in msg.find(TX + "/PmtId/EndToEndId"):
        val = msg.text_of(node)
        if val and any(p.fullmatch(val) for p in pats):
            report(node, detail="EndToEndId first 16 characters violate slash restrictions")


reg("R20", "CBPR_Interbank_Settlement_Currency_FormalRule",
    "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
    "only used for commodities.",
    lambda msg, report: [
        report(el, detail=f"commodity currency '{ccy}' not allowed")
        for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy")
        if ccy in {"XAU", "XAG", "XPD", "XPT"}
    ])


# ---------------------------------------------------------------------------
# Agent blocks - cover (interbank) chain
# ---------------------------------------------------------------------------
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
# Underlying customer credit transfer - parties
# ---------------------------------------------------------------------------
reg("R70", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(UND + "/UltmtDbtr", "PstlAdr", "Nm"))
reg("R71", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(UND + "/InitgPty", "PstlAdr", "Nm"))
reg("R72", "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
    required_when_absent(UND + "/Dbtr", "Id/OrgId/AnyBIC", ["Nm"]))
reg("R76", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(UND + "/Dbtr", "PstlAdr", "Nm"))
_party_grace_block(UND + "/Dbtr", "R78", "R79", "R80")

# Underlying agent chain
_agent_block(UND + "/DbtrAgt/FinInstnId", "R81", "R82", "R83", "R84")
_agent_block(UND + "/PrvsInstgAgt1/FinInstnId", "R85", "R86", "R87", "R88")
_agent_block(UND + "/PrvsInstgAgt2/FinInstnId", "R89", "R90", "R91", "R92")
_agent_block(UND + "/PrvsInstgAgt3/FinInstnId", "R93", "R94", "R95", "R96")
_agent_block(UND + "/IntrmyAgt1/FinInstnId", "R97", "R98", "R99", "R100")
_agent_block(UND + "/IntrmyAgt2/FinInstnId", "R101", "R102", "R103", "R104")
_agent_block(UND + "/IntrmyAgt3/FinInstnId", "R105", "R106", "R107", "R108")
_agent_block(UND + "/CdtrAgt/FinInstnId", "R109", "R110", "R111", "R112")

reg("R113", "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
    required_when_absent(UND + "/Cdtr", "Id/OrgId/AnyBIC", ["Nm"]))
reg("R117", "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(UND + "/Cdtr", "PstlAdr", "Nm"))
_party_grace_block(UND + "/Cdtr", "R119", "R120", "R121")

reg("R124", "CBPR_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
    requires_if_present(UND + "/UltmtCdtr", "PstlAdr", "Nm"))


# ---------------------------------------------------------------------------
# Mechanizable textual rules + algorithmic field validation
# ---------------------------------------------------------------------------
reg("R8", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.cov.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.cov.03"]))

# Algorithmic validations (brief), for fields present in pacs.009 COV.
reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))


# ---------------------------------------------------------------------------
# Promoted from advisory: mechanizable cross-schema / cross-field checks.
# Each combinator is conservative (skips when inputs are absent/ambiguous).
# ---------------------------------------------------------------------------
reg("R5", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business Message instance "
    "that is being transported with this header, as defined by the sending application or system. "
    "Must contain the Message Identification element from the Group Header of the underlying message, "
    "where available.",
    business_msg_id_carries_group_id())

reg("R6", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is being transported "
    "with this header. In general, it must be formatted exactly as it appears in the namespace of "
    "the Business Message instance.",
    header_msg_def_id_matches())

reg("R28", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, under any circumstances "
    "be repeated in AddressLine.",
    no_postal_address_duplication())

reg("R77", "CBPR_Debtor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain "
    "optional) - However, in case of conflicting information, AnyBIC will always take precedence.",
    bic_presence_exclusive(UND + "/Dbtr"))

reg("R118", "CBPR_Creditor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain "
    "optional) - However, in case of conflicting information, AnyBIC will always take precedence.",
    bic_presence_exclusive(UND + "/Cdtr"))

reg("R125", "CBPR_RemittanceInformation_TextualRule",
    "1. Use of Structured Remittance must be bilaterally or multilaterally agreed. 2. Structured "
    "Remittance can be repeated, however the total business data for all occurrences (excluding tags) "
    "must not exceed 9,000 characters.",
    structured_remittance_max_total(UND + "/RmtInf/Strd", 9000))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R4": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, pls refer to the CBPR Plus UHB."),
    "R7": ("CBPR_Business_Service_TextualRule",
           "This field may be used by SWIFT to support differentiated processing on SWIFT-administered "
           "services such as FINplus."),
    "R9": ("CBPR_Market_Practice_TextualRule",
           "This field may be used by SWIFT on SWIFT-administered services. For a description of reserved "
           "values, please refer to the Service Description for your service."),
    "R10": ("CBPR_Related_Business_Application_Header_TextualRule",
            "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R11": ("CBPR_Related_BAH_Business_Service_TextualRule",
            "If related BAH is present, it should transport the element Business Service."),
    "R15": ("CBPR_E2E_COV_TextualRule",
            "In the pacs.009 COV, the E2E identification should transport the instruction identification "
            "of the underlying pacs.008."),
    "R17": ("CBPR_UETR_COV_TextualRule",
            "In the pacs.009 COV, the UETR should transport the UETR of the underlying pacs.008."),
    "R18": ("CBPR_Local_Instrument_Guideline",
            "The preferred option is coded information."),
    "R19": ("CBPR_Category_Purpose_Guideline",
            "The preferred option is coded information."),
    "R21": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same "
            "country, the clearing code only may be used."),
    "R22": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)."),
    "R23": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND (Unstructured postal address OR [Structured postal address "
            "with minimum Town Name and Country] OR [Hybrid postal address with minimum Town Name and Country])."),
    "R24": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND (Unstructured OR [Structured postal address with minimum Town Name and Country] OR "
            "[Hybrid postal address with minimum Town Name and Country])."),
    "R66": ("CBPR_Purpose_Guideline",
            "The preferred option is coded information."),
    "R67": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation)."),
    "R68": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country]."),
    "R69": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country] "
            "AND (Identification: Private or Organisation)."),
    "R73": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Debtor/Name is mandatory with either Debtor Account OR Debtor "
            "Identification."),
    "R74": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R75": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND (Unstructured OR [Structured Address with minimum Town Name & Country] OR [Hybrid postal "
            "address with minimum Town Name and Country]) AND (Account Number OR Identification: Private or Organisation)."),
    "R114": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
             "For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR "
             "Creditor Identification."),
    "R115": ("CBPR_Creditor_Option_1_TextualRule",
             "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R116": ("CBPR_Creditor_Option_2_TextualRule",
             "Name AND (Unstructured OR [Structured Address with minimum Town Name & Country] OR [Hybrid postal "
             "address with minimum Town Name and Country]) AND (Account Number OR Identification: Private or Organisation)."),
    "R122": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
             "Name AND Structured Address, with minimum Country (other elements are optional, eg "
             "Identification: Private or Organisation)."),
    "R123": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
             "For Jurisdictional transactions, Name and/or Identification (Private or Organisation)."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
