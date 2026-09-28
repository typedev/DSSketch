"""
A discrete axis is discrete because it says so, not because of its name or range.

Before: DSS -> DS made an axis discrete only if it was named italic/ital, so
`slnt discrete` and custom discrete axes came out continuous and their masters
interpolated. DS -> DSS wrote a 3-value discrete axis as a 0:0:2 range, and
converting it back failed on "multiple @base".
"""

import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
    DiscreteAxisDescriptor,
    SourceDescriptor,
)

import dssketch
from dssketch import DSSParser

TEMPLATE = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
    {axis}
sources [wght, {tag}]
    A [Thin, {v0}]
    B [Regular, {v0}] @base
    C [Black, {v0}]
    D [Regular, {v1}] @base
instances off
"""


def _axis(ds, tag):
    return next(a for a in ds.axes if a.tag == tag)


@pytest.mark.parametrize(
    "axis,tag,v0,v1,labels",
    [
        ("ital discrete\n        Upright @elidable\n        Italic", "ital", "Upright", "Italic", ["Upright", "Italic"]),
        ("slnt discrete\n        Upright @elidable\n        Slanted", "slnt", "Upright", "Slanted", ["Upright", "Slanted"]),
        ("SERF discrete\n        Sans @elidable\n        Serif", "SERF", "Sans", "Serif", ["Sans", "Serif"]),
    ],
)
def test_discrete_keyword_gives_discrete_axis_whatever_the_name(axis, tag, v0, v1, labels):
    ds = dssketch.convert_dss_string_to_designspace(TEMPLATE.format(axis=axis, tag=tag, v0=v0, v1=v1))
    a = _axis(ds, tag)
    assert isinstance(a, DiscreteAxisDescriptor)
    assert a.values == [0, 1]
    assert [label.name for label in a.axisLabels] == labels


def test_three_value_discrete_axis_from_labels():
    sketch = TEMPLATE.format(
        axis="STYL discrete\n        Sans @elidable\n        Serif\n        Mono",
        tag="STYL", v0="Sans", v1="Mono",
    )
    ds = dssketch.convert_dss_string_to_designspace(sketch)
    a = _axis(ds, "STYL")
    assert isinstance(a, DiscreteAxisDescriptor)
    assert a.values == [0, 1, 2]
    assert [(label.name, label.userValue) for label in a.axisLabels] == [
        ("Sans", 0), ("Serif", 1), ("Mono", 2)
    ]


def test_zero_to_one_numeric_range_stays_continuous_except_ital():
    for tag, expected in (("FILL", AxisDescriptor), ("ital", DiscreteAxisDescriptor)):
        doc = DSSParser().parse(
            f"family T\naxes\n    {tag} 0:0:1\nsources [{tag}]\n    A [0] @base\n    B [1]\ninstances off\n"
        )
        from dssketch.converters.dss_to_designspace import DSSToDesignSpace

        a = _axis(DSSToDesignSpace().convert(doc), tag)
        assert type(a) is expected, tag


def _three_value_designspace():
    d = DesignSpaceDocument()
    w = AxisDescriptor()
    w.name, w.tag, w.minimum, w.default, w.maximum = "weight", "wght", 100, 400, 900
    d.addAxis(w)
    s = DiscreteAxisDescriptor()
    s.name, s.tag, s.values, s.default = "style", "STYL", [0, 1, 2], 0
    # value 2 deliberately has no label
    s.axisLabels = [
        AxisLabelDescriptor(name="Sans", userValue=0, elidable=True),
        AxisLabelDescriptor(name="Serif", userValue=1),
    ]
    d.addAxis(s)
    for v in (0, 1, 2):
        for wv in (400, 900):
            src = SourceDescriptor()
            src.filename, src.location = f"S{v}-{wv}.ufo", {"weight": wv, "style": v}
            d.addSource(src)
    return d


def test_three_value_discrete_axis_roundtrips():
    sketch = dssketch.convert_designspace_to_dss_string(_three_value_designspace())
    assert "STYL discrete" in sketch
    assert "        2 > 2" in sketch  # the unlabeled value survives as an unnamed point

    back = dssketch.convert_dss_string_to_designspace(sketch)
    a = _axis(back, "STYL")
    assert isinstance(a, DiscreteAxisDescriptor)
    assert a.values == [0, 1, 2]
    assert [(label.name, label.userValue) for label in a.axisLabels] == [("Sans", 0), ("Serif", 1)]
    assert len(back.sources) == 6


def test_non_positional_discrete_values_are_written_in_full():
    d = _three_value_designspace()
    d.axes[1].values = [0, 5, 10]
    d.axes[1].axisLabels = [
        AxisLabelDescriptor(name="Sans", userValue=0, elidable=True),
        AxisLabelDescriptor(name="Serif", userValue=5),
        AxisLabelDescriptor(name="Mono", userValue=10),
    ]
    for src in d.sources:
        src.location["style"] = {0: 0, 1: 5, 2: 10}[src.location["style"]]
    sketch = dssketch.convert_designspace_to_dss_string(d)
    # "Serif" alone would parse back as position 1, not 5
    assert "        5 Serif > 5" in sketch
    back = _axis(dssketch.convert_dss_string_to_designspace(sketch), "STYL")
    assert back.values == [0, 5, 10]


def test_label_based_range_must_be_ordered():
    parser = DSSParser(strict_mode=False)
    parser.parse(
        "family T\naxes\n    wght Black:Regular:Thin\n        Thin > 100\n        Regular > 400\n"
        "        Black > 900\nsources [wght]\n    A [400] @base\n"
    )
    assert any("min <= default <= max" in e for e in parser.validator.errors)
