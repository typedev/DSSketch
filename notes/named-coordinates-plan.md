# Named Source Coordinates Implementation Plan

## Goal
Add support for named coordinates in sources section to handle hidden axes efficiently.

## Problem
- Amstelvar has 126 sources with coordinates across 67 axes (4 visible + 63 hidden)
- Current format: positional `[val, val, val, val]` only supports visible axes
- Hidden axis coordinates are lost during conversion

## Solution
Add named coordinate syntax: `axis=value, axis=value`
- Only non-default coordinates need to be specified
- Supports both visible and hidden axes
- Backward compatible with positional format

## Target Format

```dssketch
# Existing positional format (unchanged)
sources [CONTRAST, wdth, wght, slnt]
    MegaFont_Black [HighContrast, Normal, Black, Slant]

# New named format (for avar2 fonts)
sources
    AmstelvarA2-Roman_wght400 @base
    AmstelvarA2-Roman_WDSP0 WDSP=0
    AmstelvarA2-Roman_GRAD-300 GRAD=-300
    AmstelvarA2-Roman_opsz144_XOUC84 opsz=144, XOUC=84
```

## Rules
1. `[...]` = positional coordinates (existing, unchanged)
2. `axis=value` = named coordinate (new)
3. Cannot mix `[...]` and `axis=value` in same line
4. Missing coordinates = axis default value
5. `@base` and other flags at end of line

---

## Implementation Steps

### Phase 1: Update Parser
- [ ] **1.1** Add regex pattern for named coordinates `axis=value`
- [ ] **1.2** Modify `_parse_source_line()` to detect format (positional vs named)
- [ ] **1.3** Implement `_parse_named_coordinates()` helper
- [ ] **1.4** Resolve named values using axis defaults from document
- [ ] **1.5** Write unit tests for parser

### Phase 2: Update Writer
- [ ] **2.1** Add method `_should_use_named_format()` to detect when to use named
- [ ] **2.2** Modify `_format_source()` to support named coordinates output
- [ ] **2.3** Calculate non-default coordinates (compare with axis defaults)
- [ ] **2.4** Include hidden axes in coordinate output
- [ ] **2.5** Write unit tests for writer

### Phase 3: Update Converter (DS → DSS)
- [ ] **3.1** Modify `_convert_source()` to preserve ALL coordinates (visible + hidden)
- [ ] **3.2** Store axis defaults for comparison in writer
- [ ] **3.3** Test with Amstelvar designspace

### Phase 4: Update Converter (DSS → DS)
- [ ] **4.1** Ensure named coordinates are properly converted to DesignSpace locations
- [ ] **4.2** Fill missing coordinates with axis defaults
- [ ] **4.3** Test roundtrip conversion

### Phase 5: Integration Testing
- [ ] **5.1** Test MegaFont (positional format) - unchanged behavior
- [ ] **5.2** Test Amstelvar (named format) - new behavior
- [ ] **5.3** Test RobotoDelta (named format)
- [ ] **5.4** Test roundtrip: DS → DSS → DS preserves all coordinates
- [ ] **5.5** Test backward compatibility with existing .dssketch files

### Phase 6: Documentation & Commit
- [ ] **6.1** Update CLAUDE.md with new syntax
- [ ] **6.2** Update examples if needed
- [ ] **6.3** Commit changes

---

## Checkpoints

### Checkpoint 1: Parser Works
After Phase 1 — parser correctly reads both formats

### Checkpoint 2: Writer Works
After Phase 2 — writer outputs named format when appropriate

### Checkpoint 3: DS → DSS Works
After Phase 3 — Amstelvar converts with all coordinates

### Checkpoint 4: Roundtrip Works
After Phase 4 — DSS → DS → DSS preserves everything

### Checkpoint 5: All Tests Pass
After Phase 5 — existing and new files work correctly

### Checkpoint 6: Complete
After Phase 6 — documented and committed

---

## Progress Log

| Step | Status | Notes |
|------|--------|-------|
| 1.1  | ✅ | Regex `(\w+)=([\w.-]+)` for named coords |
| 1.2  | ✅ | `_parse_source_line()` detects 3 formats |
| 1.3  | ✅ | `_parse_source_named()` implemented |
| 1.4  | ✅ | Uses axis defaults from visible+hidden axes |
| 1.5  | ✅ | Tested: named coords work correctly |
| 2.1  | ✅ | `use_named_format = bool(dss_doc.hidden_axes)` |
| 2.2  | ✅ | `_format_source_named()` implemented |
| 2.3  | ✅ | Compares with axis.default |
| 2.4  | ✅ | Includes hidden axes in output |
| 2.5  | ✅ | Roundtrip test passed |
| 3.1  | ✅ | `_convert_source()` now preserves ALL coords from source.location |
| 3.2  | ✅ | Defaults from ds_doc.axes, then override from source.location |
| 3.3  | ✅ | Amstelvar: 126 sources, each with 1 non-default coord |
| 4.1  | ✅ | Named coords properly passed to DS location |
| 4.2  | ✅ | Parser fills defaults, converter preserves |
| 4.3  | ✅ | DSS→DS test passed |
| 5.1  | ✅ | MegaFont: positional format preserved |
| 5.2  | ✅ | Amstelvar: full roundtrip DS→DSS→DS works |
| 5.3  | ✅ | RobotoDelta: 75 sources with named coords |
| 5.4  | ✅ | Roundtrip preserves all coordinates |
| 5.5  | ✅ | Backward compat: positional format works |
| 6.1  | ✅ | Plan files created |
| 6.2  | ✅ | Examples work correctly |
| 6.3  | ⏳ | Ready to commit |

---

## Technical Notes

### Named Coordinate Regex
```python
# Pattern: axis=value or axis=label
NAMED_COORD_PATTERN = r'(\w+)=([\w.-]+)'
# Examples: WDSP=0, opsz=144, wght=Bold, GRAD=-300
```

### Detection Logic
```python
def _detect_source_format(line):
    if '[' in line and ']' in line:
        return 'positional'
    elif '=' in line:
        return 'named'
    else:
        return 'default_only'  # Just source name + flags
```

### Default Value Resolution
```python
def _get_axis_default(axis_name, document):
    # Search in visible axes
    for axis in document.axes:
        if axis.name == axis_name or axis.tag == axis_name:
            return axis.default
    # Search in hidden axes
    for axis in document.hidden_axes:
        if axis.name == axis_name or axis.tag == axis_name:
            return axis.default
    return None
```

### Example Transformations

**Amstelvar source in DS:**
```xml
<source filename="AmstelvarA2-Roman_WDSP0.ufo">
  <location>
    <dimension name="WDSP" xvalue="0"/>
    <dimension name="GRAD" xvalue="0"/>
    <!-- 61 more dimensions with default values -->
  </location>
</source>
```

**Converted to DSS (named format):**
```dssketch
AmstelvarA2-Roman_WDSP0 WDSP=0
```
Only WDSP=0 because it differs from default (320). GRAD=0 equals default, so omitted.

---

## Edge Cases

1. **Source with all defaults** → just name + flags: `SourceName @base`
2. **Source with only visible non-defaults** → named or positional both work
3. **Source with only hidden non-defaults** → named format required
4. **Mixed visible + hidden non-defaults** → named format
5. **Negative values** → `GRAD=-300` (supported)
6. **Float values** → `opsz=14.5` (supported)
