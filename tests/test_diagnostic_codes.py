"""Stable diagnostic codes (codes.py, 1.5.0)."""

import pytest

from dssketch import codes, diagnose

# Append-only: a code once published never changes its number
PUBLISHED = {
    "UNCLASSIFIED": 0, "NO_AXES": 1, "NO_SOURCES": 2, "NO_BASE": 3, "MULTIPLE_BASE": 4,
    "BASE_NOT_AT_DEFAULT": 5, "AXIS_RANGE_EMPTY": 6, "AXIS_INCOMPLETE": 7, "DUPLICATE_LABEL": 8,
    "BASE_AUTO_DETECTED": 9, "FAMILY_EMPTY": 10, "PATH_EMPTY": 11, "LANG_INVALID": 12,
    "LANG_EN": 13, "KEYWORD_TYPO": 14, "KEYWORD_NON_ASCII": 15, "KEYWORD_UNPROCESSED": 16,
    "UNRECOGNIZED_LINE": 17, "BRACKETS": 18, "AXIS_TAG_TYPO": 19, "AXIS_RANGE_INVALID": 20,
    "AXIS_RANGE_LABEL": 21, "MAPPING_LABEL_TYPO": 22, "MAPPING_OUT_OF_RANGE": 23,
    "MAPPING_EXTREME_MISSING": 24, "NO_ELIDABLE": 25, "MAPPING_INCOMPLETE": 26,
    "MAPPING_NONSTANDARD_USER": 27, "MAPPING_USER_TWICE": 28, "BARE_LABEL_CONTINUOUS": 29,
    "HIDDEN_AXIS_INVALID": 30, "SOURCE_COORD_COUNT": 31, "SOURCE_UNKNOWN_LABEL": 32,
    "SOURCE_UNKNOWN_AXIS": 33, "SOURCE_COORD_INVALID": 34, "SOURCE_OFF_MAPPING": 35,
    "SOURCE_EXTREME_MISSING": 36, "RULE_SYNTAX": 37, "RULE_CONDITION": 38,
    "INSTANCE_LINE_IGNORED": 39, "AVAR2_MATRIX_ROW_LENGTH": 40, "AVAR2_UNDEFINED_VAR": 41,
    "AVAR2_UNKNOWN_AXIS": 42, "AVAR2_INVALID_VALUE": 43, "AVAR2_UNKNOWN_LABEL": 44,
    "AVAR2_INPUT_OUT_OF_RANGE": 45, "AVAR2_SYNTAX": 46, "SKIP_UNKNOWN_LABEL": 47,
    "ELIDED_FALLBACK_EMPTY": 48, "SOURCE_UFO_MISSING": 49, "SOURCE_LAYER_MISSING": 50,
    "RULE_GLYPH_MISSING": 51, "RULE_TARGET_MISSING": 52, "RULE_MATCHES_NOTHING": 53,
    "AVAR2_DEFAULT_INPUT": 54, "AVAR2_OUTPUT_OUT_OF_RANGE": 55, "AVAR2_DUPLICATE_INPUT": 56,
    "AVAR2_OUTPUT_ONLY_VISIBLE": 57, "AVAR2_HIDDEN_INPUT": 58, "RULES_MODE_UNKNOWN": 59,
    "INSTANCE_FIELD_INVALID": 60, "INSTANCE_LOCATION_INVALID": 61, "INSTANCE_NO_LOCATION": 62,
    "INSTANCE_OFF_IGNORED": 63, "INSTANCE_DUPLICATE": 64, "INSTANCE_SHADOWS_AUTO": 65,
}


def test_codes_are_append_only():
    current = {name: code.number for name, code in codes.CODES.items()}
    for name, number in PUBLISHED.items():
        assert current.get(name) == number, name
    numbers = list(current.values())
    assert len(numbers) == len(set(numbers))


def test_ids_and_lookup():
    code = codes.CODES["SOURCE_COORD_COUNT"]
    assert code.id == "5.31"
    assert codes.lookup("5.31") is code and codes.lookup("SOURCE_COORD_COUNT") is code
    assert codes.classify("nothing we know") is codes.UNCLASSIFIED


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
"""


def variant(old, new):
    assert old in GOOD
    return GOOD.replace(old, new, 1)


@pytest.mark.parametrize(
    "name, text",
    [
        ("NO_BASE", variant("T-Regular [Regular, Upright] @base", "T-Regular [Regular, Italic]")),
        ("MULTIPLE_BASE", variant("T-Black [Black, Upright]", "T-Black [Black, Upright] @base")),
        ("DUPLICATE_LABEL", variant("        Italic\n", "        Italic\n        Thin\n")),
        ("BASE_AUTO_DETECTED", variant(" @base", "")),
        ("FAMILY_EMPTY", variant("family T", "family")),
        ("LANG_INVALID", variant("family T", "family T\nlang 12")),
        ("LANG_EN", variant("family T", "family T\nlang en, de")),
        ("KEYWORD_TYPO", variant("family T", "familly T")),
        ("AXIS_TAG_TYPO", variant("wght 100", "wgth 100")),
        ("AXIS_RANGE_INVALID", variant("wght 100:400:900", "wght 900:400:100")),
        ("AXIS_RANGE_LABEL", variant("wght 100:400:900", "wght Thin:Foo:Black")),
        ("MAPPING_LABEL_TYPO", variant("Regular > 400", "Reguler > 400")),
        ("MAPPING_EXTREME_MISSING", variant("        Black > 900\n", "        Bold > 900\n").replace("Black", "Bold")),
        ("NO_ELIDABLE", variant("Regular > 400 @elidable", "Regular > 400")),
        ("MAPPING_NONSTANDARD_USER", variant("Black > 900", "800 Black > 900")),
        ("BARE_LABEL_CONTINUOUS", variant("        Black > 900\n", "        Black > 900\n        Bold\n")),
        ("SOURCE_COORD_COUNT", variant("T-Black [Black, Upright]", "T-Black [Black]")),
        ("SOURCE_UNKNOWN_LABEL", variant("T-Black [Black, Upright]", "T-Black [Bolt, Upright]")),
        ("SOURCE_OFF_MAPPING", variant("T-Black [Black, Upright]", "T-Black [Black, Upright]\n    T-Mid [600, Upright]")),
        ("RULE_CONDITION", variant("weight >= Black", "weight >= Bolt")),
        ("INSTANCE_LINE_IGNORED", variant("instances auto", "instances auto\nT Bold")),
        ("AVAR2_UNDEFINED_VAR", GOOD + "avar2\n    [wght=Black] > wght=$NOPE\n"),
        ("AVAR2_UNKNOWN_LABEL", GOOD + "avar2\n    [wght=Bolt] > wght=700\n"),
        ("AVAR2_SYNTAX", GOOD + "avar2\n    wght=Bolt > wght=700\n"),
        ("AVAR2_MATRIX_ROW_LENGTH", GOOD + "avar2 matrix\n    outputs wght\n    [wght=Black] 1 2\n"),
        ("NO_AXES", "family T\nsources\n    A @base\n"),
        ("SKIP_UNKNOWN_LABEL", variant("instances auto", "instances auto\n    skip\n        Bolt Italic")),
        ("ELIDED_FALLBACK_EMPTY", variant("family T", "family T\nelidedfallback")),
        ("AVAR2_UNKNOWN_AXIS", GOOD + "avar2\n    [wght=Black] > XHDI=80\n"),
        ("AVAR2_INPUT_OUT_OF_RANGE", GOOD + "avar2\n    [wght=1200] > wght=700\n"),
        ("AVAR2_DEFAULT_INPUT", GOOD + "avar2\n    [wght=Regular] > wght=500\n"),
        ("AVAR2_OUTPUT_OUT_OF_RANGE", GOOD + "avar2\n    [wght=Black] > wght=1200\n"),
        ("AVAR2_DUPLICATE_INPUT", GOOD + "avar2\n    [wght=Black] > wght=800\n    [wght=900] > wght=850\n"),
        ("AVAR2_OUTPUT_ONLY_VISIBLE", variant("    ital discrete", "    XOPQ 0:50:100\n    ital discrete") + "avar2\n    [wght=Black] > XOPQ=80\n"),
        ("AVAR2_HIDDEN_INPUT", GOOD + "axes hidden\n    XOPQ 0:50:100\navar2\n    [XOPQ=80] > wght=800\n"),
        ("RULES_MODE_UNKNOWN", GOOD + "rules lats\n    a > a.alt (weight >= Black)\n"),
        ("INSTANCE_FIELD_INVALID", variant("instances auto", "instances auto\n    Wide\n        locaton: wght=700")),
        ("INSTANCE_FIELD_INVALID", variant("instances auto", "instances auto\n    Wide\n        location wght=700")),
        ("INSTANCE_LOCATION_INVALID", variant("instances auto", "instances auto\n    Wide\n        location: wdth=700")),
        ("INSTANCE_LOCATION_INVALID", variant("instances auto", "instances auto\n    Wide\n        location: wght=Bolt")),
        ("INSTANCE_NO_LOCATION", variant("instances auto", "instances auto\n    Wide\n        style: Wide")),
        ("INSTANCE_OFF_IGNORED", variant("instances auto", "instances off\n    Wide\n        location: wght=700")),
        ("INSTANCE_DUPLICATE", variant("instances auto", "instances\n    Wide\n        location: wght=700\n"
                                       "    Wide\n        location: wght=800")),
        ("INSTANCE_SHADOWS_AUTO", variant("instances auto", "instances auto\n    Wide\n        location: wght=Black")),
    ],
)
def test_message_gets_its_code(name, text):
    wanted = codes.CODES[name].id
    found = {d.code for d in diagnose(text)}
    assert wanted in found, [(d.code, d.message) for d in diagnose(text)]


def test_clean_sketch_has_no_diagnostics():
    assert diagnose(GOOD) == []


def test_every_example_message_is_classified():
    from pathlib import Path

    for path in sorted((Path(__file__).parent.parent / "examples").glob("*.dssketch")):
        for d in diagnose(path.read_text(encoding="utf-8")):
            assert d.code != "5.0", (path.name, d.message)
