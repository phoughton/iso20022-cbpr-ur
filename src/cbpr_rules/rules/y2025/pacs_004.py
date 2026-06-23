"""CBPR+ SR2025 usage rules for pacs.004.001.09 (PaymentReturn).

Authored to mirror the pacs.008 reference module: shared combinators from
``helpers`` for the recurring presence/address/code patterns, bespoke
``fn(msg, report)`` checks for cross-field / cross-schema logic, and
``advisory`` registration for textual rules that are not mechanically
enforceable. Rule numbers, names and descriptions are taken from the
published guideline's Rules sheet; XML paths are the short ISO 20022 tags.
"""
from __future__ import annotations

import re

from ...registry import advisory, rule
from ...validators import is_valid_bic, is_valid_country, is_valid_currency, is_valid_lei
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
from decimal import Decimal, InvalidOperation

MT = "pacs.004"
YEAR = 2025
ROOT = "/Document/PmtRtr"
TX = ROOT + "/TxInf"


def reg(number, name, description, check):
    """Register a combinator-built check as a rule."""
    rule(MT, YEAR, number, name, description)(check)


def _commodity_ccy(path):
    """@Ccy on an amount must not be a commodity code (XAU/XAG/XPD/XPT)."""
    def check(msg, report):
        for el, ccy in msg.attr_nodes(path, "Ccy"):
            if ccy in {"XAU", "XAG", "XPD", "XPT"}:
                report(el, detail=f"commodity currency '{ccy}' not allowed")
    return check


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


@rule(MT, YEAR, "R1", 'CBPR_From_To_Instructing_Instructed_Agent_BIC_1_FormalRule',
      'BAH "From" BIC must match "Instructing Agent" BIC, except where BAH CopyDuplicate = COPY or = CODU BAH "To" BIC must match "Instructed Agent" BIC, except where BAH CopyDuplicate = COPY or = CODU')
def _r1(msg, report):
    if any(v in {"COPY", "CODU"} for v in msg.values("/AppHdr/CpyDplct")):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R2", 'CBPR_From_To_Instructing_Instructed_Agent_BIC_2_FormalRule',
      'BAH "From" BIC must match "Instructing Agent" BIC if CopyDuplicate is absent. BAH "To" BIC must match "Instructed Agent" BIC if CopyDuplicate is absent.')
def _r2(msg, report):
    if not msg.absent("/AppHdr/CpyDplct"):
        return
    for a, b, label in _BIC_PAIRS:
        _values_match(msg, report, a, b, label)


@rule(MT, YEAR, "R11", 'CBPR_CRED_FormalRule',
      'Charge information is mandatory if CRED is present – if no charges are taken, Zero must be used in "Amount" (any agent in the payment chain).')
def _r11(msg, report):
    for tx in msg.each(TX):
        cb = msg.values("ChrgBr", tx)
        if cb and all(v == "CRED" for v in cb) and msg.absent("ChrgsInf", tx):
            report(tx, detail="ChargesInformation required when ChargeBearer is CRED")


@rule(MT, YEAR, "R12", 'CBPR_Interbank_Settlement_Amount_FormalRule',
      'If TransactionInformation/OriginalInterbankSettlementAmount is present, then OriginalTransactionReference/InterbankSettlementAmount must not be used.')
def _r12(msg, report):
    for tx in msg.each(TX):
        if msg.present("OrgnlIntrBkSttlmAmt", tx) and msg.present("OrgnlTxRef/IntrBkSttlmAmt", tx):
            report(tx, detail="OriginalTransactionReference/InterbankSettlementAmount must be absent")


@rule(MT, YEAR, "R13", 'CBPR_Interbank_Settlement_Date_FormalRule',
      'If TransactionInformation/OriginalInterbankSettlementDate is present, then OriginalTransactionReference/InterbankSettlementDate must not be used.')
def _r13(msg, report):
    for tx in msg.each(TX):
        if msg.present("OrgnlIntrBkSttlmDt", tx) and msg.present("OrgnlTxRef/IntrBkSttlmDt", tx):
            report(tx, detail="OriginalTransactionReference/InterbankSettlementDate must be absent")


@rule(MT, YEAR, "R16", 'CBPR_Original_Message_Name_Identification_FormalRule',
      'This element should be populated with either pacs.002.001.xx or pacs.008.001.xx or pacs.009.001.xx or camt.053.001.xx or camt.054.001.xx or MT103 or MT202 or MT205 or MT 900 or MT910 or MT940 or MT950 when present.')
def _r16(msg, report):
    rx = re.compile(r'pacs\.00[289]\.001\.[0-9]{2}|camt\.05[34]\.001\.[0-9]{2}|MT103|MT202|MT205|MT900|MT910|MT940|MT950')
    for node in msg.find(TX + "/OrgnlGrpInf/OrgnlMsgNmId"):
        val = msg.text_of(node)
        if val and not rx.fullmatch(val):
            report(node, detail="OriginalMessageNameIdentification not an expected message identifier")


@rule(MT, YEAR, "R103", 'CBPR_Partial_Return_TextualRule',
      'In case of Partial Return, the "ReturnReasonInformation/Additional information" must take the fixed value "PART" and the "ReturnReasonInformation/Reason" must be populated with a code from the External reason code list.')
def _r103(msg, report):
    for tx in msg.each(TX):
        orig = msg.find("OrgnlIntrBkSttlmAmt", tx)
        rtrd = msg.find("RtrdIntrBkSttlmAmt", tx)
        if not orig or not rtrd:
            continue
        o_ccy, r_ccy = orig[0].get("Ccy"), rtrd[0].get("Ccy")
        if not o_ccy or o_ccy != r_ccy:
            continue
        try:
            ov = Decimal(msg.text_of(orig[0]))
            rv = Decimal(msg.text_of(rtrd[0]))
        except (InvalidOperation, ValueError):
            continue
        # Partial return only detectable when the returned amount is strictly
        # less than the original amount in the same currency.
        if rv >= ov:
            continue
        addtl = [msg.text_of(n) for n in msg.find("RtrRsnInf/AddtlInf", tx)]
        if not addtl or not any(v == "PART" for v in addtl):
            report(tx, detail='ReturnReasonInformation/AdditionalInformation must be "PART" for a partial return')
        elif msg.absent("RtrRsnInf/Rsn", tx):
            report(tx, detail="ReturnReasonInformation/Reason must be populated for a partial return")


# ---------------------------------------------------------------------------
# Formal rules implemented with shared combinators
# ---------------------------------------------------------------------------

reg('R4', 'CBPR_Business_Message_Identifier_TextualRule',
    'The Business Message Identifier must contain the Message Identification element from the Group Header of the underlying message, where available.',
    business_msg_id_carries_group_id())

reg('R5', 'CBPR_Message_Definition_Identifier_TextualRule',
    'The Message Definition Identifier must be formatted exactly as it appears in the namespace of the Business Message instance.',
    header_msg_def_id_matches())

reg('R25', 'CBPR_Returned_Instructed_Rule_1_TextualRule',
    'If ReturnedInstructedAmount and ReturnedInterbankSettlementAmount are expressed in the same currency and differ, Charge Information becomes mandatory.',
    charges_required_when_amounts_differ(TX, "RtrdInstdAmt", "RtrdIntrBkSttlmAmt", "ChrgsInf"))

reg('R35', 'CBPR_Duplication_Postal_Address_TextualRule',
    'Data present in structured elements within the Postal Address must not, under any circumstances be repeated in AddressLine.',
    no_postal_address_duplication())

reg('R46', 'CBPR_Debtor_BIC_Presence_TextualRule',
    'If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain optional).',
    bic_presence_exclusive('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Pty'))

reg('R92', 'CBPR_Creditor_BIC_Presence_TextualRule',
    'If Any BIC is present, then (Name and Postal Address) is NOT allowed (other elements remain optional).',
    bic_presence_exclusive('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Pty'))

reg('R18', 'CBPR_Original_Instruction_Identification_FormalRule',
    "This field must not start or end with a slash '/' and must not contain two consecutive slashes '//'.",
    not_matching_pattern('/Document/PmtRtr/TxInf/OrgnlInstrId', r"(/.*)|(.*/)|(.*//.*)"))

reg('R23', 'CBPR_Interbank_Settlement_Currency_FormalRule',
    'The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are only used for commodities.',
    _commodity_ccy('/Document/PmtRtr/TxInf/OrgnlIntrBkSttlmAmt'))

reg('R24', 'CBPR_Returned_Interbank_Settlement_Currency_FormalRule',
    'The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are only used for commodities.',
    _commodity_ccy('/Document/PmtRtr/TxInf/RtrdIntrBkSttlmAmt'))

reg('R32', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/ChrgsInf/Agt/FinInstnId', "Nm", "PstlAdr"))

reg('R33', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/ChrgsInf/Agt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R34', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/ChrgsInf/Agt/FinInstnId/PstlAdr'))

reg('R36', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/ChrgsInf/Agt/FinInstnId/PstlAdr', 35))

reg('R37', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/RtrChain/UltmtDbtr/Pty', "PstlAdr", "Nm"))

reg('R44', 'CBPR_Party_Name_Any_BIC_FormalRule',
    'If AnyBIC is absent then Name is mandatory and it is recommended to also provide the Postal Address.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Pty', "Id/OrgId/AnyBIC", ["Nm"]))

reg('R45', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Pty', "PstlAdr", "Nm"))

reg('R47', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Pty/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R48', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Pty/PstlAdr'))

reg('R49', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Pty/PstlAdr', 35))

reg('R50', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Agt/FinInstnId', "Nm", "PstlAdr"))

reg('R51', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Agt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R52', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Agt/FinInstnId/PstlAdr'))

reg('R53', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/Dbtr/Agt/FinInstnId/PstlAdr', 35))

reg('R54', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/RtrChain/InitgPty/Pty', "PstlAdr", "Nm"))

reg('R55', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/DbtrAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R56', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/DbtrAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R57', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/DbtrAgt/FinInstnId/PstlAdr'))

reg('R58', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/DbtrAgt/FinInstnId/PstlAdr', 35))

reg('R59', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt1/FinInstnId', "Nm", "PstlAdr"))

reg('R60', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt1/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R61', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt1/FinInstnId/PstlAdr'))

reg('R62', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt1/FinInstnId/PstlAdr', 35))

reg('R63', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt2/FinInstnId', "Nm", "PstlAdr"))

reg('R64', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt2/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R65', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt2/FinInstnId/PstlAdr'))

reg('R66', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt2/FinInstnId/PstlAdr', 35))

reg('R67', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt3/FinInstnId', "Nm", "PstlAdr"))

reg('R68', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt3/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R69', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt3/FinInstnId/PstlAdr'))

reg('R70', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/PrvsInstgAgt3/FinInstnId/PstlAdr', 35))

reg('R71', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt1/FinInstnId', "Nm", "PstlAdr"))

reg('R72', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt1/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R73', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt1/FinInstnId/PstlAdr'))

reg('R74', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt1/FinInstnId/PstlAdr', 35))

reg('R75', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt2/FinInstnId', "Nm", "PstlAdr"))

reg('R76', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt2/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R77', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt2/FinInstnId/PstlAdr'))

reg('R78', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt2/FinInstnId/PstlAdr', 35))

reg('R79', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt3/FinInstnId', "Nm", "PstlAdr"))

reg('R80', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt3/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R81', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt3/FinInstnId/PstlAdr'))

reg('R82', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/IntrmyAgt3/FinInstnId/PstlAdr', 35))

reg('R83', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/CdtrAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R84', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/CdtrAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R85', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/CdtrAgt/FinInstnId/PstlAdr'))

reg('R86', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/CdtrAgt/FinInstnId/PstlAdr', 35))

reg('R87', 'CBPR_Party_Name_Any_BIC_FormalRule',
    'If AnyBIC is absent then Name is mandatory and it is recommended to also provide the Postal Address.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Pty', "Id/OrgId/AnyBIC", ["Nm"]))

reg('R91', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Pty', "PstlAdr", "Nm"))

reg('R93', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Pty/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R94', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Pty/PstlAdr'))

reg('R95', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Pty/PstlAdr', 35))

reg('R96', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Agt/FinInstnId', "Nm", "PstlAdr"))

reg('R97', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Agt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R98', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Agt/FinInstnId/PstlAdr'))

reg('R99', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrChain/Cdtr/Agt/FinInstnId/PstlAdr', 35))

reg('R102', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/RtrChain/UltmtCdtr/Pty', "PstlAdr", "Nm"))

reg('R104', 'CBPR_Party_Name_Any_BIC_FormalRule',
    'If AnyBIC is absent, then Name is mandatory.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrRsnInf/Orgtr', "Id/OrgId/AnyBIC", ["Nm"]))

reg('R105', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/RtrRsnInf/Orgtr', "PstlAdr", "Nm"))

reg('R107', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/RtrRsnInf/Orgtr/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R108', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/RtrRsnInf/Orgtr/PstlAdr'))

reg('R109', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/RtrRsnInf/Orgtr/PstlAdr', 35))

reg('R111', 'CBPR_Interbank_Settlement_Currency_FormalRule',
    'The codes XAU, XAG, XPD and XPT are not allowed, as these are codes are only used for commodities.',
    _commodity_ccy('/Document/PmtRtr/TxInf/OrgnlTxRef/IntrBkSttlmAmt'))

reg('R112', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrSchmeId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R113', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrSchmeId/PstlAdr'))

reg('R114', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrSchmeId/PstlAdr', 35))

reg('R116', 'CBPR_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstgRmbrsmntAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R117', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstgRmbrsmntAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R118', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstgRmbrsmntAgt/FinInstnId/PstlAdr'))

reg('R119', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstgRmbrsmntAgt/FinInstnId/PstlAdr', 35))

reg('R120', 'CBPR_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstdRmbrsmntAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R121', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstdRmbrsmntAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R122', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstdRmbrsmntAgt/FinInstnId/PstlAdr'))

reg('R123', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/InstdRmbrsmntAgt/FinInstnId/PstlAdr', 35))

reg('R124', 'CBPR_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/ThrdRmbrsmntAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R125', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/ThrdRmbrsmntAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R126', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/ThrdRmbrsmntAgt/FinInstnId/PstlAdr'))

reg('R127', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/SttlmInf/ThrdRmbrsmntAgt/FinInstnId/PstlAdr', 35))

reg('R130', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlCdtrSchmeId/PstlAdr'))

reg('R131', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlCdtrSchmeId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R132', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlCdtrSchmeId/PstlAdr', 35))

reg('R133', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlCdtrAgt/FinInstnId/PstlAdr', 35))

reg('R134', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlCdtrAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R135', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlCdtrAgt/FinInstnId/PstlAdr'))

reg('R136', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlDbtr/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R137', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlDbtr/PstlAdr', 35))

reg('R138', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlDbtr/PstlAdr'))

reg('R139', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlDbtrAgt/FinInstnId/PstlAdr'))

reg('R140', 'CBPR_GracePeriod_Structured_FormalRule',
    'If Postal Address is used, and if Address Line is absent, then Town Name and Country must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlDbtrAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R141', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/MndtRltdInf/AmdmntInfDtls/OrgnlDbtrAgt/FinInstnId/PstlAdr', 35))

reg('R142', 'CBPR_Remittance_Mutually_Exclusive_FormalRule',
    'Either Structured or Unstructured Remittance can be present.',
    mutually_exclusive('/Document/PmtRtr/TxInf/OrgnlTxRef/RmtInf', ["Ustrd", "Strd"]))

reg('R145', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/OrgnlTxRef/UltmtDbtr/Pty', "PstlAdr", "Nm"))

reg('R149', 'CBPR_Name_Any_BIC_FormalRule',
    'If AnyBIC is Absent Then Name is mandatory.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Pty', "Id/OrgId/AnyBIC", ["Nm"]))

reg('R150', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Pty', "PstlAdr", "Nm"))

reg('R151', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Pty/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R152', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Pty/PstlAdr'))

reg('R153', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Pty/PstlAdr', 35))

reg('R154', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Agt/FinInstnId', "Nm", "PstlAdr"))

reg('R155', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Agt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R156', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Agt/FinInstnId/PstlAdr'))

reg('R157', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/Dbtr/Agt/FinInstnId/PstlAdr', 35))

reg('R158', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/DbtrAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R159', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/DbtrAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R160', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/DbtrAgt/FinInstnId/PstlAdr'))

reg('R161', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/DbtrAgt/FinInstnId/PstlAdr', 35))

reg('R163', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrAgt/FinInstnId', "Nm", "PstlAdr"))

reg('R164', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrAgt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R165', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrAgt/FinInstnId/PstlAdr'))

reg('R166', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/CdtrAgt/FinInstnId/PstlAdr', 35))

reg('R169', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Pty', "PstlAdr", "Nm"))

reg('R170', 'CBPR_Name_Any_BIC_FormalRule',
    'If AnyBIC is Absent Then Name is mandatory.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Pty', "Id/OrgId/AnyBIC", ["Nm"]))

reg('R171', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Pty/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R172', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Pty/PstlAdr'))

reg('R173', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Pty/PstlAdr', 35))

reg('R174', 'CBPR_Agent_Name_Postal_Address_FormalRule',
    'Name and Address must always be present together.',
    presence_together('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Agt/FinInstnId', "Nm", "PstlAdr"))

reg('R175', 'CBPR_GracePeriod_Structured_FormalRule',
    'If “PostalAddress” is used, and if AddressLine is absent, then Country and Town Name must be present.',
    required_when_absent('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Agt/FinInstnId/PstlAdr', "AdrLine", ["TwnNm", "Ctry"]))

reg('R176', 'CBPR_GracePeriod_Hybrid_FormalRule',
    'If Address Line is present and any other Postal Address element(s) are present, then Town Name and Country are mandatory in Postal Address and a maximum of two occurrences of Address Line are allowed.',
    address_hybrid('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Agt/FinInstnId/PstlAdr'))

reg('R177', 'CBPR_GracePeriod_Unstructured_FormalRule',
    'If Postal Address is present and if no other element than Address Line is present then every occurrence of Address Line must not exceed 35 characters.',
    address_lines_max_length('/Document/PmtRtr/TxInf/OrgnlTxRef/Cdtr/Agt/FinInstnId/PstlAdr', 35))

reg('R180', 'CBPR_Party_Name_Postal_Address_FormalRule',
    'If Postal Address is present then Name is mandatory.',
    requires_if_present('/Document/PmtRtr/TxInf/OrgnlTxRef/UltmtCdtr/Pty', "PstlAdr", "Nm"))

# ---------------------------------------------------------------------------
# Mechanizable textual rule
# ---------------------------------------------------------------------------
reg('R6', 'CBPR_Business_Service_Usage_TextualRule',
    'The value "swift.cbprplus.03" must be used.',
    code_in("/AppHdr/BizSvc", ["swift.cbprplus.03"]))

# ---------------------------------------------------------------------------
# Algorithmic field validation (project brief)
# ---------------------------------------------------------------------------
OTR = TX + "/OrgnlTxRef"
RC = TX + "/RtrChain"


def _run_all(*checks):
    """Combine several builder-produced checks into one ``check(msg, report)``."""
    def check(msg, report):
        for c in checks:
            c(msg, report)
    return check


def _valid_ccy(path):
    def check(msg, report):
        for el, ccy in msg.attr_nodes(path, "Ccy"):
            if ccy and not is_valid_currency(ccy):
                report(el, detail=f"invalid currency '{ccy}'")
    return check


reg("VAL-CCY", "CBPR_Valid_Settlement_Currency",
    "Settlement amount currencies must be valid ISO 4217 codes.",
    _run_all(
        _valid_ccy(TX + "/OrgnlIntrBkSttlmAmt"),
        _valid_ccy(TX + "/RtrdIntrBkSttlmAmt"),
        _valid_ccy(TX + "/RtrdInstdAmt"),
        _valid_ccy(OTR + "/IntrBkSttlmAmt"),
    ))

reg("VAL-BIC", "CBPR_Valid_Agent_BIC",
    "Instructing/Instructed Agent BICFI must be a structurally valid BIC.",
    _run_all(
        each_value_valid(TX + "/InstgAgt/FinInstnId/BICFI", is_valid_bic, "BIC"),
        each_value_valid(TX + "/InstdAgt/FinInstnId/BICFI", is_valid_bic, "BIC"),
    ))

reg("VAL-LEI", "CBPR_Valid_Agent_LEI",
    "Every Agent LEI must be a structurally valid LEI.",
    _run_all(
        each_value_valid(TX + "/InstgAgt/FinInstnId/LEI", is_valid_lei, "LEI"),
        each_value_valid(TX + "/InstdAgt/FinInstnId/LEI", is_valid_lei, "LEI"),
    ))

reg("VAL-CTRY", "CBPR_Valid_Country",
    "Every Country code must be a valid ISO 3166 country code.",
    _run_all(
        each_value_valid(RC + "/Dbtr/Pty/PstlAdr/Ctry", is_valid_country, "country"),
        each_value_valid(RC + "/Cdtr/Pty/PstlAdr/Ctry", is_valid_country, "country"),
        each_value_valid(OTR + "/Dbtr/Pty/PstlAdr/Ctry", is_valid_country, "country"),
        each_value_valid(OTR + "/Cdtr/Pty/PstlAdr/Ctry", is_valid_country, "country"),
    ))

# ---------------------------------------------------------------------------
# Advisory textual / guideline rules (not mechanically enforceable)
# ---------------------------------------------------------------------------
_ADVISORY = [
    ('R3', 'CBPR_Character_Set_Usage_TextualRule',
     'For further description on the usage of the field, pls refer to the CBPR Plus UHB.'),
    ('R7', 'CBPR_Business_Service_TextualRule',
     'This field may be used by SWIFT to support differentiated processing on SWIFT-administered services such as FINplus. For a description of reserved values, please refer to the Service Description for your service. To support differentiated processing on CBPRPlus, for example, SWIFT reserves a set of values that conform to a specific format. A user-specific value may be used, but please contact your Service Administrator before doing so to ensure alignment with general practice on your service.'),
    ('R8', 'CBPR_Market_Practice_TextualRule',
     'This field may be used by SWIFT on SWIFT-administered services. For a description of reserved values, please refer to the Service Description for your service. Contact your Service Administrator for further clarification, if necessary. A user-specific value may be used, but please contact your Service Administrator before doing so to ensure alignment with general practice on your service.'),
    ('R9', 'CBPR_Related_Business_Application_Header_TextualRule',
     'If used, the Related BAH must transport the exact same information as in the BAH of the related message.'),
    ('R10', 'CBPR_Related_BAH_Business_Service_TextualRule',
     'If related BAH is present, it should transport the element Business Service.'),
    ('R14', 'CBPR_Return_Chain_TextualRule',
     'It is highly recommended for the returning party to populate the Original Information, if pacs.004 follows the original payment route.'),
    ('R15', 'CBPR_Original_Message_Identification_TextualRule',
     'Original Message Identification must transport the Message Identification of the underlying payment (eg. pacs.008/pacs.009)'),
    ('R17', 'CBPR_Original_Instruction_Identification_TextualRule',
     'If present in underlying pacs.008/pacs.009, the Instruction Identification must be transported in pacs.004.'),
    ('R19', 'CBPR_Original_End_To_End_Identification_TextualRule',
     'If present in underlying pacs.008/pacs.009, the EndToEnd Identification must be transported in pacs.004.'),
    ('R20', 'CBPR_Original_Transaction_Identification_TextualRule',
     'If present in underlying pacs.008/pacs.009, the Transaction Identification must be transported in the pacs.004.'),
    ('R21', 'CBPR_Original_UETR_TextualRule',
     'Must transport the UETR of the underlying pacs.008/pacs.009'),
    ('R22', 'CBPR_Original_Clearing_System_Reference_TextualRule',
     'If present in underlying pacs.008/pacs.009, the Clearing System Reference must be transported in the pacs.004.'),
    ('R26', 'CBPR_Returned_Instructed_Rule_2_TextualRule',
     'If ReturnedInstructedAmount and ReturnedInterbankSettlementAmount are NOT expressed in the same currency: If ReturnedInstructedAmount is higher than ReturnedInterbankSettlementAmount WHEN converted in the same currency, Charge Information becomes mandatory.'),
    ('R27', 'CBPR_SHAR_TextualRule',
     'If deduct taken then charge information is mandatory. It is optional for initiator (not taking deduct).'),
    ('R28', 'CBPR_Agent_National_only_TextualRule',
     'Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same country, the clearing code only may be used.'),
    ('R29', 'CBPR_Agent_Option_1_TextualRule',
     'BICFI, complemented optionally with a LEI (preferred option)'),
    ('R30', 'CBPR_Agent_Option_2_TextualRule',
     '(Clearing Code OR LEI) AND (Name AND (Unstructured postal address OR [Structured postal address with minimum Town Name and Country] OR [Hybrid postal address with minimum Town Name and Country]). It is recommended to also add the post code when available.'),
    ('R31', 'CBPR_Agent_Option_3_TextualRule',
     'Name AND (Unstructured OR [Structured postal address with minimum Town Name and Country] OR [Hybrid postal address with minimum Town Name and Country]). It is recommended to also add the post code when available.'),
    ('R38', 'CBPR_UltimateDebtor_Option_3_Jurisdictions_only_TextualRule',
     'For Jurisdictional transactions, Name and/or Identification (Private or Organisation (that is within a country or for regions under same legislations – eg EEA) Countries impacted by the Jurisdictional rule: Belgium, Bulgaria, Czechia, Denmark, Germany, Estonia, Ireland, Greece, Spain, France, Croatia, Italy, Cyprus, Latvia, Lithuania, Luxembourg, Hungary, Malta, Netherlands, Austria, Poland, Portugal, Romania, Slovenia, Slovakia, Finland, Sweden - Iceland, Liechtenstein, Norway. Note: The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction.'),
    ('R39', 'CBPR_Ultimate_Debtor_Option_1_TextualRule',
     'Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)'),
    ('R40', 'CBPR_Ultimate_Debtor_Option_2_TextualRule',
     'Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country- it is recommended to add Post code when available] AND (Identification: Private or Organisation)'),
    ('R41', 'CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule',
     'For Jurisdictional transactions, Debtor/ Name is mandatory with either Debtor Account OR Debtor Identification (that is within a country or for regions under same legislations – eg EEA) Countries impacted by the Jurisdictional rule: Belgium, Bulgaria, Czechia, Denmark, Germany, Estonia, Ireland, Greece, Spain, France, Croatia, Italy, Cyprus, Latvia, Lithuania, Luxembourg, Hungary, Malta, Netherlands, Austria, Poland, Portugal, Romania, Slovenia, Slovakia, Finland, Sweden - Iceland, Liechtenstein, Norway. Note: The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction.'),
    ('R42', 'CBPR_Debtor_Option_1_TextualRule',
     'Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other) CBPR_Debtor_Option1 is not relevant with current version of the pacs.004 (since Debtor Account is not present). It will be applicable in the next version of the pacs.004 base message.'),
    ('R43', 'CBPR_Debtor_Option_2_TextualRule',
     'Name AND (Unstructured OR [Structured Address with minimumTown Name & Country (+ recommended to add Post code when available)]OR [Hybrid postal address with minimum Town Name and Country (+ recommended to add Post code when available)] AND (Account Number OR Identification: Private or Organisation) CBPR_Debtor_Option2 is not relevant with current version of the pacs.004 (since Debtor Account is not present). It will be applicable in the next version of the pacs.004 base message.'),
    ('R88', 'CBPR_Creditor_Option_3_Jurisdictions_only_TextualRule',
     'For Jurisdictional transactions, Creditor/Name is mandatory with either Creditor Account OR Creditor Identification (that is within a country or for regions under same legislations – eg EEA) Countries impacted by the Jurisdictional rule: Belgium, Bulgaria, Czechia, Denmark, Germany, Estonia, Ireland, Greece, Spain, France, Croatia, Italy, Cyprus, Latvia, Lithuania, Luxembourg, Hungary, Malta, Netherlands, Austria, Poland, Portugal, Romania, Slovenia, Slovakia, Finland, Sweden - Iceland, Liechtenstein, Norway. Note: The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction.'),
    ('R89', 'CBPR_Creditor_Option_1_TextualRule',
     'Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other) Textual rule is not relevant with current version of the pacs.004 (since Debtor Account is not present). It will be applicable in the next version of the pacs.004 base message.'),
    ('R90', 'CBPR_Creditor_Option_2_TextualRule',
     'Name AND (Unstructured OR [Structured Address with minimumTown Name & Country (+ recommended to add Post code when available)]OR [Hybrid postal address with minimum Town Name and Country (+ recommended to add Post code when available)) AND (Account Number OR Identification: Private or Organisation) Textual rule is not relevant with current version of the pacs.004 (since Debtor Account is not present). It will be applicable in the next version of the pacs.004 base message.'),
    ('R100', 'CBPR_Ultimate_Creditor_Option_1_TextualRule',
     'Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)].'),
    ('R101', 'CBPR_UltimateCreditor_Option_2_Jurisdictions_only_TextualRule',
     'For Jurisdictional transactions, Name and/or Identification (Private or Organisation (that is within a country or for regions under same legislations – eg EEA) Countries impacted by the Jurisdictional rule: Belgium, Bulgaria, Czechia, Denmark, Germany, Estonia, Ireland, Greece, Spain, France, Croatia, Italy, Cyprus, Latvia, Lithuania, Luxembourg, Hungary, Malta, Netherlands, Austria, Poland, Portugal, Romania, Slovenia, Slovakia, Finland, Sweden- Iceland, Liechtenstein, Norway. Note: The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction.'),
    ('R106', 'CBPR_Originator_Identification_TextualRule',
     'If AnyBIC is present, in addition to any other optional elements, in case of conflicting information it will always take precedence.'),
    ('R110', 'CBPR_Return_Chain_TextualRule',
     'It is highly recommended for the returning party to populate the Original Information, if pacs.004 follows the original payment route.'),
    ('R115', 'CBPR_Agent_Point_To_Point_On_SWIFT_TextualRule',
     'If the transaction is exchanged on the SWIFT network (ie if the sender and receiver of the message are on SWIFT), then BIC is mandatory and other elements are optional, eg LEI'),
    ('R128', 'CBPR_Local_Instrument_Guideline',
     'The preferred option is coded information.'),
    ('R129', 'CBPR_Category_Purpose_TextualRule',
     'The preferred option is coded information.'),
    ('R143', 'CBPR_Remittance_Rules_TextualRule',
     '1. Use of Structured Remittance must be bilaterally or multilaterally agreed 2. Structured Remittance can be repeated, however the total business data for all occurrences (excluding tags) must not exceed 9,000 characters.'),
    ('R144', 'CBPR_Ultimate_Debtor_Option_1_TextualRule',
     'Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)'),
    ('R146', 'CBPR_Debtor_Option_3_Jurisdictions_only_TextualRule',
     'For Jurisdictional transactions, Debtor/ Name is mandatory with either Debtor Account OR Debtor Identification (that is within a country or for regions under same legislations – eg EEA) Countries impacted by the Jurisdictional rule: Belgium, Bulgaria, Czechia, Denmark, Germany, Estonia, Ireland, Greece, Spain, France, Croatia, Italy, Cyprus, Latvia, Lithuania, Luxembourg, Hungary, Malta, Netherlands, Austria, Poland, Portugal, Romania, Slovenia, Slovakia, Finland, Sweden - Iceland, Liechtenstein, Norway. Note: The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction.'),
    ('R147', 'CBPR_Debtor_Option_1_TextualRule',
     'Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)'),
    ('R148', 'CBPR_Debtor_Option_2_TextualRule',
     'Name AND (Unstructured OR [Structured Address with minimumTown Name & Country (+ recommended to add Postal code when available)]) AND (Account Number OR Identification: Private or Organisation)'),
    ('R162', 'CBPR_Agent_National_only_TextualRule',
     'Whenever Debtor Agent, Creditor Agent and all agents in between are located within the same country, the clearing code only may be used..'),
    ('R167', 'CBPR_Creditor_Option_1_TextualRule',
     'Organisation Identification/AnyBIC AND (Account Number OR Organisation Identification/Other)'),
    ('R168', 'CBPR_Creditor_Option_2_TextualRule',
     'Name AND (Unstructured OR [Structured Address with minimumTown Name & Country (+ recommended to add Postal code when available)]) AND (Account Number OR Identification: Private or Organisation)'),
    ('R178', 'CBPR_Ultimate_Creditor_Option_1_TextualRule',
     'Name AND [(Structured Postal Address) OR (Hybrid Postal Address) with minimum Town Name & Country - it is recommended to add Post code when available)]. Other elements are optional, eg Identification: Private or Organisation'),
    ('R179', 'CBPR_Ultimate_Creditor_Option_2_Jurisdictions_only_TextualRule',
     'For Jurisdictional transactions, Name and/or Identification (Private or Organisation (that is within a country or for regions under same legislations – eg EEA) Countries impacted by the Jurisdictional rule: Belgium, Bulgaria, Czechia, Denmark, Germany, Estonia, Ireland, Greece, Spain, France, Croatia, Italy, Cyprus, Latvia, Lithuania, Luxembourg, Hungary, Malta, Netherlands, Austria, Poland, Portugal, Romania, Slovenia, Slovakia, Finland, Sweden - Iceland, Liechtenstein, Norway. Note: The jurisdictional rules apply only when all agents in the payment chain underly the same jurisdiction.'),
    ('R181', 'CBPR_Purpose_Guideline',
     'The preferred option is coded information.'),
]
for _num, _name, _desc in _ADVISORY:
    advisory(MT, YEAR, _num, _name, _desc)

