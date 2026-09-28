# DesignSpace 5 -> DSSketch expressibility map

Scope: every element/attribute in the DesignSpace 5 spec that DSSketch's
converters touch or should touch, checked against the actual code
(`src/dssketch/parsers/dss_parser.py`, `writers/dss_writer.py`,
`converters/designspace_to_dss.py`, `converters/dss_to_designspace.py`,
`core/models.py`) and verified empirically with minimal probe files run
through `dssketch.convert_designspace_to_dss_string(..., return_report=True)`
and `dssketch.convert_dss_string_to_designspace(...)`. Probes and their
roundtripped output live next to this file in `probes/`.

Five roundtrip issues are already tracked in
`notes/roundtrip-fidelity-issues.md` (mixed source paths, the `hidden`
heuristic, Amstelvar master-default verbosity, axis-name-vs-tag collision,
`instances auto` fit-checking). They are **referenced, not re-reported**
below. Everything else here is new.

Design principles this map respects (maintainer's, non-negotiable):

- DSSketch is deliberately higher-level than DesignSpace. Per-instance
  minutiae (postscriptfontname, stylemap names, localized instance names,
  instance `lib`, `locationLabel` refs, per-instance `userLocation`,
  per-instance `glyphs`) are **out of scope by design**, not gaps. What is
  fairly asked of the converter is *honesty*: say what an existing
  DesignSpace loses.
- DS -> DSS never invents DSSketch-only intent (`skip`, `hidden` topology)
  from a DesignSpace. It diagnoses; it does not transform.

## Headline findings (read this first)

1. **A rule with more than one `<conditionset>` is silently corrupted, not
   just lossy.** OR-of-conditionsets becomes a single AND-conditionset on
   DS -> DSS. This is not a metadata loss, it is a **behavior change**: a
   substitution that should fire in region A *or* region B now only fires in
   A *and* B. See "Rules" below and `probes/probe_rules_or_processing.*`.
2. **A discrete axis with more than two `values` crashes the roundtrip.**
   DS -> DSS emits a plain numeric range (`STYL 0:0:2`) instead of
   `STYL discrete`, because the discrete-axis detector is hardcoded to the
   binary 0/1 case. DSS -> DS then rejects the resulting 3-way `@base`
   sources as "multiple base sources". This is a genuine bug in current code
   (not one of the five known issues) — see "New bug" below.
3. **Document-level `<lib>` is dropped on every real file examined (4/4).**
   `DSSDocument.lib` exists in `core/models.py` but is never read, written,
   or reported — it is dead code. All four real production/reference files
   available (`AmstelvarA2-Roman`, `AmstelvarA2-Italic`,
   `AmstelvarA2-Roman_v2`, `GoogleSansFlex`) carry a non-trivial `<lib>`
   block (RoboFont/xTools4 project paths, `GSDimensionPlugin` data). None of
   it survives, and nothing says so.
4. Every silent loss below produces **zero report entries**, even though
   `DesignSpaceToDSS.report` already exists and already walks per-instance
   data (position + style name) for the `instances auto` fit check. Adding a
   diagnostic line costs little and matches the "diagnose, don't transform"
   principle the maintainer has already committed to for `skip`/`hidden`.

## Counts

| status | count |
|---|---|
| SUPPORTED | 11 |
| GAP-WORTH-ADDING | 9 (incl. 1 bug fix) |
| OUT-OF-SCOPE-BY-DESIGN (all "silent loss") | 11 |
| GREY ZONE | 3 |

(Counts are for distinct sub-features in the matrix below; a few items span
categories and are counted once, at their dominant classification.)

---

## Feature matrix

Legend: **DS→DSS** = what happens converting an existing DesignSpace down;
"report" = whether `ConversionReport` says anything; commonality is based on
`examples/` (14 DSSketch-authored files), `~/WORK/amstelvar-avar2`
(4 `.designspace` files) and `~/WORK/googlesans-flex` (1 file) — the only
non-private corpora available.

### A. Axes

| feature | DS5 element/attr | status | DS→DSS behaviour | how common | proposal |
|---|---|---|---|---|---|
| continuous range | `minimum`/`default`/`maximum` | SUPPORTED | round-trips exactly | universal | — |
| avar1 map | `<map input output>` | SUPPORTED | round-trips exactly, union-of-map-and-labels semantics preserved | universal | — |
| STAT labels: name/userValue/elidable | `<label name userValue elidable>` | SUPPORTED | round-trips | universal | — |
| discrete axis, 2 values | `values="0 1"` | SUPPORTED | round-trips via `discrete` keyword | common (italic) | — |
| **discrete axis, 3+ values** | `values="0 1 2"` | **BUG** | writes a numeric range (`STYL 0:0:2`) instead of `discrete`; the read-back then rejects the N `@base` sources as "multiple base sources" — hard crash, total loss | not observed in corpus, but spec-legal and used for e.g. non-interpolating style families | Add `DSSAxis.is_discrete: bool`, set from `isinstance(axis, DiscreteAxisDescriptor)` (not from the numeric range). Writer honours it regardless of arity; parser accepts N labelled lines under `discrete`; validator's multi-`@base` allowance already exists for discrete axes generically — it just needs the axis to be *recognized* as discrete. See `probes/` inline script in this doc's appendix. |
| `hidden="1"` | axis `hidden` | SUPPORTED (mostly) | explicit attribute is read first and wins; the avar2-only-output heuristic remains as fallback | rare explicitly, but **all 3 Amstelvar files + GoogleSansFlex mark axes hidden explicitly** (89, 87, 62, 2 axes respectively) | Already covered by known issue #2's open question (heuristic-overrides-declaration edge case). Not re-proposed here. |
| `axisOrdering` | axis `axisOrdering` | GREY ZONE | only ever written during `instances auto` generation, as a fresh sequential 0..N-1 re-index of the DSS `axes` section order; dropped entirely when `instances off` (the common case for avar2/parametric fonts — 4/5 real files have 0 instances); arbitrary/non-sequential declared values are never preserved | present in all 5 real files (fontTools always writes it when `axisLabels` exist) | Low priority: DSSketch's axis-section order already encodes relative order, so the loss is mostly cosmetic *unless* an axis is hidden mid-sequence (ties to known issue #2) or ordering is deliberately non-sequential (skips numbers). If issue #2 is ever addressed by adding `DSSAxis.hidden` + interleaved ordering, write `axisOrdering` unconditionally (not only during instance generation) at the same time. |
| STAT format 2: `userMinimum`/`userMaximum` | `<label userminimum usermaximum>` | GAP, **silent loss** | dropped entirely; format-2 labels collapse to format-1 | not observed in corpus; documented STAT pattern for multi-master families that want a labelled *range* (e.g. "Light" = user 250–349) | `Light > 300 [250:349]` — reuse the existing `[min, max]` bracket syntax already used for source coordinates, attached to a mapping line. |
| STAT format 3: `linkedUserValue` | `<label linkeduservalue>` | GAP, **silent loss** | dropped entirely; format-3 labels collapse to format-1 | not observed in corpus; used for "Bold" checkbox linking to a specific weight | `Bold > 700 @linked=400` |
| STAT flag: `olderSibling` | `<label oldersibling>` | GAP, **silent loss** | dropped | rare | `Black > 900 @oldersibling` — low priority, bundle with the two above |
| per-label localized name | `<label><labelname xml:lang>` | GAP, **silent loss** | dropped entirely | not observed in corpus | `Light > 300` then an indented `labelname fr="Léger"` line; bundle with axis-level localization below |
| axis-level localized display name | `<axis><labelname xml:lang>` (multi-locale) | GAP, **silent loss**, and actively **misleading** | *every* locale is discarded; DSSketch always regenerates a single `en` entry equal to the internal axis name/tag (e.g. original `en="Weight"`, `fr="Graisse"`, `de="Schriftstärke"` all become `en="weight"`) | not observed as multi-locale in the small corpus, but single-locale `"weight"`/`"Weight"` display names appear in most of `examples/`, and any internationally-distributed family needs this | `wght 100:400:900 "weight"` extended with a `labelname fr="Graisse" de="Schriftstärke"` line under the axis. Distinct from — and a superset of — known issue #4 (name==tag collision), which is about the *single* internal name, not the locale map. |

### B. avar2 `<mappings>` (structure only — semantics researched separately)

| feature | status | notes |
|---|---|---|
| input/output dict round-trip, `description` field | SUPPORTED | Verified on `examples/avar2.designspace`: 11 mappings in, 11 out, identical input/output/description sets. |

### C. Document-level location labels

| feature | DS5 element | status | DS→DSS behaviour | how common | proposal |
|---|---|---|---|---|---|
| `<labels>`/`<label>` (STAT format 4, free-floating named locations) | document-level `locationLabels` | GAP, **silent loss** | `DesignSpaceDocument.locationLabels` is never read; the whole block disappears with no report entry | not observed in the 5-file corpus, but this is exactly the mechanism recommended for STAT locations that don't correspond to a shipped static instance (e.g. "Reading", "Display") | `labels` section reusing the instance bracket syntax: `"Reading" [Regular] @elidable`, `"Bold Condensed" [Bold, Condensed]`. Localized names and `elidable`/`olderSibling` flags follow the axis-label proposal above. |

### D. `<variable-fonts>` / `<axis-subsets>`

| feature | DS5 element | status | DS→DSS behaviour | how common | proposal |
|---|---|---|---|---|---|
| VF subset declarations, range subsets, value (freeze) subsets, discrete value subsets, per-VF `lib`, filenames | `variable-fonts`/`variable-font`/`axis-subset` | GAP, **silent loss** | `DSSDocument.variable_fonts: List[Dict]` exists in `core/models.py` but is **never populated or read anywhere** — confirmed dead field by grep across the whole `src/` tree. The entire block vanishes silently. | not observed in any of the 5 real files checked; it is a DS5 feature aimed at large families that ship several physical VFs from one source (e.g. splitting Roman/Italic VFs, or freezing a discrete axis per file) | This is a genuine "build recipe" concept and fits the higher-level philosophy well (it says *what gets built*, not *what a font looks like*), so it is a gap worth adding rather than out-of-scope. Sketch: <br>`variable-fonts`<br>`    ProbeVF-Roman.ttf [wght, ital=Upright]`<br>`    ProbeVF-Italic.ttf [wght=400:900:400, ital=Italic]`<br>Lower priority than the items above since no example in reach actually uses it. |

### E. Sources

| feature | DS5 attr | status | DS→DSS behaviour | how common | proposal |
|---|---|---|---|---|---|
| `filename`, `location` | — | SUPPORTED | round-trips | universal | — |
| `layerName` | `@layer` | SUPPORTED | round-trips (documented feature) | present in `examples/FontWithLayers.dssketch` | — |
| `copyLib`/`copyInfo`/`copyGroups`/`copyFeatures` | `@base`-adjacent flags | SUPPORTED | round-trips | universal (every `@base` source) | — |
| `name` attribute (designer-chosen source id, distinct from filename) | `source name=` | GREY ZONE | never read on DS→DSS (`DSSSource.name` is derived from the filename stem, not from `source.name`); always regenerated as synthetic `source.N`/`sparse.N` on DSS→DS | present in probe only; not seen with meaningful values in the real corpus (fontmake-generated files use `source.0`-style names too) | This is deliberate and documented for the `sparse.*` case (CLAUDE.md: "the `sparse.` prefix is the semantic carrier"). For a hand-authored meaningful name (e.g. `master.regular`) it is a genuine, undisclosed loss if any external tool keys off it. Not proposing a fix — flagging the ambiguity. |
| `familyName`/`styleName` override (per-source, distinct from the document family) | `source familyname/stylename=` | OUT-OF-SCOPE-BY-DESIGN, **silent loss** | dropped; overridden source gets the document family + filename-derived style name instead | not observed in the 5-file corpus | Per-source family overrides describe a single UFO's metadata, which is exactly the per-file minutiae the maintainer has ruled out of scope. Worth one report line if it changes what gets *read into* the built font (see report proposal below). |
| `localisedFamilyName` | `<source><familyname xml:lang>` | OUT-OF-SCOPE-BY-DESIGN, **silent loss** | dropped | not observed | same as above |
| `muteInfo`/`muteKerning`/`mutedGlyphNames` | `<info mute>`/`<kerning mute>`/`<glyph mute>` | OUT-OF-SCOPE-BY-DESIGN, **silent loss** | not even modeled — `DSSSource` has no field for any of the three; dropped completely on DS→DSS | not observed in corpus, but a real varLib feature for masters that intentionally omit info/kerning/specific glyphs | Out of scope by the stated philosophy (per-source build tuning), but currently invisible even as a warning — see report proposal. |

### F. Instances — out of scope by design, catalogued for completeness

Per the maintainer's principle, `instances auto` + labels + `skip` replace
per-instance listing, so none of the following gets a DSSketch syntax
proposal. What is checked is whether the *existing* auto-fit report (which
already walks declared vs. generated instances by position and name) says
anything about them. It does not — confirmed empirically
(`probes/probe_instance_richness.*`): the report correctly flagged the
renamed/extra *position*, but said nothing about the instance-level data
listed below, all of which silently disappeared in the same conversion.

| feature | DS5 attr | status |
|---|---|---|
| `postScriptFontName` | instance attr | OUT-OF-SCOPE-BY-DESIGN, silent loss (regenerated from family+style instead) |
| `styleMapFamilyName`/`styleMapStyleName` | instance attr | OUT-OF-SCOPE-BY-DESIGN, silent loss |
| `localisedFamilyName`/`localisedStyleName` | instance sub-elements | OUT-OF-SCOPE-BY-DESIGN, silent loss |
| `lib` | instance `<lib>` | OUT-OF-SCOPE-BY-DESIGN, silent loss |
| `locationLabel` (instance pinned to a named location) | instance attr | OUT-OF-SCOPE-BY-DESIGN, silent loss — the whole instance disappears, not just the reference, since `instances auto` cannot regenerate an instance whose position comes from a `<label>` the converter also drops (see section C) |
| `userLocation` (vs. `designLocation`) | instance attr | OUT-OF-SCOPE-BY-DESIGN, silent loss — always regenerated as design location |
| `glyphs` (per-instance glyph masters/rules, MutatorMath-style) | instance `<glyphs>` | OUT-OF-SCOPE-BY-DESIGN, silent loss; not modeled at all |

Also related: the explicit (non-`auto`) instance list is unreadable by the
parser (`TODO` stub) and the writer can produce it with `optimize=False` —
this is known issue #5's open question, referenced not re-reported.

### G. Rules

| feature | DS5 attr | status | DS→DSS behaviour | how common | proposal |
|---|---|---|---|---|---|
| single conditionset, `&&`-joined conditions | `<conditionset><condition>` | SUPPORTED | round-trips | present in 5/14 `examples/` files | — |
| one-sided conditions (min-only / max-only stay open) | `condition` with only `minimum` or only `maximum` | SUPPORTED | confirmed: `<condition name="width" maximum="80"/>` keeps no `minimum`, matching the fix described in code comments (`dss_parser.py`) | present in most rule-bearing examples | already fixed; verified, not re-reported |
| rule `name` | `<rule name>` | SUPPORTED | round-trips | present wherever rules exist | — |
| **multiple `<conditionset>` per rule (OR semantics)** | `rule.conditionSets` (list of lists) | **GAP — and the current behaviour is actively wrong, not just lossy** | `_convert_rule()` in `designspace_to_dss.py` flattens *every* conditionset's conditions into one flat list; `DSSRule.conditions` in `core/models.py` has no grouping at all; `_convert_rule()` in `dss_to_designspace.py` always emits exactly one conditionset (`rule.conditionSets = [[]]`). Verified: a rule meaning "(weight≥700) OR (width≤80)" comes back as "(weight≥700) AND (width≤80)" — a different substitution trigger, silently, with zero report entry. | not observed in the small corpus, but OR-of-conditionsets is a documented pattern in fonttools/varLib for compound rule triggers, and is the only way DS5 expresses "either of these two regions" | Two-part fix: (1) minimum viable — DS→DSS should split a multi-conditionset rule into **N DSSketch rules that share the same name and substitutions**, one per original conditionset, and merge them back into one `<rule>` with N conditionsets on the way up. No new syntax needed: `dollar > dollar.alt (weight >= 700) "orRule"` followed by `dollar > dollar.alt (width <= 80) "orRule"` on the next line. (2) until that lands, DS→DSS must at least emit a WARNING that OR semantics were flattened to AND — this is a correctness issue, not a style-name diagnostic, and belongs in `CATEGORY_RULES` in `core/report.py` (a category that exists but currently has no codes defined). |
| document flag: `processing="last"` | `<rules processing="last">` | GAP-WORTH-ADDING, **silent loss** | `DesignSpaceDocument.rulesProcessingLast` is never read or written; always emits `<rules>` (implicit "first"), silently changing whether substitutions apply before or after other OpenType features | not observed in the 5-file corpus, but it is a one-bit, whole-document flag with real shaping consequences | A single top-level line, e.g. `rules processing last` (or `rules last`) placed before the `rules` section, mirroring `instances off`. Trivial to implement, meaningful semantic difference — high value-to-effort ratio. |

### H. Document-level metadata

| feature | DS5 attr | status | DS→DSS behaviour | how common | proposal |
|---|---|---|---|---|---|
| `<lib>` (document-level, arbitrary plist dict) | `DesignSpaceDocument.lib` | GAP-WORTH-ADDING, **silent loss**, high priority | `DSSDocument.lib: Dict` exists in the model but is **never populated on DS→DSS and never written on DSS→DS** — fully dead. Confirmed present and non-trivial in **4 of 4** real files examined (RoboFont/xTools4 project config, `GSDimensionPlugin` data). | **4/4 real files** — the single most common loss found in this survey | Since plist dict values can nest arbitrarily (seen in `GoogleSansFlex`: dict-of-dicts), propose an indented YAML-flavoured passthrough block rather than a bespoke key=value grammar: <br>`lib`<br>`    com.github.fonttools.varLib.featureVarsFeatureTag: rvrn`<br>`    com.xTools4.xProject:`<br>`      glyphConstructionsPath: AmstelvarA2-Roman.glyphConstruction`<br>Even a conservative first cut — round-trip the dict opaquely without trying to make it hand-editable — would eliminate the most common silent loss in the survey. |
| `elidedFallbackName` | `<axes elidedfallbackname>` | GAP-WORTH-ADDING, **silent loss**, trivial cost | never read or written | not observed in the 5-file corpus, but it is a one-line STAT-table detail that costs almost nothing to add | `elided-fallback Regular` as a top-level line |
| `formatVersion` | document `format=` | N/A (delegated) | fontTools' writer auto-selects the minimal format the *content* requires; DSSketch does not track the original explicitly. Already documented in `notes/roundtrip-fidelity-issues.md` Appendix B (regenerating an avar2 fixture can downgrade 5.2→5.1 as a side effect of losing STAT-label detail). | — | No new proposal; fixing the STAT-label gaps above (which is what actually drives the format bump) removes the symptom for free. |

---

## Grey zones (ambiguous, not simple gaps)

1. **`axisOrdering`** — see table entry above. Whether it deserves its own
   syntax depends entirely on whether real files use non-sequential values
   or interleave hidden/visible axes; the corpus in reach shows neither.
2. **`hidden` heuristic vs. declaration** — already the subject of known
   issue #2's open question ("is `hidden` derivable or declared?"). This
   survey adds one data point: **all axes hidden in the real corpus are
   hidden by explicit attribute**, never solely by avar2 topology, which
   weakens the case for keeping the heuristic at all. Not re-litigating the
   decision here, just surfacing the evidence.
3. **`source.name`** — doubles as (a) the sparse/non-sparse semantic carrier
   DSSketch deliberately keeps, and (b) an arbitrary designer identifier
   DSSketch deliberately discards. Both are intentional, but the same
   attribute serves two different purposes depending on which one you
   expected; worth documenting explicitly rather than fixing.

## Silent-loss catalogue (for the report proposal)

Every "silent loss" tag above shares one property: zero entries in
`ConversionReport`, even for documents where the report mechanism already
runs (any document with `ds_doc.instances`). Concretely, extending
`core/report.py` with new codes under `CATEGORY_AXES` / `CATEGORY_SOURCES` /
a currently-empty `CATEGORY_RULES`, `SEVERITY_WARNING` "dropped: STAT
userMinimum/userMaximum on axis 'weight'", "dropped: document `<lib>` (N
keys)", "dropped: rule 'orRule' had 2 conditionsets, flattened to AND" would
turn every row in this document that says "silent loss" into an honest one,
without changing what DS→DSS actually produces. This is squarely inside the
"diagnose, don't transform" principle already applied to `instances auto`.

## New bug found in this survey

**3+-value discrete axis crashes the roundtrip.** Not one of the five known
roundtrip issues. Root cause chain (see `probes/` transcript in this
session):

1. `_convert_axis()` in `converters/designspace_to_dss.py` detects
   discreteness correctly on the DS side (`hasattr(axis, "values")`), so a
   `DiscreteAxisDescriptor` with `values=[0, 1, 2]` produces a `DSSAxis`
   with `minimum=0, maximum=2` — numerically indistinguishable from a
   continuous axis.
2. `_is_default_source()` uses a *different*, correct discrete check
   (comments say "for discrete axes, any value is acceptable"), so all 3
   sources are marked `is_base=True` — correct DS5 semantics (one base per
   discrete value).
3. The **writer** decides whether to print `AXIS discrete` using
   `DiscreteAxisHandler.is_discrete()` (`utils/discrete.py`), which is
   hardcoded to `minimum == 0 and default == 0 and maximum == 1` — binary
   only. A 3-value axis fails this check and gets written as a plain
   numeric range (`STYL 0:0:2`), with 3 sources all flagged `@base`.
4. On read-back, the **parser/validator** sees a non-discrete-looking axis
   with 3 `@base` sources and raises `"Multiple base sources found (3) -
   only one allowed"` — a hard `ValueError`, not a warning. Total data loss.

Fix: give `DSSAxis` an explicit `is_discrete: bool` set from
`isinstance(axis, DiscreteAxisDescriptor)` on DS→DSS (never inferred from
the numeric range), and make the writer/parser/validator all honor that
flag instead of re-deriving discreteness from `0:0:1`. This also removes the
project-memory note's "must stay in sync" burden between
`DiscreteAxisHandler.is_discrete()` and the writer's copy of the same
check — there would be one source of truth instead of two independently
maintained heuristics.

---

## Prioritized proposal list

1. **Fix the OR-conditionset flattening (correctness bug).** At minimum, add
   a `CATEGORY_RULES` warning when a multi-conditionset rule is flattened.
   Full fix: split into repeated same-name rules on DS→DSS, merge on DSS→DS.
2. **Fix the 3+-value discrete-axis crash.** One field (`DSSAxis.is_discrete`)
   plus three call sites; turns a hard crash into correct output.
3. **Passthrough document-level `<lib>`.** Highest real-world prevalence
   found (4/4). Even opaque roundtrip (no hand-editing support) is a
   worthwhile first cut.
4. **`rules processing last`.** One boolean, one line of syntax, real
   shaping-order consequence.
5. **`elided-fallback NAME`.** One string, trivial.
6. **Extend `ConversionReport` to cover the silent losses above** (axis STAT
   detail, document `<lib>`, source mute/localised fields, rule
   flattening). This is pure diagnostics, matches the project's own stated
   principle, and requires no format changes.
7. **Document-level named locations (`labels` section, STAT format 4).**
   Reuses existing bracket-coordinate syntax; fills a real STAT-table gap.
8. **Axis STAT range/link/localization bundle** (`userMinimum`/`userMaximum`,
   `linkedUserValue`, `olderSibling`, per-label and per-axis `labelname`).
   Bundle these — they share one implementation surface (the `AxisLabelDescriptor`
   round-trip) — but treat as lower priority than 1–7 since none appeared in
   the available corpus.
9. **`variable-fonts`/`axis-subsets`.** Fits the "build recipe" philosophy
   well if the project ever wants it, but no evidence of demand in the
   corpus available for this survey; lowest priority of the additions.

---

## Appendix: probes

All probe `.designspace` files, their DS→DSS output, and the
`.roundtrip.designspace` produced by converting back are in `probes/`:

- `probe_axis_stat_labels.*` — userMinimum/userMaximum, linkedUserValue,
  olderSibling, per-label and per-axis localized names, axisOrdering.
- `probe_hidden_discrete_ordering.*` — explicit `hidden`, discrete axis,
  axisOrdering across mixed axis types.
- `probe_location_labels.*` — document-level `<labels>`/`<label>`.
- `probe_variable_fonts.*` — `<variable-fonts>`/`<axis-subsets>`, including a
  discrete value-subset.
- `probe_source_richness.*` — source `name`, familyName/styleName override,
  localisedFamilyName, muteInfo/muteKerning/mutedGlyphNames, copy flags.
- `probe_instance_richness.*` — postScriptFontName, styleMap*, localised*,
  instance `lib`, `locationLabel`, `userLocation`.
- `probe_rules_or_processing.*` — `processing="last"`, multiple
  conditionsets (OR), rule name.
- `probe_doclevel_lib.*` — document-level `<lib>`, `elidedFallbackName`.

`build_probes.py` builds all eight from scratch with fontTools'
`designspaceLib` API (authoritative — no hand-written XML). `run_roundtrip.py`
runs each through `dssketch.convert_designspace_to_dss_string(ds,
return_report=True)` then `dssketch.convert_dss_string_to_designspace(...)`
and writes the `.roundtrip.designspace` for diffing. The 3+-value discrete
axis bug and the avar2-structure check were run as inline scripts during the
session (not saved as separate probe files) — reproduction snippets are in
this document's "New bug" section and section B respectively.

No private/client repositories were opened for this survey, per instructions. The only real-world
corpora used were `~/WORK/DSSketch/examples`, `~/WORK/amstelvar-avar2`, and
`~/WORK/googlesans-flex`.
