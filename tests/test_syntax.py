"""Editor support: tokenize() for highlighting, diagnose() for positioned errors.

The tokenizer follows the parser's decisions, so the examples are checked both
for coverage (every character in exactly one token) and for agreement with
what DSSParser makes of the same text.
"""

import glob
import os

import pytest

from dssketch import DSSParser, diagnose, tokenize
from dssketch.syntax import (
    AXIS_NAME,
    AXIS_TAG,
    COMMENT,
    FLAG,
    GLYPH,
    KEYWORD,
    LABEL,
    NUMBER,
    OPERATOR,
    PUNCTUATION,
    SOURCE,
    STRING,
    TEXT,
    TOKEN_TYPES,
    UNKNOWN,
    VARIABLE,
)

EXAMPLES = sorted(
    glob.glob(os.path.join(os.path.dirname(__file__), "..", "examples", "*.dssketch"))
)


def _types(text, line=None):
    """[(text, type)] of the tokens, of one line when given, comments left out"""
    return [
        (t.text, t.type)
        for t in tokenize(text)
        if t.type != COMMENT and (line is None or t.line == line)
    ]


def _line(snippet, section="axes"):
    """Types of the last line of a snippet placed in a section"""
    text = f"{section}\n{snippet}"
    return _types(text, line=text.count("\n") + 1)


# -- examples ---------------------------------------------------------------------


@pytest.mark.parametrize("path", EXAMPLES, ids=os.path.basename)
def test_examples_are_covered_without_unknowns(path):
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    seen = {}
    for token in tokenize(text):
        assert token.type in TOKEN_TYPES
        assert lines[token.line - 1][token.column : token.column + token.length] == token.text
        assert token.type != UNKNOWN, token
        for column in range(token.column, token.column + token.length):
            key = (token.line, column)
            assert key not in seen, f"overlap at {key}"
            seen[key] = token
    for line_no, line in enumerate(lines, 1):
        for column, char in enumerate(line):
            if not char.isspace():
                assert (line_no, column) in seen, f"{path}:{line_no}:{column} not covered"


@pytest.mark.parametrize("path", EXAMPLES, ids=os.path.basename)
def test_examples_agree_with_parser(path):
    text = open(path, encoding="utf-8").read()
    doc = DSSParser().parse(text)
    tokens = tokenize(text)

    assert sum(t.type == SOURCE for t in tokens) == len(doc.sources)

    def_lines = {t.line for t in tokens if t.type in (AXIS_TAG, AXIS_NAME) and _is_axis_def(t, tokens)}
    assert len(def_lines) == len(doc.axes) + len(doc.hidden_axes)

    labels = {t.text for t in tokens if t.type == LABEL}
    for axis in doc.axes:
        for mapping in axis.mappings:
            for word in mapping.label.split():
                assert word in labels


def _is_axis_def(token, tokens):
    """An axis tag/name on a line that also has a range or discrete keyword"""
    same_line = [t for t in tokens if t.line == token.line]
    return any(t.text == ":" for t in same_line) or any(
        t.type == KEYWORD and t.text in ("discrete", "binary") for t in same_line
    )


def test_tokens_are_in_order():
    text = open(EXAMPLES[0], encoding="utf-8").read()
    tokens = tokenize(text)
    assert tokens == sorted(tokens, key=lambda t: (t.line, t.column))


# -- document lines ---------------------------------------------------------------


def test_family_path_lang():
    assert _types("family Sans Pro") == [("family", KEYWORD), ("Sans Pro", TEXT)]
    assert _types('family "Roboto Delta"') == [("family", KEYWORD), ('"Roboto Delta"', STRING)]
    assert _types("path sources") == [("path", KEYWORD), ("sources", TEXT)]
    assert _types("lang de, ru") == [
        ("lang", KEYWORD), ("de", TEXT), (",", PUNCTUATION), ("ru", TEXT),
    ]


def test_comment_starts_at_first_hash_like_the_parser():
    tokens = tokenize('family "A#B"  # note')
    assert [(t.text, t.type) for t in tokens] == [
        ("family", KEYWORD), ('"A', STRING), ("#B\"  # note", COMMENT),
    ]


def test_indented_keyword_is_not_a_section():
    # The parser only reads section keywords at the start of a line
    assert _types("  axes")[0][1] == UNKNOWN


# -- axes -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line, expected",
    [
        ("    wght 100:400:900", [("wght", AXIS_TAG)]),
        ("    weight 100:400:900", [("weight", AXIS_NAME)]),
        ("    weight wght 100:400:900", [("weight", AXIS_NAME), ("wght", AXIS_TAG)]),
        ("    CONTRAST CNTR 0:0:100", [("CONTRAST", AXIS_NAME), ("CNTR", AXIS_TAG)]),
        ("    OPTICAL SIZE opsz 8:14:144", [("OPTICAL", AXIS_NAME), ("SIZE", AXIS_NAME), ("opsz", AXIS_TAG)]),
        ("    ital discrete", [("ital", AXIS_TAG), ("discrete", KEYWORD)]),
        ("    ital binary", [("ital", AXIS_TAG), ("binary", KEYWORD)]),
    ],
)
def test_axis_definitions(line, expected):
    assert _line(line)[: len(expected)] == expected


def test_axis_range_values_and_display_name():
    assert _line('    wght Thin:Regular:Black "Weight"') == [
        ("wght", AXIS_TAG), ("Thin", LABEL), (":", PUNCTUATION), ("Regular", LABEL),
        (":", PUNCTUATION), ("Black", LABEL), ('"Weight"', STRING),
    ]
    assert [t for t, k in _line("    slnt -20:0:20") if k == NUMBER] == ["-20", "0", "20"]


@pytest.mark.parametrize(
    "line, expected",
    [
        ("Light > 300", [("Light", LABEL), (">", OPERATOR), ("300", NUMBER)]),
        ("200 Light > 230", [("200", NUMBER), ("Light", LABEL), (">", OPERATOR), ("230", NUMBER)]),
        ("100 > 100", [("100", NUMBER), (">", OPERATOR), ("100", NUMBER)]),
        ("Regular > 400 @elidable", [("Regular", LABEL), (">", OPERATOR), ("400", NUMBER), ("@elidable", FLAG)]),
        ("Upright @elidable", [("Upright", LABEL), ("@elidable", FLAG)]),
        ("-20 Reverse > -20", [("-20", NUMBER), ("Reverse", LABEL), (">", OPERATOR), ("-20", NUMBER)]),
    ],
)
def test_axis_mappings(line, expected):
    assert _line("    wght 100:400:900\n        " + line) == expected


def test_mapping_with_non_number_design_value_is_unknown():
    assert _line("    wght 100:400:900\n        Black > abc")[-1] == ("abc", UNKNOWN)


def test_hidden_axes():
    assert _line("    XOUC 4:90:310", section="axes hidden")[0] == ("XOUC", AXIS_TAG)
    assert _types("axes hidden") == [("axes", KEYWORD), ("hidden", KEYWORD)]


# -- sources ----------------------------------------------------------------------


def test_sources_header():
    assert _types("sources [wght, ital]") == [
        ("sources", KEYWORD), ("[", PUNCTUATION), ("wght", AXIS_TAG), (",", PUNCTUATION),
        ("ital", AXIS_TAG), ("]", PUNCTUATION),
    ]


def test_positional_source():
    assert _line("    upright/Font-Thin.ufo [Thin, 0] @base", "sources") == [
        ("upright/Font-Thin.ufo", SOURCE), ("[", PUNCTUATION), ("Thin", LABEL),
        (",", PUNCTUATION), ("0", NUMBER), ("]", PUNCTUATION), ("@base", FLAG),
    ]


def test_source_name_with_spaces_is_one_token():
    assert _line("    My Font Light.ufo [0]", "sources")[0] == ("My Font Light.ufo", SOURCE)
    assert _line('    "My Font Light.ufo" [0]', "sources")[0] == ('"My Font Light.ufo"', SOURCE)


def test_named_source():
    assert _line("    Font-Bold wght=700, wdth=Condensed @sparse", "sources") == [
        ("Font-Bold", SOURCE), ("wght", AXIS_TAG), ("=", PUNCTUATION), ("700", NUMBER),
        (",", PUNCTUATION), ("wdth", AXIS_TAG), ("=", PUNCTUATION), ("Condensed", LABEL),
        ("@sparse", FLAG),
    ]


def test_defaults_only_source():
    assert _line("    Font-Regular @base", "sources") == [("Font-Regular", SOURCE), ("@base", FLAG)]


@pytest.mark.parametrize(
    "flag, value",
    [('@layer="bold layer"', ('"bold layer"', STRING)),
     ("@layer 'bold'", ("'bold'", STRING)),
     ("@layer=bold", ("bold", TEXT))],
)
def test_layer_forms(flag, value):
    tokens = _line(f"    Font.ufo [700] {flag}", "sources")
    assert ("@layer", FLAG) in tokens and value in tokens
    assert tokens[0] == ("Font.ufo", SOURCE)


# -- rules and instances ----------------------------------------------------------


def test_rule_with_labels_and_compound_condition():
    text = (
        "axes\n    wght 100:400:900\n    wdth 75:100:125\nrules\n"
        '    dollar cent* > .rvrn (Regular <= weight <= Bold && wdth >= 90) "heavy"'
    )
    assert _types(text, line=5) == [
        ("dollar", GLYPH), ("cent*", GLYPH), (">", OPERATOR), (".rvrn", GLYPH),
        ("(", PUNCTUATION), ("Regular", LABEL), ("<=", OPERATOR), ("weight", AXIS_TAG),
        ("<=", OPERATOR), ("Bold", LABEL), ("&&", OPERATOR), ("wdth", AXIS_TAG),
        (">=", OPERATOR), ("90", NUMBER), (")", PUNCTUATION), ('"heavy"', STRING),
    ]


def test_rule_condition_on_custom_axis():
    text = "axes\n    CONTRAST CNTR 0:0:100\nrules\n    a > a.alt (CONTRAST >= 50)"
    assert ("CONTRAST", AXIS_TAG) in _types(text, line=4)


def test_instances_and_skip():
    text = "instances auto\n    skip\n        Bold Italic\n        Thin Italic"
    assert _types(text, line=1) == [("instances", KEYWORD), ("auto", KEYWORD)]
    assert _types(text, line=2) == [("skip", KEYWORD)]
    assert _types(text, line=3) == [("Bold", LABEL), ("Italic", LABEL)]
    assert _types("instances off") == [("instances", KEYWORD), ("off", KEYWORD)]


# -- avar2 ------------------------------------------------------------------------


def test_avar2_linear_and_block():
    text = (
        "avar2\n"
        '    "opsz144" [opsz=Display] > XOUC=84, YTUC=$\n'
        "    [wght=100] > {\n"
        "        XOUC=$XOUC\n"
        "    }"
    )
    assert _types(text, line=2) == [
        ('"opsz144"', STRING), ("[", PUNCTUATION), ("opsz", AXIS_TAG), ("=", PUNCTUATION),
        ("Display", LABEL), ("]", PUNCTUATION), (">", OPERATOR), ("XOUC", AXIS_TAG),
        ("=", PUNCTUATION), ("84", NUMBER), (",", PUNCTUATION), ("YTUC", AXIS_TAG),
        ("=", PUNCTUATION), ("$", VARIABLE),
    ]
    assert ("{", PUNCTUATION) in _types(text, line=3)
    assert _types(text, line=4) == [("XOUC", AXIS_TAG), ("=", PUNCTUATION), ("$XOUC", VARIABLE)]
    assert _types(text, line=5) == [("}", PUNCTUATION)]


def test_avar2_vars():
    assert _line("    $YTUC = 725", "avar2 vars") == [
        ("$YTUC", VARIABLE), ("=", PUNCTUATION), ("725", NUMBER),
    ]


def test_avar2_matrix():
    text = "avar2 matrix\n    outputs XOUC XOLC\n    [wght=Bold]  84  -"
    assert _types(text, line=1) == [("avar2", KEYWORD), ("matrix", KEYWORD)]
    assert _types(text, line=2) == [("outputs", KEYWORD), ("XOUC", AXIS_TAG), ("XOLC", AXIS_TAG)]
    assert _types(text, line=3)[-2:] == [("84", NUMBER), ("-", PUNCTUATION)]


# -- diagnose ---------------------------------------------------------------------

VALID = """\
family Test
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    Test-Thin [Thin]
    Test-Regular [Regular] @base
    Test-Black [Black]
instances auto
"""


def _at(text, diagnostic):
    line = text.split("\n")[diagnostic.line - 1]
    return line[diagnostic.column : diagnostic.end_column]


def test_valid_sketch_has_no_errors():
    assert [d for d in diagnose(VALID) if d.severity == "error"] == []


def test_keyword_typo_points_at_the_word():
    text = VALID.replace("family Test", "familly Test")
    [d] = [d for d in diagnose(text) if d.severity == "error"]
    assert (d.line, _at(text, d)) == (1, "familly")
    assert "Did you mean 'family'" in d.message


def test_unknown_label_points_at_the_label_not_the_source():
    text = VALID.replace("Test-Thin [Thin]", "Test-Thin [Bolt]")
    [d] = [d for d in diagnose(text) if d.severity == "error"]
    assert (d.line, _at(text, d)) == (8, "Bolt")


def test_all_failing_lines_are_reported():
    text = VALID.replace("Black > 900", "Black > abc").replace("Test-Thin [Thin]", "Test-Thin [Bolt]")
    errors = [d for d in diagnose(text) if d.severity == "error" and d.line]
    assert [d.line for d in errors][:2] == [6, 8]
    assert _at(text, errors[0]) == "abc"


def test_document_level_messages_have_no_line():
    text = "family Test\nsources\n    Test-Regular @base\n"
    critical = [d for d in diagnose(text) if d.message.startswith("CRITICAL:")]
    assert critical and all(d.line is None for d in critical)


def test_document_messages_come_after_line_messages():
    text = VALID.replace("Test-Thin [Thin]", "Test-Thin [Bolt]")
    lines = [d.line for d in diagnose(text)]
    first_none = lines.index(None) if None in lines else len(lines)
    assert all(line is None for line in lines[first_none:])


@pytest.mark.parametrize(
    "text", ["", "\x00]]][[ >>> @@@", "axes\n  wght ::::", "sources\n [", "avar2\n [ > {"]
)
def test_diagnose_never_raises(text):
    for d in diagnose(text):
        assert d.severity in ("error", "warning")


def test_parse_still_raises_by_default():
    with pytest.raises(ValueError, match="Error parsing line 6"):
        DSSParser().parse(VALID.replace("Black > 900", "Black > abc"))
