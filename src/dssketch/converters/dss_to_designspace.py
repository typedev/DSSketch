"""
DSS to DesignSpace converter

This module converts DSS documents back to DesignSpace format and includes methods for:

1. Converting DSS axes to DesignSpace axes (including discrete axes handling)
2. Converting DSS sources to DesignSpace sources
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
    AxisMappingDescriptor,
    DesignSpaceDocument,
    DiscreteAxisDescriptor,
    InstanceDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)

# Import instances module
from ..core.instances import createInstances

# Import models from core
from ..core.models import DSSAxis, DSSDocument, DSSInstance, DSSSource, DSSRule

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

        # Convert regular axes
        for dss_axis in dss_doc.axes:
            axis = self._convert_axis(dss_axis)
            doc.addAxis(axis)

        # Convert hidden axes (avar2)
        for dss_axis in dss_doc.hidden_axes:
            axis = self._convert_hidden_axis(dss_axis)
            doc.addAxis(axis)

        # Convert avar2 mappings
        if dss_doc.avar2_mappings:
            for dss_mapping in dss_doc.avar2_mappings:
                mapping = self._convert_avar2_mapping(dss_mapping, dss_doc)
                doc.axisMappings.append(mapping)

        # Convert sources
        for source_index, dss_source in enumerate(dss_doc.sources, 1):
            source = self._convert_source(dss_source, dss_doc, source_index)
            doc.addSource(source)

        # Convert instances
        if dss_doc.instances_auto:
            # Use sophisticated instance generation from instances module
            enhanced_doc, _ = createInstances(
                doc,
                dss_doc=dss_doc,
                defaultFolder="instances",
                skipFilter={},
                skipList=dss_doc.instances_skip if dss_doc.instances_skip else None,
                filterInstances={}
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
            # For custom axes (UPPERCASE tags), preserve original name
            # For standard axes, use title case (italic → Italic)
            if dss_axis.tag.isupper():
                axis.labelNames = {"en": dss_axis.name}
            else:
                axis.labelNames = {"en": dss_axis.name.title()}
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
            # For custom axes (UPPERCASE tags), preserve original name
            # For standard axes, use title case (weight → Weight)
            if dss_axis.tag.isupper():
                axis.labelNames = {"en": dss_axis.name}  # WDSP, GRAD, etc.
            else:
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

                # Add label only if it's not empty
                # (pure numeric mappings like opsz don't have labels)
                if mapping.label:
                    label_desc = AxisLabelDescriptor(
                        name=mapping.label,
                        userValue=mapping.user_value,
                        elidable=mapping.elidable,
                    )
                    axis.axisLabels.append(label_desc)

        return axis

    def _convert_hidden_axis(self, dss_axis: DSSAxis) -> AxisDescriptor:
        """Convert DSS hidden axis to DesignSpace axis with hidden=True

        Hidden axes are used by avar2 for parametric font design.
        They are not exposed to users but control internal font parameters.
        """
        axis = AxisDescriptor()
        axis.name = dss_axis.name
        axis.tag = dss_axis.tag
        axis.minimum = dss_axis.minimum
        axis.default = dss_axis.default
        axis.maximum = dss_axis.maximum
        axis.hidden = True  # Mark as hidden for avar2

        # Hidden axes typically don't have label names or mappings
        # but we set a basic labelNames for consistency
        axis.labelNames = {"en": dss_axis.name}

        return axis

    def _convert_avar2_mapping(self, dss_mapping, dss_doc: DSSDocument) -> AxisMappingDescriptor:
        """Convert DSS avar2 mapping to DesignSpace AxisMappingDescriptor

        DSS format:
            [opsz=Display, wght=Bold] > XOUC=84, YTUC=$YTUC

        DesignSpace XML format:
            <mapping description="name">
                <input>
                    <dimension name="Optical size" xvalue="144"/>
                    <dimension name="Weight" xvalue="700"/>
                </input>
                <output>
                    <dimension name="XOUC" xvalue="84"/>
                    <dimension name="YTUC" xvalue="750"/>
                </output>
            </mapping>
        """
        mapping = AxisMappingDescriptor()

        # Set description from mapping name
        if dss_mapping.name:
            mapping.description = dss_mapping.name

        # Convert input conditions
        # Input uses axis names/tags from DSS, need to resolve to DesignSpace axis names
        mapping.inputLocation = {}
        for axis_key, value in dss_mapping.input.items():
            # Find the axis name in DesignSpace (handles tag -> name conversion)
            axis_name = self._resolve_axis_name(axis_key, dss_doc)
            mapping.inputLocation[axis_name] = value

        # Convert output assignments
        # Output typically uses hidden axis names (which are their tags)
        mapping.outputLocation = {}
        for axis_key, value in dss_mapping.output.items():
            # For output, we also need to resolve the axis name
            axis_name = self._resolve_axis_name(axis_key, dss_doc)
            mapping.outputLocation[axis_name] = value

        return mapping

    def _resolve_axis_name(self, axis_key: str, dss_doc: DSSDocument) -> str:
        """Resolve axis key (name or tag) to the axis name used in DesignSpace

        Searches both regular and hidden axes.

        Args:
            axis_key: Axis name or tag from DSS (e.g., "opsz", "wght", "XOUC")
            dss_doc: DSS document with axis definitions

        Returns:
            Resolved axis name for DesignSpace
        """
        # Search in regular axes
        for axis in dss_doc.axes:
            if axis.name == axis_key or axis.tag == axis_key:
                return axis.name

        # Search in hidden axes
        for axis in dss_doc.hidden_axes:
            if axis.name == axis_key or axis.tag == axis_key:
                return axis.name

        # If not found, return the key as-is (might be a custom axis)
        DSSketchLogger.warning(
            f"avar2: axis '{axis_key}' not found in axes definitions, using as-is"
        )
        return axis_key

    def _convert_source(
        self, dss_source: DSSSource, dss_doc: DSSDocument, source_index: int
    ) -> SourceDescriptor:
        """Convert DSS source to DesignSpace source"""
        source = SourceDescriptor()

        # If path is specified in DSS document, prepend it to filename
        if dss_doc.path:
            # Ensure path uses forward slashes for consistency
            path = dss_doc.path.replace("\\", "/")
            if not path.endswith("/"):
                path += "/"
            source.filename = path + dss_source.filename
        else:
            source.filename = dss_source.filename

        # Assign automatic name
        source.name = f"source.{source_index}"

        # Always use familyName from DSS document (prioritize DSS over UFO)
        source.familyName = dss_doc.family

        # Try to read styleName from UFO file, fall back to DSS source name
        ufo_info = self._read_ufo_info(source.filename)
        if ufo_info and ufo_info.get("styleName"):
            source.styleName = ufo_info.get("styleName")
        else:
            source.styleName = dss_source.name

        source.location = dss_source.location.copy()

        # Set copy flags
        if dss_source.is_base:
            source.copyLib = True
            source.copyInfo = True
            source.copyGroups = True
            source.copyFeatures = True

        return source

    def _read_ufo_info(self, filename: str) -> Optional[dict]:
        """Read familyName and styleName from UFO file"""
        try:
            # The filename already includes the full relative path from the base_path
            # (e.g., "sources/SuperFont-Black.ufo")
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

        # If no match found, this is an error - rules must reference existing axes
        raise ValueError(
            f"Rule references axis '{dss_axis_name}' which is not defined in the document. "
            f"Available axes: {', '.join([axis.name for axis in doc.axes])}"
        )

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
