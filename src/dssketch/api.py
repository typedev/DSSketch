"""
DSSketch Public API

High-level API functions for integrating DSSketch into other projects.
Provides simple conversion functions that accept DesignSpace objects and DSS file paths.
"""

from pathlib import Path
from typing import Union

from fontTools.designspaceLib import DesignSpaceDocument

from .converters.designspace_to_dss import DesignSpaceToDSS
from .converters.dss_to_designspace import DSSToDesignSpace
from .parsers.dss_parser import DSSParser
from .utils.logging import DSSketchLogger
from .writers.dss_writer import DSSWriter


def convert_to_dss(designspace: DesignSpaceDocument, dss_path: str, optimize: bool = True) -> str:
    """
    Convert a DesignSpace object to DSSketch format and save to file.

    Args:
        designspace: DesignSpaceDocument object to convert
        dss_path: Path where the .dssketch file should be saved
        optimize: Whether to optimize the output (default True)

    Returns:
        Path to the created DSS file

    Example:
        from fontTools.designspaceLib import DesignSpaceDocument
        import dssketch

        # Load a DesignSpace document
        ds = DesignSpaceDocument()
        ds.read("MyFont.designspace")

        # Convert to DSSketch
        dssketch.convert_to_dss(ds, "MyFont.dssketch")
    """
    # Convert DesignSpace to DSS document
    converter = DesignSpaceToDSS()
    dss_doc = converter.convert(designspace)

    # Write DSS document to file
    writer = DSSWriter(optimize=optimize)
    dss_content = writer.write(dss_doc)

    dss_file = Path(dss_path)
    with open(dss_file, "w", encoding="utf-8") as f:
        f.write(dss_content)

    return str(dss_file)


def convert_to_designspace(dss_path: str) -> DesignSpaceDocument:
    """
    Convert a DSSketch file to a DesignSpace object.

    Args:
        dss_path: Path to the .dssketch or .dss file to convert

    Returns:
        DesignSpaceDocument object

    Example:
        import dssketch

        # Convert DSSketch to DesignSpace object
        ds = dssketch.convert_to_designspace("MyFont.dssketch")

        # Use the DesignSpace object
        DSSketchLogger.info(f"Family: {ds.default.familyName}")
        DSSketchLogger.info(f"Axes: {[axis.name for axis in ds.axes]}")

        # Save to file if needed
        ds.write("MyFont.designspace")
    """
    dss_file = Path(dss_path)

    # Parse DSS file
    parser = DSSParser()
    dss_doc = parser.parse_file(str(dss_file))

    # Convert to DesignSpace
    converter = DSSToDesignSpace(base_path=dss_file.parent)
    ds_doc = converter.convert(dss_doc)

    return ds_doc


def convert_dss_string_to_designspace(
    dss_content: str, base_path: Union[str, Path] = None
) -> DesignSpaceDocument:
    """
    Convert DSSketch content string to a DesignSpace object.

    Args:
        dss_content: DSSketch format string content
        base_path: Base path for resolving relative UFO paths (optional)

    Returns:
        DesignSpaceDocument object

    Example:
        import dssketch

        dss_content = '''
        family MyFont
        axes
            wght 100:400:900
                Light > 100
                Regular > 400
                Bold > 900
        masters
            Light.ufo [100]
            Regular.ufo [400] @base
            Bold.ufo [900]
        '''

        ds = dssketch.convert_dss_string_to_designspace(dss_content)
    """
    # Parse DSS content
    parser = DSSParser()
    dss_doc = parser.parse(dss_content)

    # Convert to DesignSpace
    base_path = Path(base_path) if base_path else None
    converter = DSSToDesignSpace(base_path=base_path)
    ds_doc = converter.convert(dss_doc)

    return ds_doc


def convert_designspace_to_dss_string(
    designspace: DesignSpaceDocument, optimize: bool = True
) -> str:
    """
    Convert a DesignSpace object to DSSketch format string.

    Args:
        designspace: DesignSpaceDocument object to convert
        optimize: Whether to optimize the output (default True)

    Returns:
        DSSketch format string

    Example:
        from fontTools.designspaceLib import DesignSpaceDocument
        import dssketch

        # Load a DesignSpace document
        ds = DesignSpaceDocument()
        ds.read("MyFont.designspace")

        # Convert to DSSketch string
        dss_content = dssketch.convert_designspace_to_dss_string(ds)
        DSSketchLogger.info(dss_content)
    """
    # Convert DesignSpace to DSS document
    converter = DesignSpaceToDSS()
    dss_doc = converter.convert(designspace)

    # Write DSS document to string
    writer = DSSWriter(optimize=optimize)
    return writer.write(dss_doc)
