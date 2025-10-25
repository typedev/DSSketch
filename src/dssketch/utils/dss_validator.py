"""
DSSketch Document Validator

Comprehensive validation for DSSketch documents including:
- Syntax validation (keywords, brackets, coordinates)
- Structural validation (required sections, critical elements)
- Content validation (axis ranges, rule syntax)
"""

import re
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from ..core.models import DSSAxis, DSSDocument, DSSSource
else:
    from ..core.models import DSSDocument


class DSSValidationError(Exception):
    """Raised when DSS document has validation errors"""

    def __init__(self, message: str, critical: bool = False):
        super().__init__(message)
        self.critical = critical


class DSSValidator:
    """Comprehensive DSS document validator"""

    # Valid keywords for better error detection
    VALID_KEYWORDS = {"family", "suffix", "path", "axes", "sources", "instances", "rules"}

    # Common typos for helpful error messages
    KEYWORD_SUGGESTIONS = {
        "familly": "family",
        "famile": "family",
        "familie": "family",
        "patth": "path",
        "pth": "path",
        "axess": "axes",
        "axis": "axes",
        "axees": "axes",
        "sourcse": "sources",
        "source": "sources",
        "sourcs": "sources",
        "instaces": "instances",
        "instance": "instances",
        "ruls": "rules",
        "rule": "rules",
    }

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_document(self, document: DSSDocument) -> Tuple[List[str], List[str]]:
        """
        Validate complete DSS document

        Returns:
            Tuple of (errors, warnings)

        Raises:
            DSSValidationError: If critical structural errors found
        """
        self.errors.clear()
        self.warnings.clear()

        # Structural validation (critical)
        self._validate_structure(document)

        # Content validation (non-critical)
        self._validate_content(document)

        # Check for critical errors
        critical_errors = [e for e in self.errors if e.startswith("CRITICAL:")]
        if critical_errors:
            error_msg = (
                "Critical structural errors prevent DesignSpace generation:\\n"
                + "\\n".join([f"  • {error[10:]}" for error in critical_errors])
            )  # Remove "CRITICAL: "
            raise DSSValidationError(error_msg, critical=True)

        return self.errors.copy(), self.warnings.copy()

    def _validate_structure(self, document: DSSDocument):
        """Validate critical document structure"""

        # Check family name
        if not document.family or not document.family.strip():
            self.errors.append(
                "CRITICAL: Missing or empty family name - required for valid DesignSpace"
            )

        # Check axes - CRITICAL
        if not document.axes:
            self.errors.append(
                "CRITICAL: No axes found - cannot generate valid DesignSpace without axes"
            )
        else:
            # Validate each axis has proper setup
            for i, axis in enumerate(document.axes):
                if not axis.name or not axis.tag:
                    self.errors.append(f"CRITICAL: Axis {i + 1} missing name or tag")
                if axis.minimum == axis.maximum:
                    self.errors.append(
                        f"CRITICAL: Axis '{axis.name}' has invalid range (min = max = {axis.minimum})"
                    )

        # Check sources - CRITICAL
        if not document.sources:
            self.errors.append(
                "CRITICAL: No sources found - cannot generate valid DesignSpace without sources"
            )
        else:
            # Check for base source and auto-detect if missing
            base_sources = [m for m in document.sources if m.is_base]
            if not base_sources:
                # Try to auto-detect default source based on design space coordinates
                auto_detected = self._find_default_source(document)
                if auto_detected:
                    # Mark the detected source as base
                    auto_detected.is_base = True
                    self.warnings.append(
                        f"Auto-detected base source: '{auto_detected.name}' (matches default coordinates)"
                    )
                else:
                    self.errors.append(
                        "CRITICAL: No base source found (@base flag missing) and cannot auto-detect from default coordinates"
                    )
            elif len(base_sources) > 1:
                # Check if multiple base sources are valid for discrete axes
                if self._validate_multiple_base_sources(base_sources, document):
                    # Valid configuration with discrete axes
                    pass
                else:
                    self.errors.append(
                        f"CRITICAL: Multiple base sources found ({len(base_sources)}) - only one @base source allowed"
                    )
            else:
                # Validate that the @base source has correct coordinates
                base_source = base_sources[0]
                expected_coords = self._get_default_coordinates(document)
                if expected_coords and not self._coordinates_match(
                    base_source.location, expected_coords, document.axes
                ):
                    self.errors.append(
                        f"CRITICAL: Base source '{base_source.name}' coordinates {list(base_source.location.values())} do not match default coordinates {list(expected_coords.values())}"
                    )

    def _validate_content(self, document: DSSDocument):
        """Validate document content (non-critical)"""

        # Validate axes content
        for axis in document.axes:
            if axis.mappings:
                for mapping in axis.mappings:
                    if mapping.user_value is None or mapping.design_value is None:
                        self.warnings.append(
                            f"Axis '{axis.name}' has incomplete mapping: {mapping.label}"
                        )
                        
                # Check for missing @elidable flags - important for instance naming
                elidable_count = sum(1 for mapping in axis.mappings if mapping.elidable)
                if elidable_count == 0:
                    self.warnings.append(
                        f"Axis '{axis.name}' has no @elidable mapping - this may cause issues with instance naming. "
                        f"Consider marking the default/regular style as @elidable"
                    )

        # Validate sources coordinates
        if document.axes and document.sources:
            expected_coords = len(document.axes)
            for source in document.sources:
                actual_coords = len(source.location) if source.location else 0
                if actual_coords != expected_coords:
                    self.warnings.append(
                        f"Source '{source.name}' has {actual_coords} coordinates, expected {expected_coords}"
                    )

        # Validate source coordinates match their corresponding mappings
        self._validate_source_coordinate_consistency(document)

        # Validate that minimum and maximum mappings have corresponding sources
        self._validate_extremes_coverage(document)

    @staticmethod
    def normalize_whitespace(line: str) -> str:
        """Normalize multiple spaces/tabs to single spaces"""
        if line.strip():
            # Get leading whitespace
            leading_ws = len(line) - len(line.lstrip())
            content = line.strip()
            # Normalize internal whitespace
            normalized_content = re.sub(r"\\s+", " ", content)
            return " " * leading_ws + normalized_content
        return line.strip()

    @staticmethod
    def validate_keyword(
        word: str, valid_keywords: Set[str], suggestions: dict
    ) -> Tuple[bool, Optional[str]]:
        """Check if a word might be a misspelled keyword"""
        if word.lower() in valid_keywords:
            return True, None

        # Check for common typos
        if word.lower() in suggestions:
            return False, suggestions[word.lower()]

        # Check for similar words (simple Levenshtein-like)
        for valid_keyword in valid_keywords:
            if DSSValidator._is_similar(word.lower(), valid_keyword):
                return False, valid_keyword

        return True, None  # Not a keyword (could be content)

    @staticmethod
    def _is_similar(word1: str, word2: str) -> bool:
        """Simple similarity check (character difference <= 2)"""
        if abs(len(word1) - len(word2)) > 2:
            return False

        # Count character differences
        diff_count = 0
        min_len = min(len(word1), len(word2))

        for i in range(min_len):
            if word1[i] != word2[i]:
                diff_count += 1
                if diff_count > 2:
                    return False

        diff_count += abs(len(word1) - len(word2))
        return diff_count <= 2

    def _find_default_source(self, document: "DSSDocument") -> Optional["DSSSource"]:
        """
        Find the source that should be the default based on design space coordinates.

        For DesignSpace 5.0 compatibility, the default source is the one whose coordinates
        match the default user space values mapped to design space coordinates.

        Returns:
            DSSSource or None if no suitable default source found
        """
        if not document.axes or not document.sources:
            return None

        # Get expected default coordinates for all axes
        expected_coords = self._get_default_coordinates(document)
        if not expected_coords:
            return None

        # Find source with matching coordinates
        for source in document.sources:
            if self._coordinates_match(source.location, expected_coords, document.axes):
                return source

        return None

    def _get_default_coordinates(self, document: DSSDocument) -> Optional[Dict[str, float]]:
        """
        Calculate the expected default coordinates based on axis defaults and mappings.

        For each axis:
        - For continuous axes: Use the design value that maps to the default user value
        - For discrete axes: Use the design value of the @elidable mapping

        Returns:
            Dict mapping axis names to expected default design coordinates
        """
        if not document.axes:
            return None

        default_coords = {}

        for axis in document.axes:
            # Check if this is a discrete axis (min=0, default=0, max=1)
            is_discrete = axis.minimum == 0 and axis.default == 0 and axis.maximum == 1

            if is_discrete:
                # For discrete axes, find the @elidable mapping
                elidable_mapping = next((m for m in axis.mappings if m.elidable), None)
                if elidable_mapping:
                    default_coords[axis.name] = elidable_mapping.design_value
                else:
                    # Fallback: use first mapping or axis default
                    if axis.mappings:
                        default_coords[axis.name] = axis.mappings[0].design_value
                    else:
                        default_coords[axis.name] = axis.default
            else:
                # For continuous axes, find mapping that matches default user value
                default_mapping = next(
                    (m for m in axis.mappings if m.user_value == axis.default), None
                )
                if default_mapping:
                    default_coords[axis.name] = default_mapping.design_value
                else:
                    # Fallback: use axis default directly (assumes 1:1 mapping)
                    default_coords[axis.name] = axis.default

        return default_coords

    def _coordinates_match(
        self,
        source_coords: Dict[str, float],
        expected_coords: Dict[str, float],
        axes: List["DSSAxis"],
    ) -> bool:
        """
        Check if source coordinates match expected default coordinates.

        Args:
            source_coords: Source's actual coordinates
            expected_coords: Expected default coordinates
            axes: List of axes for validation

        Returns:
            True if coordinates match within tolerance
        """
        if not source_coords or not expected_coords:
            return False

        # Check that we have coordinates for all axes
        for axis in axes:
            if axis.name not in source_coords or axis.name not in expected_coords:
                return False

            source_val = source_coords[axis.name]
            expected_val = expected_coords[axis.name]

            # Use small tolerance for floating point comparison
            if abs(source_val - expected_val) > 0.01:
                return False

        return True

    def _validate_multiple_base_sources(self, base_sources: List, document: DSSDocument) -> bool:
        """
        Validate multiple base sources for discrete axes configurations.

        Multiple base sources are valid when:
        1. There are discrete axes in the design space
        2. Each base source is at the default coordinate of different discrete axis values
        3. All base sources share the same continuous axis coordinates

        Args:
            base_sources: List of sources with @base flag
            document: DSS document being validated

        Returns:
            True if multiple base sources configuration is valid
        """
        if not document.axes or len(base_sources) < 2:
            return False
            
        # Find discrete axes (those with min=0, default=0, max=1)
        discrete_axes = []
        continuous_axes = []
        
        for axis in document.axes:
            is_discrete = axis.minimum == 0 and axis.default == 0 and axis.maximum == 1
            if is_discrete:
                discrete_axes.append(axis)
            else:
                continuous_axes.append(axis)
                
        # Must have at least one discrete axis for multiple base sources
        if not discrete_axes:
            return False

        # Extract coordinates for each base source
        source_coords = []
        for source in base_sources:
            if not source.location:
                return False
            source_coords.append(source.location)

        # Check that all base sources have the same continuous axis coordinates
        if continuous_axes:
            first_continuous_coords = {axis.name: source_coords[0].get(axis.name)
                                     for axis in continuous_axes}

            for coords in source_coords[1:]:
                current_continuous_coords = {axis.name: coords.get(axis.name)
                                           for axis in continuous_axes}

                # Check if continuous coordinates match within tolerance
                for axis_name, expected_val in first_continuous_coords.items():
                    actual_val = current_continuous_coords.get(axis_name)
                    if expected_val is None or actual_val is None:
                        return False
                    if abs(expected_val - actual_val) > 0.01:
                        return False

        # Check that each base source corresponds to a different discrete axis value
        discrete_values_used = set()

        for source in base_sources:
            for axis in discrete_axes:
                if axis.name in source.location:
                    discrete_val = source.location[axis.name]
                    
                    # Find corresponding mapping for this discrete value
                    matching_mapping = None
                    for mapping in axis.mappings:
                        if self._coordinates_equal(mapping.design_value, discrete_val):
                            matching_mapping = mapping
                            break
                            
                    if not matching_mapping:
                        return False
                        
                    # Check if this discrete value was already used
                    discrete_key = (axis.name, discrete_val)
                    if discrete_key in discrete_values_used:
                        return False
                    discrete_values_used.add(discrete_key)
                    
        return True

    def _validate_source_coordinate_consistency(self, document: DSSDocument):
        """
        Validate that each source has corresponding axis mappings with matching coordinates.

        Logic: For each source, check that there exists a mapping in each axis
        with design_value matching the source's coordinate for that axis.
        Only checks sources that exist - mappings without sources are allowed (interpolation).
        """
        if not document.axes or not document.sources:
            return

        for source in document.sources:
            for axis in document.axes:
                if axis.name not in source.location:
                    continue

                source_coord = source.location[axis.name]

                # Find mapping with matching design value
                matching_mapping = None
                for mapping in axis.mappings:
                    if self._coordinates_equal(mapping.design_value, source_coord):
                        matching_mapping = mapping
                        break

                if not matching_mapping:
                    # Find closest mapping for helpful error message
                    closest_mapping = min(
                        axis.mappings,
                        key=lambda m: abs(m.design_value - source_coord),
                        default=None,
                    )

                    if closest_mapping:
                        self.errors.append(
                            f"Source '{source.name}' coordinate {source_coord} on axis '{axis.name}' "
                            f"has no matching mapping. Closest mapping '{closest_mapping.label}' "
                            f"is at {closest_mapping.design_value}"
                        )
                    else:
                        self.errors.append(
                            f"Source '{source.name}' coordinate {source_coord} on axis '{axis.name}' "
                            f"has no corresponding mapping"
                        )
    
    def _validate_extremes_coverage(self, document: DSSDocument):
        """
        Validate that minimum and maximum mappings have corresponding sources.

        For proper interpolation space coverage, there should be sources at the
        minimum and maximum design space coordinates for each axis.
        """
        if not document.axes or not document.sources:
            return

        for axis in document.axes:
            if not axis.mappings:
                continue

            # Find minimum and maximum design space coordinates
            design_values = [mapping.design_value for mapping in axis.mappings]
            min_design = min(design_values)
            max_design = max(design_values)

            # Find corresponding mappings for extremes
            min_mapping = next((m for m in axis.mappings if self._coordinates_equal(m.design_value, min_design)), None)
            max_mapping = next((m for m in axis.mappings if self._coordinates_equal(m.design_value, max_design)), None)

            # Check if sources exist for these extremes
            min_source_exists = any(
                axis.name in source.location and self._coordinates_equal(source.location[axis.name], min_design)
                for source in document.sources
            )
            max_source_exists = any(
                axis.name in source.location and self._coordinates_equal(source.location[axis.name], max_design)
                for source in document.sources
            )

            if not min_source_exists and min_mapping:
                self.errors.append(
                    f"Missing source for minimum mapping '{min_mapping.label}' "
                    f"at coordinate {min_design} on axis '{axis.name}'. "
                    f"Variable fonts require sources at extreme coordinates for proper interpolation."
                )

            if not max_source_exists and max_mapping:
                self.errors.append(
                    f"Missing source for maximum mapping '{max_mapping.label}' "
                    f"at coordinate {max_design} on axis '{axis.name}'. "
                    f"Variable fonts require sources at extreme coordinates for proper interpolation."
                )

    def _coordinates_equal(self, val1: float, val2: float) -> bool:
        """
        Check if two coordinate values are equal, considering that:
        - 394.0 == 394 (integer equality)
        - 394.1 != 394 (different values)
        """
        # Convert to integers if they are whole numbers for comparison
        int1 = int(val1) if val1 == int(val1) else val1
        int2 = int(val2) if val2 == int(val2) else val2

        return int1 == int2

    @staticmethod
    def validate_coordinates(coords_str: str) -> Tuple[bool, str]:
        """Validate coordinate string format"""
        if not coords_str.strip():
            return False, "Empty coordinates"

        # Remove brackets if present
        coords_str = coords_str.strip("[]{}()")

        if not coords_str:
            return False, "Empty coordinate values"

        # Split by comma and validate each value
        try:
            coords = [x.strip() for x in coords_str.split(",")]
            for coord in coords:
                if not coord:
                    return False, "Empty coordinate value"
                float(coord)  # This will raise ValueError if invalid
            return True, ""
        except ValueError as e:
            return False, f"Invalid coordinate value: {str(e)}"

    @staticmethod
    def validate_axis_range(range_str: str) -> Tuple[bool, str]:
        """Validate axis range format"""
        if range_str.lower() in ["discrete", "binary"]:
            return True, ""

        if ":" not in range_str:
            # Single value
            try:
                float(range_str)
                return True, ""
            except ValueError:
                return False, f"Invalid single axis value: {range_str}"

        # Range format: min:default:max or min:max
        parts = range_str.split(":")
        if len(parts) < 2 or len(parts) > 3:
            return False, f"Invalid range format: {range_str}. Expected min:max or min:default:max"

        try:
            values = [float(part) for part in parts if part.strip()]
            if len(values) != len(parts):
                return False, "Empty values in range"

            if len(values) == 2:  # min:max
                if values[0] >= values[1]:
                    return False, f"Minimum ({values[0]}) must be less than maximum ({values[1]})"
            elif len(values) == 3:  # min:default:max
                if not (values[0] <= values[1] <= values[2]):
                    return (
                        False,
                        f"Range values must be ordered: min <= default <= max ({values[0]} <= {values[1]} <= {values[2]})",
                    )

            return True, ""
        except ValueError:
            return False, f"Non-numeric values in range: {range_str}"

    @staticmethod
    def validate_rule_syntax(rule_line: str) -> Tuple[bool, str]:
        """Validate rule syntax"""
        if ">" not in rule_line:
            return False, "Rule missing '>' separator"

        # Check for condition parentheses
        if "(" in rule_line and ")" not in rule_line:
            return False, "Unclosed parentheses in rule condition"
        if ")" in rule_line and "(" not in rule_line:
            return False, "Closing parentheses without opening in rule condition"

        # Find the main '>' separator (not inside parentheses)
        paren_depth = 0
        quote_depth = 0
        separator_pos = -1

        for i, char in enumerate(rule_line):
            if char == '"':
                quote_depth = 1 - quote_depth
            elif quote_depth == 0:  # Only process when not in quotes
                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth -= 1
                elif char == ">" and paren_depth == 0:
                    if separator_pos == -1:
                        separator_pos = i
                    else:
                        # Multiple separators at same level
                        return False, "Multiple '>' separators found"

        if separator_pos == -1:
            return False, "No valid '>' separator found"

        from_part = rule_line[:separator_pos].strip()
        to_part = rule_line[separator_pos + 1 :].strip()

        if not from_part:
            return False, "Rule missing source pattern"
        if not to_part.split("(")[0].strip():  # Remove condition part for check
            return False, "Rule missing target pattern"

        return True, ""

    @staticmethod
    def detect_bracket_mismatch(line: str) -> Optional[str]:
        """Detect mixed or mismatched bracket types"""
        # Count different bracket types
        square_open = line.count("[")
        square_close = line.count("]")
        paren_open = line.count("(")
        paren_close = line.count(")")
        curly_open = line.count("{")
        curly_close = line.count("}")

        issues = []

        # Check for coordinates with wrong bracket types
        # Look for patterns like "name (x, y)" or "name {x, y}" which should be "name [x, y]"
        if paren_open > 0 and "," in line:
            if "(" not in line.split("(")[0]:
                # Likely coordinate with wrong brackets
                issues.append("Use [] for coordinates, not ()")
        if curly_open > 0 and "," in line:
            # Likely coordinate with wrong brackets
            issues.append("Use [] for coordinates, not {}")

        # Check for mixed bracket types in coordinates (should use [])
        if square_open > 0 and (paren_open > 0 or curly_open > 0):
            issues.append("Mixed bracket types detected. Use [] for coordinates")

        # Check for mismatched brackets
        if square_open != square_close:
            issues.append(f"Mismatched square brackets: {square_open} open, {square_close} close")
        if paren_open != paren_close:
            issues.append(f"Mismatched parentheses: {paren_open} open, {paren_close} close")
        if curly_open != curly_close:
            issues.append(f"Mismatched curly brackets: {curly_open} open, {curly_close} close")

        return "; ".join(issues) if issues else None

    @staticmethod
    def is_likely_section_typo(word: str) -> bool:
        """Check if word is likely a typo of a section keyword (e.g., contains non-ASCII)"""
        # Check for non-ASCII characters (like Cyrillic 'ш' in 'axшes')
        try:
            word.encode("ascii")
        except UnicodeEncodeError:
            return True

        # Check for very similar words to valid keywords
        for keyword in DSSValidator.VALID_KEYWORDS:
            if len(word) == len(keyword):
                # Count character differences
                diff_count = sum(1 for a, b in zip(word.lower(), keyword.lower()) if a != b)
                if diff_count == 1:  # Only one character different
                    return True

        return False
