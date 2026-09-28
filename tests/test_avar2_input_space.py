"""
avar2 inputs are user space in DSSketch, in both directions, for every number.

DSS -> DS used to map an input through the axis only when it hit a labeled
point exactly: `[wght=550]` on an axis with `700 Bold > 625` stayed 550 instead
of 512.5. DS -> DSS wrote inputs in design space, so a sketch it produced read
back correctly only because the two mistakes cancelled; such sketches are
caught with the user value to write instead.
"""

import pytest
from fontTools.designspaceLib import DesignSpaceDocument

import dssketch
from dssketch import DSSParser

AXES = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        700 Bold > 625
        Black > 900
axes hidden
    XHID 0:50:100
sources [wght, XHID]
    A [Thin, 50]
    B [Regular, 50] @base
    C [Black, 50]
"""


def _inputs(sketch):
    ds = dssketch.convert_dss_string_to_designspace(sketch)
    return [dict(m.inputLocation) for m in ds.axisMappings]


def test_numeric_input_is_mapped_along_the_axis():
    sketch = AXES + "avar2\n    [wght=550] > XHID=80\n    [wght=Bold] > XHID=90\ninstances off\n"
    assert _inputs(sketch) == [{"weight": 512.5}, {"weight": 625}]


def test_numeric_input_equal_to_a_label_matches_the_label():
    by_number = _inputs(AXES + "avar2\n    [wght=700] > XHID=90\ninstances off\n")
    by_label = _inputs(AXES + "avar2\n    [wght=Bold] > XHID=90\ninstances off\n")
    assert by_number == by_label == [{"weight": 625}]


def test_designspace_inputs_are_written_as_user_values():
    ds = DesignSpaceDocument.fromfile("examples/avar2-RobotoDelta-Roman.designspace")
    sketch = dssketch.convert_designspace_to_dss_string(ds, avar2_format="linear")
    # opsz maps user 8 -> design -1; the sketch shows the user value
    assert "opsz=8" in sketch
    assert "opsz=-1" not in sketch


@pytest.mark.parametrize("fmt", ["matrix", "linear"])
def test_designspace_mappings_survive_roundtrip(fmt):
    ds = DesignSpaceDocument.fromfile("examples/avar2-RobotoDelta-Roman.designspace")
    back = dssketch.convert_dss_string_to_designspace(
        dssketch.convert_designspace_to_dss_string(ds, avar2_format=fmt)
    )

    def norm(doc):
        tags = {a.name: a.tag for a in doc.axes}
        loc = lambda d: tuple(sorted((tags.get(k, k), round(v, 3)) for k, v in d.items()))
        return sorted((loc(m.inputLocation), loc(m.outputLocation)) for m in doc.axisMappings)

    assert norm(back) == norm(ds)


def test_design_value_left_by_an_old_conversion_is_reported():
    legacy = """\
family T
axes
    opsz 8:14:144
        8 > -1
        14 > 0
        144 > 1
axes hidden
    XHID 0:50:100
sources [opsz, XHID]
    A [0, 50] @base
    B [1, 50]
avar2
    [opsz=-1] > XHID=80
instances off
"""
    parser = DSSParser(strict_mode=False)
    parser.parse(legacy)
    errors = [e for e in parser.validator.errors if "avar2 input" in e]
    assert len(errors) == 1
    assert "opsz=8" in errors[0]


def test_in_range_numeric_input_is_not_reported():
    parser = DSSParser(strict_mode=False)
    parser.parse(AXES + "avar2\n    [wght=550] > XHID=80\ninstances off\n")
    assert not [e for e in parser.validator.errors if "avar2 input" in e]
