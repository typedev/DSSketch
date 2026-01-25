"""
DSS Writer for DSSketch

This module handles writing DSSketch documents to DSS string format with optimization features.
"""

from typing import List, Optional, Set, Tuple

# For DesignSpace document type hints
from fontTools.designspaceLib import DesignSpaceDocument

# Import utilities
from ..core.mappings import Standards

# Import models from core
from ..core.models import DSSAxis, DSSDocument, DSSInstance, DSSSource, DSSRule
from ..core.validation import UFOGlyphExtractor
from ..utils.patterns import PatternMatcher


class DSSWriter:
    """Write DSS document to string format"""

    # Registered axis names that can be omitted for brevity
    REGISTERED_AXES = {
        "italic": "ital",
        "optical": "opsz",
        "slant": "slnt",
        "width": "wdth",
        "weight": "wght",
    }

    def __init__(
        self,
        optimize: bool = True,
        ds_doc: Optional[DesignSpaceDocument] = None,
        base_path: Optional[str] = None,
        use_label_coordinates: bool = True,
        use_label_ranges: bool = True,
        avar2_format: str = "matrix",
    ):
        self.optimize = optimize
        self.ds_doc = ds_doc
        self.base_path = base_path
        self.use_label_coordinates = use_label_coordinates
        self.use_label_ranges = use_label_ranges
        self.avar2_format = avar2_format  # "matrix" or "linear"

    @staticmethod
    def _quote_if_spaces(value: str) -> str:
        """Add double quotes around value if it contains spaces

        Examples:
        - "FontName Condensed" -> '"FontName Condensed"'
        - "FontName" -> "FontName"
        - "My Font Light.ufo" -> '"My Font Light.ufo"'
        """
        if " " in value:
            return f'"{value}"'
        return value

    @staticmethod
    def _format_number(value: float) -> str:
        """Format number - remove .0 for integer values

        Examples:
        - 100.0 -> "100"
        - 100.5 -> "100.5"
        - -20.0 -> "-20"
        - -15.5 -> "-15.5"
        """
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def write(self, dss_doc: DSSDocument) -> str:
        """Generate DSS string from document"""
        lines = []

        # Family declaration (with quotes if it contains spaces)
        family_value = self._quote_if_spaces(dss_doc.family)
        lines.append(f"family {family_value}")
        if dss_doc.suffix:
            lines.append(f"suffix {dss_doc.suffix}")
        if dss_doc.path:
            lines.append(f"path {dss_doc.path}")
        lines.append("")

        # Axes section
        if dss_doc.axes:
            lines.append("axes")
            for axis in dss_doc.axes:
                lines.extend(self._format_axis(axis))
            lines.append("")

        # Hidden axes section (avar2)
        if dss_doc.hidden_axes:
            lines.append("axes hidden")
            for axis in dss_doc.hidden_axes:
                lines.extend(self._format_hidden_axis(axis))
            lines.append("")

        # Sources section
        if dss_doc.sources:
            # Determine format: named (if hidden axes) or positional
            use_named_format = bool(dss_doc.hidden_axes)

            if use_named_format:
                # Named format: no axis header needed
                lines.append("sources")
                for source in dss_doc.sources:
                    lines.append(self._format_source_named(source, dss_doc))
            else:
                # Positional format: include axis header
                if dss_doc.axes:
                    # Use axis.tag directly, not axis.name (which may be display name)
                    axis_tags = [axis.tag for axis in dss_doc.axes]
                    lines.append(f"sources [{', '.join(axis_tags)}]")
                else:
                    lines.append("sources")
                for source in dss_doc.sources:
                    lines.append(self._format_source(source, dss_doc.axes))
            lines.append("")

        # avar2 vars section
        if dss_doc.avar2_vars:
            lines.append("avar2 vars")
            for var_name, var_value in dss_doc.avar2_vars.items():
                count = dss_doc.avar2_vars_counts.get(var_name, 0)
                if count > 0:
                    lines.append(f"    ${var_name} = {self._format_number(var_value)}  # used {count} times")
                else:
                    lines.append(f"    ${var_name} = {self._format_number(var_value)}")
            lines.append("")

        # avar2 mappings section
        if dss_doc.avar2_mappings:
            if self.avar2_format == "matrix":
                lines.extend(self._format_avar2_as_matrix(dss_doc))
            else:
                lines.append("avar2")
                for mapping in dss_doc.avar2_mappings:
                    lines.extend(self._format_avar2_mapping(mapping, dss_doc))
            lines.append("")

        # Rules section
        if dss_doc.rules:
            lines.append("rules")
            for rule in dss_doc.rules:
                lines.extend(self._format_rule(rule, dss_doc.axes))
            lines.append("")

        # Instances section
        if dss_doc.instances_off:
            lines.append("instances off")
        elif dss_doc.instances_auto:
            lines.append("instances auto")
        elif dss_doc.instances:
            if self.optimize:
                # When optimizing with explicit instances, use instances auto
                # (assumes instances can be regenerated from axis labels)
                lines.append("instances auto")
            else:
                lines.append("instances")
                for instance in dss_doc.instances:
                    lines.append(self._format_instance(instance, dss_doc.axes))

        return "\n".join(lines).strip()

    def _get_label_for_user_value(self, axis: DSSAxis, user_value: float) -> Optional[str]:
        """Try to find a label for a user space value

        First checks actual axis mappings (user-defined labels),
        then falls back to standard mappings.

        Args:
            axis: The axis to check
            user_value: The user space value

        Returns:
            Label name if found, None otherwise
        """
        # First priority: check actual axis mappings (user-defined labels)
        for mapping in axis.mappings:
            if mapping.user_value == user_value:
                return mapping.label

        # Second priority: check standard mappings (only for weight/width)
        axis_type = axis.name.lower()
        if axis_type not in ["weight", "width"]:
            return None

        try:
            label = Standards.get_name_by_user_space(user_value, axis_type)
            # Check if it's a standard label (not a generated numeric one like "Weight400")
            if label and not (
                label.startswith(axis_type.title()) and label[len(axis_type) :].isdigit()
            ):
                return label
        except Exception:
            pass

        return None

    def _format_axis(self, axis: DSSAxis) -> List[str]:
        """Format axis definition"""
        lines = []

        # Determine axis name for output (shortened if registered)
        axis_name = self._get_axis_display_name(axis.name, axis.tag)

        # Axis header with range - detect discrete axes by values
        is_discrete = (
            axis.minimum == 0
            and axis.default == 0
            and axis.maximum == 1
            and axis.name.lower() in ["italic", "ital"]
        )

        if is_discrete:
            # Standard discrete axis (like italic) - use 'discrete' keyword
            # If display_name exists and matches axis_name, skip axis_name to avoid duplication
            use_axis_name = axis_name
            if axis.display_name and axis_name:
                if axis_name.lower() == axis.display_name.lower():
                    use_axis_name = ""

            if use_axis_name:
                axis_line = f"    {use_axis_name} {axis.tag} discrete"
            else:
                axis_line = f"    {axis.tag} discrete"
            # Add display_name if present and different from tag
            if axis.display_name and axis.display_name != axis.tag:
                axis_line += f' "{axis.display_name}"'
            lines.append(axis_line)
        else:
            # Continuous axis or non-standard discrete axis
            # Try to use label-based range if enabled and available
            # ONLY for standard axes (weight, width)
            range_str = None
            axis_type = axis.name.lower()
            if self.use_label_ranges and self.optimize and axis_type in ["weight", "width"]:
                min_label = self._get_label_for_user_value(axis, axis.minimum)
                default_label = self._get_label_for_user_value(axis, axis.default)
                max_label = self._get_label_for_user_value(axis, axis.maximum)

                # Only use label format if all three values have labels
                # AND they match standard values (no custom overrides)
                if min_label and default_label and max_label:
                    # Verify that labels match standard values
                    # (to avoid conflicts when parsing back)
                    try:
                        std_min = Standards.get_user_space_value(min_label, axis_type)
                        std_default = Standards.get_user_space_value(default_label, axis_type)
                        std_max = Standards.get_user_space_value(max_label, axis_type)

                        # Only use label-based range if values match standards
                        if (
                            std_min == axis.minimum
                            and std_default == axis.default
                            and std_max == axis.maximum
                        ):
                            range_str = f"{min_label}:{default_label}:{max_label}"
                    except Exception:
                        pass

            # Fallback to numeric format
            if not range_str:
                range_str = f"{self._format_number(axis.minimum)}:{self._format_number(axis.default)}:{self._format_number(axis.maximum)}"

            # If display_name exists and is essentially the same as axis_name, skip axis_name
            # to avoid duplication like "ROTATION IN Z ZROT 0:0:90 "Rotation in Z""
            use_axis_name = axis_name
            if axis.display_name and axis_name:
                # Compare case-insensitively to detect duplicates
                if axis_name.lower() == axis.display_name.lower():
                    use_axis_name = ""

            if use_axis_name:
                axis_line = f"    {use_axis_name} {axis.tag} {range_str}"
            else:
                axis_line = f"    {axis.tag} {range_str}"
            # Add display_name if present and different from tag
            if axis.display_name and axis.display_name != axis.tag:
                axis_line += f' "{axis.display_name}"'
            lines.append(axis_line)

        # Mappings
        if axis.mappings:
            for mapping in axis.mappings:
                # Check if this is a discrete axis with simplified format
                if is_discrete and mapping.user_value == mapping.design_value:
                    # Simplified discrete format: just "Upright" or "Italic"
                    label_line = f"        {mapping.label}"
                    if mapping.elidable:
                        label_line += " @elidable"
                    lines.append(label_line)
                else:
                    # Traditional format
                    # Check if we can use compact form (name only) for standard axes only
                    use_compact_form = False
                    axis_type = axis.name.lower()

                    # Only try compact form for standard axes (weight, width)
                    if self.optimize and axis_type in ["weight", "width"]:
                        # Check if this label exists in standard mappings
                        if Standards.has_mapping(mapping.label, axis_type):
                            try:
                                std_user_val = Standards.get_user_value_for_name(
                                    mapping.label, axis.name
                                )
                                if std_user_val == mapping.user_value:
                                    use_compact_form = True
                            except Exception:
                                pass

                    if use_compact_form:
                        # Compact form: just "Regular > 125"
                        label_line = (
                            f"        {mapping.label} > {self._format_number(mapping.design_value)}"
                        )
                    else:
                        # Full form: "400 Regular > 125" or "100 C2 > 900"
                        # Always include user_value for non-standard axes
                        user_val_str = (
                            self._format_number(mapping.user_value)
                            if mapping.user_value is not None
                            else ""
                        )
                        design_val_str = self._format_number(mapping.design_value)
                        label_line = f"        {user_val_str} {mapping.label} > {design_val_str}"

                    if mapping.elidable:
                        label_line += " @elidable"
                    lines.append(label_line)

        return lines

    def _get_axis_display_name(self, axis_name: str, axis_tag: str) -> str:
        """Get the display name for an axis - omit registered names, use uppercase for custom"""
        # Standard axis tags that can be written without name
        STANDARD_TAGS = {"wght", "wdth", "ital", "slnt", "opsz"}

        # If tag is standard, omit the name entirely (simpler format)
        if self.optimize and axis_tag in STANDARD_TAGS:
            return ""  # Just use tag

        # For custom axes (UPPERCASE tags), use name in uppercase
        if axis_tag.isupper() and len(axis_tag) == 4:
            return axis_name.upper()

        # Fallback: keep original name
        return axis_name

    def _get_label_for_coordinate(self, axis: DSSAxis, value: float) -> Optional[str]:
        """Try to find a label for a coordinate value

        Args:
            axis: The axis to search
            value: The design space coordinate value

        Returns:
            Label name if found, None otherwise
        """
        for mapping in axis.mappings:
            if mapping.design_value == value:
                return mapping.label
        return None

    def _format_condition_value(self, value: float, axis_name: str, axes: List[DSSAxis]) -> str:
        """Format a condition value - try to use label if available, otherwise format number

        Args:
            value: The design space value to format
            axis_name: Name of the axis this value belongs to
            axes: List of all axes to search for labels

        Returns:
            Formatted value (label or number)
        """
        # Find the axis
        target_axis = None
        for axis in axes:
            if axis.name == axis_name or axis.tag == axis_name:
                target_axis = axis
                break

        # Try to find a label
        if target_axis and self.use_label_coordinates:
            label = self._get_label_for_coordinate(target_axis, value)
            if label:
                return label

        # Fallback to formatted number
        return self._format_number(value)

    def _format_source(self, source: DSSSource, axes: List[DSSAxis]) -> str:
        """Format source definition"""
        # Get coordinates in axis order
        coords = []
        for axis in axes:
            value = source.location.get(axis.name, 0)

            # Try to use label if enabled and available
            if self.use_label_coordinates:
                label = self._get_label_for_coordinate(axis, value)
                if label:
                    coords.append(label)
                    continue

            # Fallback to numeric representation with proper formatting
            coords.append(self._format_number(value))

        # Use filename if it contains path, otherwise use name
        if source.filename.endswith(".ufoz"):
            display_name = source.filename
        else:
            if "/" in source.filename:
                display_name = source.filename.replace(".ufo", "")
            else:
                display_name = source.name

        # Add quotes if display_name contains spaces
        display_name = self._quote_if_spaces(display_name)

        line = f"    {display_name} [{', '.join(coords)}]"

        if source.is_base:
            line += " @base"

        if source.layer:
            # Quote layer name if it contains spaces or special characters
            layer_value = self._quote_if_spaces(source.layer)
            line += f" @layer={layer_value}"

        return line

    def _format_source_named(self, source: DSSSource, dss_doc) -> str:
        """Format source with named coordinates (only non-default values)

        Used when document has hidden axes.
        Only outputs coordinates that differ from axis defaults.
        """
        # Collect all axes (visible + hidden) with their defaults
        all_axes = {}
        for axis in dss_doc.axes:
            all_axes[axis.name] = axis
        for axis in dss_doc.hidden_axes:
            all_axes[axis.name] = axis

        # Find non-default coordinates
        non_default_coords = []
        for axis_name, value in source.location.items():
            axis = all_axes.get(axis_name)
            if axis is None:
                continue

            # Check if value differs from default
            if value != axis.default:
                # Use axis tag for output (shorter)
                axis_ref = axis.tag

                # Try to use label if available
                if self.use_label_coordinates:
                    label = self._get_label_for_coordinate(axis, value)
                    if label:
                        non_default_coords.append(f"{axis_ref}={label}")
                        continue

                # Fallback to numeric
                formatted_value = self._format_number(value)
                non_default_coords.append(f"{axis_ref}={formatted_value}")

        # Use filename if it contains path, otherwise use name
        if source.filename.endswith(".ufoz"):
            display_name = source.filename
        else:
            if "/" in source.filename:
                display_name = source.filename.replace(".ufo", "")
            else:
                display_name = source.name

        # Add quotes if display_name contains spaces
        display_name = self._quote_if_spaces(display_name)

        # Build line
        if non_default_coords:
            line = f"    {display_name} {', '.join(non_default_coords)}"
        else:
            line = f"    {display_name}"

        if source.is_base:
            line += " @base"

        if source.layer:
            # Quote layer name if it contains spaces or special characters
            layer_value = self._quote_if_spaces(source.layer)
            line += f" @layer={layer_value}"

        return line

    def _format_rule(self, rule: DSSRule, axes: List[DSSAxis]) -> List[str]:
        """Format rule definition with label-based conditions when possible

        Args:
            rule: The rule to format
            axes: List of axes for label resolution
        """
        lines = []

        # Get condition string (shared across all substitutions in this rule)
        condition_str = ""
        if rule.conditions:
            cond_parts = []
            for cond in rule.conditions:
                axis = cond["axis"]
                min_val = cond["minimum"]
                max_val = cond["maximum"]

                if min_val == max_val:
                    # Exact match: axis == value (try label or number)
                    formatted_val = self._format_condition_value(min_val, axis, axes)
                    cond_parts.append(f"{axis} == {formatted_val}")
                elif min_val is not None and max_val is not None:
                    # Range condition
                    if min_val == 0:
                        # Only upper bound: axis <= max
                        formatted_max = self._format_condition_value(max_val, axis, axes)
                        cond_parts.append(f"{axis} <= {formatted_max}")
                    elif max_val >= 1000:
                        # Only lower bound: axis >= min
                        formatted_min = self._format_condition_value(min_val, axis, axes)
                        cond_parts.append(f"{axis} >= {formatted_min}")
                    else:
                        # Full range: min <= axis <= max (try labels or numbers)
                        formatted_min = self._format_condition_value(min_val, axis, axes)
                        formatted_max = self._format_condition_value(max_val, axis, axes)
                        cond_parts.append(f"{formatted_min} <= {axis} <= {formatted_max}")
                elif min_val is not None:
                    # Only minimum: axis >= min
                    formatted_min = self._format_condition_value(min_val, axis, axes)
                    cond_parts.append(f"{axis} >= {formatted_min}")
                elif max_val is not None:
                    # Only maximum: axis <= max
                    formatted_max = self._format_condition_value(max_val, axis, axes)
                    cond_parts.append(f"{axis} <= {formatted_max}")

            if cond_parts:
                condition_str = f"({' && '.join(cond_parts)})"

        # Try to detect patterns for multiple substitutions
        if len(rule.substitutions) > 1:
            # Extract glyph list from UFO files if DesignSpace document is available
            available_glyphs = None
            if self.ds_doc and self.base_path:
                try:
                    available_glyphs = UFOGlyphExtractor.get_all_glyphs_from_sources(
                        self.ds_doc, self.base_path
                    )
                except Exception:
                    # If glyph extraction fails, continue without validation
                    pass

            pattern_info = self._detect_substitution_pattern(rule.substitutions, available_glyphs)

            if pattern_info:
                # Use compact wildcard notation with new parentheses syntax
                from_pattern, to_pattern = pattern_info
                rule_name = self._format_rule_name(rule.name)
                lines.append(f"    {from_pattern} > {to_pattern} {condition_str}{rule_name}")
            else:
                # Fallback to individual lines
                for i, (from_glyph, to_glyph) in enumerate(rule.substitutions):
                    if i == 0:
                        # Add name to first substitution line
                        rule_name = self._format_rule_name(rule.name)
                        lines.append(f"    {from_glyph} > {to_glyph} {condition_str}{rule_name}")
                    else:
                        lines.append(f"    {from_glyph} > {to_glyph} {condition_str}")
        else:
            # Single substitution
            from_glyph, to_glyph = rule.substitutions[0]
            rule_name = self._format_rule_name(rule.name)
            lines.append(f"    {from_glyph} > {to_glyph} {condition_str}{rule_name}")

        return lines

    def _format_rule_name(self, rule_name: str) -> str:
        """Format rule name for output - omit auto-generated names like rule1, rule2"""
        if not rule_name or rule_name.startswith("rule") and rule_name[4:].isdigit():
            return ""  # Omit auto-generated names
        return f' "{rule_name}"'

    def _detect_substitution_pattern(
        self, substitutions: List[Tuple[str, str]], available_glyphs: Optional[Set[str]] = None
    ) -> Optional[Tuple[str, str]]:
        """Try to detect a pattern in substitutions for compact notation

        Returns (from_pattern, to_pattern) or None
        Examples:
        - [('dollar', 'dollar.rvrn'), ('cent', 'cent.rvrn')] -> ('dollar* cent*', '.rvrn') if safe
        - [('dollar.sc', 'dollar.sc.rvrn')] -> None (single substitution)

        Args:
            substitutions: List of (from_glyph, to_glyph) tuples
            available_glyphs: Complete set of glyphs in font for validation (optional)
        """
        if len(substitutions) < 2:
            return None

        from_glyphs = [sub[0] for sub in substitutions]

        # Check if all have the same suffix transformation
        # e.g., dollar -> dollar.rvrn, cent -> cent.rvrn
        common_suffix = None
        for from_glyph, to_glyph in substitutions:
            if to_glyph.startswith(from_glyph + "."):
                suffix = to_glyph[len(from_glyph) :]
                if common_suffix is None:
                    common_suffix = suffix
                elif common_suffix != suffix:
                    common_suffix = None
                    break
            else:
                common_suffix = None
                break

        if common_suffix:
            # Try to find patterns in the from_glyphs
            patterns = []

            # Group by common prefixes
            prefix_groups = {}
            for glyph in from_glyphs:
                # Try different prefix lengths
                for prefix_len in range(3, len(glyph) + 1):
                    prefix = glyph[:prefix_len]
                    # Find all glyphs with this prefix
                    matching = [g for g in from_glyphs if g.startswith(prefix)]
                    if len(matching) > 1:
                        if prefix not in prefix_groups or len(matching) > len(
                            prefix_groups[prefix]
                        ):
                            prefix_groups[prefix] = matching

            # Convert to wildcard patterns
            used_glyphs = set()
            for prefix, glyphs in prefix_groups.items():
                if not any(g in used_glyphs for g in glyphs):
                    patterns.append(f"{prefix}*")
                    used_glyphs.update(glyphs)

            # Add remaining single glyphs
            for glyph in from_glyphs:
                if glyph not in used_glyphs:
                    patterns.append(glyph)

            if patterns:
                from_pattern = " ".join(patterns)

                # Validate that wildcard pattern doesn't over-match if we have glyph list
                if available_glyphs and any("*" in p for p in patterns):
                    expanded_glyphs = PatternMatcher.find_matching_glyphs(
                        patterns, available_glyphs
                    )
                    original_glyphs = set(from_glyphs)

                    # Only use wildcard if it matches exactly the original glyphs
                    if expanded_glyphs == original_glyphs:
                        return (from_pattern, common_suffix)
                    else:
                        # Fall back to explicit listing to ensure exact matching
                        explicit_pattern = " ".join(from_glyphs)
                        return (explicit_pattern, common_suffix)
                else:
                    # No validation possible or no wildcards - use as-is
                    return (from_pattern, common_suffix)

        return None

    def _format_instance(self, instance: DSSInstance, axes: List[DSSAxis]) -> str:
        """Format instance definition"""
        coords = []
        for axis in axes:
            value = instance.location.get(axis.name, 0)
            coords.append(self._format_number(value))

        return f"    {instance.stylename} [{', '.join(coords)}]"

    def _get_axis_tag(self, axis_name: str) -> str:
        """Convert axis name to standard tag format, supporting both short and long forms"""
        # Standard axis mappings
        axis_mappings = {
            "weight": "wght",
            "width": "wdth",
            "italic": "ital",
            "slant": "slnt",
            "optical": "opsz",
            "opticalsize": "opsz",
            "optical size": "opsz",
        }

        # Convert to lowercase for lookup
        lower_name = axis_name.lower()

        # For standard axes, return the mapped tag
        if lower_name in axis_mappings:
            return axis_mappings[lower_name]

        # For custom axes, match the display name format (uppercase)
        # This ensures consistency with _get_axis_display_name output
        return self._get_axis_display_name(axis_name, "")

    # ============================================================
    # avar2 FORMATTING METHODS
    # ============================================================

    def _format_hidden_axis(self, axis: DSSAxis) -> List[str]:
        """Format hidden axis definition for avar2

        Hidden axes use a simpler format than regular axes:
        - No mappings/labels
        - Just the range

        Format: AXIS min:default:max
        Example: XOUC 4:90:310
        """
        lines = []

        # Hidden axes typically use their tag as the name
        axis_name = axis.tag if axis.tag else axis.name

        # Format range
        range_str = f"{self._format_number(axis.minimum)}:{self._format_number(axis.default)}:{self._format_number(axis.maximum)}"

        lines.append(f"    {axis_name} {range_str}")

        return lines

    def _get_axis_default(self, axis_name: str, dss_doc: DSSDocument) -> float | None:
        """Get the default value for an axis by name or tag.

        Searches both regular and hidden axes.

        Returns:
            The axis default value, or None if axis not found.
        """
        all_axes = dss_doc.axes + dss_doc.hidden_axes
        for axis in all_axes:
            if axis.name == axis_name or axis.tag == axis_name:
                return axis.default
        return None

    def _find_variable_for_value(self, value: float, dss_doc: DSSDocument) -> str | None:
        """Find a variable name that matches the given value.

        Returns:
            Variable name (without $) if found, None otherwise.
        """
        for var_name, var_value in dss_doc.avar2_vars.items():
            if var_value == value:
                return var_name
        return None

    def _format_avar2_mapping(self, mapping, dss_doc: DSSDocument) -> List[str]:
        """Format avar2 mapping for output

        Format: ["name"] [input] > output
        Examples:
            [opsz=144] > XOUC=84, YTUC=750
            "display" [opsz=Display, wght=Bold] > XOUC=84, YTUC=$
        """
        lines = []

        # Format input conditions
        input_parts = []
        for axis_name, value in mapping.input.items():
            # Try to use label if available
            label = self._get_avar2_label_for_value(axis_name, value, dss_doc)
            if label:
                input_parts.append(f"{axis_name}={label}")
            else:
                input_parts.append(f"{axis_name}={self._format_number(value)}")

        input_str = f"[{', '.join(input_parts)}]"

        # Format output assignments
        output_parts = []
        for axis_name, value in mapping.output.items():
            # Check if value equals axis default - use $ shorthand
            axis_default = self._get_axis_default(axis_name, dss_doc)
            if axis_default is not None and value == axis_default:
                # Use shorthand: AXIS=$
                output_parts.append(f"{axis_name}=$")
            else:
                # Check if value matches a variable
                var_name = self._find_variable_for_value(value, dss_doc)
                if var_name:
                    output_parts.append(f"{axis_name}=${var_name}")
                else:
                    output_parts.append(f"{axis_name}={self._format_number(value)}")

        output_str = ", ".join(output_parts)

        # Build the line
        if mapping.name:
            line = f'    "{mapping.name}" {input_str} > {output_str}'
        else:
            line = f"    {input_str} > {output_str}"

        lines.append(line)

        return lines

    def _get_avar2_label_for_value(self, axis_name: str, value: float, dss_doc: DSSDocument) -> Optional[str]:
        """Try to find a label for an avar2 input value

        Searches both regular and hidden axes for matching labels.

        Args:
            axis_name: Axis name or tag
            value: The value to find a label for
            dss_doc: The DSS document with axis definitions

        Returns:
            Label name if found, None otherwise
        """
        # Search in regular axes
        for axis in dss_doc.axes:
            if axis.name == axis_name or axis.tag == axis_name:
                for mapping in axis.mappings:
                    if mapping.design_value == value:
                        return mapping.label
                break

        # Hidden axes typically don't have labels
        return None

    def _format_avar2_as_matrix(self, dss_doc: DSSDocument) -> List[str]:
        """Format avar2 mappings as matrix format

        Matrix format is more compact when multiple mappings share the same output axes.

        Format:
            avar2 matrix
                outputs  AXIS1  AXIS2  AXIS3
                [input1]  val1   val2   val3
                [input2]  val1   val2   val3
        """
        lines = []

        if not dss_doc.avar2_mappings:
            return lines

        # Collect all unique output axes in consistent order
        output_axes = []
        for mapping in dss_doc.avar2_mappings:
            for axis_name in mapping.output.keys():
                if axis_name not in output_axes:
                    output_axes.append(axis_name)

        # Start matrix section
        lines.append("avar2 matrix")

        # Output header row
        header_parts = ["outputs"] + output_axes
        # Calculate column widths for alignment
        col_widths = self._calculate_matrix_column_widths(dss_doc, output_axes)
        header_line = "    " + "  ".join(
            part.ljust(col_widths.get(i, len(part)))
            for i, part in enumerate(header_parts)
        )
        lines.append(header_line)

        # Format each mapping as a data row
        for mapping in dss_doc.avar2_mappings:
            # Format input conditions
            input_parts = []
            for axis_name, value in mapping.input.items():
                label = self._get_avar2_label_for_value(axis_name, value, dss_doc)
                if label:
                    input_parts.append(f"{axis_name}={label}")
                else:
                    input_parts.append(f"{axis_name}={self._format_number(value)}")
            input_str = f"[{', '.join(input_parts)}]"

            # Format output values in column order
            value_parts = []
            for axis_name in output_axes:
                if axis_name in mapping.output:
                    value = mapping.output[axis_name]
                    # Check if value equals axis default - use $ shorthand
                    axis_default = self._get_axis_default(axis_name, dss_doc)
                    if axis_default is not None and value == axis_default:
                        value_parts.append("$")
                    else:
                        # Check if value matches a variable
                        var_name = self._find_variable_for_value(value, dss_doc)
                        if var_name:
                            value_parts.append(f"${var_name}")
                        else:
                            value_parts.append(self._format_number(value))
                else:
                    # Missing value - use dash or empty
                    value_parts.append("-")

            # Build the row with alignment
            row_parts = [input_str] + value_parts
            row_line = "    " + "  ".join(
                part.ljust(col_widths.get(i, len(part)))
                for i, part in enumerate(row_parts)
            )
            lines.append(row_line)

        return lines

    def _calculate_matrix_column_widths(self, dss_doc: DSSDocument, output_axes: List[str]) -> dict:
        """Calculate column widths for matrix alignment

        Returns dict mapping column index to width.
        """
        widths = {}

        # Column 0 is the input/outputs column
        max_input_len = len("outputs")
        for mapping in dss_doc.avar2_mappings:
            input_parts = []
            for axis_name, value in mapping.input.items():
                label = self._get_avar2_label_for_value(axis_name, value, dss_doc)
                if label:
                    input_parts.append(f"{axis_name}={label}")
                else:
                    input_parts.append(f"{axis_name}={self._format_number(value)}")
            input_str = f"[{', '.join(input_parts)}]"
            max_input_len = max(max_input_len, len(input_str))
        widths[0] = max_input_len

        # Columns 1+ are output axes
        for i, axis_name in enumerate(output_axes):
            max_len = len(axis_name)
            for mapping in dss_doc.avar2_mappings:
                if axis_name in mapping.output:
                    value = mapping.output[axis_name]
                    axis_default = self._get_axis_default(axis_name, dss_doc)
                    if axis_default is not None and value == axis_default:
                        val_str = "$"
                    else:
                        # Check if value matches a variable
                        var_name = self._find_variable_for_value(value, dss_doc)
                        if var_name:
                            val_str = f"${var_name}"
                        else:
                            val_str = self._format_number(value)
                    max_len = max(max_len, len(val_str))
            widths[i + 1] = max_len

        return widths
