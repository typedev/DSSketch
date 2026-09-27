# Changelog

All notable changes to DSSketch will be documented in this file.

## [Unreleased]

### Added
- **`instances auto` fit report**: DS → DSSketch now checks that the generator actually reproduces the instances the DesignSpace declares, instead of assuming it. Three outcomes, reported separately because they mean different things: a declared position the generator never reaches (WARNING — the sketch cannot describe this design space), the same position under a different style name (WARNING — the DesignSpace may predate a change in the elidable rules), and positions the generator adds (INFO — the DesignSpace was filtered, which is what an `instances auto` / `skip` block expresses). Instances are matched by design-space **position**, never by style name: names diverge for reasons that are not losses, and name matching produced 90 phantom losses across the example corpus where position matching reported none. The report is purely diagnostic — it never alters the document and never synthesises a `skip` block, since `skip` instructs the generator while a DesignSpace records only the result of applying it. Warnings appear wherever DSSketch logging is set up, which the CLI does
- **`DSSAxisMapping.user_value_explicit`**: tells whether the `.dssketch` source wrote the user value (`300 Light > 295`) or it was inferred (`Light > 295` from the standards table, `Custom > 500` as user = design). An inferred value depends on the standards table shipped with the installed DSSketch, so a tool diffing two revisions can treat it as derived rather than as something the file says. The writer no longer compacts an explicit value away even when it equals the standard one: `400 Regular > 400` stays as written
- **Structured conversion report**: the findings above are no longer log prose only. `convert_designspace_to_dss_string()` and `convert_to_dss()` accept `return_report=True` and then return a `(result, ConversionReport)` tuple; `DesignSpaceToDSS.report` holds the same object. Each `ConversionIssue` carries a category, a stable numeric code (`"2.0"`, switchable), a severity, a description, longer details, a suggested fix, and the affected instances as `InstanceRef` objects with their design-space locations — plus `to_dict()` for a JSON-serialisable form. The shape follows the DesignSpace validator in Font Rover so a caller consuming those results can consume these the same way. Exported from the package root: `ConversionReport`, `ConversionIssue`, `InstanceRef`, `CATEGORY_INSTANCES`, `SEVERITY_*`, `INSTANCE_UNREACHABLE`/`RENAMED`/`EXTRA`. Fully backwards compatible — without the flag both functions return exactly what they did before

### Changed
- **Parsing no longer imports the UFO stack** (#7): `import dssketch`, `DSSParser`, `DSSWriter` and the document models now load only the stdlib and PyYAML. A tool that diffs a `.dssketch` read from git — where the UFOs it names are not on disk — can parse it without defcon or fontTools being imported. The converters and the `convert_*` functions are still importable from the package root; they are resolved on first access. defcon is imported only by the code that actually opens a UFO. `pip install dssketch` still installs everything: DesignSpace conversion remains a core feature, not an extra
- **Parsing no longer creates the user data directory**: `DataManager` used to `mkdir` `~/.config/dssketch` (or `$DSSKETCH_DATA_DIR`) as soon as it was constructed, which a parse does for discrete axes. It now creates the directory only when writing to it — `dssketch-data copy`, `save_user_data()`, `dssketch-data edit`
- **Dropped the unused `fontParts` dependency**: nothing in the package imported it. Family auto-detection reads the base UFO with defcon, as the docs now say

### Fixed
- **`DSSWriter` crashed on rules parsed from DSSketch**: a rule with a wildcard or a glyph list (`dollar* cent* > .rvrn`, `* > .rvrn`, `dollar cent > .heavy`) is a DSSketch-level statement; the parser keeps it as `pattern`/`to_pattern`, and it is expanded against UFO glyphs only on the way to DesignSpace. The writer only knew the expanded `substitutions` form it gets from a DesignSpace, and raised `IndexError` on the empty list. It now writes such rules back as written, so parse → edit → write works on any `.dssketch`
- `CLAUDE.md` error-handling example used `parser.errors` / `parser.warnings`, which do not exist; it is `parser.validator.errors` / `.warnings`
- **Stale `skip` rules in two examples**: `MegaFont-WithSkip.dssketch` and `TestFont-MultiElidable.dssketch` listed skip rules written against pre-1.1.17 instance names (`Extended`, `HighContrast`), so they silently stopped matching after "Weight axis excluded from elidable removal" changed the generated names. Updated to `Extended Regular` / `HighContrast Regular`, along with the comments in `TestFont-MultiElidable.dssketch` that still described the old elidable behaviour. The unused-skip-rule validation had been reporting this all along. `TestFont-SkipValidation.dssketch` keeps its unused rules — they are deliberate fixtures for that warning
- **Regenerated the seven instance-bearing examples** from their `.dssketch` sources, so `examples/*.designspace` no longer carry pre-1.1.17 instance names (`Compressed` where the generator now produces `Compressed Regular`). Instance counts are unchanged — 315, 300, 12, 14, 4, 9, 7 — because the stale skip rules were the actual cause. The eight examples that declare no instances (`avar1`, `avar2*`, `AmstelvarA2`, `RobotoDelta`) were deliberately left untouched: they are input fixtures from the fontTools test data, and regenerating them would downgrade `format="5.2"` to `5.1`, add redundant `<labelname>` elements and expand master locations

### Documentation
- `notes/roundtrip-fidelity-issues.md`: five open findings from a DS → DSSketch → DS audit of the example corpus, each with root cause, a verified candidate fix, and the design question it turns on. Records that DSSketch sits above DesignSpace rather than mirroring it — `instances auto` and `skip` are instructions to a generator, so `skip` cannot survive a round-trip through DesignSpace and must not be reconstructed from it. No code changes

## [1.1.18] - 2026-08-29

### Added
- **Unnamed avar map points**: an axis map entry that carries no STAT label is now expressible as `100 > 100` (bare user value, no style name). This supports axes that extend past their named styles — e.g. an axis declared `100:400:1000` whose named styles only span Thin(200)…Black(900). Such a point shapes the user→design curve but names no instance.

### Fixed
- **DS→DSS no longer drops unlabeled map points**: `_convert_axis()` branched `if axis.axisLabels: ... elif axis.map: ...`, so on an axis that had both, every `<map>` entry without a matching `<label>` was silently discarded — corrupting the avar curve at both ends. It now takes the union of map keys and label keys
- **Masters are no longer required to sit on a mapped point**: a master lives in design space and may be placed between named styles (e.g. a Bold master at design 625 while the Bold label maps to 575). This was a hard error; it is now a warning
- **Masters are no longer required to sit on the extreme *named* point**: masters are commonly drawn outside the named range so that every instance interpolates inside the master envelope rather than landing on a raw master. This was a hard error; it is now a warning
- Writer emitted a stray double space for a mapping with no label (`100  > 100`); it now writes `100 > 100`
- Silenced two noise sources for intentionally unnamed points: the "typically uses label" consistency warning now skips empty labels, and instance generation logs a missing label at DEBUG rather than WARNING

### Changed
- `uv.lock` no longer conflicts on every merge: added `.gitattributes` marking it `merge=binary linguist-generated=true`, and pinned `[tool.uv] required-version = ">=0.12.5"` so all machines re-serialize the lock identically. The lockfile stays tracked for reproducible dev environments (`uv sync`); it is not part of the built sdist/wheel, whose dependencies come from `[project.dependencies]`

### Documentation
- README: document installing DSSketch as a system-wide CLI in editable mode via `uv tool install -e .` (or `pipx install --editable`), and explain how it differs from `uv pip install -e .`, which only exposes the command inside the active virtualenv

## [1.1.17] - 2026-05-16

Releases 1.1.10 through 1.1.16 shipped without changelog entries; their changes are folded into this section.

### Added
- **Custom discrete axis support**: Any axis with `0:0:1` range now works as discrete (e.g., `LOOP discrete`, `FILL discrete`), not just `ital` and `slnt`
- **UFO layer support**: Sources can specify UFO layers via `@layer="layer_name"` flag, enabling multiple masters from a single UFO file
- **Multiple `@base` sources for discrete axes**: Each discrete axis value can have its own base source, validated automatically
- **Sparse master support**: Sources can be marked as sparse (correction layers with reduced glyph coverage) via `@sparse` flag. Bidirectional: DesignSpace `name="sparse.*"` ↔ DSSketch `@sparse`. Detection on DS→DSS also recognizes `*-sparse.ufo` filename suffix as fallback.

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
