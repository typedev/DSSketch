#!/usr/bin/env python3
"""
DesignSpace Sketch CLI
Command-line interface for converting between .dssketch and .designspace formats
"""

import argparse
from pathlib import Path

from . import (
    DesignSpaceToDSS,
    DSSParser,
    DSSToDesignSpace,
    DSSWriter,
    UFOValidator,
)
from .utils.logging import DSSketchLogger


def main():
    """Simplified CLI for DesignSpace Sketch conversion"""
    parser = argparse.ArgumentParser(
        prog="dssketch",
        description="Simple converter between .dssketch and .designspace formats\n"
        "Automatically detects input format and converts to the other format.",
    )
    parser.add_argument("input", help="Input file (.dssketch or .designspace)")
    parser.add_argument("-o", "--output", help="Output file (optional, defaults to same directory)")

    # avar2 format options (mutually exclusive)
    avar2_group = parser.add_mutually_exclusive_group()
    avar2_group.add_argument(
        "--matrix",
        action="store_true",
        default=True,
        help="Use matrix format for avar2 output (default)",
    )
    avar2_group.add_argument(
        "--linear",
        action="store_true",
        help="Use linear format for avar2 output",
    )

    # avar2 variable generation options (mutually exclusive)
    vars_group = parser.add_mutually_exclusive_group()
    vars_group.add_argument(
        "--novars",
        action="store_true",
        help="Disable automatic variable generation for avar2",
    )
    vars_group.add_argument(
        "--vars",
        type=int,
        nargs="?",
        const=3,
        default=3,
        metavar="N",
        help="Generate variables for values appearing N+ times (default: 3)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        DSSketchLogger.error(f"Input file {input_path} does not exist")
        return 1

    # Setup logging for this conversion
    DSSketchLogger.setup_logger(str(input_path))

    try:
        # Auto-detect output format based on input extension
        if input_path.suffix.lower() in [".dssketch", ".dss"]:
            output_format = "designspace"
        elif input_path.suffix.lower() == ".designspace":
            output_format = "dssketch"
        else:
            DSSketchLogger.error(f"Unsupported input format {input_path.suffix}")
            DSSketchLogger.error("Supported formats: .dssketch, .dss, .designspace")
            return 1

        # Convert based on detected format
        if output_format == "designspace":
            # Convert .dssketch/.dss to .designspace
            DSSketchLogger.info("Starting DSSketch to DesignSpace conversion")
            parser = DSSParser()
            dss_doc = parser.parse_file(str(input_path))

            # Simple UFO validation with basic error handling
            validation_report = UFOValidator.validate_ufo_files(dss_doc, str(input_path))
            if validation_report.has_errors:
                if validation_report.path_errors:
                    for error in validation_report.path_errors:
                        DSSketchLogger.warning(f"Path error: {error}")

                if validation_report.missing_files:
                    DSSketchLogger.warning(f"Missing UFO files ({len(validation_report.missing_files)}):")
                    for file_path in validation_report.missing_files:
                        DSSketchLogger.warning(f"  - {file_path}")

                if validation_report.invalid_ufos:
                    DSSketchLogger.warning(f"Invalid UFO files ({len(validation_report.invalid_ufos)}):")
                    for file_path in validation_report.invalid_ufos:
                        DSSketchLogger.warning(f"  - {file_path}")

                DSSketchLogger.warning("Continuing conversion despite validation issues...")

            base_path = input_path.parent
            converter = DSSToDesignSpace(base_path)
            ds_doc = converter.convert(dss_doc)

            output_path = (
                Path(args.output) if args.output else input_path.with_suffix(".designspace")
            )
            ds_doc.write(str(output_path))
            DSSketchLogger.success(f"Converted {input_path.name} -> {output_path.name}")
            print(f"✓ Conversion completed successfully: {output_path}")

        elif output_format == "dssketch":
            # Convert .designspace to .dssketch
            DSSketchLogger.info("Starting DesignSpace to DSSketch conversion")

            # Determine variable threshold (0 = disabled)
            vars_threshold = 0 if args.novars else args.vars

            converter = DesignSpaceToDSS(vars_threshold=vars_threshold)
            dss_doc = converter.convert_file(str(input_path))

            # Load DesignSpace document for glyph validation
            from fontTools.designspaceLib import DesignSpaceDocument

            ds_doc = DesignSpaceDocument.fromfile(str(input_path))

            # Determine avar2 format
            avar2_format = "linear" if args.linear else "matrix"

            writer = DSSWriter(
                optimize=True,
                ds_doc=ds_doc,
                base_path=str(input_path.parent),
                avar2_format=avar2_format,
            )
            dss_content = writer.write(dss_doc)

            output_path = Path(args.output) if args.output else input_path.with_suffix(".dssketch")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(dss_content)
            DSSketchLogger.success(f"Converted {input_path.name} -> {output_path.name}")
            print(f"✓ Conversion completed successfully: {output_path}")

    except Exception as e:
        import traceback

        # Format error message with proper line breaks
        error_msg = str(e)
        if '\n' in error_msg:
            # Split multi-line error messages
            lines = error_msg.split('\n')
            DSSketchLogger.error(f"Error during conversion:")
            for line in lines:
                if line.strip():  # Skip empty lines
                    DSSketchLogger.error(f"  {line}")
        else:
            DSSketchLogger.error(f"Error during conversion: {error_msg}")

        DSSketchLogger.debug("Full traceback:")
        DSSketchLogger.debug(traceback.format_exc())
        return 1
    finally:
        # Always print log file path for easy IDE access
        log_path = DSSketchLogger.get_log_file_path()
        if log_path:
            print(f"\nLog file: {log_path}")
        DSSketchLogger.cleanup()

    return 0


if __name__ == "__main__":
    exit(main())
