"""CBPR+ SR2025 usage rules for pacs.008.001.08 STP (FIToFICustomerCreditTransfer).

Mirrors the reference module ``pacs_008``: each Rules-sheet R-index is registered
with its real number, name token and description, implemented either with a shared
combinator from ``helpers`` or a bespoke ``fn(msg, report)`` for cross-field logic.
Textual rules that are mechanizable are enforced; the rest are advisory.

Rule numbers and text are taken from the published STP usage guideline's Rules
sheet; XML paths are the short ISO 20022 tags from its translated XML Path column.
"""
from __future__ import annotations

import re as _re

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
)

MT = "pacs.008_stp"
YEAR = 2025
ROOT = "/Document/FIToFICstmrCdtTrf"
TX = ROOT + "/CdtTrfTxInf"

# Repeated rule descriptions (identical across the locations they apply to).
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
    "If Postal Address is present and if no other element than AddressLine is "
    "present then every occurrence of Address line must no exceed 35 characters."
)


def reg(number: str, name: str, description: str, check) -> None:
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _party_block(party_path: str, n_name_adr: str, name_token: str,
                 n_struct=None, n_hybrid=None, n_unstruct=None) -> None:
    reg(n_name_adr, name_token, D_PARTY_NAME_ADR,
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
      'CopyDuplicate = COPY or = CODU BAH "To" BIC must match "Instructed Agent" '
      "BIC, except where BAH CopyDuplicate = COPY or = CODU")
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


reg("R12", "CBPR_Related_Remit_Info_Remit_Info_Mutually_Exclusive_FormalRule",
    "In the interbank space, Related Remittance Information and Remittance "
    "Information are mutually exclusive and all may be absent.",
    mutually_exclusive(TX, ["RltdRmtInf", "RmtInf"]))


@rule(MT, YEAR, "R13", "CBPR_CRED_FormalRule",
      "Charge information is mandatory if CRED is present – if no charges are "
      'taken, Zero must be used in "Amount" (any agent in the payment chain).')
def _r13(msg, report):
    for tx in msg.each(TX):
        cb = msg.values("ChrgBr", tx)
        if cb and all(v == "CRED" for v in cb) and msg.absent("ChrgsInf", tx):
            report(tx, detail="ChargesInformation required when ChargeBearer is CRED")


# R14-R18: domestic "country couple" rules. When both Debtor Agent and Creditor
# Agent BICs fall in the listed countries (positions 5-6 of the BIC), the Debtor
# and Creditor must both carry a Name and an Account/IBAN.
def _country_couple(number: str, name_token: str, desc: str, countries):
    rx = _re.compile(r".{4}(" + "|".join(countries) + r").*")

    def check(msg, report):
        for tx in msg.each(TX):
            dbt_agt = msg.values("DbtrAgt/FinInstnId/BICFI", tx)
            cdt_agt = msg.values("CdtrAgt/FinInstnId/BICFI", tx)
            if not dbt_agt or not cdt_agt:
                return
            if not all(rx.fullmatch(v) for v in dbt_agt):
                continue
            if not all(rx.fullmatch(v) for v in cdt_agt):
                continue
            ok = (msg.present("Dbtr/Nm", tx) and msg.present("Cdtr/Nm", tx)
                  and msg.present("DbtrAcct/Id/IBAN", tx)
                  and msg.present("CdtrAcct/Id/IBAN", tx))
            if not ok:
                report(tx, detail="Debtor/Creditor Name and Account/IBAN required for domestic country couple")

    rule(MT, YEAR, number, name_token, desc)(check)


_CC_DESC = (
    "Transactions exchanged within these country couples are considered as "
    "domestic ones. IF Creditor Agent and Debtor Agent BICs are part of "
    "following countries: {cc} Then: Debtor and Creditor must be identified "
    "using a Name and the Account/IBAN."
)
_country_couple("R14", "CBPR_Debtor_Creditor_ES/AD_FormalRule",
                _CC_DESC.format(cc="ES, AD"), ["ES", "AD"])
_country_couple("R15", "CBPR_Debtor_Creditor_FR/MC_FormalRule",
                _CC_DESC.format(cc="FR, MC"), ["FR", "MC"])
_country_couple("R16", "CBPR_Debtor_Creditor_IT/SM_FormalRule",
                _CC_DESC.format(cc="IT, SM"), ["IT", "SM"])
_country_couple("R17", "CBPR_Debtor_Creditor_IT/VA_FormalRule",
                _CC_DESC.format(cc="IT, VA"), ["IT", "VA"])

_IBAN_COUNTRIES = [
    "AT", "BE", "BG", "BV", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GB", "GF", "GI", "GP", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT",
    "LU", "LV", "MQ", "MT", "NL", "NO", "PL", "PM", "PT", "RE", "RO", "SE",
    "SI", "SJ", "SK",
]
_country_couple(
    "R18", "CBPR_Debtor_Creditor_IBAN_FormalRule",
    "IF Creditor Agent and Debtor Agent BICs are part of following countries: "
    "AT, BE, BG, BV, CY, CZ, DE, DK, EE, ES, FI, FR, GB, GF, GI, GP, GR, HR, "
    "HU, IE, IS, IT, LI, LT, LU, LV, MQ (FR), MT, NL, NO, PL, PM (FR), PT, RE "
    "(FR), RO, SE, SI, SJ, SK Then: Debtor and Creditor must be identified "
    "using a Name and the Account/IBAN.",
    _IBAN_COUNTRIES)


@rule(MT, YEAR, "R19", "CBPR_DEBT_FormalRule",
      'If "Charge Bearer/DEBT" is present, then only one occurrence of '
      '"Charge Information" is allowed.')
def _r19(msg, report):
    for tx in msg.each(TX):
        if "DEBT" in msg.values("ChrgBr", tx) and len(msg.find("ChrgsInf", tx)) > 1:
            report(tx, detail="only one ChargesInformation allowed when ChargeBearer is DEBT")


reg("R20", "CBPR_Instruction_Identification_FormalRule",
    "This field must not start or end with a slash '/' and must not contain two "
    "consecutive slashes '//'.",
    not_matching_pattern(TX + "/PmtId/InstrId", r"(/.*)|(.*/)|(.*//.*)"))


@rule(MT, YEAR, "R21", "CBPR_Interbank_Settlement_Currency_FormalRule",
      "The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are "
      "only used for commodities.")
def _r21(msg, report):
    for el, ccy in msg.attr_nodes(TX + "/IntrBkSttlmAmt", "Ccy"):
        if ccy in {"XAU", "XAG", "XPD", "XPT"}:
            report(el, detail=f"commodity currency '{ccy}' not allowed")


# Parties (name/postal + grace period blocks where applicable)
_party_block(TX + "/UltmtDbtr", "R28", "CBPR_Party_Name_Postal_Address_FormalRule")
_party_block(TX + "/InitgPty", "R30", "CBPR_Party_Name_Postal_Address_FormalRule")
_party_block(TX + "/Dbtr", "R34", "CBPR_Party_Name_Postal_Address_FormalRule",
             "R37", "R38", "R39")
_party_block(TX + "/Cdtr", "R40", "CBPR_Party_Name_Postal_Address_FormalRule",
             "R46", "R47", "R48")
_party_block(TX + "/UltmtCdtr", "R51", "CBPR_Name_Postal_Address_FormalRule")


def _party_any_bic(number: str, party: str) -> None:
    reg(number, "CBPR_Party_Name_Any_BIC_FormalRule", D_PARTY_ANY_BIC,
        required_when_absent(party, "Id/OrgId/AnyBIC", ["Nm"]))


_party_any_bic("R35", TX + "/Dbtr")
_party_any_bic("R44", TX + "/Cdtr")


# ---------------------------------------------------------------------------
# Mechanizable textual rules + algorithmic field validation
# ---------------------------------------------------------------------------
reg("R8", "CBPR_Business_Service_Usage_TextualRule",
    'The value "swift.cbprplus.stp.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.stp.03"]))


reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"))


# ---------------------------------------------------------------------------
# Promoted from advisory: mechanizable textual rules now enforced.
# ---------------------------------------------------------------------------
reg("R5", "CBPR_Business_Message_Identifier_TextualRule",
    "The Business Message Identifier is the unique identifier of the Business Message instance "
    "that is being transported with this header, as defined by the sending application or system. "
    "Must contain the Message Identification element from the Group Header of the underlying "
    "message, where available.",
    business_msg_id_carries_group_id())

reg("R6", "CBPR_Message_Definition_Identifier_TextualRule",
    "The Message Definition Identifier of the Business Message instance that is being transported "
    "with this header. In general, it must be formatted exactly as it appears in the namespace of "
    "the Business Message instance.",
    header_msg_def_id_matches())

reg("R22", "CBPR_DEBT_Rule_1_TextualRule",
    "If Instructed amount and Interbank Settlement Amount are expressed in the same currency: "
    "If Charge Bearer/DEBT is used then Charge Information is only mandatory in case of prepaid "
    "charges (that is if Interbank Settlement Amount is higher than Instructed Amount) and in "
    "that case zero amount is not allowed.",
    charges_required_when_amounts_differ(TX, "InstdAmt", "IntrBkSttlmAmt", "ChrgsInf"))

reg("R29", "CBPR_Duplication_Postal_Address_TextualRule",
    "Data present in structured elements within the Postal Address must not, under any circumstances "
    "be repeated in AddressLine.",
    no_postal_address_duplication())

reg("R36", "CBPR_Debtor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain "
    "optional) - However, in case of conflicting information, AnyBIC will always take precedence.",
    bic_presence_exclusive(TX + "/Dbtr"))

reg("R45", "CBPR_Creditor_BIC_Presence_TextualRule",
    "If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain "
    "optional) - However, in case of conflicting information, AnyBIC will always take precedence.",
    bic_presence_exclusive(TX + "/Cdtr"))


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
           "This field may be used by SWIFT on SWIFT-administered services."),
    "R10": ("CBPR_Related_Business_Application_Header_TextualRule",
            "If used, the Related BAH must transport the exact same information as in the BAH of the related message."),
    "R11": ("CBPR_RelatedBAHBusinessService_TextualRule",
            "If related BAH is present, it should transport the element Business Service."),
    "R23": ("CBPR_DEBT_Rule_2_TextualRule",
            "If Instructed amount and Interbank Settlement Amount are not expressed in the same currency: "
            "If Charge Bearer/DEBT is used then Charge Information is only mandatory in case of prepaid "
            "charges (that is if Interbank Settlement Amount is higher than Instructed Amount WHEN "
            "converted in the same currency) and in that case zero amount is not allowed."),
    "R24": ("CBPR_SHAR_TextualRule",
            "If deduct taken then charge information is mandatory. It is optional for initiator (not taking deduct)."),
    "R25": ("CBPR_Ultimate_Debtor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available)"),
    "R26": ("CBPR_Ultimate_Debtor_Option_2_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available] AND (Identification: Private or Organisation)"),
    "R27": ("CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation). "
            "The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
    "R31": ("CBPR_Debtor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)"),
    "R32": ("CBPR_Debtor_Option_2_TextualRule",
            "Name AND (Unstructured OR [Structured Address with minimum Town Name & Country (+ recommended "
            "to add Postal code when available)]) AND (Account Number OR Identification: Private or Organisation)"),
    "R33": ("CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Debtor/Name is mandatory with either Debtor Account OR Debtor "
            "Identification. The jurisdictional rules apply only when all agents in the payment chain underly "
            "the same jurisdiction."),
    "R41": ("CBPR_Creditor_Option_1_TextualRule",
            "Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)"),
    "R42": ("CBPR_Creditor_Option_2_TextualRule",
            "Name AND (Unstructured OR [Structured Address with minimum Town Name & Country (+ recommended "
            "to add Postal code when available)]) AND (Account Number OR Identification: Private or Organisation)"),
    "R43": ("CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR "
            "Creditor Identification. The jurisdictional rules apply only when all agents in the payment "
            "chain underly the same jurisdiction."),
    "R49": ("CBPR_Ultimate_Creditor_Option_1_TextualRule",
            "Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & "
            "Country - it is recommended to add Post code when available)]. Other elements are optional."),
    "R50": ("CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule",
            "For Jurisdictional transactions, Name and/or Identification (Private or Organisation). "
            "The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction."),
}
for _num, (_name, _desc) in _ADVISORY.items():
    advisory(MT, YEAR, _num, _name, _desc)
