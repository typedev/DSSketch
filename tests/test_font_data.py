"""Font data from the host: FontDataProvider (fontdata.py, 1.5.x)."""

from pathlib import Path

import dssketch
from dssketch import DefconFontData, FontData, Sketch, codes, complete, diagnose, expand_rule
from dssketch.core.models import DSSRule
from dssketch.syntax import GLYPH, TEXT

EXAMPLES = Path(__file__).parent.parent / "examples"

SKETCH = """\
path masters
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    T-Thin [Thin]
    T-Regular [Regular] @base
    T-Black [Black] @layer=heavy
rules
    dollar > dollar.alt (weight >= Black) "dollar"
    a* > .ss01 (weight >= Black) "a alternates"
instances off
"""


class Host(FontData):
    """Fonts open in a host application, keyed by source path"""

    def __init__(self, fonts, family="Hosted"):
        self.fonts = fonts
        self.family = family
        self.calls = []

    def family_name(self):
        return self.family

    def style_name(self, source):
        self.calls.append(("style_name", source))
        font = self.fonts.get(source)
        return font["style"] if font else None

    def glyph_names(self, source):
        self.calls.append(("glyph_names", source))
        font = self.fonts.get(source)
        return font["glyphs"] if font else None

    def layer_names(self, source):
        font = self.fonts.get(source)
        return font["layers"] if font else None

    def source_exists(self, source):
        return source in self.fonts


GLYPHS = ["a", "a.ss01", "aacute", "b", "dollar", "dollar.alt"]
FONTS = {
    "masters/T-Thin.ufo": {"style": "Thin", "glyphs": GLYPHS, "layers": ["public.default"]},
    "masters/T-Regular.ufo": {"style": "Regular", "glyphs": GLYPHS, "layers": ["public.default"]},
    "masters/T-Black.ufo": {"style": "Black", "glyphs": GLYPHS, "layers": ["public.default", "heavy"]},
}


def codes_of(diagnostics):
    return {codes.lookup(d.code).name for d in diagnostics}


# -- conversion ---------------------------------------------------------------


def test_conversion_uses_the_hosts_fonts():
    host = Host(FONTS)
    ds = dssketch.convert_dss_string_to_designspace(SKETCH, font_data=host)
    assert ds.sources[0].familyName == "Hosted"  # no family line: the host's
    assert [s.styleName for s in ds.sources] == ["Thin", "Regular", "Black"]
    rules = {r.name: r.subs for r in ds.rules}
    assert rules["dollar"] == [("dollar", "dollar.alt")]
    assert rules["a alternates"] == [("a", "a.ss01")]  # aacute.ss01 does not exist
    assert ("glyph_names", "masters/T-Regular.ufo") in host.calls


def test_unknown_font_data_falls_back_quietly():
    ds = dssketch.convert_dss_string_to_designspace(SKETCH.replace("path masters\n", "family T\n"), font_data=FontData())
    assert [s.styleName for s in ds.sources] == ["T-Thin", "T-Regular", "T-Black"]
    assert ds.sources[0].familyName == "T"


def test_a_provider_that_raises_does_not_break_conversion():
    class Broken(FontData):
        def glyph_names(self, source):
            raise RuntimeError("host bug")

    dssketch.convert_dss_string_to_designspace("family T\n" + SKETCH, font_data=Broken())


def test_default_reads_ufos_with_defcon():
    path = EXAMPLES / "MegaFont-WithSkip.dssketch"
    provider = DefconFontData(path.parent)
    doc = dssketch.DSSParser(strict_mode=False).parse(path.read_text(encoding="utf-8"))
    source = dssketch.fontdata.source_path(doc, doc.sources[0])
    assert provider.source_exists(source)
    assert provider.glyph_names(source) and provider.style_name(source)
    assert provider.layer_names(source)
    assert provider.source_exists("nope/X.ufo") is False and provider.glyph_names("nope/X.ufo") is None


def test_explicit_provider_matches_the_default():
    path = EXAMPLES / "MegaFont-WithSkip.dssketch"
    default = dssketch.convert_to_designspace(str(path))
    explicit = dssketch.convert_to_designspace(str(path), font_data=DefconFontData(path.parent))
    assert [r.subs for r in explicit.rules] == [r.subs for r in default.rules]
    assert [s.styleName for s in explicit.sources] == [s.styleName for s in default.sources]


# -- expand_rule --------------------------------------------------------------


def test_expand_rule():
    rule = DSSRule("r", [], [], pattern="a* dollar zz", to_pattern=".ss01")
    assert expand_rule(rule, GLYPHS) == [
        ("a", "a.ss01", True),
        ("aacute", "aacute.ss01", False),
        ("dollar", "dollar.ss01", False),
        ("zz", "zz.ss01", False),  # a plain name is listed even if absent
    ]
    replace = DSSRule("r", [], [], pattern="dollar", to_pattern="dollar.alt")
    assert expand_rule(replace, GLYPHS) == [("dollar", "dollar.alt", True)]
    legacy = DSSRule("r", [("b", "b.alt")], [])
    assert expand_rule(legacy, GLYPHS) == [("b", "b.alt", False)]


# -- diagnose -----------------------------------------------------------------


def test_diagnose_reads_nothing_without_a_provider():
    assert not {"SOURCE_UFO_MISSING", "RULE_TARGET_MISSING"} & codes_of(diagnose(SKETCH))


def test_diagnose_with_a_clean_host_adds_nothing():
    assert codes_of(diagnose(SKETCH, font_data=Host(FONTS))) == codes_of(diagnose(SKETCH))


def test_missing_ufo_and_layer():
    fonts = dict(FONTS)
    del fonts["masters/T-Thin.ufo"]
    fonts["masters/T-Black.ufo"] = dict(fonts["masters/T-Black.ufo"], layers=["public.default"])
    found = {codes.lookup(d.code).name: d for d in diagnose(SKETCH, font_data=Host(fonts))}
    assert found["SOURCE_UFO_MISSING"].line == 8
    assert found["SOURCE_LAYER_MISSING"].line == 10
    assert "'heavy'" in found["SOURCE_LAYER_MISSING"].message


def test_rule_glyph_checks():
    text = SKETCH.replace("dollar > dollar.alt", "euro > euro.alt").replace("a* > .ss01", "q* > .ss01")
    found = [d for d in diagnose(text, font_data=Host(FONTS)) if d.line in (12, 13)]
    names = {codes.lookup(d.code).name for d in found}
    assert names == {"RULE_GLYPH_MISSING", "RULE_TARGET_MISSING", "RULE_MATCHES_NOTHING"}
    glyph = next(d for d in found if codes.lookup(d.code).name == "RULE_GLYPH_MISSING")
    assert text.split("\n")[11][glyph.column: glyph.end_column] == "euro"


def test_sketch_carries_font_data_through_edits():
    host = Host(FONTS)
    sk = Sketch.parse(SKETCH, font_data=host)
    result = sk.set_source_coordinate("T-Black", "wght", 400)
    assert result.sketch.font_data is host


# -- complete -----------------------------------------------------------------


def test_glyph_completion_in_rules():
    text = SKETCH.replace("    dollar > dollar.alt", "    dol > dollar.alt")
    found = complete(text, 12, 7, font_data=Host(FONTS))
    assert [(c.text, c.type) for c in found] == [("dollar", GLYPH), ("dollar.alt", GLYPH)]
    assert complete(text, 12, 7) == []  # no provider, no glyph names
    target = complete(SKETCH, 12, 16, font_data=Host(FONTS))
    assert [c.text for c in target] == ["dollar", "dollar.alt"] and target[0].detail == "target glyph"


def test_layer_completion():
    for line in ("    T-Black [Black] @layer=h", '    T-Black [Black] @layer="h', "    T-Black [Black] @layer h"):
        text = SKETCH.replace("    T-Black [Black] @layer=heavy", line)
        found = complete(text, 10, len(line), font_data=Host(FONTS))
        assert [(c.text, c.type) for c in found] == [("heavy", TEXT)], line
