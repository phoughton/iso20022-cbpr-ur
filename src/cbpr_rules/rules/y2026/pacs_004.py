"""CBPR+ SR2026 usage rules for pacs.004.001.09 (PaymentReturn).

Authored against the published usage guideline's Rules sheet. Each R-index is
registered with its real rule number, name token and description. Formal rules
reuse the shared combinators from ``helpers`` where they match a known shape;
cross-field / cross-schema logic is written as bespoke ``fn(msg, report)``.

Structure mirrors the reference module ``y2025/pacs_008.py``.
"""
from __future__ import annotations

from ...registry import advisory, rule
from ...validators import is_valid_bic
from ...helpers import (
    bic_presence_exclusive,
    business_msg_id_carries_group_id,
    charges_required_when_amounts_differ,
    each_value_valid,
    header_msg_def_id_matches,
    mutually_exclusive,
    no_postal_address_duplication,
    not_matching_pattern,
    presence_together,
    required_when_absent,
    requires_if_present,
)

from decimal import Decimal, InvalidOperation as _InvalidOperation

MT = "pacs.004"
YEAR = 2026
ROOT = "/Document/PmtRtr"
TX = ROOT + "/TxInf"
OTR = TX + "/OrgnlTxRef"
RC = TX + "/RtrChain"

# Repeated rule descriptions (identical across the locations they apply to).
D_AGENT_NAME_ADR = "Name and Address must always be present together."
D_PARTY_NAME_ADR = "If Postal Address is present then Name is mandatory."
D_PARTY_ANY_BIC = (
    "If AnyBIC is absent then Name is mandatory and it is recommended to also "
    "provide the Postal Address."
)
D_PARTY_ANY_BIC_2 = "If AnyBIC is absent, then Name is mandatory."
D_COMMODITY = (
    "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
    "only used for commodities."
)
_COMMODITY = ["XAU", "XAG", "XPD", "XPT"]


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _agent_name_adr(number: str, fin_inst_path: str) -> None:
    reg(number, "CBPR_Agent_Name_Postal_Address_FormalRule", D_AGENT_NAME_ADR,
        presence_together(fin_inst_path, "Nm", "PstlAdr"))


def _party_name_adr(number: str, party_path: str) -> None:
    reg(number, "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
        requires_if_present(party_path, "PstlAdr", "Nm"))


def _party_any_bic(number: str, party_path: str, desc: str) -> None:
    reg(number, "CBPR_Party_Name_Any_BIC_FormalRule", desc,
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


@rule(MT, YEAR, "R2", "CBPR_To_Instructed_Agent_BIC_1_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC, except where BAH '
      "CopyDuplicate = COPY or = CODU")
def _r2(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    _values_match(msg, report, "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent")


@rule(MT, YEAR, "R3", "CBPR_To_Instructed_Agent_BIC_2_FormalRule",
      'BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r3(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    _values_match(msg, report, "/AppHdr/To/FIId/FinInstnId/BICFI",
                  TX + "/InstdAgt/FinInstnId/BICFI", "To vs Instructed Agent")


@rule(MT, YEAR, "R4", "CBPR_From_Instructing_Agent_BIC_FormalRule",
      'BAH "From" BIC must match "Instructing Agent" BIC')
def _r4(msg, report):
    _values_match(msg, report, "/AppHdr/Fr/FIId/FinInstnId/BICFI",
                  TX + "/InstgAgt/FinInstnId/BICFI", "From vs Instructing Agent")


@rule(MT, YEAR, "R9", "CBPR_Interbank_Settlement_Date_FormalRule",
      "If TransactionInformation/OriginalInterbankSettlementDate is present, then "
      "OriginalTransactionReference/InterbankSettlementDate must not be used.")
def _r9(msg, report):
    for tx in msg.each(TX):
        if msg.present("OrgnlIntrBkSttlmDt", tx) and msg.present("OrgnlTxRef/IntrBkSttlmDt", tx):
            report(tx, detail="OrgnlTxRef/InterbankSettlementDate must be absent when "
                              "OriginalInterbankSettlementDate is present")


@rule(MT, YEAR, "R10", "CBPR_Interbank_Settlement_Amount_FormalRule",
      "If TransactionInformation/OriginalInterbankSettlementAmount is present, then "
      "OriginalTransactionReference/InterbankSettlementAmount must not be used.")
def _r10(msg, report):
    for tx in msg.each(TX):
        if msg.present("OrgnlIntrBkSttlmAmt", tx) and msg.present("OrgnlTxRef/IntrBkSttlmAmt", tx):
            report(tx, detail="OrgnlTxRef/InterbankSettlementAmount must be absent when "
                              "OriginalInterbankSettlementAmount is present")


@rule(MT, YEAR, "R11", "CBPR_CRED_FormalRule",
      "Charge information is mandatory if CRED is present - if no charges are "
      'taken, Zero must be used in "Amount" (any agent in the payment chain).')
def _r11(msg, report):
    for tx in msg.each(TX):
        cb = msg.values("ChrgBr", tx)
        if cb and all(v == "CRED" for v in cb) and msg.absent("ChrgsInf", tx):
            report(tx, detail="ChargesInformation required when ChargeBearer is CRED")


# R13 is a positive XML pattern (value MUST match); implement bespoke.
import re as _re  # noqa: E402

_R13_RX = _re.compile(
    r"pacs\.00[289]\.001\.[0-9]{2}|camt\.05[34]\.001\.[0-9]{2}|"
    r"MT103|MT202|MT205|MT900|MT910|MT940|MT950"
)


@rule(MT, YEAR, "R13", "CBPR_Original_Message_Name_Identification_FormalRule",
      "This element should be populated with either pacs.002.001.xx or "
      "pacs.008.001.xx or pacs.009.001.xx or camt.053.001.xx or camt.054.001.xx or "
      "MT103 or MT202 or MT205 or MT 900 or MT910 or MT940 or MT950 when present.")
def _r13(msg, report):
    for node in msg.find(TX + "/OrgnlGrpInf/OrgnlMsgNmId"):
        val = msg.text_of(node)
        if val and not _R13_RX.fullmatch(val):
            report(node, detail=f"OriginalMessageNameIdentification '{val}' not an allowed value")


reg("R14", "CBPR_Original_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/OrgnlInstrId", r"(/.*)|(.*/)|(.*//.*)"))


def _commodity_ccy(path: str):
    def check(msg, report):
        for el, ccy in msg.attr_nodes(path, "Ccy"):
            if ccy in _COMMODITY:
                report(el, detail=f"commodity currency '{ccy}' not allowed")
    return check


reg("R20", "CBPR_Interbank_Settlement_Currency_FormalRule", D_COMMODITY,
    _commodity_ccy(TX + "/OrgnlIntrBkSttlmAmt"))

reg("R23", "CBPR_Returned_Interbank_Settlement_Currency_FormalRule", D_COMMODITY,
    _commodity_ccy(TX + "/RtrdIntrBkSttlmAmt"))

reg("R65", "CBPR_Interbank_Settlement_Currency_FormalRule", D_COMMODITY,
    _commodity_ccy(OTR + "/IntrBkSttlmAmt"))


# ---------------------------------------------------------------------------
# Agent Name/Postal Address rules (presence_together on each FinInstnId)
# ---------------------------------------------------------------------------
_agent_name_adr("R29", TX + "/ChrgsInf/Agt/FinInstnId")
_agent_name_adr("R41", RC + "/Dbtr/Agt/FinInstnId")
_agent_name_adr("R43", RC + "/DbtrAgt/FinInstnId")
_agent_name_adr("R44", RC + "/PrvsInstgAgt1/FinInstnId")
_agent_name_adr("R45", RC + "/PrvsInstgAgt2/FinInstnId")
_agent_name_adr("R46", RC + "/PrvsInstgAgt3/FinInstnId")
_agent_name_adr("R47", RC + "/IntrmyAgt1/FinInstnId")
_agent_name_adr("R48", RC + "/IntrmyAgt2/FinInstnId")
_agent_name_adr("R49", RC + "/IntrmyAgt3/FinInstnId")
_agent_name_adr("R50", RC + "/CdtrAgt/FinInstnId")
_agent_name_adr("R57", RC + "/Cdtr/Agt/FinInstnId")
_agent_name_adr("R67", OTR + "/SttlmInf/InstgRmbrsmntAgt/FinInstnId")
_agent_name_adr("R68", OTR + "/SttlmInf/InstdRmbrsmntAgt/FinInstnId")
_agent_name_adr("R69", OTR + "/SttlmInf/ThrdRmbrsmntAgt/FinInstnId")
_agent_name_adr("R77", OTR + "/Dbtr/Agt/FinInstnId")
_agent_name_adr("R78", OTR + "/DbtrAgt/FinInstnId")
_agent_name_adr("R80", OTR + "/CdtrAgt/FinInstnId")
_agent_name_adr("R85", OTR + "/Cdtr/Agt/FinInstnId")


# ---------------------------------------------------------------------------
# Party Name / Postal Address rules (if PostalAddress then Name)
# ---------------------------------------------------------------------------
_party_name_adr("R34", RC + "/UltmtDbtr/Pty")
_party_name_adr("R36", RC + "/Dbtr/Pty")
_party_name_adr("R42", RC + "/InitgPty/Pty")
_party_name_adr("R53", RC + "/Cdtr/Pty")
_party_name_adr("R58", RC + "/UltmtCdtr/Pty")
_party_name_adr("R64", TX + "/RtrRsnInf/Orgtr")
_party_name_adr("R72", OTR + "/UltmtDbtr/Pty")
_party_name_adr("R75", OTR + "/Dbtr/Pty")
_party_name_adr("R81", OTR + "/Cdtr/Pty")
_party_name_adr("R88", OTR + "/UltmtCdtr/Pty")


# ---------------------------------------------------------------------------
# Party Name / AnyBIC rules (if AnyBIC absent then Name)
# ---------------------------------------------------------------------------
_party_any_bic("R37", RC + "/Dbtr/Pty", D_PARTY_ANY_BIC)
_party_any_bic("R55", RC + "/Cdtr/Pty", D_PARTY_ANY_BIC)
_party_any_bic("R63", TX + "/RtrRsnInf/Orgtr", D_PARTY_ANY_BIC_2)
_party_any_bic("R74", OTR + "/Dbtr/Pty", D_PARTY_ANY_BIC_2)
_party_any_bic("R83", OTR + "/Cdtr/Pty", D_PARTY_ANY_BIC_2)


# R70: remittance mutually exclusive
reg("R70", "CBPR_Remittance_Mutually_Exclusive_FormalRule",
    "Either Structured or Unstructured Remittance can be present.",
    mutually_exclusive(OTR + "/RmtInf", ["Ustrd", "Strd"]))


# ---------------------------------------------------------------------------
# Algorithmic field validation (brief), only for fields present in pacs.004.
# ---------------------------------------------------------------------------
def _run_all(*checks):
    """Combine several builder-produced checks into one ``check(msg, report)``."""
    def check(msg, report):
        for c in checks:
            c(msg, report)
    return check


reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    _run_all(
        each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"),
        each_value_valid(TX + "/InstdAgt/FinInstnId/BICFI", is_valid_bic, "BIC"),
    ))


# ---------------------------------------------------------------------------
# Mechanizable textual rules + advisory textual rules.
# ---------------------------------------------------------------------------
# R71: total Structured remittance business data must not exceed 9,000 chars.
@rule(MT, YEAR, "R71", "CBPR_Structured_RemittanceInformation_TextualRule",
      "Structured can be repeated, however the total business data for all "
      "occurrences (excluding tags) must not exceed 9,000 characters.")
def _r71(msg, report):
    strd = msg.find(OTR + "/RmtInf/Strd")
    if not strd:
        return
    total = 0
    for node in strd:
        total += sum(len((t or "").strip()) for t in node.itertext())
    if total > 9000:
        report(strd[0], detail=f"Structured remittance business data {total} exceeds 9000 characters")


# ---------------------------------------------------------------------------
# Rules promoted from advisory to enforced (mechanizable, conservative).
# ---------------------------------------------------------------------------
# R6: Business Message Identifier must carry the Group Header MsgId.
reg("R6", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business Message instance "
    "that is being transported with this header, as defined by the sending application or system. "
    "Must contain the Message Identification element from the Group Header of the underlying message, "
    "where available.",
    business_msg_id_carries_group_id())

# R7: Message Definition Identifier must match the Document message-definition id.
reg("R7", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance must in general be formatted "
    "exactly as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

# R30: structured Postal Address values must not be duplicated in AddressLine.
reg("R30", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, under any circumstances "
    "be repeated in AddressLine.",
    no_postal_address_duplication())

# R40 / R52: if AnyBIC present then Name and Postal Address are not allowed.
reg("R40", "CBPR_Debtor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed. In case of conflicting "
    "information, AnyBIC will always take precedence.",
    bic_presence_exclusive(RC + "/Dbtr/Pty"))

reg("R52", "CBPR_Creditor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed. In case of conflicting "
    "information, AnyBIC will always take precedence.",
    bic_presence_exclusive(RC + "/Cdtr/Pty"))

# R22: if ReturnedInstructedAmount and ReturnedInterbankSettlementAmount share a
# currency and differ, Charge Information becomes mandatory.
reg("R22", "CBPR_Returned_Instructed_Rule_1_TextualRule",
    "If ReturnedInstructedAmount and ReturnedInterbankSettlementAmount are expressed in the same "
    "currency and differ, Charge Information becomes mandatory.",
    charges_required_when_amounts_differ(TX, "RtrdInstdAmt", "RtrdIntrBkSttlmAmt", "ChrgsInf"))


# R61: Partial Return - when a partial return is detectable (returned interbank
# amount < original interbank amount, same currency), ReturnReasonInformation/
# AdditionalInformation must equal "PART" and Reason must be populated.
@rule(MT, YEAR, "R61", "CBPR_Partial_Return_TextualRule",
      'In case of Partial Return, the ReturnReasonInformation/AdditionalInformation must take the '
      'fixed value "PART" and the ReturnReasonInformation/Reason must be populated with a code from '
      "the External reason code list.")
def _r61(msg, report):
    for tx in msg.each(TX):
        rtrd = msg.find("RtrdIntrBkSttlmAmt", tx)
        orig = msg.find("OrgnlIntrBkSttlmAmt", tx)
        if not rtrd or not orig:
            continue
        r_ccy, o_ccy = rtrd[0].get("Ccy"), orig[0].get("Ccy")
        if not r_ccy or r_ccy != o_ccy:
            continue
        try:
            rv = Decimal(msg.text_of(rtrd[0]))
            ov = Decimal(msg.text_of(orig[0]))
        except (_InvalidOperation, ValueError):
            continue
        if rv >= ov:
            continue  # not a detectable partial return
        addtl = [msg.text_of(n) for n in msg.find("RtrRsnInf/AddtlInf", tx)]
        if not any(v == "PART" for v in addtl):
            report(tx, detail='Partial Return requires ReturnReasonInformation/AdditionalInformation = "PART"')
        if msg.absent("RtrRsnInf/Rsn", tx):
            report(tx, detail="Partial Return requires ReturnReasonInformation/Reason to be populated")


# Advisory textual rules (not mechanically enforceable - surfaced as guidance).
_ADVISORY = {
    "R5": ("CBPR_Related_Business_Application_Header_TextualRule",
           "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R8": ("CBPR_Related_BAH_Business_Service_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R12": ("CBPR_Original_Message_Identification_TextualRule",
            "Original Message Identification must transport the Message Identification of the underlying "
            "payment (e.g. pacs.008/pacs.009)."),
    "R15": ("CBPR_Original_Instruction_Identification_TextualRule",
            "If present in underlying pacs.008/pacs.009, the Instruction Identification must be transported in pacs.004."),
    "R16": ("CBPR_Original_End_To_End_Identification_TextualRule",
            "If present in underlying pacs.008/pacs.009, the EndToEnd Identification must be transported in pacs.004."),
    "R17": ("CBPR_Original_Transaction_Identification_TextualRule",
            "If present in underlying pacs.008/pacs.009, the Transaction Identification must be transported in the pacs.004."),
    "R18": ("CBPR_Original_UETR_TextualRule",
            "Must transport the UETR of the underlying pacs.008/pacs.009."),
    "R19": ("CBPR_Original_Clearing_System_Reference_TextualRule",
            "If present in underlying pacs.008/pacs.009, the Clearing System Reference must be transported in the pacs.004."),
    "R21": ("CBPR_Returned_Instructed_Rule_2_TextualRule",
            "If ReturnedInstructedAmount and ReturnedInterbankSettlementAmount are NOT expressed in the same "
            "currency: if ReturnedInstructedAmount is higher than ReturnedInterbankSettlementAmount when "
            "converted, Charge Information becomes mandatory."),
    "R24": ("CBPR_SHAR_TextualRule",
            "If deduct taken then charge information is mandatory. It is optional for initiator (not taking deduct)."),
    "R25": ("CBPR_Agent_Option_1_TextualRule",
            "BICFI, complemented optionally with a LEI (preferred option)."),
    "R26": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same "
            "country, the clearing code only may be used."),
    "R27": ("CBPR_Agent_Option_3_TextualRule",
            "Name AND ([Structured postal address with minimum Town Name and Country] OR [Hybrid postal "
            "address with minimum Town Name and Country]). It is recommended to also add the post code when available."),
    "R28": ("CBPR_Agent_Option_2_TextualRule",
            "(Clearing Code OR LEI) AND (Name AND ([Structured postal address with minimum Town Name and "
            "Country] OR [Hybrid postal address with minimum Town Name and Country])). It is recommended to "
            "also add the post code when available."),
    "R31": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available]."),
    "R32": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) within a "
            "country or for regions under same legislation (e.g. EEA)."),
    "R33": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country] AND (Identification: Private or Organisation)."),
    "R35": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country] OR [Hybrid postal address with "
            "minimum Town Name and Country]) AND (Account Number OR Identification). Not relevant in the "
            "current pacs.004 (Debtor Account is not present)."),
    "R38": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other). "
            "Not relevant in the current pacs.004 (Debtor Account is not present)."),
    "R39": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Debtor/Name is mandatory with either Debtor Account OR Debtor "
            "Identification within a country or for regions under same legislation (e.g. EEA)."),
    "R51": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country] OR [Hybrid postal address with "
            "minimum Town Name and Country]) AND (Account Number OR Identification). Not relevant in the "
            "current pacs.004 (Debtor Account is not present)."),
    "R54": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR "
            "Creditor Identification within a country or for regions under same legislation (e.g. EEA)."),
    "R56": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other). "
            "Not relevant in the current pacs.004 (Debtor Account is not present)."),
    "R59": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available]."),
    "R60": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) within a "
            "country or for regions under same legislation (e.g. EEA)."),
    "R62": ("CBPR_Originator_Identification_TextualRule",
            "If AnyBIC is present, in addition to any other optional elements, in case of conflicting "
            "information it will always take precedence."),
    "R66": ("CBPR_Agent_Point_To_Point_On_SWIFT_TextualRule",
            "If the transaction is exchanged on the SWIFT network, then BIC is mandatory and other elements "
            "are optional, e.g. LEI."),
    "R73": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R76": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country]) AND (Account Number OR "
            "Identification: Private or Organisation)."),
    "R79": ("CBPR_Agent_National_only_TextualRule",
            "Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same "
            "country, the clearing code only may be used."),
    "R82": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country]) AND (Account Number OR "
            "Identification: Private or Organisation)."),
    "R84": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R86": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation) within a "
            "country or for regions under same legislation (e.g. EEA)."),
    "R87": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available]. Other elements are optional."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
