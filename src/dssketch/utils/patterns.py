"""
Pattern matching utilities for wildcard glyph patterns

This module provides utilities for matching and expanding wildcard patterns in glyph names.
"""

from typing import List, Optional, Set


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

