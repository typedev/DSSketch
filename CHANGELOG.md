# Changelog

All notable changes to DSSketch will be documented in this file.

## [Unreleased]

## [1.4.0] - 2026-09-28

### Fixed
- **A variable font's default named instance could end up without a name**: a DesignSpace from DSSketch had no `elidedfallbackname`. fontmake and ufo2ft fill any instance whose localized names are empty with the names DS5 derives from the STAT labels (`splitInterpolable(makeNames=True)`), and with every label elided that name is empty — so SuperFont's Regular got an empty `fvar` name. DSS → DS now always writes `elidedfallbackname`: the weight axis's elidable label (`Regular`, `Book`, …), else `Regular`. DS → DSS reports a DesignSpace's own value only when it differs from that. The seven generated example DesignSpaces gain the attribute and nothing else

### Added
- **Upright is linked to Italic on the `ital` axis**: DSS → DS writes `linkeduservalue="1"` on the Upright label, so STAT gets the format-3 style link that compilers building STAT from the labels need (TDKit otherwise patches STAT itself). DS → DSS does not report this link as dropped data
- **Warning when the axes order puts a word after the weight**: `instances auto` names follow the order of the axes section, so `wght` before `wdth` gives "Bold Condensed". Compilers that read the weight from the style name expect it last or right before Italic/Slant — TDKit reads "Bold Condensed" as weight 400. The conversion report now says so (`INSTANCE_WEIGHT_NOT_LAST`) and names the axes to move. The `FontWithLayers` example had exactly this order and now lists width first ("Condensed Bold"); its sources are unchanged
- **`lang` — derived names in other languages**: a line `lang de, ru, es-419` makes DSS → DS write every name it derives from labels in those languages too — instance style names (the `fvar` subfamily and nameID 17), STAT label names and axis names — from `data/font-resources-translations.json` (16 languages; override with `dssketch-data copy font-resources-translations.json`). A style name is translated word by word, each word a label, in the order and with the elisions of the English name. Words without a translation stay in English and are reported per language (`DOCUMENT_TRANSLATION_MISSING`), as is a language the dictionary does not have. Hidden axes are left alone. DS → DSS writes `lang` back only when a DesignSpace's localized names are exactly the dictionary's; otherwise nothing is replaced and the differences are reported (`DOCUMENT_TRANSLATIONS_DIFFER`). The dictionary was completed for the standard labels it lacked: Hairline, Heavy, Ultra/Extra Condensed, Ultra Expanded/Extended, Upright (also for Roman), with Slant read as Slanted; label spelling no longer matters (`ExtraLight` = `Extralight` = `Extra Light`)

## [1.3.0] - 2026-09-28

### Added
- **ConversionReport for DSSketch → DesignSpace**: `convert_dss_string_to_designspace()` and `convert_to_designspace()` accept `return_report=True` and return `(designspace, report)`, like the other direction. The report holds the sketch's own validation messages (category `Sketch`) followed by what the conversion found — until now only logged, and the plain API leaves logging off: an explicit rule naming a glyph the default master lacks, wildcard substitutions skipped for a missing target (one issue per rule), a rule left out because nothing matched, an avar2 mapping naming an undefined axis (error: fontTools fails on it), a family name that could not be found
- **DesignSpace → DSSketch reports what the sketch does not carry**: DSSketch leaves some DesignSpace data out by design; it no longer does so silently. New issues cover the document `<lib>` (found in every real project we checked), `elidedFallbackName`, document location labels (STAT format 4), `<variable-fonts>`, rules `processing="last"` (which changes when substitutions apply), STAT label extras (ranges, linked values, older siblings, localized names), per-source overrides (family name, muted info/kerning/glyphs) and per-instance data `instances auto` does not generate. A PostScript name is only reported when it differs from the generated `Family-Style`. Nothing is transformed. New categories `Document` (4) and `Sketch` (5); all codes are exported from the package root

### Changed
- **Hidden axes are declared, never inferred**: DS → DSS used to hide every axis that appears only in avar2 outputs, overriding the DesignSpace — RobotoDelta went from 0 to 30 hidden axes of 39, AmstelvarA2-Roman's axes declared visible became hidden, and the axes were reordered. Only `hidden="1"` hides an axis now. A visible axis driven only by avar2 — usually a parametric axis meant to be hidden — is reported as a warning (`AXIS_OUTPUT_ONLY_VISIBLE`) with the fix, and left as the document says. The generated RobotoDelta examples were regenerated: 0 hidden axes, original axis order
- **An unknown family is left out instead of written as `family Unknown`**: DS → DSS now finds the default source with designspaceLib's `findDefault()`, which maps the axis defaults to design space; comparing source locations with the user-space defaults missed the default master on any mapped axis, and the RobotoDelta sketch was named "Unknown" although every source says "Roboto Delta". When no source or instance names a family, the sketch has no `family` line, so DSS → DS reads the name from the base UFO as it already could

### Fixed
- **Discrete axes are discrete because they say so**: DSS → DS made an axis discrete only if it was named `italic`/`ital`, so `slnt discrete` and every custom discrete axis (`SERF discrete` with Sans/Serif) came out as a continuous 0..1 axis and its masters interpolated. In the other direction, a discrete axis with three or more values was written as a `0:0:2` range, and converting it back failed on "multiple @base sources". `DSSAxis.values` now stores a discrete axis's values; parser, writer, validator and both converters read it instead of guessing from the range or the name. `discrete`/`binary` always means discrete; the numeric form `0:0:1` still does for `ital` only, as documented, and is an ordinary continuous axis elsewhere. A discrete value with no label survives DS → DSS as an unnamed point (`2 > 2`), and a label whose value is not its position is written in full (`5 Serif > 5`) so it parses back to the same value. Code that builds a `DSSAxis` by hand must now pass `values=[0, 1]` for a discrete axis; a bare 0:0:1 range is no longer taken as one
- **avar2 inputs are user space for every number, in both directions** — ⚠️ affects sketches converted from a DesignSpace by 1.2.1 or earlier. DSSketch documents avar2 inputs as user space, but DSS → DS mapped an input through the axis only when it hit a labeled point exactly: `[wght=550]` on an axis with `700 Bold > 625` stayed 550 instead of 512.5. DS → DSS, in turn, copied DesignSpace's design-space inputs without mapping them back, so a converted sketch read back correctly only because the two mistakes cancelled — and showed `opsz=-1` where it meant user 8. Both directions now map along the axis curve, and a label and its number always mean the same point.
  - **Migrating**: a sketch written by the old converter can hold design values on an axis that has a map. When such a value lies outside the axis's user range but inside its design range it is now an error that names the user value to write instead (`avar2 input opsz=-1 … The user value is opsz=8`). A design value that also lies inside the user range cannot be told apart, so the safe course is to reconvert such sketches from their DesignSpace. Sketches written by hand, or using labels, are unaffected
  - The `avar2-RobotoDelta-Roman` examples (matrix and linear) were regenerated: their inputs now read `opsz=8`, not `opsz=-1`, and they carry the sources' `@layer` flags that the old files predate. Their 38 mappings match the DesignSpace exactly
- **Omitted coordinates and avar2 `$` used the user-space default where design space is meant**: source locations and avar2 outputs are design space, but a source that left an axis out (`Regular @base`, or `Italic ital=Italic`) and an avar2 output `wght=$` got `axis.default`, the user value. With `Regular > 420` on a `Thin:Regular:Black` axis that put the master at 400 instead of 420 — an error for an `@base` source, an actively misleading "this is legal" warning for any other. Both now use the default's design value. The writer made the mirror-image mistake (it omitted a coordinate equal to the *user* default) and is fixed with it, so DS → DSS stops writing redundant values such as `opsz=0` on every source of the RobotoDelta example; every example keeps its exact master locations. `DSSAxis.get_design_value()` promised interpolation but returned its input unchanged; it now maps piecewise-linearly exactly like fontTools, with a matching `get_user_value()` and a `design_default` property
- **A rule's OR became an AND on DS → DSS**: a DesignSpace rule applies when any of its conditionsets matches, but the converter merged all of them into one AND-ed condition, so "(weight ≥ 700) or (width ≤ 80)" came out as "(weight ≥ 700) and (width ≤ 80)" — a different trigger, with no report entry. Each conditionset now becomes its own DSS rule with the same substitutions and name, which applies exactly where the original did (checked at every combination of the two regions)
- **Rule glyphs were checked against the wrong glyph set, or not at all**: a wildcard rule (`* > .rvrn`) was expanded against every source together, so a target present only in a `@sparse` master passed conversion and the build then failed in varLib ("Missing glyphs are referenced in conditional substitution rules"). Wildcards now expand against the default master(s) — the `@base` sources, one per discrete value — which is the set varLib checks; every other source is used only when no default master can be read. An explicit rule (`a > a.alt`) was never checked; it is now kept as written but reported when a glyph is missing from the default master. Without UFOs on disk nothing changes
- **Two mappings at one user value were accepted**: `300 LightA > 250` and `300 LightB > 350` on one axis gave the axis map two outputs for one input, and `instances auto` then dropped one label and placed the other at the wrong design value, with no warning. It is now an error naming both mappings
- **Explicit instance lines vanished without a word**: DSSketch generates instances from labeled mappings (`instances auto`) and does not list them, but a line such as `Bold [Black]` under `instances` was dropped silently (the parser branch was a `TODO … pass`). It is now reported as ignored, with a pointer to `instances auto`, `skip` and `instances off`
- **A label-based axis range was never checked for order**: `wght Black:Regular:Thin` produced an axis with minimum 900 and maximum 100. It is now an error, like the numeric `900:400:100`
- **`parser.validator.errors` lost the parsing-phase errors**: after a non-strict parse it held only the final validation's findings, while errors found line by line (bad coordinates, bad ranges) were logged and dropped. It now holds both, and so does `.warnings`

## [1.2.1] - 2026-09-28

### Fixed
- **Unquoted names with spaces were cut to their first word, silently**: `family Sans Pro` parsed as `Sans`, and the sources `My Font Light.ufo [Thin]`, `My Font Regular.ufo [Regular]` and `My Font Black` all became the same `My.ufo` — three masters pointing at one file that does not exist. An unquoted value is now taken whole; quoting (`family "Sans Pro"`) works as before and remains what the writer emits. Every example parses exactly as before. Reported from ufo-tdkit-report's `.dssketch` diffing

## [1.2.0] - 2026-09-27

### Added
- **`instances auto` fit report**: DS → DSSketch now checks that the generator actually reproduces the instances the DesignSpace declares, instead of assuming it. Three outcomes, reported separately because they mean different things: a declared position the generator never reaches (WARNING — the sketch cannot describe this design space), the same position under a different style name (WARNING — the DesignSpace may predate a change in the elidable rules), and positions the generator adds (INFO — the DesignSpace was filtered, which is what an `instances auto` / `skip` block expresses). Instances are matched by design-space **position**, never by style name: names diverge for reasons that are not losses, and name matching produced 90 phantom losses across the example corpus where position matching reported none. The report is purely diagnostic — it never alters the document and never synthesises a `skip` block, since `skip` instructs the generator while a DesignSpace records only the result of applying it. Warnings appear wherever DSSketch logging is set up, which the CLI does
- **`DSSAxisMapping.user_value_explicit`**: tells whether the `.dssketch` source wrote the user value (`300 Light > 295`) or it was inferred (`Light > 295` from the standards table, `Custom > 500` as user = design). An inferred value depends on the standards table shipped with the installed DSSketch, so a tool diffing two revisions can treat it as derived rather than as something the file says. The writer no longer compacts an explicit value away even when it equals the standard one: `400 Regular > 400` stays as written
- **Structured conversion report**: the findings above are no longer log prose only. `convert_designspace_to_dss_string()` and `convert_to_dss()` accept `return_report=True` and then return a `(result, ConversionReport)` tuple; `DesignSpaceToDSS.report` holds the same object. Each `ConversionIssue` carries a category, a stable numeric code (`"2.0"`, switchable), a severity, a description, longer details, a suggested fix, and the affected instances as `InstanceRef` objects with their design-space locations — plus `to_dict()` for a JSON-serialisable form. The shape follows the DesignSpace validator in Font Rover so a caller consuming those results can consume these the same way. Exported from the package root: `ConversionReport`, `ConversionIssue`, `InstanceRef`, `CATEGORY_INSTANCES`, `SEVERITY_*`, `INSTANCE_UNREACHABLE`/`RENAMED`/`EXTRA`. Fully backwards compatible — without the flag both functions return exactly what they did before

### Changed
- **Standard width values now follow the OpenType spec** — ⚠️ changes the meaning of existing files. The width table invented its own scale below Normal (Compressed 60, SemiCompressed 70, Condensed 80, SemiCondensed 90, Wide 115) and shifted names above it by one class (SemiExpanded = class 7 / 125, Expanded = class 8 / 150, ExtraExpanded = alias of Ultra / 200). It now uses the OS/2 `usWidthClass` "% of normal" column, which the spec gives as the mapping to `wdth`, and which CSS `font-width` shares: UltraCondensed 50, ExtraCondensed 62.5, Condensed 75, SemiCondensed 87.5, Normal 100, SemiExpanded 112.5, Expanded 125, ExtraExpanded 150, UltraExpanded 200. Spec names are canonical; Compressed, SemiCompressed, Narrow, Wide and the *Extended forms are aliases. Weight values were already correct.
  - **Who is affected**: a width mapping written without a user value (`Condensed > 380`, or a label range like `wdth Condensed:Normal:Extended`) now resolves to the spec value — here user 75 instead of 80. Mappings written with an explicit user value (`150 Wide > 700`) are unaffected. To keep the old value, write it out: `80 Condensed > 380`
  - The validator no longer reports an alias as a label mismatch (`Compressed` for UltraCondensed, and likewise `ExtraLight` for Extralight on weight, which it wrongly flagged before)
  - `stylenames.json` had the same shifted classes and is corrected too; `unified-mappings.json`, the fallback copy, is back in sync with the YAML
  - Examples: `FontWithLayers.dssketch` wrote `Condensed > 75` / `Wide > 125` on a `75:100:125` axis, i.e. it assumed the spec, and failed validation under the old table; it now uses `Expanded > 125` and converts. Both MegaFont sketches pin `60 Compressed > 0`, since their axis starts at 60. Regenerated `MegaFont-*` (Condensed now at user 75) and `TestFont-ElidableScenarios` / `TestFont-MultiElidable` (axis now ends at 125, not 150); instance names and counts are unchanged
- **Parsing no longer imports the UFO stack** (#7): `import dssketch`, `DSSParser`, `DSSWriter` and the document models now load only the stdlib and PyYAML. A tool that diffs a `.dssketch` read from git — where the UFOs it names are not on disk — can parse it without defcon or fontTools being imported. The converters and the `convert_*` functions are still importable from the package root; they are resolved on first access. defcon is imported only by the code that actually opens a UFO. `pip install dssketch` still installs everything: DesignSpace conversion remains a core feature, not an extra
- **Parsing no longer creates the user data directory**: `DataManager` used to `mkdir` `~/.config/dssketch` (or `$DSSKETCH_DATA_DIR`) as soon as it was constructed, which a parse does for discrete axes. It now creates the directory only when writing to it — `dssketch-data copy`, `save_user_data()`, `dssketch-data edit`
- **Dropped the unused `fontParts` dependency**: nothing in the package imported it. Family auto-detection reads the base UFO with defcon, as the docs now say

### Fixed
- **Python 3.8 and 3.9 could not import the package**: three return annotations used `float | None`, which needs 3.10, although `requires-python` has always said `>=3.8`. Replaced with `Optional[...]`; the test suite now passes on 3.8 through 3.14, and CI keeps it that way
- **`DSSWriter` crashed on rules parsed from DSSketch**: a rule with a wildcard or a glyph list (`dollar* cent* > .rvrn`, `* > .rvrn`, `dollar cent > .heavy`) is a DSSketch-level statement; the parser keeps it as `pattern`/`to_pattern`, and it is expanded against UFO glyphs only on the way to DesignSpace. The writer only knew the expanded `substitutions` form it gets from a DesignSpace, and raised `IndexError` on the empty list. It now writes such rules back as written, so parse → edit → write works on any `.dssketch`
- **One-sided rule conditions stay open**: `weight >= Bold` was closed at parse time with the largest mapping design value, so DSS → DSS rewrote it as `Bold <= weight <= Black`, and the rule silently stopped short once the axis was extended. The open bound is now kept as `None` all the way through: DesignSpace gets `<condition name="weight" minimum="725"/>`, which `designspaceLib` and `varLib` read as "to the end of the axis". DS → DSS likewise keeps a missing bound instead of inventing 0 / 1000. Compiled fonts are unchanged wherever the axis ends at its last mapping, which covers every example; the DesignSpace XML loses the redundant `maximum`/`minimum` attribute, as seen in the regenerated `MegaFont-3x5x7x3-Variable`, `MegaFont-WithSkip` and `SuperFont-6x2` examples
- `CLAUDE.md` error-handling example used `parser.errors` / `parser.warnings`, which do not exist; it is `parser.validator.errors` / `.warnings`
- **Stale `skip` rules in two examples**: `MegaFont-WithSkip.dssketch` and `TestFont-MultiElidable.dssketch` listed skip rules written against pre-1.1.17 instance names (`Extended`, `HighContrast`), so they silently stopped matching after "Weight axis excluded from elidable removal" changed the generated names. Updated to `Extended Regular` / `HighContrast Regular`, along with the comments in `TestFont-MultiElidable.dssketch` that still described the old elidable behaviour. The unused-skip-rule validation had been reporting this all along. `TestFont-SkipValidation.dssketch` keeps its unused rules — they are deliberate fixtures for that warning
- **Regenerated the seven instance-bearing examples** from their `.dssketch` sources, so `examples/*.designspace` no longer carry pre-1.1.17 instance names (`Compressed` where the generator now produces `Compressed Regular`). Instance counts are unchanged — 315, 300, 12, 14, 4, 9, 7 — because the stale skip rules were the actual cause. The eight examples that declare no instances (`avar1`, `avar2*`, `AmstelvarA2`, `RobotoDelta`) were deliberately left untouched: they are input fixtures from the fontTools test data, and regenerating them would downgrade `format="5.2"` to `5.1`, add redundant `<labelname>` elements and expand master locations

### Documentation
- `notes/roundtrip-fidelity-issues.md`: five open findings from a DS → DSSketch → DS audit of the example corpus, each with root cause, a verified candidate fix, and the design question it turns on. Records that DSSketch sits above DesignSpace rather than mirroring it — `instances auto` and `skip` are instructions to a generator, so `skip` cannot survive a round-trip through DesignSpace and must not be reconstructed from it. No code changes

### Infrastructure
- **CI** (`.github/workflows/ci.yml`): for every push to `main` and every pull request, builds the sdist and wheel, checks their metadata and that `uv.lock` is current, then installs the wheel on Python 3.8–3.14 and runs the tests against it — the published artifact, installed from its own metadata, not the source tree
- **Trusted publishing to PyPI** (`.github/workflows/publish.yml`): pushing a tag `vX.Y.Z` verifies it against `pyproject.toml`, `__init__.py` and a `## [X.Y.Z]` section in this file, runs CI on the tag, uploads to PyPI through OIDC — no API token stored anywhere — and creates the GitHub release with that changelog section as its notes. Uploads go through the `pypi` environment, which only `v*` tags may deploy to
- Classifiers list Python 3.13 and 3.14

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
