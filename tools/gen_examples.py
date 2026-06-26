"""Dev-time generator for bundled min/max example messages (NOT shipped).

Walks the enriched CBPR+ XSDs (under ``raw_rules_files/<year>/<type>/``) to build
a *minimum* (mandatory fields only) and *maximum* (every field populated, one
representative occurrence, richest single choice branch) instance of each message
type, wraps the AppHdr + Document in an <Envelope>, anonymises all data from a
fictitious value bank, then repairs and GATES each file: it is only written to
``src/cbpr_rules/examples/`` once it passes BOTH the usage-rule engine (0
violations) and the enriched Document + head.001 XSDs.

Usage:
    python tools/gen_examples.py 2025 pacs.008        # one type
    python tools/gen_examples.py 2025                 # all types for a year
    python tools/gen_examples.py                      # everything (2025+2026)
"""
from __future__ import annotations

import glob
import os
import re
import sys

from lxml import etree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cbpr_rules import validate_string  # noqa: E402
from cbpr_rules.engine import _normalise_xsd  # noqa: E402
from cbpr_rules import schema as _schema  # noqa: E402
from cbpr_rules import loader as _loader  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(REPO, "raw_rules_files")
OUT = os.path.join(REPO, "src", "cbpr_rules", "examples")
XS = "{http://www.w3.org/2001/XMLSchema}"

# Canonical msgtype -> raw_rules_files subfolder name (same string).
MSGTYPES = [
    "pacs.008", "pacs.008_stp", "pacs.009", "pacs.009_cov", "pacs.009_adv",
    "pacs.004", "pacs.002", "pain.001", "camt.052", "camt.054",
]

from cbpr_rules import idgen  # noqa: E402

DATETIME = "2026-01-01T10:00:00+00:00"
DATE = "2026-01-01"
TIME = "10:00:00+00:00"

# Per-example value bank, filled deterministically by idgen from the seed
# `{mode}_{year}_{msgtype}` at the start of each generation. Cross-field usage
# rules are satisfied by reusing one value per role (From == InstructingAgt,
# etc.); the leg countries (from=GB, to=US) keep the debtor/creditor agent
# couple cross-border (avoids the domestic-couple rules). See _set_bank.
BANK = {
    "bic_from": "EXMPGB2LXXX", "bic_to": "EXMPUS33XXX",
    "iban": "GB82WEST12345698765432", "lei": "529900T8BM49AURSDO55",
    "uetr": "11111111-1111-4111-8111-111111111111",
}


def _set_bank(seed):
    BANK["bic_from"] = idgen.generate_bic(country="GB", seed=f"{seed}:from")
    BANK["bic_to"] = idgen.generate_bic(country="US", seed=f"{seed}:to")
    BANK["iban"] = idgen.generate_iban("GB", seed=f"{seed}:iban")
    BANK["lei"] = idgen.generate_lei(seed=f"{seed}:lei")
    BANK["uetr"] = idgen.generate_uetr(idgen.deterministic_int(f"{seed}:uetr", 1, 2**63))

# Optional elements whose content we cannot meaningfully synthesise (xmldsig
# signature, open SupplementaryData). Skipped during generation.
SKIP_ELEMENTS = {"Sgntr", "SplmtryData", "SupplementaryData"}

# Allowed CBPR+ business service code per message type (rule R7/R8 family).
BIZ_SVC = {
    "pacs.008": "swift.cbprplus.03", "pacs.008_stp": "swift.cbprplus.stp.03",
    "pacs.009": "swift.cbprplus.03", "pacs.009_cov": "swift.cbprplus.cov.03",
    "pacs.009_adv": "swift.cbprplus.adv.03", "pacs.004": "swift.cbprplus.03",
    "pacs.002": "swift.cbprplus.03", "pain.001": "swift.cbprplus.03",
    "camt.052": "swift.cbprplus.03", "camt.054": "swift.cbprplus.03",
}


def _localname(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else tag


class Schema:
    """Parsed XSD: named complex/simple types and the top-level element."""

    def __init__(self, path):
        self.root = etree.parse(path).getroot()
        self.tns = self.root.get("targetNamespace")
        self.complex = {}
        self.simple = {}
        self.top = {}
        for ct in self.root.findall(f"{XS}complexType"):
            if ct.get("name"):
                self.complex[ct.get("name")] = ct
        for st in self.root.findall(f"{XS}simpleType"):
            if st.get("name"):
                self.simple[st.get("name")] = st
        for el in self.root.findall(f"{XS}element"):
            if el.get("name"):
                self.top[el.get("name")] = el


def _enum_values(st_node):
    return [e.get("value") for e in st_node.iter(f"{XS}enumeration")]


def _restriction(st_node):
    return st_node.find(f"{XS}restriction")


def _text_for_simple(schema, type_name, st_node, elem_name):
    """Pick a schema-valid, anonymised value for a simple type from the bank."""
    name = type_name or ""
    en = elem_name or ""
    # By well-known ISO 20022 type name.
    if "BICFI" in name or "AnyBIC" in name:
        return BANK["bic_from"]
    if "IBAN" in name:
        return BANK["iban"]
    if "LEIIdentifier" in name:
        return BANK["lei"]
    if "UUID" in name or en == "UETR":
        return BANK["uetr"]
    if "CountryCode" in name or name == "Country":
        return "GB"
    if "CurrencyCode" in name:
        return "EUR"
    if "CurrencyAndAmount" in name:  # amount text part
        return "1000.00"
    # Date/time by ISO type name (covers cases where the simpleType node isn't resolved).
    if name == "ISODateTime" or name.endswith("DateTime"):
        return DATETIME
    if "YearMonth" in name:
        return "2026-01"
    if name == "ISOTime" or (name.endswith("Time") and "Date" not in name):
        return TIME
    if name == "ISODate" or name.endswith("Date"):
        return DATE
    # By the simpleType's restriction (authoritative for date/time/number).
    if st_node is not None:
        enums = _enum_values(st_node)
        if enums:
            return enums[0]
        rstr = _restriction(st_node)
        if rstr is not None:
            base = rstr.get("base", "")
            pat = rstr.find(f"{XS}pattern")
            if "dateTime" in base:
                return DATETIME
            if base.endswith("}time") or base == "xs:time":
                return TIME
            if "date" in base:
                return DATE
            if "decimal" in base or "Decimal" in name:
                return "1000.00"
            if "boolean" in base:
                return "true"
            if any(t in base for t in ("integer", "Number", "Count", "nonNegative")):
                return "1"
            if pat is not None:
                v = _from_pattern(pat.get("value"))
                if v is not None:
                    return v
            ml = rstr.find(f"{XS}maxLength")
            mn = rstr.find(f"{XS}minLength")
            maxlen = int(ml.get("value")) if ml is not None else 35
            minlen = int(mn.get("value")) if mn is not None else 1
            return _text_value(en, maxlen, minlen)
    if "Decimal" in name or "Rate" in name:
        return "1000.00"
    return _text_value(en, 35, 1)


def _from_pattern(pat):
    """Generator for the simple ISO patterns we hit; None if unknown."""
    if pat is None:
        return None
    p = pat
    if "{8,8}-" in p or "4[a-f0-9]" in p.lower() or "uuid" in p.lower():
        return BANK["uetr"]
    # Phone number, e.g. \+[0-9]{1,3}-[0-9()+\-]{1,30}
    if p.startswith(r"\+") or p.startswith("[+]") or p.startswith("+"):
        return "+1-1234567890"
    if "[A-Z0-9]{4,4}[A-Z]{2,2}" in p:  # BIC
        return BANK["bic_from"]
    if "[A-Z]{2,2}[A-Z0-9]{9,9}" in p:  # ISIN: 2 letters + 9 alnum + 1 digit
        return "GB0000000001"
    if p.startswith("[A-Z]{2"):
        return "GB"
    if p.startswith("[A-Z]{3"):
        return "EUR"
    if p.startswith("[a-z]{2"):  # language code
        return "en"
    # Pure numeric text (digits, optional sign, quantifiers) e.g. [0-9]{8,28},
    # [+]{0,1}[0-9]{1,15} — return the minimum required number of digits.
    if "[0-9]" in p and re.fullmatch(r"[\[\]0-9{},+\\ -]+", p):
        m = re.search(r"\[0-9\]\{(\d+)", p)
        n = int(m.group(1)) if m else 1
        return "1" * max(n, 1)
    return None


def _text_value(elem_name, maxlen, minlen=1):
    """Safe, space-free token honouring FIN-restricted text patterns."""
    base = re.sub(r"[^A-Za-z0-9]", "", f"EX{elem_name}") or "EX"
    base = base[:maxlen]
    if len(base) < minlen:
        base = (base + "0" * minlen)[:max(minlen, len(base))]
    return base


def _content_particles(schema, ct_node):
    """Yield the top content-model node (sequence/choice) of a complexType."""
    for child in ct_node:
        ln = _localname(child.tag)
        if ln in ("sequence", "choice", "all"):
            return child
        if ln == "complexContent":
            ext = child.find(f"{XS}extension") or child.find(f"{XS}restriction")
            if ext is not None:
                for c in ext:
                    if _localname(c.tag) in ("sequence", "choice", "all"):
                        return c
    return None


def _simple_content(ct_node):
    return ct_node.find(f"{XS}simpleContent")


def _count_elements(schema, type_name, depth, seen):
    """Rough richness of a type (for picking the max choice branch)."""
    if depth > 12 or not type_name or type_name in seen:
        return 0
    ct = schema.complex.get(type_name)
    if ct is None:
        return 1
    model = _content_particles(schema, ct)
    if model is None:
        return 1
    total = 0
    for el in model.findall(f"{XS}element"):
        total += 1 + _count_elements(
            schema, el.get("type"), depth + 1, seen | {type_name}
        )
    for ch in model.findall(f"{XS}choice"):
        opts = [_count_elements(schema, e.get("type"), depth + 1, seen | {type_name})
                for e in ch.findall(f"{XS}element")]
        total += max(opts) if opts else 0
    return total


def _build_element(schema, el_def, mode, ns, depth, seen):
    """Build an lxml element for an xs:element definition, or None to omit."""
    name = el_def.get("name") or el_def.get("ref")
    type_name = el_def.get("type")
    node = etree.SubElement(_PARENT[-1], f"{{{ns}}}{name}")
    # inline simpleType?
    inline_simple = el_def.find(f"{XS}simpleType")
    inline_complex = el_def.find(f"{XS}complexType")

    if type_name and type_name in schema.complex:
        _fill_complex(schema, node, schema.complex[type_name], type_name, mode, ns, depth, seen)
    elif inline_complex is not None:
        _fill_complex(schema, node, inline_complex, None, mode, ns, depth, seen)
    else:
        st = schema.simple.get(type_name) if type_name else inline_simple
        node.text = _text_for_simple(schema, type_name, st, name)
    return node


_PARENT = []  # stack of current parent element


def _fill_complex(schema, node, ct_node, type_name, mode, ns, depth, seen):
    # simpleContent extension (e.g. amount with Ccy attribute)
    sc = _simple_content(ct_node)
    if sc is not None:
        ext = sc.find(f"{XS}extension")
        base = ext.get("base") if ext is not None else None
        node.text = _text_for_simple(schema, base, schema.simple.get(base), _localname(node.tag))
        if ext is not None:
            for attr in ext.findall(f"{XS}attribute"):
                if attr.get("use") == "required" or mode == "max":
                    aname = attr.get("name")
                    atype = attr.get("type")
                    node.set(aname, _text_for_simple(schema, atype, schema.simple.get(atype), aname))
        return

    if depth > 14 or (type_name and type_name in seen):
        return
    model = _content_particles(schema, ct_node)
    if model is None:
        return
    seen = seen | ({type_name} if type_name else set())
    _PARENT.append(node)
    try:
        _fill_model(schema, model, mode, ns, depth, seen)
    finally:
        _PARENT.pop()


def _fill_model(schema, model, mode, ns, depth, seen):
    ln = _localname(model.tag)
    if ln == "choice":
        options = list(model.findall(f"{XS}element")) + list(model.findall(f"{XS}sequence"))
        if not options:
            return
        if mode == "max":
            # richest branch
            def richness(opt):
                if _localname(opt.tag) == "element":
                    return 1 + _count_elements(schema, opt.get("type"), depth, seen)
                return sum(1 + _count_elements(schema, e.get("type"), depth, seen)
                           for e in opt.findall(f"{XS}element"))
            chosen = max(options, key=richness)
        else:
            min_occurs = model.get("minOccurs", "1")
            if min_occurs == "0":
                return  # whole choice optional -> omit in min
            chosen = min(options, key=lambda o: len(o.findall(f"{XS}element")) or 1)
        _emit_particle(schema, chosen, mode, ns, depth, seen)
        return
    # sequence / all
    for child in model:
        cln = _localname(child.tag)
        if cln in ("element", "choice", "sequence"):
            _emit_particle(schema, child, mode, ns, depth, seen)


def _emit_particle(schema, particle, mode, ns, depth, seen):
    ln = _localname(particle.tag)
    if ln == "element":
        min_occurs = particle.get("minOccurs", "1")
        if mode == "min" and min_occurs == "0":
            return
        if (particle.get("name") or particle.get("ref")) in SKIP_ELEMENTS:
            return
        _build_element(schema, particle, mode, ns, depth + 1, seen)
    elif ln in ("sequence", "choice", "all"):
        min_occurs = particle.get("minOccurs", "1")
        if mode == "min" and min_occurs == "0":
            return
        _fill_model(schema, particle, mode, ns, depth, seen)


def build_document(doc_xsd_path, mode):
    schema = Schema(doc_xsd_path)
    ns = schema.tns
    top = schema.top["Document"]
    root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
    _PARENT.append(root)
    try:
        ct = schema.complex[top.get("type")]
        _fill_complex(schema, root, ct, top.get("type"), mode, ns, 0, set())
    finally:
        _PARENT.pop()
    return root, ns


def build_apphdr(hdr_xsd_path, mode):
    schema = Schema(hdr_xsd_path)
    ns = schema.tns
    top = schema.top["AppHdr"]
    root = etree.Element(f"{{{ns}}}AppHdr", nsmap={None: ns})
    _PARENT.append(root)
    try:
        ct = schema.complex[top.get("type")]
        _fill_complex(schema, root, ct, top.get("type"), mode, ns, 0, set())
    finally:
        _PARENT.pop()
    return root, ns


def _find_xsd(year, msgtype):
    folder = os.path.join(RAW, str(year), msgtype)
    cands = glob.glob(os.path.join(folder, "*iso15enriched.xsd"))
    return cands[0] if cands else None


def _head_xsd(year):
    cands = glob.glob(os.path.join(RAW, str(year), "head.001", "*.xsd"))
    return cands[0] if cands else None


def generate(year, msgtype, mode):
    doc_xsd = _find_xsd(year, msgtype)
    hdr_xsd = _head_xsd(year)
    if not doc_xsd or not hdr_xsd:
        return None, f"missing XSD for {msgtype} {year}"
    _set_bank(f"{mode}_{year}_{msgtype}")
    doc, doc_ns = build_document(doc_xsd, mode)
    hdr, hdr_ns = build_apphdr(hdr_xsd, mode)
    env = etree.Element("Envelope")
    env.append(hdr)
    env.append(doc)
    _repair(env, doc_ns, msgtype, year)
    return env, (doc_xsd, hdr_xsd)


def _iter_local(root, name):
    return [e for e in root.iter() if _localname(e.tag) == name]


def _children(node, name):
    return [c for c in node if _localname(c.tag) == name]


def _resolve_rel(node, relpath):
    """Resolve a '/'-separated local-name path under node; return leaf nodes."""
    cur = [node]
    for seg in relpath.split("/"):
        nxt = []
        for n in cur:
            nxt.extend(_children(n, seg))
        cur = nxt
    return cur


def _resolve(root, xpath):
    """Resolve our xpath_of-style path (local names, optional [n]) to a node."""
    segs = [s for s in xpath.strip("/").split("/") if s]
    if not segs:
        return None
    node = root
    if _localname(node.tag) != re.sub(r"\[\d+\]$", "", segs[0]):
        return None
    for seg in segs[1:]:
        m = re.match(r"(.+?)\[(\d+)\]$", seg)
        name, idx = (m.group(1), int(m.group(2)) - 1) if m else (seg, 0)
        kids = _children(node, name)
        if idx >= len(kids):
            return None
        node = kids[idx]
    return node


_BIC_TO_ANC = {"To", "InstdAgt", "InstdRmbrsmntAgt", "CdtrAgt", "Cdtr"}
_BIC_FROM_ANC = {"Fr", "InstgAgt", "InstgRmbrsmntAgt", "DbtrAgt", "Dbtr"}


def _bic_side(el):
    anc = el
    while anc is not None:
        ln = _localname(anc.tag)
        if ln in _BIC_TO_ANC:
            return BANK["bic_to"]
        if ln in _BIC_FROM_ANC:
            return BANK["bic_from"]
        anc = anc.getparent()
    return BANK["bic_from"]


def _postprocess(env, doc_ns, msgtype):
    """Enforce common cross-field usage rules deterministically."""
    defn = doc_ns.split("tech:xsd:", 1)[-1]
    for n in _iter_local(env, "MsgDefIdr"):
        n.text = defn
    msgids = _iter_local(env, "MsgId")
    grp_msgid = msgids[0].text if msgids else "EXMSG0001"
    for n in _iter_local(env, "BizMsgIdr"):
        n.text = grp_msgid
    # Business service code (BAH BizSvc).
    for n in _iter_local(env, "BizSvc"):
        n.text = BIZ_SVC.get(msgtype, "swift.cbprplus.03")
    # BAH Priority must equal Document InstrPrty.
    instr = _iter_local(env, "InstrPrty")
    for n in _iter_local(env, "Prty"):
        n.text = instr[0].text if instr else "NORM"
    # BICFI by leg: From/Instructing/DebtorAgent = GB; To/Instructed/CreditorAgent = DE.
    # Keeps From==InstructingAgent / To==InstructedAgent while making the debtor/creditor
    # agent country couple cross-border (avoids domestic-couple usage rules).
    for n in _iter_local(env, "BICFI"):
        n.text = _bic_side(n)
    # Original message identifiers must be a real ISO message id.
    for n in _iter_local(env, "OrgnlMsgNmId"):
        n.text = "pacs.008.001.08"
    # pain.001: PaymentInformationIdentification must equal GroupHeader MessageIdentification.
    for n in _iter_local(env, "PmtInfId"):
        n.text = grp_msgid
    # Avoid charge-bearer rules that demand ChargesInformation. SHAR is in every
    # CBPR+ ChargeBearer enum (incl. pacs.004, which omits DEBT) and is not CRED.
    for n in _iter_local(env, "ChrgBr"):
        n.text = "SHAR"
    # pacs.004: the original settlement amount/date must not be duplicated inside
    # OriginalTransactionReference when the top-level original fields are present.
    for otr in _iter_local(env, "OrgnlTxRef"):
        for nm in ("IntrBkSttlmAmt", "IntrBkSttlmDt"):
            for leaf in _children(otr, nm):
                otr.remove(leaf)


def _repair(env, doc_ns, msgtype, year, max_passes=40):
    """Validator-driven repair: resolve usage violations until clean or stuck."""
    for _ in range(max_passes):
        _postprocess(env, doc_ns, msgtype)
        xml = etree.tostring(env, encoding="UTF-8").decode()
        viols = validate_string(xml, year, msgtype)["violations"]
        if not viols:
            return
        # Apply exactly ONE fix per pass, then re-validate: removing elements
        # shifts positional [n] indices, so other violations' xpaths would go
        # stale within a pass.
        if not _apply_one_fix(env, doc_ns, viols):
            return


def _apply_one_fix(env, doc_ns, viols):
    for v in viols:
        d = v.get("detail", "") or ""
        node = _resolve(env, v["xpath"])
        if node is None:
            continue
        if d.startswith("mutually exclusive:"):
            names = [x.strip() for x in d.split(":", 1)[1].split(",")]
            present = [nm for nm in names if _resolve_rel(node, nm)]
            for nm in present[1:]:
                for leaf in _resolve_rel(node, nm):
                    leaf.getparent().remove(leaf)
            if present[1:]:
                return True
        elif "cannot be present when" in d:
            fb = d.split(" cannot", 1)[0].strip()
            leaves = _resolve_rel(node, fb)
            for leaf in leaves:
                leaf.getparent().remove(leaf)
            if leaves:
                return True
        elif d == "element must not be used":  # must_be_absent combinator: node is the element
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                return True
        elif "required when" in d and "is absent" in d:
            req = d.split(" required", 1)[0].strip()
            for nm in [r.strip() for r in re.split(r"\band\b|,", req)]:
                if "/" in nm or not nm or _children(node, nm):
                    continue
                child = etree.Element(f"{{{doc_ns}}}{nm}")
                child.text = "EXAMPLE PARTY NV" if nm == "Nm" else "EX"
                node.insert(0, child)  # these elements lead their sequence
                return True
    return False


def write_if_valid(year, msgtype, mode, env, xsds):
    xml = etree.tostring(env, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode()
    res = validate_string(xml, year, msgtype)
    viol = res["violations"]
    # XSD gate
    tree = _loader.parse_string(xml)
    bah, doc = _loader.locate(tree)
    sch = _schema.validate_with_xsds(tree, bah, doc, list(xsds))
    schema_ok = sch["schema_valid"]
    status = f"{msgtype} {year} {mode}: {len(viol)} usage viol, schema_ok={schema_ok}"
    if viol or not schema_ok:
        return False, status, viol, sch
    out_dir = os.path.join(OUT, f"y{year}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{msgtype}.{mode}.xml"), "w") as f:
        f.write(xml)
    return True, status, viol, sch


def main():
    years = [2025, 2026]
    types = MSGTYPES
    if len(sys.argv) >= 2:
        years = [int(sys.argv[1])]
    if len(sys.argv) >= 3:
        types = [sys.argv[2]]
    for year in years:
        for mt in types:
            for mode in ("min", "max"):
                env, xsds = generate(year, mt, mode)
                if env is None:
                    print(f"SKIP {mt} {year} {mode}: {xsds}")
                    continue
                ok, status, viol, sch = write_if_valid(year, mt, mode, env, xsds)
                print(("OK   " if ok else "FAIL ") + status)
                if not ok:
                    for v in viol[:6]:
                        print(f"      usage {v['rule_number']}: {v.get('detail') or v['description']}")
                    for s in sch["schemas"]:
                        for e in s["errors"][:4]:
                            print(f"      xsd  line {e.get('line')}: {e['message'][:90]}")


if __name__ == "__main__":
    main()
