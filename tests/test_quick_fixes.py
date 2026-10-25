"""Quick fixes on diagnostics (fixes.py, 1.5.x)."""

import pytest

from dssketch import Sketch, apply_edits, codes, diagnose

GOOD = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
    ital discrete
        Upright @elidable
        Italic
sources [wght, ital]
    T-Thin [Thin, Upright]
    T-Regular [Regular, Upright] @base
    T-Black [Black, Upright]
    T-Italic [Regular, Italic]
rules
    dollar > dollar.alt (weight >= Black)
instances auto
    skip
        Thin Italic
"""


def variant(old, new):
    assert old in GOOD
    return GOOD.replace(old, new, 1)


def find(text, name):
    wanted = codes.CODES[name].id
    found = [d for d in diagnose(text) if d.code == wanted]
    assert found, [(d.code, d.message) for d in diagnose(text)]
    return found[0]


def apply(text, fix):
    return apply_edits(text, fix.edits)


def errors(text):
    return [d.message for d in diagnose(text) if d.severity == "error"]


@pytest.mark.parametrize(
    "name, broken, title",
    [
        ("KEYWORD_TYPO", variant("family T", "familly T"), "Change to 'family'"),
        ("AXIS_TAG_TYPO", variant("wght 100", "wgjt 100"), "Change to 'wght'"),
        ("SOURCE_UNKNOWN_LABEL", variant("T-Black [Black, Upright]", "T-Black [Blak, Upright]"), "Change to 'Black'"),
        ("RULE_CONDITION", variant("weight >= Black", "weight >= Blck"), "Change to 'Black'"),
        ("SKIP_UNKNOWN_LABEL", variant("        Thin Italic", "        Thin Italik"), "Change to 'Italic'"),
        ("MULTIPLE_BASE", variant("T-Black [Black, Upright]", "T-Black [Black, Upright] @base"), "Keep @base only on 'T-Regular'"),
        ("BASE_AUTO_DETECTED", variant(" @base", ""), "Mark 'T-Regular' with @base"),
        ("NO_ELIDABLE", variant("Regular > 400 @elidable", "Regular > 400"), "Mark 'Regular' @elidable"),
        ("DUPLICATE_LABEL", variant("        Italic\n", "        Italic\n        Thin\n"), "Remove 'Thin' from axis 'ital'"),
        ("LANG_EN", variant("family T", "family T\nlang en, de"), "Remove 'en'"),
    ],
)
def test_fix_removes_the_problem(name, broken, title):
    d = find(broken, name)
    titles = [f.title for f in d.fixes]
    assert title in titles, titles
    fixed = apply(broken, d.fixes[titles.index(title)])
    wanted = codes.CODES[name].id
    assert not [x for x in diagnose(fixed) if x.code == wanted]
    assert not errors(fixed), errors(fixed)


def test_label_typo_rename_follows_uses():
    broken = GOOD.replace("Black >", "Blak >").replace("[Black,", "[Blak,").replace(">= Black", ">= Blak")
    d = find(broken, "MAPPING_LABEL_TYPO")
    assert [f.title for f in d.fixes] == ["Rename 'Blak' to 'Black'"]
    assert apply(broken, d.fixes[0]) == GOOD


def test_skip_entry_can_be_removed():
    broken = variant("        Thin Italic", "        Thin Xyzzy")
    d = find(broken, "SKIP_UNKNOWN_LABEL")
    assert [f.title for f in d.fixes] == ["Remove skip entry 'Thin Xyzzy'"]
    fixed = apply(broken, d.fixes[0])
    assert "skip" not in fixed and not errors(fixed)


def test_skip_check_is_placed_on_its_line():
    broken = variant("        Thin Italic", "        Thin Italik")
    d = find(broken, "SKIP_UNKNOWN_LABEL")
    assert d.line == 19 and broken.split("\n")[18][d.column: d.end_column] == "Italik"


def test_mapping_out_of_range_offers_both_ways():
    broken = variant("Thin > 100", "50 Thin > 100")
    d = find(broken, "MAPPING_OUT_OF_RANGE")
    assert [f.title for f in d.fixes] == ["Extend the axis minimum to 50", "Move the mapping to user value 100"]
    extended = apply(broken, d.fixes[0])
    assert "wght 50:400:900" in extended
    moved = apply(broken, d.fixes[1])
    assert "        Thin > 100\n" in moved and not errors(moved)


def test_missing_extreme_adds_a_mapping():
    broken = variant("        Black > 900\n", "").replace("[Black, Upright]", "[Regular, Upright]").replace(
        "weight >= Black", "weight >= Regular"
    ).replace("T-Black [Regular, Upright]\n", "")
    d = find(broken, "MAPPING_EXTREME_MISSING")
    titles = [f.title for f in d.fixes]
    assert titles == ["Add 'Black' at 900", "Add an unnamed map point at 900"]
    fixed = apply(broken, d.fixes[0])
    assert "        Black > 900\n" in fixed
    assert not [x for x in diagnose(fixed) if x.code == d.code]


def test_no_base_offers_sources_at_the_defaults():
    broken = variant("T-Regular [Regular, Upright] @base", "T-Regular [Regular, Italic]")
    broken = broken.replace("    T-Italic [Regular, Italic]\n", "    T-Mid [Regular, Upright]\n")
    d = find(broken, "NO_BASE") if any(x.code == "5.3" for x in diagnose(broken)) else find(broken, "BASE_AUTO_DETECTED")
    assert d.fixes and "T-Mid" in d.fixes[0].title


def test_diagnostics_without_handler_have_no_fixes():
    text = variant("T-Black [Black, Upright]", "T-Black [Black]")
    d = find(text, "SOURCE_COORD_COUNT")
    assert d.fixes == ()


def test_no_close_label_no_fix():
    d = find(variant("T-Black [Black, Upright]", "T-Black [Zzzzzz, Upright]"), "SOURCE_UNKNOWN_LABEL")
    assert d.fixes == ()


def test_fix_edits_are_against_the_diagnosed_text():
    broken = variant("family T", "familly T")
    d = find(broken, "KEYWORD_TYPO")
    (edit,) = d.fixes[0].edits
    assert (edit.line, edit.col, edit.end_col, edit.new_text) == (1, 0, 7, "family")


def test_sketch_and_diagnose_give_the_same_fixes():
    broken = variant("T-Black [Black, Upright]", "T-Black [Blak, Upright] @base")
    assert Sketch.parse(broken).diagnostics == diagnose(broken)


def test_fixes_never_break_diagnose():
    for text in ["", "familly", "axes\n    wgth 1:2:3\n", "sources\n    A @base @base\n", "instances auto\n    skip\n        X"]:
        for d in diagnose(text):
            assert isinstance(d.fixes, tuple)


@pytest.mark.parametrize("condition", ["(wieght >= Black)", "(wieght >= 900)"])
def test_rule_on_an_unknown_axis(condition):
    broken = variant("(weight >= Black)", condition)
    d = find(broken, "RULE_CONDITION")
    assert d.severity == "error" and "'wieght'" in d.message
    assert [f.title for f in d.fixes] == ["Change to 'weight'"]
    assert "(weight >= " in apply(broken, d.fixes[0]) and not errors(apply(broken, d.fixes[0]))




def test_rule_glyph_fixes_with_font_data():
    from dssketch import FontData

    class Host(FontData):
        def glyph_names(self, source):
            return ["dollar", "dollar.alt", "a", "a.ss01"]

    broken = variant("dollar > dollar.alt", "dolar > dollar.alt")
    found = [d for d in diagnose(broken, font_data=Host()) if d.code == codes.CODES["RULE_GLYPH_MISSING"].id]
    assert [f.title for f in found[0].fixes] == ["Change to 'dollar'"]
    assert apply(broken, found[0].fixes[0]) == GOOD

    target = variant("dollar > dollar.alt", "dollar > dollar.atl")
    found = [d for d in diagnose(target, font_data=Host()) if d.code == codes.CODES["RULE_TARGET_MISSING"].id]
    assert apply(target, found[0].fixes[0]) == GOOD

    nothing = variant("dollar > dollar.alt", "q* > .ss01")
    found = [d for d in diagnose(nothing, font_data=Host()) if d.code == codes.CODES["RULE_MATCHES_NOTHING"].id]
    assert [f.title for f in found[0].fixes] == ["Remove the rule"]
    assert "q*" not in apply(nothing, found[0].fixes[0])
