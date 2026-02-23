# Changelog

All notable changes to DSSketch will be documented in this file.

## [Unreleased]

### Added
- **Custom discrete axis support**: Any axis with `0:0:1` range now works as discrete (e.g., `LOOP discrete`, `FILL discrete`), not just `ital` and `slnt`
- **UFO layer support**: Sources can specify UFO layers via `@layer="layer_name"` flag, enabling multiple masters from a single UFO file
- **Multiple `@base` sources for discrete axes**: Each discrete axis value can have its own base source, validated automatically

### Fixed
- `DiscreteAxisHandler.is_discrete()` no longer requires axis name in hardcoded list — any `0:0:1` axis is discrete
- Parser correctly assigns positional values (0, 1, 2...) to custom discrete axis labels instead of silently returning fallback 100.0
- Writer outputs `discrete` keyword and simplified label format for all discrete axes, not just `ital`
- **Weight axis excluded from elidable removal**: Font compilers expect a weight name in styleName — removing it (e.g., "Compressed Regular" → "Compressed") caused misinterpretation. Weight labels like "Regular" are now always preserved in instance names
- **Instance locations use design-space coordinates**: Fixed forward map (user→design) instead of broken reverseMap lookup
- Updated example files with corrected skip rules and elidable behavior

## [1.1.9] - 2026-01-07

### Added
- **UFOZ support**: Handle compressed UFO archives (contributed by @connordavenport)
- Makefile for common development tasks

### Fixed
- JSON loading encoding issue (#5, contributed by @connordavenport)

## [1.1.7] - 2026-01-06

### Fixed
- avar2 label semantics: input values now correctly use user space
- familyName extraction from UFO sources
- Build warnings: license format and MANIFEST.in syntax

### Changed
- avar2 documentation rewritten with real-world examples

## [1.1.0] - 2025-12-28

### Added
- **avar2 support**: Full bidirectional conversion for OpenType 1.9 axis variations
  - Matrix format (default) and linear format (`--linear`)
  - Variable definitions (`avar2 vars`) with counter-based naming (`$axis1`, `$axis2`)
  - `$` shorthand for axis default values
  - Hidden parametric axes (`axes hidden`)
- **CLI options**: `--novars` to disable variable generation, `--vars N` to set threshold, `--matrix`/`--linear` for avar2 format
- **`instances off`**: Option to completely disable instance generation
- **Family auto-detection**: Extracts family name from base source UFO when not specified
- **Instances auto fallback**: Generates instances from axis min/default/max when no labels defined
- **Axis display name preservation** for roundtrip conversion

### Changed
- `$` in avar2 output resolves to axis default value (not variable reference)
- Default avar2 output format is matrix

### Fixed
- Roundtrip conversion preserves zero-instance state
- avar2 edge cases for complex fonts
- Column alignment accounts for variable name lengths

## [1.0.x] - 2025-08 to 2025-11

### Added
- **Instance skip functionality**: Exclude specific instance combinations via `instances auto skip`
- **Label-based syntax**: Human-readable coordinates (`[Regular, Upright]`), axis ranges (`wght Thin:Regular:Black`), and rule conditions (`weight >= Bold`)
- **Human-readable axis names**: `weight`, `width`, `italic`, `slant`, `optical` auto-convert to tags
- **Intelligent typo detection**: Levenshtein distance-based suggestions for axis tags, mapping labels, and keywords
- **Validation framework**: Label-based range validation, rule axis validation, mapping range validation, duplicate label detection
- **Label-based rule conditions**: `weight >= Bold` instead of `weight >= 700`
- **Explicit axis order**: `sources [wght, ital]` decouples coordinate interpretation from axes order
- **High-level Python API**: `convert_to_dss()`, `convert_to_designspace()`, string-based conversions
- **Logging system**: File-based logging with auto-cleanup (5 most recent logs)
- **`dssketch-data` CLI**: Manage user data file overrides and customization

### Changed
- Terminology: "masters" renamed to "sources" throughout codebase
- CLI consolidated into `src/dssketch/cli.py`
- Rule conditions use design space coordinates (not user space)

### Fixed
- Wildcard detection for single patterns like `A*`
- Rule condition bounds use design space instead of user space
- Number formatting: integers displayed without decimal points

## [1.0.0] - 2025-08-15

### Added
- Initial release
- Bidirectional conversion between `.dssketch` and `.designspace` formats
- 84-97% size reduction compared to DesignSpace XML
- Automatic instance generation (`instances auto`) with elidable labels
- Substitution rules with wildcard pattern matching
- UFO validation and glyph extraction
- Standard weight/width mappings from unified-mappings.yaml
- Discrete axis support for `ital` and `slnt`
- Comprehensive error detection with typo suggestions
