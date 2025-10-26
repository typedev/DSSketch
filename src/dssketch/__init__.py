"""
DSSketch - Compact format for DesignSpace files

This package provides bidirectional conversion between compact .dssketch format
and verbose .designspace XML files for variable font design.
"""

__version__ = "1.0.18"

# Import all components from modular structure
# Import high-level API functions
from .api import (
    convert_designspace_to_dss_string,
    convert_dss_string_to_designspace,
    convert_to_designspace,
    convert_to_dss,
)
from .converters.designspace_to_dss import DesignSpaceToDSS
from .converters.dss_to_designspace import DSSToDesignSpace
from .core.mappings import Standards, UnifiedMappings
from .core.models import DSSAxis, DSSDocument, DSSInstance, DSSSource, DSSRule
from .core.validation import UFOValidator, ValidationReport
from .parsers.dss_parser import DSSParser
from .writers.dss_writer import DSSWriter

# Public API
__all__ = [
    # Version
    "__version__",
    # Core models
    "DSSDocument",
    "DSSAxis",
    "DSSSource",
    "DSSInstance",
    "DSSRule",
    # Mappings
    "UnifiedMappings",
    "Standards",  # Backward compatibility alias
    # Validation
    "UFOValidator",
    "ValidationReport",
    # Parser and Writer
    "DSSParser",
    "DSSWriter",
    # Converters
    "DesignSpaceToDSS",
    "DSSToDesignSpace",
    # Convenience functions
    "convert_file",
    "parse_dss",
    "write_dss",
    # High-level API functions
    "convert_to_dss",
    "convert_to_designspace",
    "convert_dss_string_to_designspace",
    "convert_designspace_to_dss_string",
]


def convert_file(input_path: str, output_path: str = None, optimize: bool = True):
    """High-level conversion function between .designspace and .dssketch formats

    Args:
        input_path: Path to input file (.designspace or .dssketch)
        output_path: Path to output file (auto-detected if None)
        optimize: Whether to optimize output (default True)

    Returns:
        Path to output file
    """
    from pathlib import Path

    input_file = Path(input_path)

    if not output_path:
        if input_file.suffix.lower() == ".designspace":
            output_path = input_file.with_suffix(".dssketch")
        elif input_file.suffix.lower() in [".dssketch", ".dss"]:
            output_path = input_file.with_suffix(".designspace")
        else:
            raise ValueError(f"Unknown input file format: {input_file.suffix}")

    output_file = Path(output_path)

    if input_file.suffix.lower() == ".designspace":
        # Convert DesignSpace to DSS
        converter = DesignSpaceToDSS()
        dss_doc = converter.convert_file(str(input_file))

        writer = DSSWriter(optimize=optimize)
        dss_content = writer.write(dss_doc)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(dss_content)

    elif input_file.suffix.lower() in [".dssketch", ".dss"]:
        # Convert DSS to DesignSpace
        parser = DSSParser()
        dss_doc = parser.parse_file(str(input_file))

        converter = DSSToDesignSpace(base_path=input_file.parent)
        ds_doc = converter.convert(dss_doc)

        ds_doc.write(str(output_file))

    else:
        raise ValueError(f"Unsupported input format: {input_file.suffix}")

    return str(output_file)


def parse_dss(content: str) -> DSSDocument:
    """Parse DSS content string into DSSDocument

    Args:
        content: DSS format string content

    Returns:
        Parsed DSSDocument
    """
    parser = DSSParser()
    return parser.parse(content)


def write_dss(dss_doc: DSSDocument, optimize: bool = True) -> str:
    """Write DSSDocument to DSS format string

    Args:
        dss_doc: DSSDocument to convert
        optimize: Whether to optimize output

    Returns:
        DSS format string
    """
    writer = DSSWriter(optimize=optimize)
    return writer.write(dss_doc)
