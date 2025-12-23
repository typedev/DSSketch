"""
DesignSpace to DSS converter

This module converts DesignSpace documents to DSS format.
"""

import json
from pathlib import Path
from typing import Optional

from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)

from ..core.models import DSSAxis, DSSAxisMapping, DSSDocument, DSSInstance, DSSSource, DSSRule, DSSAvar2Mapping


class DesignSpaceToDSS:
    """Convert DesignSpace to DSS format"""

    def __init__(self):
        self.font_resources = {}
        self.load_external_data()

    def load_external_data(self):
        """Load external font resource translations"""
        data_dir = Path(__file__).parent.parent / "data"

        try:
            with open(data_dir / "font-resources-translations.json") as f:
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
        dss_doc = DSSDocument(family=self._extract_family_name(ds_doc))

        # Determine common path for sources
        sources_path = self._determine_sources_path(ds_doc)
        if sources_path:
            dss_doc.path = sources_path

        # Convert axes - separate regular and hidden axes
        for axis in ds_doc.axes:
            dss_axis = self._convert_axis(axis)
            # Check if this is a hidden axis (avar2)
            if getattr(axis, 'hidden', False):
                dss_doc.hidden_axes.append(dss_axis)
            else:
                dss_doc.axes.append(dss_axis)

        # Convert avar2 mappings
        if hasattr(ds_doc, 'axisMappings') and ds_doc.axisMappings:
            # First, convert all mappings
            for mapping in ds_doc.axisMappings:
                dss_mapping = self._convert_avar2_mapping(mapping, ds_doc)
                dss_doc.avar2_mappings.append(dss_mapping)

            # Then analyze CONVERTED mappings to generate variables for repeated values
            # (uses axis tags, which enables the $AXIS shorthand)
            dss_doc.avar2_vars = self._extract_avar2_variables_from_dss(dss_doc.avar2_mappings)

        # Convert sources
        for source in ds_doc.sources:
            dss_source = self._convert_source(source, ds_doc, sources_path)
            dss_doc.sources.append(dss_source)

        # Convert instances (optional - can be auto-generated)
        for instance in ds_doc.instances:
            dss_instance = self._convert_instance(instance, ds_doc)
            dss_doc.instances.append(dss_instance)

        # Convert rules
        for rule in ds_doc.rules:
            dss_rule = self._convert_rule(rule, ds_doc)
            if dss_rule:
                dss_doc.rules.append(dss_rule)

        return dss_doc

    def _extract_family_name(self, ds_doc: DesignSpaceDocument) -> str:
        """Extract family name from DesignSpace document"""
        if ds_doc.instances:
            return ds_doc.instances[0].familyName or "Unknown"
        elif ds_doc.sources:
            return ds_doc.sources[0].familyName or "Unknown"
        return "Unknown"

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

        dss_axis = DSSAxis(
            name=axis.name, tag=axis.tag, minimum=minimum, default=default, maximum=maximum
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

        # Collect labels and create mappings
        if axis.axisLabels:
            for label in axis.axisLabels:
                user_val = label.userValue
                design_val = mappings_dict.get(user_val, user_val)

                mapping = DSSAxisMapping(
                    user_value=user_val,
                    design_value=design_val,
                    label=label.name,
                    elidable=getattr(label, "elidable", False),
                )
                dss_axis.mappings.append(mapping)
        elif mappings_dict:
            # No labels but has axis map - create mappings from map directly
            # This preserves non-linear axis mappings like opsz
            for user_val, design_val in mappings_dict.items():
                # Only add non-identity mappings (where user != design)
                # or all mappings if there's a non-linear relationship
                mapping = DSSAxisMapping(
                    user_value=user_val,
                    design_value=design_val,
                    label="",  # No label for pure numeric mappings
                    elidable=False,
                )
                dss_axis.mappings.append(mapping)

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

        # Build complete location with default values for missing axes
        # In DesignSpace, missing coordinate means default value
        complete_location = {}
        for axis in ds_doc.axes:
            axis_name = axis.name
            if axis_name in source.location:
                complete_location[axis_name] = source.location[axis_name]
            else:
                # Missing coordinate = default value (standard DesignSpace behavior)
                complete_location[axis_name] = axis.default

        return DSSSource(
            name=name,
            filename=filename or f"{name}.ufo",
            location=complete_location,
            is_base=is_base,
            copy_lib=source.copyLib,
            copy_info=source.copyInfo,
            copy_groups=source.copyGroups,
            copy_features=source.copyFeatures,
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

    def _convert_rule(self, rule: RuleDescriptor, ds_doc: DesignSpaceDocument) -> Optional[DSSRule]:
        """Convert DesignSpace rule to DSS rule"""
        if not rule.subs:
            return None

        substitutions = []
        for sub in rule.subs:
            substitutions.append((sub[0], sub[1]))

        conditions = []
        if hasattr(rule, "conditionSets") and rule.conditionSets:
            for condset in rule.conditionSets:
                for condition in condset:
                    conditions.append(
                        {
                            "axis": condition["name"],
                            "minimum": condition.get("minimum", 0),
                            "maximum": condition.get("maximum", 1000),
                        }
                    )
        elif hasattr(rule, "conditions"):
            for condition in rule.conditions:
                conditions.append(
                    {
                        "axis": condition.name,
                        "minimum": condition.minimum,
                        "maximum": condition.maximum,
                    }
                )

        return DSSRule(name=rule.name or "rule", substitutions=substitutions, conditions=conditions)

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
        input_location = {}
        if hasattr(mapping, 'inputLocation') and mapping.inputLocation:
            for axis_name, value in mapping.inputLocation.items():
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

    def _extract_avar2_variables_from_dss(self, dss_mappings) -> dict:
        """Extract repeated values from CONVERTED DSS avar2 mappings to create variables

        If a value appears 3+ times across all output locations,
        create a variable for it named after the axis TAG.

        Example:
            If wght=600 appears in 4 mappings, create $wght = 600
            This allows using the shorthand wght=$ in output

        Args:
            dss_mappings: List of DSSAvar2Mapping objects (already converted)

        Returns:
            Dict of variable_name (axis tag) -> value (without $ prefix)
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
