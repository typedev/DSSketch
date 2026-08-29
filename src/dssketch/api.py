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


def convert_to_dss(
    designspace: DesignSpaceDocument,
    dss_path: str,
    optimize: bool = True,
    vars_threshold: int = 3,
    avar2_format: str = "matrix",
    return_report: bool = False,
):
    """
    Convert a DesignSpace object to DSSketch format and save to file.

    Args:
        designspace: DesignSpaceDocument object to convert
        dss_path: Path where the .dssketch file should be saved
        optimize: Whether to optimize the output (default True)
        vars_threshold: Minimum frequency for auto-generating avar2 variables.
                       0 = disabled, 3 = default (values appearing 3+ times)
        avar2_format: Format for avar2 output - "matrix" (default) or "linear"
        return_report: Also return the structured ConversionReport (default False)

    Returns:
        Path to the created DSS file, or a (path, ConversionReport) tuple when
        return_report is True. The report carries what the conversion could not
        express faithfully - see dssketch.core.report.

    Example:
        from fontTools.designspaceLib import DesignSpaceDocument
        import dssketch

        # Load a DesignSpace document
        ds = DesignSpaceDocument()
        ds.read("MyFont.designspace")

        # Convert to DSSketch (default settings)
        dssketch.convert_to_dss(ds, "MyFont.dssketch")

        # Convert without variables
        dssketch.convert_to_dss(ds, "MyFont.dssketch", vars_threshold=0)

        # Convert with linear avar2 format
        dssketch.convert_to_dss(ds, "MyFont.dssketch", avar2_format="linear")
    """
    # Convert DesignSpace to DSS document
    converter = DesignSpaceToDSS(vars_threshold=vars_threshold)
    dss_doc = converter.convert(designspace)

    # Write DSS document to file
    writer = DSSWriter(optimize=optimize, avar2_format=avar2_format)
    dss_content = writer.write(dss_doc)

    dss_file = Path(dss_path)
    with open(dss_file, "w", encoding="utf-8") as f:
        f.write(dss_content)

    if return_report:
        return str(dss_file), converter.report
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
        print(f"Family: {ds.default.familyName}")
        print(f"Axes: {[axis.name for axis in ds.axes]}")

        # Save to file if needed
        ds.write("MyFont.designspace")
    """
    dss_file = Path(dss_path)

    # Setup logger for conversion
    DSSketchLogger.setup_logger(str(dss_file))

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
        sources
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
    designspace: DesignSpaceDocument,
    optimize: bool = True,
    vars_threshold: int = 3,
    avar2_format: str = "matrix",
    return_report: bool = False,
):
    """
    Convert a DesignSpace object to DSSketch format string.

    Args:
        designspace: DesignSpaceDocument object to convert
        optimize: Whether to optimize the output (default True)
        vars_threshold: Minimum frequency for auto-generating avar2 variables.
                       0 = disabled, 3 = default (values appearing 3+ times)
        avar2_format: Format for avar2 output - "matrix" (default) or "linear"
        return_report: Also return the structured ConversionReport (default False)

    Returns:
        DSSketch format string, or a (string, ConversionReport) tuple when
        return_report is True. The report carries what the conversion could not
        express faithfully - see dssketch.core.report.

    Example:
        from fontTools.designspaceLib import DesignSpaceDocument
        import dssketch

        # Load a DesignSpace document
        ds = DesignSpaceDocument()
        ds.read("MyFont.designspace")

        # Convert to DSSketch string (default settings)
        dss_content = dssketch.convert_designspace_to_dss_string(ds)

        # Convert without variables
        dss_content = dssketch.convert_designspace_to_dss_string(ds, vars_threshold=0)

        # Convert with linear format
        dss_content = dssketch.convert_designspace_to_dss_string(ds, avar2_format="linear")
    """
    # Convert DesignSpace to DSS document
    converter = DesignSpaceToDSS(vars_threshold=vars_threshold)
    dss_doc = converter.convert(designspace)

    # Write DSS document to string
    writer = DSSWriter(optimize=optimize, avar2_format=avar2_format)
    dss_string = writer.write(dss_doc)

    if return_report:
        return dss_string, converter.report
    return dss_string
