# DSSketch and avar2/HOI: traps, expressiveness, grey zones, validation

Scope: `~/WORK/DSSketch` avar2 support (parser/writer/converters/instances), checked
against the independent audit at
`~/WORK/designspace-lint/docs/audit/2026-09-coverage/failure-catalog.md` (rows
AVAR2-01..35) and its README. All work is empirical where it matters: `.dssketch`
files were written and converted with the real `dssketch` CLI
(`<venv>`), and outputs were inspected with fontTools
against the actual `DesignSpaceDocument` objects. No repo files were modified. Probe
files and round-trip outputs live in this scratchpad's `work/` subdirectory.

Bottom line: **DSSketch adds no avar2-specific validation of any kind.** The only
avar2-aware check in the whole codebase is a log-only (not `validator.errors`, not
`ConversionReport`) message for an unresolved axis name in a mapping, and it is
silent unless `setup_logger()` has run (true for the CLI, false for the plain Python
API per the project's own docs). Every failure mode below that can be detected from
the DS/DSS text alone is currently unflagged. Two of DSSketch's own conveniences —
the `$` default shorthand and the human-readable axis names — actively help with a
couple of rows, and one heuristic (hidden-axis inference) quietly *improves* on a
real published file. But the input/output space split (user on input, design on
output) that DSSketch introduces to make labels readable is a new place to go wrong
that the raw DesignSpace XML doesn't have, and it is unguarded.

---

## 1. Traps DSSketch lets you write (AVAR2-01..35)

Legend: **Writable** = can a `.dssketch` author produce the XML shape the row
describes. **Caught** = does anything in DSSketch flag it today (parser, validator,
writer, or even a log line). **Verified** = built and checked in this session, not
just read from code.

### Directly reproduced and measured

**AVAR2-01 / AVAR2-02 — mapping at the default input.** Writable, uncaught, and
already present in the wild.
- `examples/AmstelvarA2-Roman_avar2.dssketch`/`.designspace` (shipped in this repo)
  contains exactly this: `{Weight: 400}` (400 is the Weight axis's own default) →
  `YTOS=10`, while YTOS's own default is 11. I confirmed by walking all 29 mappings
  in that file that this is the *only* one whose input normalizes to the default,
  and its one diverging output is `YTOS: 11.0 → 10.0` — a delta of 10 − 11 = **−1**
  that `varLib.models.py`'s `storeMasters()` throws away as the VarStore base and
  then subtracts from every other YTOS mapping in the table (confirmed by the
  audit's own compiled-table probe: YTOS lands on 21.73 instead of 20 at Weight
  1000, a ~9% error).
- I ran this exact file through the real `dssketch` CLI: DesignSpace → DSSketch →
  DesignSpace. Zero warnings anywhere in the log. The round-tripped mapping is
  byte-identical to the source (`{'Weight': 400.0} → {'YTOS': 10.0, ...}` survives
  unchanged). DSSketch is a completely transparent carrier for this bug — it
  neither introduces it nor catches it.
- **DSSketch's own vocabulary makes this row easier to write, not harder.** The
  `$` shorthand ("use axis default") is specifically for anchoring a mapping's
  *output* at a default; nothing stops (or flags) a mapping whose *input* also
  normalizes to a default. A natural authoring habit — "map every named style,
  including `[wght=Regular]`, to its full parametric footprint" — produces this
  row directly, and CLAUDE.md's own avar2 examples (`[wght=400] > wght=400,
  XOUC=$XOUC`) are one missing "only when non-default" caveat away from doing it.
  One shipped example, `avar2QuadraticRotation.dssketch`, dodges the bug by
  accident-of-design: its default-input row is `[ZROT=0] > AAAA=$, BBBB=$` —
  output equals default, so the discarded base delta is zero and there is no
  visible corruption. That is a coincidence of that particular font, not a
  property DSSketch enforces.

**AVAR2-03 — input outside the axis range.** Writable, uncaught. Probe
(`work/probe2.dssketch`): `wght 100:400:900` with `[wght=1200] > XHID=50`.
Converted clean (one unrelated warning about a missing Thin source); the XML
carries `<dimension name="weight" xvalue="1200"/>` verbatim. fontTools will clamp
this to 900 at build time with no warning of its own — DSSketch had every fact
needed (the axis's own `minimum`/`maximum`) to catch it before that point and
didn't.

**AVAR2-06 — output outside the target axis's range.** Writable, uncaught. Same
probe file: `XHID 0:0:100` (hidden) with `[wght=900] > XHID=500`. Converted clean,
XML carries `xvalue="500"` on an axis whose declared max is 100. Same story as
AVAR2-03: DSSketch has the hidden axis's declared range in hand and never
consults it for avar2 outputs.

**AVAR2-09 — inputs written in the wrong space, when an axis has a real v1
map.** This is the row DSSketch's own design makes *newly* easy to trigger,
because DSSketch (unlike raw DS XML) presents avar2 input as **user space**
everywhere a label is used (`_resolve_avar2_value` in `dss_parser.py:1520`:
"labels resolve to USER SPACE values... The converter will transform user →
design"). A raw number in the same slot is *not* tagged as user or design; it
is passed through `_user_to_design_value` (`dss_to_designspace.py:311`) which
searches for an axis mapping whose `user_value` equals it, and — critically —
**silently falls back to treating it as already-correct (identity) the moment
it fails to land exactly on a labeled point**:
  ```python
  for mapping in axis.mappings:
      if mapping.user_value == user_value:
          return mapping.design_value
  # No exact mapping found - user and design might be equal
  return user_value
  ```
  I verified this is wrong, not just theoretically risky. Probe
  (`work/probe1.dssketch`): axis `wght 100:400:900` with `Regular > 400`
  (design 400) and `700 Bold > 625` (design 625), i.e. a real, non-identity v1
  map. `avar2 [wght=550] > XHID=50` — a number a human would read as "user-space
  550, halfway between Regular and Bold." The correct design-space value,
  interpolated along the axis's own map, is 400 + (550−400)/(700−400)×(625−400)
  ≈ **512.5**. What DSSketch actually emitted:
  ```xml
  <dimension name="weight" xvalue="550"/>
  ```
  — the raw 550, off by 37.5 design units (~7% of the Regular–Bold span), with
  no warning at any stage. This is AVAR2-09 exactly ("an author... that writes
  user values on an axis that has a v1 map gets the wrong location... Silent"),
  and DSSketch's whole selling point — "just write the label or the number you
  mean" — is what invites it. It only fails to fail when the number happens to
  exactly match a mapping's `user_value` (float equality), which is common for
  hand-picked style values and much less common for anything in between.

**AVAR2-07 — unknown/misspelled dimension name.** Writable, *partially* caught,
but only as a side-channel that most callers never see. Probe
(`work/probe3.dssketch`): `[wght=900] > XHDI=50` (typo for `XHID`). DSSketch's
`_resolve_axis_name` (`dss_to_designspace.py:342`) does not find `XHDI`, logs
`DSSketchLogger.warning("avar2: axis 'XHDI' not found in axes definitions, using
as-is")`, and **still emits it**: `<dimension name="XHDI" xvalue="50"/>`, which
will hand fontTools a bare `KeyError: 'XHDI'` at build time. Two things blunt this
half-check:
  1. It is a `DSSketchLogger` call, not a `self.validator.errors`/`warnings`
     append, so it never shows up in `parser.errors`, `parser.warnings`, or the
     structured `ConversionReport` that the API-level docs (and this project's
     own error-handling examples in CLAUDE.md) tell integrators to inspect.
  2. Per CLAUDE.md itself, `DSSketchLogger` is a no-op until `setup_logger()`
     runs, which only the CLI does. A caller using `dssketch.convert_to_designspace()`
     directly — the documented, "recommended" API path — gets **total silence**
     and a file that will crash `varLib.build()` downstream.

### Reasoned from code, not independently rebuilt (would reproduce the same way)

**AVAR2-04/05 — clamped or duplicate inputs collide.** Writable: nothing in
DSSketch checks avar2 input locations for uniqueness (only axis label mappings get
that treatment, via `_validate_duplicate_mapping_labels`, and that check is scoped
to the labeled-axis-mapping list, not `avar2_mappings`). Two `avar2` lines with the
same `[...]` key, or two that clamp to the same normalized location per AVAR2-03,
pass straight through to a `VariationModelError` at build time with no DSSketch-side
diagnostic pointing at the offending line(s).

**AVAR2-08 — `uservalue` in a mapping dimension.** Not reachable through DSSketch's
own syntax (there is no way to write a `uservalue`-flavored dimension from
`.dssketch` text — the writer always emits `xvalue`), so this specific reader
quirk is moot for files that only ever pass through DSSketch. It would only bite a
hand-edited DesignSpace that a `designspace_to_dss.py` pass never touches.

**AVAR2-10/32 — corner summing, HOI tracking-axis drift.** DSSketch's matrix syntax
supports multi-axis `[opsz=144, wght=1000, wdth=125]` inputs natively (confirmed:
20 of the 29 real mappings in AmstelvarA2-Roman are exactly this — 2- and 3-axis
corners), so an author *can* write the correct explicit-corner pattern, and the
real example does. But nothing checks that corners are *complete*: DSSketch has
every axis's label set and every mapping's input footprint in hand and could, in
principle, compute "which combinations of non-default axes never got an explicit
row" — it does not. A font with only the 9 single-axis rows and none of the 20
corner rows from the real example would convert with the identical zero warnings
I saw on the full file.

**AVAR2-11 / AVAR2-18 — output is an added delta, and mappings never chain.**
Writable and, worse, actively suggested by the syntax. `AXIS=84` in `avar2
[opsz=144] > XOUC=84` reads as an assignment ("set XOUC to 84"), and CLAUDE.md's
own prose ("giving final axis coordinates" is nowhere mentioned) never says
otherwise. Nothing in the parser, writer, or docs distinguishes "this is an
absolute value" from "this is added to whatever the axis is already at." Likewise,
because a hidden axis is just another `axes hidden` declaration, DSSketch's syntax
lets you write a mapping whose *input* references another mapping's *output* axis
(I confirmed `_resolve_avar2_value` happily resolves values on any axis in
`self.document.axes + self.document.hidden_axes`, visible or hidden, for input
position) — producing dead code that looks like intentional chaining and silently
never fires except when a user or API sets that hidden axis by hand (AVAR2-12).

**AVAR2-12/13 — user-settable hidden axes; named instances double-counting a
hidden axis's value.** Writable. DSSketch's instance generator explicitly *excludes*
hidden axes from `instances auto` (`core/instances.py`, confirmed in CLAUDE.md and
by code: "Hidden axes (from `dss_doc.hidden_axes`) should not participate in
instance generation"), which is the right default and incidentally avoids
authoring AVAR2-13 through the generator. But nothing stops a `.dssketch` file's
*hand-written* `sources`/rare manual instance data from placing a hidden-axis
coordinate at a non-default value, which is all AVAR2-13 needs.

**AVAR2-14/15/16/17 — one-sided mappings, dead outputs/masters, undriven hidden
axes, unhidden parametric axes.** All writable, none checked. AVAR2-16 and
AVAR2-17 are visible in the two real files this task inspected: GoogleSansFlex
(0 avar2 mappings at all; `GRAD` and `slnt` are `hidden="1"` purely to keep them
off UI sliders) and the shipped `AmstelvarA2-Roman_avar2.designspace`, whose 61
parametric axes are **all `hidden="0"` in the source XML** even though every one
of them appears only as an avar2 output — i.e. the real, published test file
already has AVAR2-17. See §3 for what DSSketch's own round-trip does with that.

**AVAR2-19 — non-monotonic user-axis remap via avar2.** Writable (nothing checks
ordering of avar2 outputs onto a user axis across sorted inputs), not empirically
rebuilt here — no example uses avar2 to remap a *visible* axis, only hidden ones,
so this is a real gap but a narrower one in practice for DSSketch's own examples.

**AVAR2-20 — unhelpful build errors.** Not something DSSketch can improve after
the fact (it is fontTools' error surface), but it is exactly the gap that
DSSketch-side validation is positioned to close, since DSSketch has descriptions
(`mapping.name`) attached to every avar2 row already, which fontTools' bare
`KeyError`/`VariationModelError` never surfaces.

**AVAR2-21/22/23 — DS5 split behavior.** Out of scope for DSSketch (it doesn't
implement or wrap `splitVariableFonts`), so it neither helps nor hurts here; a
DSSketch-authored file is exactly as exposed as a hand-written one.

**AVAR2-24/25/26/27/33/34/35 — renderer/tooling/version support gaps.** These are
properties of the *ecosystem* (v1-only renderers, `varLib.instancer`/`mutator`,
`ufo2ft`, `feaLib`, DS format version, STAT for hidden axes, old macOS). DSSketch
cannot avoid them by construction, but two are worth a documentation-level flag
specific to this project: (a) DSSketch always targets modern DesignSpace 5.x
output, so AVAR2-33 (silently dropped by DS < 5.1 tools) is a risk only for
whatever consumes the `.designspace` DSSketch produces, not DSSketch itself; (b)
AVAR2-26/27 (static instances and `.fea` ignore avar2 entirely) directly
contradict the mental model DSSketch's docs imply — instances generated by
`instances auto` are DesignSpace *named instances*, and nothing in CLAUDE.md warns
that any static build from those instances, or any feature-file condition
referencing the same axis, will diverge from what avar2 actually produces in the
VF.

**AVAR2-28/29/30/31 — rules seeing post-avar2 coordinates; kerning/sparse
blending; tuning-source double-counting; reference-source drift.** All out of
DSSketch's current data model (it does not reason about kerning at all, and rules
are plain DS rules with no avar2-awareness). Not writable/preventable through
DSSketch specifically beyond what raw DS authoring already exposes.

### Summary table

| Row(s) | Writable via DSSketch | Caught today | Verified this session |
|---|---|---|---|
| 01, 02 | Yes, and a shipped example already has it | No | Yes — real file + probe |
| 03 | Yes | No | Yes — probe |
| 04, 05 | Yes | No | reasoned |
| 06 | Yes | No | Yes — probe |
| 07 | Yes | Log-only, invisible to API callers | Yes — probe |
| 08 | Not reachable from DSSketch text | n/a | reasoned |
| 09 | Yes — DSSketch's user/design split makes it *easier* than raw XML | No | Yes — probe, 550→550 instead of 512.5 |
| 10, 32 | Yes | No | Yes — real file shows the correct workaround pattern, unenforced |
| 11, 18 | Yes, and syntax invites the wrong mental model | No | reasoned + syntax read |
| 12, 13 | Yes (hand-authored data only; generator avoids it) | No | reasoned |
| 14–17 | Yes | No | 16/17 confirmed in real files |
| 19 | Yes | No | reasoned |
| 20 | n/a (fontTools-side) | n/a | — |
| 21–23 | Out of DSSketch's scope (split) | n/a | — |
| 24–27, 33–35 | Ecosystem-level | n/a | 26/27 contradict doc framing |
| 28–31 | Out of DSSketch's data model | n/a | — |

---

## 2. Expressiveness: what avar2/DS5 can say that DSSketch cannot (or barely)

- **Very large matrices stay parseable but stop being readable or diffable.**
  Measured on the real Amstelvar example: 29 mappings × 63 output axes compress a
  10,484-line DesignSpace into a 355-line `.dssketch` (≈30×), which is the
  headline win — but the matrix's `outputs` header and every one of its 29 data
  rows is **527 characters wide**. That is far past any terminal or diff-pane
  width, and because `git diff` operates per line, changing a single cell (say,
  `YTOS` in one row) shows the *entire* 527-character line as replaced, not a
  one-token change. The "better diffs" benefit CLAUDE.md advertises does not hold
  at this scale; it holds for the smaller examples (avar2.dssketch, avar2Fences,
  avar2OpticalSize — a handful of columns). The format has no line-wrapping,
  column-subsetting, or automatic grouping; a human could split one huge matrix
  into several `avar2 matrix "group-name"` blocks by output-axis subset (the
  parser accepts multiple such blocks — each resets `current_avar2_matrix_outputs`
  independently), but the writer never does this automatically, so DS → DSS always
  regenerates the one giant row.
- **Partial inputs and partial outputs**: fully expressible today. The matrix's
  `-` (no output for this axis in this row) and per-row input footprints of
  different sizes (single-axis and multi-axis rows coexisting in one matrix, as in
  the real example) already cover DS5's per-mapping partial input/output shape.
  Not a gap.
- **Mapping descriptions/names**: expressible (`mapping.name` ↔ `description`),
  confirmed round-tripping correctly in every example checked. Not a gap.
- **Hidden-axis *inputs* for HOI chaining**: syntactically writable (any declared
  axis, hidden or not, can appear in an avar2 input per `_resolve_avar2_value`),
  but semantically **useless** for the one thing HOI chaining is for — because
  avar2 mappings do not chain (AVAR2-18), a mapping whose input is a hidden
  tracking axis never fires from another mapping's output. The classic
  HOI/quadratic pattern DSSketch's own example gets right
  (`avar2QuadraticRotation.dssketch`) works by having **one mapping drive both
  hidden tracking axes from the single visible input** (`[ZROT=90] > AAAA=90,
  BBBB=90`), not by chaining through a hidden intermediate. DSSketch can express
  that pattern (single-input, multi-output tracking) cleanly, and can express
  cubic/higher HOI the same way (one visible input driving three or more hidden
  tracking axes together) — but if someone tries the "obvious" chained approach
  (`[wgt2=X] > wgt3=Y`, expecting `wgt2` to already reflect `wght`), DSSketch gives
  no indication that it silently does nothing. This is a documentation and
  validation gap more than a syntax gap: the syntax *can* express every HOI
  pattern that actually works (parallel multi-output tracking), it just doesn't
  stop you from expressing the one that doesn't (chaining).
- **DS5 `<mappings>` "groups"**: DS5 has no first-class named group above the
  individual `<mapping description="...">`; DSSketch's `avar2 matrix "name"` block
  header is an addition beyond the spec (useful for organizing a huge matrix into
  logical chunks — see above — but the writer never uses it to do so).
- **Variables (`avar2 vars`)**: a DSSketch-only convenience with no DS5
  equivalent, in the good direction — it reduces repetition (Amstelvar's matrix
  uses `$YSVL3`, `$YTOS1`, etc. dozens of times) without any expressiveness loss,
  since they resolve to plain numbers before conversion. Rounding is worth a note:
  `_parse_avar2_var_line` stores whatever float was written; nothing quantizes or
  warns about float noise across many uses of the same variable if a source
  designspace's values are not bit-identical everywhere DSSketch decided to fold
  them into one variable (see grey zone below).
- **Discrete axes interacting with avar2**: not exercised in any shipped avar2
  example, and untested here; DS5 allows discrete axes to sit alongside a
  `<mappings>` block (with the AVAR2-21 split caveat), and nothing in DSSketch's
  avar2 code path special-cases a discrete input axis in a mapping.

## 3. Grey zones

- **Input space is user, output space is design — and the model, not just the
  human, can lose track of it.** Beyond the AVAR2-09 authoring trap (§1), there is
  a structural inconsistency: going **DS → DSS**, `designspace_to_dss.py`'s
  `_convert_avar2_mapping` copies `inputLocation` values verbatim (design space,
  per the DS5 spec) into the same `DSSAvar2Mapping.input` field that, going
  **DSS-text → model**, the parser fills with **user-space** values
  (`_resolve_avar2_value`'s explicit contract). The same in-memory field means two
  different things depending on which direction produced it. It happens to
  round-trip correctly *through a label* (confirmed: AmstelvarA2's `Weight=400`
  round-trips byte-identical, because the writer picks the label by matching
  `design_value` and the parser re-resolves that same label back to the matching
  `user_value`, and the two conversions cancel out) — but it round-trips only by
  the accident of both sides agreeing to route through the label lookup table.
  Any raw numeric fallback (no matching label, as in a chained-HOI hidden-axis
  input, or an odd design value) skips that cancellation and is one accidental
  `user_value` collision away from being reinterpreted incorrectly (the mechanism
  is identical to the AVAR2-09 probe in §1, just triggered by round-tripping
  instead of hand-authoring).
- **Axis `name` gets rewritten on round-trip when the source used the tag as the
  name.** Verified on `avar2-RobotoDelta-Roman`: the original DesignSpace sets
  `<axis tag="wght" name="wght" .../>` (name equals tag, a common real-world
  pattern), and DSSketch's round-trip changes the regenerated axis's `name` to
  `"weight"` (and every avar2 `<dimension name="weight">` reference along with
  it, self-consistently — I confirmed all 38 mappings match byte-for-byte once
  compared by *tag* rather than by name, so no design-space value is lost). This
  is not a data-loss bug, but it is a spec-visible XML diff that a strict
  "round-trip should be identical" expectation, or any external tool keying off
  literal `name="wght"` strings, will trip over.
- **DSSketch's hidden-axis heuristic silently "fixes" AVAR2-17 on round-trip,
  changing the file.** Verified on the same `AmstelvarA2-Roman_avar2` example: the
  *source* XML has `hidden="0"` (implicit/false) on every one of the 61 axes that
  are avar2-output-only, i.e. the real file already exhibits AVAR2-17. DSSketch's
  `_determine_hidden_axes` (`designspace_to_dss.py:638`) infers hidden=True for
  axes that are avar2-output-only and never in avar2 input, so the round-tripped
  file marks all 61 of them `hidden="1"`. This is arguably the *correct* fix, but
  it means DS → DSS → DS is not semantically inert here: it silently changes an
  `fvar` flag on 61 axes with no log line calling this out as a correction rather
  than a preservation. A user who diffs the round-trip expecting no changes will
  be confused; a user who wants the fix will get it for free but with no record
  that it happened.
- **`$` (axis default) vs. an existing avar1 `<map>`.** `_get_axis_default`
  returns `axis.default`, which is a **user-space** number for an axis with a v1
  map (the DS spec defines `default` in user space; the v1 `<map>` translates it
  to design space). But avar2 *output* values are design space. So `XOUC=$` is
  fine for a hidden axis with no v1 map (design == user, `$` is unambiguous), but
  `wght=$` on a *visible* axis that has its own non-identity v1 map would resolve
  to the user-space default rather than the design-space default the axis's own
  `<map>` would produce for it — a subtle, currently theoretical (no example uses
  `$` on a mapped visible output axis) but real ambiguity in what `$` should mean
  once outputs land on non-identity axes.
- **What `instances auto` does with avar2 input points on hidden axes.** Per
  CLAUDE.md and `_extract_avar2_points_for_axis`, hidden axes contribute their
  avar2 input points to instance generation *only* as a fallback used to build
  `tag+value`-style unlabeled instances for **visible unlabeled axes** — hidden
  axes themselves are explicitly excluded from ever appearing in a generated
  instance's location. That is a reasonable, documented choice, but it means a
  hidden axis's avar2 output values (which is where the real "shape" data lives,
  e.g. `YTOS`, `XOUC`) never show up anywhere in instance-level review; the only
  way to notice AVAR2-13/AVAR2-16-class problems is to read the matrix directly.
- **Matrix `-` vs. omitting the axis from the row entirely**: both mean "no output
  for this axis in this mapping," and the writer always emits `-` for the omitted
  case rather than shortening the row — confirmed in the format description and
  code (`value_parts.append("-")` unconditionally for a missing axis key). Not
  ambiguous once you know the rule, but the rule ("a mapping simply omitting an
  axis" vs "a matrix row showing `-` for it") is two spellings of one idea that a
  hand-editor could plausibly get backwards when moving between linear and matrix
  format; nothing currently checks that a hand-edited matrix's dash placement
  matches what the corresponding linear mapping would have.
- **Round-trip DS → DSS → DS, all six shipped avar2 examples**: mapping sets
  (input/output values, tag-normalized) are byte-identical for
  `AmstelvarA2-Roman_avar2`, `avar2`, `avar2Fences`, `avar2OpticalSize`, and
  `avar2-RobotoDelta-Roman` (once the cosmetic axis-`name` rewrite above is
  normalized out). `avar2QuadraticRotation`'s shipped `.dssketch`/`.designspace`
  pair uses different axis tags (`AAAA`/`BBBB` vs. the `.designspace`'s `A`/`B`)
  — on inspection this looks like the example pair was hand-authored twice with
  different tag choices rather than produced by an actual round-trip, so it is a
  documentation-example inconsistency, not a converter bug; I did not find a
  genuine converter-caused data loss in any of the six.

## 4. Ranked validation proposals

Ordered by (real-world impact confirmed) × (how cheaply DSSketch could check it,
since it already has the axis table, the label table, and the user/design split in
hand — checks a linter working from raw XML alone cannot do as precisely).

1. **ERROR: avar2 mapping input normalizes to the axis default on every listed
   axis, with an output that differs from that output axis's own default (AVAR2-01/02).**
   Rule: for each mapping, compute default-delta on every input axis; if all are
   zero, check every output value against that axis's default; flag any mismatch.
   FP risk: none — this pattern only "matches" a bug, never a legitimate use (a
   default-input mapping with all-default outputs is a no-op and harmless, so the
   check should special-case that as a silent no-op rather than a warning, exactly
   as `avar2QuadraticRotation`'s `[ZROT=0] > AAAA=$, BBBB=$` does). **Confirmed to
   catch a real problem**: fires on `examples/AmstelvarA2-Roman_avar2.dssketch`
   (the shipped example) as well as on the upstream fontTools test-data
   DesignSpace it was derived from.
2. **ERROR: avar2 input or output value outside the target axis's declared
   min/max (AVAR2-03/06).** Rule: resolve every input/output axis key to its
   `DSSAxis` (visible or hidden) and range-check the numeric value after label/
   variable resolution, before writing XML. FP risk: very low — DS5 permits it
   syntactically but it is always either a mistake or something fontTools will
   clamp anyway; a warning (not hard error) is safer for min/max-inclusive
   deliberate boundary values. **Confirmed to catch a real problem**: fires on
   `work/probe2.dssketch` (constructed here); did not find an instance in the
   shipped examples, but the check is cheap and has no plausible false positive.
3. **ERROR (not log-only): unresolved axis name in an avar2 input or output
   (AVAR2-07), promoted from `DSSketchLogger.warning` to `self.validator.errors`
   / a `ConversionReport` entry.** Rule: `_resolve_axis_name` already detects this;
   just route it through the structured error path instead of (or in addition to)
   the logger, and fail the conversion (or at minimum surface it in
   `parser.errors`) rather than emitting the unresolved name into the XML. FP
   risk: none — an axis name DSSketch cannot resolve against its own axis table is
   never valid DS5 output. **Confirmed to catch a real problem**: `work/probe3.dssketch`
   (typo `XHDI` for `XHID`) converts cleanly today with only a log line an
   API caller never sees.
4. **WARNING: avar2 input value on an axis with a real (non-identity) v1
   `<map>`, given as a bare number that does not exactly match any labeled
   mapping's `user_value` (AVAR2-09, DSSketch-specific instance).** Rule: when
   resolving a numeric avar2 input on an axis whose `mappings` list is non-trivial
   (more than the identity), warn that the number is being treated as user-space
   and interpolated/matched against labels, and show what design-space value it
   resolved to — so the author can catch a 550-vs-512.5-style mismatch before it
   ships. FP risk: moderate — some numeric inputs are deliberately meant as exact
   design-space values (this is genuinely ambiguous, see §3), so this should be a
   warning with the resolved value shown, not a hard error. **Confirmed to catch a
   real problem**: `work/probe1.dssketch` (constructed here) silently emits `550`
   instead of the correct `512.5`.
5. **WARNING: no explicit multi-axis corner mapping for a combination of
   non-default input axes that appear separately in single-axis mappings
   (AVAR2-10/32).** Rule: collect the set of axes that appear as sole input in any
   mapping; for each pair (or n-tuple) of such axes, check whether a mapping
   exists whose input is exactly that combination; if not, warn that deltas will
   sum at that corner. FP risk: moderate-to-high for fonts that intentionally rely
   on additive avar2 behavior at some corners (the spec allows it; Amstelvar just
   chooses not to) — should be a warning, and should exempt corners already
   covered by an explicit `n`-axis mapping. **Would catch a real gap** if applied
   to a reduced version of the Amstelvar file (e.g. keeping only the 9 single-axis
   rows and dropping the 20 corner rows the real font actually ships); on the full
   shipped example it correctly finds nothing to flag, since all 20 corners the
   axes combinations touch are present.
6. **INFO/WARNING: avar2 output axis is not marked `hidden` and never appears as
   an avar2 input anywhere (AVAR2-17).** Rule: DSSketch already computes exactly
   this set in `_determine_hidden_axes` for its own DS→DSS heuristic; surface it
   as a diagnostic on the DS→DSS path (not just act on it silently) and add the
   mirror check on the DSS→DS path for a `.dssketch` file whose `axes` (not
   `axes hidden`) section defines an axis that only ever shows up in avar2 output.
   FP risk: low. **Confirmed to catch a real problem**: the shipped
   `AmstelvarA2-Roman_avar2.designspace` has this on 61 axes; DSSketch's own
   round-trip currently "fixes" it with zero visibility (§3) — logging it turns a
   silent side effect into a reviewable diagnostic.
7. **WARNING: avar2 output on a visible (non-hidden) axis (AVAR2-11 read
   together with the delta-not-absolute semantics).** Rule: flag any avar2
   mapping whose output includes an axis that is not in `hidden_axes` — this is
   legal per spec but near-certain to be a delta-semantics surprise for an author
   who thinks in "set X to Y." FP risk: moderate (deliberately warping a visible
   axis via avar2 — e.g. clamping wdth at high weights — is a real, documented
   avar2 use case), so this should carry an explanatory message about add-not-set
   semantics rather than imply it's wrong. Not found in any shipped DSSketch
   example (all avar2 outputs in all six examples target hidden axes only), so
   this specific check would currently be silent on the corpus available — but it
   is cheap insurance given how naturally the `AXIS=value` syntax invites the
   wrong reading.
8. **Documentation-only, high value, zero FP risk: state the add-not-absolute and
   non-chaining semantics explicitly in CLAUDE.md's avar2 section**, next to the
   existing `$`/`-`/variables explanation, since nothing else in the toolchain can
   fix a wrong mental model and this project's own docs are where a DSSketch
   author's model of avar2 gets formed.
9. **WARNING: duplicate or clamp-colliding avar2 inputs (AVAR2-04/05).** Rule:
   after range-clamping (item 2) and label/variable resolution, check the full set
   of `(axis, value)` input tuples per mapping for exact duplicates across
   `avar2_mappings`. FP risk: low. Not found in any shipped example; cheap to add
   alongside item 2's clamping pass since it needs the same resolved values.
10. **WARNING: avar2 mapping input references a hidden axis with no path for a
    user or the `fvar`/API to ever set it (dead-code chaining, AVAR2-18
    read together with the hidden-axis-not-user-settable-by-instances design).**
    Rule: for each hidden axis that appears as an avar2 *input*, confirm it also
    receives a value from some *other* source than avar2 output (impossible by
    construction, since hidden axes have no fvar exposure and DSSketch's
    generator never places instances on them) — in practice this means: **any**
    avar2 mapping whose input includes a hidden axis is dead unless that hidden
    axis is meant to be set by an external API/CSS `font-variation-settings`,
    which DSSketch cannot know. Recommend a WARNING that names the pattern
    explicitly ("hidden axis used as avar2 input — this only fires if something
    outside the font sets it directly; avar2 mappings do not chain") rather than
    trying to distinguish intentional from accidental cases. FP risk: moderate,
    since AVAR2-12 (deliberately user-settable hidden axis) is a legitimate,
    documented pattern — the warning's wording matters more than its trigger
    condition here.

None of these require anything DSSketch does not already compute or store; every
one draws on data structures (`DSSAxis.mappings`, `hidden_axes`,
`DSSAvar2Mapping.input/output`) that exist today in `core/models.py`. The
highest-leverage first three (1–3) are also the only ones an XML-only linter (like
the audited tool, which never even reads `axisMappings`) structurally cannot do as
well, because DSSketch already has the label table and the user/design split that
a raw DesignSpace does not surface explicitly.
