"""Configuration and data management for DSSketch"""

import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .utils.logging import DSSketchLogger


class DataManager:
    """Manages DSSketch data files with user override support"""

    def __init__(self):
        # Package data directory (built-in defaults)
        self.package_data_dir = Path(__file__).parent / "data"

        # User data directory (overrides)
        self.user_data_dir = self._get_user_data_dir()

        # Create user directory if it doesn't exist
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_data_dir(self) -> Path:
        """Get user data directory based on OS or environment variable"""
        # Check for custom path in environment
        if custom_dir := os.environ.get("DSSKETCH_DATA_DIR"):
            return Path(custom_dir).expanduser()

        # OS-specific default paths
        system = platform.system()

        if system == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "dssketch"
        elif system == "Windows":
            app_data = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
            return Path(app_data) / "dssketch"
        else:  # Linux and others
            xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
            return Path(xdg_config) / "dssketch"

    def load_data_file(self, filename: str) -> Dict[str, Any]:
        """Load data file with user override priority"""
        # Check user directory first
        user_file = self.user_data_dir / filename
        if user_file.exists():
            return self._load_file(user_file)

        # Fall back to package data
        package_file = self.package_data_dir / filename
        if package_file.exists():
            return self._load_file(package_file)

        # Return empty dict if nothing found
        return {}

    def _load_file(self, filepath: Path) -> Dict[str, Any]:
        """Load JSON or YAML file based on extension"""
        try:
            with open(filepath, encoding="utf-8") as f:
                if filepath.suffix in [".yaml", ".yml"]:
                    return yaml.safe_load(f) or {}
                elif filepath.suffix == ".json":
                    return json.load(f)
                else:
                    # Try YAML first, then JSON
                    content = f.read()
                    try:
                        return yaml.safe_load(content) or {}
                    except yaml.YAMLError:
                        return json.loads(content)
        except Exception as e:
            DSSketchLogger.warning(f"Error loading {filepath}: {e}")
            return {}

    def save_user_data(self, filename: str, data: Dict[str, Any]) -> None:
        """Save data to user directory"""
        filepath = self.user_data_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                if filepath.suffix in [".yaml", ".yml"]:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            DSSketchLogger.info(f"Saved to {filepath}")
        except Exception as e:
            DSSketchLogger.error(f"Error saving {filepath}: {e}")

    def reset_to_defaults(self, filename: Optional[str] = None) -> None:
        """Reset user files to package defaults"""
        if filename:
            # Reset specific file
            user_file = self.user_data_dir / filename
            if user_file.exists():
                user_file.unlink()
                DSSketchLogger.info(f"Reset {filename} to defaults")
            else:
                DSSketchLogger.info(f"{filename} was already using defaults")
        else:
            # Reset all files
            count = 0
            for user_file in self.user_data_dir.glob("*"):
                if user_file.is_file():
                    user_file.unlink()
                    count += 1

            if count:
                DSSketchLogger.info(f"Reset {count} file(s) to defaults")
            else:
                DSSketchLogger.info("No user files to reset")

    def get_data_info(self) -> Dict[str, Any]:
        """Get information about data files"""
        # List files in both directories
        package_files = []
        if self.package_data_dir.exists():
            package_files = [f.name for f in self.package_data_dir.glob("*") if f.is_file()]

        user_files = []
        if self.user_data_dir.exists():
            user_files = [f.name for f in self.user_data_dir.glob("*") if f.is_file()]

        return {
            "package_data_dir": str(self.package_data_dir),
            "user_data_dir": str(self.user_data_dir),
            "package_files": sorted(package_files),
            "user_files": sorted(user_files),
        }

    def copy_package_to_user(self, filename: str) -> bool:
        """Copy a package data file to user directory for editing"""
        package_file = self.package_data_dir / filename
        user_file = self.user_data_dir / filename

        if not package_file.exists():
            DSSketchLogger.error(f"Package file {filename} not found")
            return False

        if user_file.exists():
            DSSketchLogger.warning(f"User file {filename} already exists")
            return False

        try:
            shutil.copy2(package_file, user_file)
            DSSketchLogger.info(f"Copied {filename} to user directory")
            return True
        except Exception as e:
            DSSketchLogger.error(f"Error copying {filename}: {e}")
            return False


# Singleton instance
_data_manager = None


def get_data_manager() -> DataManager:
    """Get or create the data manager singleton"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


def load_unified_mappings() -> Dict[str, Any]:
    """Load unified-mappings.yaml with user overrides"""
    return get_data_manager().load_data_file("unified-mappings.yaml")


def load_discrete_labels() -> Dict[str, Any]:
    """Load discrete-axis-labels.yaml with user overrides"""
    return get_data_manager().load_data_file("discrete-axis-labels.yaml")


def load_translations() -> Dict[str, Any]:
    """Load font-resources-translations.json with user overrides"""
    return get_data_manager().load_data_file("font-resources-translations.json")
