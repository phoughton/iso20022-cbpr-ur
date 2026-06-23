from cbpr_rules import loader
from cbpr_rules.message import ParsedMessage


def _doc(ns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"):
    return f"""<?xml version="1.0"?>
<Wrapper>
  <AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">
    <Fr><FIId><FinInstnId><BICFI>AAAAGB2LXXX</BICFI></FinInstnId></FIId></Fr>
  </AppHdr>
  <Document xmlns="{ns}">
    <FIToFICstmrCdtTrf><GrpHdr><MsgId>X</MsgId></GrpHdr></FIToFICstmrCdtTrf>
  </Document>
</Wrapper>"""


def test_locate_finds_bah_and_document_under_wrapper():
    tree = loader.parse_string(_doc())
    bah, doc = loader.locate(tree)
    assert bah is not None and loader.local_name(bah) == "AppHdr"
    assert doc is not None and loader.local_name(doc) == "Document"


def test_detect_message_type():
    tree = loader.parse_string(_doc())
    _, doc = loader.locate(tree)
    assert loader.detect_message_type(doc) == "pacs.008"


def test_namespace_agnostic_path_and_line_numbers():
    tree = loader.parse_string(_doc())
    bah, doc = loader.locate(tree)
    msg = ParsedMessage(tree, bah, doc)
    nodes = msg.find("/AppHdr/Fr/FIId/FinInstnId/BICFI")
    assert len(nodes) == 1
    assert msg.text_of(nodes[0]) == "AAAAGB2LXXX"
    assert msg.line_of(nodes[0]) == 4  # 1-based source line


def test_no_appheader_is_tolerated():
    xml = """<?xml version="1.0"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf><GrpHdr><MsgId>X</MsgId></GrpHdr></FIToFICstmrCdtTrf>
</Document>"""
    tree = loader.parse_string(xml)
    bah, doc = loader.locate(tree)
    assert bah is None and doc is not None
    msg = ParsedMessage(tree, bah, doc)
    assert msg.find("/AppHdr/Fr") == []  # gracefully empty, no crash
