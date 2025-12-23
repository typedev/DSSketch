# Axis Display Name Implementation Plan

## Goal
Preserve original axis display names during DS → DSS → DS roundtrip conversion.

## Problem
- Original: `name="Optical size"` in DesignSpace
- After roundtrip: `name="optical"` (lowercase alias used as name)
- Display names are shown in font UI (GlyphsApp, Illustrator, etc.)

## Solution
Add optional display name syntax at end of axis line:
```dssketch
opsz 8:14:144 "Optical size"
```

## Syntax Rules
1. Display name is optional, comes after range
2. Must be quoted: `"Display Name"`
3. If omitted, use tag as name (current behavior)
4. Works with both tags and aliases: `optical 8:14:144 "Optical size"`

---

## Implementation Steps

### Phase 1: Update Parser
- [ ] **1.1** Modify `_parse_axis_line()` to detect quoted string at end
- [ ] **1.2** Store display name in `DSSAxis.display_name` field
- [ ] **1.3** Handle edge cases (quotes in name, empty name)
- [ ] **1.4** Test parser with new syntax

### Phase 2: Update Models
- [ ] **2.1** Add `display_name: Optional[str]` to `DSSAxis` model
- [ ] **2.2** Update any model initialization/serialization

### Phase 3: Update Writer
- [ ] **3.1** Modify `_format_axis()` to output display name when present
- [ ] **3.2** Only output if display_name != tag (avoid redundancy)
- [ ] **3.3** Test writer output

### Phase 4: Update DS → DSS Converter
- [ ] **4.1** Extract axis.name from DesignSpace
- [ ] **4.2** Store in DSSAxis.display_name
- [ ] **4.3** Test with Amstelvar

### Phase 5: Update DSS → DS Converter
- [ ] **5.1** Use display_name for axis.name in DesignSpace
- [ ] **5.2** Fall back to tag if no display_name
- [ ] **5.3** Test roundtrip

### Phase 6: Handle avar2 Mappings
- [ ] **6.1** Ensure avar2 input/output locations use correct names
- [ ] **6.2** Build name→tag and tag→name mappings
- [ ] **6.3** Test avar2 roundtrip with Amstelvar

### Phase 7: Integration Testing
- [ ] **7.1** Test MegaFont (no display names) - unchanged behavior
- [ ] **7.2** Test Amstelvar - display names preserved
- [ ] **7.3** Test roundtrip: DS → DSS → DS
- [ ] **7.4** Verify avar2 mappings use correct names

### Phase 8: Documentation & Commit
- [ ] **8.1** Update CLAUDE.md with new syntax
- [ ] **8.2** Update examples if needed
- [ ] **8.3** Commit changes

---

## Checkpoints

### Checkpoint 1: Parser Works
After Phase 1+2 — parser reads `opsz 8:14:144 "Optical size"` correctly

### Checkpoint 2: Writer Works
After Phase 3 — writer outputs display names

### Checkpoint 3: DS → DSS Works
After Phase 4 — Amstelvar axes have display names in .dssketch

### Checkpoint 4: DSS → DS Works
After Phase 5 — DesignSpace has correct axis names

### Checkpoint 5: avar2 Works
After Phase 6 — avar2 mappings use original names

### Checkpoint 6: Complete
After Phase 7+8 — all tests pass, documented, committed

---

## Progress Log

| Step | Status | Notes |
|------|--------|-------|
| 1.1  | ✅ | Added regex to extract `"..."` at end of line |
| 1.2  | ✅ | `display_name` stored in DSSAxis |
| 1.3  | ✅ | Empty names handled by regex |
| 1.4  | ✅ | Parser test passed |
| 2.1  | ✅ | Added `display_name: Optional[str] = None` to DSSAxis |
| 2.2  | ✅ | No changes needed |
| 3.1  | ✅ | Added display_name output in both discrete and continuous cases |
| 3.2  | ✅ | Only output when display_name != tag |
| 3.3  | ✅ | Writer test passed |
| 4.1  | ✅ | `axis.name` from DS stored as `display_name` |
| 4.2  | ✅ | Set when name differs from tag |
| 4.3  | ✅ | Amstelvar shows "Optical size", "Weight", "Width" |
| 5.1  | ✅ | `_convert_axis` uses `display_name` for axis.name |
| 5.2  | ✅ | Falls back to `name` if no display_name |
| 5.3  | ✅ | Roundtrip test passed |
| 6.1  | ✅ | `_resolve_axis_name` returns display_name when available |
| 6.2  | ✅ | Mapping uses display_name for inputLocation |
| 6.3  | ✅ | All 29 avar2 mappings preserved correctly |
| 7.1  | ✅ | MegaFont: backward compat OK |
| 7.2  | ✅ | Amstelvar: all 67 axes names preserved |
| 7.3  | ✅ | Full roundtrip DS→DSS→DS success |
| 7.4  | ✅ | avar2 mappings use original names |
| 8.1  | ⏳ | Ready to update |
| 8.2  | ⏳ | Examples work correctly |
| 8.3  | ⏳ | Ready to commit |

---

## Technical Notes

### Regex Pattern for Display Name
```python
# Match: tag range "display name"
# Example: opsz 8:14:144 "Optical size"
AXIS_WITH_NAME_PATTERN = r'^(\w+)\s+(.+?)\s+"([^"]+)"$'

# Or simpler: check if line ends with quoted string
if line.rstrip().endswith('"'):
    # Extract quoted part
    match = re.search(r'"([^"]+)"$', line)
    display_name = match.group(1)
    line = line[:match.start()].strip()
```

### DSSAxis Model Update
```python
@dataclass
class DSSAxis:
    name: str           # Internal name (tag or alias)
    tag: str            # 4-char tag (wght, opsz, etc.)
    minimum: float
    default: float
    maximum: float
    mappings: List[DSSAxisMapping]
    display_name: Optional[str] = None  # NEW: UI display name
```

### Writer Logic
```python
def _format_axis(self, axis: DSSAxis) -> str:
    line = f"    {axis.tag} {axis.minimum}:{axis.default}:{axis.maximum}"

    # Add display name if different from tag
    if axis.display_name and axis.display_name != axis.tag:
        line += f' "{axis.display_name}"'

    return line
```

### avar2 Name Resolution
```python
def _build_name_mappings(self, dss_doc: DSSDocument) -> dict:
    """Build tag→display_name mapping for avar2"""
    name_map = {}
    for axis in dss_doc.axes + dss_doc.hidden_axes:
        if axis.display_name:
            name_map[axis.tag] = axis.display_name
        else:
            name_map[axis.tag] = axis.tag
    return name_map
```

---

## Example Transformations

**Amstelvar axis in DS:**
```xml
<axis tag="opsz" name="Optical size" minimum="8" default="14" maximum="144"/>
```

**Converted to DSS:**
```dssketch
opsz 8:14:144 "Optical size"
```

**Converted back to DS:**
```xml
<axis tag="opsz" name="Optical size" minimum="8" default="14" maximum="144"/>
```

---

## Edge Cases

1. **No display name** → use tag: `XOUC 4:90:310` → name="XOUC"
2. **Display name = tag** → don't output: `wght 100:900` (not `wght 100:900 "wght"`)
3. **Quotes in name** → escape or disallow: `"Name \"quoted\""`
4. **Empty name** → error or ignore: `opsz 8:14:144 ""`
5. **Unicode in name** → support: `wght 100:900 "Насыщенность"`
