#!/usr/bin/env python3
"""
DSL ↔ DesignSpace Converter
Converts between compact DSL format and fonttools .designspace XML format
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET
import json

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
class DSLAxis:
    """Represents an axis in DSL format"""
    name: str
    tag: str
    minimum: float
    default: float
    maximum: float
    map_values: List[Tuple[float, float, str]] = field(default_factory=list)  # (user, design, label)
    labels: List[Tuple[float, str]] = field(default_factory=list)

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
    filename: str
    location: Dict[str, float]  # axis_name -> design_value

@dataclass
class DSLDocument:
    """Complete DSL document structure"""
    family: str
    axes: List[DSLAxis]
    masters: List[DSLMaster]
    instances: List[DSLInstance]
    rules: List[Dict] = field(default_factory=list)
    variable_fonts: List[Dict] = field(default_factory=list)
    lib: Dict = field(default_factory=dict)


# ============================================================================
# DSL Parser
# ============================================================================

class DSLParser:
    """Parse DSL format into structured data"""
    
    # Standard weight mappings (user value -> name)
    STANDARD_WEIGHTS = {
        50: 'Hairline', 100: 'Thin', 200: 'ExtraLight', 300: 'Light',
        350: 'Book', 400: 'Regular', 500: 'Medium', 600: 'SemiBold',
        700: 'Bold', 800: 'ExtraBold', 900: 'Black'
    }
    
    # Standard width mappings
    STANDARD_WIDTHS = {
        1: 'Compressed', 2: 'ExtraCondensed', 3: 'Condensed',
        4: 'SemiCondensed', 5: 'Normal', 6: 'Wide',
        7: 'SemiExtended', 8: 'Extended', 9: 'UltraExtended'
    }
    
    def __init__(self):
        self.document = DSLDocument(family="", axes=[], masters=[], instances=[])
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
            
        elif line == 'axes' or line.startswith('axes '):
            self.current_section = 'axes'
            
        elif line == 'masters' or line.startswith('masters '):
            self.current_section = 'masters'
            
        elif line == 'instances' or line.startswith('instances '):
            self.current_section = 'instances'
            
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
        if re.match(r'^\w+\s+\w{4}\s+[\d:.-]+', line):
            parts = line.split()
            name = parts[0]
            tag = parts[1]
            
            # Parse range (min:default:max)
            range_str = parts[2]
            if ':' in range_str:
                values = range_str.split(':')
                minimum = float(values[0])
                default = float(values[1]) if len(values) > 2 else minimum
                maximum = float(values[-1])
            else:
                # Single value
                minimum = default = maximum = float(range_str)
            
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
        
        # Parse left side (can be "300 Light" or just "Light")
        left_parts = left.split()
        
        if left_parts[0].replace('.', '').replace('-', '').isdigit():
            # Format: "300 Light"
            user = float(left_parts[0])
            label = ' '.join(left_parts[1:]) if len(left_parts) > 1 else str(user)
        else:
            # Format: "Light" - need to infer user value
            label = left
            user = self._get_standard_user_value(label, self.current_axis.name)
        
        self.current_axis.map_values.append((user, design, label))
    
    def _parse_master_line(self, line: str):
        """Parse master definition line"""
        # Format: "Light [0, 0]" or "Regular 125 0 @base"
        
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
            # Format: "Light 0 0" or with explicit location
            parts = line.split()
            name = parts[0]
            coords = [float(x) for x in parts[1:] if x.replace('.', '').replace('-', '').isdigit()]
        
        # Create location dict (assuming order matches axes order)
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
        if line == 'auto':
            # Generate instances automatically
            self._generate_auto_instances()
        else:
            # Parse explicit instance
            # Similar to master parsing
            pass
    
    def _parse_rule_line(self, line: str):
        """Parse rule definition line"""
        # Format: "cent > cent.alt @ weight >= 365"
        if '>' in line:
            parts = line.split('@')
            substitution = parts[0].strip()
            condition = parts[1].strip() if len(parts) > 1 else ""
            
            sub_parts = substitution.split('>')
            from_glyph = sub_parts[0].strip()
            to_glyph = sub_parts[1].strip()
            
            # Store rule (simplified)
            self.document.rules.append({
                'from': from_glyph,
                'to': to_glyph,
                'condition': condition
            })
    
    def _get_standard_user_value(self, label: str, axis_name: str) -> float:
        """Get standard user value for a label"""
        if axis_name == 'weight':
            for value, name in self.STANDARD_WEIGHTS.items():
                if name.lower() == label.lower():
                    return value
        elif axis_name == 'width':
            for value, name in self.STANDARD_WIDTHS.items():
                if name.lower() == label.lower():
                    return value
        
        # Default fallback
        return 400 if axis_name == 'weight' else 100
    
    def _generate_auto_instances(self):
        """Generate instances automatically from axes mappings"""
        # This would generate all combinations
        # For now, simplified implementation
        pass


# ============================================================================
# DSL Writer
# ============================================================================

class DSLWriter:
    """Write DesignSpace data to DSL format"""
    
    def __init__(self, doc: DesignSpaceDocument):
        self.doc = doc
        
    def write(self, filepath: str):
        """Write DSL to file"""
        content = self.generate()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def generate(self) -> str:
        """Generate DSL content from DesignSpace document"""
        lines = []
        
        # Family name
        family = self._get_family_name()
        lines.append(f"family {family}")
        lines.append("")
        
        # Axes
        lines.append("# Axes and mappings")
        lines.append("axes")
        for axis in self.doc.axes:
            lines.extend(self._format_axis(axis))
        lines.append("")
        
        # Masters
        lines.append("# Masters")
        lines.append("masters")
        for source in self.doc.sources:
            lines.append(self._format_source(source))
        lines.append("")
        
        # Rules
        if self.doc.rules:
            lines.append("# Rules")
            lines.append("rules")
            for rule in self.doc.rules:
                lines.append(self._format_rule(rule))
            lines.append("")
        
        # Instances
        if self.doc.instances:
            lines.append("# Instances")
            lines.append("instances")
            for instance in self.doc.instances:
                lines.append(self._format_instance(instance))
        
        return '\n'.join(lines)
    
    def _get_family_name(self) -> str:
        """Extract family name from document"""
        if self.doc.instances:
            return self.doc.instances[0].familyName or "Unknown"
        elif self.doc.sources:
            return self.doc.sources[0].familyName or "Unknown"
        return "Unknown"
    
    def _format_axis(self, axis: AxisDescriptor) -> List[str]:
        """Format axis as DSL"""
        lines = []
        
        # Axis header
        tag = axis.tag
        name = axis.name
        minimum = axis.minimum
        default = axis.default
        maximum = axis.maximum
        
        lines.append(f"    {name} {tag} {minimum}:{default}:{maximum}")
        
        # Mappings
        if axis.map:
            for mapping in axis.map:
                user = mapping.inputLocation
                design = mapping.outputLocation
                
                # Find label for this user value
                label = ""
                if axis.axisLabels:
                    for axis_label in axis.axisLabels:
                        if axis_label.userValue == user:
                            label = axis_label.name
                            break
                
                if label:
                    lines.append(f"        {user} {label} > {design}")
                else:
                    lines.append(f"        {user} > {design}")
        
        return lines
    
    def _format_source(self, source: SourceDescriptor) -> str:
        """Format source/master as DSL"""
        name = Path(source.filename or "").stem
        
        # Build location coordinates
        coords = []
        for axis in self.doc.axes:
            value = source.location.get(axis.name, 0)
            coords.append(str(value))
        
        line = f"    {name} [{', '.join(coords)}]"
        
        # Add flags
        if source.copyLib or source.copyInfo or source.copyGroups or source.copyFeatures:
            line += " @base"
        
        return line
    
    def _format_rule(self, rule: RuleDescriptor) -> str:
        """Format rule as DSL"""
        # Simplified - would need more complex handling for real rules
        if rule.subs:
            return f"    {rule.name}"
        return ""
    
    def _format_instance(self, instance: InstanceDescriptor) -> str:
        """Format instance as DSL"""
        name = instance.styleName or ""
        
        # Build location
        coords = []
        for axis in self.doc.axes:
            value = instance.location.get(axis.name, 0)
            coords.append(str(value))
        
        return f"    {name} [{', '.join(coords)}]"


# ============================================================================
# Converter Classes
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
        
        # Add mappings
        axis.map = []
        for user, design, label in dsl_axis.map_values:
            mapping = AxisMappingDescriptor()
            mapping.inputLocation = user
            mapping.outputLocation = design
            axis.map.append(mapping)
            
            # Add label
            axis_label = AxisLabelDescriptor()
            axis_label.userValue = user
            axis_label.name = label
            if user == dsl_axis.default:
                axis_label.elidable = True
            axis.axisLabels = axis.axisLabels or []
            axis.axisLabels.append(axis_label)
        
        return axis
    
    def _convert_master(self, dsl_master: DSLMaster, dsl_doc: DSLDocument) -> SourceDescriptor:
        """Convert DSL master to DesignSpace source"""
        source = SourceDescriptor()
        source.filename = dsl_master.filename
        source.familyName = dsl_doc.family
        source.styleName = dsl_master.name
        
        # Convert location from design space values
        source.location = dsl_master.location
        
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
        instance.location = dsl_instance.location
        
        # Generate PostScript name
        ps_family = instance.familyName.replace(' ', '')
        ps_style = instance.styleName.replace(' ', '')
        instance.postScriptFontName = f"{ps_family}-{ps_style}"
        
        return instance
    
    def _convert_rule(self, dsl_rule: Dict, doc: DesignSpaceDocument) -> Optional[RuleDescriptor]:
        """Convert DSL rule to DesignSpace rule"""
        # Simplified implementation
        rule = RuleDescriptor()
        rule.name = f"switching {dsl_rule.get('from', '')}"
        
        # Parse condition and create rule
        # This would need more complex implementation
        
        return rule


class DesignSpaceToDS:
    """Convert DesignSpace to DSL format"""
    
    def convert(self, ds_path: str) -> str:
        """Convert DesignSpace file to DSL string"""
        doc = DesignSpaceDocument()
        doc.read(ds_path)
        
        writer = DSLWriter(doc)
        return writer.generate()


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
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
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
        converter = DesignSpaceToDS()
        dsl_content = converter.convert(str(input_path))
        
        output_path = args.output or input_path.with_suffix('.dsl')
        with open(output_path, 'w') as f:
            f.write(dsl_content)
        print(f"Converted {input_path} -> {output_path}")
        
    else:
        print(f"Unknown input format: {input_path.suffix}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
