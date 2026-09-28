"""
Data models for DSSketch

This module contains all dataclasses representing the DSSketch document structure.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DSSAxisMapping:
    """Represents a single axis mapping point"""
    user_value: float        # User space value (400)
    design_value: float      # Design space value (125)
    label: str              # Name (Regular)
    elidable: bool = False  # Whether this label can be elided in font names
    # True when the .dssketch source wrote the user value ("300 Light > 295").
    # False when it was inferred ("Light > 295" from the standards table,
    # "Custom > 500" as user = design) or when there is no source text (DS → DSS).
    user_value_explicit: bool = False


@dataclass
class DSSAxis:
    """Represents an axis in DSS format"""
    name: str
    tag: str
    minimum: float
    default: float
    maximum: float
    mappings: List[DSSAxisMapping] = field(default_factory=list)
    display_name: Optional[str] = None  # UI display name (e.g., "Optical size" for opsz)
    # Values of a discrete (non-interpolating) axis; None for a continuous axis.
    # Discreteness is stored, never guessed from the range or the axis name: a
    # custom discrete axis may have any number of values, and a continuous axis
    # may well span 0..1.
    values: Optional[List[float]] = None

    @property
    def is_discrete(self) -> bool:
        return self.values is not None

    def set_discrete_values(self, values: List[float]) -> None:
        """Make this a discrete axis over `values`, keeping min/default/max consistent"""
        self.values = sorted(set(values))
        if self.values:
            self.minimum, self.maximum = self.values[0], self.values[-1]
            if self.default not in self.values:
                self.default = self.values[0]

    def get_design_value(self, user_value: float) -> float:
        """Map a user-space value to design space through this axis's mappings.

        Piecewise linear between mapping points and shifted beyond the end ones,
        exactly like DesignSpace's axis map; identity for an axis without
        mappings. Written here rather than taken from fontTools so that the parse
        path does not import it.
        """
        return _piecewise_linear(
            user_value, [(m.user_value, m.design_value) for m in self.mappings]
        )

    def get_user_value(self, design_value: float) -> float:
        """Map a design-space value back to user space (inverse of get_design_value)"""
        return _piecewise_linear(
            design_value, [(m.design_value, m.user_value) for m in self.mappings]
        )

    @property
    def design_default(self) -> float:
        """The axis default in design space: where the default master sits"""
        return self.get_design_value(self.default)


def _piecewise_linear(value: float, points: List[Tuple[float, float]]) -> float:
    """Same result as fontTools.varLib.models.piecewiseLinearMap"""
    mapping = {x: y for x, y in points if x is not None and y is not None}
    if not mapping:
        return value
    if value in mapping:
        return mapping[value]
    lo, hi = min(mapping), max(mapping)
    if value < lo:
        return value + mapping[lo] - lo
    if value > hi:
        return value + mapping[hi] - hi
    below = max(k for k in mapping if k < value)
    above = min(k for k in mapping if k > value)
    return mapping[below] + (value - below) * (mapping[above] - mapping[below]) / (above - below)

@dataclass
class DSSSource:
    """Represents a source in DSS format"""
    name: str
    filename: str
    location: Dict[str, float]  # axis_name -> design_value
    is_base: bool = False
    is_sparse: bool = False  # Sparse master (correction layer with reduced glyph coverage)
    copy_info: bool = False
    copy_lib: bool = False
    copy_groups: bool = False
    copy_features: bool = False
    layer: Optional[str] = None  # UFO layer name (None = default layer)


@dataclass
class DSSInstance:
    """Represents an instance in DSS format"""
    name: str
    familyname: str
    stylename: str
    filename: Optional[str] = None
    location: Dict[str, float] = field(default_factory=dict)  # axis_name -> design_value


@dataclass
class DSSRule:
    """Represents a substitution rule"""
    name: str
    substitutions: List[Tuple[str, str]]  # (from_glyph, to_glyph)
    conditions: List[Dict[str, Any]]  # axis conditions
    pattern: Optional[str] = None  # wildcard pattern like "dollar* cent*"
    to_pattern: Optional[str] = None  # target pattern like ".rvrn"


@dataclass
class DSSAvar2Mapping:
    """Represents an avar2 mapping (inter-axis dependency)

    Example:
        [opsz=Display, wght=Bold] > XOUC=84, YTUC=$YTUC

    Attributes:
        name: Optional description/name for the mapping
        input: Dict of input axis conditions {axis_name: value}
        output: Dict of output axis values {axis_name: value}
    """
    name: Optional[str]
    input: Dict[str, float]  # axis_name -> input value
    output: Dict[str, float]  # axis_name -> output value


@dataclass
class DSSDocument:
    """Complete DSS document structure"""
    family: str
    suffix: str = ""
    # `lang de, ru`: languages to write derived names in (instance style names,
    # STAT labels, axis names), from data/font-resources-translations.json
    languages: List[str] = field(default_factory=list)
    path: str = ""  # Path to sources directory (relative to .dssketch file or absolute)
    axes: List[DSSAxis] = field(default_factory=list)
    hidden_axes: List[DSSAxis] = field(default_factory=list)  # avar2: hidden parametric axes
    sources: List[DSSSource] = field(default_factory=list)
    instances: List[DSSInstance] = field(default_factory=list)
    rules: List[DSSRule] = field(default_factory=list)
    variable_fonts: List[Dict] = field(default_factory=list)
    lib: Dict = field(default_factory=dict)
    instances_auto: bool = False  # Flag for automatic instance generation
    instances_off: bool = False  # Flag to disable instance generation entirely
    instances_skip: List[str] = field(default_factory=list)  # Instance combinations to skip (e.g., ["Bold Italic", "Light Italic"])
    # avar2 support
    avar2_vars: Dict[str, float] = field(default_factory=dict)  # Variable definitions: $name -> value
    avar2_vars_counts: Dict[str, int] = field(default_factory=dict)  # Variable frequency counts: $name -> count
    avar2_mappings: List[DSSAvar2Mapping] = field(default_factory=list)  # avar2 mappings

