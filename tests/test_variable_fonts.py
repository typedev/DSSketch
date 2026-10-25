"""`variable-fonts` (1.6.x): DesignSpace 5 <variable-fonts>.

    variable-fonts auto              # a font per value of the discrete axes
        SuperFont-Text               # plus blocks: sub-ranges, frozen axes
            axes: wght=Light:Bold, ital=Upright
            filename: SuperFont-Text.ttf
"""

from pathlib import Path

import pytest
from fontTools.designspaceLib import RangeAxisSubsetDescriptor, ValueAxisSubsetDescriptor, VariableFontDescriptor

import dssketch
from dssketch import DSSParser, Sketch, apply_edits, complete, diagnose, tokenize
from dssketch.core.models import auto_variable_fonts
from dssketch.structure import build

BASE = (Path(__file__).parent.parent / "examples" / "SuperFont-6x2.dssketch").read_text(encoding="utf-8")
TEXT = BASE + """
variable-fonts auto
    SuperFont-Text  # a text cut
        axes: wght=Light:Bold, ital=Upright
        filename: SuperFont-Text.ttf
"""
BLOCK = TEXT.count("\n") - 2  # the block's name line


def back(text=TEXT):
    return dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())


def shape(vf):
    out = []
    for s in vf.axisSubsets:
        if hasattr(s, "userValue"):
            out.append((s.name, s.userValue))
        else:
            out.append((s.name, s.userMinimum, s.userDefault, s.userMaximum))
    return vf.name, vf.filename, out


def test_auto_names_and_axes():
    doc = DSSParser().parse(BASE)
    assert [f.name for f in auto_variable_fonts(doc)] == ["SuperFont", "SuperFont-Italic"]
    doc.suffix = "VF"
    assert [f.name for f in auto_variable_fonts(doc)] == ["SuperFont-VF", "SuperFont-Italic-VF"]
    mega = DSSParser().parse((Path(__file__).parent.parent / "examples" / "MegaFont-3x5x7x3-Variable.dssketch").read_text())
    assert [f.name for f in auto_variable_fonts(mega)] == ["MegaFont"]  # no discrete axis: one font


def test_dss_to_ds():
    fonts = [shape(vf) for vf in back().variableFonts]
    inf = float("inf")
    assert fonts == [
        ("SuperFont", None, [("weight", -inf, None, inf), ("italic", 0.0)]),
        ("SuperFont-Italic", None, [("weight", -inf, None, inf), ("italic", 1.0)]),
        ("SuperFont-Text", "SuperFont-Text.ttf", [("weight", 300.0, None, 700.0), ("italic", 0.0)]),
    ]
    assert back(BASE).variableFonts == []  # no section: none written


def test_round_trip_and_ds_to_dss_forms():
    out = dssketch.convert_designspace_to_dss_string(back())
    assert out[out.index("variable-fonts"):].startswith(
        "variable-fonts auto\n    SuperFont-Text\n        axes: wght=Light:Bold, ital=Upright\n"
        "        filename: SuperFont-Text.ttf")
    assert [shape(v) for v in back(out).variableFonts] == [shape(v) for v in back().variableFonts]
    # the auto ones alone
    ds = back(BASE + "\nvariable-fonts auto\n")
    assert dssketch.convert_designspace_to_dss_string(ds).rstrip().endswith("variable-fonts auto")
    # an auto font missing: every font a block
    ds = back()
    ds.variableFonts = ds.variableFonts[1:]
    out = dssketch.convert_designspace_to_dss_string(ds)
    section = out[out.index("variable-fonts"):]
    assert section.startswith("variable-fonts\n    SuperFont-Italic\n        axes: wght, ital=Italic\n")


def test_lib_is_reported_the_fonts_are_not():
    ds = back()
    ds.variableFonts[2].lib = {"com.example": 1}
    _, report = dssketch.convert_designspace_to_dss_string(ds, return_report=True)
    issue = report.find(4, 3)
    assert issue and issue.raw_data["variable_fonts"] == ["SuperFont-Text"]


@pytest.mark.parametrize("block, code", [
    ("    X\n        axes: wght=Bolt\n", "5.72"),
    ("    X\n        axes: wdth\n", "5.72"),
    ("    X\n        axes: ital\n", "5.72"),          # a discrete axis takes one value
    ("    X\n        axez: wght\n", "5.72"),
    ("    SuperFont-Italic\n        axes: wght, ital=Italic\n", "5.75"),  # auto makes it
    ("    X\n        filename: x.ttf\n", "5.76"),
    ("    X\n        axes: wght, ital=2\n", "5.77"),
    ("    X\n        axes: wght=50:900\n", "5.77"),
    ("    X\n        axes: wght\n", "5.78"),          # ital left out
])
def test_diagnostics(block, code):
    text = BASE + "\nvariable-fonts auto\n" + block
    assert code in {d.code for d in diagnose(text)}, [(d.code, d.message) for d in diagnose(text)]


def test_mode_and_column_zero():
    assert "5.73" in {d.code for d in diagnose(BASE + "\nvariable-fonts all\n")}
    assert "5.74" in {d.code for d in diagnose(BASE + "\nvariable-fonts\nX\n")}
    assert not [d for d in diagnose(TEXT) if d.severity == "error"]


def test_tokens_structure_outline_query():
    tokens = [(t.text, t.type) for t in tokenize(TEXT) if t.line == BLOCK + 1]
    assert tokens == [("axes", "keyword"), (":", "punctuation"), ("wght", "axis-tag"), ("=", "punctuation"),
                      ("Light", "label"), (":", "punctuation"), ("Bold", "label"), (",", "punctuation"),
                      ("ital", "axis-tag"), ("=", "punctuation"), ("Upright", "label")]
    line = build(TEXT).line(BLOCK + 1)
    assert line.kind == "variable-font-field" and line.values["axis.wght"] == "Light:Bold"
    sk = Sketch.parse(TEXT)
    section = next(s for s in sk.outline() if s.name == "variable-fonts")
    assert [(c.kind, c.name, c.path) for c in section.children] == [
        ("variable-font", "SuperFont-Text", ("variable_font", 0))]
    fonts = sk.variable_fonts()
    assert [(f.name, f.auto) for f in fonts] == [("SuperFont", True), ("SuperFont-Italic", True), ("SuperFont-Text", False)]
    assert fonts[2].axes == {"weight": (300.0, 400.0, 700.0), "italic": 0.0}
    assert fonts[2].span.line == BLOCK
    column = TEXT.splitlines()[BLOCK].index("Upright")
    assert sk.item_at(BLOCK + 1, column) == ("variable_font", 0, "axes", "ital")


def test_operations():
    sk = Sketch.parse(BASE)
    r = sk.set_variable_fonts_mode("auto")
    assert r.text.rstrip().endswith("variable-fonts auto")
    r = r.sketch.add_variable_font("SuperFont-Text", {"wght": ("Light", "Bold"), "ital": "Upright"})
    assert r.text.endswith("    SuperFont-Text\n        axes: wght=Light:Bold, ital=Upright\n")
    r = r.sketch.set_variable_font_field(0, "filename", "t.ttf")
    assert r.text.endswith("        axes: wght=Light:Bold, ital=Upright\n        filename: t.ttf\n")
    r = r.sketch.set_variable_font_field(0, "axes", ["wght", "ital=Italic"])
    assert "        axes: wght, ital=Italic\n" in r.text
    with pytest.raises(dssketch.EditError):
        r.sketch.set_variable_font_field(0, "axes", "wght=Bolt")
    r = r.sketch.set_variable_font_name(0, "SuperFont-Display")
    assert "    SuperFont-Display\n" in r.text
    r = r.sketch.set_variable_fonts_mode(None)
    assert "\nvariable-fonts\n" in r.text
    assert "SuperFont-Display" not in r.sketch.remove_variable_font(0).text


def test_apply():
    # without the pattern rule: with no font data it expands to nothing and the
    # DesignSpace leaves it out, which apply would follow
    text = TEXT.replace('    dollar* cent* > .rvrn (weight >= Bold) "heavy alternates"\n', "")
    ds = back(text)
    ds.variableFonts.append(VariableFontDescriptor(name="SuperFont-Bold", axisSubsets=[
        RangeAxisSubsetDescriptor(name="weight", userMinimum=600, userMaximum=900),
        ValueAxisSubsetDescriptor(name="italic", userValue=1)]))
    result, report = Sketch.parse(text).apply_designspace(ds)
    assert [i for i in report if i.category == 6] == []
    assert "    SuperFont-Bold\n        axes: wght=600:Black, ital=Italic\n" in result.text
    assert apply_edits(text, result.edits) == result.text
    result, _ = Sketch.parse(text).apply_designspace(back(text))
    assert result.edits == []


def test_completion():
    text = BASE + "\nvariable-fonts auto\n    X\n        axes: wght="
    line = text.count("\n") + 1
    assert "Bold" in [c.text for c in complete(text, line, len("        axes: wght="))]
    text = BASE + "\nvariable-fonts auto\n    X\n        "
    assert [c.text for c in complete(text, text.count("\n") + 1, 8)] == ["axes", "filename"]
