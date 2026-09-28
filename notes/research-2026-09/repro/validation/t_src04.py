import sys
pass  # run from the repo root with `uv run python`
from dssketch.parsers.dss_parser import DSSParser
from dssketch.converters.dss_to_designspace import DSSToDesignSpace

# Source way outside axis min/max, on an axis with NO mappings at all (custom axis)
dss = """
family OutOfRangeSource
path sources
axes
    ZROT 0:0:90
sources [ZROT]
    Base [0] @base
    Extreme [500]
instances off
"""
parser = DSSParser(strict_mode=False)
doc = parser.parse(dss)
print("warnings:", parser.validator.warnings)
print("errors:", parser.validator.errors)
conv = DSSToDesignSpace(base_path=".")
ds = conv.convert(doc)
for s in ds.sources:
    print(s.name, s.location)
print("axis min/max:", ds.axes[0].minimum, ds.axes[0].maximum)
