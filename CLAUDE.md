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
python dssketch_cli.py examples/KazimirText-Variable.designspace
python dssketch_cli.py examples/Onweer_v2_RAIN.dssketch
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
  - `DSSParser` - Parses .dssketch format into structured data
- `src/dssketch/writers/dss_writer.py`:
  - `DSSWriter` - Generates .dssketch from structured data
- `src/dssketch/converters/designspace_to_dss.py`:
  - `DesignSpaceToDSS` - Converts .designspace → DSSketch
- `src/dssketch/converters/dss_to_designspace.py`:
  - `DSSToDesignSpace` - Converts DSSketch → .designspace
- `src/dssketch/core/validation.py`:
  - `UFOValidator` - Validates UFO master files
  - `UFOGlyphExtractor` - Extracts glyph lists from UFO files
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
- Mapping: `Regular > 362` means user requests 400, master is at 362

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
- Essential for proper variable font generation with non-compatible masters

### DSSketch Format Structure

```dssketch
family FontName
suffix VF  # optional
path masters  # common directory for masters

axes
    wght 100:400:900  # min:default:max
        Thin > 100    # label > design_value
        Regular > 400
    ital discrete  # discrete axis (equivalent to ital 0:0:1)
        Upright    # simplified format (no > 0.0 needed)
        Italic     # simplified format (no > 1.0 needed)

masters [wght, ital]  # explicit axis order for coordinates
    # If path is set, just filename needed:
    MasterName [362, 0] @base  # [coordinates] @flags
    
    # Or individual paths per master:
    # upright/Light [100, 0]
    # italic/Bold [900, 1]
    
rules
    dollar > dollar.rvrn (weight >= 480) "dollar alternates"
    cent* > .rvrn (weight >= 480) "cent patterns"  # wildcard patterns
    A* > .alt (weight <= 500)  # all glyphs starting with A
    * > .rvrn (weight >= 600)  # all glyphs that have .rvrn variants

instances auto  # or explicit list
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

**Rule Conditions:**
- Simple: `(weight >= 480)`
- Compound: `(weight >= 600 && width >= 110)`
- Exact: `(weight == 500)`
- Range: `(80 <= width <= 120)`

**Optimization:**
- Auto-compresses multiple similar rules into wildcard patterns
- Detects standard weight/width values
- Removes redundant mappings

**Path Management:**
- Auto-detects common master directories (e.g., "masters/")
- Supports mixed paths for masters in different directories
- `path` parameter in DSSketch format for common directory

**UFO Validation:**
- Automatically extracts glyph names from UFO files for wildcard expansion
- Validates target glyphs exist before creating substitution rules
- Shows warnings for missing target glyphs but continues conversion
- Uses UFOGlyphExtractor to safely read glyph lists from sources

**Explicit Axis Order (New Feature):**
- Masters section now supports explicit axis order: `masters [wght, ital]`
- Decouples coordinate interpretation from axes section order
- Supports both short tags (`wght`, `ital`) and long names (`weight`, `italic`)
- Allows users to reorder axes in axes section without breaking master coordinates
- Backward compatible: `masters` without brackets continues to work with axes order
- Example: axes can be `ital`, `wght` but coordinates follow `masters [wght, ital]` order

**Automatic Instance Generation (`instances auto`):**
- Uses sophisticated `instances.py` module for generating all meaningful instance combinations
- Creates instances from all axis mapping combinations automatically
- Handles elidable style names (removes redundant parts like "Regular" from "Regular Italic" → "Italic")
- Follows standard axis ordering: Optical → Contrast → Width → Weight → Italic → Slant
- Supports filtering and skipping unwanted combinations
- Generates proper PostScript names and file paths
- Integration: `dss_to_designspace.py:67` calls `createInstances()` when `instances_auto=True`

## Important Implementation Details

### Implementation Notes for Rules

**Code Location:**
- Rule parsing: `src/dssketch/parsers/dss_parser.py:402` (_parse_rule_line)
- Wildcard expansion: `src/dssketch/converters/dss_to_designspace.py:247` (_expand_wildcard_pattern)
- Pattern matching: `src/dssketch/utils/patterns.py` (PatternMatcher class)

**Recent Fix (важно!):**
- Fixed wildcard detection for single patterns like `A*` without spaces
- Changed condition from `if ' ' in from_part and ('*' in from_part...)` 
- To: `if '*' in from_part or (' ' in from_part...)`
- This ensures patterns like `A*` are properly recognized as wildcards

### Implementation Notes for Explicit Axis Order

**Code Location:**
- Writer axis order output: `src/dssketch/writers/dss_writer.py:66` (_get_axis_tag method)
- Parser axis order parsing: `src/dssketch/parsers/dss_parser.py:115` (masters section parsing)
- Coordinate parsing with axis order: `src/dssketch/parsers/dss_parser.py:330` (_parse_master_line)

**Key Implementation Details:**
- `DSSWriter._get_axis_tag()` converts axis names to standard tags for output
- `DSSParser.master_axis_order` stores explicit axis order when `masters [tags]` format is used
- `DSSParser._tag_to_axis_name()` converts tags back to full axis names
- Master coordinate parsing uses explicit order when available, falls back to axes order
- Supports mapping between short tags (`wght`) and long names (`weight`)
- Full backward compatibility maintained for legacy `masters` format

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
2. Sort axes in standard order (Optical → Contrast → Width → Weight → Italic → Slant)
3. Extract all axis label combinations using `itertools.product()`
4. Apply skip filters for unwanted combinations
5. Generate elidable names to clean up style names (e.g., "Regular Italic" → "Italic")
6. Create instance descriptors with proper locations and names
7. Return enhanced DesignSpace with all generated instances

**Constants:**
- `DEFAULT_AXIS_ORDER` - Standard axis ordering for consistent instance generation
- `ELIDABLE_MAJOR_AXIS = "weight"` - Primary axis that should not be elidable
- `DEFAULT_INSTANCE_FOLDER = "instances"` - Default output folder for generated instances

### Data Files

- `data/stylenames.json` - Standard weight/width mappings
- `data/unified-mappings.yaml` - Extended axis mappings
- `data/font-resources-translations.json` - Localization data
- `data/discrete-axis-labels.yaml` - Standard labels for discrete axes (ital, slnt)

### File Extensions

- `.dssketch` or `.dss` - DSSketch format (compact)
- `.designspace` - DesignSpace XML (verbose)
- Both directions preserve full functionality

## Performance Characteristics

Typical compression ratios:
- 2D fonts (weight×italic): 84-85% size reduction
- 4D fonts (weight×width×contrast×slant): 97% size reduction
- Complex fonts: Up to 36x smaller (Onweer: 204KB → 5.6KB)

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