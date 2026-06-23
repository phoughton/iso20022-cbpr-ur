"""CBPR+ SR2025 usage rules for pacs.002.001.10 (FIToFIPaymentStatusReport).

Authored to mirror the reference module ``pacs_008``: every rule from the
published usage guideline's Rules sheet is registered with its real rule
number, name and description, implemented with a shared combinator from
``helpers`` where the formal definition matches a known shape, or a bespoke
``fn(msg, report)`` for cross-field / cross-schema logic. Non-mechanizable
textual rules are surfaced via ``advisory``.

Paths are the short ISO 20022 tags from the guideline's XML Path column.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_country
from ...helpers import (
    address_hybrid,
    address_lines_max_length,
    business_msg_id_carries_group_id,
    code_in,
    each_value_valid,
    header_msg_def_id_matches,
    no_postal_address_duplication,
    not_matching_pattern,
    required_when_absent,
    requires_if_present,
)

MT = "pacs.002"
YEAR = 2025
ROOT = "/Document/FIToFIPmtStsRpt"
TX = ROOT + "/TxInfAndSts"
ORGTR = TX + "/StsRsnInf/Orgtr"


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


_BIC_PAIRS = [
    ("/AppHdr/Fr/FIId/FinInstnId/BICFI", TX + "/InstgAgt/FinInstnId/BICFI", "From vs Instructing Agent"),
    ("/AppHdr/To/FIId/FinInstnId/BICFI", TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent"),
]


@rule(MT, YEAR, "R1", "CBPR_From_To_Instructing_Instructed_Agent_BIC_1_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC, except where BAH '
      'CopyDuplicate = COPY or = CODU. BAH "To" BIC must match "Instructed '
      'Agent" BIC, except where BAH CopyDuplicate = COPY or = CODU.')
def _r1(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R2", "CBPR_From_To_Instructing_Instructed_Agent_BIC_2_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC if CopyDuplicate is '
      'absent. BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate '
      'is absent.')
def _r2(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R11", "CBPR_Transaction_Status_Reject_Effective_Sett_Date_FormalRule",
      "If TransactionStatus is “RJCT’ then Effective Interbank "
      "Settlement Date is not allowed.")
def _r11(msg, report):
    for tx in msg.each(TX):
        sts = msg.values("TxSts", tx)
        if sts and all(v == "RJCT" for v in sts) and msg.present("FctvIntrBkSttlmDt", tx):
            report(tx, detail="EffectiveInterbankSettlementDate not allowed when TransactionStatus is RJCT")


@rule(MT, YEAR, "R12", "CBPR_Transaction_Status_Reject_Reason_FormalRule",
      "If TransactionStatus/Code equals RJCT, then “Status Reason "
      "Information/Reason” is mandatory.")
def _r12(msg, report):
    for tx in msg.each(TX):
        sts = msg.values("TxSts", tx)
        if sts and all(v == "RJCT" for v in sts) and msg.absent("StsRsnInf/Rsn", tx):
            report(tx, detail="StatusReasonInformation/Reason is mandatory when TransactionStatus is RJCT")


reg("R15", "CBPR_Original_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain "
    "two consecutive slashes '//'.",
    not_matching_pattern(TX + "/OrgnlInstrId", r"(/.*)|(.*/)|(.*//.*)"))


# ---------------------------------------------------------------------------
# Originator party: AnyBIC/Name, Name/PostalAddress, grace-period address rules
# ---------------------------------------------------------------------------
reg("R19", "CBPR_Party_Name_Any_BIC_FormalRule",
    "If AnyBIC is absent, then Name is mandatory.",
    required_when_absent(ORGTR, "Id/OrgId/AnyBIC", ["Nm"]))

reg("R20", "CBPR_Party_Name_Postal_Address_FormalRule",
    "If Postal Address is present then Name is mandatory. Recommendation: If "
    "present, the BIC (AnyBIC) will always take precedence in case of "
    "conflicting information.",
    requires_if_present(ORGTR, "PstlAdr", "Nm"))

reg("R22", "CBPR_GracePeriod_Structured_FormalRule",
    "If Postal Address is used, and if Address Line is absent, then Town Name "
    "and Country must be present.",
    required_when_absent(ORGTR + "/PstlAdr", "AdrLine", ["TwnNm", "Ctry"]))

reg("R23", "CBPR_GracePeriod_Hybrid_FormalRule",
    "If Address Line is present and any other Postal Address element(s) are "
    "present, then Town Name and Country are mandatory in Postal Address and a "
    "maximum of two occurrences of Address Line are allowed.",
    address_hybrid(ORGTR + "/PstlAdr"))

reg("R25", "CBPR_GracePeriod_Unstructured_FormalRule",
    "If Postal Address is present and if no other element than Address Line is "
    "present then every occurrence of Address Line must not exceed 35 "
    "characters.",
    address_lines_max_length(ORGTR + "/PstlAdr", 35))


# ---------------------------------------------------------------------------
# Mechanizable textual rules
# ---------------------------------------------------------------------------
reg("R7", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.03"]))

reg("R4", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header, as defined by "
    "the sending application or system. Must contain the Message Identification "
    "element from the Group Header of the underlying message, where available.",
    business_msg_id_carries_group_id())

reg("R5", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted exactly "
    "as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

reg("R24", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())


# ---------------------------------------------------------------------------
# Algorithmic field validation (only for fields present in pacs.002)
# ---------------------------------------------------------------------------
reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))

reg("VAL-CTRY", "CBPR_Valid_Originator_Country",
    "Originator Postal Address Country must be a valid ISO 3166 country code.",
    each_value_valid(ORGTR + "/PstlAdr/Ctry", is_valid_country, "country"))


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R3": ("CBPR_Character_Set_Usage_TextualRule",
           "For further description on the usage of the field, pls refer to the CBPR Plus UHB."),
    "R6": ("CBPR_Business_Service_TextualRule",
           "This field may be used by SWIFT to support differentiated processing on SWIFT-administered services such as FINplus. For a description of reserved values, please refer to the Service Description for your service."),
    "R8": ("CBPR_Market_Practice_TextualRule",
           "This field may be used by SWIFT on SWIFT-administered services. For a description of reserved values, please refer to the Service Description for your service."),
    "R9": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R10": ("CBPR_Related_BAH_Business_Service_TextualRule",
            "If related BAH is present, it should transport the element Business Service."),
    "R13": ("CBPR_Original_Message_Identification_TextualRule",
            "Original Message Identification must transport the Message Identification of the underlying payment (eg. pacs.008/pacs.009/pacs.004)."),
    "R14": ("CBPR_Original_Instruction_Identification_TextualRule",
            "Should transport the Instruction Identification of the underlying payment message for example pacs.008/pacs.009 or the same Original Instruction Identification if present in pacs.004."),
    "R16": ("CBPR_Original_End_To_End_Identification_TextualRule",
            "Should transport the EndToEnd Identification of the underlying payment message for example pacs.008/pacs.009 or the same Original EndToEnd Identification as in the pacs.004."),
    "R17": ("CBPR_Original_Transaction_Identification_TextualRule",
            "Should transport the Transaction Identification of the underlying payment message for example pacs.008/pacs.009 when present, or the same Original Transaction Identification if present in pacs.004."),
    "R18": ("CBPR_Original_UETR_TextualRule",
            "Must transport the UETR of the underlying pacs.008/pacs.009."),
    "R21": ("CBPR_Originator_Identification_TextualRule",
            "If AnyBIC is present, in addition to any other optional elements, in case of conflicting information it will always take precedence."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
