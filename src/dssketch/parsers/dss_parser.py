"""
DSS Parser Module (Refactored)

Clean version with separated validation concerns.
"""

import re
from pathlib import Path
from typing import List

from ..core.mappings import Standards
from ..core.models import DSSAxis, DSSAxisMapping, DSSDocument, DSSInstance, DSSSource, DSSRule
from ..utils.discrete import DiscreteAxisHandler
from ..utils.dss_validator import DSSValidationError, DSSValidator
from ..utils.logging import DSSketchLogger


class DSSParser:
    """Parse DSS format into structured data with clean validation separation"""

    # Tag to standard name mapping for registered axes
    TAG_TO_NAME = {
        "ital": "italic",
        "opsz": "optical",
        "slnt": "slant",
        "wdth": "width",
        "wght": "weight",
    }

    def __init__(self, strict_mode: bool = True):
        self.document = DSSDocument(family="")
        self.current_section = None
        self.current_axis = None
        self.source_axis_order = None  # Explicit axis order from sources section
        self.in_skip_subsection = False  # Track if we're parsing skip subsection
        self.discrete_labels = DiscreteAxisHandler.load_discrete_labels()
        self.validator = DSSValidator(strict_mode=strict_mode)
        # Note: Rule names now handled via @name syntax instead of comments

    @staticmethod
    def _extract_quoted_or_plain_value(text: str) -> str:
        """Extract value that may be quoted ("value" or 'value') or plain (value)

        Supports:
        - Double quotes: "FontName Condensed" -> FontName Condensed
        - Single quotes: 'FontName Condensed' -> FontName Condensed
        - No quotes: FontName -> FontName
        - Strips leading/trailing whitespace from extracted value

        Returns the extracted value.
        """
        text = text.strip()

        # Check for double quotes
        if text.startswith('"') and '"' in text[1:]:
            end_quote = text.index('"', 1)
            return text[1:end_quote].strip()

        # Check for single quotes
        if text.startswith("'") and "'" in text[1:]:
            end_quote = text.index("'", 1)
            return text[1:end_quote].strip()

        # No quotes - return first word only (split on whitespace)
        # This maintains backward compatibility for values without quotes
        parts = text.split()
        return parts[0] if parts else ""

    def parse_file(self, filepath: str) -> DSSDocument:
        """Parse DSS file"""
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        return self.parse(content)

    def parse(self, content: str) -> DSSDocument:
        """Parse DSS content"""
        lines = content.split("\n")

        for line_no, line in enumerate(lines, 1):
            original_line = line.rstrip()  # Keep leading spaces but remove trailing

            # Handle comments before removing them
            if "#" in line:
                comment_part = line[line.index("#") :]
                line = line[: line.index("#")]

                # If line is only a comment, process it separately
                if not line.strip():
                    try:
                        self._parse_line(comment_part.strip(), original_line)
                    except Exception as e:
                        raise ValueError(
                            f"Error parsing line {line_no}: {original_line}\n{e}"
                        ) from e
                    continue

            line = line.rstrip()  # Remove only trailing whitespace

            if not line.strip():  # Check if line is effectively empty
                continue

            try:
                self._parse_line(line, original_line)
            except Exception as e:
                raise ValueError(f"Error parsing line {line_no}: {original_line}\n{e}") from e

        # Validate complete document
        try:
            errors, warnings = self.validator.validate_document(self.document)

            # Report warnings
            if warnings:
                DSSketchLogger.warning(f"DSS validation warnings ({len(warnings)}):")
                for warning in warnings:
                    DSSketchLogger.warning(f"  • {warning}")

            # Report non-critical errors
            non_critical_errors = [e for e in errors if not e.startswith("CRITICAL:")]
            if non_critical_errors:
                if self.validator.strict_mode:
                    error_msg = f"DSS validation errors ({len(non_critical_errors)}):" + "\n".join(
                        [f"\n  • {error}" for error in non_critical_errors]
                    )
                    raise ValueError(error_msg)
                else:
                    DSSketchLogger.error(f"DSS validation errors ({len(non_critical_errors)}):")
                    for error in non_critical_errors:
                        DSSketchLogger.error(f"  • {error}")

        except DSSValidationError as e:
            # Critical errors always fail
            raise ValueError(str(e)) from e

        return self.document

    def _parse_line(self, line: str, original_line: str = None):
        """Parse a single line based on context"""

        # Keep original for better error detection
        if original_line is None:
            original_line = line

        # Normalize whitespace for processing but keep original for detection
        line = DSSValidator.normalize_whitespace(line)

        # Check for bracket mismatches
        bracket_issues = DSSValidator.detect_bracket_mismatch(line)
        if bracket_issues:
            self.validator.warnings.append(f"Bracket issues: {bracket_issues}")

        # Handle comments - store them for potential rule names
        if line.startswith("#"):
            # Extract comment text, removing the # and whitespace
            comment_text = line[1:].strip()
            if self.current_section == "rules":
                self.current_rule_comment = comment_text
            return

        # Main sections - validate keywords
        first_word = line.split()[0] if line.split() else ""

        if line.startswith("family "):
            family_value = self._extract_quoted_or_plain_value(line[7:])
            if not family_value:
                self.validator.errors.append("Family name cannot be empty")
                return
            self.document.family = family_value
            self.current_section = "family"

        elif line == "family":
            # Handle case where "family " was stripped to "family"
            self.validator.errors.append("Family name cannot be empty")
            return

        elif line.startswith("suffix "):
            self.document.suffix = line[7:].strip()

        elif line.startswith("path "):
            path_value = line[5:].strip()
            if not path_value:
                self.validator.warnings.append("Path value is empty")
            self.document.path = path_value

        elif line == "axes" or line.startswith("axes "):
            self.current_section = "axes"

        elif line == "sources" or line.startswith("sources "):
            self.current_section = "sources"
            # Parse explicit axis order if present: sources [wght, ital]
            if "[" in line and "]" in line:
                axis_order_str = line[line.index("[") + 1 : line.index("]")]
                axis_tags = [tag.strip() for tag in axis_order_str.split(",")]
                # Convert tags to full axis names
                self.source_axis_order = [self._tag_to_axis_name(tag) for tag in axis_tags]

        elif line == "instances" or line.startswith("instances "):
            self.current_section = "instances"
            self.in_skip_subsection = False  # Reset skip subsection flag
            if "auto" in line:
                self.document.instances_auto = True

        elif line == "rules" or line.startswith("rules "):
            self.current_section = "rules"
            self.in_skip_subsection = False  # Reset skip subsection flag

        # Parse based on current section (highest priority)
        elif self.current_section == "axes":
            self._parse_axis_line(line)

        elif self.current_section == "sources":
            self._parse_source_line(line)

        elif self.current_section == "instances":
            self._parse_instance_line(line)

        elif self.current_section == "rules":
            self._parse_rule_line(line)

        # Check for potential keyword typos or misplaced section headers
        elif first_word:
            # First, check for non-ASCII characters (more specific error)
            if DSSValidator.is_likely_section_typo(first_word):
                error_msg = f"Invalid section keyword '{first_word}' - contains non-ASCII characters or typos"
                if self.validator.strict_mode:
                    # In strict mode, non-ASCII typos fail immediately
                    raise ValueError(error_msg)
                else:
                    self.validator.errors.append(error_msg)
                return

            # Then check if this might be a misspelled section keyword using Levenshtein distance
            is_valid, suggestion = DSSValidator.validate_keyword(
                first_word, DSSValidator.VALID_KEYWORDS
            )
            if not is_valid and suggestion:
                error_msg = f"Unknown keyword '{first_word}'. Did you mean '{suggestion}'?"
                if self.validator.strict_mode:
                    # In strict mode, keyword typos fail immediately
                    raise ValueError(error_msg)
                else:
                    self.validator.errors.append(error_msg)
                return
            elif first_word.lower() in [kw.lower() for kw in DSSValidator.VALID_KEYWORDS]:
                # It's a valid keyword but in wrong format or context
                self.validator.warnings.append(
                    f"Possible section keyword '{first_word}' found but not processed. Check spelling and format."
                )
            else:
                # Unrecognized line
                self.validator.warnings.append(f"Unrecognized line: {line}")

    def _parse_axis_line(self, line: str):
        """Parse axis definition lines"""

        # Strip leading whitespace for pattern matching
        line = line.strip()

        # Check for axis definition patterns
        # Pattern 1: "weight wght 100:400:900" (full form)
        # Pattern 2: "CONTRAST CNTR 0:0:100" (custom axis)
        # Pattern 3: "wght 100:400:900" (registered axis, name omitted)
        # Pattern 4: "ital binary" (registered binary axis)
        # Pattern 5: "weight 100:400:900" (legacy form with inferred tag)

        if re.match(r"^\w+\s+\w{4}\s+", line) and ">" not in line:
            # Full form: name tag range
            # Note: Exclude lines with ">" to avoid matching mappings like "500 Bold > 1000"
            parts = line.split()
            name = parts[0]
            tag = parts[1]

            # Validate axis tag for potential typos
            is_valid_tag, suggested_tag = DSSValidator.validate_axis_tag(tag)
            if not is_valid_tag and suggested_tag:
                error_msg = (
                    f"Axis tag '{tag}' looks like a typo of standard axis '{suggested_tag}'. "
                    f"Did you mean '{suggested_tag}'? "
                    f"If you want to create a custom axis, use an UPPERCASE tag (e.g., '{tag.upper()}'). "
                    f"Standard axis tags: wght, wdth, ital, slnt, opsz"
                )
                if self.validator.strict_mode:
                    raise ValueError(error_msg)
                else:
                    self.validator.errors.append(error_msg)
                    # Continue parsing - let the axis be created even with typo

            # Parse range, binary, or discrete
            if len(parts) > 2:
                range_part = parts[2]

                # Validate axis range (skip validation for label-based ranges)
                # Check if this might be a label-based range
                is_label_based = ":" in range_part and not all(
                    v.replace(".", "").replace("-", "").replace("+", "").isdigit()
                    for v in range_part.split(":")
                )

                if not is_label_based:
                    is_valid, error_msg = DSSValidator.validate_axis_range(range_part)
                    if not is_valid:
                        self.validator.errors.append(
                            f"Invalid axis range for '{name}': {error_msg}"
                        )
                        return

                if range_part in ["binary", "discrete"]:
                    minimum, default, maximum = 0, 0, 1
                elif ":" in range_part:
                    values = range_part.split(":")
                    try:
                        # Try to resolve each value (supports both numbers and labels)
                        minimum = self._resolve_axis_range_value(values[0], name)
                        default = (
                            self._resolve_axis_range_value(values[1], name)
                            if len(values) > 2
                            else minimum
                        )
                        maximum = self._resolve_axis_range_value(values[-1], name)
                    except ValueError as e:
                        self.validator.errors.append(f"Invalid axis range for '{name}': {e}")
                        return
                else:
                    try:
                        minimum = default = maximum = self._resolve_axis_range_value(
                            range_part, name
                        )
                    except ValueError as e:
                        self.validator.errors.append(f"Invalid axis range for '{name}': {e}")
                        return
            else:
                minimum = default = maximum = 0

        elif re.match(r"^\w{4}\s+", line) and ">" not in line:
            # Shortened form: tag range (for registered axes)
            # But not if it contains '>' (that's a mapping)
            parts = line.split()
            tag = parts[0]

            # Validate axis tag for potential typos
            is_valid_tag, suggested_tag = DSSValidator.validate_axis_tag(tag)
            if not is_valid_tag and suggested_tag:
                error_msg = (
                    f"Axis tag '{tag}' looks like a typo of standard axis '{suggested_tag}'. "
                    f"Did you mean '{suggested_tag}'? "
                    f"If you want to create a custom axis, use an UPPERCASE tag (e.g., '{tag.upper()}'). "
                    f"Standard axis tags: wght, wdth, ital, slnt, opsz"
                )
                if self.validator.strict_mode:
                    raise ValueError(error_msg)
                else:
                    self.validator.errors.append(error_msg)
                    # Continue parsing - let the axis be created even with typo

            # Get standard name from tag
            name = self.TAG_TO_NAME.get(tag, tag.upper())

            # Parse range, binary, or discrete
            if len(parts) > 1:
                range_part = parts[1]

                # Validate axis range (skip validation for label-based ranges)
                is_label_based = ":" in range_part and not all(
                    v.replace(".", "").replace("-", "").replace("+", "").isdigit()
                    for v in range_part.split(":")
                )

                if not is_label_based:
                    is_valid, error_msg = DSSValidator.validate_axis_range(range_part)
                    if not is_valid:
                        self.validator.errors.append(
                            f"Invalid axis range for '{name}': {error_msg}"
                        )
                        return

                if range_part in ["binary", "discrete"]:
                    minimum, default, maximum = 0, 0, 1
                elif ":" in range_part:
                    values = range_part.split(":")
                    try:
                        minimum = self._resolve_axis_range_value(values[0], name)
                        default = (
                            self._resolve_axis_range_value(values[1], name)
                            if len(values) > 2
                            else minimum
                        )
                        maximum = self._resolve_axis_range_value(values[-1], name)
                    except ValueError as e:
                        self.validator.errors.append(f"Invalid axis range for '{name}': {e}")
                        return
                else:
                    try:
                        minimum = default = maximum = self._resolve_axis_range_value(
                            range_part, name
                        )
                    except ValueError as e:
                        self.validator.errors.append(f"Invalid axis range for '{name}': {e}")
                        return
            else:
                minimum = default = maximum = 0
        elif re.match(r"^\w+\s+(\S+)", line) and ">" not in line and "@elidable" not in line:
            # Human-readable axis names: "weight 100:400:900" or "width Condensed:Normal:Extended"
            # Supports both numeric and label-based ranges
            # Excludes discrete axis labels like "Upright @elidable"
            parts = line.split()

            # Skip if only one word (likely a discrete axis label like "Upright" or "Italic")
            if len(parts) < 2:
                return

            # Second part must be a range or keyword, not a flag
            # Check if second part is a valid range/keyword
            second_part = parts[1]
            is_keyword = second_part in ["binary", "discrete"]
            is_range = ":" in second_part or (
                len(second_part) > 0 and (second_part[0].isdigit() or second_part[0] == "-")
            )

            if not (is_keyword or is_range):
                # This is not an axis definition, probably a discrete axis label
                return

            name = parts[0]

            # Infer tag from name (support human-readable names)
            if name.lower() == "weight":
                tag = "wght"
            elif name.lower() == "width":
                tag = "wdth"
            elif name.lower() == "italic":
                tag = "ital"
            elif name.lower() == "slant":
                tag = "slnt"
            elif name.lower() == "optical":
                tag = "opsz"
            else:
                tag = name[:4].upper()  # Use first 4 chars as tag

            # Parse range, binary, or discrete
            if len(parts) > 1:
                range_part = parts[1]

                # Validate axis range (skip validation for label-based ranges)
                is_label_based = ":" in range_part and not all(
                    v.replace(".", "").replace("-", "").replace("+", "").isdigit()
                    for v in range_part.split(":")
                )

                if not is_label_based:
                    is_valid, error_msg = DSSValidator.validate_axis_range(range_part)
                    if not is_valid:
                        self.validator.errors.append(
                            f"Invalid axis range for '{name}': {error_msg}"
                        )
                        return

                if range_part in ["binary", "discrete"]:
                    minimum, default, maximum = 0, 0, 1
                elif ":" in range_part:
                    values = range_part.split(":")
                    try:
                        minimum = self._resolve_axis_range_value(values[0], name)
                        default = (
                            self._resolve_axis_range_value(values[1], name)
                            if len(values) > 2
                            else minimum
                        )
                        maximum = self._resolve_axis_range_value(values[-1], name)
                    except ValueError as e:
                        self.validator.errors.append(f"Invalid axis range for '{name}': {e}")
                        return
                else:
                    try:
                        minimum = default = maximum = self._resolve_axis_range_value(
                            range_part, name
                        )
                    except ValueError as e:
                        self.validator.errors.append(f"Invalid axis range for '{name}': {e}")
                        return
            else:
                minimum = default = maximum = 0
        else:
            # Not an axis definition, might be a mapping
            if self.current_axis:
                # Check for traditional format with > or simplified format
                if ">" in line or (line.strip() and not line.startswith(" " * 8)):
                    self._parse_axis_mapping(line)
            return

        self.current_axis = DSSAxis(
            name=name, tag=tag, minimum=minimum, default=default, maximum=maximum
        )
        self.document.axes.append(self.current_axis)

    def _parse_axis_mapping(self, line: str):
        """Parse axis mapping line"""
        # Strip leading whitespace for pattern matching
        line = line.strip()
        # Check if this is a discrete axis using centralized handler
        is_discrete = DiscreteAxisHandler.is_discrete(self.current_axis)

        # Check for @elidable flag
        elidable = "@elidable" in line
        if elidable:
            line = line.replace("@elidable", "").strip()

        if ">" in line:
            # Traditional format: "300 Light > 295" or "0.0 Upright > 0.0"
            parts = line.split(">")
            left = parts[0].strip()
            design = float(parts[1].strip())

            # Parse left side
            left_parts = left.split()

            if left_parts[0].replace(".", "").replace("-", "").isdigit():
                # Format: "300 Light" or "0.0 Upright"
                user = float(left_parts[0])
                label = " ".join(left_parts[1:]) if len(left_parts) > 1 else ""
                if not label:
                    label = Standards.get_name_for_user_value(user, self.current_axis.name)
            else:
                # Format: "Light > 295" or "XX > 60" - infer user value
                label = left
                # Check if this label exists in standard mappings
                if Standards.has_mapping(label, self.current_axis.name):
                    # Use standard mapping for known labels
                    user = Standards.get_user_value_for_name(label, self.current_axis.name)
                else:
                    # For unknown labels, use design_value as user_value
                    user = design
        else:
            # Simplified format for discrete axes: just "Upright" or "Italic"
            if not is_discrete:
                raise ValueError(
                    f"Simplified label format only supported for discrete axes: {line}"
                )

            label = line.strip()

            # Find user and design values from discrete labels
            axis_tag = self.current_axis.tag
            user = None
            design = None

            if axis_tag in self.discrete_labels:
                for value, labels in self.discrete_labels[axis_tag].items():
                    if label in labels:
                        user = float(value)
                        design = float(value)  # For discrete axes, design = user
                        break

            if user is None:
                # Fallback: try standard mappings
                try:
                    user = Standards.get_user_value_for_name(label, self.current_axis.name)
                    design = user
                except Exception:
                    raise ValueError(f"Unknown discrete axis label: {label}")

        # Validate mapping label for potential typos
        is_valid_label, suggested_label = DSSValidator.validate_mapping_label(
            label, self.current_axis.tag, self.document.axes
        )
        if not is_valid_label and suggested_label:
            self.validator.warnings.append(
                f"Axis '{self.current_axis.name}': mapping label '{label}' looks like a typo. "
                f"Did you mean '{suggested_label}'? "
                f"If this is a custom label, ignore this warning."
            )

        mapping = DSSAxisMapping(
            user_value=user, design_value=design, label=label, elidable=elidable
        )
        self.current_axis.mappings.append(mapping)

    def _resolve_axis_range_value(self, value_str: str, axis_name: str) -> float:
        """Resolve axis range value - can be numeric or label name

        Args:
            value_str: String value that can be either a number (e.g., "400") or label (e.g., "Regular")
            axis_name: Name of the axis (e.g., "weight", "width")

        Returns:
            Float user space coordinate value

        Raises:
            ValueError: If label not found in standard mappings or invalid numeric value

        Examples:
            _resolve_axis_range_value("400", "weight") -> 400.0
            _resolve_axis_range_value("Regular", "weight") -> 400.0
            _resolve_axis_range_value("Condensed", "width") -> 75.0
        """
        value_str = value_str.strip()

        # Try to parse as number first
        try:
            return float(value_str)
        except ValueError:
            # Not a number, treat as label name
            pass

        # Try to get user space value from standard mappings
        # This only works for standard axes (weight, width)
        axis_type = axis_name.lower()
        if axis_type in ["weight", "width"]:
            # Check if this label exists in standard mappings
            if not Standards.has_mapping(value_str, axis_type):
                raise ValueError(
                    f"Label '{value_str}' not found in standard {axis_type} mappings. "
                    f"Use numeric values or valid standard labels (e.g., Thin, Light, Regular, Bold, Black for weight)."
                )

            user_value = Standards.get_user_space_value(value_str, axis_type)
            return user_value
        else:
            raise ValueError(
                f"Label-based ranges only supported for 'weight' and 'width' axes. "
                f"Axis '{axis_name}' requires numeric values."
            )

    def _resolve_coordinate_value(self, value_str: str, axis_index: int) -> float:
        """Resolve coordinate value - can be numeric or label name

        Args:
            value_str: String value that can be either a number (e.g., "362") or label (e.g., "Regular")
            axis_index: Index of the axis in the axis order

        Returns:
            Float design space coordinate value

        Raises:
            ValueError: If label not found in axis mappings or invalid numeric value
        """
        value_str = value_str.strip()

        # Try to parse as number first
        try:
            return float(value_str)
        except ValueError:
            # Not a number, treat as label name
            pass

        # Get the corresponding axis
        if self.source_axis_order:
            # Use explicit axis order
            if axis_index >= len(self.source_axis_order):
                raise ValueError(f"Coordinate index {axis_index} exceeds axis count")
            axis_name = self.source_axis_order[axis_index]
        else:
            # Use document axes order
            if axis_index >= len(self.document.axes):
                raise ValueError(f"Coordinate index {axis_index} exceeds axis count")
            axis_name = self.document.axes[axis_index].name

        # Find the axis in document
        target_axis = None
        for axis in self.document.axes:
            if axis.name == axis_name:
                target_axis = axis
                break

        if not target_axis:
            raise ValueError(f"Axis '{axis_name}' not found in document")

        # Search for label in axis mappings
        for mapping in target_axis.mappings:
            if mapping.label == value_str:
                return mapping.design_value

        # Label not found
        raise ValueError(
            f"Label '{value_str}' not found in axis '{axis_name}' mappings. "
            f"Available labels: {', '.join([m.label for m in target_axis.mappings])}"
        )

    def _resolve_condition_value(self, value_str: str, axis_name: str) -> float:
        """Resolve condition value - can be numeric or label name

        Args:
            value_str: String value that can be either a number (e.g., "700") or label (e.g., "Bold")
            axis_name: Name or tag of the axis (e.g., "weight", "wght", "width")

        Returns:
            Float design space coordinate value

        Raises:
            ValueError: If label not found in axis mappings or invalid numeric value
        """
        value_str = value_str.strip()

        # Try to parse as number first
        try:
            return float(value_str)
        except ValueError:
            # Not a number, treat as label name
            pass

        # Find the axis in document by name or tag
        target_axis = None
        for axis in self.document.axes:
            if axis.name == axis_name or axis.tag == axis_name:
                target_axis = axis
                break

        if not target_axis:
            raise ValueError(
                f"Axis '{axis_name}' not found in document. "
                f"Available axes: {', '.join([a.name for a in self.document.axes])}"
            )

        # Search for label in axis mappings
        for mapping in target_axis.mappings:
            if mapping.label == value_str:
                return mapping.design_value

        # Label not found
        raise ValueError(
            f"Label '{value_str}' not found in axis '{target_axis.name}' mappings. "
            f"Available labels: {', '.join([m.label for m in target_axis.mappings])}"
        )

    def _parse_source_line(self, line: str):
        """Parse source definition line"""
        # Strip leading whitespace for pattern matching
        line = line.strip()
        # Extract flags
        is_base = "@base" in line
        line = line.replace("@base", "").strip()

        # Parse coordinates
        if "[" in line and "]" in line:
            # Format: "Light [0, 0]" or "My Font Light.ufo" [0, 0]
            # Also supports: "Regular [Regular, Upright]" (label-based)
            name_part = line[: line.index("[")].strip()
            name = self._extract_quoted_or_plain_value(name_part)
            coords_str = line[line.index("[") + 1 : line.index("]")]

            # Validate coordinates (skip if using labels - will validate during resolution)
            coord_parts = [x.strip() for x in coords_str.split(",")]

            # Check if all parts are numeric
            all_numeric = all(
                x.replace(".", "")
                .replace("-", "")
                .replace("+", "")
                .replace("e", "")
                .replace("E", "")
                .isdigit()
                for x in coord_parts
                if x
            )

            if all_numeric:
                # Traditional numeric validation
                is_valid, error_msg = DSSValidator.validate_coordinates(coords_str)
                if not is_valid:
                    self.validator.errors.append(
                        f"Invalid coordinates in source '{name}': {error_msg}"
                    )
                    return

            # Resolve coordinates - supports both numbers and labels
            coords = []
            for i, coord_str in enumerate(coord_parts):
                try:
                    value = self._resolve_coordinate_value(coord_str, i)
                    coords.append(value)
                except ValueError as e:
                    self.validator.errors.append(
                        f"Invalid coordinate in source '{name}' at position {i}: {e}"
                    )
                    return
        else:
            # Format: "Light 0 0" (space-separated, only works without quotes)
            parts = line.split()
            name = parts[0]
            coords = [float(x) for x in parts[1:] if x.replace(".", "").replace("-", "").isdigit()]

        # Create location dict using explicit axis order if available
        location = {}
        if self.source_axis_order:
            # Use explicit axis order from sources section
            for i, axis_name in enumerate(self.source_axis_order):
                if i < len(coords):
                    # Find the matching axis in document.axes to get the full axis object
                    for axis in self.document.axes:
                        if axis.name == axis_name:
                            location[axis.name] = coords[i]
                            break
        else:
            # Fallback to document.axes order (backward compatibility)
            for i, axis in enumerate(self.document.axes):
                if i < len(coords):
                    location[axis.name] = coords[i]

        # Determine filename and name
        if "/" in name:
            # Path is included in the name
            filename = name if name.endswith(".ufo") else f"{name}.ufo"
            name = Path(name).stem
        else:
            # Simple name without path
            filename = name if name.endswith(".ufo") else f"{name}.ufo"

        source = DSSSource(name=name, filename=filename, location=location, is_base=is_base)

        self.document.sources.append(source)

    def _parse_instance_line(self, line: str):
        """Parse instance definition line

        Handles:
        - skip subsection: collects instance combinations to skip
        - explicit instances (not implemented yet)
        """
        # Check if this is the start of skip subsection
        if line.strip().startswith("skip"):
            self.in_skip_subsection = True
            return

        # If we're in skip subsection, collect skip combinations
        if self.in_skip_subsection:
            # Skip combinations should be indented
            if line.startswith("    ") or line.startswith("\t"):
                combination = line.strip()
                if combination:  # Ignore empty lines
                    self.document.instances_skip.append(combination)
            else:
                # Non-indented line means we're exiting skip subsection
                self.in_skip_subsection = False
                # Don't return - let it fall through to process this line

        # Parse explicit instances (if not auto and not skip)
        line = line.strip()
        if line != "auto" and not self.in_skip_subsection:
            # Parse explicit instance (similar to source parsing)
            # TODO: implement explicit instance parsing if needed
            pass

    def _parse_condition_string(self, condition_str: str) -> List[dict]:
        """Parse condition string like 'weight >= 480' or 'weight >= Bold'

        Supports:
        - Numeric values: 'weight >= 700', '400 <= weight <= 700'
        - Label values: 'weight >= Bold', 'Regular <= weight <= Black'
        - Mixed: '400 <= weight <= Black', 'Regular <= width <= 125'
        """
        conditions = []
        if not condition_str:
            return conditions

        # Split by && for multiple conditions
        cond_parts = [part.strip() for part in condition_str.split("&&")]

        for cond_part in cond_parts:
            # Try range condition first: "400 <= weight <= 700", "Regular <= weight <= Bold", "-100 <= weight <= 200"
            # Pattern accepts both numbers (with optional negative sign) and words (labels)
            range_match = re.search(r"([-\d.]+|\w+)\s*<=\s*(\w+)\s*<=\s*([-\d.]+|\w+)", cond_part)
            if range_match:
                min_str = range_match.group(1)
                axis = range_match.group(2)
                max_str = range_match.group(3)

                # Resolve values (can be numeric or labels)
                try:
                    min_val = self._resolve_condition_value(min_str, axis)
                    max_val = self._resolve_condition_value(max_str, axis)
                    conditions.append({"axis": axis, "minimum": min_val, "maximum": max_val})
                except ValueError as e:
                    self.validator.errors.append(f"Invalid condition value: {e}")
                    if self.validator.strict_mode:
                        raise
                continue

            # Standard conditions: "weight >= 480", "weight >= Bold", "weight <= 400", "weight == Regular"
            # Pattern accepts both numbers (with optional negative sign) and words (labels)
            std_match = re.search(r"(\w+)\s*(>=|<=|==)\s*([-\d.]+|\w+)", cond_part)
            if std_match:
                axis = std_match.group(1)
                operator = std_match.group(2)
                value_str = std_match.group(3)

                # Resolve value (can be numeric or label)
                try:
                    value = self._resolve_condition_value(value_str, axis)
                except ValueError as e:
                    self.validator.errors.append(f"Invalid condition value: {e}")
                    if self.validator.strict_mode:
                        raise
                    continue

                # Find axis bounds from document axes (design space)
                axis_min = -1000  # Default very low minimum
                axis_max = 1000  # Default very high maximum

                for doc_axis in self.document.axes:
                    if doc_axis.name == axis or doc_axis.tag == axis:
                        # Get design space bounds from mappings, not user space bounds
                        axis_min, axis_max = self._get_design_space_bounds(doc_axis)
                        break

                if operator == ">=":
                    conditions.append(
                        {
                            "axis": axis,
                            "minimum": value,
                            "maximum": axis_max,
                        }
                    )
                elif operator == "<=":
                    conditions.append(
                        {
                            "axis": axis,
                            "minimum": axis_min,
                            "maximum": value,
                        }
                    )
                elif operator == "==":
                    conditions.append({"axis": axis, "minimum": value, "maximum": value})

        return conditions

    def _get_design_space_bounds(self, axis: DSSAxis) -> tuple[float, float]:
        """Get design space bounds for axis from mappings"""
        if not axis.mappings:
            # No mappings, use user space bounds as fallback
            return axis.minimum, axis.maximum

        # Extract design space values from all mappings
        design_values = [mapping.design_value for mapping in axis.mappings]
        return min(design_values), max(design_values)

    def _tag_to_axis_name(self, tag: str) -> str:
        """Convert axis tag to actual axis name, matching existing axes in document"""
        # Standard tag mappings (reverse of TAG_TO_NAME)
        tag_mappings = {
            "wght": "weight",
            "wdth": "width",
            "ital": "italic",
            "slnt": "slant",
            "opsz": "optical",
        }

        # Convert to lowercase for lookup
        lower_tag = tag.lower()

        # First, try to find axis by its tag (most important for custom axes)
        for axis in self.document.axes:
            if hasattr(axis, "tag") and axis.tag and axis.tag.lower() == tag.lower():
                return axis.name

        # Second, try to find exact match in existing axes by name
        for axis in self.document.axes:
            if axis.name.lower() == lower_tag:
                return axis.name
            # Also check if tag matches the actual axis name (case-insensitive)
            if tag.lower() == axis.name.lower():
                return axis.name

        # If it's a standard tag, return the full name
        if lower_tag in tag_mappings:
            return tag_mappings[lower_tag]

        # If it's already a full name, check if it maps back to a standard tag
        for full_name in tag_mappings.values():
            if lower_tag == full_name:
                return full_name

        # Return original for custom axes
        return tag

    def _parse_rule_line(self, line: str):
        """Parse rule definition line with parentheses syntax: pattern > target (condition) "name" """
        # Strip leading whitespace for pattern matching
        line = line.strip()
        if ">" in line:
            # Validate rule syntax first
            is_valid, error_msg = DSSValidator.validate_rule_syntax(line)
            if not is_valid:
                self.validator.errors.append(f"Invalid rule syntax: {error_msg} in '{line}'")
                return

            # Parse parentheses syntax: pattern > target (condition) "name"
            paren_match = re.match(r'^(.+?)\s*>\s*(.+?)\s*\(([^)]+)\)(?:\s*"([^"]+)")?', line)

            if paren_match:
                from_part = paren_match.group(1).strip()
                to_part = paren_match.group(2).strip()
                condition_str = paren_match.group(3).strip()
                rule_name = paren_match.group(4) if paren_match.group(4) else None

                # Parse conditions
                conditions = self._parse_condition_string(condition_str)

                # Create rule with auto-generated name if needed
                if not rule_name:
                    rule_name = f"rule{len(self.document.rules) + 1}"

                # Create DSSRule
                # Check if it's a wildcard pattern or multi-glyph rule
                if "*" in from_part or (" " in from_part and len(from_part.split()) > 1):
                    # Wildcard or multi-glyph pattern
                    rule = DSSRule(
                        name=rule_name,
                        substitutions=[],  # Will be populated when converting to DesignSpace
                        conditions=conditions,
                        pattern=from_part,
                        to_pattern=to_part,
                    )
                else:
                    # Single substitution
                    rule = DSSRule(
                        name=rule_name,
                        substitutions=[
                            (from_part, from_part + to_part if to_part.startswith(".") else to_part)
                        ],
                        conditions=conditions,
                    )

                self.document.rules.append(rule)
                return
            else:
                # Invalid rule syntax
                DSSketchLogger.warning(f"Invalid rule syntax: {line}")
                DSSketchLogger.warning('Expected format: pattern > target (condition) "name"')
                return

    def _generate_auto_instances(self):
        """Generate instances automatically from axes mappings"""
        # Generate all meaningful combinations
        if not self.document.axes:
            return

        # For now, generate from axis mappings
        axis_values = {}
        for axis in self.document.axes:
            if axis.mappings:
                axis_values[axis.name] = [
                    (m.user_value, m.label, m.design_value) for m in axis.mappings
                ]

        # Generate combinations (simplified)
        if axis_values:
            # Generate a few key instances
            for axis_name, values in axis_values.items():
                for _, label, design_val in values:
                    if label in ["Regular", "Bold", "Light"]:
                        instance = DSSInstance(
                            name=label,
                            familyname=self.document.family,
                            stylename=label,
                            location={axis_name: design_val},
                        )
                        self.document.instances.append(instance)
