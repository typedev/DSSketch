"""
DSSketch - Compact format for DesignSpace files

This package provides bidirectional conversion between compact .dssketch format
and verbose .designspace XML files for variable font design.
"""

__version__ = "1.4.0"

# Light components: stdlib + PyYAML only. Importing these must never pull in
# defcon or fontTools, so that a parse-only consumer (e.g. a diff tool reading
# a .dssketch from git) can use DSSParser/DSSWriter without the UFO stack.
from .core.mappings import Standards, UnifiedMappings
from .core.models import DSSAxis, DSSDocument, DSSInstance, DSSSource, DSSRule
from .core.report import (
    AVAR2_UNKNOWN_AXIS,
    AXIS_LABEL_DATA_DROPPED,
    AXIS_OUTPUT_ONLY_VISIBLE,
    CATEGORY_AXES,
    CATEGORY_DOCUMENT,
    CATEGORY_INSTANCES,
    CATEGORY_RULES,
    CATEGORY_SKETCH,
    CATEGORY_SOURCES,
    DOCUMENT_ELIDED_FALLBACK_DROPPED,
    DOCUMENT_FAMILY_UNKNOWN,
    DOCUMENT_LIB_DROPPED,
    DOCUMENT_LOCATION_LABELS_DROPPED,
    DOCUMENT_TRANSLATION_MISSING,
    DOCUMENT_TRANSLATIONS_DIFFER,
    DOCUMENT_VARIABLE_FONTS_DROPPED,
    INSTANCE_EXTRA,
    INSTANCE_FIELDS_DROPPED,
    INSTANCE_RENAMED,
    INSTANCE_UNREACHABLE,
    INSTANCE_WEIGHT_NOT_LAST,
    RULE_DROPPED_EMPTY,
    RULE_GLYPH_NOT_IN_DEFAULT,
    RULE_SUBSTITUTIONS_SKIPPED,
    RULES_PROCESSING_LAST_DROPPED,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SKETCH_VALIDATION_MESSAGE,
    SOURCE_FIELDS_DROPPED,
    ConversionIssue,
    ConversionReport,
    InstanceRef,
)
from .core.validation import UFOValidator, ValidationReport
from .parsers.dss_parser import DSSParser
from .writers.dss_writer import DSSWriter

# Converters need fontTools.designspaceLib; they load on first access.
_LAZY = {
    "convert_designspace_to_dss_string": ".api",
    "convert_dss_string_to_designspace": ".api",
    "convert_to_designspace": ".api",
    "convert_to_dss": ".api",
    "DesignSpaceToDSS": ".converters.designspace_to_dss",
    "DSSToDesignSpace": ".converters.dss_to_designspace",
}


def __getattr__(name):
    if name in _LAZY:
        import importlib

        value = getattr(importlib.import_module(_LAZY[name], __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


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
    # Structured conversion diagnostics
    "ConversionReport",
    "ConversionIssue",
    "InstanceRef",
    "CATEGORY_AXES",
    "CATEGORY_SOURCES",
    "CATEGORY_INSTANCES",
    "CATEGORY_RULES",
    "CATEGORY_DOCUMENT",
    "CATEGORY_SKETCH",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",
    "INSTANCE_UNREACHABLE",
    "INSTANCE_RENAMED",
    "INSTANCE_EXTRA",
    "INSTANCE_FIELDS_DROPPED",
    "INSTANCE_WEIGHT_NOT_LAST",
    "AXIS_OUTPUT_ONLY_VISIBLE",
    "AXIS_LABEL_DATA_DROPPED",
    "AVAR2_UNKNOWN_AXIS",
    "SOURCE_FIELDS_DROPPED",
    "RULES_PROCESSING_LAST_DROPPED",
    "RULE_GLYPH_NOT_IN_DEFAULT",
    "RULE_SUBSTITUTIONS_SKIPPED",
    "RULE_DROPPED_EMPTY",
    "DOCUMENT_LIB_DROPPED",
    "DOCUMENT_ELIDED_FALLBACK_DROPPED",
    "DOCUMENT_LOCATION_LABELS_DROPPED",
    "DOCUMENT_VARIABLE_FONTS_DROPPED",
    "DOCUMENT_FAMILY_UNKNOWN",
    "DOCUMENT_TRANSLATION_MISSING",
    "DOCUMENT_TRANSLATIONS_DIFFER",
    "SKETCH_VALIDATION_MESSAGE",
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

    from .converters.designspace_to_dss import DesignSpaceToDSS
    from .converters.dss_to_designspace import DSSToDesignSpace

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
