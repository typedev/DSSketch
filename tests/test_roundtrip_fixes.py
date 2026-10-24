"""Round-trip findings #1 and #4 from notes/roundtrip-fidelity-issues.md."""

from pathlib import Path

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor

import dssketch

EXAMPLES = Path(__file__).parent.parent / "examples"


def _roundtrip(ds):
    sketch = dssketch.convert_designspace_to_dss_string(ds)
    return sketch, dssketch.convert_dss_string_to_designspace(sketch)


def _doc(axis_name="opsz", filenames=("A.ufo", "sub/B.ufo")):
    ds = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = "opsz", axis_name
    axis.minimum, axis.default, axis.maximum = 8, 14, 144
    ds.addAxis(axis)
    for i, filename in enumerate(filenames):
        source = SourceDescriptor()
        source.filename = filename
        source.familyName = "Test"
        source.location = {axis_name: [14, 144][i % 2]}
        ds.addSource(source)
    return ds


# 1. mixed root / subdirectory sources


def test_mixed_root_and_subdirectory_sources_keep_their_paths():
    sketch, back = _roundtrip(_doc())
    assert "\npath " not in sketch
    assert [s.filename for s in back.sources] == ["A.ufo", "sub/B.ufo"]


def test_common_subdirectory_still_becomes_path():
    sketch, back = _roundtrip(_doc(filenames=("sub/A.ufo", "sub/B.ufo")))
    assert "\npath sub\n" in sketch
    assert [s.filename for s in back.sources] == ["sub/A.ufo", "sub/B.ufo"]


def test_all_root_sources_write_no_path():
    sketch, back = _roundtrip(_doc(filenames=("A.ufo", "B.ufo")))
    assert "\npath " not in sketch


# 4. axis name equal to its tag


def test_axis_name_equal_to_tag_survives():
    sketch, back = _roundtrip(_doc(filenames=("A.ufo", "B.ufo")))
    assert 'opsz 8:14:144 "opsz"' in sketch
    assert [a.name for a in back.axes] == ["opsz"]
    assert set(back.sources[0].location) == {"opsz"}


def test_other_axis_names_unchanged():
    sketch, back = _roundtrip(_doc(axis_name="Optical size", filenames=("A.ufo", "B.ufo")))
    assert '"Optical size"' in sketch
    assert [a.name for a in back.axes] == ["Optical size"]


def test_unnamed_axis_in_sketch_keeps_long_default():
    ds = dssketch.convert_dss_string_to_designspace(
        "family T\naxes\n    opsz 8:14:144\nsources [opsz]\n    A [14] @base\ninstances off\n"
    )
    assert [a.name for a in ds.axes] == ["optical"]


def test_custom_axis_named_after_its_tag_writes_no_quotes():
    ds = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag = axis.name = "XOUC"
    axis.minimum, axis.default, axis.maximum = 0, 100, 200
    ds.addAxis(axis)
    source = SourceDescriptor()
    source.filename, source.familyName, source.location = "A.ufo", "T", {"XOUC": 100}
    ds.addSource(source)
    sketch, back = _roundtrip(ds)
    assert '"XOUC"' not in sketch
    assert [a.name for a in back.axes] == ["XOUC"]


def test_robotodelta_roundtrip_keeps_axis_names_and_paths():
    ds = DesignSpaceDocument.fromfile(str(EXAMPLES / "avar2-RobotoDelta-Roman.designspace"))
    _, back = _roundtrip(ds)
    assert [a.name for a in back.axes] == [a.name for a in ds.axes]
    assert [s.filename for s in back.sources] == [s.filename for s in ds.sources]
