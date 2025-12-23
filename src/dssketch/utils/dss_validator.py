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

from ..core.mappings import Standards


class DSSValidationError(Exception):
    """Raised when DSS document has validation errors"""

    def __init__(self, message: str, critical: bool = False):
        super().__init__(message)
        self.critical = critical


class DSSValidator:
    """Comprehensive DSS document validator"""

    # Valid keywords for better error detection
    VALID_KEYWORDS = {"family", "suffix", "path", "axes", "sources", "instances", "rules"}

    # Maximum Levenshtein distance for typo suggestions (1-2 character edits)
    MAX_TYPO_DISTANCE = 2

    # Standard registered axis tags (OpenType spec)
    STANDARD_AXIS_TAGS = {
        'wght',  # Weight
        'wdth',  # Width
        'ital',  # Italic
        'slnt',  # Slant
        'opsz',  # Optical Size
    }

    # Mapping of human-readable names to tags
    AXIS_NAME_TO_TAG = {
        'weight': 'wght',
        'width': 'wdth',
        'italic': 'ital',
        'slant': 'slnt',
        'optical': 'opsz',
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
        # Preserve errors from parsing phase
        parsing_errors = self.errors.copy()
        parsing_warnings = self.warnings.copy()

        self.errors.clear()
        self.warnings.clear()

        # Structural validation (critical)
        self._validate_structure(document, parsing_errors)

        # Content validation (non-critical)
        self._validate_content(document)

        # Merge parsing errors/warnings with validation errors/warnings
        all_errors = parsing_errors + self.errors
        all_warnings = parsing_warnings + self.warnings

        # Check for critical errors (from both parsing and validation)
        critical_errors = [e for e in all_errors if e.startswith("CRITICAL:")]
        if critical_errors:
            error_msg = (
                "Critical structural errors prevent DesignSpace generation:\\n"
                + "\\n".join([f"  • {error[10:]}" for error in critical_errors])
            )  # Remove "CRITICAL: "
            raise DSSValidationError(error_msg, critical=True)

        return all_errors, all_warnings

    def _validate_structure(self, document: DSSDocument, parsing_errors: List[str] = None):
        """Validate critical document structure

        Args:
            document: DSS document to validate
            parsing_errors: Errors from parsing phase (to avoid duplicate error messages)
        """
        if parsing_errors is None:
            parsing_errors = []

        # Check family name
        if not document.family or not document.family.strip():
            self.errors.append(
                "CRITICAL: Missing or empty family name - required for valid DesignSpace"
            )

        # Check axes - CRITICAL
        if not document.axes:
            # Only add "No axes found" if there are no parsing errors about axes
            # (parsing errors would explain WHY axes are missing)
            has_axis_parsing_errors = any("axis range" in err.lower() for err in parsing_errors)
            if not has_axis_parsing_errors:
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

        # CRITICAL: Check for duplicate mapping labels across axes
        self._validate_duplicate_mapping_labels(document)

        # Validate axes content
        for axis in document.axes:
            if axis.mappings:
                for mapping in axis.mappings:
                    if mapping.user_value is None or mapping.design_value is None:
                        self.warnings.append(
                            f"Axis '{axis.name}' has incomplete mapping: {mapping.label}"
                        )

                    # Check that mapping user_value is within axis range
                    if mapping.user_value is not None:
                        if mapping.user_value < axis.minimum or mapping.user_value > axis.maximum:
                            self.errors.append(
                                f"Axis '{axis.name}': mapping '{mapping.label}' has user_value {mapping.user_value} "
                                f"which is outside the axis range [{axis.minimum}, {axis.maximum}]. "
                                f"All mappings must be within the axis min/max range."
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

        # Validate axis labels match standard weight/width names
        self._validate_axis_label_consistency(document)

    def _validate_duplicate_mapping_labels(self, document: DSSDocument):
        """
        Validate that mapping labels are unique across ALL axes.

        CRITICAL ERROR: Having the same label in different axes causes serious conflicts:
        - Instance generation: "Light" + "Light" = "Light Light"?
        - Label-based coordinates: [Light, ...] - which axis's "Light"?
        - Ambiguous font naming and style identification

        Examples of conflicts:
            axes
                wght 100:900
                    Light > 100
                wdth 75:125
                    Light > 75  # CONFLICT!
        """
        if not document.axes:
            return

        # Collect all labels from all axes with their source axis
        label_to_axes = {}  # {label: [(axis_name, axis_tag)]}

        for axis in document.axes:
            for mapping in axis.mappings:
                label = mapping.label
                # Skip empty labels - they are valid for pure numeric axis maps
                if not label:
                    continue
                if label not in label_to_axes:
                    label_to_axes[label] = []
                label_to_axes[label].append((axis.name, axis.tag))

        # Find and report duplicates
        for label, axes_info in label_to_axes.items():
            if len(axes_info) > 1:
                axes_names = [f"'{name}' ({tag})" for name, tag in axes_info]
                self.errors.append(
                    f"CRITICAL: Mapping label '{label}' is used in multiple axes: {', '.join(axes_names)}. "
                    f"Each mapping label must be unique across all axes to avoid conflicts in instance naming "
                    f"and label-based coordinates. Use different labels for each axis "
                    f"(e.g., 'LightWeight' and 'LightWidth', or 'Light' and 'Narrow')."
                )

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
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance (edit distance) between two strings.

        Returns the minimum number of single-character edits (insertions,
        deletions, or substitutions) required to change s1 into s2.

        Examples:
            levenshtein_distance("familly", "family") = 1  (delete one 'l')
            levenshtein_distance("axess", "axes") = 1      (delete one 's')
            levenshtein_distance("sourcse", "sources") = 2 (swap 's' and 'e')
        """
        if len(s1) < len(s2):
            return DSSValidator.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        # Create two rows for dynamic programming
        previous_row = range(len(s2) + 1)

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def validate_keyword(
        word: str, valid_keywords: Set[str], suggestions: dict = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a word might be a misspelled keyword using Levenshtein distance.

        Args:
            word: The word to check
            valid_keywords: Set of valid keywords
            suggestions: Deprecated, kept for backward compatibility (not used)

        Returns:
            Tuple of (is_valid, suggestion) where:
            - is_valid: True if word is valid or too far from any keyword
            - suggestion: Closest valid keyword if word is likely a typo, None otherwise

        Examples:
            validate_keyword("family", valid_keywords) -> (True, None)
            validate_keyword("familly", valid_keywords) -> (False, "family")
            validate_keyword("axess", valid_keywords) -> (False, "axes")
            validate_keyword("xyz", valid_keywords) -> (True, None)  # Too far from any keyword
        """
        word_lower = word.lower()

        # Exact match - valid keyword
        if word_lower in valid_keywords:
            return True, None

        # Find closest keyword using Levenshtein distance
        closest_keyword = None
        min_distance = float('inf')

        for keyword in valid_keywords:
            distance = DSSValidator.levenshtein_distance(word_lower, keyword)

            # Update if this is closer
            if distance < min_distance:
                min_distance = distance
                closest_keyword = keyword

        # If distance is within threshold, suggest the closest keyword
        if min_distance <= DSSValidator.MAX_TYPO_DISTANCE:
            return False, closest_keyword

        # Word is too far from any keyword - likely not a typo
        return True, None

    @staticmethod
    def validate_axis_tag(tag: str) -> Tuple[bool, Optional[str]]:
        """
        Check if axis tag might be a typo of a standard registered axis tag.

        Important distinction:
        - lowercase 4-char tags → check for typos (wgth → wght)
        - UPPERCASE 4+ char tags → assume custom axis (OK)

        Args:
            tag: The axis tag to check (e.g., 'wgth', 'wdht', 'CUSTOM')

        Returns:
            Tuple of (is_valid, suggestion) where:
            - is_valid: True if tag is valid or clearly custom
            - suggestion: Standard tag if typo detected, None otherwise

        Examples:
            validate_axis_tag('wght') → (True, None)       # Valid standard
            validate_axis_tag('wgth') → (False, 'wght')    # Typo
            validate_axis_tag('widht') → (False, 'wdth')   # Typo
            validate_axis_tag('CUSTOM') → (True, None)     # Custom axis
            validate_axis_tag('WGTH') → (True, None)       # Custom (uppercase)
        """
        # Exact match with standard tag - valid
        if tag.lower() in DSSValidator.STANDARD_AXIS_TAGS:
            return True, None

        # Check if it's a human-readable name that should be converted to tag
        if tag.lower() in DSSValidator.AXIS_NAME_TO_TAG:
            return False, DSSValidator.AXIS_NAME_TO_TAG[tag.lower()]

        # UPPERCASE tags are assumed to be custom axes - don't check for typos
        if tag.isupper() and len(tag) >= 4:
            return True, None

        # For lowercase 4-char tags, check for typos using Levenshtein
        if len(tag) == 4 and tag.islower():
            closest_tag = None
            min_distance = float('inf')

            # Check against standard tags
            for standard_tag in DSSValidator.STANDARD_AXIS_TAGS:
                distance = DSSValidator.levenshtein_distance(tag, standard_tag)
                if distance < min_distance:
                    min_distance = distance
                    closest_tag = standard_tag

            # If within threshold, likely a typo
            if min_distance <= DSSValidator.MAX_TYPO_DISTANCE:
                return False, closest_tag

        # Everything else is considered valid (custom axis)
        return True, None

    @staticmethod
    def get_valid_labels_for_axis(
        axis_tag: str,
        all_axes: List["DSSAxis"]
    ) -> Set[str]:
        """
        Get valid labels considering other axes in document (smart cross-axis logic).

        Logic:
        - If ONLY wght (no wdth) → weight + width labels allowed
        - If ONLY wdth (no wght) → width + weight labels allowed
        - If BOTH wght AND wdth → each uses only its own labels

        Args:
            axis_tag: Tag of the axis being validated ('wght', 'wdth', etc.)
            all_axes: List of all axes in the document

        Returns:
            Set of valid label names for this axis

        Examples:
            # Document with only wght:
            get_valid_labels_for_axis('wght', axes)
                → {'Thin', 'Light', 'Bold', 'Condensed', 'Wide', ...}

            # Document with both wght and wdth:
            get_valid_labels_for_axis('wght', axes)
                → {'Thin', 'Light', 'Bold', ...}  # only weight
            get_valid_labels_for_axis('wdth', axes)
                → {'Condensed', 'Wide', 'Normal', ...}  # only width
        """
        axis_tag_lower = axis_tag.lower()

        # Check what axes exist in document
        has_weight = any(a.tag in ['wght'] for a in all_axes)
        has_width = any(a.tag in ['wdth'] for a in all_axes)

        valid_labels = set()

        if axis_tag_lower in ['wght']:
            # Always include weight labels
            valid_labels.update(Standards.get_all_labels('weight'))

            # If no width axis exists, allow width labels too
            if not has_width:
                valid_labels.update(Standards.get_all_labels('width'))

        elif axis_tag_lower in ['wdth']:
            # Always include width labels
            valid_labels.update(Standards.get_all_labels('width'))

            # If no weight axis exists, allow weight labels too
            if not has_weight:
                valid_labels.update(Standards.get_all_labels('weight'))

        # For other axes (ital, slnt, opsz, custom), no standard labels
        return valid_labels

    @staticmethod
    def validate_mapping_label(
        label: str,
        axis_tag: str,
        all_axes: List["DSSAxis"]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if mapping label might be a typo using Levenshtein distance.

        Only validates for standard axes (wght, wdth).
        Uses smart cross-axis logic from get_valid_labels_for_axis().

        Args:
            label: The label to check (e.g., 'Reguler', 'Bol')
            axis_tag: Tag of the axis ('wght', 'wdth', etc.)
            all_axes: List of all axes in the document

        Returns:
            (is_valid, suggestion)

        Examples:
            validate_mapping_label('Regular', 'wght', axes) → (True, None)
            validate_mapping_label('Reguler', 'wght', axes) → (False, 'Regular')
            validate_mapping_label('MyCustom', 'wght', axes) → (True, None)
        """
        # Only validate for standard weight/width axes
        if axis_tag.lower() not in ['wght', 'wdth']:
            return True, None

        # Get valid labels for this axis (considering cross-axis logic)
        valid_labels = DSSValidator.get_valid_labels_for_axis(axis_tag, all_axes)

        if not valid_labels:
            return True, None

        # Exact match - valid
        if label in valid_labels:
            return True, None

        # Find closest match using Levenshtein
        closest_label = None
        min_distance = float('inf')

        for valid_label in valid_labels:
            distance = DSSValidator.levenshtein_distance(label.lower(), valid_label.lower())
            if distance < min_distance:
                min_distance = distance
                closest_label = valid_label

        # If within threshold, suggest correction
        if min_distance <= DSSValidator.MAX_TYPO_DISTANCE:
            return False, closest_label

        # Too far - assume custom label
        return True, None

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

                # Skip validation for axes without mappings - this is a valid pattern
                # (e.g., custom axes like ZROT that use numeric values directly)
                if not axis.mappings:
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

            # Only check for sources if mapping has a label (for instance generation)
            # Pure numeric axis maps (empty labels) don't require sources at extremes
            if not min_source_exists and min_mapping and min_mapping.label:
                self.errors.append(
                    f"Missing source for minimum mapping '{min_mapping.label}' "
                    f"at coordinate {min_design} on axis '{axis.name}'. "
                    f"Variable fonts require sources at extreme coordinates for proper interpolation."
                )

            if not max_source_exists and max_mapping and max_mapping.label:
                self.errors.append(
                    f"Missing source for maximum mapping '{max_mapping.label}' "
                    f"at coordinate {max_design} on axis '{axis.name}'. "
                    f"Variable fonts require sources at extreme coordinates for proper interpolation."
                )

    def _validate_axis_label_consistency(self, document: DSSDocument):
        """
        Validate that axis labels match standard weight/width names.

        Checks:
        1. For standard axes (wght, wdth): verify labels match expected standard names
        2. Verify that axis extremes (min/default/max) have corresponding mappings
        3. If user_value is explicitly specified and differs from standard - warn

        Important: Allows explicit user_value override (e.g., "200 Light > 122")
        but warns if it doesn't match the standard value for that label.
        """
        if not document.axes:
            return

        for axis in document.axes:
            # Only validate standard axes that have known mappings
            if axis.tag not in ['wght', 'wdth']:
                continue

            axis_type = 'weight' if axis.tag == 'wght' else 'width'

            if not axis.mappings:
                continue

            # Check 1: Verify axis extremes (min/default/max) have mappings
            self._check_axis_extremes_coverage(axis, axis_type)

            # Check 2: Validate label consistency with standard mappings
            for mapping in axis.mappings:
                self._check_mapping_label_consistency(mapping, axis, axis_type)

    def _check_axis_extremes_coverage(self, axis: "DSSAxis", axis_type: str):
        """
        Check that axis minimum, default, and maximum user_values have corresponding mappings.

        For example, if axis is declared as "wght 100:400:900", there should be mappings
        with user_value = 100, 400, and 900.
        """
        required_values = {
            'minimum': axis.minimum,
            'default': axis.default,
            'maximum': axis.maximum
        }

        # Get all user_values from mappings
        mapping_user_values = {m.user_value for m in axis.mappings if m.user_value is not None}

        for extreme_name, extreme_value in required_values.items():
            # Check if any mapping has this user_value (with tolerance for floating point)
            has_mapping = any(
                abs(user_val - extreme_value) < 0.1
                for user_val in mapping_user_values
            )

            if not has_mapping:
                # Find expected standard label for this value
                expected_label = Standards.get_name_by_user_space(extreme_value, axis_type)

                self.errors.append(
                    f"Axis '{axis.name}' ({extreme_name}={extreme_value}): missing mapping for {extreme_name} value. "
                    f"Expected mapping with user_value {extreme_value} "
                    f"(typically labeled '{expected_label}')."
                )

    def _check_mapping_label_consistency(self, mapping, axis: "DSSAxis", axis_type: str):
        """
        Check if mapping label is consistent with standard naming conventions.

        Handles two cases:
        1. Label with standard name but non-standard user_value (e.g., "200 Light > 122")
        2. User_value with standard value but non-standard label
        """
        label = mapping.label
        user_value = mapping.user_value

        if user_value is None:
            return

        # Check if label exists in standard mappings
        if Standards.has_mapping(label, axis_type):
            # Get expected user_value for this standard label
            expected_user_value = Standards.get_user_space_value(label, axis_type)

            # If user_value differs significantly from standard, warn about override
            if abs(user_value - expected_user_value) > 0.1:
                self.warnings.append(
                    f"Axis '{axis.name}': label '{label}' typically maps to user_value {expected_user_value}, "
                    f"but {user_value} is explicitly specified. "
                    f"This is allowed but may cause confusion. "
                    f"Consider using a custom label or the standard value."
                )

        # Check if user_value matches a standard value
        expected_label = Standards.get_name_by_user_space(user_value, axis_type)

        # Only warn if expected_label is a real standard name (not fallback like "Weight100")
        is_standard_name = not expected_label.startswith(axis_type.title())

        if is_standard_name and expected_label != label:
            # User_value matches a standard value but label is different
            self.warnings.append(
                f"Axis '{axis.name}': user_value {user_value} typically uses "
                f"label '{expected_label}', but '{label}' is specified. "
                f"Consider using the standard label for better consistency."
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

            if len(values) == 2 and values[0] >= values[1]:  # min:max
                return False, f"Minimum ({values[0]}) must be less than maximum ({values[1]})"
            elif len(values) == 3 and not (values[0] <= values[1] <= values[2]):  # min:default:max
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
        if paren_open > 0 and "," in line and "(" not in line.split("(")[0]:
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
