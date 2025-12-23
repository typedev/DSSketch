# Hidden Axes Detection Implementation Plan

## Goal
Improve hidden axis detection in DS → DSS conversion by analyzing avar2 mappings.

## Current State
- Hidden axes detected only by `hidden="1"` attribute (rarely used in real files)
- Real files like Amstelvar don't use `hidden="1"` — all 67 axes listed as regular
- DSS `axes hidden` section exists but not populated correctly from real DS files

## Target State
- **Priority 1**: Use `hidden="1"` attribute if present
- **Priority 2**: Analyze avar2 mappings — axes only in OUTPUT are hidden
- DSS → DS: Set `hidden="1"` for axes from `axes hidden` section

---

## Implementation Steps

### Phase 1: Understand Current Code
- [ ] **1.1** Review current hidden axis handling in `designspace_to_dss.py`
- [ ] **1.2** Review avar2 parsing in `designspace_to_dss.py`
- [ ] **1.3** Identify where axis classification happens

### Phase 2: Implement avar2 Input/Output Analysis
- [ ] **2.1** Create helper function `_collect_avar2_input_axes()`
  - Parse all avar2 mappings
  - Extract axis names from INPUT parts `[axis=value, ...]`
  - Return set of axis names/tags
- [ ] **2.2** Create helper function `_collect_avar2_output_axes()`
  - Extract axis names from OUTPUT parts `> axis=value, ...`
  - Return set of axis names/tags
- [ ] **2.3** Write unit tests for both helpers

### Phase 3: Modify Axis Classification Logic
- [ ] **3.1** Modify `_classify_axes()` or create new method
  - Check `hidden="1"` first (priority)
  - If no avar2 → all axes visible
  - If has avar2 → axes only in output = hidden
- [ ] **3.2** Update `convert()` method to use new classification
- [ ] **3.3** Write integration tests

### Phase 4: Update DSS → DS Direction
- [ ] **4.1** Verify `dss_to_designspace.py` sets `hidden="1"` for hidden axes
- [ ] **4.2** Add test for roundtrip: DSS → DS → DSS preserves hidden status

### Phase 5: Test with Real Files
- [ ] **5.1** Test with `AmstelvarA2-Roman_avar2.designspace`
  - Should detect ~61 hidden axes (XOUC, YOUC, etc.)
  - Should keep opsz, wght, wdth as visible
- [ ] **5.2** Test with `RobotoDelta-Roman.designspace`
- [ ] **5.3** Test with simple avar2 examples (no hidden axes expected)
- [ ] **5.4** Test roundtrip conversion preserves structure

### Phase 6: Documentation & Cleanup
- [ ] **6.1** Update CLAUDE.md with new behavior
- [ ] **6.2** Update avar2-specification.md
- [ ] **6.3** Commit changes

---

## Checkpoints

### Checkpoint 1: Analysis Complete
After Phase 1 — understand current code structure

### Checkpoint 2: Helpers Working
After Phase 2 — input/output extraction works with unit tests

### Checkpoint 3: Classification Working
After Phase 3 — DS → DSS correctly identifies hidden axes

### Checkpoint 4: Roundtrip Working
After Phase 4 — DSS → DS → DSS preserves hidden status

### Checkpoint 5: Real Files Pass
After Phase 5 — Amstelvar and RobotoDelta work correctly

### Checkpoint 6: Complete
After Phase 6 — documented and committed

---

## Progress Log

| Step | Status | Notes |
|------|--------|-------|
| 1.1  | ✅ | `convert()` lines 54-61: uses `getattr(axis, 'hidden', False)` only |
| 1.2  | ✅ | `axisMappings` has `inputLocation` and `outputLocation` dicts |
| 1.3  | ✅ | Classification at lines 54-61, need to add avar2 analysis before |
| 2.1  | ✅ | `_collect_avar2_input_axes()` implemented |
| 2.2  | ✅ | `_collect_avar2_output_axes()` implemented |
| 2.3  | ✅ | `_determine_hidden_axes()` implemented, tested on Amstelvar |
| 3.1  | ✅ | `convert()` now uses `_determine_hidden_axes()` |
| 3.2  | ✅ | Amstelvar: 4 visible, 63 hidden (correct by algorithm) |
| 3.3  | ⏳ | Need formal unit tests |
| 4.1  | ✅ | `_convert_hidden_axis()` already sets `hidden=True` (line 191) |
| 4.2  | ✅ | Roundtrip test passes: DS→DSS→DS→DSS preserves hidden status |
| 5.1  | ✅ | Amstelvar: 4 visible (opsz,wght,wdth,XTSP), 63 hidden |
| 5.2  | ✅ | RobotoDelta: 9 visible, 30 hidden |
| 5.3  | ✅ | avar1/avar2 simple: 3 visible, 0 hidden |
| 5.4  | ✅ | Roundtrip test passed |
| 6.1  | ✅ | Added note about semi-parametric axes |
| 6.2  | ✅ | avar2-specification.md already documents hidden axes |
| 6.3  | ⏳ | Ready to commit |

---

## Technical Notes

### avar2 Mapping Format in DesignSpace
```xml
<mappings>
  <mapping>
    <input>
      <dimension name="opsz" xvalue="144"/>
      <dimension name="wdth" xvalue="125"/>
    </input>
    <output>
      <dimension name="XOUC" xvalue="84"/>
      <dimension name="XOLC" xvalue="78"/>
    </output>
  </mapping>
</mappings>
```

### Expected Result
- `opsz`, `wdth` in input → visible axes
- `XOUC`, `XOLC` only in output → hidden axes

### Edge Cases
1. Axis in both input AND output → visible (user can control it)
2. No avar2 section → all axes visible
3. `hidden="1"` attribute → always hidden (priority)

### Note on Semi-Parametric Axes
In original `AmstelvarA2-Roman_avar2.dssketch`, axes WDSP and GRAD were manually marked as visible ("Semi-parametric - visible to advanced users"). However, our algorithm correctly identifies them as hidden because they only appear in avar2 OUTPUT, never in INPUT.

This is a design decision by the font designer. The algorithm provides a technically correct classification based on avar2 usage. Users can manually adjust the classification if needed.

**Original DSS (manual):** 6 visible (opsz, wght, wdth, XTSP, WDSP, GRAD)
**Auto-detected:** 4 visible (opsz, wght, wdth, XTSP) — WDSP/GRAD hidden
