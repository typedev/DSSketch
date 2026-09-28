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
from ..core.translations import Translations
from ..core.models import elided_fallback_name
from ..core.models import DSSAxis, DSSDocument, DSSInstance, DSSSource, DSSRule

# Import validation components
from ..core.validation import UFOGlyphExtractor
from ..utils.discrete import DiscreteAxisHandler
from ..core.report import (
    AVAR2_UNKNOWN_AXIS,
    CATEGORY_AXES,
    CATEGORY_DOCUMENT,
    CATEGORY_RULES,
    DOCUMENT_FAMILY_UNKNOWN,
    DOCUMENT_TRANSLATION_MISSING,
    RULE_DROPPED_EMPTY,
    RULE_GLYPH_NOT_IN_DEFAULT,
    RULE_SUBSTITUTIONS_SKIPPED,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    ConversionIssue,
    ConversionReport,
)
from ..utils.logging import DSSketchLogger

# Import utility classes
from ..utils.patterns import PatternMatcher


class DSSToDesignSpace:
    """Convert DSS to DesignSpace format"""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize converter with optional base path for UFO files"""
        self.base_path = base_path
        self.logger = DSSketchLogger()
        #: What the last convert() found; see core/report.py
        self.report = ConversionReport()

    def _report(self, category: int, code: int, severity: int, description: str, **fields) -> None:
        """Record an issue in the report and log it, so the CLI still shows it"""
        self.report.add(ConversionIssue(category=category, code=code, severity=severity,
                                        description=description, **fields))
        log = self.logger.info if severity == SEVERITY_INFO else self.logger.warning
        log(description)

    def _detect_family_name(self, dss_doc: DSSDocument) -> str:
        """Detect family name from UFO if not specified in DSS document.

        Priority:
        1. Explicit family name from DSS document
        2. familyName from base source UFO
        3. Fallback to "Unknown"
        """
        # If family is explicitly specified, use it
        if dss_doc.family and dss_doc.family.strip():
            return dss_doc.family

        # Try to find base source
        base_source = None
        for source in dss_doc.sources:
            if source.is_base:
                base_source = source
                break

        if not base_source:
            return self._family_unknown("no family line and no @base source to read it from")

        # Construct UFO path
        ufo_filename = base_source.filename
        if dss_doc.path:
            ufo_path = Path(dss_doc.path) / ufo_filename
        else:
            ufo_path = Path(ufo_filename)

        # Make path absolute if base_path is set
        if self.base_path and not ufo_path.is_absolute():
            ufo_path = self.base_path / ufo_path

        # Try to read familyName from UFO
        try:
            if not ufo_path.exists() or not ufo_path.is_dir():
                return self._family_unknown(f"no family line, and the base UFO '{ufo_path}' was not found")

            from defcon import Font

            font = Font(str(ufo_path))
            family_name = font.info.familyName

            if family_name:
                self.logger.info(f"Detected family name '{family_name}' from {ufo_path.name}")
                return family_name
            else:
                return self._family_unknown(f"no family line, and '{ufo_path.name}' has no familyName")
        except Exception as e:
            return self._family_unknown(f"no family line, and '{ufo_path}' could not be read: {e}")

    def _family_unknown(self, reason: str) -> str:
        self._report(
            CATEGORY_DOCUMENT, DOCUMENT_FAMILY_UNKNOWN, SEVERITY_WARNING,
            f"Family name unknown ({reason}); using 'Unknown'",
            suggested_fix="Add a `family` line to the sketch.",
        )
        return "Unknown"

    def convert(self, dss_doc: DSSDocument) -> DesignSpaceDocument:
        """Convert DSS document to DesignSpace document"""
        self.report = ConversionReport()
        doc = DesignSpaceDocument()

        # Detect family name if not specified
        dss_doc.family = self._detect_family_name(dss_doc)

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

        # Convert instances (skip if instances_off is set)
        if not dss_doc.instances_off:
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

        # Always named: without it the STAT-derived name of the all-elided
        # location is empty, and fontmake gives that VF instance an empty name
        doc.elidedFallbackName = elided_fallback_name(dss_doc)

        if dss_doc.languages:
            self._apply_languages(doc, dss_doc)

        return doc

    def _apply_languages(self, doc: DesignSpaceDocument, dss_doc: DSSDocument) -> None:
        """`lang`: write every derived name in the listed languages too.

        Visible axis names and their STAT labels get `labelNames`, and every
        instance a localized style name built from the same labels, word by
        word. Hidden (parametric) axes are left alone. Words without a
        translation stay in English and are reported per language.
        """
        known = set(Translations.languages())
        hidden = {a.name for a in dss_doc.hidden_axes} | {
            a.display_name for a in dss_doc.hidden_axes if a.display_name
        }
        for language in dss_doc.languages:
            missing = set()
            if language not in known:
                self._report(
                    CATEGORY_DOCUMENT, DOCUMENT_TRANSLATION_MISSING, SEVERITY_WARNING,
                    f"lang {language}: the dictionary has no words in this language; "
                    f"names stay in English",
                    suggested_fix=(
                        "Add the language to font-resources-translations.json "
                        "(dssketch-data copy font-resources-translations.json). "
                        f"Available: {', '.join(sorted(known))}"
                    ),
                    raw_data={"language": language, "words": []},
                )
                continue
            for axis in doc.axes:
                if axis.name in hidden or getattr(axis, "hidden", False):
                    continue
                english = axis.labelNames.get("en", axis.name)
                translated = Translations.axis_name(axis.tag, english, language)
                if translated:
                    axis.labelNames[language] = translated
                else:
                    missing.add(english)
                for label in axis.axisLabels or []:
                    word = Translations.label(label.name, language)
                    if word:
                        label.labelNames[language] = word
                    else:
                        missing.add(label.name)
            for instance in doc.instances:
                if not instance.styleName:
                    continue
                name, words = Translations.style_name(instance.styleName, language)
                instance.localisedStyleName[language] = name
                missing.update(words)
            if missing:
                self._report(
                    CATEGORY_DOCUMENT, DOCUMENT_TRANSLATION_MISSING, SEVERITY_WARNING,
                    f"lang {language}: no translation for {', '.join(sorted(missing))}; "
                    f"kept in English",
                    suggested_fix=(
                        "Add the words to font-resources-translations.json "
                        "(dssketch-data copy font-resources-translations.json)."
                    ),
                    raw_data={"language": language, "words": sorted(missing)},
                )

    def _convert_axis(self, dss_axis: DSSAxis):
        """Convert DSS axis to DesignSpace axis (returns AxisDescriptor or DiscreteAxisDescriptor)"""
        if dss_axis.is_discrete:
            # Create DiscreteAxisDescriptor for discrete axes
            axis = DiscreteAxisDescriptor()
            # Use display_name if available, otherwise fall back to name
            axis.name = dss_axis.display_name if dss_axis.display_name else dss_axis.name
            axis.tag = dss_axis.tag
            # For labelNames, use display_name if available
            if dss_axis.display_name:
                axis.labelNames = {"en": dss_axis.display_name}
            elif dss_axis.tag.isupper():
                axis.labelNames = {"en": dss_axis.name}
            else:
                axis.labelNames = {"en": dss_axis.name.title()}
            axis.values = list(dss_axis.values or [dss_axis.minimum, dss_axis.maximum])
            axis.default = dss_axis.default

            # Add discrete labels
            axis.axisLabels = []

            if not dss_axis.mappings:
                # No labels written ("ital discrete"): the standard ones for this tag,
                # if it has any. A custom tag gets none rather than invented names
                standard = DiscreteAxisHandler.load_discrete_labels().get(dss_axis.tag, {})
                for value in axis.values:
                    names = standard.get(int(value))
                    if names:
                        axis.axisLabels.append(
                            AxisLabelDescriptor(
                                name=names[0], userValue=value, elidable=value == axis.default
                            )
                        )
            else:
                # Use custom mappings for discrete axis labels. An unnamed point
                # ("2 > 2") only declares a value; it names nothing
                for mapping in dss_axis.mappings:
                    if not mapping.label:
                        continue
                    label_desc = AxisLabelDescriptor(
                        name=mapping.label,
                        userValue=mapping.user_value,
                        elidable=mapping.elidable,
                    )
                    axis.axisLabels.append(label_desc)
                if any(m.user_value != m.design_value for m in dss_axis.mappings):
                    axis.map = [(m.user_value, m.design_value) for m in dss_axis.mappings]
        else:
            # Create regular AxisDescriptor for continuous axes
            axis = AxisDescriptor()
            # Use display_name if available, otherwise fall back to name
            axis.name = dss_axis.display_name if dss_axis.display_name else dss_axis.name
            axis.tag = dss_axis.tag
            # For labelNames, use display_name if available
            if dss_axis.display_name:
                axis.labelNames = {"en": dss_axis.display_name}
            elif dss_axis.tag.isupper():
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
        # Use display_name if available, otherwise fall back to name
        axis.name = dss_axis.display_name if dss_axis.display_name else dss_axis.name
        axis.tag = dss_axis.tag
        axis.minimum = dss_axis.minimum
        axis.default = dss_axis.default
        axis.maximum = dss_axis.maximum
        axis.hidden = True  # Mark as hidden for avar2

        # Hidden axes typically don't have label names or mappings
        # but we set a basic labelNames for consistency
        if dss_axis.display_name:
            axis.labelNames = {"en": dss_axis.display_name}
        else:
            axis.labelNames = {"en": dss_axis.name}

        return axis

    def _convert_avar2_mapping(self, dss_mapping, dss_doc: DSSDocument) -> AxisMappingDescriptor:
        """Convert DSS avar2 mapping to DesignSpace AxisMappingDescriptor

        DSS format (input in USER space, output in DESIGN space):
            [opsz=Display, wght=Bold] > XOUC=84, YTUC=$YTUC

        DesignSpace XML format (everything in DESIGN space):
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

        The parser stores input values in USER space (labels resolve to user values).
        This method converts them to DESIGN space for DesignSpace XML.
        """
        mapping = AxisMappingDescriptor()

        # Set description from mapping name
        if dss_mapping.name:
            mapping.description = dss_mapping.name

        # Convert input conditions
        # Input is in USER space (from parser), convert to DESIGN space for DesignSpace XML
        mapping.inputLocation = {}
        for axis_key, user_value in dss_mapping.input.items():
            # Find the axis name in DesignSpace (handles tag -> name conversion)
            axis_name = self._resolve_axis_name(axis_key, dss_doc)
            # Convert user space → design space
            design_value = self._user_to_design_value(axis_key, user_value, dss_doc)
            mapping.inputLocation[axis_name] = design_value

        # Convert output assignments
        # Output is already in DESIGN space (no conversion needed)
        mapping.outputLocation = {}
        for axis_key, value in dss_mapping.output.items():
            # For output, we also need to resolve the axis name
            axis_name = self._resolve_axis_name(axis_key, dss_doc)
            mapping.outputLocation[axis_name] = value

        return mapping

    def _user_to_design_value(self, axis_key: str, user_value: float, dss_doc: DSSDocument) -> float:
        """Convert a user-space value to design space through the axis's mappings.

        avar2 inputs are user space in DSSketch (labels and plain numbers alike)
        and design space in DesignSpace. A number between two mapping points is
        interpolated along the axis curve; it used to pass through unchanged
        unless it hit a labeled point exactly.
        """
        for axis in dss_doc.axes + dss_doc.hidden_axes:
            if axis.name == axis_key or axis.tag == axis_key:
                return axis.get_design_value(user_value)

        # Axis not found - return as-is
        return user_value

    def _resolve_axis_name(self, axis_key: str, dss_doc: DSSDocument) -> str:
        """Resolve axis key (name or tag) to the axis name used in DesignSpace

        Searches both regular and hidden axes.
        Uses display_name if available (for preserving original names like "Optical size").

        Args:
            axis_key: Axis name or tag from DSS (e.g., "opsz", "wght", "XOUC")
            dss_doc: DSS document with axis definitions

        Returns:
            Resolved axis name for DesignSpace (display_name if available, else name)
        """
        # Search in regular axes
        for axis in dss_doc.axes:
            if axis.name == axis_key or axis.tag == axis_key:
                # Use display_name if available, otherwise fall back to name
                return axis.display_name if axis.display_name else axis.name

        # Search in hidden axes
        for axis in dss_doc.hidden_axes:
            if axis.name == axis_key or axis.tag == axis_key:
                # Use display_name if available, otherwise fall back to name
                return axis.display_name if axis.display_name else axis.name

        # Not defined anywhere: written as is, and varLib fails on it
        self._report(
            CATEGORY_AXES, AVAR2_UNKNOWN_AXIS, SEVERITY_ERROR,
            f"avar2 mapping names axis '{axis_key}', which the sketch does not define",
            details="It is written to the DesignSpace as is; fontTools fails on it when building.",
            suggested_fix="Check the spelling, or define the axis (hidden axes go in `axes hidden`).",
            raw_data={"axis": axis_key},
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

        # Assign automatic name (sparse masters get "sparse." prefix for round-trip preservation)
        if dss_source.is_sparse:
            source.name = f"sparse.{source_index}"
        else:
            source.name = f"source.{source_index}"

        # Always use familyName from DSS document (prioritize DSS over UFO)
        source.familyName = dss_doc.family

        # Try to read styleName from UFO file, fall back to DSS source name
        ufo_info = self._read_ufo_info(source.filename)
        if ufo_info and ufo_info.get("styleName"):
            source.styleName = ufo_info.get("styleName")
        else:
            source.styleName = dss_source.name

        # Convert location keys from tags to axis names (fontTools uses axis.name)
        # Build mapping: tag -> axis_name (display_name if available, else name)
        tag_to_name = {}
        for axis in dss_doc.axes + dss_doc.hidden_axes:
            axis_name = axis.display_name if axis.display_name else axis.name
            tag_to_name[axis.tag] = axis_name
            tag_to_name[axis.name] = axis_name  # Also map name to itself

        source.location = {}
        for key, value in dss_source.location.items():
            # Convert tag to axis name if needed
            axis_name = tag_to_name.get(key, key)
            source.location[axis_name] = value

        # Set copy flags
        if dss_source.is_base:
            source.copyLib = True
            source.copyInfo = True
            source.copyGroups = True
            source.copyFeatures = True

        # Set UFO layer name if specified
        if dss_source.layer:
            source.layerName = dss_source.layer

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

            from defcon import Font

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
            # Use existing substitutions, also sorted. An explicit rule is kept as
            # written, but a glyph the default master lacks is reported: varLib
            # would reject the rule at build time
            rule.subs = sorted(dss_rule.substitutions, key=lambda x: x[0])
            default_glyphs = self._default_master_glyphs(doc)
            if default_glyphs:
                missing = sorted(
                    {g for pair in rule.subs for g in pair if g not in default_glyphs}
                )
                if missing:
                    self._report(
                        CATEGORY_RULES, RULE_GLYPH_NOT_IN_DEFAULT, SEVERITY_WARNING,
                        f"Rule '{dss_rule.name}' uses {', '.join(repr(g) for g in missing)}, "
                        f"not in the default master; fontTools will reject this rule when building",
                        raw_data={"rule": dss_rule.name, "glyphs": missing},
                    )

        # Skip empty rules (no valid substitutions)
        if not rule.subs:
            self._report(
                CATEGORY_RULES, RULE_DROPPED_EMPTY, SEVERITY_WARNING,
                f"Rule '{dss_rule.name}' left out: no substitution matched the default master",
                raw_data={"rule": dss_rule.name},
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

    def _default_master_glyphs(self, doc: DesignSpaceDocument) -> set:
        """Glyph names of the default master(s), or an empty set if unreadable.

        The @base sources (copyInfo) are the default masters; with a discrete
        axis there is one per value, each the default of its own font, so their
        glyph sets are combined.
        """
        cache = getattr(self, "_default_glyphs_cache", None)
        if cache is not None and cache[0] is doc:
            return cache[1]
        base_path = (
            Path(self.base_path)
            if self.base_path and not isinstance(self.base_path, Path)
            else self.base_path
        )
        base_sources = [s for s in doc.sources if s.copyInfo]
        glyphs = UFOGlyphExtractor.get_all_glyphs_from_sources(base_sources, base_path)
        self._default_glyphs_cache = (doc, glyphs)
        return glyphs

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
        # Substitutions must exist in the default master: that is the glyph set
        # varLib checks rules against, and a glyph present only in a sparse or
        # other non-default master fails the build. Fall back to every source
        # only when no default master can be read
        all_glyphs = self._default_master_glyphs(doc) or UFOGlyphExtractor.get_all_glyphs_from_sources(
            doc.sources, base_path
        )

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
        skipped = []
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
                skipped.append((glyph, target))

        # By design for patterns like `* > .rvrn`: one note per rule, not per glyph
        if skipped and substitutions:
            shown = ", ".join(f"{a} -> {b}" for a, b in skipped[:5])
            more = f" and {len(skipped) - 5} more" if len(skipped) > 5 else ""
            self._report(
                CATEGORY_RULES, RULE_SUBSTITUTIONS_SKIPPED, SEVERITY_INFO,
                f"Rule '{dss_rule.name}': {len(skipped)} substitutions skipped, target not "
                f"in the default master ({shown}{more})",
                raw_data={"rule": dss_rule.name, "skipped": [list(p) for p in skipped]},
            )

        return substitutions
