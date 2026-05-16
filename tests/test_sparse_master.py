"""Tests for @sparse master support in sources

Sparse masters are correction layers with reduced glyph coverage,
used for interpolation correction without contributing a full set of glyphs.

In DesignSpace XML, they're marked with name="sparse.*" prefix.
In DSSketch, they're marked with the @sparse flag (analogous to @base).
"""

import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    SourceDescriptor,
)

from src.dssketch.converters.designspace_to_dss import DesignSpaceToDSS
from src.dssketch.converters.dss_to_designspace import DSSToDesignSpace
from src.dssketch.core.models import DSSAxis, DSSDocument, DSSSource
from src.dssketch.parsers.dss_parser import DSSParser
from src.dssketch.writers.dss_writer import DSSWriter


class TestSparseParsing:
    """Test parsing of @sparse flag in source lines"""

    def test_parse_sparse_flag(self):
        """@sparse flag is extracted and is_sparse=True"""
        content = """
family TestFont

axes
    wght 100:400:900

sources [wght]
    Font-Regular [400] @base
    Font-Correction-sparse [500] @sparse
"""
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        assert len(doc.sources) == 2
        assert doc.sources[0].is_sparse is False
        assert doc.sources[1].is_sparse is True

    def test_parse_sparse_without_flag(self):
        """Sources without @sparse have is_sparse=False"""
        content = """
family TestFont

axes
    wght 100:400:900

sources [wght]
    Font-Regular [400] @base
    Font-Bold [700]
"""
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        assert all(s.is_sparse is False for s in doc.sources)

    def test_parse_sparse_combined_with_layer(self):
        """@sparse can coexist with @layer"""
        content = """
family TestFont

axes
    wght 100:400:900

sources [wght]
    Font-Master.ufo [400] @base
    Font-Master.ufo [500] @sparse @layer="correction"
"""
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        assert doc.sources[1].is_sparse is True
        assert doc.sources[1].layer == "correction"

    def test_parse_sparse_in_named_format(self):
        """@sparse works with named coordinates (axis=value)"""
        content = """
family TestFont

axes
    wght 100:400:900
    wdth 60:100:200

sources
    Font-Regular @base
    Font-Correction wght=500 @sparse
"""
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        assert doc.sources[1].is_sparse is True


class TestSparseWriting:
    """Test writing @sparse flag in source lines"""

    def test_write_sparse_flag(self):
        """is_sparse=True produces @sparse in output"""
        doc = DSSDocument(family="TestFont")
        doc.axes = [DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900)]
        doc.sources = [
            DSSSource(name="Regular", filename="Font-Regular.ufo",
                      location={"weight": 400}, is_base=True),
            DSSSource(name="Correction", filename="Font-Correction-sparse.ufo",
                      location={"weight": 500}, is_sparse=True),
        ]

        writer = DSSWriter(use_label_coordinates=False)
        output = writer.write(doc)

        assert "@sparse" in output
        # Non-sparse source should not have @sparse
        regular_line = [l for l in output.splitlines() if "Regular" in l and "[" in l][0]
        assert "@sparse" not in regular_line

    def test_write_no_sparse_when_false(self):
        """is_sparse=False does not produce @sparse"""
        doc = DSSDocument(family="TestFont")
        doc.axes = [DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900)]
        doc.sources = [
            DSSSource(name="Regular", filename="Font-Regular.ufo",
                      location={"weight": 400}, is_base=True),
        ]

        writer = DSSWriter(use_label_coordinates=False)
        output = writer.write(doc)

        assert "@sparse" not in output


class TestSparseRoundtripDSS:
    """Test DSSketch → DSSketch roundtrip preserves @sparse"""

    def test_dss_roundtrip(self):
        """Parse → write → parse preserves is_sparse"""
        original = """
family TestFont

axes
    wght 100:400:900

sources [wght]
    Font-Regular [400] @base
    Font-Correction-sparse [500] @sparse
    Font-Bold [700]
"""
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(original)

        writer = DSSWriter(use_label_coordinates=False)
        output = writer.write(doc)

        parser2 = DSSParser(strict_mode=False)
        doc2 = parser2.parse(output)

        assert doc2.sources[0].is_sparse is False
        assert doc2.sources[1].is_sparse is True
        assert doc2.sources[2].is_sparse is False


class TestSparseDetectionFromDesignSpace:
    """Test DS → DSS detects sparse from name attribute or filename"""

    def _build_ds(self, sources_meta):
        """Helper: build minimal DesignSpace with given sources"""
        ds = DesignSpaceDocument()
        axis = AxisDescriptor()
        axis.tag = "wght"
        axis.name = "weight"
        axis.minimum = 100
        axis.default = 400
        axis.maximum = 900
        ds.addAxis(axis)

        for filename, name, location in sources_meta:
            src = SourceDescriptor()
            src.filename = filename
            src.name = name
            src.location = location
            ds.addSource(src)
        return ds

    def test_detect_sparse_by_name_prefix(self):
        """name='sparse.X' → is_sparse=True"""
        ds = self._build_ds([
            ("Font-Regular.ufo", "source.0", {"weight": 400}),
            ("Font-Correction.ufo", "sparse.MyCorrection", {"weight": 500}),
        ])

        converter = DesignSpaceToDSS()
        dss = converter.convert(ds)

        assert dss.sources[0].is_sparse is False
        assert dss.sources[1].is_sparse is True

    def test_detect_sparse_by_filename_suffix(self):
        """filename '*-sparse.ufo' → is_sparse=True even without name prefix"""
        ds = self._build_ds([
            ("Font-Regular.ufo", "source.0", {"weight": 400}),
            ("Font-Bold-sparse.ufo", "source.1", {"weight": 700}),
        ])

        converter = DesignSpaceToDSS()
        dss = converter.convert(ds)

        assert dss.sources[0].is_sparse is False
        assert dss.sources[1].is_sparse is True

    def test_no_false_positive(self):
        """Sources without sparse markers stay is_sparse=False"""
        ds = self._build_ds([
            ("Font-Regular.ufo", "source.0", {"weight": 400}),
            ("Font-Bold.ufo", "MyBold", {"weight": 700}),
        ])

        converter = DesignSpaceToDSS()
        dss = converter.convert(ds)

        assert all(s.is_sparse is False for s in dss.sources)


class TestSparseNameGenerationToDesignSpace:
    """Test DSS → DS generates sparse.N for sparse sources"""

    def test_sparse_name_prefix(self):
        """is_sparse=True → source.name starts with 'sparse.'"""
        doc = DSSDocument(family="TestFont")
        doc.axes = [DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900)]
        doc.sources = [
            DSSSource(name="Regular", filename="Font-Regular.ufo",
                      location={"weight": 400}, is_base=True),
            DSSSource(name="Correction-sparse", filename="Font-Correction-sparse.ufo",
                      location={"weight": 500}, is_sparse=True),
        ]

        converter = DSSToDesignSpace()
        ds = converter.convert(doc)

        # Sparse source: name must start with "sparse."
        sparse_source = [s for s in ds.sources
                         if s.filename and "Correction-sparse" in s.filename][0]
        assert sparse_source.name.startswith("sparse.")

        # Non-sparse source: name must NOT start with "sparse."
        regular_source = [s for s in ds.sources
                          if s.filename and "Regular" in s.filename][0]
        assert not regular_source.name.startswith("sparse.")
        assert regular_source.name.startswith("source.")


class TestSparseFullRoundtrip:
    """Test full DS → DSS → DS roundtrip preserves sparse markers"""

    def test_full_roundtrip(self):
        """DesignSpace with sparse masters → DSSketch → DesignSpace: sparse preserved"""
        # Build DS with one regular + two sparse sources
        ds = DesignSpaceDocument()
        axis = AxisDescriptor()
        axis.tag = "wght"
        axis.name = "weight"
        axis.minimum = 100
        axis.default = 400
        axis.maximum = 900
        ds.addAxis(axis)

        src1 = SourceDescriptor()
        src1.filename = "Font-Regular.ufo"
        src1.name = "Regular"
        src1.location = {"weight": 400}
        ds.addSource(src1)

        src2 = SourceDescriptor()
        src2.filename = "Font-Correction-sparse.ufo"
        src2.name = "sparse.Font-Correction"
        src2.location = {"weight": 500}
        ds.addSource(src2)

        src3 = SourceDescriptor()
        src3.filename = "Font-Bold-sparse.ufo"
        src3.name = "sparse.Font-Bold"
        src3.location = {"weight": 700}
        ds.addSource(src3)

        # DS → DSS
        dss = DesignSpaceToDSS().convert(ds)
        sparse_filenames = {s.filename for s in dss.sources if s.is_sparse}
        assert sparse_filenames == {"Font-Correction-sparse.ufo", "Font-Bold-sparse.ufo"}

        # DSS → DS
        ds2 = DSSToDesignSpace().convert(dss)

        # All previously-sparse sources should have name starting with "sparse."
        sparse_names = [s.name for s in ds2.sources
                        if s.filename and "sparse" in s.filename]
        assert len(sparse_names) == 2
        assert all(n.startswith("sparse.") for n in sparse_names)
