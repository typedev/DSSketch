"""`elidedfallback` carries the DesignSpace elidedFallbackName (1.5.0)."""

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor

import dssketch
from dssketch import Sketch, complete, diagnose, tokenize
from dssketch.syntax import KEYWORD, TEXT

SKETCH = """\
family T
elidedfallback Book
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    T-Thin [Thin]
    T-Regular [Regular] @base
    T-Black [Black]
instances off
"""


def _ds(fallback):
    ds = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = "wght", "weight"
    axis.minimum, axis.default, axis.maximum = 100, 400, 900
    ds.addAxis(axis)
    source = SourceDescriptor()
    source.filename, source.familyName, source.location = "T.ufo", "T", {"weight": 400}
    ds.addSource(source)
    ds.elidedFallbackName = fallback
    return ds


def test_dss_to_ds_sets_it():
    assert dssketch.convert_dss_string_to_designspace(SKETCH).elidedFallbackName == "Book"
    derived = dssketch.convert_dss_string_to_designspace(SKETCH.replace("elidedfallback Book\n", ""))
    assert derived.elidedFallbackName == "Regular"


def test_quoted_and_spaced_names():
    for line, name in (('elidedfallback "Text Regular"', "Text Regular"), ("elidedfallback Text Regular", "Text Regular")):
        ds = dssketch.convert_dss_string_to_designspace(SKETCH.replace("elidedfallback Book", line))
        assert ds.elidedFallbackName == name


def test_empty_line_is_an_error():
    errors = [d for d in diagnose(SKETCH.replace("elidedfallback Book", "elidedfallback")) if d.severity == "error"]
    assert errors and errors[0].line == 2


def test_ds_to_dss_writes_it_only_when_not_derived():
    sketch, report = dssketch.convert_designspace_to_dss_string(_ds("Book"), return_report=True)
    assert "\nelidedfallback Book\n" in sketch
    assert not [i for i in report.issues if "elidedFallbackName" in i.description]
    assert dssketch.convert_dss_string_to_designspace(sketch).elidedFallbackName == "Book"
    plain = dssketch.convert_designspace_to_dss_string(_ds("Regular"))
    assert "elidedfallback" not in plain
    spaced = dssketch.convert_designspace_to_dss_string(_ds("Text Regular"))
    assert '\nelidedfallback "Text Regular"\n' in spaced
    assert dssketch.convert_dss_string_to_designspace(spaced).elidedFallbackName == "Text Regular"


def test_dss_roundtrip():
    doc = dssketch.DSSParser().parse(SKETCH)
    assert doc.elided_fallback == "Book"
    assert "elidedfallback Book" in dssketch.DSSWriter().write(doc)


def test_editor_support():
    tokens = [(t.text, t.type) for t in tokenize(SKETCH) if t.line == 2]
    assert tokens == [("elidedfallback", KEYWORD), ("Book", TEXT)]
    assert any(c.text == "elidedfallback" for c in complete("eli", 1, 3))
    sk = Sketch.parse(SKETCH)
    assert sk.item_at(2, 16) == ("elidedfallback", "value")
    assert sk.set_elided_fallback("Text").text == SKETCH.replace("Book", "Text")
    assert "elidedfallback" not in sk.set_elided_fallback(None).text
    added = Sketch.parse(SKETCH.replace("elidedfallback Book\n", "")).set_elided_fallback("Book")
    assert added.text == SKETCH
