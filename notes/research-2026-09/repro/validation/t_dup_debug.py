import sys
pass  # run from the repo root with `uv run python`
import dssketch
from dssketch.core.instances import getInstancesMapping, sortAxisOrder
from dssketch.parsers.dss_parser import DSSParser
from dssketch.converters.dss_to_designspace import DSSToDesignSpace

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

instances off
"""
parser = DSSParser(strict_mode=True)
dss_doc = parser.parse(dss)
conv = DSSToDesignSpace(base_path=".")
ds = conv.convert(dss_doc)
axisOrder = sortAxisOrder(ds, dss_doc)
mp = getInstancesMapping(ds, axisOrder[0], dss_doc=dss_doc)
print("axisLabels dict:", mp["axisLabels"])
print("reverseMap:", mp["reverseMap"])
