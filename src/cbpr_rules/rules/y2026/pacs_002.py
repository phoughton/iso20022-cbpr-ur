"""CBPR+ SR2026 usage rules for pacs.002.001.10 (FIToFIPaymentStatusReport).

Rule numbers, names and descriptions are taken from the published usage
guideline's Rules sheet; XML paths are the short ISO 20022 tags from its
Full_View / XML Path column. Structure mirrors the reference module
``rules/y2025/pacs_008.py``.
"""
from __future__ import annotations

import re as _re

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    business_msg_id_carries_group_id,
    header_msg_def_id_matches,
    no_postal_address_duplication,
    not_matching_pattern,
    requires_if_present,
    required_when_absent,
    same_value,
)

MT = "pacs.002"
YEAR = 2026
ROOT = "/Document/FIToFIPmtStsRpt"
TX = ROOT + "/TxInfAndSts"


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


# ---------------------------------------------------------------------------
# Cross-schema BIC / identifier matching (BAH vs Document)
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


@rule(MT, YEAR, "R1", "CBPR_To_Instructed_Agent_BIC_1_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC, except where BAH '
      "CopyDuplicate = COPY or = CODU.")
def _r1(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    _values_match(msg, report,
                  "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI",
                  "To BIC must equal Instructed Agent BIC")


@rule(MT, YEAR, "R2", "CBPR_To_Instructed_Agent_BIC_2_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r2(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    _values_match(msg, report,
                  "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI",
                  "To BIC must equal Instructed Agent BIC")


reg("R3", "CBPR_BusinessMessageIdentifier_FormalRule",
    "The Business Message Identifier must match the Message Identification in "
    "the Group Header.",
    same_value("/AppHdr/BizMsgIdr", ROOT + "/GrpHdr/MsgId"))


reg("R4", "CBPR_From_Instructing_Agent_BIC_FormalRule",
    'BAH "From" BIC must match "Instructing Agent" BIC.',
    same_value("/AppHdr/Fr/FIId/FinInstnId/BICFI",
               TX + "/InstgAgt/FinInstnId/BICFI"))


# ---------------------------------------------------------------------------
# Transaction status / reject handling
# ---------------------------------------------------------------------------

@rule(MT, YEAR, "R9", "CBPR_Transaction_Status_Reject_Reason_FormalRule",
      'If TransactionStatus/Code equals RJCT, then "Status Reason Information/'
      'Reason" is mandatory.')
def _r9(msg, report):
    for tx in msg.each(TX):
        if "RJCT" in msg.values("TxSts", tx) and msg.absent("StsRsnInf/Rsn", tx):
            report(tx, detail="StatusReasonInformation/Reason required when TransactionStatus is RJCT")


@rule(MT, YEAR, "R10", "CBPR_Transaction_Status_Reject_Effective_Sett_Date_FormalRule",
      "If TransactionStatus is 'RJCT' then Effective Interbank Settlement Date "
      "is not allowed.")
def _r10(msg, report):
    for tx in msg.each(TX):
        if "RJCT" in msg.values("TxSts", tx) and msg.present("FctvIntrBkSttlmDt", tx):
            report(tx, detail="EffectiveInterbankSettlementDate not allowed when TransactionStatus is RJCT")


@rule(MT, YEAR, "R12", "CBPR_OriginalMessageNameIdentification_FormalRule",
      "This element must be populated with either pacs.008.001.xx, "
      "pacs.009.001.xx, pacs.004.001.xx, pacs.003.001.xx or pacs.010.001.xx.")
def _r12(msg, report):
    rx = _re.compile(r"pacs\.00[8349]\.001\.[0-9]{2}|pacs\.010\.001\.[0-9]{2}")
    for node in msg.find(TX + "/OrgnlGrpInf/OrgnlMsgNmId"):
        val = msg.text_of(node)
        if val and not rx.fullmatch(val):
            report(node, detail=f"'{val}' is not an allowed OriginalMessageNameIdentification")


reg("R14", "CBPR_Original_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/OrgnlInstrId", r"(/.*)|(.*/)|(.*//.*)"))


# ---------------------------------------------------------------------------
# Status Reason Information / Originator party rules
# ---------------------------------------------------------------------------
_ORGTR = TX + "/StsRsnInf/Orgtr"

reg("R19", "CBPR_Party_Name_Postal_Address_FormalRule",
    "If Postal Address is present then Name is mandatory. Recommendation: If "
    "present, the BIC (AnyBIC) will always take precedence in case of "
    "conflicting information.",
    requires_if_present(_ORGTR, "PstlAdr", "Nm"))

reg("R20", "CBPR_Party_Name_Any_BIC_FormalRule",
    "If AnyBIC is absent, then Name is mandatory.",
    required_when_absent(_ORGTR, "Id/OrgId/AnyBIC", ["Nm"]))


# ---------------------------------------------------------------------------
# Algorithmic field validation (project brief) - only fields present here.
# ---------------------------------------------------------------------------
@rule(MT, YEAR, "VAL-BIC", "CBPR_Valid_Agent_BIC",
      "Every Instructing/Instructed Agent BICFI must be a structurally valid BIC.")
def _val_bic(msg, report):
    for path in (TX + "/InstgAgt/FinInstnId/BICFI", TX + "/InstdAgt/FinInstnId/BICFI"):
        for node in msg.find(path):
            val = msg.text_of(node)
            if val and not is_valid_bic(val):
                report(node, detail=f"invalid BIC: '{val}'")


# ---------------------------------------------------------------------------
# Mechanizable textual rules promoted to enforced checks (conservative: each
# combinator skips when its inputs are absent, so valid messages never fail).
# ---------------------------------------------------------------------------
reg("R6", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header, as defined by "
    "the sending application or system. Must contain the Message Identification "
    "element from the Group Header of the underlying message, where available.",
    business_msg_id_carries_group_id())

reg("R7", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted exactly "
    "as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

reg("R21", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())


# ---------------------------------------------------------------------------
# Advisory textual rules (not mechanically enforceable - surfaced as guidance)
# ---------------------------------------------------------------------------
_ADVISORY = {
    "R5": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R8": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R11": ("CBPR_Original_Message_Identification_TextualRule",
            "Original Message Identification must transport the Message Identification of the underlying payment (e.g. pacs.008/pacs.009/pacs.004)."),
    "R13": ("CBPR_Original_Instruction_Identification_TextualRule",
            "Should transport the Instruction Identification of the underlying payment message for example pacs.008/pacs.009 or the same Original Instruction Identification if present in pacs.004."),
    "R15": ("CBPR_Original_End_To_End_Identification_TextualRule",
            "Should transport the EndToEnd Identification of the underlying payment message for example pacs.008/pacs.009 or the same Original EndToEnd Identification as in the pacs.004."),
    "R16": ("CBPR_Original_Transaction_Identification_TextualRule",
            "Should transport the Transaction Identification of the underlying payment message for example pacs.008/pacs.009 when present, or the same Original Transaction Identification if present in pacs.004."),
    "R17": ("CBPR_Original_UETR_TextualRule",
            "Must transport the UETR of the underlying pacs.008/pacs.009."),
    "R18": ("CBPR_Originator_Identification_TextualRule",
            "If AnyBIC is present, in addition to any other optional elements, in case of conflicting information it will always take precedence."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
