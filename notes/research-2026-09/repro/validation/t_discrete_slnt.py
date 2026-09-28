import sys
pass  # run from the repo root with `uv run python`
import dssketch

dss = """
family TestDiscreteSlant
path sources

axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
    slant slnt discrete
        Upright @elidable
        Slanted

sources [wght, slnt]
    Regular [400, 0] @base
    Bold [700, 0]
    RegularSlanted [400, 1]
    BoldSlanted [700, 1]

instances auto
"""

ds = dssketch.convert_dss_string_to_designspace(dss)
for axis in ds.axes:
    print(type(axis).__name__, axis.name, axis.tag, getattr(axis, "minimum", None), getattr(axis, "maximum", None), getattr(axis, "values", None))
print("num instances:", len(ds.instances))
for i in ds.instances:
    print(" ", i.styleName, i.location)
