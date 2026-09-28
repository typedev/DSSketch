# DSSketch vs. the DesignSpace failure catalog (non-avar2 rows)

Scope: all rows in `~/WORK/designspace-lint/docs/audit/2026-09-coverage/failure-catalog.md`
except `AVAR2-*` (covered by another researcher). Categories: AXIS, LABEL, DISC, SRC, INST,
RULE, GLYPH, KERN, FEAT, ORDER, INFO — 128 rows total (counting `GLYPH-13†`/`INFO-07†`).

Method: read the full catalog and README, then read the DSSketch source in full
(`dss_parser.py`, `dss_validator.py`, `dss_writer.py`, `dss_to_designspace.py`,
`designspace_to_dss.py`, `instances.py`, `models.py`, `discrete.py`, `patterns.py`,
`core/validation.py`). Every **CAN INTRODUCE** claim below was reproduced with a minimal
`.dssketch` string run through `dssketch.convert_dss_string_to_designspace` (or the parser
directly), in `/tmp/.../validation/t_*.py`. Two used tiny defcon UFOs
(`validation/sources/*.ufo`, built by `make_ufos.py`) to reach fontTools' own
`_checkSubstitutionGlyphsExist`. Rows classified from code reading alone (no repro script)
say so explicitly.

Class legend: **PREVENTED** (syntax can't express it) · **CAUGHT** (parser/validator reports
it today) · **COULD CATCH** (cheap, not implemented) · **CAN INTRODUCE** (DSSketch's own
generation creates the failure) · **N/A** (belongs to a UFO linter / fontTools build step,
outside what DSSketch opens or generates).

---

## 1. The bugs that matter most — CAN INTRODUCE, ranked

### #1 — Wildcard/multi-glyph rules validate glyphs against the union of *all* sources, not the base master (RULE-17)

`DSSToDesignSpace._expand_wildcard_pattern` (`converters/dss_to_designspace.py:559`) builds
`all_glyphs` with `UFOGlyphExtractor.get_all_glyphs_from_sources(doc.sources, base_path)` —
every source, sparse masters included — then accepts any target that appears *anywhere* in
that union. fontTools' own `varLib.build()` starts the output font as
`deepcopy(master_fonts[ds.base_idx])` (base master only) and `_checkSubstitutionGlyphsExist`
checks against that fixed glyph order. A target that exists only in a sparse correction
master is a false all-clear.

Repro (`t_rule17.py` + `make_ufos.py`, sources under `validation/sources/`):
`Regular.ufo` has `dollar, cent` but not `dollar.rvrn`/`cent.rvrn`; `Bold-sparse.ufo` (marked
`@sparse`) has `dollar.rvrn, cent.rvrn`. Rule `* > .rvrn (weight >= Bold)` converts cleanly to
`[('cent', 'cent.rvrn'), ('dollar', 'dollar.rvrn')]` with no warning. Feeding the base
master's real glyph set to fontTools' own `_checkSubstitutionGlyphsExist` (`t_rule17_confirm.py`)
reproduces the exact failure this document ships to users:
`VarLibValidationError: Missing glyphs are referenced in conditional substitution rules: dollar.rvrn, cent.rvrn`.

### #2 — Explicit (non-wildcard) substitution rules get *zero* glyph validation

Worse than #1. `_convert_rule` (`dss_to_designspace.py:481`) only calls
`_expand_wildcard_pattern` — the only place any glyph check happens — `if dss_rule.pattern
and dss_rule.to_pattern`. A single-glyph rule (`dollar > dollar.rvrn (weight >= Bold)`, the
most common shape in every CLAUDE.md example and in `examples/SuperFont-6x2.dssketch:26`,
`MegaFont-3x5x7x3-Variable.dssketch:28`) never sets `.pattern`/`.to_pattern`
(`dss_parser.py:1184-1192`), so it takes the `else` branch and `dss_rule.substitutions` is
used completely unchecked.

Repro (`t_misc2.py`, TEST3): `zzz_nonexistent > zzz_nonexistent.alt (weight >= Bold)` — a
glyph pair that exists in *no* UFO at all — converts with `num rules: 1`,
`subs: [('zzz_nonexistent', 'zzz_nonexistent.alt')]`, no error, no warning.

### #3 — A discrete axis is only recognized if its *name* is literally "italic"/"ital"

`DSSToDesignSpace._convert_axis` (`dss_to_designspace.py:164-168`):
```python
is_discrete = (
    dss_axis.minimum == 0
    and dss_axis.maximum == 1
    and dss_axis.name.lower() in ["italic", "ital"]
)
```
Every other piece of the codebase treats "discrete" as a pure range test —
`DiscreteAxisHandler.is_discrete()` (`utils/discrete.py:16`, used by the parser to accept the
simplified `Upright`/`Italic` label syntax), the writer's own `is_discrete`
(`dss_writer.py:213`), and `DiscreteAxisHandler.DISCRETE_AXES = ["italic", "ital", "slant",
"slnt"]` all agree slant is discrete too. Only the converter that actually emits the
DesignSpace disagrees.

Repro (`t_discrete_slnt.py`): `slant slnt discrete` with `Upright`/`Slanted` labels, parsed
without error, round-trips through `instances auto` producing sensible instance names — but
`ds.axes[0]` comes out as a plain `AxisDescriptor` (`slnt`, `minimum=0.0`, `maximum=1.0`,
`values=None`), not a `DiscreteAxisDescriptor`. The two masters at `slnt=0` and `slnt=1` will
interpolate continuously in the compiled font — the opposite of what a discrete/non-interpolating
axis exists to guarantee, and exactly wrong if the two masters are not shape-compatible (the
usual reason to make an axis discrete in the first place). Same result for any custom
discrete axis, confirmed separately with `GRAD grad discrete` (`t_discrete_custom.py`).

### #4 — Two mapping labels sharing an explicit user_value corrupt the axis map, then silently drop one instance and mislocate the other (AXIS-05)

`_validate_duplicate_mapping_labels` (`dss_validator.py:226`) checks label-name uniqueness
across axes; nothing anywhere checks *user_value* uniqueness within one axis. The explicit
`user_value label > design` syntax (`dss_parser.py:563-579`) lets two different labels claim
the same user_value with different design values.

Repro (`t_dup_uservalue.py` + `t_dup_debug.py`): `300 LightA > 250` and `300 LightB > 350` on
one `wght` axis. Parses and converts cleanly. Two independent bugs compound:
- `axis.map` gets two tuples `(300.0, 250.0)` and `(300.0, 350.0)` — an AXIS-05 duplicate
  input, silently resolved by whichever tuple is later when something does `dict(axis.map)`.
- `getInstancesMapping()` (`core/instances.py:180-198`) matches each `axis.map` entry to the
  *first* `axisLabel` whose `userValue` equals that entry's user value and `break`s — so both
  map entries (250 and 350) resolve to the same first label, **"LightB" is silently dropped
  from instance generation entirely**, and "LightA" — the one that survives — gets
  `forwardMap[300.0]`, which is `350.0` (the *other* label's design value, because
  `dict(axis.map)` keeps the later tuple). Confirmed instance list: `LightA {'weight': 350.0}`
  — wrong location, and no `LightB` instance at all. Zero warnings anywhere.

### #5 — Coordinate-omission shorthand uses the axis's *user*-space default where a *design*-space value is required (AXIS-18)

`_parse_source_defaults_only` and `_parse_source_named` (`dss_parser.py:846-849, 880-885`)
fill every axis a source doesn't mention with `axis.default` — which is a **user**-space
number (DSSAxis.minimum/default/maximum are always user-space; see the MegaFont-style
`wght Thin:Regular:Black` / `Regular > 420` idiom in CLAUDE.md and in
`examples/MegaFont-3x5x7x3-Variable.dssketch:16`). `SourceDescriptor.location` must be
**design**-space. Whenever an axis's default user value maps to a different design value,
every source using the no-brackets or partial-named shorthand for that axis lands in the
wrong place.

Repro A (`t_default_space.py`): a lone `Regular @base` source (shorthand, no brackets) with
`wght Thin:Regular:Black`, `Regular > 420` (user 400 → design 420) is correctly *rejected*:
`_validate_structure`'s base-source check independently recomputes the true default via
`_get_default_coordinates()` (which does look up the mapping) and raises `CRITICAL: Base
source 'Regular' coordinates [400.0] do not match default coordinates [420.0]`. Good — this
path is defended.

Repro B (`t_default_space2.py`/`t_default_space3.py`): the *non-base* source
`RegularItalic ital=1` (named shorthand, omits `weight`) is **not** defended the same way. It
lands at `weight=400.0` (should be `420.0`), and the only diagnostic is a soft, actively
misleading warning: *"Source 'RegularItalic' coordinate 400.0 on axis 'weight' does not sit
on a mapped point. Closest mapping 'Regular' is at 420.0. **This is legal** - masters live in
design space and may be placed between named styles."* — worded for the legitimate
"master intentionally between named styles" case, but here it is masking an authoring
accident from the exact same shorthand syntax CLAUDE.md recommends.

### #6 — A backwards label-based axis range skips ordering validation and produces an inverted axis

`validate_axis_range()` (numeric min≤default≤max check) is skipped whenever
`is_label_based` is true (`dss_parser.py:359-362, 409-412, 489-492`), because label-based
ranges resolve through `_resolve_axis_range_value` instead. Nothing re-checks ordering after
resolution.

Repro (`t_batch2.py` "reversed-label-range" + `t_reversed_full.py`): `wght Black:Regular:Thin`
(labels written backwards) parses in non-strict mode and converts to
`AxisDescriptor(minimum=900.0, default=400.0, maximum=100.0)` — an inverted axis that would
crash `fontTools.varLib.models.normalizeValue()`'s `lower <= default <= upper` assertion the
moment anything normalizes a location. In *strict* mode the run does fail, but with three
misleading per-mapping errors ("mapping 'Thin' has user_value 100.0 ... outside the axis
range [900.0, 100.0]") that blame the mappings, not the one real cause (the range itself is
backwards).

### #7 — Hand-written explicit instances are silently dropped, with no diagnostic at all

`_parse_instance_line` (`dss_parser.py:1011-1040`) fully implements `auto`, `off`, and `skip`
handling, but the branch for anything else is:
```python
if line != "auto" and not self.in_skip_subsection:
    # TODO: implement explicit instance parsing if needed
    pass
```
`DSSInstance`, `DSSDocument.instances`, and `DSSToDesignSpace._convert_instance` all fully
support explicit instances on the model/converter side — the parser is the only piece that
never got built. Any `instances` section that is not `auto`/`off`/a `skip` list is silently
worth nothing.

Repro (`t_more.py`, TEST A): an `instances` section with one fully-specified explicit instance
line parses with `doc.instances == []`, converts to a DesignSpace with `0` instances, and
`parser.validator.warnings == []`.

### #8 — No source/instance location is ever checked against its axis's declared range or against other sources (SRC-02/03/04, INST-03, DISC-10)

Nothing in `dss_validator.py` computes `axis.minimum <= v <= axis.maximum` for a source or
instance location independent of whether it sits on a *mapped* point.
`_validate_source_coordinate_consistency` explicitly skips axes with no mappings
(`if not axis.mappings: continue`), and even where mappings exist it only ever produces a
**warning**, never an error, and never for values wildly outside the axis (it just reports
the nearest mapping).

Repro 1 (`t_src04.py`): axis `ZROT 0:0:90` (no mappings), source at design value `500` — 5.5×
past the declared maximum — converts with zero warnings and zero errors.
Repro 2 (`t_dup_location.py`): two distinct non-base sources (`BlackA`, `BlackB`) both placed
at `weight=900.0` — an exact duplicate, non-default location — convert cleanly, no diagnostic.
fontTools would reject both at `varLib.build()` time (`VarLibValidationError: ... out-of-range
location`, and `VariationModelError: Locations must be unique.` respectively) with messages
that don't even name the offending source; DSSketch has every piece of information needed to
catch both instantly, for free, at conversion time, and currently catches neither.

---

## 2. Top 10 COULD-CATCH proposals (cheap, DS+axes-only unless noted)

1. **Source/instance range-bounds check** — for every source and instance, compute the
   design→user value (via `axis.map_backward`-equivalent for continuous axes, direct compare
   for discrete) and flag anything outside `[axis.minimum, axis.maximum]`. Closes #8's
   SRC-04/INST-03/DISC-10 gap. Near-zero false-positive risk (fontTools rejects it anyway);
   severity: error.
2. **Duplicate source-location check** — flag two sources (or a source and the implicit
   default) sharing the same full design-space location. Closes #8's SRC-02/03 half.
   Severity: error, zero false-positive risk.
3. **Duplicate user_value within one axis** — extend `_validate_duplicate_mapping_labels`'s
   sibling logic to also collect `(axis, user_value) -> [labels]` and flag `len(labels) > 1`.
   Closes #4 (AXIS-05). Severity: critical (it corrupts both the map and instance
   generation).
4. **Axis map monotonicity check** — after resolving all mappings, verify design values are
   non-decreasing as user values increase (or catch the AXIS-05 duplicate-input case
   generally, not just the user_value-duplicate case #3 already covers). Severity: warning
   (a genuinely reversed local map segment is rare but real); moderate false-positive risk if
   an axis intentionally has a locally flat segment (design value repeated for two adjacent
   user values) — allow equal, only flag strictly decreasing.
5. **Rule condition range-order check** — reject or warn on `minimum > maximum` in a
   `<= axis <=` range condition, mirroring fontTools' RULE-02 build-time check. Trivial:
   compare the two resolved floats in `_parse_condition_string`. Zero false-positive risk.
6. **Apply axis-range ordering validation to label-based ranges too** — after
   `_resolve_axis_range_value` resolves all three parts, re-run the same
   `min <= default <= max` check numeric ranges already get. Closes #6. Zero false-positive
   risk (a font's own axis genuinely can't have max < min).
7. **Validate rule glyphs against the base master specifically, not the union of sources** —
   in `_expand_wildcard_pattern`, extract the base master's glyph set separately (it's already
   known: `dss_source.is_base`) and warn (or error) when a substitution's source or target
   glyph exists in the union but not in the base master specifically. Also extend the same
   check to the currently-unvalidated explicit-substitution path. Closes #1/#2. This is the
   single highest-value fix in this whole report: it turns two silent false-all-clears into
   an actionable error before a build ever runs. Low false-positive risk — a rule referencing
   a glyph that is genuinely absent from the base master by design (rare, and arguably itself
   worth a warning) is the only edge case.
8. **Warn or error on any non-`auto`/`off`/`skip` content in an `instances` section** — even
   without implementing full explicit-instance parsing, detecting "this line was ignored"
   and surfacing it removes a silent, total feature no-op. Closes #7. Zero false-positive
   risk.
9. **unitsPerEm consistency across source UFOs** — `UFOValidator` already opens every source
   UFO to check `metainfo.plist`/`fontinfo.plist`/`glyphs` presence; comparing
   `font.info.unitsPerEm` (and arguably `ascender`/`descender` sign consistency) across all
   sources is nearly free from the same pass and guards against the catalog's own INFO-01,
   one of its "10 most dangerous silent failures." Severity: error (a genuine unitsPerEm
   mismatch silently misinterprets every non-default master's outline scale).
10. **Design/user-space heuristic on numeric rule conditions** — when a bare numeric condition
    value exactly equals a *user*-space label value that differs from that axis's *design*
    value at the same label, warn "this looks like a user-space value; rule conditions are
    design-space" (RULE-01). Necessarily heuristic and opt-in-strength only (a numeric
    condition that happens to coincide with a user value by design is legitimate), but the
    false-positive cost is a warning, and CLAUDE.md already documents this exact trap as a
    common real mistake.

Runner-up, lower priority: duplicate custom-axis **tag** across axes (AXIS-07) currently
surfaces only as a confusing, unrelated-looking coordinate-count/base-mismatch error (verified
in `t_batch2.py` "dup-custom-tag") rather than a direct "duplicate tag" message — worth a
direct check purely for error-message quality, not because anything currently slips through
silently.

---

## 3. Per-row table

Legend for the **evidence** column: `[T]` = reproduced with a script in this pass (see file
names above/below); `[C]` = classified from direct code reading only, not separately
scripted; `[S]` = spec/catalog reasoning only (feature does not exist in DSSketch).

### AXIS (18 rows)

| row | class | evidence | proposal |
|---|---|---|---|
| AXIS-01 non-monotonic map | COULD CATCH | `[C]` no monotonicity check anywhere on resolved `axis.map` | proposal #4 |
| AXIS-02 map missing at minimum | CAUGHT | `[T]` `_check_axis_extremes_coverage` (`dss_validator.py:851`) — error "missing mapping for minimum value" | — |
| AXIS-03 map missing at maximum | CAUGHT | `[T]` same function, "missing mapping for maximum value" | — |
| AXIS-04 map missing at default | CAUGHT | `[C]` same function also checks `default` | — |
| AXIS-05 duplicate map input, different outputs | **CAN INTRODUCE** | `[T]` finding #4 above | proposal #3 |
| AXIS-06 map output pushes source outside range | COULD CATCH | `[C]` no `map_backward`-style check exists; folds into finding #8 | proposal #1 |
| AXIS-07 duplicate tag across axes | COULD CATCH | `[T]` `t_batch2.py` "dup-custom-tag": no direct check; cascades into a confusing coordinate-mismatch error instead of a clear message | runner-up above |
| AXIS-08 missing `default` attribute | PREVENTED | `[C]` `DSSAxis` dataclass requires all three of minimum/default/maximum; DSS grammar has no axis form that omits a value | — |
| AXIS-09 default outside [min,max] | CAUGHT for numeric ranges / **CAN INTRODUCE** for label-based ranges | `[T]` numeric: `validate_axis_range` orders min≤default≤max; label-based: skipped, see finding #6 | proposal #6 |
| AXIS-10 min > max (reversed) | same as AXIS-09 | `[T]` finding #6 | proposal #6 |
| AXIS-11 min == max (degenerate) | CAUGHT (stricter than fontTools) | `[C]` `dss_validator.py:129-132`: `CRITICAL: Axis ... has invalid range (min = max = ...)` — fontTools itself tolerates this via `normalizeValue`'s early return; DSSketch forbids it outright | — |
| AXIS-12 non-numeric discrete `values` | PREVENTED | `[S]` discrete axes are always the hardcoded pair `[0,1]`; there is no DSSketch syntax for an arbitrary `values=` list at all (also means DSSketch cannot express a >2-value discrete axis — a feature gap, not a validation gap) | — |
| AXIS-13 discrete default not in `values` | PREVENTED | `[C]` discrete axis default is hardcoded to `0` (`dss_parser.py:373-374`), always a member of `[0,1]` | — |
| AXIS-14 discrete `values` out of order | N/A | `[S]` no user-editable `values` list exists | — |
| AXIS-15 axis-subset range on discrete axis | N/A | `[S]` DSSketch has no `<variable-fonts>`/`<axis-subset>` support at all | — |
| AXIS-16 `hidden="1"` not hidden from STAT | N/A | `[C]` DSSketch correctly sets `axis.hidden = True`; the STAT-builder gap is fontTools-internal and outside DSSketch's output | — |
| AXIS-17 parametric axis not marked hidden | mostly PREVENTED | `[C]` DS→DSS auto-detects avar2-output-only axes and re-classifies them hidden (`_determine_hidden_axes`); DSS→DS always sets `hidden=True` for anything placed under `axes hidden`. A user can still choose to expose such an axis deliberately — that is a choice, not a bug | — |
| AXIS-18 user-space value used for a source's design location | **CAN INTRODUCE** (non-base) / CAUGHT (base) | `[T]` finding #5 above | proposal follows #5's own logic: extend the `_get_default_coordinates`-based check to every source, not only `@base` |

### LABEL (16 rows)

| row | class | evidence | proposal |
|---|---|---|---|
| LABEL-01 missing default "en" `labelNames` | PREVENTED | `[C]` every axis conversion path (`_convert_axis`, `_convert_hidden_axis`) always sets `labelNames = {"en": ...}`; DSSketch has no syntax for other-language-only names | — |
| LABEL-02 dangling `linkedUserValue` | N/A | `[S]` no `linkedUserValue`/linked-label syntax exists in DSSketch | — |
| LABEL-03 duplicate label name, same axis | CAUGHT | `[T]` `t_batch2.py` "dup-label-same-axis": `_validate_duplicate_mapping_labels` fires (message text is confusing — repeats `'weight' (wght)` twice since both entries are literally the same axis — but the CRITICAL failure is correct) | minor: word the message differently when all colliding entries share one axis |
| LABEL-04 duplicate top-level location-label name | N/A | `[S]` no free-standing `<labels>`/`LocationLabelDescriptor` syntax in DSSketch | — |
| LABEL-05 instance references unknown location label | N/A | `[S]` same — instances always carry an explicit `location` dict, never a label reference | — |
| LABEL-06 top-level label given design location | N/A | `[S]` no top-level labels | — |
| LABEL-07 no label matches a user value (debug-level silent) | mostly N/A | `[C]` `instances auto` only ever visits locations *derived from* the labels themselves, so this can't arise there; the one path where it could (a hand-written instance at an arbitrary location) is swallowed entirely by finding #7 instead | see proposal #8 |
| LABEL-08 fully-elidable location → empty style name | PREVENTED | `[T]` `t_more.py` TEST B: the `if cleaned:` guard in `createInstances` (`instances.py:397`) rejects any removal that would leave an empty string, so the last surviving word can never be stripped; also weight is always excluded from elision when present | — |
| LABEL-09 `elidedFallbackName` silent default | N/A | `[C]` DSSketch never sets it and never builds STAT itself; this is a `varLib.stat.buildVFStatTable`-internal default, outside DSSketch's output surface | — |
| LABEL-10 duplicate `axisOrdering` | PREVENTED | `[C]` `sortAxisOrder()` assigns `axisOrdering = idx` sequentially over the DSS-declared axis list — always unique by construction | — |
| LABEL-11 ranged label + `linkedUserValue` together | N/A | `[S]` DSSketch has neither ranged labels (`userMinimum`/`userMaximum`) nor `linkedUserValue` | — |
| LABEL-12 unknown label attribute (positive control) | N/A | `[S]` DSSketch builds fontTools objects directly, never hand-writes arbitrary XML attributes, so it cannot introduce or need to guard against this reader-side check | — |
| LABEL-13 instance with no default English style name | PREVENTED (auto path) | `[C]` `instances auto` always derives a non-empty `styleName` from label text; the explicit-instance path that could violate this is swallowed by finding #7 instead of reaching the DesignSpace at all | — |
| LABEL-14 STAT-derived names override explicit instance names | N/A | `[S]` UNVERIFIED fontTools-internal bug (#4206), unrelated to anything DSSketch controls | — |
| LABEL-15 unexpected `fvar` instance names | N/A | `[S]` UNVERIFIED fontTools-internal bug (#3131) | — |
| LABEL-16 name-table dedup gaps | N/A | `[S]` UNVERIFIED fontTools-internal (#1648), name-table byte-level concern | — |

### DISC (12 rows)

DSSketch has no `<variable-fonts>`/`<axis-subset>` support at all, which removes most of this
category outright (DISC-01/03/04/05/07/11/12 are N/A). The `values` list for a discrete axis
is always the hardcoded pair `[0, 1]` (DISC-06/08/09 PREVENTED). The one row that does apply,
DISC-10, is really the same gap as finding #8 (SRC-04/INST-03), generalized to discrete axes.

| row | class | evidence | proposal |
|---|---|---|---|
| DISC-01 `values=` in pre-v5 doc | PREVENTED | `[C]` DSSketch never authors raw XML `format=`; fontTools' own writer bumps it automatically whenever a `DiscreteAxisDescriptor` is present | — |
| DISC-02 unsplit discrete doc fed to `build()` directly | N/A | `[S]` DSSketch never calls `varLib.build()`/`load_designspace()` itself; this is downstream tooling's responsibility. Worth a documentation note ("discrete-axis DesignSpaces need `build_many`, not `build`"), not a code fix | — |
| DISC-03 `userDefault=0` falsy bug | N/A | `[S]` no axis-subset support | — |
| DISC-04 axis-subset names unknown axis | N/A | `[S]` no axis-subset support | — |
| DISC-05 range subset on discrete axis | N/A | `[S]` no axis-subset support | — |
| DISC-06 discrete default not in `values` | PREVENTED | `[C]` same as AXIS-13 | — |
| DISC-07 axis-subset `userValue` typo | N/A | `[S]` no axis-subset support | — |
| DISC-08 duplicate `values` entries | PREVENTED | `[C]` `values` is always the literal `[0, 1]`, never user-editable text | — |
| DISC-09 single-value discrete axis | PREVENTED | `[C]` `values` is always exactly two entries | — |
| DISC-10 source at undeclared discrete value | **CAN INTRODUCE** | `[T]` same mechanism as finding #8 — no bounds check on any axis, discrete included; a discrete-axis source at e.g. `2` when only `0`/`1` are declared gets, at best, the same soft "closest mapping" warning `_validate_source_coordinate_consistency` gives any other axis | proposal #1 |
| DISC-11 `getVariableFonts()` all-or-nothing | N/A | `[S]` DSSketch never emits `<variable-fonts>` | — |
| DISC-12 STAT scoping to top-level doc | N/A | `[S]` no VF splitting | — |

### SRC (14 rows)

| row | class | evidence | proposal |
|---|---|---|---|
| SRC-01 no source at default | CAUGHT | `[T]` `_validate_structure`'s base-source detection/validation (`t_default_space.py` shows the mismatch path; the "no base found at all" path raises the sibling CRITICAL) | — |
| SRC-02 >1 source at default | CAUGHT (via `@base` only) | `[T]` `t_misc.py` TEST1: two `@base` sources on a continuous axis → CRITICAL. Two accidental non-`@base` sources landing on the true default by coordinate coincidence are **not** separately checked | fold into proposal #2 |
| SRC-03 two sources, same non-default location | **CAN INTRODUCE** | `[T]` finding #8, `t_dup_location.py` | proposal #2 |
| SRC-04 source/instance out of mapped range | **CAN INTRODUCE** | `[T]` finding #8, `t_src04.py` | proposal #1 |
| SRC-05 location axis name unknown at consolidation | mostly PREVENTED | `[C]` `_find_axis_by_name_or_tag`/`_tag_to_axis_name` resolve every axis reference at parse time against `document.axes`/`hidden_axes`; an unresolvable named-coordinate axis is reported (`Unknown axis '...' in source`, `dss_parser.py:893`). A positional coordinate can't reference a wrong axis name at all (index-based) | — |
| SRC-06 source given user-space location instead of design | PREVENTED | `[S]` DSSketch source coordinates are always documented and treated as design-space; the *reverse* mistake (finding #5, using a user-space *default* to fill a *missing* design coordinate) is the DSSketch-specific variant of this exact confusion | see AXIS-18 |
| SRC-07 `copy*`/`mute*` flags are no-ops for `varLib.build` | N/A, but worth a doc note | `[C]` DSSketch always sets `copyLib/copyInfo/copyGroups/copyFeatures = True` on the base source only (`dss_to_designspace.py:420-424`) and exposes no DSS syntax to set these per-source, so it can't introduce this confusion — but see the catalog's own note that this pattern is "one of the most likely sources of false confidence for DSSketch-adjacent tooling"; CLAUDE.md doesn't currently say these flags matter only outside `varLib.build()` | documentation only |
| SRC-08 `layer=` source without a `font` object | N/A | `[S]` call-site concern for whoever runs `varLib.load_masters` directly; DSSketch just sets `layerName` | — |
| SRC-09 source file doesn't resolve | CAUGHT (separately, in `UFOValidator`) | `[C]` `UFOValidator.validate_ufo_files` (`core/validation.py:39`) checks every source path exists; not run automatically inside `convert_dss_string_to_designspace`/API calls, only via CLI/explicit call | note: the plain API path (`dssketch.convert_to_designspace`) does not call `UFOValidator` at all — a source pointing at a missing UFO produces a DesignSpace that references a nonexistent file with zero diagnostic from the API surface |
| SRC-10 same filename, different `layer=`, non-layer-aware opener | N/A | `[S]` downstream opener behavior, not a DSSketch decision | — |
| SRC-11/12 empty glyph vs. sparse-omitted glyph ambiguity | N/A | `[S]` requires per-glyph outline inspection across masters — belongs to a UFO/interpolation linter | — |
| SRC-13 localized names on a source are inert for `varLib.build` | N/A | `[S]` DSSketch doesn't expose per-source localized names | — |
| SRC-14 unnamed source gets an auto temp-name | N/A | `[S]` DSSketch always assigns `source.{n}`/`sparse.{n}` itself (`dss_to_designspace.py:390-393`); this is a different, always-present naming scheme, not the reader's fallback | — |

### INST (9 rows)

| row | class | evidence | proposal |
|---|---|---|---|
| INST-01 instance no default English style name | PREVENTED (auto) | `[C]` see LABEL-13 | — |
| INST-02 instance gives both location forms | N/A | `[S]` no `location="label"` instance syntax; only explicit `location` dicts, and those are currently unparsed anyway (finding #7) | — |
| INST-03 instance location out of range | **CAN INTRODUCE** | `[T]` same as finding #8 (SRC-04), applies identically to instance locations produced by `createInstances()`'s forward-map lookup — an instance placed via a corrupted map (finding #4) is a concrete case of this | proposal #1 |
| INST-04 instance at undeclared discrete value | see AXIS-08/DISC-10 | `[C]` folded per catalog's own note | proposal #1 |
| INST-05 instance style name collides with existing nameID 2 text off-default | N/A | `[S]` build-time `name`-table bookkeeping fontTools does internally | — |
| INST-06 instance discrete coordinates filtered from `fvar` | N/A (correct, documented fontTools behavior) | `[S]` not something DSSketch's output triggers incorrectly | — |
| INST-07 PS name not validated for legality/uniqueness | COULD CATCH (very low priority) | `[C]` `createInstance()` (`instances.py:253-261`) builds PS names by naive space-stripping with no character-set or length check; duplicates could only arise from a label containing an internal space colliding with two concatenated single-word labels (labels with spaces are syntactically possible even though CLAUDE.md recommends camelCase) | cheap: reject/normalize labels containing whitespace at parse time |
| INST-08 duplicate style names, different locations | mostly PREVENTED | `[C]` distinct label combinations only produce identical style-name text if labels collide, which is already CRITICAL-blocked across axes; the one way to still hit this is finding #4's duplicate-user_value corruption, or an axis label containing internal whitespace (INST-07) | folds into #3/#4 and INST-07 |
| INST-09 instance-level `<lib>/<info>/<glyphs>/<kerning>` are no-ops for the VF | N/A | `[S]` DSSketch exposes no such per-instance overrides at all | — |

### RULE (24 rows)

| row | class | evidence | proposal |
|---|---|---|---|
| RULE-01 user-space value used where design-space required | PREVENTED for label-based conditions / COULD CATCH for numeric | `[C]` `_resolve_condition_value` resolves a label straight to `mapping.design_value` — by construction, `weight >= Bold` cannot be user/design-confused. A bare number typed by hand still can be | proposal #10 |
| RULE-02 condition minimum > maximum | **CAN INTRODUCE** | `[T]` finding not separately listed above but confirmed in `t_misc2.py` TEST2: `(700 <= weight <= 400)` converts to `conditionSets=[[{'minimum': 700.0, 'maximum': 400.0}]]` verbatim, no diagnostic | proposal #5 |
| RULE-03 condition min == max (degenerate point) | COULD CATCH (low value) | `[C]` no check; legal per spec, same as fontTools — matches the catalog's own "not wrong, just a de-facto no-op" framing | low priority: warn only if writing a min==max condition from a numeric literal (not from `==` label syntax, which is intentional) |
| RULE-04 condition references undefined axis | CAUGHT | `[T]` `_find_axis_name_in_designspace` (`dss_to_designspace.py:513-546`) raises `ValueError: Rule references axis '...' which is not defined ...` — confirmed by CLAUDE.md's own documented test suite and consistent with code read | — |
| RULE-05/06 overlapping conditionsets, declaration-order winner | COULD CATCH | `[C]` no geometric overlap detection between rules exists anywhere in DSSketch | worth adding: intersect every pair of rules' resolved condition boxes and flag when they share a target glyph — same DS-XML-alone geometry the catalog describes |
| RULE-07 condition box outside axis range | folds into finding #8 | `[C]` conditions use `_get_design_space_bounds`-derived resolution but nothing checks the *result* against the axis's own design extremes | proposal #1 (extend to rule conditions) |
| RULE-08 substitution target glyph missing | **CAN INTRODUCE** (false all-clear) | `[T]` finding #1/#2 | proposal #7 |
| RULE-09 substitution source glyph missing | **CAN INTRODUCE** | `[T]` same code path — `from_glyph` is never checked to exist anywhere, wildcard or explicit | proposal #7 |
| RULE-10/11 rvrn vs rclt tag choice / no per-rule tag | N/A | `[S]` DSSketch has no per-rule or document-level `processing=` control surface at all (not found anywhere in the parser/converter) — same document-wide-only limitation as fontTools itself, inherited rather than introduced | feature gap, not a validation gap |
| RULE-12 empty conditionset dropped on write | N/A | `[S]` DSSketch never authors an empty conditionset — every rule condition list is built directly from parsed conditions, and a rule with zero conditions is exactly "match everywhere," which DSSketch expresses correctly (`rule.conditionSets` only set `if dss_rule.conditions:`, so a ruleless-condition DSS rule intentionally gets no conditionSets at all — see RULE-13 below for what that means) | — |
| RULE-13 rule with zero conditionsets is permanently inert | **CAN INTRODUCE** (unlikely but real) | `[C]` a DSSketch rule line with no `(...)` at all fails DSSketch's own rule-syntax regex (`_parse_rule_line` requires the `\(([^)]+)\)` group), so this specific shape can't currently be authored through normal syntax — but `_convert_rule` (`dss_to_designspace.py:498`) only adds `conditionSets` `if dss_rule.conditions:`; a rule whose *only* condition failed to parse (e.g. an invalid label inside `()`, logged as an error but not necessarily fatal in non-strict mode) leaves `dss_rule.conditions == []`, producing exactly this dead-rule shape silently in non-strict mode | in non-strict mode, a rule that loses all its conditions to parse errors should be dropped (like the existing "no valid substitutions" skip) rather than kept with empty conditionSets |
| RULE-14 multiple conditionsets, OR semantics | N/A (positive control, not reachable) | `[S]` DSSketch only ever emits one conditionset per rule (`rule.conditionSets = [[]]`, `dss_to_designspace.py:499`) — DSSketch has no syntax for OR'd conditionsets on one rule at all | feature gap |
| RULE-15/16 discrete-axis rule conditions need the split pipeline | N/A / interacts with finding #3 | `[C]` DSSketch never calls `build_many`/`splitInterpolable` itself (downstream concern) — but note a rule condition on an axis affected by finding #3 (discrete axis silently downgraded to continuous) will behave as an ordinary continuous-axis condition instead of being pruned per discrete value, compounding #3's severity | see #3 |
| RULE-17 sparse-master glyph existence (base-master-only) | **CAN INTRODUCE** | `[T]` finding #1, exact match to this row | proposal #7 |
| RULE-18 rename pipelines between UFO names and build glyph order | N/A | `[S]` DSSketch validates against UFO glyph names directly; any renaming happens in a downstream build step DSSketch doesn't see | — |
| RULE-19/20 re-adding FeatureVariations / table version conflicts | N/A | `[S]` `varLib`-internal, only reachable by calling its lookup-merging functions twice — DSSketch never calls them | — |
| RULE-21 rule valid for the doc but not for one DS5 multi-VF subset | N/A | `[S]` no `<variable-fonts>` support | — |
| RULE-22 invalid `processing=` value (positive control) | N/A | `[S]` no `processing=` surface exposed by DSSketch | — |
| RULE-23 condition with neither bound (positive control) | PREVENTED | `[C]` `_parse_condition_string`'s regexes require an operator and a value; a condition string that specifies neither a `>=`/`<=`/`==` nor a range simply matches neither regex and is silently ignored (produces no condition dict) rather than reaching fontTools' reader — different failure shape (silently fewer conditions) but the malformed condition can't reach the DesignSpace as an invalid `<condition>` element | worth a warning when a condition-string clause matches neither pattern (currently silent) |
| RULE-24 wildcard fan-out amplifies every other rule failure | **CAN INTRODUCE**, same root cause as #1/#2 | `[T]` confirmed structurally: `examples/MegaFont-3x5x7x3-Variable.dssketch:27` and `SuperFont-6x2.dssketch:25` both use `* > .rvrn` / `dollar* cent* > .rvrn` in real, shipped examples — the exact pattern finding #1 exploits | proposal #7 |

### GLYPH (13 rows incl. `GLYPH-13†`)

DSSketch opens UFOs only to extract glyph *names* (`UFOGlyphExtractor`, for rule wildcard
matching) and basic structural presence (`UFOValidator`). It never reads point lists,
contour/component structure, anchors, or advance widths. Per the task's own design
principle — DSSketch's natural job stops at what it already opens — essentially this whole
category is out of scope.

| row | class | evidence |
|---|---|---|
| GLYPH-01…05 point/contour/component/on-curve compatibility | N/A — belongs to a UFO/interpolation linter (`fontTools.varLib.interpolatable`, fontmake's `CompatibilityChecker`) |
| GLYPH-06/07 `.notdef` synthesis, glyf-vs-CFF2 merge asymmetry | N/A — compiled-binary/ufo2ft concern |
| GLYPH-08 empty glyph vs. sparse-omitted ambiguity | N/A — same, though see SRC-11/12 |
| GLYPH-09 `USE_MY_METRICS` inconsistency | N/A — component-flag/build concern |
| GLYPH-10 glyph missing from a non-sparse master | COULD CATCH, cheap, in scope | `UFOGlyphExtractor` already opens every source UFO for rule wildcard matching; a name-set diff across non-sparse sources (excluding `@sparse`-flagged ones) is nearly free from that same pass and is a real, common authoring mistake (a glyph added to one master and forgotten in another) |
| GLYPH-11/12 anchor set / ligature-anchor mismatches | N/A — belongs to a UFO linter (mark/anchor structure) |
| GLYPH-13† gvar-sparse vs. HVAR-sparse sentinel mismatch (0xFFFF) | N/A — compiled-binary concern, invisible at the UFO/DesignSpace level |

### KERN (6 rows)

DSSketch never reads `kerning.plist`/`groups.plist`. The "already opens UFOs" exception used
for GLYPH-10 is weaker here since kerning compatibility needs full group-membership diffing, a
meaningfully larger scope than a glyph-name set. Not recommended as a DSSketch feature.

| row | class | evidence | proposal |
|---|---|---|---|
| KERN-01 one master has zero non-zero kerning pairs | N/A | `[S]` requires reading `kerning.plist` per master; belongs to ufo2ft/a UFO linter | — |
| KERN-02 differing kern-subtable count per master | N/A | `[S]` internal ufo2ft kern-splitter heuristic, unreachable from DS/UFO metadata | — |
| KERN-03 pair absent in one master (non-failure baseline) | N/A (correct, not a failure) | `[S]` UFO kerning-cascade semantics; DSSketch never touches kerning so cannot get this wrong | — |
| KERN-04 kerning group membership differs per master | N/A | `[S]` requires `groups.plist` diffing, belongs to a UFO linter | — |
| KERN-05 kerning pair references a glyph absent from a master | N/A | `[S]` same, UNVERIFIED even in the source catalog | — |
| KERN-06 mark/mkmk FeatureCount drift from anchor differences | N/A | `[S]` compiled-GPOS concern, same mechanism as FEAT-01 | — |

### FEAT (6 rows)

All six rows require compiled GSUB/GPOS/GDEF table inspection, entirely beyond what a
DesignSpace/UFO-metadata tool can see pre-build. **N/A — belongs to fontmake/ufo2ft's own OTL
merge diagnostics.**

| row | class | evidence | proposal |
|---|---|---|---|
| FEAT-01 differing feature set compiled per master | N/A | `[S]` compiled-OTL merge concern (`_merge_OTL`) | — |
| FEAT-02 only default source's hand-authored features.fea used (older pipelines) | N/A | `[S]` toolchain/ufo2ft-version concern, invisible from DS+UFO alone | — |
| FEAT-03 GDEF classification differs per master | N/A | `[S]` compiled-GDEF concern | — |
| FEAT-04 rvrn/rclt structurally-clean but semantically-wrong across masters | N/A | `[S]` shaping-semantics concern beyond DS/UFO metadata | — |
| FEAT-05 inconsistent extension-lookup wrapping | N/A | `[S]` compiled-table-size concern, only visible post-compile | — |
| FEAT-06 mark/mkmk subtable format differs per master | N/A | `[S]` compiled-OTL concern | — |

### ORDER (3 rows)

| row | class | evidence |
|---|---|---|
| ORDER-01 glyph-order-relative coverage mismatch | N/A — compiled-binary concern |
| ORDER-02 differing `public.glyphOrder` lib key across masters | COULD CATCH, cheap, in scope | Every source UFO is already opened for glyph-name extraction; comparing the `public.glyphOrder` lib key (when present) across all non-sparse masters is a cheap, purely-static addition, and a plausible authoring mistake (reordering glyphs in one master's font editor without doing the same everywhere) |
| ORDER-03 glyph renamed in only one master | folds into GLYPH-10/ORDER-02 | same glyph-name-set diff catches a rename as "present here, absent there" (though it can't distinguish a rename from an actual omission — both surface as the same diff) |

### INFO (7 rows incl. `INFO-07†`)

| row | class | evidence |
|---|---|---|
| INFO-01 unitsPerEm / other fontinfo mismatch across masters | COULD CATCH, cheap, high value | `UFOValidator` already opens every source UFO; comparing `font.info.unitsPerEm` is nearly free and guards one of the catalog's own "10 most dangerous silent failures" (see proposal #9) |
| INFO-02 MVAR-eligible metrics vary unintentionally | N/A — requires judging designer intent behind fontinfo drift, not a structural check |
| INFO-03 name table sourced from DS/instance, not master fontinfo | N/A — documentation point, not a validation gap (DSSketch's own `familyName`/`styleName` handling is already DS-driven by design) |
| INFO-04/05 hinting silently stripped on any mismatch | N/A — compiled TrueType-hinting concern, invisible at UFO level |
| INFO-06 kerning cascade vs. interpolation (non-failure baseline) | N/A — correctly out of scope |
| INFO-07† `post` underline sentinel (-0x8000) collision | N/A — compiled-binary sentinel, invisible at UFO/DesignSpace level (though trivia: comparing `postscriptUnderlineThickness`/`Position` across masters for the literal sentinel value would be cheap if ever wanted — very low priority, low real-world incidence) |

---

## 4. Examples audit

- `examples/MegaFont-3x5x7x3-Variable.dssketch` and `examples/SuperFont-6x2.dssketch` both use
  wildcard rules (`* > .rvrn`, `dollar* cent* > .rvrn`) exactly matching finding #1/RULE-24's
  false-all-clear pattern — real, shipped, non-hypothetical exposure, though neither example
  currently ships a `@sparse` source, so the specific failure isn't *triggered* in these
  files, only reachable by the pattern they use.
- `examples/MegaFont-3x5x7x3-Variable.dssketch` uses the exact `wght Thin:Regular:Black` /
  `Regular > 420` (non-identity default mapping) idiom that finding #5 depends on — but every
  source in that file gives full, explicit per-axis coordinates (no shorthand/omission), so it
  does not itself trigger the bug. It is the textbook case that *would* trigger it the moment
  someone "simplifies" one of its sources to the shorthand form CLAUDE.md documents elsewhere.
- No example currently defines a discrete axis other than `ital`/`italic` (finding #3) or a
  `@sparse` source at all — grepped across all 20 `examples/*.dssketch` files.
- No example uses explicit (non-`auto`) instances (finding #7) or duplicate/near-duplicate
  mapping user_values (finding #4) or backwards label ranges (finding #6).

## 5. Files in this pass

All under `validation/` in the scratchpad (paths below are relative to it):
`t_discrete_custom.py`, `t_discrete_slnt.py`, `t_rule17.py` + `make_ufos.py` +
`sources/*.ufo`, `t_rule17_confirm.py`, `t_dup_uservalue.py`, `t_dup_debug.py`,
`t_default_space.py`, `t_default_space2.py`, `t_default_space3.py`, `t_misc.py`,
`t_misc2.py`, `t_reversed_full.py`, `t_batch2.py`, `t_more.py`, `t_src04.py`,
`t_dup_location.py`.
