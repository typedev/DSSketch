# DesignSpace Sketch

**Human-friendly alternative to DesignSpace XML**

DSSketch provides a simple, intuitive text format for describing variable fonts, replacing the overcomplicated and verbose XML format with clean, readable text that font designers can easily understand and edit by hand. This makes variable font development more accessible and less error-prone.

**The core philosophy:** Transform complex, verbose XML into simple, human-readable format that achieves 84-97% size reduction while maintaining full functionality.

## Why DSSketch?

### Before: DesignSpace XML (verbose, error-prone)
```xml
<?xml version='1.0' encoding='UTF-8'?>
<designspace format="5.0">
  <axes>
    <axis tag="wght" name="weight" minimum="100" maximum="900" default="400">
      <labelname xml:lang="en">Weight</labelname>
      <map input="100" output="0"/>
      <map input="300" output="211"/>
      <map input="400" output="356"/>
      <map input="500" output="586"/>
      <map input="700" output="789"/>
      <map input="900" output="1000"/>
      <labels ordering="0">
        <label uservalue="100" name="Thin"/>
        <label uservalue="300" name="Light"/>
        <label uservalue="400" name="Regular" elidable="true"/>
        <label uservalue="500" name="Medium"/>
        <label uservalue="700" name="Bold"/>
        <label uservalue="900" name="Black"/>
      </labels>
    </axis>
    <axis tag="ital" name="italic" values="0 1" default="0">
      <labelname xml:lang="en">Italic</labelname>
      <labels ordering="1">
        <label uservalue="0" name="Upright" elidable="true"/>
        <label uservalue="1" name="Italic"/>
      </labels>
    </axis>
  </axes>
  <rules>
    <rule name="heavy alternates">
      <conditionset>
        <condition name="weight" minimum="600" maximum="1000"/>
      </conditionset>
      <sub name="cent" with="cent.rvrn"/>
      <sub name="cent.old" with="cent.old.rvrn"/>
      <sub name="cent.sc" with="cent.sc.rvrn"/>
      <sub name="cent.tln" with="cent.tln.rvrn"/>
      <sub name="cent.ton" with="cent.ton.rvrn"/>
      <sub name="dollar" with="dollar.rvrn"/>
      <sub name="dollar.old" with="dollar.old.rvrn"/>
      <sub name="dollar.sc" with="dollar.sc.rvrn"/>
      <sub name="dollar.tln" with="dollar.tln.rvrn"/>
      <sub name="dollar.ton" with="dollar.ton.rvrn"/>
    </rule>
  </rules>
  <sources>
    <source filename="masters/SuperFont-Thin.ufo" familyname="SuperFont" stylename="Thin">
      <location>
        <dimension name="Weight" xvalue="0"/>
        <dimension name="Italic" xvalue="0"/>
      </location>
    </source>
    <source filename="masters/SuperFont-Regular.ufo" familyname="SuperFont" stylename="Regular">
      <location>
        <dimension name="Weight" xvalue="356"/>
        <dimension name="Italic" xvalue="0"/>
      </location>
    </source>
    <!-- ... 50+ more lines for simple 2-axis font ... -->
  </sources>
  <instances>
    <!-- ... hundreds of lines for instance definitions ... -->
  </instances>
</designspace>
```

### After: DSSketch (clean, intuitive)
```dssketch
family SuperFont
path masters

axes
    wght 100:400:900
        Thin > 0
        Light > 211
        Regular > 356 @elidable
        Medium > 586
        Bold > 789
        Black > 1000
    ital discrete
        Upright @elidable
        Italic

masters [wght, ital]
    SuperFont-Thin [0, 0]
    SuperFont-Regular [356, 0] @base
    SuperFont-Black [1000, 0]
    SuperFont-Thin-Italic [0, 1]
    SuperFont-Italic [356, 1]
    SuperFont-Black-Italic [1000, 1]

rules
    dollar* cent* > .rvrn (weight >= 600) "heavy alternates"

instances auto
```

**Result: 93% smaller, infinitely more readable**

## Key Advantages

### 1. **Dramatic Size Reduction**
- **2D fonts** (weight × italic): 84-85% smaller
- **4D fonts** (weight × width × contrast × slant): 97% smaller
- **Real example**: MyFont 204KB → 5.6KB (36x compression)

### 2. **Human-Friendly Syntax**
- **Intuitive axis definitions**: `wght 100:400:900` instead of verbose XML attributes
- **Simple master coordinates**: `[400, 0]` instead of complex XML dimension tags
- **Readable rules**: `dollar > .rvrn (weight >= 400)` instead of nested XML structures
- **Common directory paths**: `path masters` eliminates repetitive file paths

### 3. **Smart Automation**
- **Auto instance generation**: `instances auto` creates all meaningful combinations
- **Standard weight mapping**: Recognizes `Regular > 400`, `Bold > 700` automatically
- **Wildcard rule expansion**: `* > .alt` finds all glyphs with .alt variants
- **UFO validation**: Automatically validates master files and extracts glyph lists

### 4. **Advanced Features Made Simple**

#### Discrete Axes (Revolutionary Simplicity)
```dssketch
# Instead of complex XML values="0 1" attributes:
ital discrete
    Upright @elidable    # No need for > 0
    Italic               # No need for > 1
```

#### Flexible Substitution Rules
```dssketch
rules
    # Simple glyph substitution
    dollar > dollar.rvrn (weight >= 400)

    # Wildcard patterns
    A* > .alt (weight >= 600)      # All glyphs starting with A
    * > .rvrn (weight >= 500)      # All glyphs with .rvrn variants

    # Complex conditions with design space coordinates
    ampersand > .fancy (weight >= 600 && width >= 110)
    thin* > .ultra (weight >= -100)  # Negative coordinates supported
```

#### Explicit Axis Order Control
```dssketch
# Control instance generation order
axes
    wdth 60:100:200    # First in names: "Condensed Light" - "{width} {weight}"
        Condensed > 350.0
        Normal > 560.0 @elidable
    wght 100:400:900   # Second in names
        Light > 100
        Bold > 900

masters [wght, wdth]   # Coordinates follow this order: [weight, width]
    Light.ufo [100, 350]
    Regular.ufo [400, 350]
```

### 5. **Robust Error Detection**
- **Typo detection**: `familly` → "Did you mean 'family'?"
- **Coordinate validation**: `[abc, def]` → "Invalid coordinate value"
- **Missing base master**: Prevents broken DesignSpace generation
- **Rule syntax validation**: Catches incomplete substitution rules
- **Bracket type detection**: `(100, 0)` → "Use [] for coordinates"

## Installation & Usage

### Command Line
```bash
# Install from source
pip install -e .

# Convert DesignSpace → DSSketch (with UFO validation)
dssketch font.designspace

# Convert DSSketch → DesignSpace
dssketch font.dssketch

# With explicit output
dssketch input.designspace -o output.dssketch

# Skip UFO validation (not recommended)
dssketch font.dssketch --no-validation

# Alternative: direct Python
python dssketch_cli.py font.designspace
```

### Python API
```python
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

# High-level API functions (recommended)
# Convert DesignSpace object to DSSketch file
ds = DesignSpaceDocument()
ds.read("MyFont.designspace")
dssketch.convert_to_dss(ds, "MyFont.dssketch")

# Convert DSSketch file to DesignSpace object
ds = dssketch.convert_to_designspace("MyFont.dssketch")

# Work with DSSketch strings (for programmatic generation)
dss_content = """
family MyFont
axes
    wght 100:400:900
        Light > 100
        Regular > 400
        Bold > 900
masters
    Light.ufo [100]
    Regular.ufo [400] @base
    Bold.ufo [900]
"""

# Convert DSSketch string to DesignSpace object
ds = dssketch.convert_dss_string_to_designspace(dss_content, base_path="./")

# Convert DesignSpace object to DSSketch string
dss_string = dssketch.convert_designspace_to_dss_string(ds)
```

## DSSketch Format Examples

### Basic 2-Axis Font
```dssketch
family MyFont
path masters

axes
    wght 100:400:900
        Light > 100
        Regular > 400 @elidable
        Bold > 900
    ital discrete
        Upright @elidable
        Italic

masters [wght, ital]
    Light.ufo [100, 0]
    Regular.ufo [400, 0] @base
    Bold.ufo [900, 0]
    LightItalic.ufo [100, 1]
    Italic.ufo [400, 1]
    BoldItalic.ufo [900, 1]

instances auto
```

### Complex Multi-Axis Font
```dssketch
family SuperFont
suffix VF
path masters

axes
    wght 50:400:900
        Hairline > 0
        Thin > 68
        Light > 196
        Regular > 362 @elidable
        Medium > 477
        Bold > 732
        Black > 1000
    wdth 60:100:200
        Condensed > 60
        Normal > 100 @elidable
        Extended > 200
    ital discrete
        Upright @elidable
        Italic

masters [wght, wdth, ital]
    Hairline [0, 100, 0]
    Regular [362, 100, 0] @base
    Black [1000, 100, 0]
    HairlineCondensed [0, 60, 0]
    BlackExtended [1000, 200, 0]
    HairlineItalic [0, 100, 1]
    Italic [362, 100, 1]
    BlackItalic [1000, 100, 1]

rules
    # Currency symbols get heavy alternates
    dollar cent > .rvrn (weight >= 480)

    # Wildcard patterns
    A* > .alt (weight >= 600)      # All A-glyphs get alternates
    * > .fancy (weight >= 700 && width >= 150)  # Complex conditions

    # Negative design space coordinates
    thin* > .ultra (weight >= -50)

instances auto
```

### Advanced Rules and Patterns
```dssketch
family AdvancedFont

axes
    wght 100:400:900
    wdth 60:100:200
    CONT 0:50:100  # Custom axis (uppercase)

masters [wght, wdth, CONT]
    Light [100, 100, 0] @base
    Bold [900, 100, 100]

rules
    # Exact glyph substitution
    dollar > dollar.heavy (weight >= 500)

    # Multiple glyphs with same target
    dollar cent > .currency (weight >= 600)

    # Prefix wildcards (all glyphs starting with pattern)
    A* > .stylistic (weight >= 700)      # A, AE, Aacute, etc.
    num* > .proportional (CONT >= 50)    # number variants

    # Universal wildcard (all glyphs with matching targets)
    * > .rvrn (weight >= 400)            # Only creates rules where .rvrn exists
    * > .alt (weight >= 600 && width >= 150)  # Complex conditions

    # Range conditions
    o > o.round (400 <= weight <= 600)

    # Negative coordinates (supported in design space)
    ultra* > .thin (weight >= -100)
    back* > .forward (CONT <= -25)

instances auto
```

## Key Concepts

### User Space vs Design Space
```
User Space = Values users see (CSS font-weight: 400) = OS/2 table
Design Space = Actual coordinates where masters are located

Mapping example:
Regular > 362  means:
- User requests font-weight: 400 (Regular)
- Master is located at coordinate 362 in design space
- CSS 400 maps to design space 362
```

### Rule Conditions Use Design Space
**Important**: All rule conditions use design space coordinates, not user space values.

```dssketch
axes
    wght 100:400:900
        Light > 100     # User 100 → Design 100
        Regular > 362   # User 400 → Design 362
        Bold > 900      # User 700 → Design 900

rules
    # This condition uses design space coordinate 362, not user space 400
    dollar > .heavy (weight >= 362)  # Activates at Regular and heavier
```

### Discrete Axes (Revolutionary)
Traditional XML requires complex `values="0 1"` attributes. DSSketch makes it simple:

```dssketch
# Old way (still supported):
ital 0:0:1
    Upright > 0
    Italic > 1

# New way (recommended):
ital discrete
    Upright @elidable
    Italic
```

### Automatic Instance Generation
The `instances auto` feature intelligently creates all meaningful combinations:

```dssketch
axes
    ital discrete        # Controls name order: Italic first
        Upright @elidable
        Italic
    wght 100:400:900     # Weight second in names
        Light > 100
        Regular > 400 @elidable
        Bold > 900

instances auto  # Generates: "Light", "Italic", "Bold", "Italic Light", "Italic Bold"
```

**Result**: Automatic generation of proper PostScript names, file paths, and style linking.

## Architecture & API

### Core Components
- **High-level API**: `convert_to_dss()`, `convert_to_designspace()`, `convert_dss_string_to_designspace()`
- **Parsers**: `DSSParser` with comprehensive validation and error detection
- **Writers**: `DSSWriter` with optimization and compression
- **Converters**: Bidirectional `DesignSpaceToDSS` ↔ `DSSToDesignSpace`
- **Validation**: `UFOValidator`, `UFOGlyphExtractor` for robust master file handling
- **Instances**: `createInstances()` for intelligent automatic instance generation

### Data Management
```bash
# Install package first
pip install -e .

# Show data file locations
dssketch-data info

# Copy default files for customization
dssketch-data copy unified-mappings.yaml

# Edit user data directory
dssketch-data edit

# Reset to defaults
dssketch-data reset --all
```

### Error Handling
```python
from src.dssketch.parsers.dss_parser import DSSParser

# Strict mode (stops on first error)
parser = DSSParser(strict_mode=True)
try:
    result = parser.parse(content)
except ValueError as e:
    print(f"Parsing failed: {e}")

# Non-strict mode (collects all issues)
parser = DSSParser(strict_mode=False)
result = parser.parse(content)

# Review all validation issues
for error in parser.errors:
    print(f"ERROR: {error}")
for warning in parser.warnings:
    print(f"WARNING: {warning}")
```

## Performance Comparison

| Format | Lines | Size | Readability | Edit Safety |
|--------|-------|------|-------------|-------------|
| .designspace | 266 | 11.2 KB | ⭐⭐ | ⭐ |
| .dssketch | 21 | 0.8 KB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**Savings: 93% size reduction, 10x better readability, significantly safer manual editing**

## Real-World Benefits

### For Font Designers
- **Edit by hand**: Simple text format vs complex XML
- **Fewer errors**: Robust validation catches typos and mistakes
- **Faster iteration**: Quick edits without XML complexity
- **Better version control**: Clean diffs, readable changes

### For Developers
- **Easy integration**: Simple Python API
- **Smaller files**: 84-97% compression improves performance
- **Reliable parsing**: Comprehensive error detection and handling
- **Flexible automation**: Programmatic generation and processing

### For Teams
- **Better collaboration**: Human-readable format for reviews
- **Reduced errors**: Validation prevents broken DesignSpace files
- **Simplified workflows**: Less complex tooling needed
- **Knowledge sharing**: Format is self-documenting

## Testing

```bash
# Test with provided examples
python dssketch_cli.py examples/SuperFont-Variable.designspace
python dssketch_cli.py examples/MyFont_v2_VER1.dssketch

# Run validation tests
python -m pytest tests/test_parser_validation.py -v

# Test specific validation features
python -m pytest tests/test_parser_validation.py::TestParserValidation::test_keyword_typo_detection -v
```

## Examples

The `examples/` directory contains:
- `SuperFont-Variable.designspace` → Complex multi-axis font with non-linear mapping
- `SuperFont-compact.dss` → Equivalent DSSketch format (93% smaller)
- `wildcard-test.dss` → Demonstrates advanced wildcard rules
- Various test files showing edge cases and features

---

**DSSketch makes variable font development human-friendly. Simple syntax, powerful features, dramatic size reduction.**
