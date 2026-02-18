"""
Utilities for handling discrete axes

This module provides centralized logic for discrete axis detection and processing.
"""

from typing import Dict, List


class DiscreteAxisHandler:
    """Centralized handling of discrete axes"""

    DISCRETE_AXES = ["italic", "ital", "slant", "slnt"]

    @staticmethod
    def is_discrete(axis) -> bool:
        """Check if an axis is discrete

        Args:
            axis: An axis object with minimum, default, maximum, and name attributes

        Returns:
            True if the axis is discrete (binary 0/1 axis like italic)
        """
        return (
            hasattr(axis, "minimum")
            and axis.minimum == 0
            and hasattr(axis, "default")
            and axis.default == 0
            and hasattr(axis, "maximum")
            and axis.maximum == 1
        )

    @staticmethod
    def load_discrete_labels() -> Dict[str, Dict[int, List[str]]]:
        """Load discrete axis labels from YAML file with user overrides

        Returns:
            Dictionary mapping axis tags to value->labels mappings
        """
        from ..config import get_data_manager

        # Load from data manager (with user overrides)
        labels = get_data_manager().load_data_file("discrete-axis-labels.yaml")

        if labels:
            # Convert string keys to int for values
            result = {}
            for axis, values in labels.items():
                result[axis] = {}
                for value, names in values.items():
                    result[axis][int(value)] = names if isinstance(names, list) else [names]
            return result

        # Default fallback if file not found
        return {
            "ital": {0: ["Upright", "Roman", "Normal"], 1: ["Italic"]},
            "slnt": {0: ["Upright", "Normal"], 1: ["Slanted", "Oblique"]},
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
