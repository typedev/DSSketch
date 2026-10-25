"""Sketch editing operations: minimal TextEdits on a hand-written text (1.5.0)."""

import difflib

import pytest

from dssketch import EditError, Sketch, SourceKey, apply_edits

DEMO = """\
# Demo font
family Demo  # the family
path sources

axes
    # weight comes first
    wght 100:400:900  # weight axis
        Thin > 100
        Regular > 400 @elidable  # default
        Black > 900
    ital discrete
        Upright @elidable
        Italic

sources [wght, ital]
    # masters
    Demo-Thin [Thin, Upright]
    Demo-Regular [Regular, Upright] @base
    Demo-Black [Black, Upright]   # heavy
    Demo-Italic [Regular, Italic] @base

rules
    dollar > dollar.alt (weight >= Black) "heavy dollar"

instances auto
    skip
        Thin Italic
"""


@pytest.fixture
def sk():
    sketch = Sketch.parse(DEMO)
    assert not [d for d in sketch.diagnostics if d.severity == "error"]
    return sketch


def diff(result):
    """The changed lines as '-old' / '+new'"""
    return [
        line.rstrip("\n")
        for line in difflib.unified_diff(DEMO.splitlines(True), result.text.splitlines(True), n=0)
        if line[:1] in "+-" and not line.startswith(("---", "+++"))
    ]


def check(result):
    """Edits reproduce the text, in order, without overlap; the new text parses"""
    assert apply_edits(DEMO, result.edits) == result.text
    for a, b in zip(result.edits, result.edits[1:]):
        assert (a.end_line, a.end_col) <= (b.line, b.col)
    assert not [d for d in result.sketch.diagnostics if d.severity == "error"]
    return diff(result)


def refused(code, fn):
    with pytest.raises(EditError) as info:
        fn()
    assert info.value.code == code
    return info.value


# -- round trip ---------------------------------------------------------------


def test_unchanged_sketch_is_byte_identical(sk):
    assert sk.text == DEMO
    assert sk.set_family("Demo").text == DEMO
    assert sk.set_mapping_design("wght", "Thin", 100).text == DEMO


def test_noop_operations_return_no_edits(sk):
    for result in (
        sk.set_mapping_elidable("wght", "Regular", True),
        sk.set_sparse("Demo-Thin", False),
        sk.set_instances_mode("auto"),
        sk.set_axis_discrete("ital", True),
        sk.move_axis("wght", 0),
    ):
        assert result.edits == [] and result.text == DEMO


# -- header -------------------------------------------------------------------


def test_set_family_keeps_trailing_comment(sk):
    assert check(sk.set_family("Demo Sans")) == [
        "-family Demo  # the family", "+family Demo Sans  # the family",
    ]


def test_family_with_hash_is_quoted(sk):
    assert check(sk.set_family("Demo #2"))[1] == '+family "Demo #2"  # the family'


def test_clear_path_removes_line(sk):
    assert check(sk.set_path(None)) == ["-path sources"]


def test_new_header_lines_go_in_order(sk):
    assert check(sk.set_suffix("VF")) == ["+suffix VF"]
    result = sk.set_suffix("VF")
    assert result.text.splitlines()[1:4] == ["family Demo  # the family", "suffix VF", "path sources"]
    assert check(sk.set_lang(["de", "ru"])) == ["+lang de, ru"]
    assert sk.set_lang(["de"]).text.splitlines()[3] == "lang de"


def test_family_added_before_first_section():
    text = "axes\n    wght 1:1:2\nsources\n    A [1] @base\n"
    result = Sketch.parse(text).set_family("New")
    assert result.text == "family New\n\naxes\n    wght 1:1:2\nsources\n    A [1] @base\n"


# -- axes ---------------------------------------------------------------------


def test_add_axis_adds_a_column_to_every_source(sk):
    assert check(sk.add_axis("wdth", 75, 100, 125)) == [
        "+    wdth 75:100:125",
        "-sources [wght, ital]",
        "+sources [wght, ital, wdth]",
        "-    Demo-Thin [Thin, Upright]",
        "-    Demo-Regular [Regular, Upright] @base",
        "-    Demo-Black [Black, Upright]   # heavy",
        "-    Demo-Italic [Regular, Italic] @base",
        "+    Demo-Thin [Thin, Upright, 100]",
        "+    Demo-Regular [Regular, Upright, 100] @base",
        "+    Demo-Black [Black, Upright, 100]   # heavy",
        "+    Demo-Italic [Regular, Italic, 100] @base",
    ]


def test_add_axis_at_index_keeps_comments_with_the_next_axis(sk):
    result = sk.add_axis("CNTR", 0, 0, 100, name="CONTRAST", index=0)
    check(result)
    lines = result.text.splitlines()
    assert lines[5:8] == ["    CONTRAST CNTR 0:0:100", "    # weight comes first", "    wght 100:400:900  # weight axis"]


def test_add_hidden_axis_creates_section(sk):
    result = sk.add_axis("XOUC", 0, 100, 200, hidden=True)
    check(result)
    assert "axes hidden\n    XOUC 0:100:200\n" in result.text
    assert result.text.index("axes hidden") < result.text.index("sources [")


def test_add_axis_refuses_duplicate(sk):
    refused("duplicate", lambda: sk.add_axis("wght", 1, 2, 3))
    refused("invalid-value", lambda: sk.add_axis("wghtt", 1, 2, 3))


def test_remove_axis_in_use_is_refused(sk):
    error = refused("in-use", lambda: sk.remove_axis("ital"))
    assert "skip 'Thin Italic'" in error.messages


def test_remove_axis_drops_its_column():
    text = DEMO.replace("    skip\n        Thin Italic\n", "")
    text = text.replace("Demo-Italic [Regular, Italic] @base", "Demo-Italic [600, Italic]")
    result = Sketch.parse(text).remove_axis("ital")
    assert result.text.count("Upright") == 0 and "sources [wght]" in result.text
    assert "    Demo-Thin [Thin]\n" in result.text
    assert "    Demo-Italic [600]\n" in result.text
    assert not [d for d in result.sketch.diagnostics if d.severity == "error"]


def test_remove_axis_leaving_two_bases_is_rejected():
    text = DEMO.replace("    skip\n        Thin Italic\n", "")
    error = refused("rejected", lambda: Sketch.parse(text).remove_axis("ital"))
    assert "Multiple base" in error.message


def test_move_axis_moves_block_with_comments(sk):
    assert check(sk.move_axis("ital", 0)) == [
        "+    ital discrete",
        "+        Upright @elidable",
        "+        Italic",
        "-    ital discrete",
        "-        Upright @elidable",
        "-        Italic",
    ]
    moved = sk.move_axis("wght", 1)
    check(moved)
    assert moved.text.splitlines()[5:9] == [
        "    ital discrete", "        Upright @elidable", "        Italic", "    # weight comes first",
    ]


def test_move_axis_writes_source_order_when_missing():
    text = DEMO.replace("sources [wght, ital]", "sources")
    result = Sketch.parse(text).move_axis("ital", 0)
    assert "sources [wght, ital]" in result.text
    assert not [d for d in result.sketch.diagnostics if d.severity == "error"]


def test_set_axis_tag_follows_references(sk):
    assert check(sk.set_axis_tag("wght", "WGHT")) == [
        "-    wght 100:400:900  # weight axis",
        "+    WGHT 100:400:900  # weight axis",
        "-sources [wght, ital]",
        "+sources [WGHT, ital]",
        '-    dollar > dollar.alt (weight >= Black) "heavy dollar"',
        '+    dollar > dollar.alt (WGHT >= Black) "heavy dollar"',
    ]


def test_set_axis_name(sk):
    result = sk.set_axis_name("wght", "Heaviness")
    check(result)
    assert "    Heaviness wght 100:400:900  # weight axis" in result.text
    assert "(Heaviness >= Black)" in result.text
    back = result.sketch.set_axis_name("wght", None)
    assert back.text == DEMO


def test_display_name_set_and_cleared(sk):
    result = sk.set_axis_display_name("wght", "Weight")
    assert check(result) == [
        "-    wght 100:400:900  # weight axis", '+    wght 100:400:900 "Weight"  # weight axis',
    ]
    assert result.sketch.set_axis_display_name("wght", None).text == DEMO


def test_set_axis_range(sk):
    # the maximum needs a mapping: refused, then accepted where it fixes an error
    refused("rejected", lambda: sk.set_axis_range("wght", maximum=1000))
    broken = Sketch.parse(DEMO.replace("        Black > 900\n", "        Black > 900\n        1000 > 1000\n"))
    result = broken.set_axis_range("wght", maximum=1000)
    assert "wght 100:400:1000  # weight axis" in result.text
    assert not [d for d in result.sketch.diagnostics if d.severity == "error"]
    error = refused("rejected", lambda: sk.set_axis_range("wght", minimum=200))
    assert "outside the axis range" in error.message
    refused("invalid-value", lambda: sk.set_axis_range("wght", minimum=500))
    refused("not-applicable", lambda: sk.set_axis_range("ital", maximum=2))


def test_label_range_keeps_labels():
    text = DEMO.replace("wght 100:400:900", "wght Thin:Regular:Black")
    sk = Sketch.parse(text)
    result = sk.set_axis_range("wght", maximum=900)
    assert "wght Thin:Regular:Black" in result.text
    widened = Sketch.parse(text.replace("Black > 900", "Black > 900\n        1000 > 1000")).set_axis_range("wght", maximum=1000)
    assert "wght 100:400:1000" in widened.text


def test_discrete_toggle(sk):
    result = sk.set_axis_discrete("ital", False)
    assert check(result) == ["-    ital discrete", "+    ital 0:0:1"]


# -- mappings -----------------------------------------------------------------


def test_add_mapping_in_user_order(sk):
    assert check(sk.add_mapping("wght", "Bold", 700)) == ["+        Bold > 700"]
    assert sk.add_mapping("wght", "Bold", 700).text.splitlines()[9] == "        Bold > 700"
    assert check(sk.add_mapping("wght", "Light", 300)) == ["+        Light > 300"]
    assert sk.add_mapping("wght", "Light", 300).text.splitlines()[8] == "        Light > 300"


def test_add_mapping_writes_user_only_when_needed(sk):
    assert check(sk.add_mapping("wght", "Heavy", 850, user=850)) == ["+        850 Heavy > 850"]
    assert check(sk.add_mapping("wght", "Bold", 680, user=700)) == ["+        Bold > 680"]
    assert check(sk.add_mapping("wght", "", 450, user=450)) == ["+        450 > 450"]


def test_add_mapping_refuses_duplicate_label(sk):
    refused("duplicate", lambda: sk.add_mapping("wght", "Thin", 100))
    refused("duplicate", lambda: sk.add_mapping("wght", "Italic", 100))


def test_remove_used_mapping_is_rejected(sk):
    error = refused("rejected", lambda: sk.remove_mapping("wght", "Black"))
    assert "Black" in error.message


def test_set_mapping_values(sk):
    assert check(sk.set_mapping_design("wght", "Regular", 420)) == [
        "-        Regular > 400 @elidable  # default", "+        Regular > 420 @elidable  # default",
    ]
    assert check(sk.set_mapping_elidable("wght", "Regular", False)) == [
        "-        Regular > 400 @elidable  # default", "+        Regular > 400  # default",
    ]
    result = sk.set_mapping_user("wght", "Black", 900)  # = the standard value: stays inferred
    assert result.text == DEMO


def test_set_mapping_label_is_local(sk):
    # its uses are not rewritten: the source still says Thin
    refused("rejected", lambda: sk.set_mapping_label("wght", "Thin", "Hairline"))


def test_set_mapping_label_keeps_user_value(sk):
    with_bold = sk.add_mapping("wght", "Bold", 700).sketch
    # Heavy is a standard label at another user value: 700 is written out
    result = with_bold.set_mapping_label("wght", "Bold", "Heavy")
    assert "        700 Heavy > 700\n" in result.text
    assert "        Medium > 700\n" not in with_bold.set_mapping_label("wght", "Bold", "Bold2").text
    assert "        Bold2 > 700\n" in with_bold.set_mapping_label("wght", "Bold", "Bold2").text


def test_rename_label_rewrites_uses(sk):
    assert check(sk.rename_label("wght", "Black", "Heavy")) == [
        "-        Black > 900",
        "+        900 Heavy > 900",
        "-    Demo-Black [Black, Upright]   # heavy",
        "+    Demo-Black [Heavy, Upright]   # heavy",
        '-    dollar > dollar.alt (weight >= Black) "heavy dollar"',
        '+    dollar > dollar.alt (weight >= Heavy) "heavy dollar"',
    ]
    renamed = sk.rename_label("wght", "Thin", "Hair")
    assert "        Hair Italic" in renamed.text
    assert "    Demo-Thin [Hair, Upright]" in renamed.text
    assert "100 Hair > 100" not in renamed.text and "Hair > 100" in renamed.text


# -- sources ------------------------------------------------------------------


def test_add_source_in_the_documents_form(sk):
    assert check(sk.add_source("Demo-Bold", {"wght": 700})) == ["+    Demo-Bold [700, Upright]"]
    assert check(sk.add_source("Demo-BlackItalic", {"wght": "Black", "ital": 1})) == [
        "+    Demo-BlackItalic [Black, Italic]",
    ]
    assert check(sk.add_source("Demo-X", {"wght": 850}, prefer="number")) == ["+    Demo-X [850, 0]"]
    assert check(sk.add_source("My Font", {"weight": 100, "ital": 1}, sparse=True, layer="fix")) == [
        '+    "My Font" [Thin, Italic] @sparse @layer="fix"',
    ]


def test_add_source_named_form():
    text = DEMO.replace("    Demo-Thin [Thin, Upright]", "    Demo-Thin wght=Thin")
    text = text.replace("    Demo-Regular [Regular, Upright] @base", "    Demo-Regular @base")
    text = text.replace("    Demo-Black [Black, Upright]   # heavy", "    Demo-Black wght=Black   # heavy")
    text = text.replace("    Demo-Italic [Regular, Italic] @base", "    Demo-Italic ital=Italic @base")
    sk = Sketch.parse(text)
    assert not [d for d in sk.diagnostics if d.severity == "error"]
    result = sk.add_source("Demo-Bold", {"wght": 900, "ital": 1})
    assert "    Demo-Bold wght=Black, ital=Italic\n" in result.text
    moved = sk.set_source_coordinate("Demo-Thin", "ital", 1)
    assert "    Demo-Thin wght=Thin, ital=Italic" in moved.text
    added = sk.set_source_coordinate("Demo-Black", "ital", 1)
    assert "    Demo-Black wght=Black, ital=Italic   # heavy" in added.text


def test_remove_source_takes_its_leading_comment(sk):
    assert check(sk.remove_source("Demo-Thin")) == ["-    # masters", "-    Demo-Thin [Thin, Upright]"]


def test_remove_base_is_rejected(sk):
    refused("rejected", lambda: sk.remove_source("Demo-Regular"))


def test_rename_source(sk):
    assert check(sk.rename_source("Demo-Black", "Demo-Heavy")) == [
        "-    Demo-Black [Black, Upright]   # heavy", "+    Demo-Heavy [Black, Upright]   # heavy",
    ]
    assert '"Demo Heavy" [Black' in sk.rename_source("Demo-Black", "Demo Heavy").text


def test_set_source_coordinate_spelling(sk):
    assert check(sk.set_source_coordinate("Demo-Thin", "ital", 1))[1] == "+    Demo-Thin [Thin, Italic]"
    assert check(sk.set_source_coordinate("Demo-Black", "wght", 850))[1] == "+    Demo-Black [850, Upright]   # heavy"
    assert check(sk.set_source_coordinate("Demo-Thin", "italic", 1, prefer="number"))[1] == "+    Demo-Thin [Thin, 1]"
    refused("invalid-value", lambda: sk.set_source_coordinate("Demo-Black", "wght", "Bolt"))
    refused("unknown-key", lambda: sk.set_source_coordinate("Demo-Black", "wdth", 100))
    refused("unknown-key", lambda: sk.set_source_coordinate("Nope", "wght", 100))


def test_source_keys():
    text = DEMO.replace(
        "    Demo-Black [Black, Upright]   # heavy",
        "    Demo-Black [Black, Upright]   # heavy\n    Demo-Black [850, Upright] @layer=mid",
    )
    sk = Sketch.parse(text)
    refused("ambiguous-key", lambda: sk.source("Demo-Black"))
    assert sk.source(SourceKey("Demo-Black.ufo", "mid")).layer == "mid"
    result = sk.set_layer(SourceKey("Demo-Black.ufo", "mid"), "middle")
    assert "    Demo-Black [850, Upright] @layer=middle" in result.text


def test_flags(sk):
    assert check(sk.set_sparse("Demo-Black", True))[1] == "+    Demo-Black [Black, Upright] @sparse   # heavy"
    assert check(sk.set_layer("Demo-Black", "bold layer"))[1] == '+    Demo-Black [Black, Upright] @layer="bold layer"   # heavy'
    assert check(sk.set_sparse("Demo-Regular", True))[1] == "+    Demo-Regular [Regular, Upright] @sparse @base"


def test_set_base_off_default_is_rejected(sk):
    refused("rejected", lambda: sk.set_base("Demo-Black"))


def test_edit_error_text_has_no_critical_prefix(sk):
    with pytest.raises(EditError) as caught:
        sk.set_base("Demo-Black")
    assert caught.value.messages and not caught.value.message.startswith("CRITICAL")
    assert not any(m.startswith("CRITICAL") for m in caught.value.messages)


def test_set_base_moves_flag():
    text = DEMO.replace("Demo-Regular [Regular, Upright] @base", "Demo-Regular [Regular, Upright]")
    text = text.replace("    Demo-Black [Black, Upright]   # heavy", "    Demo-Regular2 [Regular, Upright] @base")
    sk = Sketch.parse(text)
    result = sk.set_base("Demo-Regular")
    assert "    Demo-Regular [Regular, Upright] @base\n" in result.text
    assert "    Demo-Regular2 [Regular, Upright]\n" in result.text
    assert "    Demo-Italic [Regular, Italic] @base\n" in result.text  # other discrete value


# -- instances ----------------------------------------------------------------


def test_instances_mode(sk):
    assert check(sk.set_instances_mode("off")) == ["-instances auto", "+instances off"]
    refused("invalid-value", lambda: sk.set_instances_mode("on"))


def test_instances_section_added_when_missing():
    text = DEMO[: DEMO.index("instances auto")]
    result = Sketch.parse(text).set_instances_mode("off")
    assert result.text.endswith("\ninstances off\n")


def test_skip_entries(sk):
    assert check(sk.add_skip("Black  Italic")) == ["+        Black Italic"]
    refused("invalid-value", lambda: sk.add_skip("Bolt Italic"))
    refused("duplicate", lambda: sk.add_skip("Thin Italic"))
    assert check(sk.remove_skip("Thin Italic")) == ["-    skip", "-        Thin Italic"]
    refused("unknown-key", lambda: sk.remove_skip("Black Italic"))


def test_skip_block_created():
    text = DEMO.replace("    skip\n        Thin Italic\n", "")
    result = Sketch.parse(text).add_skip("Thin Italic")
    assert result.text.endswith("instances auto\n    skip\n        Thin Italic\n")


# -- recover mode -------------------------------------------------------------


def test_edits_work_with_errors_elsewhere(sk):
    broken = DEMO.replace("    Demo-Black [Black, Upright]   # heavy", "    Demo-Black [Bolt, Upright]   # heavy")
    sk = Sketch.parse(broken)
    assert [d for d in sk.diagnostics if d.severity == "error"]
    result = sk.set_family("Other")
    assert "family Other  # the family" in result.text
    assert sk.add_mapping("wght", "Bold", 700).text.count("Bold > 700") == 1


def test_target_with_errors_is_refused():
    broken = DEMO.replace("Demo-Black [Black, Upright]", "Demo-Black [Bolt, Upright]")
    sk = Sketch.parse(broken)
    # the source did not parse: it has no model, so no key
    refused("unknown-key", lambda: sk.set_sparse("Demo-Black", True))


def test_editing_never_touches_other_lines(sk):
    for result in (
        sk.set_source_coordinate("Demo-Black", "wght", 850),
        sk.add_mapping("wght", "Bold", 700),
        sk.set_axis_display_name("wght", "Weight"),
    ):
        old, new = DEMO.splitlines(), result.text.splitlines()
        changed = {e.line for e in result.edits}
        for number, line in enumerate(old, 1):
            if number not in changed and number < min(changed):
                assert new[number - 1] == line


HIDDEN = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900

axes hidden
    XOUC 0:100:200
    XOLC 0:50:100

sources [wght]
    T-Thin [Thin]
    T-Regular [Regular] @base
    T-Black [Black]

avar2
    [wght=Black] > XOUC=150
instances off
"""


def test_hidden_axis_range_and_remove():
    sk = Sketch.parse(HIDDEN)
    assert "    XOLC 0:50:120\n" in sk.set_axis_range("XOLC", maximum=120).text
    removed = sk.remove_axis("XOLC").text
    assert "XOLC" not in removed and "axes hidden\n    XOUC 0:100:200\n\nsources" in removed
    refused("in-use", lambda: sk.remove_axis("XOUC"))


def test_removing_the_last_hidden_axis_removes_the_section():
    text = HIDDEN.replace("    XOLC 0:50:100\n", "").replace("\navar2\n    [wght=Black] > XOUC=150\n", "\n")
    result = Sketch.parse(text).remove_axis("XOUC")
    assert "axes hidden" not in result.text
    assert "        Black > 900\n\nsources [wght]" in result.text
    assert not [d for d in result.sketch.diagnostics if d.severity == "error"]


def test_a_commented_hidden_section_header_stays():
    text = HIDDEN.replace("axes hidden\n", "axes hidden  # parametric\n").replace("    XOLC 0:50:100\n", "")
    text = text.replace("\navar2\n    [wght=Black] > XOUC=150\n", "\n")
    assert "axes hidden  # parametric\n" in Sketch.parse(text).remove_axis("XOUC").text


# -- rules ----------------------------------------------------------------------

RULES = DEMO.replace(
    '    dollar > dollar.alt (weight >= Black) "heavy dollar"\n',
    '    # heavy forms\n'
    '    dollar > dollar.alt (weight >= Black) "heavy dollar"\n'
    '    a* > .ss01 (Regular <= weight <= Black)  # alternates\n'
    '    g > g.alt (italic == 1 && weight >= Regular) "italic g"\n',
)


@pytest.fixture
def rk():
    return Sketch.parse(RULES)


def rules_of(text):
    return text.split("rules\n", 1)[1].split("\n\ninstances", 1)[0]


def test_add_rule(rk):
    result = rk.add_rule("b", "b.alt", "weight >= Black", name="b alt")
    assert rules_of(result.text).endswith('    b > b.alt (weight >= Black) "b alt"')
    first = rk.add_rule("c*", ".ss02", ["weight >= Regular", "italic == 1"], index=0)
    assert rules_of(first.text).startswith("    c* > .ss02 (weight >= Regular && italic == 1)\n    # heavy forms\n")
    assert first.sketch.document.rules[0].pattern == "c*"


def test_add_rule_creates_the_section():
    text = DEMO.replace('rules\n    dollar > dollar.alt (weight >= Black) "heavy dollar"\n\n', "")
    result = Sketch.parse(text).add_rule("b", "b.alt", "weight >= Black")
    assert "\nrules\n    b > b.alt (weight >= Black)\n" in result.text
    assert result.text.index("rules") < result.text.index("instances auto")


def test_remove_and_move_rule(rk):
    removed = rk.remove_rule(0).text
    assert "heavy" not in rules_of(removed)  # with its leading comment
    moved = rk.move_rule(2, 0)
    assert [r.name for r in moved.sketch.document.rules] == ["italic g", "heavy dollar", moved.sketch.document.rules[2].name]
    assert rules_of(moved.text).splitlines()[0] == '    g > g.alt (italic == 1 && weight >= Regular) "italic g"'
    back = rk.move_rule(0, 2)
    assert rules_of(back.text).splitlines()[-2:] == [
        "    # heavy forms", '    dollar > dollar.alt (weight >= Black) "heavy dollar"',
    ]
    assert rk.move_rule(1, 1).edits == []


def test_set_rule_fields(rk):
    assert '    dollar cent > dollar.alt (weight >= Black) "heavy dollar"' in rk.set_rule_pattern(0, "dollar  cent").text
    assert '    dollar > dollar.heavy (weight >= Black)' in rk.set_rule_target(0, "dollar.heavy").text
    assert '(weight >= Black) "dollar alternates"' in rk.set_rule_name(0, "dollar alternates").text
    assert '    dollar > dollar.alt (weight >= Black)\n' in rk.set_rule_name(0, None).text
    assert '    a* > .ss01 (Regular <= weight <= Black) "a"  # alternates' in rk.set_rule_name(1, "a").text


def test_rule_conditions(rk):
    added = rk.add_rule_condition(0, "italic == 0")
    assert "(weight >= Black && italic == 0)" in added.text
    assert "(500 <= weight <= Black)" in rk.set_rule_condition(1, 0, "500 <= weight <= Black").text
    assert "(weight >= Regular)" in rk.remove_rule_condition(2, 0).text
    assert "(italic == 1)" in rk.remove_rule_condition(2, 1).text


def test_rule_ops_refuse(rk):
    refused("unknown-key", lambda: rk.remove_rule(3))
    refused("unknown-key", lambda: rk.set_rule_condition(0, 4, "weight >= Black"))
    refused("not-applicable", lambda: rk.remove_rule_condition(0, 0))
    refused("invalid-value", lambda: rk.add_rule("a > b", "x", "weight >= Black"))
    refused("invalid-value", lambda: rk.add_rule("a", "b c", "weight >= Black"))
    refused("invalid-value", lambda: rk.add_rule("a", "b", []))
    refused("invalid-value", lambda: rk.set_rule_name(0, 'say "hi"'))
    refused("rejected", lambda: rk.set_rule_condition(0, 0, "weight >= Bolt"))
    refused("rejected", lambda: rk.add_rule_condition(0, "wdth >= 100"))  # no such axis
