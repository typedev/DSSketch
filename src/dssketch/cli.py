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
        print(f"Error: Input file {input_path} does not exist")
        return 1

    try:
        # Auto-detect output format based on input extension
        if input_path.suffix.lower() in [".dssketch", ".dss"]:
            output_format = "designspace"
        elif input_path.suffix.lower() == ".designspace":
            output_format = "dssketch"
        else:
            print(f"Error: Unsupported input format {input_path.suffix}")
            print("Supported formats: .dssketch, .dss, .designspace")
            return 1

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            if output_format == "designspace":
                output_path = input_path.with_suffix(".designspace")
            else:
                output_path = input_path.with_suffix(".dssketch")

        # Convert based on detected format
        if output_format == "designspace":
            # Convert .dssketch/.dss to .designspace
            parser = DSSParser()
            dss_data = parser.parse_file(str(input_path))

            converter = DSSToDesignSpace()
            doc = converter.convert(dss_data)
            doc.write(output_path)

        else:
            # Convert .designspace to .dssketch
            converter = DesignSpaceToDSS()
            dss_data = converter.convert(
                str(input_path),
                validate_ufos=not args.no_validation,
                allow_missing_ufos=args.allow_missing_ufos,
            )

            writer = DSSWriter()
            writer.write_file(str(output_path), dss_data)

        print(f"Conversion completed: {input_path} → {output_path}")
        return 0

    except Exception as e:
        print(f"Error during conversion: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
