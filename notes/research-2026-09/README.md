# DSSketch gap research (September 2026)

This research asks what DSSketch is missing, measured against an independent
audit of DesignSpace failure modes: `designspace-lint`'s
`docs/audit/2026-09-coverage/`, 163 rows derived from the specs and the fontTools
source. It rests on two design principles:

- DSSketch sits above DesignSpace. Instances are generated from labeled mappings
  (`instances auto` / `skip`) rather than listed, so per-instance features are
  out of scope by design.
- DS → DSS diagnoses rather than transforms. DSS-only constructs are never
  inferred from a DesignSpace.

The headline findings below were re-verified by hand, beyond the reports' own
probes.

## Reports

| File | Question |
|---|---|
| `expressibility.md` | Which DesignSpace 5 features DSSketch can express: supported, worth adding, out of scope by design, grey zone. Round-trip probes included |
| `avar2-hoi.md` | The avar2/HOI rows of the audit against DSSketch's avar2 syntax: traps it lets through, gaps in what it can express, grey zones, proposed checks |
| `validation-gaps.md` | Every non-avar2 audit row: prevented by construction, caught, could catch, or **can introduce** (bugs DSSketch's own generation ships) |

`repro/` holds the probes behind the reports. Run the `repro/validation/*.py`
scripts from the repository root with `uv run python`. The ones that need UFOs
expect to run inside `repro/validation/` after `python make_ufos.py`.

## Plan

**1.2.2: fixes only. Done 2026-09-28** (commits `2656cc7`..`121f82e`). Correct
files keep their behaviour; silent failures become errors. The one exception is
item 4: sketches that an older DS → DSS left with design values in avar2 inputs.
Those values are caught when they fall outside the axis's user range, and the
CHANGELOG explains how to migrate.
1. **Discreteness is inferred, not stored.** DSS → DS treats an axis as discrete
   only if it is named `italic`/`ital`, so `slnt discrete` and custom discrete axes
   become continuous. DS → DSS writes a 3+-value discrete axis as a range
   (`0:0:2`), and converting it back crashes with "multiple @base".
2. **Rule OR becomes AND.** A DesignSpace rule with several `<conditionset>`s (OR)
   is flattened into one AND condition on DS → DSS.
3. **Omitted source coordinates use the user-space default** where the
   design-space default is needed.
4. **avar2 numeric input is not mapped.** A numeric input that is not a label is
   passed through instead of being mapped through the axis `<map>`: `[wght=550]`
   stays 550 where 512.5 is correct. The model also carries user values when parsed
   from text and design values when converted from DS.
5. **Two labels with the same user value on one axis** corrupt the axis map and
   `instances auto`.
6. **Rule glyphs are checked against the union of all masters**, not the default
   master, and explicit `a > a.alt` rules are not checked at all.
7. **An explicit `instances` list is dropped without a word.**
8. **Label-based axis ranges skip the min ≤ default ≤ max check.**

**1.3.0: checks and diagnostics.**
- avar2 checks: a default-input mapping (AVAR2-01) is an error, and the
  `AmstelvarA2-Roman` example has one; inputs/outputs outside the axis; an unknown
  axis name as a real error rather than a log line; corner completeness; outputs on
  visible axes.
- Source range and duplicate locations, axis map monotonicity, rule min ≤ max,
  UPM consistency.
- ConversionReport entries for everything DS → DSS drops without saying so:
  per-instance and per-source fields, `rulesProcessingLast`, `elidedFallbackName`,
  and the hidden-axis heuristic's changes.

**1.4.0: syntax.** Document `lib` (present in 4 of 4 real files, lost today); rule
OR; `rules processing last`; `elided-fallback`; a readable form for large avar2
matrices; documentation of avar2 output semantics (outputs are deltas, and mappings
never chain).

## Open decisions

1. ~~Keep the `hidden` heuristic?~~ **Decided: removed.** Only `hidden="1"` hides
   an axis. A visible axis driven only by avar2 is reported
   (`AXIS_OUTPUT_ONLY_VISIBLE`) rather than hidden.
2. ~~`DSSAvar2Mapping.input` always user space?~~ **Decided: yes (1.2.2).** DS → DSS
   maps inputs back through the axis `<map>`. Legacy design values are caught when
   they fall outside the axis's user range.
3. ~~`$` on a visible output axis with its own `<map>`?~~ **Decided: the design
   default (1.2.2).** avar2 outputs are design space, so this is the only
   consistent reading.
4. Explicit instances: **to be discussed separately.** The maintainer's direction:
   listing instances one by one, with all their parameters, conflicts with what a
   sketch is. Instead, an input check:
   - Instances that `instances auto` (plus `skip`) reproduces are dropped as
     redundant. The position-based fit report from DS → DSS already tells which
     ones those are.
   - For the ones it cannot reproduce, a *targeted* description that states only
     what is not reproducible. Its shape is still open: a per-instance override,
     an extra point, or a naming exception.

   Until then, an explicit instance line is reported as ignored (1.2.2).
