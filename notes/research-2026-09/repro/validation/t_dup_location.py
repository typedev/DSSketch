import sys
pass  # run from the repo root with `uv run python`
import dssketch

# Two DIFFERENT sources (not @base) sharing the exact same non-default design location
dss = """
family DupLocation
path sources
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    Regular [400] @base
    Thin [100]
    BlackA [900]
    BlackB [900]
instances off
"""
ds = dssketch.convert_dss_string_to_designspace(dss)
for s in ds.sources:
    print(s.name, s.location)
