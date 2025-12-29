# Changelog

All notable changes to DSSketch will be documented in this file.

## [Unreleased]

### Added
- **CLI options for variable generation**: `--novars` to disable, `--vars N` to set threshold
- **Counter-based variable naming**: Auto-generated variables now use `$axis1`, `$axis2` format
- **`$` = axis default**: In avar2 output, `$` now means "use axis default value"
- **avar2 matrix format**: New tabular format for complex avar2 mappings (default)
- **avar2 linear format**: Traditional one-mapping-per-line format (`--linear`)
- **`instances off`**: Option to completely disable instance generation
- **Hidden axes support**: Parametric axes that only appear in avar2 output
- **Family auto-detection**: Extracts family name from UFO sources when not specified
- **Instances auto fallback**: Generates instances from axis min/default/max when no labels defined

### Changed
- Variable naming changed from `$axis` to `$axis1`, `$axis2`, etc. to avoid confusion with `$` shorthand
- `$` in avar2 now resolves to axis.default (not variable reference)
- Default avar2 output format is now matrix (use `--linear` for old format)

### Fixed
- Roundtrip conversion preserves axis display names
- avar2 mappings correctly handle hidden axes
- Column alignment accounts for variable name lengths
- Instance generation excludes hidden axes

## [0.1.0] - 2024-12

### Added
- Initial release
- Bidirectional conversion between `.dssketch` and `.designspace` formats
- 84-97% size reduction compared to DesignSpace XML
- Label-based syntax for source coordinates and axis ranges
- Human-readable axis names (`weight` instead of `wght`)
- Automatic instance generation (`instances auto`)
- Instance skip functionality
- Substitution rules with wildcards
- UFO validation
- Comprehensive error detection with typo suggestions
