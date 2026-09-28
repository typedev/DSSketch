import sys
pass  # run from the repo root with `uv run python`
import dssketch

dss = """
family DupUserValue
path sources

axes
    wght 100:400:900
        Thin > 100
        300 LightA > 250
        300 LightB > 350
        Regular > 400 @elidable
        Black > 900

sources [wght]
    Thin [100]
    Regular [400] @base
    Black [900]

instances auto
"""

ds = dssketch.convert_dss_string_to_designspace(dss)
axis = ds.axes[0]
print("map:", axis.map)
print("labels:", [(l.name, l.userValue) for l in axis.axisLabels])

print("---instances---")
for i in ds.instances:
    print(i.styleName, i.location)

fw = dict(axis.map)
print("forward map dict (last wins):", fw)
