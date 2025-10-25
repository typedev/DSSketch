# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DesignSpace Sketch (DSSketch) is a Python tool that provides bidirectional conversion between compact `.dssketch` format and verbose `.designspace` XML files. It achieves 84-97% size reduction while maintaining full functionality for variable font design.

**Key Philosophy:**
The core idea of DSSketch is to provide a **human-friendly, simple, and intuitive** way to describe variable font design spaces, replacing the overly complex and verbose XML format with a clean, readable text format that font designers can easily understand and edit by hand. This makes variable font development more accessible and less error-prone.

## Key Commands

### Running the converter
```bash
# Primary CLI (preferred method) - UFO validation and optimization by default
python dssketch_cli.py font.designspace
python dssketch_cli.py font.dssketch

# After pip install -e . you can use CLI commands directly:
dssketch font.designspace       # Main converter
dssketch font.dssketch -o output.designspace

# CLI options:
dssketch font.dssketch --no-validation        # Skip UFO validation (not recommended)
dssketch font.dssketch --allow-missing-ufos   # Allow missing UFO files

# Or use Python directly:
python dssketch_cli.py input.designspace -o output.dssketch

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
# Install dependencies
pip install -r requirements.txt

# Dependencies: fonttools, fontParts, designspaceProblems, icecream
```

### Testing examples
```bash
# Test with provided examples
python dssketch_cli.py examples/SuperFont-Variable.designspace
python dssketch_cli.py examples/MyFont_v2_VER1.dssketch
python dssketch_cli.py examples/wildcard-test.dss
```

### Data file management
```bash
# Install package in development mode first
pip install -e .

# Show data files locations and status
dssketch-data info

# Copy default file for editing
dssketch-data copy unified-mappings.yaml

# Open user data directory in file manager
dssketch-data edit

# Reset files to defaults
dssketch-data reset --file unified-mappings.yaml
dssketch-data reset --all
```

## API Integration

DSSketch provides a high-level Python API for easy integration into other projects and applications. The API functions work with DesignSpace objects and DSSketch file paths, making it simple to incorporate DSSketch conversion into existing font development workflows.

### Core API Functions

```python
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

# Convert DesignSpace object to DSSketch file
dssketch.convert_to_dss(designspace: DesignSpaceDocument, dss_path: str, optimize: bool = True) -> str

# Convert DSSketch file to DesignSpace object
dssketch.convert_to_designspace(dss_path: str) -> DesignSpaceDocument

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
        Light > 100
        Regular > 400
        Bold > 900
sources
    MyFont-Light.ufo [100]
    MyFont-Regular.ufo [400] @base
    MyFont-Bold.ufo [900]
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

**Module Structure (after refactoring):**
- `dssketch_cli.py` - Main command-line interface
- `src/dssketch/` - Package root
  - `cli.py` - CLI implementation
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
- `src/dssketch/utils/validation.py`:
  - `DSSketchValidator` - Validation utilities for robust parsing and error detection
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
    wght 100:400:900  # min:default:max
        Thin > 100    # label > design_value
        Regular > 400
    ital discrete  # discrete axis (equivalent to ital 0:0:1)
        Upright    # simplified format (no > 0.0 needed)
        Italic     # simplified format (no > 1.0 needed)

sources [wght, ital]  # explicit axis order for coordinates
    # If path is set, just filename needed:
    SourceName [362, 0] @base  # [coordinates] @flags

    # Or individual paths per source:
    # upright/Light [100, 0]
    # italic/Bold [900, 1]

rules
    dollar > dollar.rvrn (weight >= 480) "dollar alternates"  # 480 = design space coordinate
    cent* > .rvrn (weight >= 480) "cent patterns"  # wildcard patterns
    A* > .alt (weight <= 500)  # all glyphs starting with A  
    * > .rvrn (weight >= 600)  # all glyphs that have .rvrn variants
    # Negative design space coordinates supported:
    thin* > .ultra (weight >= -100)  # negative design space value
    slanted* > .back (slnt <= -15)  # negative slant coordinate

instances auto  # instances follow axes section order
```

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
- **IMPORTANT**: Rule conditions always use **design space coordinates**, not user space
- Simple: `(weight >= 480)` - 480 is design space value, not user space
- Compound: `(weight >= 600 && width >= 110)` - both values are design space
- Exact: `(weight == 500)` - exact design space coordinate
- Range: `(80 <= width <= 120)` - design space range
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

**Parser Validation & Robustness (New!):**
- **Critical Structure Validation**: Ensures required sections (axes, sources, base source) are present - **ALWAYS FAILS** if missing
- **Typo Detection**: Catches common keyword misspellings (`familly` → `"Did you mean 'family'?"`)
- **Non-ASCII Character Detection**: Catches Unicode typos (`axшes` → `"contains non-ASCII characters"`)
- **Empty Value Validation**: Detects missing required values (`family ` → `"Family name cannot be empty"`)
- **Coordinate Validation**: Validates coordinate format and numeric values (`[abc, def]` → `"Invalid coordinate value"`)
- **Bracket Type Detection**: Warns about wrong bracket types (`(100, 0)` → `"Use [] for coordinates, not ()"`)
- **Axis Range Validation**: Checks axis range logic (`900:100:400` → `"Range values must be ordered"`)
- **Rule Syntax Validation**: Validates substitution rule completeness and syntax
- **Multiple Base Source Detection**: Prevents multiple @base sources which breaks DesignSpace
- **Two Processing Modes**: Strict mode (fails on errors) vs. non-strict (collects warnings, but **critical errors always fail**)
- **Whitespace Normalization**: Handles multiple spaces, tabs, and mixed whitespace gracefully
- **Unicode Support**: Full support for international characters in names and paths (but detects typos with wrong scripts)

**Explicit Axis Order (New Feature):**
- Sources section now supports explicit axis order: `sources [wght, ital]`
- Decouples coordinate interpretation from axes section order
- Supports both short tags (`wght`, `ital`) and long names (`weight`, `italic`)
- Allows users to reorder axes in axes section without breaking source coordinates
- Backward compatible: `sources` without brackets continues to work with axes order
- Example: axes can be `ital`, `wght` but coordinates follow `sources [wght, ital]` order

**Automatic Instance Generation (`instances auto`):**
- Uses sophisticated `instances.py` module for generating all meaningful instance combinations
- Creates instances from all axis mapping combinations automatically
- Handles elidable style names (removes redundant parts like "Regular" from "Regular Italic" → "Italic")
- **Respects axes order from DSS document**: instances follow the sequence defined in axes section
- Supports filtering and skipping unwanted combinations
- Generates proper PostScript names and file paths
- Integration: `dss_to_designspace.py:67` calls `createInstances()` when `instances_auto=True`
- **Custom axis ordering**: Change axes order in DSS to control instance name generation

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
        Light > 100
        Regular > 400
    wdth 60:100:200
        Condensed > 60
        Normal > 100

# Result: instances like "Italic Light Condensed"
```

### Data Files

- `data/stylenames.json` - Standard weight/width mappings
- `data/unified-mappings.yaml` - Extended axis mappings
- `data/font-resources-translations.json` - Localization data
- `data/discrete-axis-labels.yaml` - Standard labels for discrete axes (ital, slnt)

### Test Files

- `tests/test_parser_validation.py` - Comprehensive parser validation test suite
- Tests cover: keyword typos, empty values, coordinate validation, bracket detection, axis ranges, rule syntax
- Run with: `python -m pytest tests/test_parser_validation.py -v`

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

**7. Critical Structure Validation (Always Fails!):**
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
for error in parser.errors:
    print(f"ERROR: {error}")
for warning in parser.warnings:
    print(f"WARNING: {warning}")
```

### Validation Test Suite

Run comprehensive validation tests:
```bash
# Run parser validation tests
python -m pytest tests/test_parser_validation.py -v

# Test specific validation features
python -m pytest tests/test_parser_validation.py::TestParserValidation::test_keyword_typo_detection -v
```

### Best Practices for Manual Editing

**✅ Recommended Format:**
```dssketch
family SuperFont
path sources

axes
    wght 100:400:900
        Light > 100
        Regular > 400 @elidable
    ital discrete
        Upright @elidable
        Italic

sources [wght, ital]
    Font-Light [100, 0]
    Font-Regular [400, 0] @base
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

# Incomplete rules
* > (weight >= 400) # → * > .rvrn (weight >= 400)
```
