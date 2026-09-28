import sys
pass  # run from the repo root with `uv run python`
from dssketch.parsers.dss_parser import DSSParser
from dssketch.converters.dss_to_designspace import DSSToDesignSpace

dss = """
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
"""
parser = DSSParser(strict_mode=False)
doc = parser.parse(dss)
conv = DSSToDesignSpace(base_path=".")
ds = conv.convert(doc)
axis = ds.axes[0]
print("minimum:", axis.minimum, "default:", axis.default, "maximum:", axis.maximum)
