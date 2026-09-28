"""
What DSSketch emits for compilers that build names and STAT from a designspace.

Agreed with TDKit (2026-09-28): the weight stays in the style name, last or
right before the slope word; elidedfallbackname is always written (see
test_elided_fallback.py); the ital axis links Upright to Italic.
"""

import dssketch
from dssketch import CATEGORY_AXES, CATEGORY_INSTANCES, INSTANCE_WEIGHT_NOT_LAST, AXIS_LABEL_DATA_DROPPED

AXES_WIDTH_FIRST = """\
    wdth 75:100:100
        Condensed > 75
        Normal > 100 @elidable
    wght 100:400:700
        Regular > 400 @elidable
        Bold > 700
"""
AXES_WEIGHT_FIRST = """\
    wght 100:400:700
        Regular > 400 @elidable
        Bold > 700
    wdth 75:100:100
        Condensed > 75
        Normal > 100 @elidable
"""
SKETCH = """\
family T
axes
{axes}    ital discrete
        Upright @elidable
        Italic
sources [wght, wdth, ital]
    A [Regular, Normal, Upright] @base
    B [Bold, Normal, Upright]
    C [Regular, Condensed, Upright]
    D [Regular, Normal, Italic] @base
instances auto
"""


def _convert(axes):
    return dssketch.convert_dss_string_to_designspace(
        SKETCH.format(axes=axes).replace("100:400:700", "400:400:700"), return_report=True
    )


def test_weight_word_is_last_or_before_the_slope_word():
    ds, report = _convert(AXES_WIDTH_FIRST)
    names = {i.styleName for i in ds.instances}
    assert {"Condensed Bold", "Condensed Bold Italic", "Bold Italic"} <= names
    assert not report.find(CATEGORY_INSTANCES, INSTANCE_WEIGHT_NOT_LAST)


def test_weight_before_width_is_reported():
    ds, report = _convert(AXES_WEIGHT_FIRST)
    assert "Bold Condensed" in {i.styleName for i in ds.instances}
    issue = report.find(CATEGORY_INSTANCES, INSTANCE_WEIGHT_NOT_LAST)
    assert issue and issue.raw_data == {"axes": ["wdth"]}


def test_ital_upright_links_to_italic():
    ds, _ = _convert(AXES_WIDTH_FIRST)
    ital = next(a for a in ds.axes if a.tag == "ital")
    assert {label.name: label.linkedUserValue for label in ital.axisLabels} == {"Upright": 1, "Italic": None}


def test_generated_link_is_not_reported_as_dropped():
    ds, _ = _convert(AXES_WIDTH_FIRST)
    _, report = dssketch.convert_designspace_to_dss_string(ds, return_report=True)
    issue = report.find(CATEGORY_AXES, AXIS_LABEL_DATA_DROPPED)
    assert not issue or "linked value" not in issue.details
