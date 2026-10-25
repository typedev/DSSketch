"""Wide avar2 matrices are written as sections of DSSWriter.MATRIX_COLUMNS
columns; rows at one input location combine into one mapping (1.5.x)."""

from pathlib import Path

import pytest
from fontTools.designspaceLib import DesignSpaceDocument

import dssketch
from dssketch import diagnose
from dssketch.writers.dss_writer import DSSWriter

EXAMPLES = Path(__file__).parent.parent / "examples"

HEAD = """\
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
"""


def mappings(text):
    ds = dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())
    return [(dict(m.inputLocation), dict(m.outputLocation), m.description) for m in ds.axisMappings]


def test_sections_combine():
    text = HEAD + """\
avar2 matrix
    outputs      XA  XB
    [wght=Black] 80  -
    [wght=Thin]  10  20

avar2 matrix
    outputs      XC
    [wght=Black] 90
"""
    assert mappings(text) == [
        ({"weight": 900.0}, {"XA": 80.0, "XC": 90.0}, None),
        ({"weight": 100.0}, {"XA": 10.0, "XB": 20.0}, None),
    ]
    assert not [d for d in diagnose(text) if d.severity == "error"]


def test_one_output_twice_is_an_error():
    text = HEAD + """\
avar2 matrix
    outputs      XA
    [wght=Black] 80

avar2
    [wght=900] > XA=70
"""
    found = [d for d in diagnose(text) if d.code == "5.56"]
    assert len(found) == 1 and "sets XA there too" in found[0].message and found[0].line == 19


def test_rows_at_the_default_never_combine():
    text = HEAD + "avar2\n    [wght=Regular] > XA=60\n    [wght=Regular] > XB=40\n"
    assert len(mappings(text)) == 2


def test_matrix_row_names():
    text = HEAD + 'avar2 matrix "m"\n    outputs XA\n    "heavy" [wght=Black] 80\n    [wght=Thin] 10\n'
    assert [m[2] for m in mappings(text)] == ["heavy", "m"]


def test_writer_splits_wide_matrices(monkeypatch):
    monkeypatch.setattr(DSSWriter, "MATRIX_COLUMNS", 2)
    text = HEAD + """\
avar2
    "heavy" [wght=Black] > XA=80, XB=70, XC=60
    [wght=Thin] > XC=10
    [wght=Regular] > XA=55
"""
    ds = dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())
    out = dssketch.convert_designspace_to_dss_string(ds)
    section = out[out.index("avar2 matrix"):]
    assert section == (
        "avar2 matrix\n"
        "    outputs               XA  XB\n"
        '    "heavy" [wght=Black]  80  70\n'
        "\n"
        "avar2 matrix\n"
        "    outputs       XC\n"
        "    [wght=Black]  60\n"
        "    [wght=Thin]   10\n"
        "\n"
        "avar2\n"
        "    [wght=Regular] > XA=55\n"
        "\n"
        "instances off"
    )
    assert sorted(map(str, mappings(out))) == sorted(map(str, mappings(text)))


@pytest.mark.parametrize("name", ["AmstelvarA2-Roman_avar2", "avar2-RobotoDelta-Roman"])
def test_large_examples(name):
    ds = DesignSpaceDocument.fromfile(EXAMPLES / f"{name}.designspace")
    text = (EXAMPLES / f"{name}.dssketch").read_text(encoding="utf-8")
    assert text.strip() == dssketch.convert_designspace_to_dss_string(ds).strip()
    avar2 = text[text.index("avar2 matrix"):text.index("\ninstances")]
    assert max(len(line) for line in avar2.splitlines()) < 130
    back = dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())
    key = lambda d: sorted(str((sorted(m.inputLocation.items()), sorted(m.outputLocation.items()), m.description))
                           for m in d.axisMappings)
    assert key(back) == key(ds)
