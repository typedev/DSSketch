"""
Tests for avar map points that carry no STAT label.

In DesignSpace, an axis holds two independent lists: the <map> (the avar curve,
user -> design) and <labels> (the named styles). They need not cover the same
user values. A real-world pattern:

    <map input="100" output="100"/>   <- no label: axis extends past named styles
    <map input="200" output="175"/>   <- label "Thin"
    ...
    <map input="1000" output="1000"/> <- no label

Masters are then drawn at the *unnamed* extremes (design 100 and 1000) so that
every named instance interpolates inside the master envelope instead of sitting
on a raw master.

DSSketch writes such a point as a mapping with no label: "100 > 100".
"""

import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
    SourceDescriptor,
)

import dssketch
from dssketch.core.models import DSSAxis, DSSAxisMapping
from dssketch.writers.dss_writer import DSSWriter
from dssketch.parsers.dss_parser import DSSParser


# A production-shaped axis: 9 map points, 7 labels, masters off-label.
MAP = [
    (100, 100), (200, 175), (300, 288), (400, 400), (500, 500),
    (700, 575), (800, 825), (900, 983), (1000, 1000),
]
LABELS = [
    (200, "Thin", False), (300, "Light", False), (400, "Regular", True),
    (500, "Medium", False), (700, "Bold", False), (800, "Heavy", False),
    (900, "Black", False),
]
SOURCE_COORDS = [100, 400, 625, 1000]


def build_designspace() -> DesignSpaceDocument:
    doc = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = "wght", "weight"
    axis.minimum, axis.default, axis.maximum = 100, 400, 1000
    axis.map = list(MAP)
    axis.axisLabels = [
        AxisLabelDescriptor(name=name, userValue=uv, elidable=elidable)
        for uv, name, elidable in LABELS
    ]
    doc.addAxis(axis)

    for coord in SOURCE_COORDS:
        src = SourceDescriptor()
        src.filename = f"Font-{coord}.ufo"
        src.familyName = "Test"
        src.location = {"weight": coord}
        if coord == 400:
            src.copyLib = src.copyInfo = True
        doc.addSource(src)
    return doc


@pytest.fixture
def dss_string():
    return dssketch.convert_designspace_to_dss_string(build_designspace())


class TestUnnamedMapPointsSurviveConversion:
    def test_all_map_points_are_kept(self, dss_string):
        """Every map point reaches the sketch, labelled or not."""
        doc = DSSParser(strict_mode=False).parse(dss_string)
        assert [(m.user_value, m.design_value) for m in doc.axes[0].mappings] == [
            (float(u), float(d)) for u, d in MAP
        ]

    def test_only_labelled_points_carry_a_name(self, dss_string):
        doc = DSSParser(strict_mode=False).parse(dss_string)
        named = {m.user_value: m.label for m in doc.axes[0].mappings if m.label}
        assert named == {float(uv): name for uv, name, _ in LABELS}

    def test_unnamed_points_written_without_a_placeholder_name(self, dss_string):
        """The surface form is "100 > 100" - one space, no invented label."""
        assert "        100 > 100\n" in dss_string
        assert "        1000 > 1000\n" in dss_string

    def test_elidable_flag_survives(self, dss_string):
        doc = DSSParser(strict_mode=False).parse(dss_string)
        elidable = {m.label for m in doc.axes[0].mappings if m.elidable}
        assert elidable == {"Regular"}


class TestRoundtrip:
    def test_designspace_is_reproduced(self):
        original = build_designspace()
        sketch = dssketch.convert_designspace_to_dss_string(original)
        result = dssketch.convert_dss_string_to_designspace(sketch)

        axis = result.axes[0]
        assert axis.map == [(float(u), float(d)) for u, d in MAP]
        assert [(l.userValue, l.name, bool(l.elidable)) for l in axis.axisLabels] == [
            (float(uv), name, elidable) for uv, name, elidable in LABELS
        ]
        assert sorted(s.location["weight"] for s in result.sources) == [
            float(c) for c in SOURCE_COORDS
        ]

    def test_unnamed_points_produce_no_instances(self):
        """A map point without a name shapes the curve but names no style."""
        sketch = dssketch.convert_designspace_to_dss_string(build_designspace())
        result = dssketch.convert_dss_string_to_designspace(
            sketch.replace("instances off", "instances auto")
        )
        assert sorted(i.styleName for i in result.instances) == sorted(
            name for _, name, _ in LABELS
        )
        # Instances land on the *mapped* design values, not on the master positions.
        by_name = {i.styleName: i.location["weight"] for i in result.instances}
        assert by_name["Thin"] == 175
        assert by_name["Black"] == 983


class TestMastersNeedNotSitOnMappedPoints:
    """A master lives in design space and may be placed between named styles."""

    def test_off_map_master_is_a_warning_not_an_error(self, dss_string):
        parser = DSSParser(strict_mode=False)
        parser.parse(dss_string)
        joined = " ".join(parser.validator.errors)
        assert "625" not in joined, f"unexpected error: {parser.validator.errors}"

    def test_conversion_succeeds_with_off_map_master(self, dss_string):
        result = dssketch.convert_dss_string_to_designspace(dss_string)
        assert 625.0 in [s.location["weight"] for s in result.sources]


class TestWriterFormatting:
    def test_named_and_unnamed_mappings_side_by_side(self):
        axis = DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=1000)
        axis.mappings = [
            DSSAxisMapping(100, 100, ""),
            DSSAxisMapping(200, 175, "Thin"),
            DSSAxisMapping(1000, 1000, ""),
        ]
        assert DSSWriter()._format_axis(axis) == [
            "    wght 100:400:1000",
            "        100 > 100",
            "        200 Thin > 175",
            "        1000 > 1000",
        ]

    def test_unnamed_mapping_parses_back_unnamed(self):
        """No standard label is invented for a bare numeric mapping."""
        sketch = (
            "family X\n\naxes\n    wght 100:400:1000\n"
            "        100 > 100\n        400 Regular > 400\n"
            "\nsources [wght]\n    A [400] @base\n"
        )
        doc = DSSParser(strict_mode=False).parse(sketch)
        assert [(m.user_value, m.label) for m in doc.axes[0].mappings] == [
            (100.0, ""),
            (400.0, "Regular"),
        ]
