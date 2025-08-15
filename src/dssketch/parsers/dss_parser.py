"""
DSS Parser Module

Parses DSSketch (.dss/.dssketch) format files into structured data.
"""

import re
from pathlib import Path
from typing import Dict, List

import yaml

from ..core.mappings import Standards
from ..core.models import DSSAxis, DSSAxisMapping, DSSDocument, DSSInstance, DSSMaster, DSSRule


class DSSParser:
    """Parse DSS format into structured data"""

    # Tag to standard name mapping for registered axes
    TAG_TO_NAME = {
        "ital": "italic",
        "opsz": "optical",
        "slnt": "slant",
        "wdth": "width",
        "wght": "weight",
    }

    def __init__(self):
        self.document = DSSDocument(family="")
        self.current_section = None
        self.current_axis = None
        self.master_axis_order = None  # Explicit axis order from masters section
        self.discrete_labels = self._load_discrete_labels()
        # Note: Rule names now handled via @name syntax instead of comments

    def _load_discrete_labels(self) -> Dict[str, Dict[int, List[str]]]:
        """Load discrete axis labels from YAML file"""
        try:
            data_dir = Path(__file__).parent.parent / "data"
            with open(data_dir / "discrete-axis-labels.yaml") as f:
                return yaml.safe_load(f) or {}
        except (FileNotFoundError, Exception):
            # Default fallback if file not found
            return {
                "ital": {0: ["Upright", "Roman", "Normal"], 1: ["Italic"]},
                "slnt": {0: ["Upright", "Normal"], 1: ["Slanted", "Oblique"]},
            }

    def parse_file(self, filepath: str) -> DSSDocument:
        """Parse DSS file"""
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        return self.parse(content)

    def parse(self, content: str) -> DSSDocument:
        """Parse DSS content"""
        lines = content.split("\n")

        for line_no, line in enumerate(lines, 1):
            original_line = line.strip()

            # Handle comments before removing them
            if "#" in line:
                comment_part = line[line.index("#") :]
                line = line[: line.index("#")]

                # If line is only a comment, process it separately
                if not line.strip():
                    try:
                        self._parse_line(comment_part.strip())
                    except Exception as e:
                        raise ValueError(f"Error parsing line {line_no}: {original_line}\n{e}")
                    continue

            line = line.strip()

            if not line:
                continue

            try:
                self._parse_line(line)
            except Exception as e:
                raise ValueError(f"Error parsing line {line_no}: {original_line}\n{e}")

        return self.document

    def _parse_line(self, line: str):
        """Parse a single line based on context"""

        # Handle comments - store them for potential rule names
        if line.startswith("#"):
            # Extract comment text, removing the # and whitespace
            comment_text = line[1:].strip()
            if self.current_section == "rules":
                self.current_rule_comment = comment_text
            return

        # Main sections
        if line.startswith("family "):
            self.document.family = line[7:].strip()
            self.current_section = "family"

        elif line.startswith("suffix "):
            self.document.suffix = line[7:].strip()

        elif line.startswith("path "):
            self.document.path = line[5:].strip()

        elif line == "axes" or line.startswith("axes "):
            self.current_section = "axes"

        elif line == "masters" or line.startswith("masters "):
            self.current_section = "masters"
            # Parse explicit axis order if present: masters [wght, ital]
            if "[" in line and "]" in line:
                axis_order_str = line[line.index("[") + 1 : line.index("]")]
                axis_tags = [tag.strip() for tag in axis_order_str.split(",")]
                # Convert tags to full axis names
                self.master_axis_order = [self._tag_to_axis_name(tag) for tag in axis_tags]

        elif line == "instances" or line.startswith("instances "):
            self.current_section = "instances"
            if "auto" in line:
                self.document.instances_auto = True

        elif line.startswith("rules"):
            self.current_section = "rules"

        # Parse based on current section
        elif self.current_section == "axes":
            self._parse_axis_line(line)

        elif self.current_section == "masters":
            self._parse_master_line(line)

        elif self.current_section == "instances":
            self._parse_instance_line(line)

        elif self.current_section == "rules":
            self._parse_rule_line(line)

    def _parse_axis_line(self, line: str):
        """Parse axis definition lines"""

        # Check for axis definition patterns
        # Pattern 1: "weight wght 100:400:900" (full form)
        # Pattern 2: "CONTRAST CNTR 0:0:100" (custom axis)
        # Pattern 3: "wght 100:400:900" (registered axis, name omitted)
        # Pattern 4: "ital binary" (registered binary axis)
        # Pattern 5: "weight 100:400:900" (legacy form with inferred tag)

        if re.match(r"^\w+\s+\w{4}\s+", line):
            # Full form: name tag range
            parts = line.split()
            name = parts[0]
            tag = parts[1]

            # Parse range, binary, or discrete
            if len(parts) > 2:
                range_part = parts[2]
                if range_part in ["binary", "discrete"]:
                    minimum, default, maximum = 0, 0, 1
                elif ":" in range_part:
                    values = range_part.split(":")
                    minimum = float(values[0])
                    default = float(values[1]) if len(values) > 2 else minimum
                    maximum = float(values[-1])
                else:
                    minimum = default = maximum = float(range_part)
            else:
                minimum = default = maximum = 0

        elif re.match(r"^\w{4}\s+", line) and ">" not in line:
            # Shortened form: tag range (for registered axes)
            # But not if it contains '>' (that's a mapping)
            parts = line.split()
            tag = parts[0]

            # Get standard name from tag
            name = self.TAG_TO_NAME.get(tag, tag.upper())

            # Parse range, binary, or discrete
            if len(parts) > 1:
                range_part = parts[1]
                if range_part in ["binary", "discrete"]:
                    minimum, default, maximum = 0, 0, 1
                elif ":" in range_part:
                    values = range_part.split(":")
                    minimum = float(values[0])
                    default = float(values[1]) if len(values) > 2 else minimum
                    maximum = float(values[-1])
                else:
                    minimum = default = maximum = float(range_part)
            else:
                minimum = default = maximum = 0
        elif re.match(r"^\w+\s+([\d.:-]+|binary|discrete)", line) and ">" not in line:
            # Legacy form: "weight 100:400:900" (infer tag from name)
            parts = line.split()
            name = parts[0]

            # Infer tag from name
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
                if range_part in ["binary", "discrete"]:
                    minimum, default, maximum = 0, 0, 1
                elif ":" in range_part:
                    values = range_part.split(":")
                    minimum = float(values[0])
                    default = float(values[1]) if len(values) > 2 else minimum
                    maximum = float(values[-1])
                else:
                    minimum = default = maximum = float(range_part)
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
        # Check if this is a discrete axis (min=0, default=0, max=1)
        is_discrete = (
            self.current_axis.minimum == 0
            and self.current_axis.default == 0
            and self.current_axis.maximum == 1
        )

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
                # Format: "Light" - infer user value
                label = left
                user = Standards.get_user_value_for_name(label, self.current_axis.name)
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

        mapping = DSSAxisMapping(
            user_value=user, design_value=design, label=label, elidable=elidable
        )
        self.current_axis.mappings.append(mapping)

    def _parse_master_line(self, line: str):
        """Parse master definition line"""
        # Extract flags
        is_base = "@base" in line
        line = line.replace("@base", "").strip()

        # Parse coordinates
        if "[" in line and "]" in line:
            # Format: "Light [0, 0]"
            name = line[: line.index("[")].strip()
            coords_str = line[line.index("[") + 1 : line.index("]")]
            coords = [float(x.strip()) for x in coords_str.split(",")]
        else:
            # Format: "Light 0 0"
            parts = line.split()
            name = parts[0]
            coords = [float(x) for x in parts[1:] if x.replace(".", "").replace("-", "").isdigit()]

        # Create location dict using explicit axis order if available
        location = {}
        if self.master_axis_order:
            # Use explicit axis order from masters section
            for i, axis_name in enumerate(self.master_axis_order):
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
            filename = f"{name}.ufo"

        master = DSSMaster(name=name, filename=filename, location=location, is_base=is_base)

        self.document.masters.append(master)

    def _parse_instance_line(self, line: str):
        """Parse instance definition line"""
        if line != "auto":
            # Parse explicit instance (similar to master parsing)
            pass

    def _parse_condition_string(self, condition_str: str) -> List[dict]:
        """Parse condition string like 'weight >= 480' or 'weight >= 600 && width >= 110'"""
        conditions = []
        if not condition_str:
            return conditions

        # Split by && for multiple conditions
        cond_parts = [part.strip() for part in condition_str.split("&&")]

        for cond_part in cond_parts:
            # Try range condition first: "400 <= weight <= 700"
            range_match = re.search(r"([\d.]+)\s*<=\s*(\w+)\s*<=\s*([\d.]+)", cond_part)
            if range_match:
                min_val = float(range_match.group(1))
                axis = range_match.group(2)
                max_val = float(range_match.group(3))
                conditions.append({"axis": axis, "minimum": min_val, "maximum": max_val})
                continue

            # Standard conditions: "weight >= 480", "weight <= 400", "weight == 500"
            std_match = re.search(r"(\w+)\s*(>=|<=|==)\s*([\d.]+)", cond_part)
            if std_match:
                axis = std_match.group(1)
                operator = std_match.group(2)
                value = float(std_match.group(3))

                if operator == ">=":
                    conditions.append(
                        {
                            "axis": axis,
                            "minimum": value,
                            "maximum": 1000,  # Default high maximum
                        }
                    )
                elif operator == "<=":
                    conditions.append(
                        {
                            "axis": axis,
                            "minimum": 0,  # Default low minimum
                            "maximum": value,
                        }
                    )
                elif operator == "==":
                    conditions.append({"axis": axis, "minimum": value, "maximum": value})

        return conditions

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
        for standard_tag, full_name in tag_mappings.items():
            if lower_tag == full_name:
                return full_name

        # Return original for custom axes
        return tag

    def _parse_rule_line(self, line: str):
        """Parse rule definition line with parentheses syntax: pattern > target (condition) "name" """
        if ">" in line:
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
                print(f"⚠️  Warning: Invalid rule syntax: {line}")
                print('Expected format: pattern > target (condition) "name"')
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
                for user_val, label, design_val in values:
                    if label in ["Regular", "Bold", "Light"]:
                        instance = DSSInstance(
                            name=label,
                            familyname=self.document.family,
                            stylename=label,
                            location={axis_name: design_val},
                        )
                        self.document.instances.append(instance)
