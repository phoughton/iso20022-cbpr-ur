"""CBPR+ SR2026 usage rules for pacs.008.001.08 STP (FIToFICustomerCreditTransfer).

Structure mirrors the reference module ``rules.y2025.pacs_008``: each Rules-sheet
R-index is registered with its real rule number, name token and description, using
shared combinators where the formal logic matches a known shape and bespoke
``fn(msg, report)`` checks otherwise. Algorithmic field validations are added as
extra VAL-* rules for the data types that appear in this message.
"""
from __future__ import annotations

import re

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
    requires_if_present,
    required_when_absent,
    same_value,
)

MT = "pacs.008_stp"
YEAR = 2026
ROOT = "/Document/FIToFICstmrCdtTrf"
TX = ROOT + "/CdtTrfTxInf"

D_PARTY_NAME_ADR = "If Postal Address is present then Name is mandatory."
D_PARTY_ANY_BIC = (
    "If AnyBIC is absent then Name is mandatory and it is recommended to also "
    "provide the Postal Address."
)


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
# BAH / cross-schema consistency
# ---------------------------------------------------------------------------
reg("R1", "CBPR_BusinessMessageIdentifier_FormalRule",
    "The Business Message Identifier must match the Message Identification in the Group Header.",
    same_value("/AppHdr/BizMsgIdr", ROOT + "/GrpHdr/MsgId"))


@rule(MT, YEAR, "R2", "CBPR_Priority_Instruction_Priority_FormalRule",
      'If "Priority" is used in the BAH for pacs messages, the value should be '
      'identical to the one in the Payment Type Information/InstructionPriority if present.')
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


reg("R5", "CBPR_From_Instructing_Agent_BIC_FormalRule",
    'BAH "From" BIC must match "Instructing Agent" BIC',
    same_value("/AppHdr/Fr/FIId/FinInstnId/BICFI", TX + "/InstgAgt/FinInstnId/BICFI"))


# ---------------------------------------------------------------------------
# Service level / remittance / charges
# ---------------------------------------------------------------------------
@rule(MT, YEAR, "R10", "CBPR_GPI_ServiceLevel_Code_FormalRule",
      "The GPI ServiceLevel Code in pacs.008 STP must be 'G001'.")
def _r10(msg, report):
    forbidden = {"G002", "G003", "G004", "G005", "G006", "G007", "G009"}
    for doc in msg.each(ROOT):
        if msg.absent("CdtTrfTxInf/PmtTpInf/SvcLvl", doc):
            continue
        for node in msg.find("CdtTrfTxInf/PmtTpInf/SvcLvl/Cd", doc):
            if msg.text_of(node) in forbidden:
                report(node, detail="ServiceLevel Code must be G001")


reg("R11", "CBPR_Related_Remit_Info_Remit_Info_Mutually_Exclusive_FormalRule",
    "In the interbank space, Related Remittance Information and Remittance "
    "Information are mutually exclusive and all may be absent.",
    mutually_exclusive(TX, ["RltdRmtInf", "RmtInf"]))


# ---------------------------------------------------------------------------
# Domestic / jurisdiction country-couple rules (R12, R15-R18)
# ---------------------------------------------------------------------------
def _bic_country(bic: str) -> str:
    return bic[4:6] if bic and len(bic) >= 6 else ""


def _domestic_name_iban(number: str, name: str, description: str, countries):
    """Debtor/Creditor agent BICs both in `countries` => Debtor & Creditor Name +
    Account/IBAN must be present."""
    cset = set(countries)

    @rule(MT, YEAR, number, name, description)
    def _check(msg, report, _cset=cset):
        for tx in msg.each(TX):
            dbtr_bics = msg.values("DbtrAgt/FinInstnId/BICFI", tx)
            cdtr_bics = msg.values("CdtrAgt/FinInstnId/BICFI", tx)
            if not dbtr_bics or not cdtr_bics:
                continue
            if not all(_bic_country(b) in _cset for b in dbtr_bics):
                continue
            if not all(_bic_country(b) in _cset for b in cdtr_bics):
                continue
            required = {
                "Debtor/Name": "Dbtr/Nm",
                "Creditor/Name": "Cdtr/Nm",
                "DebtorAccount/IBAN": "DbtrAcct/Id/IBAN",
                "CreditorAccount/IBAN": "CdtrAcct/Id/IBAN",
            }
            missing = [lbl for lbl, p in required.items() if msg.absent(p, tx)]
            if missing:
                report(tx, detail="domestic transaction requires " + ", ".join(missing))


_SEPA = ["AT", "BE", "BG", "BV", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
         "GB", "GF", "GI", "GP", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT",
         "LU", "LV", "MQ", "MT", "NL", "NO", "PL", "PM", "PT", "RE", "RO", "SE",
         "SI", "SJ", "SK"]

_domestic_name_iban(
    "R12", "CBPR_Debtor_Creditor_IBAN_FormalRule",
    "IF Creditor Agent and Debtor Agent BICs are part of following countries: "
    "AT, BE, BG, BV, CY, CZ, DE, DK, EE, ES, FI, FR, GB, GF, GI, GP, GR, HR, HU, "
    "IE, IS, IT, LI, LT, LU, LV, MQ (FR), MT, NL, NO, PL, PM (FR), PT, RE (FR), "
    "RO, SE, SI, SJ, SK Then: Debtor and Creditor must be identified using a "
    "Name and the Account/IBAN.",
    _SEPA)

_domestic_name_iban(
    "R15", "CBPR_Debtor_Creditor_IT/VA_FormalRule",
    "Transactions exchanged within these country couples are considered as "
    "domestic ones. IF Creditor Agent and Debtor Agent BICs are part of "
    "following countries: IT, VA Then: Debtor and Creditor must be identified "
    "using a Name and the Account/IBAN.",
    ["IT", "VA"])

_domestic_name_iban(
    "R16", "CBPR_Debtor_Creditor_FR/MC_FormalRule",
    "Transactions exchanged within these country couples are considered as "
    "domestic ones. IF Creditor Agent and Debtor Agent BICs are part of "
    "following countries: FR, MC Then: Debtor and Creditor must be identified "
    "using a Name and the Account/IBAN.",
    ["FR", "MC"])

_domestic_name_iban(
    "R17", "CBPR_Debtor_Creditor_ES/AD_FormalRule",
    "Transactions exchanged within these country couples are considered as "
    "domestic ones. IF Creditor Agent and Debtor Agent BICs are part of "
    "following countries: ES, AD Then: Debtor and Creditor must be identified "
    "using a Name and the Account/IBAN.",
    ["ES", "AD"])

_domestic_name_iban(
    "R18", "CBPR_Debtor_Creditor_IT/SM_FormalRule",
    "Transactions exchanged within these country couples are considered as "
    "domestic ones. IF Creditor Agent and Debtor Agent BICs are part of "
    "following countries: IT, SM Then: Debtor and Creditor must be identified "
    "using a Name and the Account/IBAN.",
    ["IT", "SM"])


@rule(MT, YEAR, "R13", "CBPR_DEBT_FormalRule",
      'If "Charge Bearer/DEBT" is present, then only one occurrence of '
      '"Charge Information" is allowed.')
def _r13(msg, report):
    for tx in msg.each(TX):
        if "DEBT" in msg.values("ChrgBr", tx) and len(msg.find("ChrgsInf", tx)) > 1:
            report(tx, detail="only one ChargesInformation allowed when ChargeBearer is DEBT")


@rule(MT, YEAR, "R14", "CBPR_CRED_FormalRule",
      "Charge information is mandatory if CRED is present - if no charges are "
      'taken, Zero must be used in "Amount" (any agent in the payment chain).')
def _r14(msg, report):
    for tx in msg.each(TX):
        cb = msg.values("ChrgBr", tx)
        if cb and all(v == "CRED" for v in cb) and msg.absent("ChrgsInf", tx):
            report(tx, detail="ChargesInformation required when ChargeBearer is CRED")


reg("R19", "CBPR_Instruction_Identification_FormalRule",
    "This element must not start or end with a slash '/' and must not contain "
    "two consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R21", "CBPR_Interbank_Settlement_Currency_FormalRule",
      "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
      "only used for commodities.")
def _r21(msg, report):
    for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy"):
        if ccy in {"XAU", "XAG", "XPD", "XPT"}:
            report(el, detail=f"commodity currency '{ccy}' not allowed")


# ---------------------------------------------------------------------------
# Party name / postal address / AnyBIC (formal)
# ---------------------------------------------------------------------------
def _party_name_adr(number: str, party: str) -> None:
    reg(number, "CBPR_Party_Name_Postal_Address_FormalRule", D_PARTY_NAME_ADR,
        requires_if_present(party, "PstlAdr", "Nm"))


_party_name_adr("R28", TX + "/UltmtDbtr")
_party_name_adr("R30", TX + "/InitgPty")
_party_name_adr("R31", TX + "/Dbtr")
_party_name_adr("R40", TX + "/Cdtr")
_party_name_adr("R43", TX + "/UltmtCdtr")


def _party_any_bic(number: str, party: str) -> None:
    reg(number, "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
        required_when_absent(party, "Id/OrgId/AnyBIC", ["Nm"]))


_party_any_bic("R33", TX + "/Dbtr")
_party_any_bic("R41", TX + "/Cdtr")


# ---------------------------------------------------------------------------
# Promoted from advisory to enforced (conservative, no false positives)
# ---------------------------------------------------------------------------
reg("R7", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business "
    "Message instance that is being transported with this header, as defined by "
    "the sending application or system. Must contain the Message Identification "
    "element from the Group Header of the underlying message, where available.",
    business_msg_id_carries_group_id())

reg("R8", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is "
    "being transported with this header. In general, it must be formatted exactly "
    "as it appears in the namespace of the Business Message instance.",
    header_msg_def_id_matches())

reg("R23", "CBPR_DEBT_Rule_1_TextualRule",
    "If Instructed amount and Interbank Settlement Amount are expressed in the "
    "same currency: if Charge Bearer/DEBT is used then Charge Information is only "
    "mandatory in case of prepaid charges and in that case zero amount is not "
    "allowed; otherwise Charge information is optional.",
    charges_required_when_amounts_differ(TX, "InstdAmt", "IntrBkSttlmAmt", "ChrgsInf"))

reg("R29", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, "
    "under any circumstances be repeated in AddressLine.",
    no_postal_address_duplication())

reg("R35", "CBPR_Debtor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other "
    "elements remain optional). However, in case of conflicting information, "
    "AnyBIC will always take precedence.",
    bic_presence_exclusive(TX + "/Dbtr"))

reg("R38", "CBPR_Creditor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other "
    "elements remain optional). However, in case of conflicting information, "
    "AnyBIC will always take precedence.",
    bic_presence_exclusive(TX + "/Cdtr"))


@rule(MT, YEAR, "R20", "CBPR_EndToEndIdentification_TextualRule",
      "If no EndToEndIdentification is provided by the Debtor, then the element "
      'must be populated with "NOTPROVIDED".')
def _r20(msg, report):
    for node in msg.find(TX + "/PmtId/EndToEndId"):
        if not msg.text_of(node).strip():
            report(node, detail='EndToEndIdentification must be populated (use "NOTPROVIDED" when none provided)')


# ---------------------------------------------------------------------------
# Algorithmic field validation (VAL-*) - only for fields present in this message
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
    "R9": ("CBPR_RelatedBAHBusinessService_TextualRule",
           "If related BAH is present, it should transport the element Business Service."),
    "R22": ("CBPR_DEBT_Rule_2_TextualRule",
            "If Instructed amount and Interbank Settlement Amount are not expressed in the same currency: if Charge Bearer/DEBT is used then Charge Information is only mandatory in case of prepaid charges and in that case zero amount is not allowed; otherwise Charge information is optional."),
    "R24": ("CBPR_SHAR_TextualRule",
            "If deduct taken then charge information is mandatory. It is optional for initiator (not taking deduct)."),
    "R25": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available] AND (Identification: Private or Organisation)."),
    "R26": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation). The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R27": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)."),
    "R32": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Debtor/Name is mandatory with either Debtor Account OR Debtor Identification. The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R34": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country (+ recommended to add Postal code when available)]) AND (Account Number OR Identification: Private or Organisation)."),
    "R36": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R37": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)."),
    "R39": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND ([Structured Address with minimum Town Name & Country (+ recommended to add Postal code when available)]) AND (Account Number OR Identification: Private or Organisation)."),
    "R42": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR Creditor Identification. The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R44": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)]. Other elements are optional, e.g. Identification: Private or Organisation."),
    "R45": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation). The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
