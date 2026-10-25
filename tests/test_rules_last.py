"""`rules last`: DesignSpace processing="last" (1.5.x)."""

from fontTools.designspaceLib import DesignSpaceDocument

import dssketch
from dssketch import Sketch, apply_edits, diagnose, tokenize
from dssketch.structure import build

TEXT = """\
family A
axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900
sources [wght]
    A-Thin [Thin]
    A-Regular [Regular] @base
    A-Black [Black]
rules{mode}  # swaps
    dollar > dollar.alt (weight >= Black)
"""


def text(mode=""):
    return TEXT.format(mode=mode)


def to_ds(t):
    return dssketch.convert_dss_string_to_designspace(t, font_data=dssketch.FontData())


def test_parsed_and_converted():
    assert dssketch.DSSParser().parse(text(" last")).rules_processing_last
    assert not dssketch.DSSParser().parse(text()).rules_processing_last
    assert not dssketch.DSSParser().parse(text(" first")).rules_processing_last
    assert to_ds(text(" last")).rulesProcessingLast
    assert not to_ds(text()).rulesProcessingLast


def test_round_trip():
    ds = to_ds(text(" last"))
    back = dssketch.convert_designspace_to_dss_string(ds)
    assert "\nrules last\n" in back
    ds2 = to_ds(back)
    assert ds2.rulesProcessingLast


def test_unknown_mode_is_an_error():
    found = [d for d in diagnose(text(" lats")) if d.severity == "error"]
    assert [d.code for d in found] == [dssketch.codes.CODES["RULES_MODE_UNKNOWN"].id]
    assert found[0].line == 11


def test_tokens_and_structure():
    tokens = [t for t in tokenize(text(" last")) if t.line == 11]
    assert [(t.text, t.type) for t in tokens][:2] == [("rules", "keyword"), ("last", "keyword")]
    header = build(text(" last")).section_header("rules")
    assert header.values["mode"] == "last"


def test_completion_offers_last():
    found = dssketch.complete("rules ", 1, 6)
    assert "last" in [c.text for c in found]


def test_sketch_op():
    sk = Sketch.parse(text())
    r = sk.set_rules_processing(True)
    assert "rules last  # swaps" in r.text and apply_edits(sk.text, r.edits) == r.text
    r2 = r.sketch.set_rules_processing(False)
    assert r2.text == text()
    assert r2.sketch.set_rules_processing(False).edits == []
    assert Sketch.parse(text(" first")).set_rules_processing(True).text == text(" last")


def test_sketch_op_adds_section():
    t = text().split("rules")[0]
    r = Sketch.parse(t).set_rules_processing(True)
    assert "\nrules last\n" in r.text + "\n"


def test_apply_designspace_carries_it():
    ds = to_ds(text())
    ds.rulesProcessingLast = True
    result, _ = Sketch.parse(text()).apply_designspace(ds)
    assert "rules last  # swaps" in result.text
