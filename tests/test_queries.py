"""What a sketch means, in numbers (queries.py, 1.5.1)."""

from pathlib import Path

import pytest

import dssketch
from dssketch import DefconFontData, FontData, Sketch, SourceKey

EXAMPLES = Path(__file__).parent.parent / "examples"
AUTO_EXAMPLES = [
    p.name for p in sorted(EXAMPLES.glob("*.dssketch"))
    if "instances auto" in p.read_text(encoding="utf-8")
]

SKETCH = """\
family Q
axes
    wght 100:400:900 "Weight"
        Thin > 100
        Regular > 420 @elidable
        700 Bold > 600
        Black > 900
    ital discrete
        Upright @elidable
        Italic
sources [wght, ital]
    Q-Thin [Thin, Upright]
    Q-Regular [Regular, Upright] @base
    Q-Black [Black, Upright]
    Q-Italic [Regular, Italic] @base
    Q-Mid [500, Upright] @layer=mid
rules
    dollar > dollar.alt (weight >= Bold) "dollar"
    a* > .ss01 (450 <= weight <= Bold) "a"
    dollar.alt > dollar.alt2 (italic == 1) "chained"
instances auto
    skip
        Thin Italic
"""


@pytest.fixture
def sk():
    return Sketch.parse(SKETCH)


# -- axes -------------------------------------------------------------------------


def test_axis_maps(sk):
    assert sk.user_to_design("Weight", 700) == 600
    assert sk.user_to_design("wght", 550) == pytest.approx(510)  # between Regular and Bold
    assert sk.user_to_design("weight", "Bold") == 600
    assert sk.design_to_user("wght", 600) == 700
    assert sk.design_to_user("Weight", "Bold") == 700
    assert sk.user_to_design("ital", "Italic") == 1


def test_axis_queries_never_raise(sk):
    assert sk.user_to_design("wdth", 100) is None
    assert sk.user_to_design("wght", "Bolt") is None
    assert sk.user_to_design("wght", None) is None
    assert sk.user_to_design(None, 1) is None
    assert dssketch.user_to_design("not a sketch at all", "wght", 1) is None


# -- sources ----------------------------------------------------------------------


def test_source_locations(sk):
    found = {s.key: s for s in sk.source_locations()}
    black = found[SourceKey("Q-Black.ufo")]
    assert black.user_location == {"Weight": 900, "italic": 0}
    assert black.design_location == {"Weight": 900, "italic": 0}
    mid = found[SourceKey("Q-Mid.ufo", "mid")]
    assert mid.design_location["Weight"] == 500 and mid.user_location["Weight"] == pytest.approx(400 + 80 / 180 * 300)
    assert [s.is_base for s in sk.source_locations()] == [False, True, False, True, False]
    assert found[SourceKey("Q-Italic.ufo")].line == 15


def test_source_locations_keyed_like_the_designspace():
    path = EXAMPLES / "MegaFont-WithSkip.dssketch"
    ds = dssketch.convert_to_designspace(str(path))
    found = Sketch.parse(path.read_text(encoding="utf-8")).source_locations()
    assert [s.design_location for s in found] == [dict(s.location) for s in ds.sources]


# -- rules ------------------------------------------------------------------------


def test_rule_regions(sk):
    regions = sk.rule_regions()
    assert [(r.index, r.name) for r in regions] == [(0, "dollar"), (1, "a"), (2, "chained")]
    assert regions[0].region == {"Weight": (600, 900)}  # open end = axis end (design)
    assert regions[1].region == {"Weight": (450, 600)}
    assert regions[2].region == {"italic": (1, 1)}
    assert regions[0].line == 18


def test_substitutions_at(sk):
    glyphs = ["a", "aacute", "a.ss01", "dollar", "dollar.alt", "dollar.alt2"]
    assert sk.substitutions_at({"Weight": 420}, glyphs) == {}
    assert sk.substitutions_at({"Weight": 500}, glyphs) == {"a": "a.ss01"}
    assert sk.substitutions_at({"wght": 700}, glyphs, space="user") == {"a": "a.ss01", "dollar": "dollar.alt"}
    # rules apply in order, each to what the earlier ones made
    assert sk.substitutions_at({"Weight": 900, "italic": 1}, glyphs) == {
        "dollar": "dollar.alt2", "dollar.alt": "dollar.alt2",
    }
    # without glyph names only explicit rules apply
    assert sk.substitutions_at({"Weight": 900}) == {"dollar": "dollar.alt"}


def test_substitutions_use_the_font_data_glyphs():
    class Host(FontData):
        def glyph_names(self, source):
            return ["a", "a.ss01", "dollar", "dollar.alt"]

    sk = Sketch.parse(SKETCH, font_data=Host())
    assert sk.substitutions_at({"Weight": 500}) == {"a": "a.ss01"}


def test_substitutions_agree_with_fonttools():
    from fontTools.designspaceLib import processRules

    path = EXAMPLES / "MegaFont-WithSkip.dssketch"
    ds = dssketch.convert_to_designspace(str(path))
    sk = Sketch.parse(path.read_text(encoding="utf-8"), font_data=DefconFontData(path.parent))
    glyphs = sorted(DefconFontData(path.parent).glyph_names(dssketch.fontdata.source_path(sk.document, sk.document.sources[0])) or ())
    assert glyphs
    seen = 0
    for instance in ds.instances:
        expected = {a: b for a, b in zip(glyphs, processRules(ds.rules, instance.location, glyphs)) if a != b}
        assert sk.substitutions_at(instance.location, glyphs) == expected, instance.styleName
        seen += bool(expected)
    assert seen  # some instances do swap glyphs


# -- instances --------------------------------------------------------------------


def test_instances(sk):
    found = sk.instances()
    assert [i.style_name for i in found] == [
        "Thin", "Thin Italic", "Regular", "Italic", "Bold", "Bold Italic", "Black", "Black Italic",
    ]
    skipped = [i for i in found if i.skipped]
    assert [i.name for i in skipped] == ["Thin Italic"] and skipped[0].index is None
    assert skipped[0].skip_entry == "Thin Italic" and skipped[0].skip_span.line == 23
    assert [i.index for i in found if not i.skipped] == list(range(7))
    bold = next(i for i in found if i.style_name == "Bold")
    assert bold.user_location == {"Weight": 700, "italic": 0}
    assert bold.design_location == {"Weight": 600, "italic": 0}
    assert bold.family_name == "Q" and bold.group == ("Upright",)


@pytest.mark.parametrize("name", AUTO_EXAMPLES)
def test_instances_match_the_designspace(name):
    path = EXAMPLES / name
    ds = dssketch.convert_to_designspace(str(path))
    generated = [i for i in Sketch.parse(path.read_text(encoding="utf-8")).instances() if not i.skipped]
    assert [(i.style_name, i.design_location) for i in generated] == [
        (i.styleName, dict(i.location)) for i in ds.instances
    ]


def test_family_from_the_font_data():
    class Host(FontData):
        def family_name(self):
            return "Hosted"

    text = SKETCH.replace("family Q\n", "")
    assert Sketch.parse(text).instances()[0].family_name is None
    assert Sketch.parse(text, font_data=Host()).instances()[0].family_name == "Hosted"


def test_no_instances_when_off_or_broken():
    assert Sketch.parse(SKETCH.replace("instances auto\n    skip\n        Thin Italic\n", "instances off\n")).instances() == []
    assert Sketch.parse("").instances() == []
    assert dssketch.expand_instances("axes\n    wght 1:2\n") is not None  # never raises


def test_free_functions_take_a_text(sk):
    assert dssketch.expand_instances(SKETCH) == sk.instances()
    assert dssketch.source_locations(SKETCH) == sk.source_locations()
    assert dssketch.rule_regions(SKETCH) == sk.rule_regions()
    assert dssketch.substitutions_at(SKETCH, {"Weight": 900}) == {"dollar": "dollar.alt"}
    assert dssketch.design_to_user(sk, "wght", 600) == 700


# -- hover ------------------------------------------------------------------------


def hover_at(sk, line, word, offset=0):
    text = sk.text.split("\n")[line - 1]
    return sk.hover(line, text.index(word) + offset)


def test_hover():
    class Host(FontData):
        def glyph_names(self, source):
            return ["a", "aacute", "a.ss01", "dollar", "dollar.alt"]

    sk = Sketch.parse(SKETCH, font_data=Host())
    assert hover_at(sk, 6, "Bold") == "Bold (Weight): user 700, design 600"
    assert hover_at(sk, 5, "Regular").endswith("(user value from the standard table)")
    assert hover_at(sk, 3, "wght").startswith("Weight (wght), axis: user 100…900, default 400; design 100…900, default 420")
    assert hover_at(sk, 6, "700") == "Weight: user 700 → design 600"
    assert hover_at(sk, 16, "500") == "Weight: design 500 = user 533.333"
    assert hover_at(sk, 13, "Q-Regular") == "Q-Regular (base source): Weight 400 (design 420), italic 0"
    assert hover_at(sk, 18, "dollar") == "dollar → dollar.alt: applies at Weight 600…900 (design space)"
    assert hover_at(sk, 19, "a*") == "Swaps 1 glyph (applies at Weight 450…600 (design space)): a → a.ss01"
    assert hover_at(sk, 19, "Bold") == "Bold (Weight): user 700, design 600"  # in a condition
    assert hover_at(sk, 23, "Thin") == "Removes the instance 'Thin Italic' at Weight 100, italic 1"


def test_hover_without_font_data_and_off_code(sk):
    assert hover_at(sk, 19, "a*").endswith("the glyphs it swaps need the fonts")
    assert sk.hover(1, 0) is None  # `family` keyword
    assert sk.hover(4, 0) is None  # indentation
    assert sk.hover(999, 0) is None
    unused = Sketch.parse(SKETCH.replace("        Thin Italic", "        Regular Upright"))
    assert "matches no generated instance" in hover_at(unused, 23, "Regular")
    assert dssketch.hover(SKETCH, 6, 12) == "Bold (Weight): user 700, design 600"


# -- outline ----------------------------------------------------------------------


def walk(symbols):
    for symbol in symbols:
        yield symbol
        yield from walk(symbol.children)


def test_outline(sk):
    tree = sk.outline()
    assert [(s.kind, s.name) for s in tree] == [
        ("family", "Q"), ("section", "axes"), ("section", "sources"), ("section", "rules"), ("section", "instances"),
    ]
    axes = tree[1]
    wght = axes.children[0]
    assert (wght.kind, wght.name, wght.detail, wght.path) == ("axis", "wght", "Weight 100:400:900", ("axis", "wght"))
    assert [m.name for m in wght.children] == ["Thin", "Regular", "Bold", "Black"]
    assert wght.children[2].detail == "user 700 → design 600"
    assert (wght.span.line, wght.span.end_line) == (3, 7)  # with its mappings
    assert (axes.span.line, axes.span.end_line) == (2, 10)
    sources = tree[2]
    assert sources.detail == "[wght, ital]"
    assert sources.children[1].detail == "[Regular, Upright] @base"
    assert tree[3].children[1].detail == "a* > .ss01 (450 <= weight <= Bold)"
    assert [(s.kind, s.name) for s in tree[4].children] == [("skip", "Thin Italic")]


def test_outline_paths_match_spans(sk):
    for symbol in walk(sk.outline()):
        if symbol.path and symbol.kind not in ("family", "section"):
            span = sk.span(symbol.path)
            assert span is not None and span.line == symbol.span.line, symbol


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.dssketch")), ids=lambda p: p.name)
def test_outline_covers_every_item(path):
    from dssketch import structure as st

    sk = Sketch.parse(path.read_text(encoding="utf-8"))
    lines = {s.span.line for s in walk(sk.outline())}
    kinds = {st.AXIS, st.MAPPING, st.SOURCE_LINE, st.RULE, st.SKIP_ENTRY, st.AVAR2_VAR, st.AVAR2_ROW, st.SECTION}
    wanted = {ln.number for ln in sk.structure.lines if ln.kind in kinds}
    assert wanted <= lines


def test_outline_never_raises():
    for text in ["", "axes\n    wght\n", "sources\n    [x\n", "family\n", "rules\n    > (\n", "    stray\n"]:
        assert isinstance(Sketch.parse(text).outline(), list)
    assert dssketch.outline(SKETCH) == Sketch.parse(SKETCH).outline()
