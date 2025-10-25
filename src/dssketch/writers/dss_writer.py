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
    ):
        self.optimize = optimize
        self.ds_doc = ds_doc
        self.base_path = base_path

    def write(self, dss_doc: DSSDocument) -> str:
        """Generate DSS string from document"""
        lines = []

        # Family declaration
        lines.append(f"family {dss_doc.family}")
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

        # Sources section
        if dss_doc.sources:
            # Add sources keyword with explicit axis order
            if dss_doc.axes:
                axis_tags = [self._get_axis_tag(axis.name) for axis in dss_doc.axes]
                lines.append(f"sources [{', '.join(axis_tags)}]")
            else:
                lines.append("sources")

            for source in dss_doc.sources:
                lines.append(self._format_source(source, dss_doc.axes))
            lines.append("")

        # Rules section
        if dss_doc.rules:
            lines.append("rules")
            for rule in dss_doc.rules:
                lines.extend(self._format_rule(rule))
            lines.append("")

        # Instances (if not using auto)
        if dss_doc.instances and not self.optimize:
            lines.append("instances")
            for instance in dss_doc.instances:
                lines.append(self._format_instance(instance, dss_doc.axes))
        elif self.optimize:
            lines.append("instances auto")

        return "\n".join(lines).strip()

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
            if axis_name:
                lines.append(f"    {axis_name} {axis.tag} discrete")
            else:
                lines.append(f"    {axis.tag} discrete")
        else:
            # Continuous axis or non-standard discrete axis
            if axis_name:
                lines.append(
                    f"    {axis_name} {axis.tag} {axis.minimum}:{axis.default}:{axis.maximum}"
                )
            else:
                lines.append(f"    {axis.tag} {axis.minimum}:{axis.default}:{axis.maximum}")

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
                    # Check if we can use compact form (name only)
                    try:
                        std_user_val = Standards.get_user_value_for_name(mapping.label, axis.name)
                        if std_user_val == mapping.user_value and self.optimize:
                            # Compact form: just "Regular > 125"
                            label_line = f"        {mapping.label} > {mapping.design_value}"
                        else:
                            # Full form: "400 Regular > 125"
                            label_line = f"        {mapping.user_value} {mapping.label} > {mapping.design_value}"
                    except Exception:
                        # Full form when standard lookup fails
                        label_line = (
                            f"        {mapping.user_value} {mapping.label} > {mapping.design_value}"
                        )

                    if mapping.elidable:
                        label_line += " @elidable"
                    lines.append(label_line)

        return lines

    def _get_axis_display_name(self, axis_name: str, axis_tag: str) -> str:
        """Get the display name for an axis - omit registered names, use uppercase for custom"""
        axis_name_lower = axis_name.lower()

        # Check if it's a registered axis (can be omitted)
        if self.optimize and axis_name_lower in self.REGISTERED_AXES:
            expected_tag = self.REGISTERED_AXES[axis_name_lower]
            # Only omit if the tag matches the expected registered tag
            if axis_tag == expected_tag:
                return ""  # Will be handled in the caller

        # For non-registered axes, use uppercase
        if axis_name_lower not in self.REGISTERED_AXES:
            return axis_name.upper()

        # For registered axes with non-standard tags, keep original name
        return axis_name

    def _format_source(self, source: DSSSource, axes: List[DSSAxis]) -> str:
        """Format source definition"""
        # Get coordinates in axis order
        coords = []
        for axis in axes:
            value = source.location.get(axis.name, 0)
            coords.append(str(int(value) if value.is_integer() else value))

        # Use filename if it contains path, otherwise use name
        if "/" in source.filename:
            # Remove .ufo extension for display
            display_name = source.filename.replace(".ufo", "")
        else:
            display_name = source.name

        line = f"    {display_name} [{', '.join(coords)}]"

        if source.is_base:
            line += " @base"

        return line

    def _format_rule(self, rule: DSSRule) -> List[str]:
        """Format rule definition"""
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
                    cond_parts.append(f"{axis} == {min_val}")
                elif min_val is not None and max_val is not None:
                    if min_val == 0:
                        cond_parts.append(f"{axis} <= {max_val}")
                    elif max_val >= 1000:
                        cond_parts.append(f"{axis} >= {min_val}")
                    else:
                        cond_parts.append(f"{min_val} <= {axis} <= {max_val}")
                elif min_val is not None:
                    cond_parts.append(f"{axis} >= {min_val}")
                elif max_val is not None:
                    cond_parts.append(f"{axis} <= {max_val}")

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
            coords.append(str(int(value) if value.is_integer() else value))

        return f"    {instance.stylename} [{', '.join(coords)}]"
    
    def _get_axis_tag(self, axis_name: str) -> str:
        """Convert axis name to standard tag format, supporting both short and long forms"""
        # Standard axis mappings
        axis_mappings = {
            'weight': 'wght',
            'width': 'wdth', 
            'italic': 'ital',
            'slant': 'slnt',
            'optical': 'opsz',
            'opticalsize': 'opsz',
        }
        
        # Convert to lowercase for lookup
        lower_name = axis_name.lower()
        
        # For standard axes, return the mapped tag
        if lower_name in axis_mappings:
            return axis_mappings[lower_name]
        
        # For custom axes, match the display name format (uppercase)
        # This ensures consistency with _get_axis_display_name output
        return self._get_axis_display_name(axis_name, "")
