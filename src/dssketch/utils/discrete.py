"""
Utilities for handling discrete axes

This module provides centralized logic for discrete axis detection and processing.
"""

from pathlib import Path
from typing import Dict, List

import yaml


class DiscreteAxisHandler:
    """Centralized handling of discrete axes"""

    DISCRETE_AXES = ['italic', 'ital', 'slant', 'slnt']

    @staticmethod
    def is_discrete(axis) -> bool:
        """Check if an axis is discrete

        Args:
            axis: An axis object with minimum, default, maximum, and name attributes

        Returns:
            True if the axis is discrete (binary 0/1 axis like italic)
        """
        return (
            hasattr(axis, 'minimum') and axis.minimum == 0 and
            hasattr(axis, 'default') and axis.default == 0 and
            hasattr(axis, 'maximum') and axis.maximum == 1 and
            hasattr(axis, 'name') and axis.name.lower() in DiscreteAxisHandler.DISCRETE_AXES
        )

    @staticmethod
    def load_discrete_labels() -> Dict[str, Dict[int, List[str]]]:
        """Load discrete axis labels from YAML file

        Returns:
            Dictionary mapping axis tags to value->labels mappings
        """
        try:
            data_dir = Path(__file__).parent.parent / "data"
            with open(data_dir / "discrete-axis-labels.yaml", 'r') as f:
                return yaml.safe_load(f) or {}
        except (FileNotFoundError, Exception):
            # Default fallback if file not found
            return {
                'ital': {
                    0: ['Upright', 'Roman', 'Normal'],
                    1: ['Italic']
                },
                'slnt': {
                    0: ['Upright', 'Normal'],
                    1: ['Slanted', 'Oblique']
                }
            }

    @staticmethod
    def get_label_for_value(axis_tag: str, value: int) -> str:
        """Get the default label for a discrete axis value

        Args:
            axis_tag: The axis tag (e.g., 'ital', 'slnt')
            value: The discrete value (0 or 1)

        Returns:
            The default label for this value
        """
        labels = DiscreteAxisHandler.load_discrete_labels()
        if axis_tag in labels and value in labels[axis_tag]:
            return labels[axis_tag][value][0]  # Return first label as default
        return str(value)  # Fallback to string value

