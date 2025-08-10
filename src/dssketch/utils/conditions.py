"""
Utilities for parsing and formatting rule conditions

This module provides centralized handling of substitution rule conditions.
"""

import re
from typing import Any, Dict, List


class ConditionHandler:
    """Centralized handling of rule conditions"""

    @staticmethod
    def parse(condition_str: str) -> List[Dict[str, Any]]:
        """Parse condition string into structured format

        Supports:
        - Simple: "weight >= 480"
        - Compound: "weight >= 600 && width >= 110"
        - Range: "400 <= weight <= 700"
        - Exact: "weight == 500"

        Args:
            condition_str: Condition string to parse

        Returns:
            List of condition dictionaries with axis, minimum, maximum
        """
        conditions = []
        if not condition_str:
            return conditions

        # Split by && for multiple conditions
        cond_parts = [part.strip() for part in condition_str.split('&&')]

        for cond_part in cond_parts:
            # Try range condition first: "400 <= weight <= 700"
            range_match = re.search(r'([\d.]+)\s*<=\s*(\w+)\s*<=\s*([\d.]+)', cond_part)
            if range_match:
                min_val = float(range_match.group(1))
                axis = range_match.group(2)
                max_val = float(range_match.group(3))
                conditions.append({
                    'axis': axis,
                    'minimum': min_val,
                    'maximum': max_val
                })
                continue

            # Standard conditions: "weight >= 480", "weight <= 400", "weight == 500"
            std_match = re.search(r'(\w+)\s*(>=|<=|==)\s*([\d.]+)', cond_part)
            if std_match:
                axis = std_match.group(1)
                operator = std_match.group(2)
                value = float(std_match.group(3))

                if operator == '>=':
                    conditions.append({
                        'axis': axis,
                        'minimum': value,
                        'maximum': 1000  # Default high maximum
                    })
                elif operator == '<=':
                    conditions.append({
                        'axis': axis,
                        'minimum': 0,  # Default low minimum
                        'maximum': value
                    })
                elif operator == '==':
                    conditions.append({
                        'axis': axis,
                        'minimum': value,
                        'maximum': value
                    })

        return conditions

    @staticmethod
    def format(conditions: List[Dict[str, Any]]) -> str:
        """Format conditions into a readable string

        Args:
            conditions: List of condition dictionaries

        Returns:
            Formatted condition string with parentheses
        """
        if not conditions:
            return ""

        cond_parts = []
        for cond in conditions:
            axis = cond['axis']
            min_val = cond.get('minimum')
            max_val = cond.get('maximum')

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
            return f"({' && '.join(cond_parts)})"
        return ""

