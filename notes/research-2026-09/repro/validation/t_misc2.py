import sys
pass  # run from the repo root with `uv run python`
import dssketch

dss2 = """
family InvertedRule
path sources
axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
sources [wght]
    Regular [400] @base
    Bold [700]
rules
    a > a.alt (700 <= weight <= 400) "inverted"
instances off
"""
try:
    ds = dssketch.convert_dss_string_to_designspace(dss2, base_path=".")
    for r in ds.rules:
        print("TEST2 rule conditionSets:", r.conditionSets)
except Exception as e:
    print(f"TEST2 inverted rule: {type(e).__name__}: {e}")

print()

dss3 = """
family MissingGlyphRule
path sources
axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
sources [wght]
    Regular [400] @base
    Bold [700]
rules
    zzz_nonexistent > zzz_nonexistent.alt (weight >= Bold) "bad rule"
instances off
"""
try:
    ds = dssketch.convert_dss_string_to_designspace(dss3, base_path=".")
    print("TEST3 num rules:", len(ds.rules))
    for r in ds.rules:
        print("TEST3 rule subs:", r.subs)
except Exception as e:
    print(f"TEST3: {type(e).__name__}: {e}")
