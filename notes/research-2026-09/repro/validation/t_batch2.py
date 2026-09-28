import sys
pass  # run from the repo root with `uv run python`
import dssketch
from dssketch.parsers.dss_parser import DSSParser

def try_parse(name, content, strict=True):
    print(f"--- {name} ---")
    try:
        parser = DSSParser(strict_mode=strict)
        doc = parser.parse(content)
        print("OK, no exception.")
        if not strict:
            print(" warnings:", parser.validator.warnings)
            print(" errors:", parser.validator.errors)
        return doc
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        return None

# LABEL-03 analog: duplicate label same axis, different user_value
try_parse("dup-label-same-axis", """
family DupLabelSameAxis
path sources
axes
    wght 100:400:900
        Thin > 100
        Regular > 300
        Regular > 400 @elidable
        Black > 900
sources [wght]
    Thin [100]
    Regular [400] @base
    Black [900]
instances off
""")

# AXIS-07 analog: duplicate custom axis tags
d = try_parse("dup-custom-tag", """
family DupTag
path sources
axes
    CONTRAST CNTR 0:0:100
        0 Low > 0
        100 High > 100
    SATURATION CNTR 0:0:50
        0 Dull > 0
        50 Vivid > 50
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
sources [CNTR, CNTR, wght]
    Regular [0, 0, 400] @base
    Bold [100, 50, 700]
instances off
""", strict=False)
if d:
    for a in d.axes:
        print(" axis:", a.name, a.tag)

# AXIS-09/10 analog: reversed label-based range
try_parse("reversed-label-range", """
family ReversedLabelRange
path sources
axes
    wght Black:Regular:Thin
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    Thin [100]
    Regular [400] @base
    Black [900]
instances off
""", strict=False)
