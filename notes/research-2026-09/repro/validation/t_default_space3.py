import sys
pass  # run from the repo root with `uv run python`
from dssketch.parsers.dss_parser import DSSParser

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
parser = DSSParser(strict_mode=False)
doc = parser.parse(dss)
for s in doc.sources:
    print(s.name, s.location)
print("--- warnings ---")
for w in parser.validator.warnings:
    print("WARN:", w)
print("--- errors ---")
for e in parser.validator.errors:
    print("ERR:", e)
