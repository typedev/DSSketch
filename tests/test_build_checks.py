"""Checks for what fontTools cannot build or silently changes (1.5.x): a map
whose design values fall, a master outside its axis's design range, two
masters at one location, a rule condition with minimum above maximum, an
avar2 row in a DesignSpace that names an axis by tag."""

from fontTools.designspaceLib import AxisDescriptor, AxisMappingDescriptor, DesignSpaceDocument, SourceDescriptor

import dssketch
from dssketch import Sketch, apply_edits, diagnose
from dssketch.core.report import AXIS_AVAR2_NAMED_BY_TAG, CATEGORY_AXES

BASE = """\
family T
axes
    wght 100:400:900
        Thin > 0
        Regular > 400 @elidable
        Black > 1000
sources [wght]
    T-Thin [Thin]
    T-Regular [Regular] @base
    T-Black [Black]
rules
    dollar > dollar.alt (weight >= 600)
"""


def codes(text):
    return [(d.code, d.severity, d.line) for d in diagnose(text) if d.code in ("5.67", "5.68", "5.69", "5.70")]


def fixed(text, code):
    d = next(d for d in Sketch.parse(text).diagnostics if d.code == code)
    return apply_edits(text, d.fixes[0].edits)


def test_clean_sketch_has_none():
    assert codes(BASE) == []


def test_map_falling():
    text = BASE.replace("Black > 1000", "Black > 300")
    assert codes(text)[0] == ("5.67", "error", 6)  # the masters then fall outside the range too


def test_flat_map_is_allowed():
    assert codes(BASE.replace("Black > 1000", "Black > 400")) == [("5.69", "error", 10)]  # but masters meet


def test_source_out_of_range_and_fix():
    text = BASE.replace("    T-Black [Black]", "    T-Black [1200]")
    assert codes(text) == [("5.68", "warning", 10)]
    assert "    T-Black [1000]\n" in fixed(text, "5.68")


def test_two_masters_at_one_location_and_fix():
    text = BASE.replace("    T-Black [Black]\n", "    T-Black [Black]\n    T-Heavy [1000]\n")
    assert codes(text) == [("5.69", "error", 11)]
    assert "T-Heavy" not in fixed(text, "5.69")
    # clamped onto the same end counts too
    text = BASE.replace("    T-Black [Black]\n", "    T-Black [Black]\n    T-Heavy [1100]\n")
    assert ("5.69", "error", 11) in codes(text)


def test_layers_and_sparse_masters_need_their_own_location():
    text = BASE.replace("    T-Black [Black]\n", "    T-Black [Black]\n    T-Black [Black] @layer=fix\n")
    assert codes(text) == [("5.69", "error", 11)]
    text = BASE.replace("    T-Black [Black]\n", "    T-Black [Black]\n    T-Fix [700] @sparse\n")
    assert codes(text) == []


def test_rule_condition_empty_and_fix():
    text = BASE.replace("(weight >= 600)", "(700 <= weight <= 600)")
    assert codes(text) == [("5.70", "warning", 12)]
    assert "(600 <= weight <= 700)" in fixed(text, "5.70")


def test_designspace_avar2_named_by_tag_is_reported():
    doc = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.name, axis.tag, axis.minimum, axis.default, axis.maximum = "Weight", "wght", 100, 400, 900
    doc.addAxis(axis)
    s = SourceDescriptor()
    s.filename, s.location = "A.ufo", {"Weight": 400}
    doc.addSource(s)
    m = AxisMappingDescriptor()
    m.inputLocation, m.outputLocation = {"wght": 900}, {"wght": 850}
    doc.axisMappings = [m]
    _, report = dssketch.convert_designspace_to_dss_string(doc, return_report=True)
    issue = report.find(CATEGORY_AXES, AXIS_AVAR2_NAMED_BY_TAG)
    assert issue and issue.raw_data["tags"] == ["wght"]


def test_units_per_em_with_font_data():
    class Host(dssketch.FontData):
        def units_per_em(self, source):
            return 2048 if "Black" in source else 1000

    text = BASE
    found = [d for d in diagnose(text, font_data=Host()) if d.code == "5.71"]
    assert [(d.severity, d.line) for d in found] == [("error", 10)]
    assert "2048 units per em" in found[0].message and "'T-Regular' has 1000" in found[0].message
    assert not [d for d in diagnose(text) if d.code == "5.71"]  # no font data: not checked
