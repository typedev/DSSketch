import sys
pass  # run from the repo root with `uv run python`
import dssketch

dss = """
family TestDiscrete
path sources

axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
    GRAD grad discrete
        Off @elidable
        On

sources [wght, grad]
    Regular [400, 0] @base
    Bold [700, 0]
    RegularOn [400, 1]
    BoldOn [700, 1]

instances auto
"""

ds = dssketch.convert_dss_string_to_designspace(dss)
for axis in ds.axes:
    print(type(axis).__name__, axis.name, axis.tag, getattr(axis, "minimum", None), getattr(axis, "maximum", None), getattr(axis, "values", None))
