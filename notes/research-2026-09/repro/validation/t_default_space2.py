import sys
pass  # run from the repo root with `uv run python`
import dssketch

dss = """
family DefaultSpaceBug2
path sources

axes
    wght Thin:Regular:Black
        Thin > 0
        Regular > 420 @elidable
        Black > 1000
    ital discrete
        Upright @elidable
        Italic

sources [wght, ital]
    Regular [420, 0] @base
    Black [1000, 0]
    Thin [0, 0]
    RegularItalic ital=1

instances off
"""

ds = dssketch.convert_dss_string_to_designspace(dss)
for s in ds.sources:
    print("source:", s.name, s.location)
