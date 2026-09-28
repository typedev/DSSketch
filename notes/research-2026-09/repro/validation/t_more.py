import sys
pass  # run from the repo root with `uv run python`
import dssketch
from dssketch.parsers.dss_parser import DSSParser

# Test A: explicit (non-auto) instance line - is it silently dropped?
dssA = """
family ExplicitInstanceTest
path sources
axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
sources [wght]
    Regular [400] @base
    Bold [700]
instances
    MyCustomInstance familyname=ExplicitInstanceTest stylename=MyCustomInstance [550]
"""
parser = DSSParser(strict_mode=False)
doc = parser.parse(dssA)
print("TEST A explicit instance count in DSSDocument:", len(doc.instances))
ds = dssketch.convert_dss_string_to_designspace(dssA)
print("TEST A DesignSpace instance count:", len(ds.instances))
print("warnings:", parser.validator.warnings)
print()

# Test B: weightless axes (width + italic only), both elidable -> empty style name risk
dssB = """
family WeightlessTest
path sources
axes
    width wdth 75:100:100
        Condensed > 75
        Normal > 100 @elidable
    ital discrete
        Upright @elidable
        Italic

sources [wdth, ital]
    Normal [100, 0] @base
    Condensed [75, 0]
    NormalItalic [100, 1]
    CondensedItalic [75, 1]

instances auto
"""
ds2 = dssketch.convert_dss_string_to_designspace(dssB)
print("TEST B instances:")
for i in ds2.instances:
    print(f"  styleName='{i.styleName}' location={i.location} psname={i.postScriptFontName}")
