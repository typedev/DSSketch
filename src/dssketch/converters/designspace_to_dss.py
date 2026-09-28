"""
DesignSpace to DSS converter

This module converts DesignSpace documents to DSS format.
"""

import json
from pathlib import Path
from typing import List, Optional

from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)

from ..core.models import DSSAxis, DSSAxisMapping, DSSDocument, DSSInstance, DSSSource, DSSRule, DSSAvar2Mapping
from ..core.instances import createInstances
from ..core.translations import Translations
from ..core.report import (
    AXIS_LABEL_DATA_DROPPED,
    AXIS_OUTPUT_ONLY_VISIBLE,
    CATEGORY_AXES,
    CATEGORY_DOCUMENT,
    CATEGORY_INSTANCES,
    CATEGORY_RULES,
    CATEGORY_SOURCES,
    DOCUMENT_ELIDED_FALLBACK_DROPPED,
    DOCUMENT_LIB_DROPPED,
    DOCUMENT_TRANSLATIONS_DIFFER,
    DOCUMENT_LOCATION_LABELS_DROPPED,
    DOCUMENT_VARIABLE_FONTS_DROPPED,
    INSTANCE_EXTRA,
    INSTANCE_FIELDS_DROPPED,
    INSTANCE_RENAMED,
    INSTANCE_UNREACHABLE,
    RULES_PROCESSING_LAST_DROPPED,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_FIELDS_DROPPED,
    ConversionIssue,
    ConversionReport,
    InstanceRef,
)
from ..utils.logging import DSSketchLogger


class DesignSpaceToDSS:
    """Convert DesignSpace to DSS format"""

    def __init__(self, vars_threshold: int = 3):
        """Initialize converter.

        Args:
            vars_threshold: Minimum frequency for auto-generating variables.
                           0 = disabled, 3 = default (values appearing 3+ times)
        """
        self.vars_threshold = vars_threshold
        self.font_resources = {}
        #: Structured diagnostics from the most recent convert() call.
        self.report = ConversionReport()
        self.load_external_data()

    def load_external_data(self):
        """Load external font resource translations"""
        data_dir = Path(__file__).parent.parent / "data"

        try:
            with open(data_dir / "font-resources-translations.json", encoding="utf-8") as f:
                self.font_resources = json.load(f)
        except FileNotFoundError:
            pass

    def convert_file(self, ds_path: str) -> DSSDocument:
        """Convert DesignSpace file to DSS document"""
        doc = DesignSpaceDocument()
        doc.read(ds_path)
        return self.convert(doc)

    def convert(self, ds_doc: DesignSpaceDocument) -> DSSDocument:
        """Convert DesignSpace document to DSS document"""
        self.report = ConversionReport()
        dss_doc = DSSDocument(family=self._extract_family_name(ds_doc))

        # Determine common path for sources
        sources_path = self._determine_sources_path(ds_doc)
        if sources_path:
            dss_doc.path = sources_path

        # Hidden is what the DesignSpace declares (hidden="1"), nothing else.
        # Whether to expose an axis is the designer's decision; avar2 topology is
        # evidence about it, reported below, never a reason to rewrite it
        hidden_axis_names = self._determine_hidden_axes(ds_doc)
        self._report_output_only_visible_axes(ds_doc, hidden_axis_names)

        # Convert axes - separate regular and hidden axes
        for axis in ds_doc.axes:
            dss_axis = self._convert_axis(axis)
            # Check if this axis should be hidden
            if axis.name in hidden_axis_names:
                dss_doc.hidden_axes.append(dss_axis)
            else:
                dss_doc.axes.append(dss_axis)

        # Convert avar2 mappings
        if hasattr(ds_doc, 'axisMappings') and ds_doc.axisMappings:
            # First, convert all mappings
            for mapping in ds_doc.axisMappings:
                dss_mapping = self._convert_avar2_mapping(mapping, ds_doc)
                dss_doc.avar2_mappings.append(dss_mapping)

            # Generate variables for repeated values (named $axis1 to avoid confusion with axis.default)
            if self.vars_threshold > 0:
                dss_doc.avar2_vars, dss_doc.avar2_vars_counts = self._extract_avar2_variables_from_dss(
                    dss_doc.avar2_mappings, self.vars_threshold
                )

        # Convert sources
        for source in ds_doc.sources:
            dss_source = self._convert_source(source, ds_doc, sources_path)
            dss_doc.sources.append(dss_source)

        # Convert instances (optional - can be auto-generated)
        if ds_doc.instances:
            for instance in ds_doc.instances:
                dss_instance = self._convert_instance(instance, ds_doc)
                dss_doc.instances.append(dss_instance)
            self._report_instances_auto_fit(ds_doc, dss_doc)
        else:
            # No instances in original - set instances_off to preserve this
            dss_doc.instances_off = True

        # Convert rules
        for rule in ds_doc.rules:
            dss_doc.rules.extend(self._convert_rule(rule, ds_doc))

        try:
            self._detect_languages(ds_doc, dss_doc)
        except Exception as e:  # a diagnostic must never break a conversion
            DSSketchLogger.warning(f"Could not compare localized names: {e}")

        try:
            self._report_dropped_data(ds_doc, dss_doc)
        except Exception as e:  # a diagnostic must never break a conversion
            DSSketchLogger.warning(f"Could not report dropped data: {e}")

        return dss_doc

    # ============================================================
    # DIAGNOSTICS: what the sketch does not carry
    # ============================================================

    def _detect_languages(self, ds_doc: DesignSpaceDocument, dss_doc: DSSDocument) -> None:
        """Write `lang` when the document's localized names are exactly the ones
        `lang` would generate from the dictionary.

        This carries data, it does not guess intent: a sketch with `lang` builds
        the very same names. Any difference - a hand-made translation, a language
        on some instances only - leaves `lang` out and is reported, so nothing
        is silently replaced by dictionary words.
        """
        languages = set()
        for instance in ds_doc.instances:
            languages |= set(instance.localisedStyleName)
        for axis in ds_doc.axes:
            if getattr(axis, "hidden", False):
                continue
            languages |= set(axis.labelNames or {})
            for label in axis.axisLabels or []:
                languages |= set(label.labelNames or {})
        languages.discard("en")
        if not languages:
            return

        differences = []
        for language in sorted(languages):
            for instance in ds_doc.instances:
                if not instance.styleName:
                    continue
                expected, _ = Translations.style_name(instance.styleName, language)
                actual = instance.localisedStyleName.get(language)
                if actual != expected:
                    differences.append(f"{language} '{instance.styleName}': {actual!r}, dictionary {expected!r}")
            for axis in ds_doc.axes:
                if getattr(axis, "hidden", False):
                    continue
                english = (axis.labelNames or {}).get("en", axis.name)
                expected = Translations.axis_name(axis.tag, english, language)
                actual = (axis.labelNames or {}).get(language)
                if actual != expected:
                    differences.append(f"{language} axis {axis.tag}: {actual!r}, dictionary {expected!r}")
                for label in axis.axisLabels or []:
                    expected = Translations.label(label.name, language)
                    actual = (label.labelNames or {}).get(language)
                    if actual != expected:
                        differences.append(f"{language} label {label.name}: {actual!r}, dictionary {expected!r}")

        if not differences:
            dss_doc.languages = sorted(languages)
            return
        self.report.add(ConversionIssue(
            category=CATEGORY_DOCUMENT, code=DOCUMENT_TRANSLATIONS_DIFFER, severity=SEVERITY_WARNING,
            description=(
                f"Localized names in {', '.join(sorted(languages))} are not the dictionary's; "
                f"not carried ({len(differences)} differences)"
            ),
            details="; ".join(differences[:20]) + (" ..." if len(differences) > 20 else ""),
            suggested_fix=(
                "If the dictionary's words are acceptable, add `lang "
                f"{', '.join(sorted(languages))}` to the sketch; to keep these names, "
                "put them in font-resources-translations.json."
            ),
            raw_data={"languages": sorted(languages), "differences": differences},
        ))

    def _report_dropped_data(self, ds_doc: DesignSpaceDocument, dss_doc: DSSDocument) -> None:
        """Report DesignSpace data the sketch does not express.

        DSSketch is deliberately higher-level than DesignSpace, so some data has
        no place in a sketch. Dropping it is by design; dropping it silently is
        not. Each kind of loss is one issue, listing what it affects. Nothing
        here changes the sketch.
        """
        report = self.report

        # -- document ------------------------------------------------------
        if ds_doc.lib:
            report.add(ConversionIssue(
                category=CATEGORY_DOCUMENT, code=DOCUMENT_LIB_DROPPED, severity=SEVERITY_WARNING,
                description=f"Document <lib> dropped ({len(ds_doc.lib)} keys: {', '.join(sorted(ds_doc.lib))})",
                details="Tools store project settings here (paths, plugin data, varLib options).",
                raw_data={"keys": sorted(ds_doc.lib)},
            ))
        if ds_doc.elidedFallbackName:
            report.add(ConversionIssue(
                category=CATEGORY_DOCUMENT, code=DOCUMENT_ELIDED_FALLBACK_DROPPED, severity=SEVERITY_INFO,
                description=f"elidedFallbackName '{ds_doc.elidedFallbackName}' dropped",
                raw_data={"elidedFallbackName": ds_doc.elidedFallbackName},
            ))
        if ds_doc.locationLabels:
            names = [label.name for label in ds_doc.locationLabels]
            report.add(ConversionIssue(
                category=CATEGORY_DOCUMENT, code=DOCUMENT_LOCATION_LABELS_DROPPED, severity=SEVERITY_WARNING,
                description=f"{len(names)} location labels dropped: {', '.join(names)}",
                details="Document-level location labels become STAT format 4 entries.",
                raw_data={"labels": names},
            ))
        if ds_doc.variableFonts:
            names = [vf.name for vf in ds_doc.variableFonts]
            report.add(ConversionIssue(
                category=CATEGORY_DOCUMENT, code=DOCUMENT_VARIABLE_FONTS_DROPPED, severity=SEVERITY_WARNING,
                description=f"{len(names)} <variable-font> definitions dropped: {', '.join(names)}",
                details="Without them a build produces the default set of variable fonts.",
                raw_data={"variable_fonts": names},
            ))

        # -- rules ---------------------------------------------------------
        if ds_doc.rulesProcessingLast and ds_doc.rules:
            report.add(ConversionIssue(
                category=CATEGORY_RULES, code=RULES_PROCESSING_LAST_DROPPED, severity=SEVERITY_WARNING,
                description='rules processing="last" dropped',
                details=(
                    "The DesignSpace applies its substitutions after other features "
                    "(rclt); a build from the sketch applies them first (rvrn)."
                ),
            ))

        # -- axes: STAT label data -----------------------------------------
        label_losses = []
        for axis in ds_doc.axes:
            covered = set(dss_doc.languages) | {"en"}
            other_langs = sorted(k for k in (axis.labelNames or {}) if k not in covered)
            if other_langs:
                label_losses.append(f"{axis.tag}: axis name in {', '.join(other_langs)}")
            for label in axis.axisLabels or []:
                dropped = []
                if label.userMinimum is not None or label.userMaximum is not None:
                    dropped.append("range")
                if label.linkedUserValue is not None:
                    dropped.append("linked value")
                if label.olderSibling:
                    dropped.append("older sibling")
                if set(label.labelNames or {}) - covered:
                    dropped.append("localized names")
                if dropped:
                    label_losses.append(f"{axis.tag} {label.name}: {', '.join(dropped)}")
        if label_losses:
            report.add(ConversionIssue(
                category=CATEGORY_AXES, code=AXIS_LABEL_DATA_DROPPED, severity=SEVERITY_INFO,
                description=f"STAT label data dropped for {len(label_losses)} items",
                details="; ".join(label_losses),
                raw_data={"items": label_losses},
            ))

        # -- sources -------------------------------------------------------
        source_losses = []
        for source in ds_doc.sources:
            dropped = []
            if source.familyName and source.familyName != dss_doc.family:
                dropped.append(f"family name '{source.familyName}'")
            if source.localisedFamilyName:
                dropped.append("localized family names")
            if source.muteInfo:
                dropped.append("muted info")
            if source.muteKerning:
                dropped.append("muted kerning")
            if source.mutedGlyphNames:
                dropped.append(f"{len(source.mutedGlyphNames)} muted glyphs")
            if dropped:
                label = source.filename or source.name or "?"
                source_losses.append(f"{label}: {', '.join(dropped)}")
        if source_losses:
            report.add(ConversionIssue(
                category=CATEGORY_SOURCES, code=SOURCE_FIELDS_DROPPED, severity=SEVERITY_WARNING,
                description=f"Per-source data dropped for {len(source_losses)} sources",
                details="; ".join(source_losses),
                raw_data={"sources": source_losses},
            ))

        # -- instances -----------------------------------------------------
        fields = {
            "styleMapFamilyName": "style-map family name",
            "styleMapStyleName": "style-map style name",
            "localisedFamilyName": "localized family names",
            "localisedStyleName": "localized style names",
            "localisedStyleMapFamilyName": "localized style-map family names",
            "localisedStyleMapStyleName": "localized style-map style names",
            "lib": "instance lib",
            "glyphs": "glyph instances",
            "locationLabel": "location label",
        }
        counts = {}
        refs = []
        for instance in ds_doc.instances:
            present = [f for f in fields if getattr(instance, f, None)]
            # `lang` regenerates localized style names exactly (checked before)
            if "localisedStyleName" in present and not (
                set(instance.localisedStyleName) - set(dss_doc.languages) - {"en"}
            ):
                present.remove("localisedStyleName")
            # instances auto writes Family-Style; only a different name is lost
            generated = (
                f"{(instance.familyName or dss_doc.family or '').replace(' ', '')}-"
                f"{(instance.styleName or '').replace(' ', '')}"
            )
            if instance.postScriptFontName and instance.postScriptFontName != generated:
                present.append("postScriptFontName")
            for f in present:
                counts[f] = counts.get(f, 0) + 1
            if present:
                refs.append(InstanceRef(style_name=instance.styleName or instance.name or "?",
                                        location=dict(instance.getFullDesignLocation(ds_doc))))
        if counts:
            fields["postScriptFontName"] = "PostScript name"
            summary = ", ".join(f"{fields[f]} ({n})" for f, n in sorted(counts.items()))
            report.add(ConversionIssue(
                category=CATEGORY_INSTANCES, code=INSTANCE_FIELDS_DROPPED, severity=SEVERITY_INFO,
                description=f"Per-instance data dropped for {len(refs)} instances: {summary}",
                details=(
                    "instances auto generates instances from the labeled axis "
                    "mappings; hand-set instance data has no place in a sketch."
                ),
                instances=refs,
                raw_data={"fields": dict(counts)},
            ))

    def _extract_family_name(self, ds_doc: DesignSpaceDocument) -> str:
        """Family name of the default source, else the sources' most common one.

        The default source is found with designspaceLib's findDefault(), which
        maps the axis defaults to design space. Comparing source locations with
        the user-space defaults, as this used to, misses the default master on
        any axis whose default is mapped (RobotoDelta: opsz 14 -> 0), and the
        sketch was then named "Unknown".
        """
        default_source = None
        for source in ds_doc.sources:
            if source.copyLib:
                default_source = source
                break
        if default_source is None:
            try:
                default_source = ds_doc.findDefault()
            except Exception:
                default_source = None
        if default_source is not None and default_source.familyName:
            return default_source.familyName

        names = [s.familyName for s in ds_doc.sources if s.familyName]
        names += [i.familyName for i in ds_doc.instances if i.familyName]
        if names:
            return max(set(names), key=names.count)

        # None known: leave it empty, so the sketch has no `family` line and
        # DSS -> DS reads the name from the base UFO
        return ""

    def _determine_sources_path(self, ds_doc: DesignSpaceDocument) -> Optional[str]:
        """Determine common path for all sources"""
        if not ds_doc.sources:
            return None

        # Collect all source paths
        source_paths = []
        for source in ds_doc.sources:
            if source.filename:
                source_paths.append(Path(source.filename))

        if not source_paths:
            return None

        # Find common directory
        directories = set()
        for path in source_paths:
            if path.parent != Path("."):
                directories.add(path.parent)

        # If all sources are in root directory (no parent path)
        if not directories:
            return None

        # If all sources are in the same directory
        if len(directories) == 1:
            common_dir = directories.pop()
            return str(common_dir).replace("\\", "/")

        # Sources are in different directories - return None
        return None

    def _convert_axis(self, axis: AxisDescriptor) -> DSSAxis:
        """Convert DesignSpace axis to DSS axis"""
        # Handle discrete axes (like italic)
        if hasattr(axis, "values") and axis.values:
            values = list(axis.values)
            minimum = min(values)
            maximum = max(values)
            default = getattr(axis, "default", minimum)
        else:
            minimum = getattr(axis, "minimum", 0)
            maximum = getattr(axis, "maximum", 1000)
            default = getattr(axis, "default", minimum)

        # Store original axis.name as display_name for UI preservation
        # Use tag as the internal name (will be normalized later)
        display_name = axis.name if axis.name != axis.tag else None

        dss_axis = DSSAxis(
            name=axis.name, tag=axis.tag, minimum=minimum, default=default, maximum=maximum,
            display_name=display_name
        )

        # Process mappings and labels
        mappings_dict = {}

        # Collect mappings
        if axis.map:
            for mapping in axis.map:
                if hasattr(mapping, "inputLocation"):
                    user_val = mapping.inputLocation
                    design_val = mapping.outputLocation
                else:
                    user_val, design_val = mapping
                mappings_dict[user_val] = design_val

        # Collect labels, keyed by user value
        labels_dict = {}
        if axis.axisLabels:
            for label in axis.axisLabels:
                labels_dict[label.userValue] = label

        # The avar map and the STAT labels are two independent lists and need not
        # cover the same user values. A map point may carry no label (an axis that
        # extends past its named styles), and a label may sit on a user value that
        # has no explicit map entry (then user == design). Take the union of both
        # so neither list is lost.
        for user_val in sorted(set(mappings_dict) | set(labels_dict)):
            label = labels_dict.get(user_val)
            mapping = DSSAxisMapping(
                user_value=user_val,
                design_value=mappings_dict.get(user_val, user_val),
                label=label.name if label else "",
                elidable=getattr(label, "elidable", False) if label else False,
            )
            dss_axis.mappings.append(mapping)

        if hasattr(axis, "values") and axis.values:
            # A discrete axis: every value must survive, including one that has
            # neither a label nor a map entry. It becomes an unnamed point
            present = {m.user_value for m in dss_axis.mappings}
            for value in axis.values:
                if value not in present:
                    dss_axis.mappings.append(
                        DSSAxisMapping(user_value=value, design_value=value, label="")
                    )
            dss_axis.values = sorted(axis.values)

        # Sort mappings by user value
        dss_axis.mappings.sort(key=lambda m: m.user_value)

        return dss_axis

    def _convert_source(
        self,
        source: SourceDescriptor,
        ds_doc: DesignSpaceDocument,
        sources_path: Optional[str] = None,
    ) -> DSSSource:
        """Convert DesignSpace source to DSS source"""
        filename = source.filename or ""
        name = Path(filename).stem

        # If we have a common sources path, strip it from the filename
        if sources_path and filename.startswith(sources_path):
            filename = filename[len(sources_path) :].lstrip("/")

        # Determine if this is a base source by checking if coordinates match defaults
        # Base source has coordinates matching default values in design space
        is_base = self._is_default_source(source, ds_doc)

        # Detect sparse master: either by name="sparse.*" prefix (DesignSpace convention)
        # or by filename "-sparse.ufo" suffix (filename convention)
        name_attr = (source.name or "").lower()
        fname_lower = (source.filename or "").lower()
        is_sparse = name_attr.startswith("sparse.") or fname_lower.endswith("-sparse.ufo")

        # Build complete location with ALL coordinates from source
        # Include both visible and hidden axis coordinates
        # In DesignSpace, missing coordinate means default value
        complete_location = {}

        # First, add defaults for all axes (visible and hidden)
        for axis in ds_doc.axes:
            complete_location[axis.name] = axis.default

        # Then, override with actual source coordinates
        # This preserves ALL coordinates including hidden axes
        for axis_name, value in source.location.items():
            complete_location[axis_name] = value

        return DSSSource(
            name=name,
            filename=filename or f"{name}.ufo",
            location=complete_location,
            is_base=is_base,
            is_sparse=is_sparse,
            copy_lib=source.copyLib,
            copy_info=source.copyInfo,
            copy_groups=source.copyGroups,
            copy_features=source.copyFeatures,
            layer=source.layerName,  # UFO layer name (None = default layer)
        )

    def _is_default_source(self, source: SourceDescriptor, ds_doc: DesignSpaceDocument) -> bool:
        """Check if a source is at the default location for all continuous axes.
        For discrete axes, any value is acceptable - we need base sources for each discrete value."""

        for axis in ds_doc.axes:
            axis_name = axis.name

            # Get source's coordinate in design space
            # Missing coordinate means default value (standard DesignSpace behavior)
            source_coord = source.location.get(axis_name)
            if source_coord is None:
                source_coord = axis.default

            # Skip discrete axes - they can have any value
            # We need base sources for each discrete value (e.g., both Roman and Italic)
            if hasattr(axis, "values") and axis.values:
                # Just check that the value is valid
                if source_coord not in axis.values:
                    return False
                continue

            # For continuous axes, check if at default position
            default_user = axis.default

            # Convert user space default to design space
            default_design = default_user  # Default: no mapping

            # Check if axis has mappings
            if hasattr(axis, "map") and axis.map:
                # Find the mapping for default user value
                for mapping in axis.map:
                    if hasattr(mapping, "inputLocation"):
                        user_val = mapping.inputLocation
                        design_val = mapping.outputLocation
                    else:
                        user_val, design_val = mapping

                    if user_val == default_user:
                        default_design = design_val
                        break

            # For continuous axes, compare with small tolerance for floating point
            if abs(source_coord - default_design) > 0.001:
                return False

        return True

    def _convert_instance(
        self, instance: InstanceDescriptor, ds_doc: DesignSpaceDocument
    ) -> DSSInstance:
        """Convert DesignSpace instance to DSS instance"""
        return DSSInstance(
            name=instance.styleName or "",
            familyname=instance.familyName or "",
            stylename=instance.styleName or "",
            filename=instance.filename,
            location=dict(instance.location),
        )

    def _convert_rule(self, rule: RuleDescriptor, ds_doc: DesignSpaceDocument) -> List[DSSRule]:
        """Convert a DesignSpace rule to DSS rules, one per conditionset.

        A DesignSpace rule applies when ANY of its conditionsets matches, and the
        conditions inside one conditionset are ANDed. A DSS rule holds a single
        AND-ed condition, so a rule with several conditionsets becomes several
        DSS rules with the same substitutions and name, one per conditionset.
        That keeps the OR: the substitution applies wherever any of them matches.
        Merging the conditions into one rule would turn it into an AND.
        """
        if not rule.subs:
            return []

        substitutions = [(sub[0], sub[1]) for sub in rule.subs]

        condition_sets = []
        if getattr(rule, "conditionSets", None):
            for condset in rule.conditionSets:
                condition_sets.append(
                    [
                        {
                            "axis": condition["name"],
                            "minimum": condition.get("minimum"),
                            "maximum": condition.get("maximum"),
                        }
                        for condition in condset
                    ]
                )
        elif getattr(rule, "conditions", None):
            condition_sets.append(
                [
                    {
                        "axis": condition.name,
                        "minimum": condition.minimum,
                        "maximum": condition.maximum,
                    }
                    for condition in rule.conditions
                ]
            )
        if not condition_sets:
            condition_sets = [[]]

        return [
            DSSRule(name=rule.name or "rule", substitutions=list(substitutions), conditions=conditions)
            for conditions in condition_sets
        ]

    # ============================================================
    # avar2 CONVERSION METHODS
    # ============================================================

    def _convert_avar2_mapping(self, mapping, ds_doc: DesignSpaceDocument) -> DSSAvar2Mapping:
        """Convert DesignSpace AxisMappingDescriptor to DSS avar2 mapping

        DesignSpace format:
            <mapping description="name">
                <input><dimension name="Optical size" xvalue="144"/></input>
                <output><dimension name="XOUC" xvalue="84"/></output>
            </mapping>

        DSS format:
            "name" [opsz=144] > XOUC=84
        """
        # Get mapping name/description
        name = getattr(mapping, 'description', None)

        # Convert input location (axis name -> value)
        # DesignSpace stores inputs in design space; DSSketch holds them in user
        # space (what a label means, and what DSS -> DS maps forward again)
        input_location = {}
        if hasattr(mapping, 'inputLocation') and mapping.inputLocation:
            axes_by_name = {axis.name: axis for axis in ds_doc.axes}
            for axis_name, value in mapping.inputLocation.items():
                axis = axes_by_name.get(axis_name)
                if axis is not None and getattr(axis, "map", None):
                    value = axis.map_backward(value)
                # Convert to axis tag if possible for shorter output
                axis_tag = self._get_axis_tag(axis_name, ds_doc)
                input_location[axis_tag] = value

        # Convert output location (axis name -> value)
        output_location = {}
        if hasattr(mapping, 'outputLocation') and mapping.outputLocation:
            for axis_name, value in mapping.outputLocation.items():
                # Convert to axis tag if possible
                axis_tag = self._get_axis_tag(axis_name, ds_doc)
                output_location[axis_tag] = value

        return DSSAvar2Mapping(
            name=name,
            input=input_location,
            output=output_location
        )

    def _get_axis_tag(self, axis_name: str, ds_doc: DesignSpaceDocument) -> str:
        """Get axis tag from axis name

        Returns the axis tag if found, otherwise returns the original name.
        """
        for axis in ds_doc.axes:
            if axis.name == axis_name:
                return axis.tag
        return axis_name

    def _collect_avar2_input_axes(self, ds_doc: DesignSpaceDocument) -> set:
        """Collect all axis names/tags that appear in avar2 INPUT locations.

        Axes in input are user-controllable (visible axes).

        Returns:
            Set of axis names that appear in any avar2 input location.
        """
        input_axes = set()

        if not hasattr(ds_doc, 'axisMappings') or not ds_doc.axisMappings:
            return input_axes

        for mapping in ds_doc.axisMappings:
            if hasattr(mapping, 'inputLocation') and mapping.inputLocation:
                for axis_name in mapping.inputLocation.keys():
                    input_axes.add(axis_name)

        return input_axes

    def _collect_avar2_output_axes(self, ds_doc: DesignSpaceDocument) -> set:
        """Collect all axis names/tags that appear in avar2 OUTPUT locations.

        Axes only in output (never in input) are typically hidden parametric axes.

        Returns:
            Set of axis names that appear in any avar2 output location.
        """
        output_axes = set()

        if not hasattr(ds_doc, 'axisMappings') or not ds_doc.axisMappings:
            return output_axes

        for mapping in ds_doc.axisMappings:
            if hasattr(mapping, 'outputLocation') and mapping.outputLocation:
                for axis_name in mapping.outputLocation.keys():
                    output_axes.add(axis_name)

        return output_axes

    def _report_instances_auto_fit(
        self, ds_doc: DesignSpaceDocument, dss_doc: DSSDocument
    ) -> None:
        """Report how well `instances auto` reproduces the declared instances.

        The sketch normally says `instances auto` rather than listing instances,
        on the assumption that the generator rebuilds them from the axis labels.
        This checks that assumption against the DesignSpace we just read and
        reports where it does not hold.

        Instances are matched by **design-space position**, not by style name.
        Names diverge for reasons that are not losses - elidable rules change
        them - whereas a position either survives or it does not. Comparing by
        name produces large numbers of phantom losses.

        Purely diagnostic: it never alters the document. In particular it does
        not synthesise a `skip` block. `skip` is an instruction to the
        generator and a DesignSpace records only the result of applying it, so
        the intent behind an absent instance cannot be recovered from the file.
        Extra instances are reported so a human can write that block.
        """
        try:
            generated, _ = createInstances(ds_doc, dss_doc)
        except Exception as exc:  # diagnostics must never break a conversion
            DSSketchLogger.debug(f"Could not verify `instances auto`: {exc}")
            return

        defaults = {axis.name: axis.default for axis in ds_doc.axes}

        def position(instance) -> tuple:
            # An omitted dimension means the axis default, so drop defaults to
            # make "absent" and "explicitly at default" compare equal.
            return tuple(
                sorted(
                    (name, value)
                    for name, value in instance.location.items()
                    if defaults.get(name) != value
                )
            )

        declared = {position(i): i.styleName for i in ds_doc.instances}
        produced = {position(i): i.styleName for i in generated.instances}

        missing = [declared[p] for p in declared if p not in produced]
        renamed = [
            (declared[p], produced[p])
            for p in declared
            if p in produced and declared[p] != produced[p]
        ]
        extra = [produced[p] for p in produced if p not in declared]

        if missing:
            refs = [
                InstanceRef(style_name=name, location=dict(loc))
                for loc, name in ((p, declared[p]) for p in declared if p not in produced)
            ]
            issue = self.report.add(
                ConversionIssue(
                    category=CATEGORY_INSTANCES,
                    code=INSTANCE_UNREACHABLE,
                    severity=SEVERITY_WARNING,
                    description=(
                        f"`instances auto` does not reach {len(missing)} of the "
                        f"{len(declared)} instances declared in the DesignSpace"
                    ),
                    details=(
                        "The sketch will not describe this design space completely. "
                        "These positions are not produced by any combination of the "
                        "axis labels, so they cannot be regenerated."
                    ),
                    suggested_fix=(
                        "Add axis labels that land on these positions, or keep the "
                        "instances listed explicitly."
                    ),
                    instances=sorted(refs, key=lambda r: r.style_name),
                    raw_data={"declared": len(declared), "unreachable": len(missing)},
                )
            )
            DSSketchLogger.warning(f"{issue.description}: {self._sample(missing)}")

        if renamed:
            refs = [
                InstanceRef(
                    style_name=declared[p],
                    location=dict(p),
                    other_style_name=produced[p],
                )
                for p in declared
                if p in produced and declared[p] != produced[p]
            ]
            issue = self.report.add(
                ConversionIssue(
                    category=CATEGORY_INSTANCES,
                    code=INSTANCE_RENAMED,
                    severity=SEVERITY_WARNING,
                    description=(
                        f"{len(renamed)} instance(s) keep their position but are "
                        f"named differently by the generator"
                    ),
                    details=(
                        "The DesignSpace may predate a change in the elidable naming "
                        "rules. The positions themselves are intact."
                    ),
                    suggested_fix=(
                        "Regenerate the DesignSpace from its sketch so the names agree."
                    ),
                    instances=sorted(refs, key=lambda r: r.style_name),
                    raw_data={"declared": len(declared), "renamed": len(renamed)},
                )
            )
            DSSketchLogger.warning(
                issue.description
                + " - the DesignSpace may predate a change in the elidable rules: "
                + ", ".join(f"'{was}' -> '{now}'" for was, now in renamed[:3])
                + (f" (+{len(renamed) - 3} more)" if len(renamed) > 3 else "")
            )

        if extra:
            refs = [
                InstanceRef(style_name=name, location=dict(loc))
                for loc, name in ((p, produced[p]) for p in produced if p not in declared)
            ]
            issue = self.report.add(
                ConversionIssue(
                    category=CATEGORY_INSTANCES,
                    code=INSTANCE_EXTRA,
                    severity=SEVERITY_INFO,
                    description=(
                        f"`instances auto` generates {len(extra)} instance(s) beyond "
                        f"the {len(declared)} in the DesignSpace"
                    ),
                    details=(
                        "The DesignSpace was filtered. A sketch expresses that with an "
                        "`instances auto` / `skip` block, which cannot be recovered "
                        "from a DesignSpace: `skip` instructs the generator, while a "
                        "DesignSpace records only the result of applying it."
                    ),
                    suggested_fix=(
                        "If the omission is intentional, list these under "
                        "`instances auto` / `skip`."
                    ),
                    instances=sorted(refs, key=lambda r: r.style_name),
                    raw_data={"declared": len(declared), "extra": len(extra)},
                )
            )
            DSSketchLogger.info(
                issue.description
                + ". If that is intentional, add them to an `instances auto` / "
                + f"`skip` block: {self._sample(extra)}"
            )

        if not self.report.of_category(CATEGORY_INSTANCES):
            DSSketchLogger.debug(
                f"`instances auto` reproduces all {len(declared)} declared instances"
            )

    @staticmethod
    def _sample(names: list, limit: int = 5) -> str:
        """Render a few names for a log line, noting how many were left out."""
        shown = ", ".join(f"'{n}'" for n in sorted(names)[:limit])
        remaining = len(names) - limit
        return shown + (f" (+{remaining} more)" if remaining > 0 else "")

    def _determine_hidden_axes(self, ds_doc: DesignSpaceDocument) -> set:
        """Axes the DesignSpace declares hidden (hidden="1").

        This used to also hide every axis that appears only in avar2 outputs.
        That rewrote the designer's decision: RobotoDelta went from 0 to 30 hidden
        axes of 39, and AmstelvarA2-Roman's axes declared visible became hidden.
        See notes/roundtrip-fidelity-issues.md, finding 2.
        """
        return {axis.name for axis in ds_doc.axes if getattr(axis, "hidden", False)}

    def _report_output_only_visible_axes(self, ds_doc: DesignSpaceDocument, hidden: set) -> None:
        """Point out visible axes that only avar2 drives.

        An axis that appears in avar2 outputs but never in inputs is usually a
        parametric axis meant to be hidden. Reported, not changed: the document
        may expose it on purpose.
        """
        input_axes = self._collect_avar2_input_axes(ds_doc)
        output_axes = self._collect_avar2_output_axes(ds_doc)
        candidates = [
            axis
            for axis in ds_doc.axes
            if axis.name not in hidden
            and (axis.name in output_axes or axis.tag in output_axes)
            and not (axis.name in input_axes or axis.tag in input_axes)
        ]
        if not candidates:
            return
        tags = [axis.tag for axis in candidates]
        self.report.add(
            ConversionIssue(
                category=CATEGORY_AXES,
                code=AXIS_OUTPUT_ONLY_VISIBLE,
                severity=SEVERITY_WARNING,
                description=(
                    f"{len(tags)} visible axes are driven only by avar2 outputs: "
                    f"{', '.join(tags)}"
                ),
                details=(
                    "Such axes are usually parametric axes meant to be hidden. The "
                    "DesignSpace does not declare them hidden, so the sketch keeps "
                    "them visible and a font built from it exposes them to users."
                ),
                suggested_fix=(
                    "If they should not be exposed, move them to an `axes hidden` "
                    "section of the sketch (or set hidden=\"1\" in the DesignSpace)."
                ),
                raw_data={"axes": tags},
            )
        )

    def _extract_avar2_variables_from_dss(self, dss_mappings, threshold: int = 3) -> tuple:
        """Extract repeated values from CONVERTED DSS avar2 mappings to create variables

        If a value appears threshold+ times across all output locations,
        create a variable for it named $axis1, $axis2, etc. (counter to avoid confusion with axis.default).

        Example (threshold=3):
            If wght=600 appears 4 times, create $wght1 = 600
            If wght=800 appears 3 times, create $wght2 = 800
            Writer will output $wght1, $wght2 where these values appear

        Args:
            dss_mappings: List of DSSAvar2Mapping objects (already converted)
            threshold: Minimum frequency for creating a variable (default: 3)

        Returns:
            Tuple of (variables, counts):
                - variables: Dict of variable_name (axis_tag + counter) -> value (without $ prefix)
                - counts: Dict of variable_name -> frequency count
        """
        # Count value occurrences per axis
        axis_value_counts = {}  # {axis_tag: {value: count}}

        for mapping in dss_mappings:
            for axis_tag, value in mapping.output.items():
                if axis_tag not in axis_value_counts:
                    axis_value_counts[axis_tag] = {}
                if value not in axis_value_counts[axis_tag]:
                    axis_value_counts[axis_tag][value] = 0
                axis_value_counts[axis_tag][value] += 1

        # Create variables for values that appear threshold+ times
        variables = {}
        counts = {}
        axis_counters = {}  # Track counter per axis

        for axis_tag, value_counts in axis_value_counts.items():
            # Sort by count descending to get most common values first
            sorted_values = sorted(value_counts.items(), key=lambda x: -x[1])

            for value, count in sorted_values:
                if count >= threshold:
                    # Increment counter for this axis
                    if axis_tag not in axis_counters:
                        axis_counters[axis_tag] = 0
                    axis_counters[axis_tag] += 1

                    # Use axis tag + counter as variable name
                    var_name = f"{axis_tag}{axis_counters[axis_tag]}"
                    variables[var_name] = value
                    counts[var_name] = count

        return variables, counts

    def _extract_avar2_variables(self, axis_mappings) -> dict:
        """Extract repeated values from avar2 mappings to create variables

        If a value appears 3+ times across all output locations,
        create a variable for it named after the axis TAG (not name).

        Example:
            If wght=600 appears in 10 mappings, create $wght = 600
            This allows using the shorthand wght=$ in output

        Returns:
            Dict of variable_name (axis tag) -> value (without $ prefix)
        """
        # Count value occurrences per axis (using output keys which are axis tags)
        axis_value_counts = {}  # {axis_tag: {value: count}}

        for mapping in axis_mappings:
            if hasattr(mapping, 'outputLocation') and mapping.outputLocation:
                for axis_tag, value in mapping.outputLocation.items():
                    if axis_tag not in axis_value_counts:
                        axis_value_counts[axis_tag] = {}
                    if value not in axis_value_counts[axis_tag]:
                        axis_value_counts[axis_tag][value] = 0
                    axis_value_counts[axis_tag][value] += 1

        # Create variables for values that appear 3+ times
        variables = {}
        for axis_tag, value_counts in axis_value_counts.items():
            # Find the value with the most occurrences
            max_count = 0
            max_value = None
            for value, count in value_counts.items():
                if count > max_count:
                    max_count = count
                    max_value = value

            if max_count >= 3 and max_value is not None:
                # Use axis tag as variable name (allows $AXIS shorthand)
                variables[axis_tag] = max_value

        return variables
