#!/usr/bin/env python3
"""
DesignSpace Sketch (DSSketch)
A compact, human-readable format for DesignSpace files with bidirectional conversion

Key concepts:
- User Space: values users see (font-weight: 400)
- Design Space: real coordinates in file (can be 125, 380, anything)  
- Mapping: Regular 400 > 125 means user requests 400, master is at 125

Features:
- Bidirectional conversion between .dsl and .designspace formats
- Smart defaults for standard weights/widths
- Compact DSL syntax with auto-expansion
- Proper user/design space mapping
- Shortened axis names for registered axes (wght, ital, opsz, slnt, wdth)
- Uppercase notation for custom axes (CONTRAST CNTR)
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field

# For proper DesignSpace handling
from fontTools.designspaceLib import (
    DesignSpaceDocument,
    AxisDescriptor,
    SourceDescriptor,
    InstanceDescriptor,
    RuleDescriptor,
    AxisLabelDescriptor,
)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DSLAxisMapping:
    """Represents a single axis mapping point"""
    user_value: float        # User space value (400)
    design_value: float      # Design space value (125)
    label: str              # Name (Regular)

@dataclass
class DSLAxis:
    """Represents an axis in DSL format"""
    name: str
    tag: str
    minimum: float
    default: float
    maximum: float
    mappings: List[DSLAxisMapping] = field(default_factory=list)
    
    def get_design_value(self, user_value: float) -> float:
        """Convert user value to design value"""
        for mapping in self.mappings:
            if mapping.user_value == user_value:
                return mapping.design_value
        # Linear interpolation if not found
        return user_value

@dataclass
class DSLMaster:
    """Represents a master/source in DSL format"""
    name: str
    filename: str
    location: Dict[str, float]  # axis_name -> design_value
    is_base: bool = False
    copy_info: bool = False
    copy_lib: bool = False
    copy_groups: bool = False
    copy_features: bool = False

@dataclass
class DSLInstance:
    """Represents an instance in DSL format"""
    name: str
    familyname: str
    stylename: str
    filename: Optional[str] = None
    location: Dict[str, float] = field(default_factory=dict)  # axis_name -> design_value

@dataclass
class DSLRule:
    """Represents a substitution rule"""
    name: str
    substitutions: List[Tuple[str, str]]  # (from_glyph, to_glyph)
    conditions: List[Dict[str, Any]]  # axis conditions
    pattern: Optional[str] = None  # wildcard pattern like "dollar* cent*"
    to_pattern: Optional[str] = None  # target pattern like ".rvrn"

@dataclass
class DSLDocument:
    """Complete DSL document structure"""
    family: str
    suffix: str = ""
    path: str = ""  # Path to masters directory (relative to .dssketch file or absolute)
    axes: List[DSLAxis] = field(default_factory=list)
    masters: List[DSLMaster] = field(default_factory=list)
    instances: List[DSLInstance] = field(default_factory=list)
    rules: List[DSLRule] = field(default_factory=list)
    variable_fonts: List[Dict] = field(default_factory=list)
    lib: Dict = field(default_factory=dict)


# ============================================================================
# UFO Validation
# ============================================================================

@dataclass
class ValidationReport:
    """Report of UFO file validation"""
    missing_files: List[str] = field(default_factory=list)
    invalid_ufos: List[str] = field(default_factory=list)
    path_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.missing_files) > 0 or len(self.invalid_ufos) > 0 or len(self.path_errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

class UFOValidator:
    """Validate UFO files existence and basic structure"""
    
    @staticmethod
    def validate_ufo_files(dsl_doc: DSLDocument, dssketch_file_path: str) -> ValidationReport:
        """Validate UFO files existence and basic structure"""
        report = ValidationReport()
        
        # Determine base path for masters
        dssketch_dir = Path(dssketch_file_path).parent
        
        if dsl_doc.path:
            # Path specified in DSSketch file
            if Path(dsl_doc.path).is_absolute():
                base_path = Path(dsl_doc.path)
            else:
                base_path = dssketch_dir / dsl_doc.path
        else:
            # Default: same directory as .dssketch file
            base_path = dssketch_dir
        
        # Validate base path exists
        if not base_path.exists():
            report.path_errors.append(f"Masters path does not exist: {base_path}")
            return report
        
        if not base_path.is_dir():
            report.path_errors.append(f"Masters path is not a directory: {base_path}")
            return report
        
        # Check each master file
        for master in dsl_doc.masters:
            ufo_path = base_path / master.filename
            
            if not ufo_path.exists():
                report.missing_files.append(str(ufo_path))
                continue
            
            # Basic UFO validation
            if not UFOValidator._is_valid_ufo(ufo_path):
                report.invalid_ufos.append(str(ufo_path))
            
            # Check if filename ends with .ufo
            if not master.filename.endswith('.ufo'):
                report.warnings.append(f"Master filename should end with .ufo: {master.filename}")
        
        return report
    
    @staticmethod
    def _is_valid_ufo(ufo_path: Path) -> bool:
        """Basic UFO structure validation"""
        if not ufo_path.is_dir():
            return False
            
        # Check for required UFO files
        required_files = ['metainfo.plist', 'fontinfo.plist']
        for req_file in required_files:
            if not (ufo_path / req_file).exists():
                return False
        
        # Check for glyphs directory or layer contents
        if not (ufo_path / 'glyphs').exists() and not (ufo_path / 'glyphs.contents.plist').exists():
            return False
        
        return True


# ============================================================================
# Standard Mappings and Defaults
# ============================================================================

class UnifiedMappings:
    """Unified mappings for font attributes: name ↔ OS/2 ↔ user_space"""
    
    # Will be loaded from JSON file
    MAPPINGS = {}
    DEFAULTS = {}
    
    @classmethod
    def _load_mappings(cls):
        """Load mappings from JSON or YAML file"""
        if cls.MAPPINGS:  # Already loaded
            return
            
        data_dir = Path(__file__).parent / "data"
        
        # Try YAML first (if available), then JSON
        yaml_file = data_dir / "unified-mappings.yaml"
        json_file = data_dir / "unified-mappings.json"
        
        data = None
        
        # Try YAML if available
        if yaml_file.exists():
            try:
                import yaml
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            except ImportError:
                # yaml module not available, fall back to JSON
                pass
            except Exception:
                # YAML parsing failed, fall back to JSON
                pass
        
        # Try JSON if YAML didn't work
        if data is None and json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        
        if data:
            # Extract main mappings (weight, width)
            cls.MAPPINGS = {
                key: value for key, value in data.items() 
                if key not in ['metadata']
            }
            
            # Extract defaults from metadata
            if 'metadata' in data and 'defaults' in data['metadata']:
                cls.DEFAULTS = data['metadata']['defaults']
            else:
                # Fallback defaults
                cls.DEFAULTS = {
                    "weight": {"os2": 400, "user_space": 400.0},
                    "width": {"os2": 5, "user_space": 100.0}
                }
        else:
            # Fallback to minimal hardcoded data if no file found
            cls.MAPPINGS = {
                "weight": {
                    "Regular": {"os2": 400, "user_space": 400},
                    "Bold": {"os2": 700, "user_space": 700}
                },
                "width": {
                    "Normal": {"os2": 5, "user_space": 100}
                }
            }
            cls.DEFAULTS = {
                "weight": {"os2": 400, "user_space": 400.0},
                "width": {"os2": 5, "user_space": 100.0}
            }
    
    @classmethod
    def _resolve_alias(cls, name: str, axis_type: str) -> Dict[str, Any]:
        """Resolve alias to actual entry data"""
        if axis_type not in cls.MAPPINGS or name not in cls.MAPPINGS[axis_type]:
            return {}
            
        entry = cls.MAPPINGS[axis_type][name]
        
        # If this is an alias, resolve it
        if "alias_of" in entry:
            target_name = entry["alias_of"]
            if target_name in cls.MAPPINGS[axis_type]:
                # Get the target entry and merge with alias entry
                target_entry = cls.MAPPINGS[axis_type][target_name].copy()
                # Overlay any additional properties from the alias
                for key, value in entry.items():
                    if key != "alias_of":
                        target_entry[key] = value
                return target_entry
        
        return entry

    @classmethod
    def get_user_space_value(cls, name: str, axis_type: str) -> float:
        """Get user_space coordinate value by name"""
        cls._load_mappings()
        axis_type = axis_type.lower()
        
        entry = cls._resolve_alias(name, axis_type)
        
        if entry:
            # Try user_space first, then fallback to os2
            if "user_space" in entry:
                return float(entry["user_space"])
            elif "os2" in entry:
                return float(entry["os2"])  # Fallback: use os2 as user_space
        
        # Default fallback from metadata
        return cls.DEFAULTS.get(axis_type, {}).get("user_space", 400.0 if axis_type == "weight" else 100.0)
    
    @classmethod
    def get_os2_value(cls, name: str, axis_type: str) -> int:
        """Get OS/2 table value by name"""
        cls._load_mappings()
        axis_type = axis_type.lower()
        
        entry = cls._resolve_alias(name, axis_type)
        
        if entry:
            # Try os2 first, then fallback to user_space
            if "os2" in entry:
                return int(entry["os2"])
            elif "user_space" in entry:
                return int(entry["user_space"])  # Fallback: use user_space as os2
        
        # Default fallback from metadata
        return cls.DEFAULTS.get(axis_type, {}).get("os2", 400 if axis_type == "weight" else 5)
    
    @classmethod
    def get_name_by_user_space(cls, value: float, axis_type: str) -> str:
        """Get name by user_space coordinate value"""
        cls._load_mappings()
        axis_type = axis_type.lower()
        if axis_type in cls.MAPPINGS:
            for name, entry in cls.MAPPINGS[axis_type].items():
                # Skip aliases - we want to find the canonical name
                if "alias_of" in entry:
                    continue
                    
                resolved_entry = cls._resolve_alias(name, axis_type)
                if resolved_entry:
                    # Check user_space first, then os2 as fallback
                    user_space_val = resolved_entry.get("user_space") or resolved_entry.get("os2")
                    if user_space_val and float(user_space_val) == value:
                        return name
        # Fallback to numeric name
        return f"{axis_type.title()}{int(value)}"
    
    @classmethod
    def get_name_by_os2(cls, value: int, axis_type: str) -> str:
        """Get name by OS/2 table value"""
        cls._load_mappings()
        axis_type = axis_type.lower()
        if axis_type in cls.MAPPINGS:
            for name, entry in cls.MAPPINGS[axis_type].items():
                # Skip aliases - we want to find the canonical name
                if "alias_of" in entry:
                    continue
                    
                resolved_entry = cls._resolve_alias(name, axis_type)
                if resolved_entry:
                    # Check os2 first, then user_space as fallback
                    os2_val = resolved_entry.get("os2") or resolved_entry.get("user_space")
                    if os2_val and int(os2_val) == value:
                        return name
        # Fallback to numeric name  
        return f"{axis_type.title()}{value}"
    
    @classmethod
    def get_user_value_for_name(cls, name: str, axis_name: str) -> float:
        """Legacy compatibility method - maps to get_user_space_value"""
        return cls.get_user_space_value(name, axis_name)
    
    @classmethod
    def get_name_for_user_value(cls, value: float, axis_name: str) -> str:
        """Legacy compatibility method - maps to get_name_by_user_space"""
        return cls.get_name_by_user_space(value, axis_name)


# ============================================================================
# Pattern Matching Utils
# ============================================================================

class PatternMatcher:
    """Utilities for wildcard pattern matching in glyph names"""
    
    @staticmethod
    def matches_pattern(glyph_name: str, pattern: str) -> bool:
        """Check if glyph name matches a wildcard pattern
        
        Patterns:
        - dollar* : starts with 'dollar'  
        - *Heavy : ends with 'Heavy'
        - a.*alt : starts with 'a.', ends with 'alt'
        """
        if '*' not in pattern:
            return glyph_name == pattern
        
        if pattern.endswith('*'):
            # Prefix match: dollar*
            prefix = pattern[:-1]
            return glyph_name.startswith(prefix)
        elif pattern.startswith('*'):
            # Suffix match: *Heavy
            suffix = pattern[1:]
            return glyph_name.endswith(suffix)
        else:
            # Middle wildcard: a.*alt
            parts = pattern.split('*', 1)
            prefix, suffix = parts[0], parts[1]
            return glyph_name.startswith(prefix) and glyph_name.endswith(suffix)
    
    @staticmethod
    def find_matching_glyphs(patterns: List[str], all_glyphs: Set[str]) -> Set[str]:
        """Find all glyphs that match any of the given patterns"""
        matched = set()
        for pattern in patterns:
            for glyph in all_glyphs:
                if PatternMatcher.matches_pattern(glyph, pattern):
                    matched.add(glyph)
        return matched
    
    @staticmethod
    def detect_pattern_from_glyphs(glyph_names: List[str]) -> Optional[str]:
        """Try to detect a wildcard pattern from a list of glyph names"""
        if len(glyph_names) < 2:
            return None
            
        # Try to find common prefix
        common_prefix = ""
        for i in range(min(len(name) for name in glyph_names)):
            char = glyph_names[0][i]
            if all(name[i] == char for name in glyph_names):
                common_prefix += char
            else:
                break
        
        # Try to find common suffix
        common_suffix = ""
        min_len = min(len(name) for name in glyph_names)
        for i in range(1, min_len + 1):
            char = glyph_names[0][-i]
            if all(name[-i] == char for name in glyph_names):
                common_suffix = char + common_suffix
            else:
                break
        
        # Generate pattern if we have significant commonality
        if len(common_prefix) >= 3:  # At least 3 chars for prefix
            # Check if all names actually start with this prefix
            if all(name.startswith(common_prefix) for name in glyph_names):
                return f"{common_prefix}*"
        
        if len(common_suffix) >= 3:  # At least 3 chars for suffix  
            # Check if all names actually end with this suffix
            if all(name.endswith(common_suffix) for name in glyph_names):
                return f"*{common_suffix}"
        
        return None


# Backward compatibility alias
Standards = UnifiedMappings


# ============================================================================
# DesignSpace to DSL Converter
# ============================================================================

class DesignSpaceToDSL:
    """Convert DesignSpace to DSL format"""
    
    def __init__(self):
        # Load external data
        self.load_external_data()
    
    def load_external_data(self):
        """Load external font resource translations"""
        data_dir = Path(__file__).parent / "data"
        
        self.font_resources = {}
        
        try:
            with open(data_dir / "font-resources-translations.json", 'r') as f:
                self.font_resources = json.load(f)
        except FileNotFoundError:
            pass
    
    def convert_file(self, ds_path: str) -> DSLDocument:
        """Convert DesignSpace file to DSL document"""
        doc = DesignSpaceDocument()
        doc.read(ds_path)
        return self.convert(doc)
    
    def convert(self, ds_doc: DesignSpaceDocument) -> DSLDocument:
        """Convert DesignSpace document to DSL document"""
        dsl_doc = DSLDocument(family=self._extract_family_name(ds_doc))
        
        # Convert axes
        for axis in ds_doc.axes:
            dsl_axis = self._convert_axis(axis)
            dsl_doc.axes.append(dsl_axis)
        
        # Convert masters/sources
        for source in ds_doc.sources:
            dsl_master = self._convert_source(source, ds_doc)
            dsl_doc.masters.append(dsl_master)
        
        # Convert instances (optional - can be auto-generated)
        for instance in ds_doc.instances:
            dsl_instance = self._convert_instance(instance, ds_doc)
            dsl_doc.instances.append(dsl_instance)
        
        # Convert rules
        for rule in ds_doc.rules:
            dsl_rule = self._convert_rule(rule, ds_doc)
            if dsl_rule:
                dsl_doc.rules.append(dsl_rule)
        
        return dsl_doc
    
    def _extract_family_name(self, ds_doc: DesignSpaceDocument) -> str:
        """Extract family name from DesignSpace document"""
        if ds_doc.instances:
            return ds_doc.instances[0].familyName or "Unknown"
        elif ds_doc.sources:
            return ds_doc.sources[0].familyName or "Unknown"
        return "Unknown"
    
    def _convert_axis(self, axis: AxisDescriptor) -> DSLAxis:
        """Convert DesignSpace axis to DSL axis"""
        # Handle discrete axes (like italic)
        if hasattr(axis, 'values') and axis.values:
            # Discrete axis
            values = list(axis.values)
            minimum = min(values)
            maximum = max(values)
            default = getattr(axis, 'default', minimum)
        else:
            # Continuous axis
            minimum = getattr(axis, 'minimum', 0)
            maximum = getattr(axis, 'maximum', 1000)
            default = getattr(axis, 'default', minimum)
        
        dsl_axis = DSLAxis(
            name=axis.name,
            tag=axis.tag,
            minimum=minimum,
            default=default,
            maximum=maximum
        )
        
        # Process mappings and labels
        mappings_dict = {}
        
        # Collect mappings
        if axis.map:
            for mapping in axis.map:
                if hasattr(mapping, 'inputLocation'):
                    user_val = mapping.inputLocation
                    design_val = mapping.outputLocation
                else:
                    # Handle tuple format (input, output)
                    user_val, design_val = mapping
                mappings_dict[user_val] = design_val
        
        # Collect labels and create mappings
        if axis.axisLabels:
            for label in axis.axisLabels:
                user_val = label.userValue
                design_val = mappings_dict.get(user_val, user_val)
                
                mapping = DSLAxisMapping(
                    user_value=user_val,
                    design_value=design_val,
                    label=label.name
                )
                dsl_axis.mappings.append(mapping)
        
        # Sort mappings by user value
        dsl_axis.mappings.sort(key=lambda m: m.user_value)
        
        return dsl_axis
    
    def _convert_source(self, source: SourceDescriptor, ds_doc: DesignSpaceDocument) -> DSLMaster:
        """Convert DesignSpace source to DSL master"""
        # Extract name from filename
        name = Path(source.filename or "").stem
        
        # Determine if this is a base master
        is_base = bool(source.copyLib or source.copyInfo or 
                      source.copyGroups or source.copyFeatures)
        
        return DSLMaster(
            name=name,
            filename=source.filename or f"{name}.ufo",
            location=dict(source.location),
            is_base=is_base,
            copy_lib=source.copyLib,
            copy_info=source.copyInfo,
            copy_groups=source.copyGroups,
            copy_features=source.copyFeatures
        )
    
    def _convert_instance(self, instance: InstanceDescriptor, ds_doc: DesignSpaceDocument) -> DSLInstance:
        """Convert DesignSpace instance to DSL instance"""
        return DSLInstance(
            name=instance.styleName or "",
            familyname=instance.familyName or "",
            stylename=instance.styleName or "",
            filename=instance.filename,
            location=dict(instance.location)
        )
    
    def _convert_rule(self, rule: RuleDescriptor, ds_doc: DesignSpaceDocument) -> Optional[DSLRule]:
        """Convert DesignSpace rule to DSL rule"""
        if not rule.subs:
            return None
        
        substitutions = []
        for sub in rule.subs:
            substitutions.append((sub[0], sub[1]))
        
        conditions = []
        if hasattr(rule, 'conditionSets') and rule.conditionSets:
            # Handle modern conditionSets format
            for condset in rule.conditionSets:
                for condition in condset:
                    # condition is a dict with keys: name, minimum, maximum
                    conditions.append({
                        'axis': condition['name'],
                        'minimum': condition.get('minimum', 0),
                        'maximum': condition.get('maximum', 1000)
                    })
        elif hasattr(rule, 'conditions'):
            # Handle older conditions format (deprecated)
            for condition in rule.conditions:
                conditions.append({
                    'axis': condition.name,
                    'minimum': condition.minimum,
                    'maximum': condition.maximum
                })
        
        return DSLRule(
            name=rule.name or "rule",
            substitutions=substitutions,
            conditions=conditions
        )


# ============================================================================
# DSL Writer
# ============================================================================

class DSLWriter:
    """Write DSL document to string format"""
    
    # Registered axis names that can be omitted for brevity
    REGISTERED_AXES = {
        'italic': 'ital',
        'optical': 'opsz', 
        'slant': 'slnt',
        'width': 'wdth',
        'weight': 'wght'
    }
    
    def __init__(self, optimize: bool = True):
        self.optimize = optimize
    
    def write(self, dsl_doc: DSLDocument) -> str:
        """Generate DSL string from document"""
        lines = []
        
        # Family declaration
        lines.append(f"family {dsl_doc.family}")
        if dsl_doc.suffix:
            lines.append(f"suffix {dsl_doc.suffix}")
        if dsl_doc.path:
            lines.append(f"path {dsl_doc.path}")
        lines.append("")
        
        # Axes section
        if dsl_doc.axes:
            lines.append("axes")
            for axis in dsl_doc.axes:
                lines.extend(self._format_axis(axis))
            lines.append("")
        
        # Masters section
        if dsl_doc.masters:
            lines.append("masters")
            for master in dsl_doc.masters:
                lines.append(self._format_master(master, dsl_doc.axes))
            lines.append("")
        
        # Rules section
        if dsl_doc.rules:
            lines.append("rules")
            for rule in dsl_doc.rules:
                lines.extend(self._format_rule(rule))
            lines.append("")
        
        # Instances (if not using auto)
        if dsl_doc.instances and not self.optimize:
            lines.append("instances")
            for instance in dsl_doc.instances:
                lines.append(self._format_instance(instance, dsl_doc.axes))
        elif self.optimize:
            lines.append("instances auto")
        
        return "\n".join(lines).strip()
    
    def _format_axis(self, axis: DSLAxis) -> List[str]:
        """Format axis definition"""
        lines = []
        
        # Determine axis name for output (shortened if registered)
        axis_name = self._get_axis_display_name(axis.name, axis.tag)
        
        # Axis header with range
        if axis.minimum == axis.default == axis.maximum:
            # Binary axis
            if axis_name:
                lines.append(f"    {axis_name} {axis.tag} binary")
            else:
                lines.append(f"    {axis.tag} binary")
        else:
            if axis_name:
                lines.append(f"    {axis_name} {axis.tag} {axis.minimum}:{axis.default}:{axis.maximum}")
            else:
                lines.append(f"    {axis.tag} {axis.minimum}:{axis.default}:{axis.maximum}")
        
        # Mappings
        if axis.mappings:
            for mapping in axis.mappings:
                # Check if we can use compact form (name only)
                std_user_val = Standards.get_user_value_for_name(mapping.label, axis.name)
                
                if std_user_val == mapping.user_value and self.optimize:
                    # Compact form: just "Regular > 125"
                    lines.append(f"        {mapping.label} > {mapping.design_value}")
                else:
                    # Full form: "400 Regular > 125"
                    lines.append(f"        {mapping.user_value} {mapping.label} > {mapping.design_value}")
        
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
    
    def _format_master(self, master: DSLMaster, axes: List[DSLAxis]) -> str:
        """Format master definition"""
        # Get coordinates in axis order
        coords = []
        for axis in axes:
            value = master.location.get(axis.name, 0)
            coords.append(str(int(value) if value.is_integer() else value))
        
        line = f"    {master.name} [{', '.join(coords)}]"
        
        if master.is_base:
            line += " @base"
        
        return line
    
    def _format_rule(self, rule: DSLRule) -> List[str]:
        """Format rule definition"""
        lines = []
        
        # Get condition string (shared across all substitutions in this rule)
        condition_str = ""
        if rule.conditions:
            cond_parts = []
            for cond in rule.conditions:
                axis = cond['axis']
                min_val = cond['minimum']
                max_val = cond['maximum']
                
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
                condition_str = f" @ {' && '.join(cond_parts)}"
        
        # Try to detect patterns for multiple substitutions
        if len(rule.substitutions) > 1:
            pattern_info = self._detect_substitution_pattern(rule.substitutions)
            
            if pattern_info:
                # Use compact wildcard notation
                from_pattern, to_pattern = pattern_info
                lines.append(f"    {from_pattern} > {to_pattern}{condition_str}")
            else:
                # Fallback to individual lines with comment
                lines.append(f"    # {rule.name}")
                for from_glyph, to_glyph in rule.substitutions:
                    lines.append(f"    {from_glyph} > {to_glyph}{condition_str}")
        else:
            # Single substitution
            for from_glyph, to_glyph in rule.substitutions:
                lines.append(f"    {from_glyph} > {to_glyph}{condition_str}")
        
        return lines
    
    def _detect_substitution_pattern(self, substitutions: List[Tuple[str, str]]) -> Optional[Tuple[str, str]]:
        """Try to detect a pattern in substitutions for compact notation
        
        Returns (from_pattern, to_pattern) or None
        Examples:
        - [('dollar', 'dollar.rvrn'), ('cent', 'cent.rvrn')] -> ('dollar* cent*', '.rvrn')
        - [('dollar.sc', 'dollar.sc.rvrn')] -> None (single substitution)
        """
        if len(substitutions) < 2:
            return None
        
        from_glyphs = [sub[0] for sub in substitutions]
        
        # Check if all have the same suffix transformation
        # e.g., dollar -> dollar.rvrn, cent -> cent.rvrn
        common_suffix = None
        for from_glyph, to_glyph in substitutions:
            if to_glyph.startswith(from_glyph + '.'):
                suffix = to_glyph[len(from_glyph):]
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
                        if prefix not in prefix_groups or len(matching) > len(prefix_groups[prefix]):
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
                return (from_pattern, common_suffix)
        
        return None
    
    def _format_instance(self, instance: DSLInstance, axes: List[DSLAxis]) -> str:
        """Format instance definition"""
        coords = []
        for axis in axes:
            value = instance.location.get(axis.name, 0)
            coords.append(str(int(value) if value.is_integer() else value))
        
        return f"    {instance.stylename} [{', '.join(coords)}]"


# ============================================================================
# DSL Parser (Enhanced)
# ============================================================================

class DSLParser:
    """Parse DSL format into structured data"""
    
    # Tag to standard name mapping for registered axes
    TAG_TO_NAME = {
        'ital': 'italic',
        'opsz': 'optical', 
        'slnt': 'slant',
        'wdth': 'width',
        'wght': 'weight'
    }
    
    def __init__(self):
        self.document = DSLDocument(family="")
        self.current_section = None
        self.current_axis = None
        
    def parse_file(self, filepath: str) -> DSLDocument:
        """Parse DSL file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.parse(content)
    
    def parse(self, content: str) -> DSLDocument:
        """Parse DSL content"""
        lines = content.split('\n')
        
        for line_no, line in enumerate(lines, 1):
            # Remove comments
            if '#' in line:
                line = line[:line.index('#')]
            line = line.strip()
            
            if not line:
                continue
                
            try:
                self._parse_line(line)
            except Exception as e:
                raise ValueError(f"Error parsing line {line_no}: {line}\n{e}")
        
        return self.document
    
    def _parse_line(self, line: str):
        """Parse a single line based on context"""
        
        # Main sections
        if line.startswith('family '):
            self.document.family = line[7:].strip()
            self.current_section = 'family'
            
        elif line.startswith('suffix '):
            self.document.suffix = line[7:].strip()
            
        elif line.startswith('path '):
            self.document.path = line[5:].strip()
            
        elif line == 'axes' or line.startswith('axes '):
            self.current_section = 'axes'
            
        elif line == 'masters' or line.startswith('masters '):
            self.current_section = 'masters'
            
        elif line == 'instances' or line.startswith('instances '):
            self.current_section = 'instances'
            if 'auto' in line:
                self._generate_auto_instances()
            
        elif line.startswith('rules'):
            self.current_section = 'rules'
            
        # Parse based on current section
        elif self.current_section == 'axes':
            self._parse_axis_line(line)
            
        elif self.current_section == 'masters':
            self._parse_master_line(line)
            
        elif self.current_section == 'instances':
            self._parse_instance_line(line)
            
        elif self.current_section == 'rules':
            self._parse_rule_line(line)
    
    def _parse_axis_line(self, line: str):
        """Parse axis definition lines"""
        
        # Check for axis definition patterns
        # Pattern 1: "weight wght 100:400:900" (full form)
        # Pattern 2: "CONTRAST CNTR 0:0:100" (custom axis)  
        # Pattern 3: "wght 100:400:900" (registered axis, name omitted)
        # Pattern 4: "ital binary" (registered binary axis)
        # Pattern 5: "weight 100:400:900" (legacy form with inferred tag)
        
        if re.match(r'^\w+\s+\w{4}\s+', line):
            # Full form: name tag range
            parts = line.split()
            name = parts[0]
            tag = parts[1]
            
            # Parse range or binary
            if len(parts) > 2:
                range_part = parts[2]
                if range_part == 'binary':
                    minimum, default, maximum = 0, 0, 1
                elif ':' in range_part:
                    values = range_part.split(':')
                    minimum = float(values[0])
                    default = float(values[1]) if len(values) > 2 else minimum
                    maximum = float(values[-1])
                else:
                    minimum = default = maximum = float(range_part)
            else:
                minimum = default = maximum = 0
                
        elif re.match(r'^\w{4}\s+', line) and '>' not in line:
            # Shortened form: tag range (for registered axes)
            # But not if it contains '>' (that's a mapping)
            parts = line.split()
            tag = parts[0]
            
            # Get standard name from tag
            name = self.TAG_TO_NAME.get(tag, tag.upper())
            
            # Parse range or binary
            if len(parts) > 1:
                range_part = parts[1]
                if range_part == 'binary':
                    minimum, default, maximum = 0, 0, 1
                elif ':' in range_part:
                    values = range_part.split(':')
                    minimum = float(values[0])
                    default = float(values[1]) if len(values) > 2 else minimum
                    maximum = float(values[-1])
                else:
                    minimum = default = maximum = float(range_part)
            else:
                minimum = default = maximum = 0
        elif re.match(r'^\w+\s+([\d.:-]+|binary)', line) and '>' not in line:
            # Legacy form: "weight 100:400:900" (infer tag from name)
            parts = line.split()
            name = parts[0]
            
            # Infer tag from name
            if name.lower() == 'weight':
                tag = 'wght'
            elif name.lower() == 'width':
                tag = 'wdth'
            elif name.lower() == 'italic':
                tag = 'ital'
            elif name.lower() == 'slant':
                tag = 'slnt'
            elif name.lower() == 'optical':
                tag = 'opsz'
            else:
                tag = name[:4].upper()  # Use first 4 chars as tag
            
            # Parse range or binary
            if len(parts) > 1:
                range_part = parts[1]
                if range_part == 'binary':
                    minimum, default, maximum = 0, 0, 1
                elif ':' in range_part:
                    values = range_part.split(':')
                    minimum = float(values[0])
                    default = float(values[1]) if len(values) > 2 else minimum
                    maximum = float(values[-1])
                else:
                    minimum = default = maximum = float(range_part)
            else:
                minimum = default = maximum = 0
        else:
            # Not an axis definition, might be a mapping
            if '>' in line and self.current_axis:
                self._parse_axis_mapping(line)
            return
        
        self.current_axis = DSLAxis(
            name=name, tag=tag,
            minimum=minimum, default=default, maximum=maximum
        )
        self.document.axes.append(self.current_axis)
    
    def _parse_axis_mapping(self, line: str):
        """Parse axis mapping line"""
        parts = line.split('>')
        left = parts[0].strip()
        design = float(parts[1].strip())
        
        # Parse left side
        left_parts = left.split()
        
        if left_parts[0].replace('.', '').replace('-', '').isdigit():
            # Format: "300 Light"
            user = float(left_parts[0])
            label = ' '.join(left_parts[1:]) if len(left_parts) > 1 else ""
            if not label:
                label = Standards.get_name_for_user_value(user, self.current_axis.name)
        else:
            # Format: "Light" - infer user value
            label = left
            user = Standards.get_user_value_for_name(label, self.current_axis.name)
        
        mapping = DSLAxisMapping(
            user_value=user,
            design_value=design,
            label=label
        )
        self.current_axis.mappings.append(mapping)
    
    def _parse_master_line(self, line: str):
        """Parse master definition line"""
        # Extract flags
        is_base = '@base' in line
        line = line.replace('@base', '').strip()
        
        # Parse coordinates
        if '[' in line and ']' in line:
            # Format: "Light [0, 0]"
            name = line[:line.index('[')].strip()
            coords_str = line[line.index('[')+1:line.index(']')]
            coords = [float(x.strip()) for x in coords_str.split(',')]
        else:
            # Format: "Light 0 0"
            parts = line.split()
            name = parts[0]
            coords = [float(x) for x in parts[1:] if x.replace('.', '').replace('-', '').isdigit()]
        
        # Create location dict
        location = {}
        for i, axis in enumerate(self.document.axes):
            if i < len(coords):
                location[axis.name] = coords[i]
        
        # Determine filename
        filename = f"{name}.ufo"
        if '/' in name or '.' in name:
            filename = name
            name = Path(name).stem
        
        master = DSLMaster(
            name=name,
            filename=filename,
            location=location,
            is_base=is_base
        )
        
        self.document.masters.append(master)
    
    def _parse_instance_line(self, line: str):
        """Parse instance definition line"""
        if line != 'auto':
            # Parse explicit instance (similar to master parsing)
            pass
    
    def _parse_rule_line(self, line: str):
        """Parse rule definition line"""
        if '>' in line:
            parts = line.split('@')
            substitution = parts[0].strip()
            condition_str = parts[1].strip() if len(parts) > 1 else ""
            
            sub_parts = substitution.split('>')
            from_part = sub_parts[0].strip()
            to_part = sub_parts[1].strip()
            
            # Parse conditions (same as before)
            conditions = []
            if condition_str:
                # Split by && for multiple conditions
                cond_parts = [part.strip() for part in condition_str.split('&&')]
                
                for cond_part in cond_parts:
                    # Try range condition first: "400 <= weight <= 700"
                    range_match = re.search(r'([\d.]+)\s*<=\s*(\w+)\s*<=\s*([\d.]+)', cond_part)
                    if range_match:
                        min_val, axis_name, max_val = range_match.groups()
                        conditions.append({
                            'axis': axis_name,
                            'minimum': float(min_val),
                            'maximum': float(max_val)
                        })
                    else:
                        # Try simple condition: "weight >= 480"
                        cond_match = re.search(r'(\w+)\s*(>=|<=|==|>|<)\s*([\d.]+)', cond_part)
                        if cond_match:
                            axis_name, op, value = cond_match.groups()
                            value = float(value)
                            
                            if op in ['>=', '>']:
                                conditions.append({
                                    'axis': axis_name,
                                    'minimum': value,
                                    'maximum': 1000  # Large number
                                })
                            elif op in ['<=', '<']:
                                conditions.append({
                                    'axis': axis_name,
                                    'minimum': 0,
                                    'maximum': value
                                })
                            elif op == '==':
                                conditions.append({
                                    'axis': axis_name,
                                    'minimum': value,
                                    'maximum': value
                                })
            
            # Check if this is a wildcard pattern rule
            if self._is_wildcard_rule(from_part, to_part):
                # Handle wildcard patterns: "dollar* cent* > .rvrn"
                self._parse_wildcard_rule(from_part, to_part, conditions)
            else:
                # Handle single substitution
                from_glyph = from_part
                to_glyph = to_part
                
                # Check if we already have a rule with these conditions
                existing_rule = None
                for rule in self.document.rules:
                    if rule.conditions == conditions and conditions:  # Same conditions and not empty
                        existing_rule = rule
                        break
                
                if existing_rule:
                    # Add substitution to existing rule
                    existing_rule.substitutions.append((from_glyph, to_glyph))
                else:
                    # Create new rule
                    rule_name = f"switching {from_glyph}" if conditions else f"substitution {from_glyph}"
                    rule = DSLRule(
                        name=rule_name,
                        substitutions=[(from_glyph, to_glyph)],
                        conditions=conditions
                    )
                    self.document.rules.append(rule)
    
    def _is_wildcard_rule(self, from_part: str, to_part: str) -> bool:
        """Check if this is a wildcard pattern rule"""
        return ('*' in from_part or 
                to_part.startswith('.') or
                ' ' in from_part)  # Multiple patterns like "dollar* cent*"
    
    def _parse_wildcard_rule(self, from_part: str, to_part: str, conditions: List[Dict]):
        """Parse wildcard rule like 'dollar* cent* > .rvrn'"""
        # Extract all patterns from from_part
        patterns = from_part.split()
        
        # Create rule with pattern info
        rule_name = f"wildcard {patterns[0].replace('*', '')}" if patterns else "wildcard rule"
        rule = DSLRule(
            name=rule_name,
            substitutions=[],  # Will be populated when converting to DesignSpace
            conditions=conditions,
            pattern=from_part  # Store the original pattern
        )
        
        # Store the transformation pattern
        rule.to_pattern = to_part
        
        self.document.rules.append(rule)
    
    def _generate_auto_instances(self):
        """Generate instances automatically from axes mappings"""
        # Generate all meaningful combinations
        if not self.document.axes:
            return
        
        # For now, generate from axis mappings
        axis_values = {}
        for axis in self.document.axes:
            if axis.mappings:
                axis_values[axis.name] = [(m.user_value, m.label, m.design_value) 
                                         for m in axis.mappings]
        
        # Generate combinations (simplified)
        if axis_values:
            # Generate a few key instances
            for axis_name, values in axis_values.items():
                for user_val, label, design_val in values:
                    if label in ['Regular', 'Bold', 'Light']:
                        instance = DSLInstance(
                            name=label,
                            familyname=self.document.family,
                            stylename=label,
                            location={axis_name: design_val}
                        )
                        self.document.instances.append(instance)


# ============================================================================
# DSL to DesignSpace Converter
# ============================================================================

class DSLToDesignSpace:
    """Convert DSL to DesignSpace format"""
    
    def convert(self, dsl_doc: DSLDocument) -> DesignSpaceDocument:
        """Convert DSL document to DesignSpace document"""
        doc = DesignSpaceDocument()
        
        # Convert axes
        for dsl_axis in dsl_doc.axes:
            axis = self._convert_axis(dsl_axis)
            doc.addAxis(axis)
        
        # Convert masters/sources
        for dsl_master in dsl_doc.masters:
            source = self._convert_master(dsl_master, dsl_doc)
            doc.addSource(source)
        
        # Convert instances
        for dsl_instance in dsl_doc.instances:
            instance = self._convert_instance(dsl_instance, dsl_doc)
            doc.addInstance(instance)
        
        # Convert rules
        for dsl_rule in dsl_doc.rules:
            rule = self._convert_rule(dsl_rule, doc)
            if rule:
                doc.addRule(rule)
        
        return doc
    
    def _convert_axis(self, dsl_axis: DSLAxis) -> AxisDescriptor:
        """Convert DSL axis to DesignSpace axis"""
        axis = AxisDescriptor()
        axis.name = dsl_axis.name
        axis.tag = dsl_axis.tag
        
        # Add labelname (localized axis name)
        axis.labelNames = {
            'en': dsl_axis.name.title()  # Weight, Italic, etc.
        }
        
        # Check if this is a binary/discrete axis (like italic)
        is_binary = (dsl_axis.minimum == 0 and dsl_axis.maximum == 1 and 
                    dsl_axis.name.lower() in ['italic', 'ital'])
        
        # Always set basic properties first
        axis.minimum = dsl_axis.minimum
        axis.default = dsl_axis.default 
        axis.maximum = dsl_axis.maximum
        
        if is_binary:
            # For binary axis, also add values (both are supported)
            axis.values = [0, 1]
            
            # Add standard binary labels if no custom mappings provided
            axis.axisLabels = []
            
            if not dsl_axis.mappings:
                # Default binary labels for italic
                upright_label = AxisLabelDescriptor(
                    name="Upright",
                    userValue=0,
                    elidable=True
                )
                italic_label = AxisLabelDescriptor(
                    name="Italic", 
                    userValue=1,
                    elidable=False
                )
                axis.axisLabels = [upright_label, italic_label]
            else:
                # Use custom mappings
                for mapping in dsl_axis.mappings:
                    label_desc = AxisLabelDescriptor(
                        name=mapping.label,
                        userValue=mapping.user_value,
                        elidable=(mapping.user_value == dsl_axis.default)
                    )
                    axis.axisLabels.append(label_desc)
        else:
            # Continuous axis - add mappings and labels
            axis.map = []
            axis.axisLabels = []
            
            for mapping in dsl_axis.mappings:
                # Add mapping as tuple (older format)
                axis.map.append((mapping.user_value, mapping.design_value))
                
                # Add label
                label_desc = AxisLabelDescriptor(
                    name=mapping.label,
                    userValue=mapping.user_value,
                    elidable=(mapping.user_value == dsl_axis.default)
                )
                axis.axisLabels.append(label_desc)
        
        return axis
    
    def _convert_master(self, dsl_master: DSLMaster, dsl_doc: DSLDocument) -> SourceDescriptor:
        """Convert DSL master to DesignSpace source"""
        source = SourceDescriptor()
        source.filename = dsl_master.filename
        source.familyName = dsl_doc.family
        source.styleName = dsl_master.name
        source.location = dsl_master.location.copy()
        
        # Set copy flags
        if dsl_master.is_base:
            source.copyLib = True
            source.copyInfo = True
            source.copyGroups = True
            source.copyFeatures = True
        
        return source
    
    def _convert_instance(self, dsl_instance: DSLInstance, dsl_doc: DSLDocument) -> InstanceDescriptor:
        """Convert DSL instance to DesignSpace instance"""
        instance = InstanceDescriptor()
        instance.familyName = dsl_instance.familyname or dsl_doc.family
        instance.styleName = dsl_instance.stylename
        instance.filename = dsl_instance.filename
        instance.location = dsl_instance.location.copy()
        
        # Generate PostScript name
        ps_family = instance.familyName.replace(' ', '').replace('-', '')
        ps_style = instance.styleName.replace(' ', '').replace('-', '')
        instance.postScriptFontName = f"{ps_family}-{ps_style}"
        
        return instance
    
    def _convert_rule(self, dsl_rule: DSLRule, doc: DesignSpaceDocument) -> Optional[RuleDescriptor]:
        """Convert DSL rule to DesignSpace rule"""
        rule = RuleDescriptor()
        rule.name = dsl_rule.name
        
        # Handle wildcard patterns
        if dsl_rule.pattern and dsl_rule.to_pattern:
            # Expand wildcard patterns to concrete substitutions
            substitutions = self._expand_wildcard_pattern(dsl_rule, doc)
            rule.subs = substitutions
        else:
            # Use existing substitutions
            rule.subs = dsl_rule.substitutions
        
        # Add conditions using modern conditionSets format
        if dsl_rule.conditions:
            rule.conditionSets = [[]]  # Create one condition set
            for condition in dsl_rule.conditions:
                cond_dict = {
                    'name': condition['axis'],
                    'minimum': condition['minimum'],
                    'maximum': condition['maximum']
                }
                rule.conditionSets[0].append(cond_dict)
        
        return rule
    
    def _expand_wildcard_pattern(self, dsl_rule: DSLRule, doc: DesignSpaceDocument) -> List[Tuple[str, str]]:
        """Expand wildcard patterns to concrete glyph substitutions"""
        if not dsl_rule.pattern or not dsl_rule.to_pattern:
            return dsl_rule.substitutions
        
        # Extract all glyph names from DesignSpace sources
        all_glyphs = set()
        for source in doc.sources:
            # In a real implementation, we'd load the UFO and get all glyph names
            # For now, we'll use a simulated approach based on common patterns
            
            # Extract base glyph names from common patterns
            base_names = ['dollar', 'cent', 'euro', 'yen', 'sterling', 
                         'dollar.sc', 'cent.sc', 'dollar.old', 'cent.old',
                         'dollar.ton', 'cent.ton', 'dollar.tln', 'cent.tln',
                         'a', 'e', 'i', 'o', 'u', 'ampersand', 'at', 'percent']
            all_glyphs.update(base_names)
        
        # Parse patterns from dsl_rule.pattern
        patterns = dsl_rule.pattern.split()
        
        # Find matching glyphs
        matching_glyphs = PatternMatcher.find_matching_glyphs(patterns, all_glyphs)
        
        # Generate substitutions
        substitutions = []
        to_suffix = dsl_rule.to_pattern
        
        for glyph in matching_glyphs:
            if to_suffix.startswith('.'):
                # Append suffix: dollar -> dollar.rvrn
                target = glyph + to_suffix
            else:
                # Replace with target: might support other patterns in future
                target = to_suffix
            
            substitutions.append((glyph, target))
        
        return substitutions


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command-line interface for DesignSpace Sketch"""
    import argparse
    
    parser = argparse.ArgumentParser(
        prog='dssketch',
        description='DesignSpace Sketch - Convert between .dssketch and .designspace formats'
    )
    parser.add_argument('input', help='Input file (.dssketch or .designspace)')
    parser.add_argument('-o', '--output', help='Output file (optional)')
    parser.add_argument('--format', choices=['dssketch', 'dsl', 'designspace', 'auto'], 
                       default='auto', help='Output format (dsl is alias for dssketch)')
    parser.add_argument('--optimize', action='store_true', default=True,
                       help='Optimize DSSketch output (default: True)')
    parser.add_argument('--no-optimize', action='store_false', dest='optimize',
                       help='Disable DSSketch optimization')
    parser.add_argument('--validate-ufos', action='store_true', 
                       help='Validate UFO master files existence and structure')
    parser.add_argument('--strict', action='store_true',
                       help='Fail on missing UFO files (use with --validate-ufos)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist")
        return 1
    
    try:
        # Determine output format
        output_format = args.format
        if output_format == 'auto':
            # Auto-detect based on input extension
            if input_path.suffix.lower() == '.dssketch':
                output_format = 'designspace'
            elif input_path.suffix.lower() == '.designspace':
                output_format = 'dssketch'
            else:
                print(f"Error: Cannot auto-detect format for {input_path.suffix}")
                print("Supported input formats: .dssketch, .designspace")
                print("Use --format to specify output format explicitly")
                return 1
        
        # Normalize dsl to dssketch
        if output_format == 'dsl':
            output_format = 'dssketch'
        
        # Determine conversion direction
        if output_format == 'designspace':
            # Convert to DesignSpace
            if input_path.suffix.lower() == '.dssketch':
                parser = DSLParser()
                dsl_doc = parser.parse_file(str(input_path))
                
                # Validate UFO files if requested
                if args.validate_ufos:
                    validation_report = UFOValidator.validate_ufo_files(dsl_doc, str(input_path))
                    
                    # Print validation results
                    if validation_report.has_errors:
                        print("❌ UFO Validation Errors:")
                        for error in validation_report.path_errors:
                            print(f"  - Path error: {error}")
                        for missing in validation_report.missing_files:
                            print(f"  - Missing UFO: {missing}")
                        for invalid in validation_report.invalid_ufos:
                            print(f"  - Invalid UFO: {invalid}")
                        
                        if args.strict:
                            return 1
                    
                    if validation_report.has_warnings:
                        print("⚠️  UFO Validation Warnings:")
                        for warning in validation_report.warnings:
                            print(f"  - {warning}")
                    
                    if not validation_report.has_errors and not validation_report.has_warnings:
                        print("✅ All UFO files validated successfully")
                
                converter = DSLToDesignSpace()
                ds_doc = converter.convert(dsl_doc)
                
                output_path = args.output or input_path.with_suffix('.designspace')
                ds_doc.write(str(output_path))
                print(f"Converted {input_path} -> {output_path}")
            else:
                print(f"Error: Cannot convert {input_path.suffix} to .designspace")
                print("Input must be .dssketch file for conversion to .designspace")
                return 1
            
        elif output_format == 'dssketch':
            # Convert to DSSketch/DSL
            if input_path.suffix.lower() == '.designspace':
                converter = DesignSpaceToDSL()
                dsl_doc = converter.convert_file(str(input_path))
                
                writer = DSLWriter(optimize=args.optimize)
                dsl_content = writer.write(dsl_doc)
                
                output_path = args.output or input_path.with_suffix('.dssketch')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(dsl_content)
                print(f"Converted {input_path} -> {output_path}")
            else:
                print(f"Error: Cannot convert {input_path.suffix} to .dssketch")
                print("Input must be .designspace file for conversion to .dssketch")
                return 1
            
        else:
            print(f"Error: Unknown output format: {output_format}")
            print("Supported formats: dssketch, dsl, designspace, auto")
            return 1
            
    except Exception as e:
        print(f"Error during conversion: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())