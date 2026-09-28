import sys
pass  # run from the repo root with `uv run python`
import dssketch

# wght axis: user default 400 maps to DESIGN value 420 (non-identity map at default)
dss = """
family DefaultSpaceBug
path sources

axes
    wght Thin:Regular:Black
        Thin > 0
        Regular > 420 @elidable
        Black > 1000

sources [wght]
    Regular @base
    Black [1000]
    Thin [0]

instances off
"""

ds = dssketch.convert_dss_string_to_designspace(dss)
axis = ds.axes[0]
print("axis min/default/max (user space):", axis.minimum, axis.default, axis.maximum)
print("axis map (user->design):", axis.map)
for s in ds.sources:
    print("source:", s.name, s.location, "copyLib=", s.copyLib)
