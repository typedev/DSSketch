# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DesignSpace Sketch (DSSketch) is a Python tool that provides bidirectional conversion between compact `.dssketch` format and verbose `.designspace` XML files. It achieves 84-97% size reduction while maintaining full functionality for variable font design.

**Key Philosophy:**
The core idea of DSSketch is to provide a **human-friendly, simple, and intuitive** way to describe variable font design spaces, replacing the overly complex and verbose XML format with a clean, readable text format that font designers can easily understand and edit by hand. This makes variable font development more accessible and less error-prone.

## Key Commands

### Running the converter
```bash
# After pip install -e . (recommended - installs CLI commands):
dssketch font.designspace       # Main converter
dssketch font.dssketch -o output.designspace
dss font.designspace            # Alternative short command

# Without installation (using Python module directly):
python -m dssketch.cli font.designspace
python -m dssketch.cli font.dssketch -o output.designspace

# Import as package:
from dssketch import DSSParser, DSSWriter
from dssketch.converters import DesignSpaceToDSS, DSSToDesignSpace

# High-level API functions (recommended):
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

# Convert DesignSpace object to DSSketch file
ds = DesignSpaceDocument()
ds.read("font.designspace")
dssketch.convert_to_dss(ds, "font.dssketch")

# Convert DSSketch file to DesignSpace object
ds = dssketch.convert_to_designspace("font.dssketch")

# Convert DSSketch string to DesignSpace object
dss_content = "family MyFont\naxes\n..."
ds = dssketch.convert_dss_string_to_designspace(dss_content, base_path="./")

# Convert DesignSpace object to DSSketch string
dss_string = dssketch.convert_designspace_to_dss_string(ds)
```

### Development setup
```bash
# Using uv (recommended):
uv pip install -e .                  # Install in editable mode
uv pip install -e ".[dev]"           # Install with dev dependencies
uv run pytest tests/                 # Run tests

# Using pip:
pip install -e .                     # Install in editable mode
pip install -r requirements.txt      # Or install dependencies manually

# Dependencies: fonttools, fontParts, defcon, pyyaml
```

### Testing examples
```bash
# Test with provided examples (after pip install -e .):
dssketch examples/MegaFont-3x5x7x3-Variable.designspace
dssketch examples/SuperFont-6x2.designspace
dssketch examples/MegaFont-3x5x7x3-Variable.dssketch

# Or without installation:
python -m dssketch.cli examples/MegaFont-3x5x7x3-Variable.designspace
python -m dssketch.cli examples/SuperFont-6x2.dssketch
```

### Data file management
```bash
# After pip install -e . (recommended):
dssketch-data info                              # Show data files locations
dssketch-data copy unified-mappings.yaml        # Copy default file for editing
dssketch-data edit                              # Open user data directory
dssketch-data reset --file unified-mappings.yaml # Reset specific file
dssketch-data reset --all                       # Reset all files

# Without installation (using Python module directly):
python -m dssketch.data_cli info
python -m dssketch.data_cli copy unified-mappings.yaml
python -m dssketch.data_cli edit
```

## API Integration

DSSketch provides a high-level Python API for easy integration into other projects and applications. The API functions work with DesignSpace objects and DSSketch file paths, making it simple to incorporate DSSketch conversion into existing font development workflows.

### Core API Functions

```python
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

# Convert DesignSpace object to DSSketch file
dssketch.convert_to_dss(designspace, dss_path, optimize=True, vars_threshold=3, avar2_format="matrix") -> str

# Convert DSSketch file to DesignSpace object
dssketch.convert_to_designspace(dss_path: str) -> DesignSpaceDocument

# Convert DesignSpace to DSSketch string
dssketch.convert_designspace_to_dss_string(designspace, optimize=True, vars_threshold=3, avar2_format="matrix") -> str

# Convert DSSketch string to DesignSpace object
dssketch.convert_dss_string_to_designspace(dss_content: str, base_path: str = None) -> DesignSpaceDocument

# Convert DesignSpace object to DSSketch string
dssketch.convert_designspace_to_dss_string(designspace: DesignSpaceDocument, optimize: bool = True) -> str
```

### Integration Examples

**Basic conversion workflow:**
```python
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

# Load existing DesignSpace
ds = DesignSpaceDocument()
ds.read("MyFont.designspace")

# Convert to compact DSSketch format
dssketch.convert_to_dss(ds, "MyFont.dssketch")

# Later, load back as DesignSpace object
ds_loaded = dssketch.convert_to_designspace("MyFont.dssketch")

# Use the loaded DesignSpace
print(f"Family: {ds_loaded.default.familyName}")
print(f"Axes: {[axis.name for axis in ds_loaded.axes]}")
```

**Working with DSSketch content strings:**
```python
import dssketch

# Create DSSketch content programmatically
dss_content = """
family MyVariableFont
axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900
sources
    MyFont-Thin.ufo [100]
    MyFont-Regular.ufo [400] @base
    MyFont-Black.ufo [900]
"""

# Convert to DesignSpace object
ds = dssketch.convert_dss_string_to_designspace(dss_content, base_path="./sources")

# Save as traditional DesignSpace file
ds.write("MyVariableFont.designspace")
```

**Integrating with build tools:**
```python
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

def optimize_designspace_workflow(source_path: str, output_dir: str):
    """Optimize a DesignSpace by converting through DSSketch format"""

    # Load original DesignSpace
    ds = DesignSpaceDocument()
    ds.read(source_path)

    # Convert to optimized DSSketch string (84-97% smaller)
    dss_string = dssketch.convert_designspace_to_dss_string(ds, optimize=True)

    # Save the compact version
    with open(f"{output_dir}/optimized.dssketch", "w") as f:
        f.write(dss_string)

    # Convert back to DesignSpace with all optimizations applied
    ds_optimized = dssketch.convert_dss_string_to_designspace(dss_string)
    ds_optimized.write(f"{output_dir}/optimized.designspace")

    return len(dss_string)  # Return compressed size for metrics
```

### Error Handling

The API functions include robust error handling and validation:

```python
import dssketch
from pathlib import Path
from src.dssketch.parsers.dss_parser import DSSParser

# Basic error handling
try:
    # Convert DSSketch file
    ds = dssketch.convert_to_designspace("font.dssketch")
    print(f"Conversion successful: {len(ds.axes)} axes, {len(ds.sources)} sources")

except FileNotFoundError:
    print("DSSketch file not found")

except ValueError as e:
    print(f"Invalid DSSketch format: {e}")

except Exception as e:
    print(f"Conversion error: {e}")

# Advanced error handling with validation details
parser = DSSParser(strict_mode=False)  # Non-strict mode to collect all issues
try:
    with open("font.dssketch") as f:
        content = f.read()

    result = parser.parse(content)

    # Check for validation issues
    if parser.errors:
        print(f"Found {len(parser.errors)} errors:")
        for error in parser.errors:
            print(f"  ERROR: {error}")

    if parser.warnings:
        print(f"Found {len(parser.warnings)} warnings:")
        for warning in parser.warnings:
            print(f"  WARNING: {warning}")

    if not parser.errors:
        print("Parsing successful!")

except Exception as e:
    print(f"Parser exception: {e}")
```

### Performance Benefits

When integrating DSSketch API into your workflow:

- **Storage**: 84-97% size reduction compared to DesignSpace XML
- **Parsing**: Faster parsing due to simpler format structure
- **Human-readable**: Easy to generate DSSketch content programmatically
- **Version control**: Much better diffs due to compact, structured format
- **Validation**: Built-in UFO validation and glyph extraction

## Architecture & Core Concepts

### Main Components

**Module Structure:**
- `src/dssketch/` - Package root
  - `cli.py` - Main command-line interface implementation
  - `data_cli.py` - Data file management CLI
  - `converters/` - Conversion modules
  - `parsers/` - Parsing modules
  - `writers/` - Writing modules
  - `utils/` - Utility functions
  - `core/` - Core models and validation

**Core Classes (refactored structure):**
- `src/dssketch/parsers/dss_parser.py`:
  - `DSSParser` - Parses .dssketch format into structured data with robust validation
- `src/dssketch/writers/dss_writer.py`:
  - `DSSWriter` - Generates .dssketch from structured data
- `src/dssketch/converters/designspace_to_dss.py`:
  - `DesignSpaceToDSS` - Converts .designspace → DSSketch
- `src/dssketch/converters/dss_to_designspace.py`:
  - `DSSToDesignSpace` - Converts DSSketch → .designspace
- `src/dssketch/core/validation.py`:
  - `UFOValidator` - Validates UFO source files
  - `UFOGlyphExtractor` - Extracts glyph lists from UFO files
- `src/dssketch/utils/dss_validator.py`:
  - `DSSValidator` - Comprehensive validation with intelligent typo detection
  - Uses **Levenshtein distance algorithm** for typo suggestions (like git, npm, bash)
  - Detects duplicate mapping labels (CRITICAL), axis tag typos (ERROR), mapping label typos (WARNING)
  - Smart cross-axis validation logic
- `src/dssketch/core/mappings.py`:
  - `Standards` - Built-in weight/width mappings
- `src/dssketch/utils/patterns.py`:
  - `PatternMatcher` - Wildcard pattern matching for glyphs
- `src/dssketch/utils/discrete.py`:
  - `DiscreteAxisHandler` - Manages discrete axis detection and labels
- `src/dssketch/core/instances.py`:
  - `createInstances` - Automatic instance generation from axis combinations
  - `sortAxisOrder` - Standard axis ordering for instances
  - `getElidabledNames` - Generates elidable style name variations
- `src/dssketch/config.py`:
  - `DataManager` - Handles user data file overrides and customization

### Critical Design Concepts

**User Space vs Design Space:**
- User Space: Values users see (font-weight: 400)
- Design Space: Actual coordinates in font files (can be any value)
- Mapping: `Regular > 362` means user requests 400, source is at 362

**Axis Types:**
- Standard axes use lowercase tags: `wght`, `wdth`, `ital`, `slnt`, `opsz`
- **Human-readable names supported**: `weight`, `width`, `italic`, `slant`, `optical` (automatically converted to tags)
- Custom axes use uppercase: `CONTRAST CNTR`
- Discrete axes: `ital discrete` or `ital 0:0:1` for non-interpolating axes (like italic on/off)

**Discrete Axes:**
- Used for axes that don't interpolate (e.g., Roman vs Italic)
- Format: `ital discrete` (preferred) or `ital 0:0:1` (verbose)
- Simplified labels: just `Upright` and `Italic` (no redundant > values)
- Supports multiple label names: Upright/Roman/Normal for 0, Italic for 1
- Labels stored in `data/discrete-axis-labels.yaml` for easy customization
- Both old and new formats supported for backward compatibility
- Generates DesignSpace `values="0 1"` attribute instead of `minimum/maximum`
- Essential for proper variable font generation with non-compatible sources

### DSSketch Format Structure

```dssketch
family FontName
suffix VF  # optional
path sources  # common directory for sources

axes  # Order of axes controls instance generation sequence
    wght 100:400:900  # min:default:max (numeric format)
        # Three axis mapping formats supported:

        # Format 1: label > design_value (standard/custom labels)
        Thin > 100     # Standard label, user_value inferred from mappings (100)
        Regular > 400  # Standard label, user_value = 400
        Black > 900    # Standard label, user_value = 900

        # Format 2: user_value label > design_value (explicit user-space)
        200 Light > 230        # Explicit: user=200 (override standard 300), design=230
        980 DeepBlack > 1000   # Custom label: user=980, design=1000

        # Format 3: custom_label > design_value (user=design)
        MyCustom > 500         # Unknown label: user_value = design_value = 500

    # Label-based axis ranges (for weight and width only)
    wght Thin:Regular:Black  # Uses standard user-space values
        Thin > 100
        Regular > 400
        Black > 900

    ital discrete  # discrete axis (equivalent to ital 0:0:1)
        Upright    # simplified format (no > 0.0 needed)
        Italic     # simplified format (no > 1.0 needed)

sources [wght, ital]  # explicit axis order for coordinates
    # Traditional numeric coordinates:
    SourceName [362, 0] @base  # [coordinates] @flags

    # Label-based coordinates (more readable):
    SourceName [Regular, Upright] @base  # Uses axis mapping labels
    SourceName [Black, Italic]  # Mixed numeric and labels supported

    # Or individual paths per source:
    # upright/Thin [Thin, Upright]  # Label-based
    # italic/Black [900, 1]  # Numeric

rules
    # Label-based conditions (more readable!)
    dollar > dollar.heavy (weight >= Bold) "heavy dollar"
    ampersand > ampersand.fancy (weight >= Bold && width <= Wide) "compound condition"
    g > g.alt (Regular <= weight <= Bold) "range condition"

    # Numeric conditions (still fully supported)
    dollar > dollar.rvrn (weight >= 480) "dollar alternates"  # 480 = design space coordinate
    cent* > .rvrn (weight >= 480) "cent patterns"  # wildcard patterns
    A* > .alt (weight <= 500)  # all glyphs starting with A
    * > .rvrn (weight >= 600)  # all glyphs that have .rvrn variants

    # Mixed label and numeric conditions
    b > b.alt (450 <= weight <= Bold) "mixed condition"

    # Negative design space coordinates supported:
    thin* > .ultra (weight >= -100)  # negative design space value
    slanted* > .back (slnt <= -15)  # negative slant coordinate

instances auto  # instances follow axes section order
    skip  # optional: skip specific instance combinations
        # Skip rules must use FINAL instance names (after elidable cleanup)
        # Must follow axis order from "axes" section
        # Comments supported for documentation

        Bold Italic  # skip this specific combination
        Thin Italic  # skip another combination

instances off  # completely disable instance generation (useful for avar2 fonts)

# avar2 support (OpenType 1.9 - inter-axis dependencies)
axes hidden  # parametric axes not exposed to users
    XOUC 0:100:200
    XOLC 0:100:200
    YTUC 400:500:600

avar2 vars  # reusable variable definitions
    $XOUC = 91
    $YTUC = 725

avar2  # linear format
    [wght=100] > wght=300
    [wght=400] > wght=400, XOUC=$XOUC
    [opsz=144] > XOUC=84, XOLC=78, YTUC=$  # $ = use axis default

avar2 matrix  # tabular format (default for output)
    outputs              XOUC  XOLC  YTUC
    [opsz=144]          84    78    $
    [opsz=144, wdth=50] 78    71    500
    [wght=100]          40    42    -     # - = no value for this axis
```

### Label-Based Syntax

DSSketch now supports a more human-friendly label-based syntax for both axis ranges and source coordinates, making files easier to read and edit by hand.

**Label-Based Source Coordinates:**

Instead of remembering design-space numbers, you can use axis mapping labels:

```dssketch
# Traditional numeric format:
sources [wght, ital]
    Font-Regular [362, 0] @base
    Font-Black [1000, 1]
    Font-Hairline [0, 0]

# Label-based format (more readable):
sources [wght, ital]
    Font-Regular [Regular, Upright] @base
    Font-Black [Black, Italic]
    Font-Hairline [Hairline, Upright]

# Mixed format also supported:
sources [wght, ital]
    Font-Regular [400, Upright] @base  # numeric + label
    Font-Black [Black, 1]  # label + numeric
```

**How it works:**
- Labels are resolved from axis mappings (e.g., `Regular` → `362.0` from `Regular > 362`)
- Supports all axes - standard (wght, wdth, ital) and custom axes
- Backward compatible - numeric format still fully supported
- Writer automatically uses labels when `use_label_coordinates=True` (default)

**Label-Based Axis Ranges:**

For standard `weight` and `width` axes, you can use label names instead of numeric user-space values:

```dssketch
# Traditional numeric format:
axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900

# Label-based format:
axes
    wght Thin:Regular:Black  # min:default:max using standard labels
        Thin > 100
        Regular > 400
        Black > 900

# Width axis example:
axes
    wdth Condensed:Normal:Extended
        Condensed > 75
        Normal > 100
        Extended > 125
```

**How it works:**
- Uses standard user-space mappings from `data/unified-mappings.yaml`
- Only works for `weight` and `width` axes (most common use case)
- Example: `Thin` → `100`, `Regular` → `400`, `Black` → `900` (standard weight values)
- Writer automatically uses labels when ranges match standard values and `use_label_ranges=True` (default)

**Benefits:**
- **More readable**: `[Regular, Upright]` is clearer than `[362, 0]`
- **Less error-prone**: No need to remember design-space coordinates
- **Better diffs**: Git diffs show meaningful label changes instead of number changes
- **Self-documenting**: Labels make the font structure immediately clear

**Examples:**

```dssketch
family MyVariableFont

axes
    wght Light:Regular:Bold  # Label-based range
        Light > 300
        Regular > 400
        Bold > 700
    ital discrete
        Upright
        Italic

sources [wght, ital]
    Font-Light [Light, Upright]  # Label-based coordinates
    Font-Regular [Regular, Upright] @base
    Font-Bold [Bold, Upright]
    Font-LightItalic [Light, Italic]
    Font-Italic [Regular, Italic]
    Font-BoldItalic [Bold, Italic]

instances auto
```

This converts to the same DesignSpace as numeric format, but is much easier to read and maintain!

**Human-Readable Axis Names:**

For standard axes, you can use human-readable names instead of short tags:

```dssketch
# Short tags (traditional):
axes
    wght 100:400:900
    wdth 75:100:125
    ital discrete

# Human-readable names:
axes
    weight 100:400:900  # Automatically converted to wght
    width 75:100:125    # Automatically converted to wdth
    italic discrete     # Automatically converted to ital

# Can be combined with label-based ranges:
axes
    weight Thin:Regular:Black  # Both human name AND labels!
    width Condensed:Normal:Extended
```

**Supported human-readable names:**
- `weight` → `wght`
- `width` → `wdth`
- `italic` → `ital`
- `slant` → `slnt`
- `optical` → `opsz`

This makes DSSketch files even more accessible to font designers who are not familiar with OpenType axis tags!

**Label-Based Rule Conditions:**

Rules can use axis mapping labels in conditions instead of numeric design-space coordinates:

```dssketch
# Traditional numeric format:
rules
    dollar > dollar.heavy (weight >= 700) "heavy dollar"
    ampersand > ampersand.fancy (weight >= 700 && width >= 110) "compound"
    g > g.alt (450 <= weight <= 650) "range condition"

# Label-based format (more readable):
rules
    dollar > dollar.heavy (weight >= Bold) "heavy dollar"
    ampersand > ampersand.fancy (weight >= Bold && width <= Wide) "compound"
    g > g.alt (Regular <= weight <= Bold) "range condition"

# Mixed format also supported:
rules
    b > b.alt (450 <= weight <= Bold) "mixed condition"
```

**How it works:**
- Labels are resolved from axis mappings to design-space values
- Supports all axes - standard (wght, wdth, ital) and custom axes
- Works with all condition operators: `>=`, `<=`, `==`, range conditions
- Backward compatible - numeric format still fully supported
- Writer automatically uses labels when `use_label_coordinates=True` (default)

**Benefits:**
- **More readable**: `weight >= Bold` is clearer than `weight >= 700`
- **Self-documenting**: Labels show the semantic meaning of conditions
- **Less error-prone**: No need to remember design-space coordinate values
- **Flexible**: Can combine numeric and label values in same condition

### Key Features

**Substitution Rules (Critical for Variable Fonts):**
Rules define glyph substitutions based on axis conditions. The syntax is:
`pattern > target (condition) "optional name"`

**Pattern Types:**
- **Exact glyph**: `dollar > dollar.rvrn` - single glyph substitution
- **Prefix wildcard**: `A* > .alt` - all glyphs starting with 'A' (A, AE, Aacute, etc.)
- **Multiple glyphs**: `dollar cent > .heavy` - specific list of glyphs
- **Universal wildcard**: `* > .rvrn` - ALL glyphs in the font

**Target Types:**
- **Suffix append**: `.rvrn` - adds suffix to source glyph (dollar → dollar.rvrn)
- **Full replacement**: `dollar.heavy` - replaces with specific glyph

**Smart Wildcard Expansion:**
- When converting DSSketch → DesignSpace, wildcards are expanded to actual glyphs
- `A*` finds all glyphs starting with 'A' in the UFO files
- `*` matches all glyphs but only creates substitutions where target exists
- Example: `* > .rvrn` only creates rules for glyphs that have .rvrn variants

**Target Validation:**
- System checks if target glyphs exist in UFO files
- Skips invalid substitutions with warnings
- Prevents broken DesignSpace rules

**Rule Conditions (Design Space Coordinates):**
- **IMPORTANT**: Rule conditions use **design space coordinates** (numeric or labels)
- **Label-based conditions** (recommended for readability):
  - Simple: `(weight >= Bold)` - uses Bold's design value from axis mappings
  - Compound: `(weight >= Bold && width <= Wide)` - combines multiple label conditions
  - Range: `(Regular <= weight <= Bold)` - range between two labels
  - Exact: `(weight == Regular)` - exact match with label value
- **Numeric conditions** (still fully supported):
  - Simple: `(weight >= 480)` - 480 is design space value, not user space
  - Compound: `(weight >= 600 && width >= 110)` - both values are design space
  - Range: `(80 <= width <= 120)` - design space range
- **Mixed conditions**: `(450 <= weight <= Bold)` - combine numbers and labels
- **Negative values supported**: `(weight >= -100)`, `(slnt <= -15)`
- **Bounds validation**: Conditions must be within axis design space min/max limits

**Optimization:**
- Auto-compresses multiple similar rules into wildcard patterns
- Detects standard weight/width values
- Removes redundant mappings

**Path Management:**
- Auto-detects common source directories (e.g., "sources/")
- Supports mixed paths for sources in different directories
- `path` parameter in DSSketch format for common directory

**UFO Validation:**
- Automatically extracts glyph names from UFO files for wildcard expansion
- Validates target glyphs exist before creating substitution rules
- Shows warnings for missing target glyphs but continues conversion
- Uses UFOGlyphExtractor to safely read glyph lists from sources

**Parser Validation & Robustness:**
- **Critical Structure Validation**: Ensures required sections (axes, sources, base source) are present - **ALWAYS FAILS** if missing
- **Typo Detection**: Catches common keyword misspellings (`familly` → `"Did you mean 'family'?"`)
- **Non-ASCII Character Detection**: Catches Unicode typos (`axшes` → `"contains non-ASCII characters"`)
- **Empty Value Validation**: Detects missing required values (`family ` → `"Family name cannot be empty"`)
- **Coordinate Validation**: Validates coordinate format and numeric values (`[abc, def]` → `"Invalid coordinate value"`)
- **Bracket Type Detection**: Warns about wrong bracket types (`(100, 0)` → `"Use [] for coordinates, not ()"`)
- **Axis Range Validation**: Checks axis range logic (`900:100:400` → `"Range values must be ordered"`)
- **Label-Based Range Validation**: Validates that label names in axis ranges exist in standard mappings (`wght s:r:Bold` → `"Label 's' not found in standard weight mappings"`)
- **Rule Syntax Validation**: Validates substitution rule completeness and syntax
- **Rule Axis Validation**: Ensures rules only reference existing axes (`(italic == 1)` when no italic axis → `"Rule references axis 'italic' which is not defined"`)
- **Mapping Range Validation**: Validates all axis mappings are within axis min/max range (`Bold > 1000` with axis `300:400:500` → `"mapping 'Bold' has user_value 700.0 outside the axis range [300.0, 500.0]"`)
- **Multiple Base Source Detection**: Prevents multiple @base sources which breaks DesignSpace
- **Two Processing Modes**: Strict mode (fails on errors) vs. non-strict (collects warnings, but **critical errors always fail**)
- **Whitespace Normalization**: Handles multiple spaces, tabs, and mixed whitespace gracefully
- **Unicode Support**: Full support for international characters in names and paths (but detects typos with wrong scripts)

**Explicit Axis Order**
- Sources section now supports explicit axis order: `sources [wght, ital]`
- Decouples coordinate interpretation from axes section order
- Supports both short tags (`wght`, `ital`) and long names (`weight`, `italic`)
- Allows users to reorder axes in axes section without breaking source coordinates
- Backward compatible: `sources` without brackets continues to work with axes order
- Example: axes can be `ital`, `wght` but coordinates follow `sources [wght, ital]` order

**Automatic Instance Generation (`instances auto`):**
- Uses sophisticated `instances.py` module for generating all meaningful instance combinations
- **Combinatorial algorithm**: Uses `itertools.product()` to create cartesian product of all axis label combinations
- **Example calculation**: 3 weights × 2 widths × 2 italics = 12 total instances
- Creates instances from all axis mapping combinations automatically
- Handles elidable style names (removes redundant parts like "Regular" from "Regular Italic" → "Italic")
- **Respects axes order from DSS document**: instances follow the sequence defined in axes section
- **Order determines naming**: First axis appears first in names (e.g., `wdth, wght` → "Condensed Light" vs `wght, wdth` → "Light Condensed")
- **Instance Skip Support**: Optionally exclude specific combinations via `skip` subsection
- Generates proper PostScript names and file paths
- Integration: `dss_to_designspace.py:67` calls `createInstances()` when `instances_auto=True`
- **Custom axis ordering**: Change axes order in DSS to control instance name generation

**Fallback for Axes Without Labels:**
- When axes have no mappings (only `min:def:max`), instances are generated from range values
- Uses axis `minimum`, `default`, and `maximum` as instance points
- Instance names use `tag+value` format (e.g., `wght400 wdth100`)
- Works for both simple fonts and avar2 fonts (avar2 adds input points from mappings)
- **Example**: `wght 100:400:900` without labels → instances at wght100, wght400, wght900
- Useful for quick prototyping without defining full axis mappings

**Instance Skip Functionality (`instances auto skip`):**
- **Purpose**: Exclude specific instance combinations from automatic generation
- **Syntax**: Indented list under `skip` keyword within `instances auto` section
- **Critical**: Skip rules must use FINAL instance names (after elidable cleanup)
- **Axis order**: Skip combinations must follow the axis order defined in `axes` section
- **Comment support**: Lines starting with `#` are ignored, useful for documentation
- **Logging**: All skip operations logged at INFO level for visibility
- **Example**: `instances auto skip` → `Bold Italic` → `Thin Italic`
- **Use cases**: Skip impractical combinations (e.g., Thin Italic too fragile, Extended Black Slant distorted)
- **Implementation**: `instances.py:230-233` checks skip rules after elidable cleanup
- **Testing**: See `examples/MegaFont-WithSkip.dssketch` (315 → 301 instances)

**Algorithm Steps (core/instances.py):**
1. `sortAxisOrder()` - Extract axes order from DSS document or use DEFAULT_AXIS_ORDER fallback
2. `getInstancesMapping()` - Extract axis label mappings for each axis
3. `itertools.product()` - Generate all combinations of labels (cartesian product)
4. `getElidabledNames()` - Determine which style names are elidable
5. For each combination:
   a. Name cleanup - Remove elidable labels from instance names
   b. Special case handling - "Regular Italic" → "Italic"
   c. **Skip check** - If final name in skip list, skip this instance (logged at INFO level)
   d. `createInstance()` - Create InstanceDescriptor with location, familyName, styleName, PostScript name

**Example:**
```dssketch
axes
    wght 100:400:900
        Thin > 100          # Label 1
        Regular > 400 @elidable
        Black > 900         # Label 2
    ital discrete
        Upright @elidable   # Label A
        Italic              # Label B

# Combinations: [Thin, Regular, Black] × [Upright, Italic]
# Raw: 3 × 2 = 6 instances
# After elidable cleanup:
# - "Upright Thin" → "Thin"
# - "Upright Regular" → "Regular"
# - "Upright Black" → "Black"
# - "Italic Thin" → "Italic Thin"
# - "Italic Regular" → "Italic"
# - "Italic Black" → "Italic Black"
```

**Skip Validation (Two Levels):**

DSSketch validates skip rules at two levels to ensure correctness:

1. **ERROR Level** - Invalid label detection (stops conversion):
   - Validates that all labels in skip rules exist in axis definitions
   - Each word in skip combination must be a valid axis label (no spaces allowed in labels)
   - Use camelCase for compound names: "ExtraLight", "SemiBold" (not "Extra Light", "Semi Bold")
   - Provides clear error message with available labels
   - Example: `Heavy Italic` where "Heavy" not defined → ERROR with full label list

2. **WARNING Level** - Unused skip rule detection (logs warning):
   - Tracks which skip rules are actually used during generation
   - After completion, reports skip rules that never matched any instance
   - Helps identify typos or rules affected by elidable cleanup
   - Example: `Bold Upright` where Upright is @elidable → WARNING "never used"

**Implementation Details:**
- Validation function: `_validate_skip_labels()` in `instances.py:151-187`
- Simple split-based validation: each space-separated word must be valid label
- Unused tracking: Set-based tracking of `used_skip_rules` (lines 259, 280, 306-315)
- Error messages include full list of available labels for easy correction

**Test Coverage:**
- 6 comprehensive tests in `tests/test_skip_validation.py`
- Tests cover: invalid labels, typos, camelCase labels, unused rules, valid rules
- All tests pass, including production MegaFont example (15 skip rules)

## Important Implementation Details

### Implementation Notes for Rules

**Code Location:**
- Rule parsing: `src/dssketch/parsers/dss_parser.py:402` (_parse_rule_line)
- Wildcard expansion: `src/dssketch/converters/dss_to_designspace.py:247` (_expand_wildcard_pattern)
- Pattern matching: `src/dssketch/utils/patterns.py` (PatternMatcher class)

**Recent Fix (important!):**
- Fixed wildcard detection for single patterns like `A*` without spaces
- Changed condition from `if ' ' in from_part and ('*' in from_part...)`
- To: `if '*' in from_part or (' ' in from_part...)`
- This ensures patterns like `A*` are properly recognized as wildcards

**Critical Fix for Rule Conditions (Design Space Coordinates):**
- **Issue**: Rule condition bounds used user space axis bounds instead of design space bounds
- **Problem**: `weight >= 480` with axis range 50:900 (user) created condition `minimum="480" maximum="900"` (user space max)
- **Fix**: Added `_get_design_space_bounds()` method in `dss_parser.py:422-430`
- **Solution**: Extract min/max from all `mapping.design_value` instead of `axis.minimum/maximum`
- **Result**: Now correctly uses design space bounds: `minimum="480" maximum="1000"` (design space max)
- **Code Location**: `src/dssketch/parsers/dss_parser.py:391-399` (condition parsing with design space bounds)
- **Negative Values**: Fully supported in both rule conditions and axis bounds validation

### Implementation Notes for Explicit Axis Order

**Code Location:**
- Writer axis order output: `src/dssketch/writers/dss_writer.py:66` (_get_axis_tag method)
- Parser axis order parsing: `src/dssketch/parsers/dss_parser.py:115` (sources section parsing)
- Coordinate parsing with axis order: `src/dssketch/parsers/dss_parser.py:330` (_parse_source_line)

**Key Implementation Details:**
- `DSSWriter._get_axis_tag()` converts axis names to standard tags for output
- `DSSParser.source_axis_order` stores explicit axis order when `sources [tags]` format is used
- `DSSParser._tag_to_axis_name()` converts tags back to full axis names
- Source coordinate parsing uses explicit order when available, falls back to axes order
- Supports mapping between short tags (`wght`) and long names (`weight`)
- Full backward compatibility maintained for legacy `sources` format

### Implementation Notes for Automatic Instance Generation

**Code Location:**
- Core instance logic: `src/dssketch/core/instances.py` (full module)
- Integration point: `src/dssketch/converters/dss_to_designspace.py:67` (createInstances call)
- DSS parsing: `src/dssketch/parsers/dss_parser.py:486` (_generate_auto_instances fallback)

**Key Functions:**
- `createInstances(dssource, defaultFolder, skipFilter, filter)` - Main function for generating all combinations
- `sortAxisOrder(ds)` - Orders axes according to `DEFAULT_AXIS_ORDER` standard
- `getElidabledNames(ds, axisOrder, ignoreAxis)` - Finds elidable labels for style name cleanup
- `getInstancesMapping(ds, axisName)` - Extracts axis value mappings from DesignSpace
- `createInstance(location, familyName, styleName, defaultFolder)` - Creates single instance descriptor

**Algorithm:**
1. Copy DesignSpace without instances
2. **Sort axes using DSS document order** or fallback to DEFAULT_AXIS_ORDER
3. Extract all axis label combinations using `itertools.product()`
4. Apply skip filters for unwanted combinations
5. Generate elidable names to clean up style names (e.g., "Regular Italic" → "Italic")
6. Create instance descriptors with proper locations and names
7. Return enhanced DesignSpace with all generated instances

**Axis Order Priority:**
1. **DSS axes section order** - Primary method for controlling instance generation
2. `DEFAULT_AXIS_ORDER` - Fallback when no DSS document provided

**Constants:**
- `DEFAULT_AXIS_ORDER` - Fallback axis ordering (Optical → Contrast → Width → Weight → Italic → Slant)
- `ELIDABLE_MAJOR_AXIS = "weight"` - Primary axis that should not be elidable
- `DEFAULT_INSTANCE_FOLDER = "instances"` - Default output folder for generated instances

**Examples:**
```dssketch
# Custom axis order: italic first, then weight, then width
axes
    ital discrete
        Upright @elidable
        Italic
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900
    wdth 60:100:200
        Condensed > 60
        Normal > 100

# Result: instances like "Italic Thin Condensed"
```

### Implementation Notes for Label-Based Syntax

**Code Location:**
- Label resolution in sources: `src/dssketch/parsers/dss_parser.py:_resolve_coordinate_value()` (method added)
- Label resolution in axis ranges: `src/dssketch/parsers/dss_parser.py:_resolve_axis_range_value()` (method added)
- Label-based coordinate parsing: `src/dssketch/parsers/dss_parser.py:_parse_source_line()` (modified)
- Label-based range parsing: `src/dssketch/parsers/dss_parser.py:_parse_axis_line()` (modified in 3 places)
- Writer label coordinates: `src/dssketch/writers/dss_writer.py:_get_label_for_coordinate()` (method added)
- Writer label ranges: `src/dssketch/writers/dss_writer.py:_get_label_for_user_value()` (method added)

**Key Implementation Details:**

**Source Coordinate Resolution (`_resolve_coordinate_value`):**
```python
def _resolve_coordinate_value(self, value_str: str, axis_index: int) -> float:
    """Resolve coordinate value - can be numeric or label name"""
    # Try parsing as numeric first
    try:
        return float(value_str)
    except ValueError:
        pass

    # Get the corresponding axis
    if axis_index >= len(self.axes):
        raise ValueError(f"Coordinate index {axis_index} out of range")

    axis = self.axes[axis_index]

    # Find label in axis mappings
    for mapping in axis.mappings:
        if mapping.label == value_str:
            return mapping.design_value

    raise ValueError(f"Unknown label '{value_str}' for axis '{axis.name}'")
```

**Axis Range Resolution (`_resolve_axis_range_value`):**
```python
def _resolve_axis_range_value(self, value_str: str, axis_name: str) -> float:
    """Resolve axis range value - can be numeric or label name"""
    # Try parsing as numeric first
    try:
        return float(value_str)
    except ValueError:
        pass

    # Only works for weight and width axes
    axis_type = None
    if axis_name in ['wght', 'weight']:
        axis_type = 'weight'
    elif axis_name in ['wdth', 'width']:
        axis_type = 'width'
    else:
        raise ValueError(f"Label-based ranges only supported for weight/width, not '{axis_name}'")

    # Get standard user-space value
    user_value = Standards.get_user_space_value(value_str, axis_type)
    return user_value
```

**Writer Label Output:**
- `DSSWriter.__init__` accepts `use_label_coordinates=True` and `use_label_ranges=True` parameters
- When enabled, writer converts numeric values back to labels for readability
- Uses axis mappings to find matching labels for design-space coordinates
- Uses standard mappings to find matching labels for user-space values

**Backward Compatibility:**
- Numeric format continues to work in all cases
- Mixed numeric and label coordinates supported
- Label-based ranges fall back to numeric if label not found
- Parser accepts both formats transparently

**Benefits:**
- **Readability**: `[Regular, Upright]` is clearer than `[362, 0]`
- **Maintainability**: Changes to design-space coordinates don't require updating all sources
- **Self-documenting**: Labels make font structure immediately clear
- **Version control**: Git diffs show meaningful changes

**Important Refactoring (2025-01):**
- Parser now uses centralized `DiscreteAxisHandler` instead of duplicating discrete axis detection
- Removed duplicate `_load_discrete_labels()` method (12 lines eliminated)
- All discrete axis operations now go through `DiscreteAxisHandler.load_discrete_labels()` and `DiscreteAxisHandler.is_discrete()`
- This ensures consistency and supports user data file overrides via DataManager

### Implementation Notes for Axis Mapping Formats

**Code Location:**
- Axis mapping parsing: `src/dssketch/parsers/dss_parser.py:_parse_axis_mapping()` (lines 491-560)
- Format detection: Lines 503-527 (three-way format detection logic)

**Three Supported Formats:**

**1. Standard Label Format** (`Light > 300`):
- **Detection**: Line contains `>`, left side is non-numeric string
- **Logic**: Parser checks if label exists in `Standards` mappings (lines 522-524)
- **User-space value**: Retrieved from standard mappings (e.g., Light=300, Bold=700)
- **Code path**: `Standards.has_mapping()` → `Standards.get_user_value_for_name()`
- **Example**: `Light > 300` → user=300 (from Standards), label="Light", design=300

**2. Custom Label Format** (`MyCustom > 500`):
- **Detection**: Line contains `>`, left side is non-numeric string, label NOT in Standards
- **Logic**: Unknown labels use design-space value as user-space value (lines 526-527)
- **User-space value**: Equals design-space value (user=design)
- **Code path**: Falls through to `user = design` assignment
- **Example**: `MyCustom > 500` → user=500, label="MyCustom", design=500

**3. Explicit User-Space Format** (`300 Light > 295`):
- **Detection**: Line contains `>`, left side starts with numeric value (lines 512-517)
- **Logic**: `left_parts[0].replace(".", "").replace("-", "").isdigit()` check
- **Parsing**: `user = float(left_parts[0])`, `label = " ".join(left_parts[1:])`, `design = float(parts[1])`
- **User-space value**: Explicitly provided (overrides any standard mappings)
- **Code path**: Direct numeric parsing of first component
- **Examples**:
  - `300 Light > 295` → user=300, label="Light", design=295
  - `200 Light > 230` → user=200 (overrides standard 300), design=230
  - `980 DeepBlack > 1000` → user=980 (custom label), design=1000
  - `0 NonContrast > 0` → user=0, label="NonContrast", design=0
  - `150 Wide > 700` → user=150 (overrides standard 100), design=700

**Key Implementation Code (dss_parser.py:503-527):**
```python
if ">" in line:
    # Traditional format: "300 Light > 295" or "0.0 Upright > 0.0"
    parts = line.split(">")
    left = parts[0].strip()
    design = float(parts[1].strip())

    # Parse left side
    left_parts = left.split()

    if left_parts[0].replace(".", "").replace("-", "").isdigit():
        # Format: "300 Light" or "0.0 Upright" - EXPLICIT USER-SPACE
        user = float(left_parts[0])
        label = " ".join(left_parts[1:]) if len(left_parts) > 1 else ""
        if not label:
            label = Standards.get_name_for_user_value(user, self.current_axis.name)
    else:
        # Format: "Light > 295" or "XX > 60" - infer user value
        label = left
        # Check if this label exists in standard mappings
        if Standards.has_mapping(label, self.current_axis.name):
            # Use standard mapping for known labels
            user = Standards.get_user_value_for_name(label, self.current_axis.name)
        else:
            # For unknown labels, use design_value as user_value
            user = design
```

**Real-World Usage:**
- **Standard format**: Most common for standard weight/width scales
- **Custom format**: Useful for custom axes (CONTRAST, CUSTOM, etc.)
- **Explicit format**: Required for:
  - Overriding standard mappings (e.g., `200 Light > 230` instead of 300)
  - Non-standard CSS scales (e.g., 50-980 instead of 100-900)
  - Custom axes with meaningful user-space values

**Examples from `examples/MegaFont-3x5x7x3-Variable.dssketch`:**
```dssketch
axes
    CONTRAST CNTR 0:0:100
        0 NonContrast > 0       # user=0, label=NonContrast, design=0
        50 LowContrast > 100    # user=50, label=LowContrast, design=100
        100 HighContrast > 200  # user=100, label=HighContrast, design=200
    wdth 60:100:200
        Compressed > 0          # Standard: user=62.5 (from mappings), design=0
        Condensed > 380         # Standard: user=75 (from mappings), design=380
        Normal > 560            # Standard: user=100 (from mappings), design=560
        150 Wide > 700          # Explicit: user=150 (overrides standard 100), design=700
        200 Extended > 1000     # Explicit: user=200 (overrides standard 125), design=1000
    wght Thin:Regular:Black
        Thin > 0                # Standard: user=100 (from mappings), design=0
        200 Light > 230         # Explicit: user=200 (overrides standard 300), design=230
        Regular > 420           # Standard: user=400 (from mappings), design=420
        Bold > 725              # Standard: user=700 (from mappings), design=725
        Black > 1000            # Standard: user=900 (from mappings), design=1000
```

**Important Notes:**
- The explicit format `user_value label > design_value` is fully functional but was not previously documented
- All three formats are actively used in production examples (`examples/MegaFont-3x5x7x3-Variable.dssketch`)
- Format detection is automatic - no flags or configuration needed
- Supports negative values: `-20 Reverse > -20`
- No tests currently cover explicit user-space format (test gap identified)

### Implementation Notes for New Validations (2025-01)

**1. Label-Based Range Validation**

**Code Location:**
- Validation logic: `src/dssketch/parsers/dss_parser.py:_resolve_axis_range_value()` (lines 510-554)
- Key validation check: `Standards.has_mapping()` (lines 542-546)
- Test suite: `tests/test_label_range_validation.py` (8 tests)

**Key Implementation:**
```python
def _resolve_axis_range_value(self, value_str: str, axis_name: str) -> float:
    """Resolve axis range value - can be numeric or label name"""
    # Try parsing as numeric first
    try:
        return float(value_str)
    except ValueError:
        pass

    # Only works for weight and width axes
    axis_type = axis_name.lower()
    if axis_type in ["weight", "width"]:
        # Check if this label exists in standard mappings
        if not Standards.has_mapping(value_str, axis_type):
            raise ValueError(
                f"Label '{value_str}' not found in standard {axis_type} mappings. "
                f"Use numeric values or valid standard labels."
            )
        user_value = Standards.get_user_space_value(value_str, axis_type)
        return user_value
    else:
        raise ValueError(
            f"Label-based ranges only supported for 'weight' and 'width' axes."
        )
```

**Error Detection:**
- Invalid labels like `s`, `r`, `Foo` are caught immediately during parsing
- Provides helpful error message with guidance to use standard labels
- Works in both strict and non-strict modes

**2. Rule Axis Validation**

**Code Location:**
- Validation logic: `src/dssketch/converters/dss_to_designspace.py:_find_axis_name_in_designspace()` (lines 298-302)
- Changed from warning to error when axis not found
- Test suite: `tests/test_rule_axis_validation.py` (5 tests)

**Key Implementation:**
```python
def _find_axis_name_in_designspace(self, dss_axis_name: str, doc: DSSDocument) -> str:
    """Find axis name in DesignSpace, raising error if not found"""
    # ... search logic ...

    # If no match found, this is an error
    raise ValueError(
        f"Rule references axis '{dss_axis_name}' which is not defined in the document. "
        f"Available axes: {', '.join([axis.name for axis in doc.axes])}"
    )
```

**Critical Behavior:**
- Rules must only reference axes that exist in the document
- Provides clear error message listing all available axes
- Users must fix by either adding the axis or removing/modifying the rule
- This prevents invalid DesignSpace generation

**3. Mapping Range Validation**

**Code Location:**
- Validation logic: `src/dssketch/utils/dss_validator.py:_validate_content()` (lines 185-192)
- Checks during document validation phase
- Test suite: `tests/test_mapping_range_validation.py` (8 tests)

**Key Implementation:**
```python
def _validate_content(self, document: DSSDocument):
    """Validate document content (non-critical errors)"""
    for axis in document.axes:
        for mapping in axis.mappings:
            # Check that mapping user_value is within axis range
            if mapping.user_value is not None:
                if mapping.user_value < axis.minimum or mapping.user_value > axis.maximum:
                    self.errors.append(
                        f"Axis '{axis.name}': mapping '{mapping.label}' has user_value {mapping.user_value} "
                        f"which is outside the axis range [{axis.minimum}, {axis.maximum}]. "
                        f"All mappings must be within the axis min/max range."
                    )
```

**Validation Rules:**
- All axis mappings must have `user_value` within `[axis.minimum, axis.maximum]`
- Mappings at exact minimum or maximum are valid
- Applies to all axis types: weight, width, custom axes
- Clear error message showing the mapping, its value, and valid range

**Error Preservation:**
- All three validations properly preserve parsing errors through the validation phase
- `dss_validator.py:validate_document()` merges parsing_errors with validation errors
- Critical errors always cause immediate failure regardless of mode

### Implementation Notes for avar2 Support (2025-12)

**avar2 (axis variations v2)** is an OpenType 1.9 feature enabling non-linear axis mappings and inter-axis dependencies. Essential for parametric fonts like AmstelvarA2.

**Code Locations:**
- Parser: `src/dssketch/parsers/dss_parser.py` - sections `avar2`, `avar2 vars`, `avar2 matrix`
- Writer: `src/dssketch/writers/dss_writer.py` - `_format_avar2_as_matrix()`, `_format_avar2_as_linear()`
- Models: `src/dssketch/core/models.py` - `DSSAvar2Mapping`, `DSSDocument.avar2_mappings`
- Instances: `src/dssketch/core/instances.py` - `_extract_avar2_points_for_axis()`
- Converter: `src/dssketch/converters/dss_to_designspace.py` - `_user_to_design_value()` for user→design conversion

**avar2 Semantic Model (IMPORTANT):**

Labels in avar2 use **user space** for input and **design space** for output:

```
avar2 INPUT:  USER space    (Regular=400, Condensed=80)
avar2 OUTPUT: DESIGN space  (wght=385, XOUC=50)
```

**Example:**
```dssketch
axes
    wght 100:400:900
        Regular > 435      # user=400 → design=435 (DEFAULT)
        Bold > 700

avar2
    [wght=Regular, wdth=Condensed] > wght=385
    #     ↑                              ↑
    #  user=400                      design=385
```

**How it works:**
1. Parser resolves `Regular` to user_value=400 (via `_resolve_avar2_value()`)
2. Converter transforms user=400 → design=435 for DesignSpace XML (via `_user_to_design_value()`)
3. Output values are already in design space, used as-is

**This creates clean semantics:**
- Axis mapping `Regular > 435` = default design value
- avar2 overrides for specific axis combinations
- Labels ALWAYS mean user space everywhere in DSSketch

**Key Features:**

1. **Linear Format** - Traditional one-mapping-per-line:
   ```
   avar2
       [wght=Regular] > wght=300, XOUC=80    # Regular = user 400
       [opsz=Display] > XOUC=84, XOLC=78     # Display = user 144
   ```

2. **Matrix Format** (default) - Tabular for complex fonts:
   ```
   avar2 matrix
       outputs                         XOUC  XOLC  YTUC
       [wght=Regular, wdth=Condensed]  84    78    $
       [wght=Bold, wdth=Condensed]     40    42    -
   ```
   - `$` = use axis default value (e.g., `XOUC=$` means use XOUC's default from axis definition)
   - `-` = no output for this axis in this mapping

3. **Variables** (`avar2 vars`):
   ```
   avar2 vars
       $XOUC = 91
       $YTUC = 725
   ```

4. **Hidden Axes** - Parametric axes not exposed to users:
   ```
   axes hidden
       XOUC 0:100:200
       YTUC 400:500:600
   ```

**Instance Generation Fallback:**

When axes have no labels (common in avar2 fonts), instance generation uses:
1. Axis min, default, max values
2. Unique input points from avar2 mappings

```python
def _generate_fallback_mapping(axisDescriptor, dss_doc=None) -> dict:
    """Generate mapping from min:def:max + avar2 points."""
    points = {axis.minimum, axis.default, axis.maximum}
    if dss_doc:
        points |= _extract_avar2_points_for_axis(dss_doc, axis.tag)
    return {_format_axis_value_label(tag, v): v for v in sorted(points)}
```

Instance names: `wght400 opsz16` format (tag + value).

**Hidden axes excluded** from instance generation - only user-facing axes contribute.

**CLI Options:**
- `--matrix` - Use matrix format (default)
- `--linear` - Use linear format
- `--novars` - Disable automatic variable generation
- `--vars N` - Set variable generation threshold (default: 3)

### Implementation Notes for instances off (2025-12)

**Purpose:** Completely disable instance generation in DesignSpace output.

**Code Locations:**
- Model: `src/dssketch/core/models.py` - `DSSDocument.instances_off: bool`
- Parser: `src/dssketch/parsers/dss_parser.py:203` - parses `instances off`
- Converter: `src/dssketch/converters/dss_to_designspace.py:78` - skips instance generation
- Writer: `src/dssketch/writers/dss_writer.py:150` - outputs `instances off`

**Usage:**
```dssketch
instances off
```

**Use cases:**
- avar2 fonts where instances are not needed
- Build pipelines that generate instances externally
- Testing axis configurations without instance overhead

### Implementation Notes for Family Auto-Detection (2025-12)

**Purpose:** Make the `family` field optional - auto-detect from base source UFO if not specified.

**Code Locations:**
- Validator: `src/dssketch/utils/dss_validator.py` - changed from CRITICAL error to warning
- Parser: `src/dssketch/parsers/dss_parser.py` - handles empty family with warning
- Converter: `src/dssketch/converters/dss_to_designspace.py` - `_detect_family_name()` method

**How it works:**
1. If `family` is specified in DSSketch - use it as-is
2. If `family` is missing or empty:
   - Find the base source (`@base` flag)
   - Read the UFO using fontParts
   - Extract `font.info.familyName`
   - Falls back to "Unknown" if UFO not found or has no familyName
   - Logs a warning (non-critical)

**Key Implementation (`dss_to_designspace.py`):**
```python
def _detect_family_name(self, dss_doc: DSSDocument) -> str:
    """Detect family name from UFO if not specified in DSS document."""
    if dss_doc.family and dss_doc.family.strip():
        return dss_doc.family

    # Find base source
    base_source = None
    for source in dss_doc.sources:
        if source.is_base:
            base_source = source
            break

    if not base_source:
        self.logger.warning("No base source found - using 'Unknown'")
        return "Unknown"

    # Build UFO path
    ufo_path = Path(dss_doc.path or "") / base_source.filename
    if self.base_path and not ufo_path.is_absolute():
        ufo_path = self.base_path / ufo_path

    try:
        font = Font(str(ufo_path))
        family_name = font.info.familyName
        if family_name:
            self.logger.info(f"Detected family name '{family_name}' from {ufo_path.name}")
            return family_name
    except Exception as e:
        self.logger.warning(f"Failed to read UFO '{ufo_path}': {e}")

    return "Unknown"
```

**Usage:**
```dssketch
# Family is optional - will be auto-detected from base source UFO
path sources

axes
    wght 100:400:900
sources [wght]
    Regular [400] @base  # Family detected from this UFO
```

### Implementation Notes for Instances Roundtrip (2025-12)

**Purpose:** Preserve zero-instance state during DesignSpace → DSSketch → DesignSpace roundtrip.

**Problem:** Original DesignSpace files with 0 instances were getting thousands of auto-generated instances after roundtrip conversion (due to `instances auto` default).

**Fix:** When converting DesignSpace → DSSketch, if original has 0 instances, set `instances_off=True`.

**Code Location:** `src/dssketch/converters/designspace_to_dss.py`

```python
# Convert instances (optional - can be auto-generated)
if ds_doc.instances:
    for instance in ds_doc.instances:
        dss_instance = self._convert_instance(instance, ds_doc)
        dss_doc.instances.append(dss_instance)
else:
    # No instances in original - set instances_off to preserve this
    dss_doc.instances_off = True
```

**Result:** Files with 0 instances now correctly roundtrip to 0 instances.

### Module Reference

Complete reference of all modules in the DSSketch project. **IMPORTANT: Always check this reference before implementing new functionality to avoid code duplication.**

#### Core Package (`src/dssketch/`)

**`__init__.py`**
- Package initialization
- Exports public API functions: `convert_to_dss`, `convert_to_designspace`, `convert_dss_string_to_designspace`, `convert_designspace_to_dss_string`
- Exports core classes: `DSSParser`, `DSSWriter`, converters

**`api.py`** - High-level API for DSSketch integration
- `convert_to_dss(designspace, dss_path, optimize=True, vars_threshold=3, avar2_format="matrix")` - Convert DesignSpace object to DSSketch file
- `convert_to_designspace(dss_path)` - Convert DSSketch file to DesignSpace object
- `convert_dss_string_to_designspace(dss_content, base_path)` - Convert DSSketch string to DesignSpace
- `convert_designspace_to_dss_string(designspace, optimize=True, vars_threshold=3, avar2_format="matrix")` - Convert DesignSpace to DSSketch string
- **Parameters**: `vars_threshold` (0=disabled, 3=default), `avar2_format` ("matrix" or "linear")
- **Purpose**: Provides simple, user-friendly API for integrating DSSketch into other projects

**`cli.py`** - Command-line interface implementation
- Main CLI entry point after package installation
- Handles argument parsing and conversion workflows
- Integrates with UFO validation and logging
- **CLI options**:
  - `--matrix` - Use matrix format for avar2 output (default)
  - `--linear` - Use linear format for avar2 output
  - `--novars` - Disable automatic variable generation
  - `--vars N` - Set variable generation threshold (default: 3)
  - `-o, --output` - Specify output file path
- **Purpose**: User-facing CLI for DSSketch conversions

**`data_cli.py`** - Data file management CLI
- `dssketch-data info` - Show data file locations and status
- `dssketch-data copy <file>` - Copy default data files to user directory
- `dssketch-data edit` - Open user data directory in file manager
- `dssketch-data reset` - Reset data files to defaults
- **Purpose**: Manage user data file overrides and customization

**`config.py`** - Configuration and data file management
- `DataManager` class - Handles user data file overrides
- Manages paths to `data/` directory
- Supports user-specific customization via `~/.dssketch/` directory
- **Purpose**: Centralized configuration and data file resolution

#### Parsers (`src/dssketch/parsers/`)

**`dss_parser.py`** - Main DSSketch format parser
- `DSSParser` class - Parses .dssketch format into `DSSDocument` structure
- Robust validation with typo detection, coordinate validation, syntax checking
- Label-based coordinate resolution (`_resolve_coordinate_value`)
- Label-based axis range resolution (`_resolve_axis_range_value`)
- Human-readable axis name support (weight → wght, etc.)
- Supports strict/non-strict parsing modes
- Uses `DiscreteAxisHandler` for discrete axis detection
- **Purpose**: Convert DSSketch text format to structured data model
- **Key Methods**:
  - `parse(content)` - Parse DSSketch string
  - `parse_file(file_path)` - Parse DSSketch file
  - `_parse_source_line()` - Parse source definitions (supports label-based coordinates)
  - `_parse_axis_line()` - Parse axis definitions (supports label-based ranges)
  - `_parse_rule_line()` - Parse substitution rules
  - `_get_design_space_bounds()` - Extract design space bounds for rule conditions

#### Writers (`src/dssketch/writers/`)

**`dss_writer.py`** - DSSketch format writer
- `DSSWriter` class - Generates .dssketch format from `DSSDocument` structure
- Optimization and compression features
- Label-based coordinate output (`use_label_coordinates=True`)
- Label-based range output (`use_label_ranges=True`)
- Path optimization and common directory detection
- **avar2 format**: `avar2_format="matrix"` (default) or `"linear"`
- **Purpose**: Convert structured data model to DSSketch text format
- **Key Methods**:
  - `write(dss_doc)` - Generate DSSketch string
  - `_format_source()` - Format source definitions (outputs labels when available)
  - `_format_axis()` - Format axis definitions (outputs label-based ranges)
  - `_get_label_for_coordinate()` - Find label for design-space coordinate
  - `_get_label_for_user_value()` - Find label for user-space value

#### Converters (`src/dssketch/converters/`)

**`designspace_to_dss.py`** - DesignSpace → DSSketch converter
- `DesignSpaceToDSS` class - Converts DesignSpace XML to DSSketch format
- Extracts family, axes, sources, instances, rules from DesignSpace
- Detects common paths and optimizes output
- Maps DesignSpace structures to DSS data models
- **Purpose**: Convert from verbose XML to compact DSSketch format

**`dss_to_designspace.py`** - DSSketch → DesignSpace converter
- `DSSToDesignSpace` class - Converts DSSketch format to DesignSpace XML
- Expands wildcard patterns in rules using UFO glyph lists
- Generates instances from `instances auto` directive
- Validates UFO files and extracts glyph names
- **Purpose**: Convert from DSSketch to standard DesignSpace format
- **Key Methods**:
  - `convert(dss_doc)` - Main conversion entry point
  - `_expand_wildcard_pattern()` - Expand rule wildcards to actual glyphs
  - `_create_rule()` - Create DesignSpace rule from DSS rule

#### Core Models & Logic (`src/dssketch/core/`)

**`models.py`** - Data models for DSSketch
- `DSSDocument` - Complete DSSketch document structure
  - `instances_auto: bool` - Flag for automatic instance generation
  - `instances_off: bool` - Flag to disable instance generation entirely
  - `instances_skip: List[str]` - Instance combinations to skip
  - `hidden_axes: List[DSSAxis]` - avar2 hidden parametric axes
  - `avar2_vars: Dict[str, float]` - avar2 variable definitions ($name -> value)
  - `avar2_mappings: List[DSSAvar2Mapping]` - avar2 inter-axis mappings
- `DSSAxis` - Axis definition with mappings
- `DSSAxisMapping` - Single axis mapping point (user/design values, label, elidable flag)
- `DSSSource` - Source file definition with location
- `DSSInstance` - Instance definition
- `DSSRule` - Substitution rule with conditions
- `DSSAvar2Mapping` - avar2 mapping (input conditions -> output values)
  - `name: Optional[str]` - Optional description
  - `input: Dict[str, float]` - Input axis conditions
  - `output: Dict[str, float]` - Output axis values
- **Purpose**: Type-safe data structures for DSSketch document representation

**`mappings.py`** - Standard weight/width mappings
- `Standards` class - Built-in weight/width value mappings
- `get_user_space_value(name, axis_type)` - Get standard user-space value for label
- `get_name_by_user_space(value, axis_type)` - Get standard label for user-space value
- `has_mapping(name, axis_type)` - Check if label exists in standard mappings
- **Purpose**: Centralized standard axis value mappings for label-based syntax

**`validation.py`** - UFO file validation
- `UFOValidator` - Validates UFO source files
- `UFOGlyphExtractor` - Extracts glyph lists from UFO files
- Safe UFO reading without modifying files
- **Purpose**: Validate sources and extract glyph information for wildcard expansion

**`instances.py`** - Automatic instance generation
- `createInstances(dssource, defaultFolder, skipFilter)` - Generate all instance combinations
- `sortAxisOrder(ds)` - Order axes according to DSS document or DEFAULT_AXIS_ORDER
  - **Hidden axes excluded**: Only user-facing axes included in instance generation
- `getElidabledNames(ds, axisOrder, ignoreAxis)` - Find elidable labels for name cleanup
- `getInstancesMapping(ds, axisName)` - Extract axis value mappings
  - **Fallback for unlabeled axes**: When axis has no labels, generates from min:def:max + avar2 input points
  - Instance names use format `tag+value` (e.g., `wght400 opsz16`)
- `createInstance(location, familyName, styleName, defaultFolder)` - Create single instance
- Uses `itertools.product()` for combinatorial generation
- **Purpose**: Sophisticated automatic instance generation from axis combinations

#### Utilities (`src/dssketch/utils/`)

**`discrete.py`** - Discrete axis handling
- `DiscreteAxisHandler` class - Centralized discrete axis detection and label management
- `load_discrete_labels()` - Load discrete axis labels from `data/discrete-axis-labels.yaml`
- `is_discrete(axis)` - Detect if axis is discrete (values attribute or 0:0:1 range)
- `get_labels(axis_name)` - Get standard labels for discrete axis
- Supports user data file overrides via DataManager
- **Purpose**: Centralized discrete axis functionality (avoids code duplication)

**`patterns.py`** - Wildcard pattern matching
- `PatternMatcher` class - Glyph pattern matching for rules
- Supports prefix wildcards (`A*`), exact matches, universal wildcards (`*`)
- `matches(pattern, glyph_name)` - Check if glyph matches pattern
- `expand_pattern(pattern, available_glyphs)` - Expand wildcard to matching glyphs
- **Purpose**: Smart wildcard expansion for substitution rules

**`conditions.py`** - Rule condition parsing and formatting
- `ConditionHandler` class - Centralized condition handling
- `parse(condition_str, axis_ranges)` - Parse condition string to structured format
- `format(conditions)` - Format conditions to readable string
- Supports: `>=`, `<=`, `==`, range conditions, compound conditions with `&&`
- **Purpose**: Parse and format substitution rule conditions

**`dss_validator.py`** - DSSketch document validation
- `DSSValidator` class - Comprehensive document validation with intelligent typo detection
- `validate_document(document)` - Full document structural and content validation
- `levenshtein_distance(s1, s2)` - Edit distance algorithm for typo detection (threshold: 2 chars)
- `validate_axis_tag(tag)` - Detects axis tag typos and human-readable names
- `validate_mapping_label(label, axis_tag, all_axes)` - Detects mapping label typos
- `get_valid_labels_for_axis(axis_tag, all_axes)` - Smart cross-axis label validation
- `_validate_duplicate_mapping_labels(document)` - CRITICAL: prevents duplicate labels across axes
- Critical structure validation (axes, sources, base source required)
- Content validation (mappings, coordinates, labels)
- Coordinate and range validation
- **Purpose**: Robust error detection with helpful suggestions (similar to git, npm, bash)

**`logging.py`** - Logging configuration
- `DSSketchLogger` class - Centralized logging for DSSketch operations
- `setup_logger(file_path, log_level)` - Setup file and console logging
- Automatic `logs/` subdirectory creation
- Log filename format: `{basename}_{timestamp}.log`
- Methods: `info()`, `warning()`, `error()`, `debug()`, `success()`
- **Purpose**: Consistent logging across all DSSketch operations

### Data Files

- `data/unified-mappings.yaml` - Standard weight/width mappings and extended axis mappings (used for label-based ranges)
- `data/unified-mappings.json` - JSON fallback version of unified-mappings.yaml
- `data/font-resources-translations.json` - Localization data
- `data/discrete-axis-labels.yaml` - Standard labels for discrete axes (ital, slnt)

### Test Files

- `tests/test_parser_validation.py` - Comprehensive parser validation test suite (19 tests)
- `tests/test_typo_validation.py` - Typo detection validation tests (13 tests):
  - Duplicate mapping labels across axes (CRITICAL)
  - Axis tag typos (ERROR): wgth → wght, human-readable names
  - Mapping label typos (WARNING): Reguler → Regular, Lite → Light
  - Smart cross-axis logic validation
- `tests/test_label_based_syntax.py` - Label-based syntax tests (coordinates and ranges)
- `tests/test_label_based_conditions.py` - Label-based rule conditions tests (11 tests):
  - Simple label conditions: `weight >= Bold`
  - Range label conditions: `Regular <= weight <= Bold`
  - Compound conditions: `weight >= Bold && width <= Wide`
  - Mixed numeric and label conditions
  - Error handling for invalid labels
- `tests/test_label_range_validation.py` - Label-based range validation tests (8 tests)
- `tests/test_rule_axis_validation.py` - Rule axis validation tests (5 tests)
- `tests/test_mapping_range_validation.py` - Mapping range validation tests (8 tests)
- `tests/test_discrete_axis_no_warning.py` - Discrete axis warning tests
- `tests/test_human_axis_names.py` - Human-readable axis name tests
- Tests cover: keyword typos, axis tag typos, mapping label typos, duplicate labels, empty values, coordinate validation, bracket detection, axis ranges, rule syntax, label validation, axis references, mapping bounds, label-based conditions
- **Total**: 85 tests passing
- Run with: `python -m pytest tests/ -v`

### File Extensions

- `.dssketch` or `.dss` - DSSketch format (compact)
- `.designspace` - DesignSpace XML (verbose)
- Both directions preserve full functionality

## Performance Characteristics

Typical compression ratios:
- 2D fonts (weight×italic): 84-85% size reduction
- 4D fonts (weight×width×contrast×slant): 97% size reduction
- Complex fonts: Up to 36x smaller (MyFont: 204KB → 5.6KB)

## Common Development Tasks

When modifying the converter:
1. Test with all examples in `examples/` directory
2. Ensure bidirectional conversion preserves data
3. Check wildcard pattern detection/expansion
4. Validate axis mapping integrity

When adding features:
1. Update both parser and writer components
2. Test bidirectional conversion (DSSketch ↔ DesignSpace)
3. Verify complex rules with compound conditions
4. Check handling of both standard and custom axes
5. Validate wildcard expansion with UFO files
6. Add validation logic to `src/dssketch/utils/validation.py`
7. Test both strict and non-strict parsing modes
8. Add test cases to `tests/test_parser_validation.py`

## Parser Validation Framework

### Validation Features

The DSSketch parser includes comprehensive validation to catch common manual editing errors:

**1. Keyword Typo Detection:**
```python
# Detects and suggests corrections for typos
familly SuperFont     # → "Unknown keyword 'familly'. Did you mean 'family'?"
axess                 # → "Unknown keyword 'axess'. Did you mean 'axes'?"
sourcse              # → "Unknown keyword 'sourcse'. Did you mean 'sources'?"
```

**2. Empty Value Validation:**
```python
# Catches missing required values
family               # → "Family name cannot be empty"
family               # → "Family name cannot be empty" (trailing space)
```

**3. Coordinate Validation:**
```python
# Validates coordinate format and values
Font-Light [abc, def] # → "Invalid coordinates: Invalid coordinate value: could not convert..."
Font-Regular []       # → "Invalid coordinates: Empty coordinate values"
Font-Bold [100, ]     # → "Invalid coordinates: Empty coordinate value"
```

**4. Bracket Type Detection:**
```python
# Warns about incorrect bracket types
Font-Light (100, 0)   # → "Use [] for coordinates, not ()"
Font-Regular {400, 0} # → "Use [] for coordinates, not {}"
```

**5. Axis Range Validation:**
```python
# Validates axis range logic and format
wght 900:100:400      # → "Range values must be ordered: min <= default <= max"
wdth abc:def:ghi      # → "Non-numeric values in range"
ital 0:1:2:3          # → "Invalid range format. Expected min:max or min:default:max"
```

**6. Rule Syntax Validation:**
```python
# Validates substitution rule completeness
dollar > .rvrn (weight >= )    # → "Invalid rule syntax: ..."
* > (weight >= 400)            # → "Rule missing target pattern"
dollar .rvrn (weight >= 400)   # → "Rule missing '>' separator"
```

**7. Label-Based Range Validation:**
```python
# Validates label names in axis ranges
wght s:r:Bold       # → "Label 's' not found in standard weight mappings"
wght Thin:Foo:Black # → "Label 'Foo' not found in standard weight mappings"
wdth A:B:C          # → "Label 'A' not found in standard width mappings"

# Valid examples:
wght Thin:Regular:Black  # Uses standard weight labels
wdth Condensed:Normal:Extended  # Uses standard width labels
```

**8. Rule Axis Validation:**
```python
# Rules must reference existing axes
a > a.italic (italic == 1)  # → "Rule references axis 'italic' which is not defined"
# When italic axis is not defined in axes section

# Valid example (italic axis exists):
axes
    ital discrete
        Upright
        Italic
rules
    a > a.italic (italic == 1)  # OK - italic axis exists
```

**9. Mapping Range Validation:**
```python
# Mappings must be within axis range
axes
    wght 300:400:500
        Bold > 1000  # → "mapping 'Bold' has user_value 700.0 outside the axis range [300.0, 500.0]"

# Valid example:
axes
    wght 300:400:900
        Light > 300  # user_value 300 is within [300, 900]
        Regular > 400
        Bold > 700   # user_value 700 is within [300, 900]
```

**10. Critical Structure Validation (Always Fails!):**
```python
# Missing axes section
family SuperFont
sources
    Font-Light [100] @base     # → "CRITICAL: No axes found - cannot generate valid DesignSpace"

# Missing sources section
family SuperFont
axes
    wght 100:400:900           # → "CRITICAL: No sources found - cannot generate valid DesignSpace"

# Missing base source
sources
    Font-Light [100]
    Font-Regular [400]         # → "CRITICAL: No base source found (@base flag missing)"

# Multiple base sources
sources
    Font-Light [100] @base
    Font-Regular [400] @base   # → "CRITICAL: Multiple base sources found (2) - only one allowed"

# Non-ASCII characters in keywords
axшes                         # → "Invalid section keyword 'axшes' - contains non-ASCII characters"
```

**11. CRITICAL - Duplicate Mapping Labels:**
```python
# Prevents labels used across multiple axes (breaks instance generation)
axes
    wght 100:900
        Light > 100   # ❌ CRITICAL ERROR
    wdth 75:125
        Light > 75    # Same label "Light" in different axes!

# → "CRITICAL: Mapping label 'Light' is used in multiple axes: 'weight' (wght), 'width' (wdth).
#    Each mapping label must be unique across all axes to avoid conflicts in instance naming
#    and label-based coordinates. Use different labels for each axis."
```

**12. ERROR - Axis Tag Typos:**
```python
# Detects typos in standard axis tags using Levenshtein distance algorithm
axes
    wgth 100:900      # ❌ ERROR: "Axis tag 'wgth' looks like a typo..." (strict mode)
    widht 75:125      # ❌ ERROR: "Axis tag 'widht' looks like a typo..."

    # ✅ Human-readable names are VALID (automatically converted):
    weight 100:900    # ✅ OK: auto-converts to 'wght', no error
    width 75:125      # ✅ OK: auto-converts to 'wdth', no error
    italic discrete   # ✅ OK: auto-converts to 'ital', no error

    # ✅ Custom axes (UPPERCASE) are valid:
    WGTH 100:900      # ✅ OK: custom axis, not checked for typos
    CUSTOM 0:100      # ✅ OK: custom axis

# How it works:
# - Typos in 4-char lowercase tags detected with edit distance ≤ 2 (strict mode only)
# - Human-readable names supported: weight, width, italic, slant, optical → auto-converted
# - UPPERCASE tags treated as custom axes (not checked): WGTH, CUSTOM, CNTR
```

**13. WARNING - Mapping Label Typos:**
```python
# Detects typos in standard weight/width mapping labels
axes
    wght 100:400:900
        Lite > 300        # ⚠️ Warning: "Lite looks like a typo. Did you mean 'Light'?"
        Reguler > 400     # ⚠️ Warning: "Reguler looks like a typo. Did you mean 'Regular'?"
        Bol > 700         # ⚠️ Warning: "Bol looks like a typo. Did you mean 'Bold'?"

# Smart Cross-Axis Logic:
# - Only wght axis: Allows both weight AND width labels (Light, Bold, Condensed, Wide)
# - Only wdth axis: Allows both width AND weight labels (Condensed, Wide, Light, Bold)
# - Both wght and wdth: Each axis restricted to its own standard labels

# Example: Width labels allowed when only wght exists
axes
    wght 100:900
        Condensed > 100  # ✅ OK - no wdth axis, so width labels allowed
        Extended > 900   # ✅ OK

# But NOT when both axes exist
axes
    wght 100:900
        Bold > 700       # ✅ OK - weight label in weight axis
    wdth 75:125
        Bold > 125       # ❌ CRITICAL - duplicate label across axes
```

**Algorithm Details:**
- **Levenshtein distance** with threshold of 2 characters (same as git, npm, bash)
- Custom labels (distance > 2 from standards) are accepted without warnings
- Test suite: `tests/test_typo_validation.py` (13 comprehensive tests)

### Using the Validation Framework

**Strict Mode (Default):**
```python
from src.dssketch.parsers.dss_parser import DSSParser

parser = DSSParser(strict_mode=True)  # Stops on first error
try:
    result = parser.parse(content)
except ValueError as e:
    print(f"Parsing failed: {e}")
```

**Non-Strict Mode (Collect All Issues):**
```python
parser = DSSParser(strict_mode=False)  # Collects all errors and warnings
result = parser.parse(content)

# Review all issues
for error in parser.validator.errors:
    print(f"ERROR: {error}")
for warning in parser.validator.warnings:
    print(f"WARNING: {warning}")
```

### Validation Test Suite

Run comprehensive validation tests:
```bash
# Run all parser validation tests
python -m pytest tests/test_parser_validation.py -v

# Run typo detection tests
python -m pytest tests/test_typo_validation.py -v

# Test specific validation features
python -m pytest tests/test_parser_validation.py::TestParserValidation::test_keyword_typo_detection -v
python -m pytest tests/test_typo_validation.py::TestDuplicateMappingLabels -v
python -m pytest tests/test_typo_validation.py::TestAxisTagTypos -v
python -m pytest tests/test_typo_validation.py::TestMappingLabelTypos -v
```

### Best Practices for Manual Editing

**✅ Recommended Format:**
```dssketch
family SuperFont
path sources

axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
    ital discrete
        Upright @elidable
        Italic

sources [wght, ital]
    Font-Thin [100, 0]
    Font-Regular [400, 0] @base
    Font-Black [900, 0]
    Font-Italic [400, 1]

rules
    dollar > .rvrn (weight >= 400) "dollar alternates"

instances auto
```

**❌ Common Errors to Avoid:**
```dssketch
# CRITICAL ERRORS (Always fail, break DesignSpace generation):
axшes               # → axes (non-ASCII character)
# Missing axes section completely
# Missing sources section completely
# No @base source defined
# Multiple @base sources

# Keyword typos
familly SuperFont    # → family
axess               # → axes

# Empty values
family              # → family SuperFont

# Wrong brackets
Font-Light (100, 0) # → Font-Light [100, 0]

# Invalid ranges
wght 900:100:400    # → wght 100:400:900

# Invalid label-based ranges
wght s:r:Bold       # → wght Thin:Regular:Black (use standard labels)
wght Foo:Bar:Baz    # → wght 100:400:900 (or use standard labels)

# Rules referencing non-existent axes
a > a.italic (italic == 1)  # → Add italic axis first, or remove rule

# Mappings outside axis range
axes
    wght 300:400:500
        Bold > 1000  # → Change axis range or mapping value

# Incomplete rules
* > (weight >= 400) # → * > .rvrn (weight >= 400)
```
