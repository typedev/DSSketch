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
    <source filename="sources/SuperFont-Thin.ufo" familyname="SuperFont" stylename="Thin">
      <location>
        <dimension name="Weight" xvalue="0"/>
        <dimension name="Italic" xvalue="0"/>
      </location>
    </source>
    <source filename="sources/SuperFont-Regular.ufo" familyname="SuperFont" stylename="Regular">
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
path sources

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

sources [wght, ital]
    SuperFont-Thin [0, 0]
    SuperFont-Regular [356, 0] @base
    SuperFont-Black [1000, 0]
    SuperFont-Thin-Italic [0, 1]
    SuperFont-Italic [356, 1]
    SuperFont-Black-Italic [1000, 1]

rules
    dollar* cent* > .rvrn (weight >= Bold) "heavy alternates"

instances auto
```

**Result: 93% smaller, infinitely more readable**

## Key Advantages

### 1. **Human-Friendly Syntax**
- **Intuitive axis definitions**: `wght 100:400:900` instead of verbose XML attributes
- **Simple source coordinates**: `[400, 0]` instead of complex XML dimension tags
- **Readable rules**: `dollar > .rvrn (weight >= 400)` instead of nested XML structures
- **Common directory paths**: `path sources` eliminates repetitive file paths

### 2. **Smart Automation**
- **Auto instance generation**: `instances auto` creates all meaningful combinations
- **Standard weight mapping**: Recognizes `Regular > 400`, `Bold > 700` automatically
- **Wildcard rule expansion**: `* > .alt` finds all glyphs with .alt variants
- **UFO validation**: Automatically validates source files and extracts glyph lists

### 3. **Label-Based Syntax**

Make your font files even more readable with label-based coordinates and ranges:

#### Label-Based Source Coordinates
```dssketch
# Traditional numeric format:
sources [wght, ital]
    Font-Regular [362, 0] @base
    Font-Black [1000, 1]

# Label-based format:
sources [wght, ital]
    Font-Regular [Regular, Upright] @base
    Font-Black [Black, Italic]
```

#### Label-Based Axis Ranges
```dssketch
# Traditional numeric format:
axes
    wght 100:400:900
    wdth 75:100:125

# Label-based ranges for weight and width:
axes
    weight Thin:Regular:Black   # Auto-converts to 100:400:900
    width Condensed:Normal:Extended  # Auto-converts to 80:100:150
```

#### Human-Readable Axis Names
```dssketch
# Short tags (traditional):
axes
    wght 100:400:900
    wdth 75:100:125
    ital discrete

# Human-readable names:
axes
    weight 100:400:900    # Auto-converts to wght
    width 75:100:125      # Auto-converts to wdth
    italic discrete       # Auto-converts to ital
```

**Supported names:** `weight` → `wght`, `width` → `wdth`, `italic` → `ital`, `slant` → `slnt`, `optical` → `opsz`

#### Label-Based Rule Conditions
```dssketch
# Traditional numeric format:
rules
    dollar > dollar.heavy (weight >= 700) "heavy dollar"
    ampersand > ampersand.fancy (weight >= 700 && width >= 110) "compound"

# Label-based format:
rules
    dollar > dollar.heavy (weight >= Bold) "heavy dollar"
    ampersand > ampersand.fancy (weight >= Bold && width <= Wide) "compound"
    g > g.alt (Regular <= weight <= Bold) "range condition"
```

**Benefits:**
- More readable: `weight >= Bold` vs `weight >= 700`
- Self-documenting: labels show semantic meaning
- Works with all operators: `>=`, `<=`, `==`, ranges
- Supports all axes: standard and custom
- Can mix numeric and label values

```dssketch
# Complete label-based example
family SuperFont
path sources

axes
    weight Thin:Regular:Black
        Thin > 0
        Light > 211
        Regular > 356 @elidable
        Medium > 586
        Bold > 789
        Black > 1000
    italic discrete
        Upright @elidable
        Italic

sources [wght, ital]
    SuperFont-Thin [Thin, Upright]
    SuperFont-Regular [Regular, Upright]
    SuperFont-Black [Black, Upright]
    SuperFont-Thin-Italic [Thin, Italic]
    SuperFont-Italic [Regular, Italic]
    SuperFont-Black-Italic [Black, Italic]

rules
    dollar* cent* > .rvrn (weight >= Bold) "heavy alternates"
    g > g.alt (Regular <= weight <= Bold) "medium weight"

instances auto
```


### 4. **Advanced Features Made Simple**

#### Discrete Axes
```dssketch
# Instead of complex XML values="0 1" attributes:
ital discrete
    Upright @elidable    # No need for > 0
    Italic               # No need for > 1
```

#### Flexible Substitution Rules
```dssketch
rules
    # Simple glyph substitution with labels
    dollar > dollar.heavy (weight >= Bold)

    # Wildcard patterns with labels
    A* > .alt (weight >= Bold)         # All glyphs starting with A
    * > .rvrn (weight >= Medium)       # All glyphs with .rvrn variants

    # Complex conditions with labels
    ampersand > .fancy (weight >= Bold && width <= Wide)
    g > g.alt (Regular <= weight <= Bold)  # Range conditions

    # Numeric conditions still work
    thin* > .ultra (weight >= -100)    # Negative coordinates supported
    b > b.alt (450 <= weight <= Bold)  # Mix labels and numbers
```

#### Explicit Axis Order Control
```dssketch
# Control instance generation order
axes
    wdth 60:100:200    # First in names: "Condensed Thin" - "{width} {weight}"
        Condensed > 350.0
        Normal > 560.0 @elidable
    wght 100:400:900   # Second in names
        Thin > 100
        Regular > 400
        Black > 900

sources [wght, wdth]   # Coordinates follow this order: [weight, width]
    Thin-Condensed [100, 350]
    Regular-Condensed [400, 350] @base
    Black-Condensed [900, 350]
    Thin-Normal [100, 560]
    Regular-Normal [400, 560]
    Black-Normal [900, 560]
```

#### Custom Axis
```dssketch
# Control instance generation order
axes
    CONTRAST CNTR 0:0:100 # First in names: "C2 Condensed Thin" - "{CNTR} {width} {weight}"
        0 C0 > 100.0 @elidable
        50 C1 > 600.0
        100 C2 > 900.0
    wdth 60:100:100
        Condensed > 350.0
        Normal > 560.0 @elidable
    wght 100:400:900   # Third in names
        Thin > 100
        Regular > 400
        Black > 900

sources [wght, wdth, CONTRAST]   # Coordinates follow this order: [weight, width, CONTRAST]
    Thin-Condensed-C2 [Thin, Condensed, C2]
    Regular-Condensed-C2 [Regular, Condensed, C2] @base
    Black-Condensed-C2 [Black, Condensed, C2]
```


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
        Thin > 100
        Regular > 400
        Black > 900
sources
    Thin [100]
    Regular [400] @base
    Black [900]
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
path path_to_sources

axes
    wght 300:400:700
        Light > 300
        Regular > 390 @elidable
        Bold > 700
    ital discrete
        Upright @elidable
        Italic

sources [wght, ital]
    Light [Light, 0]
    Regular [Regular, 0] @base
    Bold [Bold, 0]
    LightItalic [Light, 1]
    Italic [Regular, 1]
    BoldItalic [Bold, 1]

instances auto
```

### Complex Multi-Axis Font
```dssketch
family SuperFont
suffix VF

axes
    wght Thin:Regular:Black         # user space 100:400:900
        Thin > 0                    # 100
        Light > 196                 # 300
        Regular > 362 @elidable     # 400
        Medium > 477                # 500
        Bold > 732                  # 700
        Black > 1000                # 900
    wdth Condensed:Normal:Extended
        Condensed > 60
        Normal > 100 @elidable
        Extended > 200
    ital discrete
        Upright @elidable
        Italic

sources [wght, wdth, ital]
    Thin [Thin, Condensed, Upright]
    Regular [Regular, Condensed, Upright] @base
    Black [Black, Condensed, Upright]
    ThinItalic [Thin, Condensed, Italic]
    Italic [Regular, Condensed, Italic]
    BlackItalic [Black, Condensed, Italic]
    ThinExtended [Thin, Extended, Upright]
    RegularExtended [Regular, Extended, Upright]
    BlackExtended [Black, Extended, Upright]
    ThinExtendedItalic [Thin, Extended, Italic]
    ExtendedItalic [Regular, Extended, Italic]
    BlackExtendedItalic [Black, Extended, Italic]


rules
    # Currency symbols get heavy alternates
    dollar cent > .rvrn (weight >= Medium)

    # Wildcard patterns
    A* > .alt (weight >= Bold)      # All A-glyphs get alternates
    dollar cent at number > .fancy (weight >= 700 && width >= 150)  # Complex conditions

instances auto
```

### Advanced Rules and Patterns
```dssketch
family AdvancedFont

axes
    wght 100:400:900
    wdth 60:100:200
    CONTRAST CNTR 0:50:100  # Custom axis (uppercase)

sources [wght, wdth, CONTRAST]
    Light [100, 100, 0] @base
    Bold [900, 100, 100]

rules
    # Exact glyph substitution
    dollar > dollar.heavy (weight >= 500)

    # Multiple glyphs with same target
    dollar cent > .currency (weight >= 600)

    # Prefix wildcards (all glyphs starting with pattern)
    A* > .stylistic (weight >= 700)      # A, AE, Aacute, etc.
    num* > .proportional (CONTRAST >= 50)    # number variants

    # Universal wildcard (all glyphs with matching targets)
    S* G*  > .rvrn (weight >= Regular)         # Only creates rules where .rvrn exists
    Q* > .alt (weight >= 600 && width >= 150)  # Complex conditions

    # Range conditions
    o > o.round (Regular <= weight <= Bold)

    # Negative coordinates (supported in design space)
    ultra* > .thin (weight >= -100)
    back* > .forward (CONTRAST <= -25)

instances auto
```

## Key Concepts

### User Space vs Design Space
```
User Space = Values users see (CSS font-weight: 400) = OS/2 table
Design Space = Actual coordinates where sources are located

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
    wght 300:400:700
        Light > 0        # User 300 → Design 0
        Regular > 362    # User 400 → Design 362
        Bold > 1000      # User 700 → Design 1000

rules
    # This condition uses design space coordinate 362, not user space 400
    dollar > .heavy (weight >= 362)  # Activates at Regular and heavier
```

### Discrete Axes
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
The `instances auto` feature intelligently creates **all possible combinations** of axis labels using combinatorial logic (`itertools.product`):

```dssketch
axes
    ital discrete        # Controls name order: Italic first
        Upright @elidable
        Italic
    wght 100:400:900     # Weight second in names
        Thin > 100
        Regular > 400 @elidable
        Black > 900

instances auto  # Generates: "Thin", "Regular", "Black", "Italic Thin", "Italic", "Italic Black"
```

**How it works:**
1. **Combinatorial generation**: Creates cartesian product of all axis labels
   - Axis 1 (ital): `[Upright, Italic]` × Axis 2 (wght): `[Thin, Regular, Black]`
   - Result: 2 × 3 = **6 combinations**
2. **Elidable name cleanup**: Removes redundant `@elidable` labels
   - `Upright Thin` → `Thin`
   - `Upright Regular` → `Regular` (both parts elidable)
   - `Italic Regular` → `Italic` (Regular is elidable)
3. **Final instances**: `Thin`, `Regular`, `Black`, `Italic`, `Italic Thin`, `Italic Black`

**Axis order controls name sequence:**
```dssketch
# Order 1: Width first, then Weight
axes
    wdth 60:100:200
        Condensed > 60
        Normal > 100 @elidable
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900

# Result: "Condensed Thin", "Condensed Regular", "Condensed Black", "Thin", "Regular", "Black"

# Order 2: Weight first, then Width
axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900
    wdth 60:100:200
        Condensed > 60
        Normal > 100 @elidable

# Result: "Thin Condensed", "Regular Condensed", "Black Condensed", "Thin", "Regular", "Black"
```

**Complex multi-axis example:**
```dssketch
axes
    wdth 60:100:100
        Condensed > 60
        Normal > 100 @elidable
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
    ital discrete
        Upright @elidable
        Italic

instances auto
# Generates: 2 × 3 × 2 = 12 combinations
# Result: Thin, Regular, Black,
#         Condensed Thin, Condensed, Condensed Black,
#         Thin Italic, Italic, Black Italic,
#         Condensed Thin Italic, Condensed Italic, Condensed Black Italic
```

**Result**: Automatic generation of all meaningful style combinations with proper PostScript names, file paths, and style linking based on axes order.

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
for error in parser.validator.errors:
    print(f"ERROR: {error}")
for warning in parser.validator.warnings:
    print(f"WARNING: {warning}")
```

### Intelligent Typo Detection

DSSketch uses advanced **Levenshtein distance algorithm** to detect typos and suggest corrections, similar to how git, npm, and bash help users. Three severity levels ensure robust validation:

#### 1. CRITICAL - Duplicate Mapping Labels
Prevents labels used across multiple axes, which breaks instance generation:
```dssketch
axes
    wght 100:900
        Light > 100   # ❌ CRITICAL ERROR
    wdth 75:125
        Light > 75    # Same label "Light" in different axes!
```
**Error**: `CRITICAL: Mapping label 'Light' is used in multiple axes: 'weight' (wght), 'width' (wdth)`

#### 2. ERROR - Axis Tag Typos
Detects typos in standard axis tags:
```dssketch
axes
    wgth 100:900      # ❌ ERROR: Typo detected → suggests 'wght'
    widht 75:125      # ❌ ERROR: Typo detected → suggests 'wdth'

    # ✅ Human-readable names are VALID (automatically converted):
    weight 100:900    # ✅ OK: auto-converts to 'wght'
    width 75:125      # ✅ OK: auto-converts to 'wdth'
    italic discrete   # ✅ OK: auto-converts to 'ital'
```
**Detection**:
- Typos in 4-char lowercase tags: `wgth` → suggests `wght`, `widht` → suggests `wdth`
- **Human-readable names supported**: `weight`, `width`, `italic`, `slant`, `optical` → auto-converted to standard tags
- UPPERCASE tags treated as custom axes (not checked for typos)

#### 3. WARNING - Mapping Label Typos
Detects typos in standard weight/width mapping labels:
```dssketch
axes
    wght 100:400:900
        Lite > 300        # ⚠️ Warning: Lite → Light
        Reguler > 400     # ⚠️ Warning: Reguler → Regular
        Bol > 700         # ⚠️ Warning: Bol → Bold
```

**Smart Cross-Axis Logic**:
- **Only wght**: Allows both weight AND width labels (Light, Bold, Condensed, Wide)
- **Only wdth**: Allows both width AND weight labels (Condensed, Wide, Light, Bold)
- **Both wght and wdth**: Each axis restricted to its own standard labels

**How it works**:
- Uses **edit distance** with threshold of 2 characters
- Suggests closest standard label if typo detected
- Custom labels (distance > 2) are accepted without warnings

```bash
# Test typo detection
python -m pytest tests/test_typo_validation.py -v
```

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
