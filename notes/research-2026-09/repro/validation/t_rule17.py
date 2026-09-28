import sys
pass  # run from the repo root with `uv run python`
import dssketch

dss = """
family RuleTest
path sources

axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700

sources [wght]
    Regular [400] @base
    Bold [700]
    Bold-sparse [700] @sparse

rules
    * > .rvrn (weight >= Bold) "heavy alternates"

instances auto
"""

ds = dssketch.convert_dss_string_to_designspace(dss, base_path=".")
for rule in ds.rules:
    print(rule.name, rule.subs)
ds.write("rule17_test.designspace")
