"""Editing avar2 in a Sketch, and quick fixes for the avar2 checks (1.5.x)."""

import pytest

import dssketch
from dssketch import EditError, Sketch, apply_edits

TEXT = """\
family A
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
axes hidden
    XA 0:50:100
    XB 0:50:100
    XC 0:50:100
sources
    A-Regular @base
    A-Black wght=Black
avar2 vars
    $V = 70
avar2 matrix
    outputs       XA  XB
    [wght=Black]  80  -
    [wght=Thin]   10  20

avar2 matrix
    outputs       XC
    [wght=Black]  90
avar2
    [wght=Thin] > XC=5  # note
    [wght=200] > {
        XA=30
    }
"""


def mappings(text):
    ds = dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())
    return {tuple(sorted(m.inputLocation.items())): dict(m.outputLocation) for m in ds.axisMappings}


def run(op):
    result = op(Sketch.parse(TEXT))
    assert apply_edits(TEXT, result.edits) == result.text
    return result


def changed(result):
    old, new = TEXT.split("\n"), result.text.split("\n")
    return [line for line in new if line not in old], [line for line in old if line not in new]


BLACK, THIN, W200 = (("weight", 900.0),), (("weight", 100.0),), (("weight", 200.0),)


def test_output_in_a_matrix_cell():
    r = run(lambda sk: sk.set_avar2_output(0, "XB", 33))
    assert changed(r) == (["    [wght=Black]  80  33"], ["    [wght=Black]  80  -"])
    assert mappings(r.text)[BLACK] == {"XA": 80.0, "XB": 33.0, "XC": 90.0}


def test_output_where_the_location_sets_it():
    # row 0 is in the first matrix; XC is a column of the second, at the same input
    r = run(lambda sk: sk.set_avar2_output(0, "XC", 91))
    assert changed(r) == (["    [wght=Black]  91"], ["    [wght=Black]  90"])
    # and row 2 (second matrix) edits XA in the first
    r = run(lambda sk: sk.set_avar2_output(2, "XA", 1))
    assert mappings(r.text)[BLACK]["XA"] == 1.0


def test_output_removed_and_last_output_removes_the_row():
    r = run(lambda sk: sk.set_avar2_output(1, "XB", None))
    assert "    [wght=Thin]   10  -" in r.text
    r = run(lambda sk: sk.set_avar2_output(1, "XC", None))
    assert "XC=5" not in r.text and "# note" not in r.text
    assert mappings(r.text)[THIN] == {"XA": 10.0, "XB": 20.0}


def test_output_in_linear_rows_and_blocks():
    r = run(lambda sk: sk.set_avar2_output(3, "XB", "$V"))
    assert mappings(r.text)[THIN]["XB"] == 70.0  # the matrix cell at that location
    r = run(lambda sk: sk.set_avar2_output(4, "XB", 12))
    assert "        XA=30\n        XB=12\n    }" in r.text
    r = run(lambda sk: sk.set_avar2_output(4, "XA", 31))
    assert "        XA=31\n" in r.text


def test_output_added_as_a_row_when_no_matrix_has_the_column():
    text = TEXT.replace("avar2\n    [wght=Thin] > XC=5  # note\n    [wght=200] > {\n        XA=30\n    }\n", "")
    sk = Sketch.parse(text)
    r = sk.set_avar2_output(1, "XC", 7)  # Thin: XC is a column only of the second matrix, without Thin
    assert "\navar2\n    [wght=Thin] > XC=7\n" in r.text
    assert mappings(r.text)[THIN] == {"XA": 10.0, "XB": 20.0, "XC": 7.0}


def test_add_mapping():
    r = run(lambda sk: sk.add_avar2_mapping({"wght": 300}, {"XA": 1, "XB": 2}))
    assert "    [wght=Thin]   10  20\n    [wght=300]    1   2\n" in r.text
    r = run(lambda sk: sk.add_avar2_mapping({"wght": 300}, {"XC": 1, "XB": 2}, name="mix"))
    assert r.text.endswith('    "mix" [wght=300] > XC=1, XB=2\n')
    with pytest.raises(EditError):
        run(lambda sk: sk.add_avar2_mapping({"wght": 300}, {"NOPE": 1}))


def test_inputs_name_remove():
    r = run(lambda sk: sk.set_avar2_input(3, "wght", 150))
    assert "    [wght=150] > XC=5  # note" in r.text
    r = run(lambda sk: sk.set_avar2_input(3, "XA", 10))  # a hidden axis as input: allowed, warned
    assert "    [wght=Thin, XA=10] > XC=5" in r.text
    r = run(lambda sk: sk.set_avar2_name(3, "thin c"))
    assert '    "thin c" [wght=Thin] > XC=5' in r.text
    r = r.sketch.set_avar2_name(3, None)
    assert r.text == TEXT
    r = run(lambda sk: sk.remove_avar2_mapping(4))
    assert "[wght=200]" not in r.text and "XA=30" not in r.text and "    }" not in r.text


def test_variables():
    r = run(lambda sk: sk.set_avar2_var("W", 5))
    assert "    $V = 70\n    $W = 5\n" in r.text
    r = run(lambda sk: sk.set_avar2_var("V", 71))
    assert "    $V = 71\n" in r.text
    used = run(lambda sk: sk.set_avar2_output(3, "XC", "$V")).sketch
    with pytest.raises(EditError):
        used.set_avar2_var("V", None)


def test_item_paths():
    sk = Sketch.parse(TEXT)
    assert sk.item_at(18, 18) == ("avar2", 0, "output", "XA")
    assert sk.item_at(25, 12) == ("avar2", 3, "input", "wght")


# -- quick fixes ---------------------------------------------------------------------


def fixed(text, code, which=0):
    d = next(d for d in Sketch.parse(text).diagnostics if d.code == code)
    return apply_edits(text, d.fixes[which].edits)


def test_fix_unknown_axis():
    assert "XC=5" in fixed(TEXT.replace("XC=5", "XCC=5"), "5.42")


def test_fix_default_input():
    text = TEXT.replace("    [wght=200] > {", "    [wght=Regular] > XB=10\n    [wght=200] > {")
    assert "    [wght=Regular] > XB=$\n" in fixed(text, "5.54")
    assert "[wght=Regular]" not in fixed(text, "5.54", 1)


def test_fix_output_out_of_range():
    assert "    [wght=Thin] > XC=100  # note" in fixed(TEXT.replace("XC=5", "XC=150"), "5.55")


def test_fix_duplicate_and_hidden_input():
    text = TEXT.replace("    [wght=200] > {", "    [wght=100] > XB=1\n    [wght=200] > {")
    assert "[wght=100]" not in fixed(text, "5.56")
    text = TEXT.replace("    [wght=200] > {", "    [XA=10] > XB=1\n    [wght=200] > {")
    assert "[XA=10]" not in fixed(text, "5.58")
