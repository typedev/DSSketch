#!/usr/bin/env python3
"""
DSL ↔ DesignSpace Converter
Converts between compact DSL format and fonttools .designspace XML format

Key concepts:
- User Space: values users see (font-weight: 400)
- Design Space: real coordinates in file (can be 125, 380, anything)
- Mapping: Regular 400 > 125 means user requests 400, master is at 125

Features:
- Bidirectional conversion
- Smart defaults for standard weights/widths
- Compact DSL syntax with auto-expansion
- Proper user/design space mapping
"""

import re
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

# For proper DesignSpace handling
from fontTools.designspaceLib import (
    DesignSpaceDocument,
    AxisDescriptor,
    SourceDescriptor,
    InstanceDescriptor,
    RuleDescriptor,
    AxisLabelDescriptor,
    AxisMappingDescriptor,
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
    axes: List[DSLAxis] = field(default_factory=list)
    masters: List[DSLMaster] = field(default_factory=list)
    instances: List[DSLInstance] = field(default_factory=list)
    rules: List[DSLRule] = field(default_factory=list)
    variable_fonts: List[Dict] = field(default_factory=list)
    lib: Dict = field(default_factory=dict)


# ============================================================================
# Standard Mappings and Defaults
# ============================================================================

class Standards:
    """Standard weight, width and axis mappings"""
    
    # Standard weight mappings (user value -> name)
    WEIGHTS = {
        50: 'Hairline', 100: 'Thin', 200: 'Extralight', 300: 'Light',
        350: 'Book', 400: 'Regular', 500: 'Medium', 600: 'Semibold',
        700: 'Bold', 800: 'Extrabold', 900: 'Black'
    }
    
    # Standard width mappings
    WIDTHS = {
        60: 'Compressed', 70: 'SemiCompressed', 80: 'Condensed',
        90: 'SemiCondensed', 100: 'Normal', 125: 'SemiExpanded',
        150: 'Expanded', 200: 'ExtraExpanded'
    }
    
    # Reverse lookups
    WEIGHT_NAMES = {v: k for k, v in WEIGHTS.items()}
    WIDTH_NAMES = {v: k for k, v in WIDTHS.items()}
    
    # Common variations in naming
    WEIGHT_ALIASES = {
        'ExtraLight': 'Extralight',
        'SemiBold': 'Semibold',
        'ExtraBold': 'Extrabold',
    }


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


# Add the missing methods to Standards class
def _get_user_value_for_name(cls, name: str, axis_name: str) -> float:
    """Get standard user value for a weight/width name"""
    name = cls.WEIGHT_ALIASES.get(name, name)
    
    if axis_name.lower() == 'weight':
        return cls.WEIGHT_NAMES.get(name, 400)
    elif axis_name.lower() == 'width':
        return cls.WIDTH_NAMES.get(name, 100)
    return 400 if axis_name.lower() == 'weight' else 100

def _get_name_for_user_value(cls, value: float, axis_name: str) -> str:
    """Get standard name for a user value"""
    if axis_name.lower() == 'weight':
        return cls.WEIGHTS.get(int(value), f"Weight{int(value)}")
    elif axis_name.lower() == 'width':
        return cls.WIDTHS.get(int(value), f"Width{int(value)}")
    return str(int(value))

Standards.get_user_value_for_name = classmethod(_get_user_value_for_name)
Standards.get_name_for_user_value = classmethod(_get_name_for_user_value)


# ============================================================================
# DesignSpace to DSL Converter
# ============================================================================

class DesignSpaceToDSL:
    """Convert DesignSpace to DSL format"""
    
    def __init__(self):
        # Load external data
        self.load_external_data()
    
    def load_external_data(self):
        """Load external weight/width mappings from JSON files"""
        data_dir = Path(__file__).parent / "data"
        
        self.font_resources = {}
        self.stylenames = {}
        
        try:
            with open(data_dir / "font-resources-translations.json", 'r') as f:
                self.font_resources = json.load(f)
        except FileNotFoundError:
            pass
            
        try:
            with open(data_dir / "stylenames.json", 'r') as f:
                self.stylenames = json.load(f)
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
    
    def __init__(self, optimize: bool = True):
        self.optimize = optimize
    
    def write(self, dsl_doc: DSLDocument) -> str:
        """Generate DSL string from document"""
        lines = []
        
        # Family declaration
        lines.append(f"family {dsl_doc.family}")
        if dsl_doc.suffix:
            lines.append(f"suffix {dsl_doc.suffix}")
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
        
        # Axis header with range
        if axis.minimum == axis.default == axis.maximum:
            # Binary axis
            lines.append(f"    {axis.name} {axis.tag} binary")
        else:
            lines.append(f"    {axis.name} {axis.tag} {axis.minimum}:{axis.default}:{axis.maximum}")
        
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
        to_glyphs = [sub[1] for sub in substitutions]
        
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
        
        # New axis definition: "weight wght 100:400:900"
        if re.match(r'^\w+\s+\w{4}\s+', line):
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
            
            self.current_axis = DSLAxis(
                name=name, tag=tag,
                minimum=minimum, default=default, maximum=maximum
            )
            self.document.axes.append(self.current_axis)
            
        # Axis mapping: "300 Light > 0" or "Light > 0"
        elif '>' in line and self.current_axis:
            self._parse_axis_mapping(line)
    
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
        axis.minimum = dsl_axis.minimum
        axis.default = dsl_axis.default
        axis.maximum = dsl_axis.maximum
        
        # Add mappings and labels
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
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert between DSL and DesignSpace formats')
    parser.add_argument('input', help='Input file (.dsl or .designspace)')
    parser.add_argument('-o', '--output', help='Output file (optional)')
    parser.add_argument('--format', choices=['dsl', 'designspace', 'auto'], 
                       default='auto', help='Output format')
    parser.add_argument('--optimize', action='store_true', default=True,
                       help='Optimize DSL output (default: True)')
    parser.add_argument('--no-optimize', action='store_false', dest='optimize',
                       help='Disable DSL optimization')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist")
        return 1
    
    try:
        # Determine conversion direction
        if input_path.suffix.lower() == '.dsl':
            # DSL to DesignSpace
            parser = DSLParser()
            dsl_doc = parser.parse_file(str(input_path))
            
            converter = DSLToDesignSpace()
            ds_doc = converter.convert(dsl_doc)
            
            output_path = args.output or input_path.with_suffix('.designspace')
            ds_doc.write(str(output_path))
            print(f"Converted {input_path} -> {output_path}")
            
        elif input_path.suffix.lower() == '.designspace':
            # DesignSpace to DSL
            converter = DesignSpaceToDSL()
            dsl_doc = converter.convert_file(str(input_path))
            
            writer = DSLWriter(optimize=args.optimize)
            dsl_content = writer.write(dsl_doc)
            
            output_path = args.output or input_path.with_suffix('.dsl')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(dsl_content)
            print(f"Converted {input_path} -> {output_path}")
            
        else:
            print(f"Error: Unknown input format: {input_path.suffix}")
            print("Supported formats: .dsl, .designspace")
            return 1
            
    except Exception as e:
        print(f"Error during conversion: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())