"""Source names in the DesignSpace: unique, from the UFO file, without dots.

FontLab 8 reads a dot in a master name as "master.sublayer": `source.1` became
sublayer `1` of master `source`, and every component lost its layer.
"""

from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, SourceDescriptor

from dssketch.converters.designspace_to_dss import DesignSpaceToDSS
from dssketch.converters.dss_to_designspace import DSSToDesignSpace
from dssketch.core.models import DSSAxis, DSSDocument, DSSSource
from dssketch.core.report import CATEGORY_SOURCES, SOURCE_STYLE_NAME_DUPLICATE


def _doc(*sources):
    doc = DSSDocument(family="TestFont")
    doc.axes = [DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900)]
    doc.sources = list(sources)
    return doc


def _names(doc):
    return [s.name for s in DSSToDesignSpace().convert(doc).sources]


def _src(filename, weight, **kw):
    return DSSSource(name=filename, filename=filename, location={"weight": weight}, **kw)


def test_names_come_from_ufo_files():
    doc = _doc(
        _src("Font-Regular.ufo", 400, is_base=True),
        _src("Font-Bold.ufo", 700),
    )
    assert _names(doc) == ["Font-Regular", "Font-Bold"]


def test_path_and_extension_are_dropped():
    doc = _doc(
        _src("upright/Font-Regular.ufo", 400, is_base=True),
        _src("Font-Bold.ufoz", 700),
    )
    doc.path = "sources"
    assert _names(doc) == ["Font-Regular", "Font-Bold"]


def test_no_dots_in_any_name():
    doc = _doc(
        _src("Font.Regular.ufo", 400, is_base=True),
        _src("Font.Regular.ufo", 500, layer="public.background"),
        _src("Font.Bold-sparse.ufo", 700, is_sparse=True),
    )
    names = _names(doc)
    assert names == ["Font-Regular", "Font-Regular-public-background", "sparse-Font-Bold-sparse"]
    assert not any("." in n for n in names)


def test_layers_of_one_ufo_get_distinct_names():
    doc = _doc(
        _src("Font-Master.ufo", 400, is_base=True),
        _src("Font-Master.ufo", 500, layer="wght500"),
        _src("Font-Master.ufo", 600, layer="wght600"),
    )
    assert _names(doc) == ["Font-Master", "Font-Master-wght500", "Font-Master-wght600"]


def test_same_stem_in_two_folders_is_made_unique():
    doc = _doc(
        _src("upright/Font.ufo", 400, is_base=True),
        _src("italic/Font.ufo", 700),
        _src("other/Font.ufo", 900),
    )
    names = _names(doc)
    assert names == ["Font", "Font-2", "Font-3"]


def _ds_with_source(name, filename):
    ds = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = "wght", "weight"
    axis.minimum, axis.default, axis.maximum = 100, 400, 900
    ds.addAxis(axis)
    for n, f, w in [("Regular", "Font-Regular.ufo", 400), (name, filename, 600)]:
        src = SourceDescriptor()
        src.name, src.filename, src.location = n, f, {"weight": w}
        ds.addSource(src)
    return ds


def test_sparse_read_back_from_new_and_old_prefix():
    for name in ("sparse-Font-Fix", "sparse.Font-Fix", "sparse.3"):
        dss = DesignSpaceToDSS().convert(_ds_with_source(name, "Font-Fix.ufo"))
        assert dss.sources[1].is_sparse is True, name


def test_source_prefix_is_not_sparse():
    dss = DesignSpaceToDSS().convert(_ds_with_source("source-3", "Font-Fix.ufo"))
    assert dss.sources[1].is_sparse is False


def _duplicate_issues(converter):
    return [
        i for i in converter.report.issues
        if (i.category, i.code) == (CATEGORY_SOURCES, SOURCE_STYLE_NAME_DUPLICATE)
    ]


def test_duplicate_family_style_is_reported():
    # No UFOs on disk: every style name falls back to the source name, so
    # give two different files the same one
    doc = _doc(
        DSSSource(name="Bold", filename="Font-Bold.ufo", location={"weight": 700}),
        DSSSource(name="Bold", filename="Font-BoldItalic.ufo", location={"weight": 700}),
        DSSSource(name="Regular", filename="Font-Regular.ufo", location={"weight": 400}, is_base=True),
    )
    converter = DSSToDesignSpace()
    converter.convert(doc)
    issues = _duplicate_issues(converter)
    assert len(issues) == 1
    assert issues[0].raw_data["files"] == ["Font-Bold.ufo", "Font-BoldItalic.ufo"]


def test_layers_of_one_ufo_are_not_duplicates():
    doc = _doc(
        DSSSource(name="Master", filename="Font-Master.ufo", location={"weight": 400}, is_base=True),
        DSSSource(name="Master", filename="Font-Master.ufo", location={"weight": 600}, layer="wght600"),
    )
    converter = DSSToDesignSpace()
    converter.convert(doc)
    assert _duplicate_issues(converter) == []
