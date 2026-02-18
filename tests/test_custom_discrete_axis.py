"""Tests for custom discrete axis support (e.g., LOOP, FILL, etc.)"""

import pytest
from src.dssketch.parsers.dss_parser import DSSParser
from src.dssketch.writers.dss_writer import DSSWriter
from src.dssketch.utils.discrete import DiscreteAxisHandler
from src.dssketch.core.models import DSSDocument, DSSAxis, DSSAxisMapping, DSSSource


class TestDiscreteAxisDetection:
    """Test DiscreteAxisHandler.is_discrete() for custom axes"""

    def test_standard_discrete_axis(self):
        """Standard ital axis with 0:0:1 is discrete"""
        axis = DSSAxis(name="italic", tag="ital", minimum=0, default=0, maximum=1)
        assert DiscreteAxisHandler.is_discrete(axis) is True

    def test_custom_discrete_axis(self):
        """Custom LOOP axis with 0:0:1 is discrete"""
        axis = DSSAxis(name="LOOP", tag="LOOP", minimum=0, default=0, maximum=1)
        assert DiscreteAxisHandler.is_discrete(axis) is True

    def test_custom_discrete_axis_lowercase(self):
        """Custom lowercase axis with 0:0:1 is discrete"""
        axis = DSSAxis(name="FILL", tag="FILL", minimum=0, default=0, maximum=1)
        assert DiscreteAxisHandler.is_discrete(axis) is True

    def test_continuous_axis_not_discrete(self):
        """Standard weight axis is not discrete"""
        axis = DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900)
        assert DiscreteAxisHandler.is_discrete(axis) is False

    def test_non_binary_range_not_discrete(self):
        """Axis with 0:0:2 range is not discrete"""
        axis = DSSAxis(name="LOOP", tag="LOOP", minimum=0, default=0, maximum=2)
        assert DiscreteAxisHandler.is_discrete(axis) is False


class TestCustomDiscreteAxisParsing:
    """Test parsing of custom discrete axes"""

    def test_parse_custom_discrete_axis(self):
        """Custom LOOP discrete axis is parsed correctly"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, Loopoff] @base
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        loop_axis = [a for a in doc.axes if a.tag == "LOOP"][0]
        assert loop_axis.minimum == 0
        assert loop_axis.default == 0
        assert loop_axis.maximum == 1

    def test_custom_discrete_labels_positional_values(self):
        """Custom discrete labels get positional values: first=0, second=1"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, Loopoff] @base
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        loop_axis = [a for a in doc.axes if a.tag == "LOOP"][0]
        assert len(loop_axis.mappings) == 2
        assert loop_axis.mappings[0].label == "Loopoff"
        assert loop_axis.mappings[0].user_value == 0.0
        assert loop_axis.mappings[0].design_value == 0.0
        assert loop_axis.mappings[1].label == "Loop"
        assert loop_axis.mappings[1].user_value == 1.0
        assert loop_axis.mappings[1].design_value == 1.0

    def test_custom_discrete_elidable(self):
        """@elidable flag works on custom discrete labels"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, Loopoff] @base
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        loop_axis = [a for a in doc.axes if a.tag == "LOOP"][0]
        assert loop_axis.mappings[0].elidable is True
        assert loop_axis.mappings[1].elidable is False

    def test_custom_discrete_source_coordinates_by_label(self):
        """Source coordinates resolve custom discrete labels correctly"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, Loopoff] @base
    Font-Loop [400, Loop]
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        assert doc.sources[0].location["LOOP"] == 0.0
        assert doc.sources[1].location["LOOP"] == 1.0

    def test_custom_discrete_source_coordinates_numeric(self):
        """Numeric coordinates still work for custom discrete axes"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, 0] @base
    Font-Loop [400, 1]
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        assert doc.sources[0].location["LOOP"] == 0.0
        assert doc.sources[1].location["LOOP"] == 1.0

    def test_multiple_custom_discrete_axes(self):
        """Multiple custom discrete axes parsed correctly"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop
    FILL discrete
        Outline @elidable
        Filled

sources [wght, LOOP, FILL]
    Font-Regular [400, Loopoff, Outline] @base
    Font-Loop-Filled [400, Loop, Filled]
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        loop_axis = [a for a in doc.axes if a.tag == "LOOP"][0]
        fill_axis = [a for a in doc.axes if a.tag == "FILL"][0]

        assert loop_axis.mappings[0].label == "Loopoff"
        assert loop_axis.mappings[0].user_value == 0.0
        assert loop_axis.mappings[1].label == "Loop"
        assert loop_axis.mappings[1].user_value == 1.0

        assert fill_axis.mappings[0].label == "Outline"
        assert fill_axis.mappings[0].user_value == 0.0
        assert fill_axis.mappings[1].label == "Filled"
        assert fill_axis.mappings[1].user_value == 1.0

        assert doc.sources[1].location["LOOP"] == 1.0
        assert doc.sources[1].location["FILL"] == 1.0


class TestMultipleBaseSourcesWithDiscrete:
    """Test multiple @base sources validation for discrete axes"""

    def test_two_base_sources_with_discrete_axis(self):
        """Two @base sources valid when discrete axis has different values"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [Regular, Loopoff] @base
    Font-Loop-Regular [Regular, Loop] @base
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(content)

        base_sources = [s for s in doc.sources if s.is_base]
        assert len(base_sources) == 2
        assert base_sources[0].location["LOOP"] == 0.0
        assert base_sources[1].location["LOOP"] == 1.0

    def test_two_base_sources_same_discrete_value_rejected(self):
        """Two @base at same discrete value is an error"""
        content = '''
family TestFont

axes
    wght 100:400:900
        Thin > 100
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Thin [Thin, Loopoff] @base
    Font-Regular [Regular, Loopoff] @base
'''
        with pytest.raises(ValueError, match="Multiple base sources"):
            parser = DSSParser(strict_mode=True)
            parser.parse(content)


class TestCustomDiscreteAxisWriting:
    """Test writing custom discrete axes"""

    def test_write_custom_discrete_keyword(self):
        """Writer outputs 'discrete' keyword for custom discrete axis"""
        doc = DSSDocument(family="TestFont")
        doc.axes = [
            DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900,
                    mappings=[DSSAxisMapping(400, 400, "Regular")]),
            DSSAxis(name="LOOP", tag="LOOP", minimum=0, default=0, maximum=1,
                    mappings=[
                        DSSAxisMapping(0, 0, "Loopoff", elidable=True),
                        DSSAxisMapping(1, 1, "Loop"),
                    ]),
        ]
        doc.sources = [
            DSSSource(name="Regular", filename="Font-Regular.ufo",
                      location={"weight": 400, "LOOP": 0}, is_base=True),
        ]

        writer = DSSWriter(use_label_coordinates=False)
        output = writer.write(doc)

        assert "LOOP discrete" in output

    def test_write_custom_discrete_simplified_labels(self):
        """Writer uses simplified label format for custom discrete axis"""
        doc = DSSDocument(family="TestFont")
        doc.axes = [
            DSSAxis(name="weight", tag="wght", minimum=100, default=400, maximum=900,
                    mappings=[DSSAxisMapping(400, 400, "Regular")]),
            DSSAxis(name="LOOP", tag="LOOP", minimum=0, default=0, maximum=1,
                    mappings=[
                        DSSAxisMapping(0, 0, "Loopoff", elidable=True),
                        DSSAxisMapping(1, 1, "Loop"),
                    ]),
        ]
        doc.sources = [
            DSSSource(name="Regular", filename="Font-Regular.ufo",
                      location={"weight": 400, "LOOP": 0}, is_base=True),
        ]

        writer = DSSWriter(use_label_coordinates=False)
        output = writer.write(doc)

        # Simplified format: just label names without "> value"
        assert "Loopoff @elidable" in output
        assert "Loop" in output
        # Should NOT have "> 0" or "> 1" format
        lines = output.split('\n')
        loop_label_lines = [l.strip() for l in lines if 'Loopoff' in l or l.strip() == 'Loop']
        for line in loop_label_lines:
            assert ">" not in line


class TestCustomDiscreteAxisRoundtrip:
    """Test roundtrip: parse → write → parse preserves custom discrete axes"""

    def test_roundtrip_custom_discrete(self):
        """Roundtrip preserves custom discrete axis structure"""
        original = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, 0] @base
    Font-Loop [400, 1]
'''
        # Parse
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(original)

        # Write
        writer = DSSWriter(use_label_coordinates=False)
        output = writer.write(doc)

        # Parse again
        parser2 = DSSParser(strict_mode=False)
        doc2 = parser2.parse(output)

        # Verify axis preserved
        loop_axis = [a for a in doc2.axes if a.tag == "LOOP"][0]
        assert loop_axis.minimum == 0
        assert loop_axis.default == 0
        assert loop_axis.maximum == 1
        assert len(loop_axis.mappings) == 2
        assert loop_axis.mappings[0].label == "Loopoff"
        assert loop_axis.mappings[0].user_value == 0.0
        assert loop_axis.mappings[0].elidable is True
        assert loop_axis.mappings[1].label == "Loop"
        assert loop_axis.mappings[1].user_value == 1.0

        # Verify source coordinates preserved
        assert doc2.sources[0].location["LOOP"] == 0.0
        assert doc2.sources[1].location["LOOP"] == 1.0

    def test_roundtrip_with_label_coordinates(self):
        """Roundtrip with label-based source coordinates"""
        original = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [Regular, Loopoff] @base
    Font-Loop [Regular, Loop]
'''
        parser = DSSParser(strict_mode=False)
        doc = parser.parse(original)

        writer = DSSWriter(use_label_coordinates=True)
        output = writer.write(doc)

        parser2 = DSSParser(strict_mode=False)
        doc2 = parser2.parse(output)

        assert doc2.sources[0].location["LOOP"] == 0.0
        assert doc2.sources[1].location["LOOP"] == 1.0


class TestCustomDiscreteAxisConversion:
    """Test DSS → DesignSpace conversion with custom discrete axes"""

    def test_dss_to_designspace_custom_discrete(self):
        """Custom discrete axis converts to DesignSpace with values attribute"""
        from src.dssketch.converters.dss_to_designspace import DSSToDesignSpace

        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [400, Loopoff] @base
    Font-Loop [400, Loop]

instances off
'''
        parser = DSSParser(strict_mode=False)
        dss_doc = parser.parse(content)

        converter = DSSToDesignSpace()
        ds = converter.convert(dss_doc)

        # Verify axes
        loop_axis = [a for a in ds.axes if a.tag == "LOOP"][0]
        assert loop_axis.minimum == 0
        assert loop_axis.default == 0
        assert loop_axis.maximum == 1

        # Verify source locations
        assert len(ds.sources) == 2
        source_loop_values = [s.location.get("LOOP", s.location.get("loop")) for s in ds.sources]
        assert 0.0 in source_loop_values
        assert 1.0 in source_loop_values

    def test_dss_to_designspace_multiple_base_with_discrete(self):
        """Multiple @base sources convert correctly for discrete axes"""
        from src.dssketch.converters.dss_to_designspace import DSSToDesignSpace

        content = '''
family TestFont

axes
    wght 100:400:900
        Regular > 400
    LOOP discrete
        Loopoff @elidable
        Loop

sources [wght, LOOP]
    Font-Regular [Regular, Loopoff] @base
    Font-Loop-Regular [Regular, Loop] @base

instances off
'''
        parser = DSSParser(strict_mode=False)
        dss_doc = parser.parse(content)

        converter = DSSToDesignSpace()
        ds = converter.convert(dss_doc)

        # Both base sources should have copyInfo=True
        base_sources = [s for s in ds.sources if s.copyInfo]
        assert len(base_sources) == 2
