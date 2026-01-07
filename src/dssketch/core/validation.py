"""
UFO file validation for DSSketch

This module handles validation of UFO files referenced in DSSketch documents.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from defcon import Font

from ..core.models import DSSDocument
from ..utils.logging import DSSketchLogger


@dataclass
class ValidationReport:
    """Report of UFO file validation"""

    missing_files: List[str] = field(default_factory=list)
    invalid_ufos: List[str] = field(default_factory=list)
    path_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return (
            len(self.missing_files) > 0 or len(self.invalid_ufos) > 0 or len(self.path_errors) > 0
        )

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class UFOValidator:
    """Validate UFO files existence and basic structure"""

    @staticmethod
    def validate_ufo_files(dss_doc: DSSDocument, dssketch_file_path: str) -> ValidationReport:
        """Validate UFO files existence and basic structure"""
        report = ValidationReport()

        # Determine base path for sources
        dssketch_dir = Path(dssketch_file_path).parent

        if dss_doc.path:
            # Path specified in DSSketch file
            if Path(dss_doc.path).is_absolute():
                base_path = Path(dss_doc.path)
            else:
                base_path = dssketch_dir / dss_doc.path
        else:
            # Default: same directory as .dssketch file
            base_path = dssketch_dir

        # Validate base path exists
        if not base_path.exists():
            report.path_errors.append(f"Sources path does not exist: {base_path}")
            return report

        if not base_path.is_dir():
            report.path_errors.append(f"Sources path is not a directory: {base_path}")
            return report

        # Check each source file
        for source in dss_doc.sources:
            ufo_path = base_path / source.filename

            if not ufo_path.exists():
                report.missing_files.append(str(ufo_path))
                continue

            # Basic UFO validation
            if not UFOValidator._is_valid_ufo(ufo_path):
                report.invalid_ufos.append(str(ufo_path))

            # Check if filename ends with .ufo
            if not source.filename.endswith((".ufo", ".ufoz")):
                report.warnings.append(f"Source filename should end with .ufo(z): {source.filename}")

        return report

    @staticmethod
    def _is_valid_ufo(ufo_path: Path) -> bool:
        """Basic UFO structure validation"""
        if not ufo_path.is_dir():
            return False

        # Check for required UFO files
        required_files = ["metainfo.plist", "fontinfo.plist"]
        for req_file in required_files:
            if not (ufo_path / req_file).exists():
                return False

        # Check for glyphs directory or layer contents
        if not (ufo_path / "glyphs").exists() and not (ufo_path / "glyphs.contents.plist").exists():
            return False

        return True


class UFOGlyphExtractor:
    """Extract glyph names from UFO files for wildcard pattern matching"""

    @staticmethod
    def get_glyph_names_from_ufo(ufo_path: Path) -> Set[str]:
        """Extract all glyph names from a UFO file"""
        try:
            font = Font(str(ufo_path))
            return set(font.keys())
        except Exception as e:
            DSSketchLogger.warning(f"Could not read glyphs from {ufo_path}: {e}")
            return set()

    @staticmethod
    def get_all_glyphs_from_sources(sources, base_path: Path = None) -> Set[str]:
        """Extract all unique glyph names from all sources

        Args:
            sources: List of source descriptors or DSSMaster objects
            base_path: Base path for resolving relative UFO paths
        """
        all_glyphs = set()

        for source in sources:
            # Handle both DesignSpace sources and DSSMaster objects
            filename = getattr(source, "filename", None)
            if not filename:
                continue

            # Determine the full path to the UFO file
            source_path = Path(filename)

            if source_path.is_absolute():
                ufo_path = source_path
            elif base_path:
                # If source filename already includes a relative path (like "sources/file.ufo"),
                # and base_path also points to sources, we need to avoid duplication
                if source_path.parts[0] == base_path.name:
                    # Remove the first part and use base_path's parent
                    relative_parts = source_path.parts[1:]
                    ufo_path = base_path / Path(*relative_parts)
                else:
                    ufo_path = base_path / filename
            else:
                ufo_path = source_path

            if ufo_path.exists():
                glyph_names = UFOGlyphExtractor.get_glyph_names_from_ufo(ufo_path)
                all_glyphs.update(glyph_names)

        return all_glyphs
