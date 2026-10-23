"""complete(): suggestions for the word at the cursor.

The cursor is written as `|` in the test texts.
"""

import pytest

from dssketch import complete
from dssketch.syntax import AXIS_TAG, FLAG, KEYWORD, LABEL, VARIABLE

AXES = """\
family Test
axes
    wght 100:400:900
        Thin > 100
        Regular > 420 @elidable
        Black > 900
    ital discrete
        Upright @elidable
        Italic
"""

HIDDEN = AXES + "axes hidden\n    XOUC 0:100:200\navar2 vars\n    $XO = 50\n"


def _complete(text):
    at = text.index("|")
    before = text[:at]
    line = before.count("\n") + 1
    column = len(before.split("\n")[-1])
    return complete(text.replace("|", "", 1), line, column)


def _texts(text):
    return [c.text for c in _complete(text)]


def test_section_keywords_at_line_start():
    assert _texts("ax|") == ["axes", "axes hidden"]
    assert set(_texts("|")) >= {"family", "axes", "sources", "rules", "instances auto", "avar2 matrix"}


def test_header_followers():
    assert _texts("instances |") == ["auto", "off"]
    assert _texts("avar2 m|") == ["matrix"]


def test_replace_range_covers_the_whole_word():
    [c] = _complete(AXES + "sources [wght, ital]\n    A [Reg|ul, Upright] @base")
    assert (c.text, c.column, c.end_column) == ("Regular", 7, 12)


def test_source_coordinates_follow_the_axis_order():
    assert _texts(AXES + "sources [wght, ital]\n    A [|") == ["Thin", "Regular", "Black"]
    assert _texts(AXES + "sources [wght, ital]\n    A [Regular, |") == ["Upright", "Italic"]
    assert _texts(AXES + "sources [ital, wght]\n    A [|") == ["Upright", "Italic"]


def test_source_label_detail_is_design_space():
    [c] = _complete(AXES + "sources [wght, ital]\n    A [Re|")
    assert (c.type, c.detail) == (LABEL, "design 420")


def test_source_flags():
    assert _texts(AXES + "sources [wght, ital]\n    A [Regular, Upright] |") == [
        "@base", "@sparse", "@layer=",
    ]
    [c] = _complete(AXES + "sources [wght, ital]\n    A [Regular, Upright] @s|")
    assert (c.text, c.type) == ("@sparse", FLAG)


def test_named_source_coordinates():
    assert _texts(AXES + "sources\n    A wght=B|") == ["Black"]
    assert "ital" in _texts(AXES + "sources\n    A wght=Black, |")


def test_sources_header_lists_unused_axes():
    assert _texts(AXES + "sources [wght, |") == ["ital"]


def test_mapping_offers_standard_labels_not_yet_used():
    texts = _texts(AXES.replace("    ital discrete\n        Upright @elidable\n        Italic\n", "")
                   + "        B|")
    assert texts[:2] == ["Book", "Bold"] and "Black" not in texts
    assert all(" " not in t for t in texts)


def test_mapping_after_explicit_user_value():
    assert "Light" in _texts(AXES.split("    ital")[0] + "        300 L|")


def test_discrete_axis_labels():
    assert _texts(AXES.replace("        Italic\n", "") + "        I|") == ["Italic"]


def test_elidable_after_design_value():
    assert _texts(AXES + "        Bold > 700 |") == ["@elidable"]


def test_axis_definition_offers_unused_registered_axes():
    texts = _texts(AXES + "    w|")
    assert texts == ["wdth", "width"]


def test_label_range():
    assert "Thin" in _texts("axes\n    wght |")
    assert "Regular" in _texts("axes\n    wght Thin:|")
    assert _texts("axes\n    ital |") == ["discrete"]


def test_rule_condition():
    texts = _texts(AXES + "rules\n    a > a.alt (|")
    assert texts[:2] == ["weight", "italic"] and "Regular" in texts
    assert _texts(AXES + "rules\n    a > a.alt (weight >= |") == ["Thin", "Regular", "Black"]
    assert _texts(AXES + "rules\n    a > a.alt (Regular <= |")[0] == "weight"
    assert _texts(AXES + "rules\n    a > a.alt (weight >= Bold && |")[0] == "weight"


def test_rule_glyphs_have_no_suggestions():
    assert _texts(AXES + "rules\n    dol|") == []


def test_instances_skip():
    assert _texts(AXES + "instances auto\n    |") == ["skip"]
    assert _texts(AXES + "instances auto\n    skip\n        Bl|") == ["Black"]
    assert "Bold" not in _texts(AXES + "instances auto\n    skip\n        Thin |")
    assert "Italic" in _texts(AXES + "instances auto\n    skip\n        Thin |")


def test_lang_codes():
    assert {"de", "da"} <= set(_texts("lang d|"))
    assert "de" not in _texts("lang de, d|")


def test_avar2_inputs_are_user_space():
    [c] = _complete(HIDDEN + "avar2\n    [wght=Re|")
    assert (c.text, c.detail) == ("Regular", "user 400")
    assert _texts(HIDDEN + "avar2\n    [|") == ["wght", "ital"]


def test_avar2_outputs():
    assert _texts(HIDDEN + "avar2\n    [wght=Regular] > |") == ["wght", "ital", "XOUC"]
    out = _complete(HIDDEN + "avar2\n    [wght=Regular] > XOUC=|")
    assert [(c.text, c.type) for c in out] == [("$", VARIABLE), ("$XO", VARIABLE)]
    assert _texts(HIDDEN + "avar2\n    [wght=Regular] > {\n        |") == ["wght", "ital", "XOUC"]


def test_avar2_matrix():
    assert _texts(HIDDEN + "avar2 matrix\n    |") == ["outputs"]
    assert _texts(HIDDEN + "avar2 matrix\n    outputs XOUC |") == ["wght", "ital"]
    assert "-" in _texts(HIDDEN + "avar2 matrix\n    outputs XOUC\n    [wght=Regular] |")


def test_types():
    assert {c.type for c in _complete("|")} == {KEYWORD}
    assert {c.type for c in _complete(AXES + "    w|")} == {AXIS_TAG}


@pytest.mark.parametrize(
    "text",
    [AXES + "    # a comm|ent", 'family "My F|', "", "\x00]]][[ |", AXES + "rules\n    a > (((|"],
)
def test_nothing_and_never_raises(text):
    if "|" in text:
        result = _complete(text)
    else:
        result = complete(text, 5, 99)
    assert isinstance(result, list)
    if "comm" in text or "My F" in text:
        assert result == []
