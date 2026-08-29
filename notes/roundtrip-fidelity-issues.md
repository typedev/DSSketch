# Roundtrip Fidelity: Open Issues

Status: **for discussion — no implementation yet**
Found: 2026-08-29, on DSSketch 1.1.18

## Why this note exists

Running the `examples/` corpus through DS → DSSketch → DS turned up several
differences between the original DesignSpace and the one that comes back. Three
were reported informally; investigating them to root cause changed the picture:

- one of the three is **not a bug** — the output is semantically identical;
- another is a **symptom of something larger** than what was reported;
- **two further problems** surfaced that were not on the list.

None of the remaining items is a typo-level defect. Each turns on a design
question about what the format is for — most sharply: *is `hidden` a property
that can be derived, or a statement the designer makes?* That is why this is a
discussion note and not a plan.

The two candidate fixes named below were verified by monkeypatching the corpus
run; no code in `src/` has been changed.

## What "fidelity" can mean here

DSSketch is not a symmetric transcoder. It sits **above** DesignSpace: it is the
format a project is meant to be designed in, and DS → DSSketch exists to lift an
existing project out of verbose XML, not to mirror XML one-to-one.

That asymmetry decides what we are allowed to expect:

- **DSSketch declares intent; DesignSpace records the result.** `instances auto`
  and its `skip` list are instructions to a generator. A DesignSpace holds only
  the instances that came out the other side.
- Therefore `skip` **cannot survive** DSSketch → DS → DSSketch, and a DS → DSSketch
  conversion **must not try to reconstruct it**. Inferring a skip list from which
  instances happen to be absent would be inventing authorial intent from output —
  the same mistake as issue 2, where avar2 topology is used to infer `hidden`.
- What DS → DSSketch *can* owe us is honesty: if the sketch it writes does not
  describe the DesignSpace it read, say so.

Read the issues below with that split in mind. Issues 1, 2 and 4 are failures of
fidelity — the converter changes data it should have carried across. Issue 5 is
different in kind: it is about a DSSketch-only construct, and the fix is a
diagnostic, not a transformation.

---

## 1. Mixed source paths collapse into a bogus common directory

**Severity: high — produces unusable paths.**

### Symptom

In `avar2-RobotoDelta-Roman.designspace`, all 75 masters come back with an
`instances/` prefix:

```
Roboto-Delta-BARS0.ufo   →   instances/Roboto-Delta-BARS0.ufo
Roboto-Delta-GRAD150.ufo →   instances/Roboto-Delta-GRAD150.ufo
```

The generated sketch carries `path instances` even though the document declares
zero instances.

### Root cause

`DesignSpaceToDSS._determine_sources_path()` — `converters/designspace_to_dss.py:132`.

The file mixes locations: **68 masters sit at the root, 7 sit in `instances/`**.
The directory-collecting loop (line 149) reads:

```python
for path in source_paths:
    if path.parent != Path("."):
        directories.add(path.parent)
```

Root-level sources are **excluded from the set** rather than contributing
`Path(".")`. So `{root × 68, instances/ × 7}` collapses to `{instances}`,
`len(directories) == 1` fires, and the function declares `instances` the common
directory of all 75. `_convert_source()` then strips the prefix from the 7 that
have it, the writer emits `path instances`, and on read-back every source gets
it prepended.

### Candidate fix (verified)

Let root-level sources contribute `Path(".")`. The set becomes
`{Path("."), Path("instances")}`, `len > 1`, and the function correctly returns
`None`, leaving each source with its own relative path.

### Open questions

None. This is an unambiguous defect.

---

## 2. The `hidden` heuristic overwrites the designer's decision

**Severity: high — changes which axes a built font exposes.**

### Symptom

Reported as "axis `XTSP` moves from position 5 to position 9". The reordering
is real but it is a side effect. The actual change:

```
avar2-RobotoDelta-Roman:   hidden axes  0 of 39  →  30 of 39
```

The original marks no axis hidden. The roundtrip marks thirty. Those axes would
disappear from the user-facing axis list of a font built from the result.
`avar2QuadraticRotation` is affected the same way.

### Root cause

Two separate mechanisms combine.

**The classification.** `_determine_hidden_axes()` —
`converters/designspace_to_dss.py:458` — treats an axis as hidden when it
appears only in avar2 *output* and never in *input*:

```python
if in_output and not in_input:
    hidden_axes.add(axis.name)
```

**The ordering.** Hidden-ness is encoded purely by *which list an axis lands in*
— `DSSDocument.axes` vs `DSSDocument.hidden_axes`. `DSSAxis` has no `hidden`
field. The writer emits the `axes` block and then the `axes hidden` block, so an
axis that sat fifth among the visible ones re-emerges first among the hidden
ones. Interleaved order is not representable in the sketch at all.

### Prior context

`notes/hidden-axes-detection-plan.md` records this as a deliberate decision, and
states the conflict outright:

> In original `AmstelvarA2-Roman_avar2.dssketch`, axes WDSP and GRAD were
> manually marked as visible ("Semi-parametric - visible to advanced users").
> However, our algorithm correctly identifies them as hidden […]
> **This is a design decision by the font designer.**

So the tension was seen at the time and resolved in favour of the algorithm.

That same note logs "Roundtrip test passes: DS→DSS→DS→DSS preserves hidden
status". That is true and not reassuring: the classification is *idempotent*, so
it is stable from the second pass onward. The pass that changes the data is the
first one, DS→DSS→DS, and it was not what the test measured.

### Candidate fix (verified)

Read only the explicit attribute:

```python
return {a.name for a in ds_doc.axes if getattr(a, "hidden", False)}
```

On the corpus this fixes the classification **and** the ordering, because no
file then has hidden axes interleaved among visible ones.

### Open questions

1. **Is `hidden` derivable or declared?** In DesignSpace it is an authorial
   statement about what to expose. avar2 topology is evidence about it, not a
   definition of it. If we accept that, the heuristic has to go: it is not
   DS→DSS's job to correct its input.
2. **If the heuristic is worth keeping, where does it belong?** It is genuinely
   useful when hand-authoring a sketch for a parametric font. That is a
   different operation from faithfully reading someone's DesignSpace.
3. **Does axis order need protecting on its own?** Only if a DesignSpace exists
   with explicitly-hidden axes interleaved among visible ones. There is none in
   the corpus. Protecting it would mean adding `DSSAxis.hidden` plus an
   `@hidden` flag inside a single `axes` section, keeping `axes hidden` as
   shorthand — a real format extension, worth doing only if such files turn up.

---

## 3. Master coordinates in Amstelvar — not a bug

**Severity: none. Recommend closing.**

### Symptom

In `AmstelvarA2-Roman_avar2.designspace`, every one of the 126 masters comes
back with a location of 67 axes instead of 63.

### Why it is not a bug

The four added axes are `opsz`, `wght`, `wdth`, `XTSP`, and each is added at
**exactly its own default** (14, 400, 100, 0). In DesignSpace an omitted
dimension *means* the axis default, so the two documents describe the same
locations.

The filling happens in the parser, not the converter: a source line in a sketch
lists only the axes that matter, and the parser materialises the full location.
That is the format working as designed — it is what lets

```dssketch
    Roboto-Delta-GRAD150 GRAD=150
```

stand in for a location across 39 axes.

The only cost is verbosity in the written XML: 126 × 4 = 504 redundant
`<dimension>` elements.

### Recommendation

Close it. Document the behaviour, and compare locations *modulo defaults* when
checking roundtrip fidelity, so it stops showing up as a false difference.
Teaching the model to distinguish "axis absent" from "axis at default" would add
state for no semantic gain.

---

## 4. An axis name is lost when it equals the tag

**Severity: medium — rewrites the file, builds the same font.**

### Symptom

`avar2-RobotoDelta-Roman` writes its axes as `<axis tag="opsz" name="opsz">`.
After a roundtrip:

```xml
<axis tag="opsz" name="optical">
...
<dimension name="optical" xvalue="0"/>   <!-- was name="opsz" -->
```

Every axis whose `name` equals its `tag` is renamed to the long human-readable
form, and every `<dimension>` key follows. The document stays internally
consistent, so a font built from it is unchanged — but the file is rewritten and
anything keyed on the axis name breaks.

Only RobotoDelta is affected in the corpus; the other examples use `"Weight"` or
`"weight"`, which the `display_name` mechanism preserves correctly.

### Root cause

`converters/designspace_to_dss.py:179` deliberately discards the name when it
matches the tag:

```python
display_name = axis.name if axis.name != axis.tag else None
```

`converters/dss_to_designspace.py:208` (and 175, 249) then falls back to the
internal long name:

```python
axis.name = dss_axis.display_name if dss_axis.display_name else dss_axis.name
```

For a standard axis `dss_axis.name` is `"optical"`, `"weight"`, and so on.

### This deviates from the written design

`notes/axis-display-name-plan.md` specifies the opposite fallback:

> 3. If omitted, use **tag** as name (current behavior)
> **5.2** Fall back to **tag** if no display_name

So the intended target was `name="opsz"`. The implementation falls back to the
long name instead.

### Candidates

**(a) Preserve the original name always** — set `display_name = axis.name`
unconditionally, and let the writer emit the quoted name even when it equals the
tag, producing `opsz 8:14:144 "opsz"`. **Verified: the whole corpus round-trips
clean.** Nothing else changes, because every other file already emits a quoted
name (`"weight"`, `"Weight"`).

**(b) Fall back to the tag**, as the plan specifies. Verified partially: the
axes come out right, but master locations are keyed by the DSS-internal axis
name, so those keys need remapping too or RobotoDelta still differs.

### Open question

Which one is correct? (a) preserves what the author wrote. (b) matches the
documented design and reads more cleanly, but changes the default for
hand-written sketches — `wght 100:400:900` would produce `name="wght"` rather
than today's `name="weight"`.

---

## 5. `instances auto` is written without checking that it fits

**Severity: medium. Fix is a diagnostic, not a transformation.**

### Two related behaviours

**With `optimize=True` (the default)** the writer discards explicit instances and
emits `instances auto` — `writers/dss_writer.py:160`:

```python
if self.optimize:
    # When optimizing with explicit instances, use instances auto
    # (assumes instances can be regenerated from axis labels)
    lines.append("instances auto")
```

The assumption is usually sound. It is never checked.

**With `optimize=False`** the writer prints an explicit list
(`_format_instance`, `writers/dss_writer.py:693`) that the parser cannot read.
`parsers/dss_parser.py:1031`:

```python
if line != "auto" and not self.in_skip_subsection:
    # TODO: implement explicit instance parsing if needed
    pass
```

Measured on `SuperFont-6x2`: 12 instances → written as an explicit list → parsed
back as **0**, with `instances_auto` and `instances_off` both false. That path is
not reachable from the CLI, so nothing in normal use hits it today.

### The analyser — implemented 2026-08-29

> Built as `DesignSpaceToDSS._report_instances_auto_fit()`; tests in
> `tests/test_instances_auto_fit.py`. The open question below (the unreadable
> explicit-instance branch) is untouched.


`createInstances()` accepts a `DesignSpaceDocument` plus the `DSSDocument` being
built, so DS → DSSketch can generate what `instances auto` *would* produce and
compare it against what the DesignSpace actually declares — no round-trip
needed. Measured cost on the largest example (315 instances): 1.1 ms → 1.7 ms.
`core/instances.py` imports only `utils.logging`, so there is no import cycle.

**Compare by location, not by name.** Names diverge for reasons that are not
losses; positions in the design space are the thing that either survives or does
not. On the corpus before the examples were regenerated, comparing by name
reported 90 phantom losses; comparing by location reported zero.

Three outcomes, meaning three different things:

| finding | meaning | level |
|---|---|---|
| a declared position `auto` never reaches | real loss — the sketch cannot describe this DesignSpace | WARNING |
| same position, different style name | the naming rules disagree with the source | WARNING |
| `auto` produces positions the DS does not declare | the DS was filtered; `skip` is how a sketch expresses that | INFO |

The third is **not a defect**. It is the measurable footprint of a DSSketch-only
feature, and the report should say so — naming the extra instances so a human can
write the `skip` block, and never writing one automatically.

### What the corpus says

After regenerating the examples (Appendix B), across all seven files that carry
instances:

```
lost positions: 0        renamed: 0        extra: 15, 4, 4, 3, 1, 0, 0
```

and the extras match the number of skip rules that actually fire, exactly:

| file | effective skip rules | extra instances |
|---|---|---|
| MegaFont-WithSkip | 15 | 15 |
| TestFont-MultiElidable | 4 | 4 |
| TestFont-Skip | 3 | 3 |
| TestFont-SkipValidation | 1 | 1 |

So the only residual gap between a DesignSpace and what `instances auto`
reproduces is precisely the `skip` information — which is exactly the part that
lives above DesignSpace and cannot be recovered from it. The generator itself
loses nothing.

### Open question

The analyser is worth building on its own merits. Separately: what to do with the
unreadable explicit-instance branch — complete the parser, warn on write, or drop
it. Nothing in the corpus needs an explicit list.

## Appendix A: corpus status

15 files: the 14 in `examples/` plus one production file. "clean" means the
original and the round-tripped DesignSpace agree on axes, sources and instances,
comparing locations modulo axis defaults (see issue 3).

| file | today | with fixes 1, 2, 4 |
|---|---|---|
| AmstelvarA2-Roman_avar2 | axes | **clean** |
| avar2-RobotoDelta-Roman | axes, sources | **clean** |
| avar2QuadraticRotation | axes | **clean** |
| avar1 | clean | clean |
| avar2 | clean | clean |
| avar2Fences | clean | clean |
| avar2OpticalSize | clean | clean |
| SuperFont-6x2 | clean | clean |
| production 1-axis file | clean | clean |
| MegaFont-3x5x7x3 | clean | clean |
| MegaFont-WithSkip | skip only | skip only |
| TestFont-ElidableScenarios | skip only | skip only |
| TestFont-MultiElidable | skip only | skip only |
| TestFont-Skip | skip only | skip only |
| TestFont-SkipValidation | skip only | skip only |

Nothing regresses. The three large avar2 files become clean.

"skip only" means the sole difference is that `instances auto` regenerates the
instances the sketch's `skip` block removes — expected, and not recoverable from
a DesignSpace. See issue 5.

## Appendix B: the examples were stale — now regenerated

Before 2026-08-29 the example DesignSpace files carried pre-fix instance names:

```
in the example:   Compressed        Compressed Reverse        Condensed
generated now:    Compressed Regular  Compressed Regular Reverse  Condensed Regular
```

This is the corrected behaviour from "Weight axis excluded from elidable
removal" (CHANGELOG 1.1.17) — font compilers expect a weight name in the
styleName. The generator was right; the examples were never regenerated.

Two `.dssketch` files were stale as well, and this is the more interesting part:
their `skip` rules were written against the **old** names, so they silently
stopped matching. The built-in unused-rule validation had been reporting it all
along:

```
MegaFont-WithSkip.dssketch       Unused skip rule: 'Extended'
TestFont-MultiElidable.dssketch  Unused skip rule: 'Extended'
                                 Unused skip rule: 'HighContrast'
```

Both were updated to the current names (`Extended Regular`,
`HighContrast Regular`), along with the explanatory comments in
`TestFont-MultiElidable.dssketch`, which still described the pre-fix elidable
behaviour.

`TestFont-SkipValidation.dssketch` also reports two unused rules and was **left
alone**: its own comments mark them as deliberate fixtures for that warning.

The seven instance-bearing examples were then regenerated from their `.dssketch`
sources. Instance counts came out unchanged across the board — 315, 300, 12, 14,
4, 9, 7 — because fixing the skip rules restored what the files had always
declared. Three of the seven were already byte-identical.

The remaining eight examples (`avar1`, `avar2*`, `AmstelvarA2`, `RobotoDelta`)
were **not** regenerated. They declare no instances, so the naming ambiguity
never touched them, and regenerating would degrade them: it downgrades
`format="5.2"` to `5.1`, adds redundant `<labelname>` elements, and expands
master locations (issues 3 and 4). They are input fixtures and should stay as
they arrived from the fontTools test data.

---

## Summary

| # | issue | verdict | needs a decision |
|---|---|---|---|
| 1 | mixed paths → `instances/` prefix | defect | no |
| 2 | `hidden` heuristic rewrites input | defect, by design | **yes** — derived or declared? |
| 3 | Amstelvar master locations | not a bug | close it |
| 4 | axis name lost when `name == tag` | defect, deviates from plan | **yes** — which fallback? |
| 5 | `instances auto` written unchecked | build the analyser | **yes** — what about the dead branch? |
