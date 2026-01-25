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
    A > A.alt (Regular <= weight <= Bold) "medium weight"

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

#### UFO Layer Support
Store multiple masters as layers within a single UFO file:
```dssketch
sources [wght]
    # Default layer (foreground) - base master
    Font-Master.ufo [400] @base

    # Intermediate masters stored as layers in same UFO
    Font-Master.ufo [500] @layer="wght500"
    Font-Master.ufo [600] @layer="wght600"
    Font-Master.ufo [700] @layer="bold-layer"

    # Separate UFO for extreme weight
    Font-Black.ufo [900]
```

**Benefits:**
- **Reduces file count**: Multiple masters in one UFO
- **Organized structure**: Related masters kept together
- **Full bidirectional support**: DesignSpace `layerName` ↔ DSSketch `@layer`

**Syntax formats:**
- `@layer="layer name"` - with double quotes (supports spaces)
- `@layer='layer name'` - with single quotes
- `@layer=layername` - without quotes (no spaces)

Can be combined with `@base`: `Font.ufo [400] @base @layer="default"`

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

### Installation

#### Using uv (recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install DSSketch
uv pip install dssketch

# Or install from source (for development)
uv pip install -e .

# Install with development dependencies
uv pip install -e ".[dev]"
```

#### Using pip
```bash
pip install dssketch

# Or install from source
pip install -e .
```

### Command Line
```bash
# Convert DesignSpace → DSSketch (with UFO validation)
dssketch font.designspace

# Convert DSSketch → DesignSpace
dssketch font.dssketch

# With explicit output
dssketch input.designspace -o output.dssketch

# Skip UFO validation (not recommended)
dssketch font.dssketch --no-validation

# avar2 format options
dssketch font.designspace --matrix    # Matrix format (default)
dssketch font.designspace --linear    # Linear format

# Without installation (using Python module directly)
python -m dssketch.cli font.designspace
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

# With options: vars_threshold (0=disabled, 3=default), avar2_format ("matrix"/"linear")
dssketch.convert_to_dss(ds, "MyFont.dssketch", vars_threshold=0)  # no variables
dssketch.convert_to_dss(ds, "MyFont.dssketch", avar2_format="linear")  # linear format

# Convert DSSketch file to DesignSpace object
ds = dssketch.convert_to_designspace("MyFont.dssketch")

# Convert DesignSpace to DSSketch string
dss_string = dssketch.convert_designspace_to_dss_string(ds)
dss_string = dssketch.convert_designspace_to_dss_string(ds, vars_threshold=2)  # more variables

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
    skip
        # Skip Light Italic (optional - removes unwanted combinations)
        Light Italic
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
    skip
        # Skip extreme combinations
        Thin Italic
        Extended Bold Italic
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

### Font with UFO Layers
```dssketch
# Using layers to store intermediate masters in single UFO files
# Reduces file count while maintaining full design flexibility

family FontWithLayers

axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Bold > 700
        Black > 900
    wdth 75:100:125
        Condensed > 75
        Normal > 100 @elidable
        Wide > 125

sources [wght, wdth]
    # Main master files (default layer)
    Font-Regular.ufo [400, 100] @base
    Font-Thin.ufo [100, 100]
    Font-Black.ufo [900, 100]

    # Width extremes
    Font-Condensed.ufo [400, 75]
    Font-Wide.ufo [400, 125]

    # Intermediate weight masters as layers in Font-Regular.ufo
    Font-Regular.ufo [300, 100] @layer="wght300"
    Font-Regular.ufo [500, 100] @layer="wght500"
    Font-Regular.ufo [600, 100] @layer="wght600"
    Font-Regular.ufo [700, 100] @layer="wght700"

    # Condensed intermediates as layers
    Font-Condensed.ufo [300, 75] @layer="wght300-condensed"
    Font-Condensed.ufo [700, 75] @layer="wght700-condensed"

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

### Axis Mapping Formats

DSSketch supports three formats for defining axis mappings, giving you full control over user-space and design-space coordinates:

#### 1. Standard Label (inferred user-space)
```dssketch
axes
    wght 100:400:900
        Light > 251     # Uses standard user-space value (300) → design-space value 251
        Regular > 398   # Uses standard user-space value (400) → design-space value 398
        Bold > 870      # Uses standard user-space value (700) → design-space value 870
```
**How it works**: For known labels (Light, Regular, Bold, etc.), user-space values are automatically taken from standard mappings in `data/unified-mappings.yaml`.

#### 2. Custom Label (design-space as user-space)
```dssketch
axes
    wght 100:400:900
        MyCustom > 500  # Custom label, user_value = design_value = 500
```
**How it works**: For unknown labels, user-space value equals design-space value.

#### 3. Explicit User-Space Mapping (full control)
```dssketch
axes
    wght 50:500:980
        50 UltraThin > 0       # Explicit: user=50, design=0
        200 Light > 230        # Override: user=200 instead of standard 300
        500 Regular > 420      # Override: user=500 instead of standard 400
        980 DeepBlack > 1000   # Custom: user=980, design=1000

    wdth 60:100:200
        Condensed > 380        # Standard: user=80 (from mappings)
        Normal > 560           # Standard: user=100 (from mappings)
        150 Wide > 700         # Override: user=150 instead of standard 100
        200 Extended > 1000    # Override: user=200 instead of standard 125

    CUSTOM CSTM 0:50:100
        0 Low > 0              # Custom axis: user=0, design=0
        50 Medium > 100        # Custom axis: user=50, design=100
        100 High > 200         # Custom axis: user=100, design=200
```

**Format**: `user_value label > design_value`

**Use cases**:
- **Create custom labels** with explicit user-space values for non-standard scales
- **Override standard mappings** with different user-space coordinates
- **Define custom axes** with meaningful user-space values
- **Fine-tune weight/width scales** beyond standard CSS values

**Example from `examples/MegaFont-3x5x7x3-Variable.dssketch`**:
```dssketch
axes
    wdth 60:100:200
        Compressed > 0
        Condensed > 380
        Normal > 560 @elidable
        150 Wide > 700         # user=150 (custom), design=700
        200 Extended > 1000    # user=200 (custom), design=1000
    wght Thin:Regular:Black
        Thin > 0
        200 Light > 230        # user=200 (override standard 300), design=230
        Regular > 420 @elidable
        Bold > 725
        Black > 1000
```

### Family Auto-Detection

The `family` field is optional in DSSketch. If not specified, DSSketch will automatically detect the family name from the base source UFO file:

```dssketch
# Family name is optional - will be detected from UFO
path sources

axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900

sources [wght]
    Thin [100]
    Regular [400] @base    # Family name detected from this UFO's font.info.familyName
    Black [900]

instances auto
```

**How it works:**
- When `family` is missing, DSSketch reads the base source UFO (`@base` flag)
- Extracts `font.info.familyName` from the UFO using fontParts
- Falls back to "Unknown" if UFO is not found or has no familyName
- Logs a warning if auto-detection is used (non-critical)

This is useful for quick prototyping or when the family name should always match the UFO metadata.

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

#### Fallback for Axes Without Labels

When axes have no mappings defined (only `min:def:max`), DSSketch automatically generates instances from the axis range values:

```dssketch
family QuickPrototype

axes
    wght 100:400:900    # No labels defined
    wdth 75:100:125     # No labels defined

instances auto
# Generates 9 instances (3 × 3):
# wght100 wdth75, wght100 wdth100, wght100 wdth125
# wght400 wdth75, wght400 wdth100, wght400 wdth125
# wght900 wdth75, wght900 wdth100, wght900 wdth125
```

**How fallback works:**
- Uses axis `minimum`, `default`, and `maximum` values as instance points
- Instance names use `tag+value` format (e.g., `wght400 wdth100`)
- Useful for quick prototyping without defining full axis mappings

This also works with avar2 fonts, where additional points from avar2 input mappings are included.

### Instance Skip Functionality

When using `instances auto`, you can exclude specific instance combinations with the `skip` subsection. This is useful for removing impractical or unwanted style combinations:

```dssketch
axes
    wdth 60:100:200
        Condensed > 60
        Normal > 100 @elidable
        Extended > 200
    wght 100:400:900
        Thin > 100
        Light > 300
        Regular > 400 @elidable
        Bold > 700
    ital discrete
        Upright @elidable
        Italic

instances auto
    skip
        # Skip extreme thin italic combinations (too fragile)
        Thin Italic
        Light Italic

        # Skip extremely wide and heavy combinations
        Extended Bold

# Without skip: 3 widths × 4 weights × 2 italics = 24 instances
# With 3 skipped: 24 - 3 = 21 instances
```

**Important rules for skip:**

1. **Use FINAL instance names** (after elidable cleanup):
   ```dssketch
   axes
       wdth 60:100:200
           Condensed > 60
           Normal > 100 @elidable
       wght 100:400:900
           Regular > 400 @elidable
           Bold > 700

   instances auto
       skip
           # ✅ CORRECT: Uses final name after "Normal" and "Regular" are removed
           Bold

           # ❌ WRONG: Would not match because "Normal Regular Bold" becomes "Bold"
           Normal Regular Bold
   ```

2. **Follow axis order** from axes section:
   ```dssketch
   # Axes order: wdth → wght → ital
   skip
       Condensed Thin Italic      # ✅ Correct: width → weight → italic
       Thin Condensed Italic      # ❌ Wrong: doesn't match axis order
   ```

3. **Comments supported**: Use `#` for inline comments explaining skip rules

**Example with multiple elidable labels:**
```dssketch
family MegaFont

axes
    CONTRAST CNTR 0:0:100
        NonContrast > 0 @elidable
        HighContrast > 100
    wdth 60:100:200
        Condensed > 60
        Normal > 100 @elidable
        Extended > 200
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Bold > 700

instances auto
    skip
        # "NonContrast Normal Thin" → "Thin" (after cleanup) - so we skip "Thin"
        Thin

        # "NonContrast Normal Regular" → "Regular" (after cleanup)
        Regular

        # "HighContrast Normal Thin" → "HighContrast Thin" (after cleanup)
        HighContrast Thin

        # "NonContrast Extended Thin" → "Extended Thin" (after cleanup)
        Extended Thin

# Generation process:
# 1. Create all combinations: 2 contrasts × 3 widths × 3 weights = 18 combinations
# 2. Apply elidable cleanup (remove NonContrast, Normal, Regular where appropriate)
# 3. Check skip rules on FINAL names
# 4. Generate remaining instances
```

**Production example from `examples/MegaFont-WithSkip.dssketch`:**
```dssketch
instances auto
    skip
        # Skip extreme thin weights with reverse slant (too fragile)
        Compressed Thin Reverse
        Condensed Thin Reverse
        Extended Thin Reverse

        # Skip low contrast with compressed thin (readability issues)
        LowContrast Compressed Thin
        LowContrast Compressed Thin Slant
        LowContrast Compressed Thin Reverse

        # Skip high contrast extended black (too heavy/wide)
        HighContrast Extended Black Slant
        HighContrast Extended Black Reverse

        # Skip middle-weight compressed (redundant)
        Compressed Medium Reverse
        Compressed Extrabold

# Result: 315 total combinations - 14 skipped = 301 instances generated
```

### Skip Rule Validation

DSSketch validates skip rules at **two levels** to ensure correctness and provide helpful feedback:

**1. ERROR Level - Invalid Label Detection**

Stops conversion if skip rules contain labels that don't exist in axis definitions:

```
# Example DSSketch with error:
axes
    wght 100:700
        Thin > 100
        Bold > 700
    ital discrete
        Upright
        Italic

instances auto
    skip
        Heavy Italic  # ERROR: "Heavy" not defined in any axis
```

**Error message:**
```
ERROR: Skip rule 'Heavy Italic' contains label 'Heavy' which is not defined in any axis.
Available labels: Bold, Italic, Thin, Upright
```

**2. WARNING Level - Unused Skip Rule Detection**

Logs warnings for skip rules that never match any generated instance (may indicate typo or elidable cleanup):

```
# Example DSSketch with warning:
axes
    wght 100:700
        Thin > 100
        Bold > 700
    ital discrete
        Upright @elidable
        Italic

instances auto
    skip
        Bold Upright  # WARNING: "Upright" is @elidable, so "Bold Upright" becomes just "Bold"
```

**Warning message:**
```
WARNING: Skip validation: 1 skip rule(s) were never used. This may indicate a typo or that elidable cleanup changed the instance names.
  - Unused skip rule: 'Bold Upright'
```

**Label Naming Rules:**

Labels cannot contain spaces. Use camelCase for compound names:

```
# ✅ CORRECT - camelCase labels
axes
    wght 100:900
        ExtraLight > 100    # camelCase, no spaces
        SemiBold > 900      # camelCase, no spaces

instances auto
    skip
        ExtraLight Italic   # Two labels: "ExtraLight" + "Italic"

# ❌ INCORRECT - spaces in labels
axes
    wght 100:900
        Extra Light > 100   # ERROR: spaces not allowed
        Semi Bold > 900     # ERROR: spaces not allowed
```

This matches standard font naming conventions (ExtraLight, SemiBold) from `data/unified-mappings.yaml`.

**Benefits:**
- **Catches typos**: Detects misspelled labels before they cause silent failures
- **Identifies unreachable rules**: Warns about skip rules affected by elidable cleanup
- **Clear error messages**: Shows available labels for easy correction
- **Simple and predictable**: Each space separates labels, no ambiguity
- **Production-ready**: All validation tested on large MegaFont example (15 skip rules)

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

### Disabling Instance Generation (`instances off`)

When you want to completely disable automatic instance generation (e.g., for avar2 fonts where instances are not needed or should be managed externally):

```dssketch
family MyFont

axes
    wght 100:400:900
    wdth 75:100:125

instances off
```

This produces a DesignSpace file with zero instances, which is useful for:
- **avar2 variable fonts** where instances may be generated differently
- **Build pipelines** that generate instances externally
- **Testing** axis configurations without instance overhead

### avar2 Support (OpenType 1.9)

DSSketch provides comprehensive support for avar2 (axis variations version 2), enabling non-linear axis mappings and inter-axis dependencies. This is essential for sophisticated variable fonts like parametric fonts.

#### User Space vs Design Space in avar2

**Critical concept**: avar2 mappings have a clean separation between spaces:

- **Input** (`[axis=value]`): Always **USER space** — the CSS values that applications request
- **Output** (`axis=value`): Always **DESIGN space** — the internal font coordinates

**Labels always mean user space:**

```dssketch
axes
    wght 100:400:900
        Regular > 435     # Axis mapping: user=400 → design=435 (default)
    wdth 75:100:125
        Condensed > 75
        Normal > 100

avar2
    # Input uses USER space: Regular=400, Condensed=80 (CSS standard)
    # Output uses DESIGN space: wght=385
    [wght=Regular, wdth=Condensed] > wght=385
```

**Interpretation:**
- When user requests Regular and Condensed
- The font will use design coordinate 385 instead of the default 435
- This allows the font to optically compensate for the condensed width

**The axis mapping `Regular > 435` defines the DEFAULT design value.** avar2 can OVERRIDE it for specific axis combinations.

#### Basic avar2 Syntax

**Mapping structure: `[input] > output`**

- **Input**: `[axis=value]` — USER space coordinate (what CSS/apps request)
- **Output**: `axis=value` — DESIGN space value (internal font coordinate)

**Example 1: Non-linear weight curve** (from `examples/avar2.dssketch`)

```dssketch
axes
    wght 1:400:1000 "Weight"
    wdth 50:100:150 "Width"

avar2 matrix
    outputs      wght  wdth
    [wght=100]   300   -      # user asks wght=100 → font uses wght=300
    [wght=400]   $     -      # user asks wght=400 → font uses default (400)
    [wght=700]   600   -      # user asks wght=700 → font uses wght=600
    [wdth=75]    -     90     # user asks wdth=75  → font uses wdth=90
    [wdth=100]   -     $      # user asks wdth=100 → font uses default (100)
```

Here `-` means "no change for this axis", `$` means "use axis default".

**Example 2: Optical size affects weight and width** (from `examples/avar2OpticalSize.dssketch`)

```dssketch
axes
    wght 1:400:1000 "Weight"
    wdth 50:100:150 "Width"
    opsz 6:16:144 "Optical size"

avar2 matrix
    outputs                         wght  wdth
    [opsz=6, wght=400, wdth=100]    600   125   # small text: heavier, wider
    [opsz=144, wght=400, wdth=100]  200   75    # large display: lighter, narrower
```

At small sizes (opsz=6), text needs more weight to be readable. At large sizes (opsz=144), less weight looks better.

**Example 3: Hidden parametric axes** (from `examples/avar2QuadraticRotation.dssketch`)

```dssketch
axes
    ZROT 0:0:90 "Rotation"

axes hidden
    AAAA 0:0:90
    BBBB 0:0:90

avar2 matrix
    outputs    AAAA  BBBB
    [ZROT=0]   $     $      # at rotation=0: use defaults
    [ZROT=90]  90    90     # at rotation=90: set both to 90
```

User controls `ZROT`, font internally adjusts hidden axes `AAAA` and `BBBB`.

**Example 4: Cross-axis dependency with labels**

```dssketch
axes
    wght 100:400:900
        Light > 300
        Regular > 435      # user=400 → design=435 (default)
        Bold > 700
    wdth 75:100:125
        Condensed > 75
        Normal > 100
        Wide > 125

sources [wght, wdth]
    Regular-Normal [Regular, Normal] @base
    Bold [Bold, Normal]
    .....

avar2
    # Labels resolve to USER space: Regular=400, Condensed=80
    # Output is DESIGN space
    [wght=Regular, wdth=Condensed] > wght=385
    [wght=Bold, wdth=Condensed] > wght=650
```

**What this means:**
- `Regular > 435` defines the DEFAULT design value for Regular weight
- At Condensed width, Regular needs a lighter design value (385) for optical balance
- The label `Regular` always means user=400 everywhere in DSSketch
- The converter automatically translates user→design for DesignSpace XML

**Sources for avar2 fonts** — use `AXIS=value` format (from `examples/avar2-RobotoDelta-Roman.dssketch`):

```dssketch
sources
    Roboto-Regular opsz=0 @base
    Roboto-GRAD-250 opsz=0, GRAD=-250
    Roboto-GRAD150 opsz=0, GRAD=150
    Roboto-VROT13 opsz=0, VANG=13, VROT=13
    Roboto-XTUC741-wght100 opsz=1, wght=100, wdth=151, XTUC=741
```

Format: `SourceName AXIS=value, AXIS=value, ...` — list only axes that differ from defaults. Values are **design-space** coordinates (same as in DesignSpace XML `xvalue`).

**Variables (`avar2 vars`)** — define reusable values (from `examples/avar2Fences.dssketch`)

```dssketch
avar2 vars
    $wght1 = 600           # define variable

avar2 matrix
    outputs                  wght    wdth
    [wght=1000, wdth=50]     $wght1  50     # use variable (= 600)
    [wght=1000, wdth=90]     $wght1  90     # same value reused
    [wght=600, wdth=50]      $wght1  50
    [wght=600, wdth=90]      $wght1  90
```

Variables start with `$`, useful when same value appears many times.

#### Linear vs Matrix Format

**Linear format** — one mapping per line:
```dssketch
avar2
    [wght=100] > wght=300
    [wght=700] > wght=600

    # With optional description name:
    "opsz144_wght1000" [opsz=144, wght=1000] > XOUC=244, XOLC=234
```

**Matrix format** — tabular, better for multiple output axes:
```dssketch
avar2 matrix
    outputs      wght  wdth
    [wght=100]   300   -
    [wght=700]   600   -
```

**Complex matrix** (from `examples/avar2-RobotoDelta-Roman.dssketch`):
```dssketch
avar2 matrix
    outputs                                       XOPQ  XOUC  XOLC  XTUC  YOPQ  YOUC
    [opsz=-1, wght=100, wdth=25, slnt=0, GRAD=0]  50    50    50    451   48    48
    [opsz=-1, wght=400, wdth=25, slnt=0, GRAD=0]  100   100   100   430   85    85
    [opsz=-1, wght=1000, wdth=25, slnt=0, GRAD=0] 150   150   150   400   105   105
    [opsz=0, wght=100, wdth=100, slnt=0, GRAD=0]  47    47    47    516   44    44
    [opsz=0, wght=400, wdth=100, slnt=0]          $     $     $     $     $     $
    [opsz=1, wght=100, wdth=25, slnt=0, GRAD=0]   2     2     2     278   2     2
```

Each row: `[input conditions]` → values for all output columns. `$` = axis default, `-` = no output.

Both formats produce identical results. Matrix is default for output, linear is easier to read for simple cases.

#### CLI Options for avar2

```bash
# Format options
dssketch font.designspace --matrix    # matrix format (default)
dssketch font.designspace --linear    # linear format

# Variable generation options
dssketch font.designspace             # auto-generate vars (threshold=3, default)
dssketch font.designspace --novars    # disable variable generation
dssketch font.designspace --vars 2    # threshold=2 (more variables)
dssketch font.designspace --vars 5    # threshold=5 (fewer variables)
```

**Variable generation**: Values appearing N+ times become variables (`$var1`, `$var2`, etc.)

#### Instances with avar2

For avar2 fonts, `instances off` is often the better choice:

```dssketch
instances off   # recommended for most avar2 fonts
```

**Why?** avar2 fonts often have complex axis interactions where automatic instance generation produces too many or inappropriate combinations. Use `instances auto` only when you understand which combinations make sense.

When using `instances auto` with avar2 fonts that have axes without labels, DSSketch automatically generates instance points from:

1. Axis min, default, and max values
2. Unique input points from avar2 mappings

```dssketch
axes
    wght 1:400:1000  # No labels defined
    opsz 6:16:144    # No labels defined

avar2
    [wght=100] > wght=300
    [wght=700] > wght=600
    [opsz=144] > wght=200

instances auto
# Generates instances at: wght=[1, 100, 400, 700, 1000] × opsz=[6, 16, 144]
# Instance names: wght1 opsz6, wght100 opsz6, wght400 opsz16, etc.
```

**Hidden axes are excluded** from instance generation - only user-facing axes contribute to instance combinations.

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
# After pip install -e . (recommended):
dssketch-data info                              # Show data file locations
dssketch-data copy unified-mappings.yaml        # Copy default file for editing
dssketch-data edit                              # Open user data directory
dssketch-data reset --file unified-mappings.yaml # Reset specific file
dssketch-data reset --all                       # Reset all files

# Without installation (using Python module directly):
python -m dssketch.data_cli info
python -m dssketch.data_cli copy unified-mappings.yaml
python -m dssketch.data_cli edit
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
# Test with provided examples (after pip install -e .)
dssketch examples/SuperFont-6x2.designspace
dssketch examples/MegaFont-3x5x7x3-Variable.dssketch

# Or without installation
python -m dssketch.cli examples/SuperFont-6x2.designspace

# Run validation tests
python -m pytest tests/test_parser_validation.py -v

# Test specific validation features
python -m pytest tests/test_parser_validation.py::TestParserValidation::test_keyword_typo_detection -v
```

## Examples

The `examples/` directory contains:
- `examples/MegaFont-3x5x7x3-Variable.designspace` → Complex multi-axis font
- `examples/SuperFont-6x2.dssketch` → Equivalent DSSketch format (93% smaller)
- `examples/FontWithLayers.dssketch` → UFO layer support demo
- Various avar2 examples (`avar2*.dssketch`) → OpenType 1.9 axis variations
- Various test files showing edge cases and features

---

**DSSketch makes variable font development human-friendly. Simple syntax, powerful features, dramatic size reduction.**

## Author & Credits

**DSSketch** was developed by **Alexander Lubovenko** in collaboration with **Claude (Anthropic AI)**.

This project represents a collaborative effort combining human expertise in font design and engineering with AI-assisted development to create more accessible and efficient tooling for the variable font community.

## License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Alexander Lubovenko
