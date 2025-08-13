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


@dataclass
class DSSAxis:
    """Represents an axis in DSS format"""
    name: str
    tag: str
    minimum: float
    default: float
    maximum: float
    mappings: List[DSSAxisMapping] = field(default_factory=list)

    def get_design_value(self, user_value: float) -> float:
        """Convert user value to design value"""
        for mapping in self.mappings:
            if mapping.user_value == user_value:
                return mapping.design_value
        # Linear interpolation if not found
        return user_value


@dataclass
class DSSMaster:
    """Represents a master/source in DSS format"""
    name: str
    filename: str
    location: Dict[str, float]  # axis_name -> design_value
    is_base: bool = False
    copy_info: bool = False
    copy_lib: bool = False
    copy_groups: bool = False
    copy_features: bool = False


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
class DSSDocument:
    """Complete DSS document structure"""
    family: str
    suffix: str = ""
    path: str = ""  # Path to masters directory (relative to .dssketch file or absolute)
    axes: List[DSSAxis] = field(default_factory=list)
    masters: List[DSSMaster] = field(default_factory=list)
    instances: List[DSSInstance] = field(default_factory=list)
    rules: List[DSSRule] = field(default_factory=list)
    variable_fonts: List[Dict] = field(default_factory=list)
    lib: Dict = field(default_factory=dict)
    instances_auto: bool = False  # Flag for automatic instance generation

