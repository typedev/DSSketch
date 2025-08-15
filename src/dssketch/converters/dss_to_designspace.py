"""
DSS to DesignSpace converter

This module converts DSS documents back to DesignSpace format and includes methods for:

1. Converting DSS axes to DesignSpace axes (including discrete axes handling)
2. Converting DSS masters to DesignSpace sources
3. Converting DSS instances to DesignSpace instances
4. Converting DSS rules to DesignSpace rules with wildcard expansion
5. UFO file reading capabilities for glyph name extraction
"""

from pathlib import Path
from typing import List, Optional, Tuple

# UFO reading
from defcon import Font

# FontTools imports
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
    DiscreteAxisDescriptor,
    InstanceDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)

# Import instances module
from ..core.instances import createInstances

# Import models from core
from ..core.models import DSSAxis, DSSDocument, DSSInstance, DSSMaster, DSSRule

# Import validation components
from ..core.validation import UFOGlyphExtractor
from ..utils.logging import DSSketchLogger

# Import utility classes
from ..utils.patterns import PatternMatcher


class DSSToDesignSpace:
    """Convert DSS to DesignSpace format"""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize converter with optional base path for UFO files"""
        self.base_path = base_path

    def convert(self, dss_doc: DSSDocument) -> DesignSpaceDocument:
        """Convert DSS document to DesignSpace document"""
        doc = DesignSpaceDocument()

        # Convert axes
        for dss_axis in dss_doc.axes:
            axis = self._convert_axis(dss_axis)
            doc.addAxis(axis)

        # Convert masters/sources
        for source_index, dss_master in enumerate(dss_doc.masters, 1):
            source = self._convert_master(dss_master, dss_doc, source_index)
            doc.addSource(source)

        # Convert instances
        if dss_doc.instances_auto:
            # Use sophisticated instance generation from instances module
            enhanced_doc, _ = createInstances(
                doc, dss_doc=dss_doc, defaultFolder="instances", skipFilter={}, filterInstances={}
            )
            # Copy the generated instances back to our document
            doc.instances = enhanced_doc.instances
        else:
            # Use explicit instances from DSS document
            for dss_instance in dss_doc.instances:
                instance = self._convert_instance(dss_instance, dss_doc)
                doc.addInstance(instance)

        # Convert rules
        for dss_rule in dss_doc.rules:
            rule = self._convert_rule(dss_rule, doc)
            if rule:
                doc.addRule(rule)

        return doc

    def _convert_axis(self, dss_axis: DSSAxis):
        """Convert DSS axis to DesignSpace axis (returns AxisDescriptor or DiscreteAxisDescriptor)"""
        # Check if this is a discrete axis (like italic)
        is_discrete = (
            dss_axis.minimum == 0
            and dss_axis.maximum == 1
            and dss_axis.name.lower() in ["italic", "ital"]
        )

        if is_discrete:
            # Create DiscreteAxisDescriptor for discrete axes
            axis = DiscreteAxisDescriptor()
            axis.name = dss_axis.name
            axis.tag = dss_axis.tag
            axis.labelNames = {"en": dss_axis.name.title()}  # Weight, Italic, etc.
            axis.values = [0, 1]
            axis.default = dss_axis.default

            # Add discrete labels
            axis.axisLabels = []

            if not dss_axis.mappings:
                # Default discrete labels for italic
                upright_label = AxisLabelDescriptor(name="Upright", userValue=0, elidable=True)
                italic_label = AxisLabelDescriptor(name="Italic", userValue=1, elidable=False)
                axis.axisLabels = [upright_label, italic_label]
            else:
                # Use custom mappings for discrete axis labels
                for mapping in dss_axis.mappings:
                    label_desc = AxisLabelDescriptor(
                        name=mapping.label,
                        userValue=mapping.user_value,
                        elidable=mapping.elidable,
                    )
                    axis.axisLabels.append(label_desc)
        else:
            # Create regular AxisDescriptor for continuous axes
            axis = AxisDescriptor()
            axis.name = dss_axis.name
            axis.tag = dss_axis.tag
            axis.labelNames = {"en": dss_axis.name.title()}  # Weight, Italic, etc.
            axis.minimum = dss_axis.minimum
            axis.default = dss_axis.default
            axis.maximum = dss_axis.maximum

            # Continuous axis - add mappings and labels
            axis.map = []
            axis.axisLabels = []

            for mapping in dss_axis.mappings:
                # Add mapping as tuple (older format)
                axis.map.append((mapping.user_value, mapping.design_value))

                # Add label
                label_desc = AxisLabelDescriptor(
                    name=mapping.label,
                    userValue=mapping.user_value,
                    elidable=mapping.elidable,
                )
                axis.axisLabels.append(label_desc)

        return axis

    def _convert_master(
        self, dss_master: DSSMaster, dss_doc: DSSDocument, source_index: int
    ) -> SourceDescriptor:
        """Convert DSS master to DesignSpace source"""
        source = SourceDescriptor()

        # If path is specified in DSS document, prepend it to filename
        if dss_doc.path:
            # Ensure path uses forward slashes for consistency
            path = dss_doc.path.replace("\\", "/")
            if not path.endswith("/"):
                path += "/"
            source.filename = path + dss_master.filename
        else:
            source.filename = dss_master.filename

        # Assign automatic name
        source.name = f"source.{source_index}"

        # Try to read familyName and styleName from UFO file
        ufo_info = self._read_ufo_info(source.filename)
        if ufo_info:
            source.familyName = ufo_info.get("familyName", dss_doc.family)
            source.styleName = ufo_info.get("styleName", dss_master.name)
        else:
            source.familyName = dss_doc.family
            source.styleName = dss_master.name

        source.location = dss_master.location.copy()

        # Set copy flags
        if dss_master.is_base:
            source.copyLib = True
            source.copyInfo = True
            source.copyGroups = True
            source.copyFeatures = True

        return source

    def _read_ufo_info(self, filename: str) -> Optional[dict]:
        """Read familyName and styleName from UFO file"""
        try:
            # The filename already includes the full relative path from the base_path
            # (e.g., "masters/SuperFont-Black.ufo")
            ufo_path = Path(filename)
            if self.base_path and not ufo_path.is_absolute():
                ufo_path = self.base_path / filename

            if not ufo_path.exists() or not ufo_path.is_dir():
                return None

            font = Font(str(ufo_path))
            return {"familyName": font.info.familyName, "styleName": font.info.styleName}
        except Exception:
            # If UFO reading fails, return None to fall back to defaults
            return None

    def _convert_instance(
        self, dss_instance: DSSInstance, dss_doc: DSSDocument
    ) -> InstanceDescriptor:
        """Convert DSS instance to DesignSpace instance"""
        instance = InstanceDescriptor()
        instance.familyName = dss_instance.familyname or dss_doc.family
        instance.styleName = dss_instance.stylename
        instance.filename = dss_instance.filename
        instance.location = dss_instance.location.copy()

        # Generate PostScript name
        ps_family = instance.familyName.replace(" ", "").replace("-", "")
        ps_style = instance.styleName.replace(" ", "").replace("-", "")
        instance.postScriptFontName = f"{ps_family}-{ps_style}"

        return instance

    def _convert_rule(
        self, dss_rule: DSSRule, doc: DesignSpaceDocument
    ) -> Optional[RuleDescriptor]:
        """Convert DSS rule to DesignSpace rule

        Each DSSketch rule becomes exactly ONE DesignSpace rule with all
        wildcard-expanded substitutions as multiple <sub> elements.
        """
        rule = RuleDescriptor()
        rule.name = dss_rule.name

        # Handle wildcard patterns
        if dss_rule.pattern and dss_rule.to_pattern:
            # Expand wildcard patterns to concrete substitutions
            substitutions = self._expand_wildcard_pattern(dss_rule, doc)
            # Sort substitutions by source glyph name for consistent output
            rule.subs = sorted(substitutions, key=lambda x: x[0])
        else:
            # Use existing substitutions, also sorted
            rule.subs = sorted(dss_rule.substitutions, key=lambda x: x[0])

        # Skip empty rules (no valid substitutions)
        if not rule.subs:
            DSSketchLogger.warning(
                f"Skipping rule '{dss_rule.name}' - no valid substitutions found"
            )
            return None

        # Add conditions using modern conditionSets format
        if dss_rule.conditions:
            rule.conditionSets = [[]]  # Create one condition set
            for condition in dss_rule.conditions:
                # Find correct axis name from DesignSpace document
                axis_name = self._find_axis_name_in_designspace(condition["axis"], doc)

                cond_dict = {
                    "name": axis_name,
                    "minimum": condition["minimum"],
                    "maximum": condition["maximum"],
                }
                rule.conditionSets[0].append(cond_dict)

        return rule

    def _find_axis_name_in_designspace(self, dss_axis_name: str, doc: DesignSpaceDocument) -> str:
        """Find correct axis name in DesignSpace document based on DSS axis name

        DSS rules might use capitalized names like 'Weight' or 'Italic'
        but DesignSpace axes use lowercase like 'weight' or 'italic'
        """
        dss_name_lower = dss_axis_name.lower()

        # First try exact match with axis.name
        for axis in doc.axes:
            if axis.name.lower() == dss_name_lower:
                return axis.name

        # Then try common variations and tag matching
        axis_mapping = {
            "weight": ["wght", "weight"],
            "width": ["wdth", "width"],
            "italic": ["ital", "italic"],
            "slant": ["slnt", "slant"],
            "optical": ["opsz", "optical"],
        }

        for standard_name, variations in axis_mapping.items():
            if dss_name_lower in variations or dss_name_lower == standard_name:
                # Find matching axis in document
                for axis in doc.axes:
                    if axis.name.lower() == standard_name or axis.tag.lower() in variations:
                        return axis.name

        # If no match found, return original (fallback)
        DSSketchLogger.warning(f"Could not find axis '{dss_axis_name}' in DesignSpace, using as-is")
        return dss_axis_name

    def _expand_wildcard_pattern(
        self, dss_rule: DSSRule, doc: DesignSpaceDocument
    ) -> List[Tuple[str, str]]:
        """Expand wildcard patterns to concrete glyph substitutions"""
        # Extract all glyph names from UFO files for validation
        # Ensure base_path is a Path object
        base_path = (
            Path(self.base_path)
            if self.base_path and not isinstance(self.base_path, Path)
            else self.base_path
        )
        all_glyphs = UFOGlyphExtractor.get_all_glyphs_from_sources(doc.sources, base_path)

        if not dss_rule.pattern or not dss_rule.to_pattern:
            # Validate regular substitutions (non-wildcard)
            validated_substitutions = []
            for from_glyph, to_glyph in dss_rule.substitutions:
                if to_glyph in all_glyphs:
                    validated_substitutions.append((from_glyph, to_glyph))
                else:
                    DSSketchLogger.warning(
                        f"Skipping substitution {from_glyph} -> {to_glyph} - target glyph '{to_glyph}' not found in UFO files"
                    )
            return validated_substitutions

        # For wildcard patterns, all_glyphs is already extracted above

        # Parse patterns from dss_rule.pattern
        patterns = dss_rule.pattern.split()

        # Find matching glyphs
        matching_glyphs = PatternMatcher.find_matching_glyphs(patterns, all_glyphs)

        # Generate substitutions
        substitutions = []
        to_suffix = dss_rule.to_pattern

        for glyph in matching_glyphs:
            if to_suffix.startswith("."):
                # Append suffix: dollar -> dollar.rvrn
                # But skip if glyph already has this suffix to avoid .rvrn.rvrn
                if glyph.endswith(to_suffix):
                    continue
                target = glyph + to_suffix
            else:
                # Replace with target: might support other patterns in future
                target = to_suffix

            # Validate that target glyph exists in the font
            if target in all_glyphs:
                substitutions.append((glyph, target))
            else:
                # Skip invalid substitutions and warn about missing target glyph
                DSSketchLogger.warning(
                    f"Skipping substitution {glyph} -> {target} - target glyph '{target}' not found in UFO files"
                )
                pass

        return substitutions
