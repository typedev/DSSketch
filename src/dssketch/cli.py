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
    parser.add_argument(
        "--no-validation", action="store_true", help="Skip UFO validation (not recommended)"
    )
    parser.add_argument("--allow-missing-ufos", action="store_true", help="Allow missing UFO files")

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

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            if output_format == "designspace":
                output_path = input_path.with_suffix(".designspace")
            else:
                output_path = input_path.with_suffix(".dssketch")

        DSSketchLogger.info(f"Converting {input_path.name} to {output_path.name}")

        # Convert based on detected format
        if output_format == "designspace":
            # Convert .dssketch/.dss to .designspace
            DSSketchLogger.info("Starting DSSketch to DesignSpace conversion")
            parser = DSSParser()
            dss_data = parser.parse_file(str(input_path))

            converter = DSSToDesignSpace()
            doc = converter.convert(dss_data)
            doc.write(output_path)

        else:
            # Convert .designspace to .dssketch
            DSSketchLogger.info("Starting DesignSpace to DSSketch conversion")
            converter = DesignSpaceToDSS()
            dss_data = converter.convert(
                str(input_path),
                validate_ufos=not args.no_validation,
                allow_missing_ufos=args.allow_missing_ufos,
            )

            writer = DSSWriter()
            writer.write_file(str(output_path), dss_data)

        DSSketchLogger.success(f"Conversion completed: {input_path} → {output_path}")
        return 0

    except Exception as e:
        DSSketchLogger.error(f"Error during conversion: {e}")
        return 1
    finally:
        DSSketchLogger.cleanup()


if __name__ == "__main__":
    exit(main())
