import sys
sys.path.insert(0, "site-packages")
from fontTools.varLib.featureVars import _checkSubstitutionGlyphsExist

# base master glyph order (Regular.ufo) - lacks the .rvrn glyphs
base_master_glyphs = {"dollar", "cent", "a", "b", ".notdef"}

substitutions = [("dollar", "dollar.rvrn"), ("cent", "cent.rvrn")]
try:
    _checkSubstitutionGlyphsExist(glyphNames=base_master_glyphs, substitutions=[({}, dict(substitutions))])
    print("NO ERROR (unexpected)")
except Exception as e:
    print(f"{type(e).__name__}: {e}")
