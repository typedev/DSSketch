"""
Unified mappings for font attributes

This module provides mappings between stylenames, OS/2 values, and user space coordinates.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class UnifiedMappings:
    """Unified mappings for font attributes: name ↔ OS/2 ↔ user_space"""

    # Will be loaded from JSON/YAML file
    MAPPINGS = {}
    DEFAULTS = {}

    @classmethod
    def _load_mappings(cls):
        """Load mappings from JSON or YAML file"""
        if cls.MAPPINGS:  # Already loaded
            return

        data_dir = Path(__file__).parent.parent / "data"

        # Try YAML first (if available), then JSON
        yaml_file = data_dir / "unified-mappings.yaml"
        json_file = data_dir / "unified-mappings.json"

        data = None

        # Try YAML if available
        if yaml_file.exists():
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
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
                    "Thin": {"os2": 100, "user_space": 100},
                    "Light": {"os2": 300, "user_space": 300},
                    "Regular": {"os2": 400, "user_space": 400},
                    "Medium": {"os2": 500, "user_space": 500},
                    "Bold": {"os2": 700, "user_space": 700},
                    "Black": {"os2": 900, "user_space": 900}
                },
                "width": {
                    "Condensed": {"os2": 3, "user_space": 75},
                    "Normal": {"os2": 5, "user_space": 100},
                    "Extended": {"os2": 7, "user_space": 125}
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


# Backward compatibility alias
Standards = UnifiedMappings

