"""Runs of spaces and tabs inside a line count as one space, except in quotes.

normalize_whitespace() used the pattern r"\\s+" (a literal backslash and s), so
nothing was collapsed: `axes  hidden` declared visible axes and a skip line
with two spaces never matched.
"""

from dssketch import DSSParser, tokenize
from dssketch.syntax import KEYWORD
from dssketch.utils.dss_validator import DSSValidator

normalize = DSSValidator.normalize_whitespace


def test_internal_runs_collapse_and_indent_stays():
    assert normalize("    Bold  \t Italic") == "    Bold Italic"
    assert normalize("axes\thidden") == "axes hidden"


def test_quoted_text_is_kept():
    assert normalize('    "My  Font.ufo"  [0]') == '    "My  Font.ufo" [0]'
    assert normalize("    Font.ufo [0]  @layer='bold  layer'") == "    Font.ufo [0] @layer='bold  layer'"


BASE = """\
family Test
axes
    wght 100:400:700
        Thin > 100
        Regular > 400 @elidable
        Bold > 700
    ital discrete
        Upright @elidable
        Italic
{extra}
sources [wght, ital]
    {name} [Regular, Upright] @base{layer}
    Test-Bold [Bold, Upright]
    Test-Thin [Thin, Upright]
    Test-Italic [Regular, Italic]
    Test-BoldItalic [Bold, Italic]
    Test-ThinItalic [Thin, Italic]
instances auto
    skip
        Bold  Italic
"""


def _parse(extra="", name="Test-Regular", layer=""):
    return DSSParser().parse(BASE.format(extra=extra, name=name, layer=layer))


def test_double_space_in_section_header():
    doc = _parse(extra="axes  hidden\n    XOUC 0:100:200")
    assert [a.name for a in doc.hidden_axes] == ["XOUC"]


def test_double_space_in_skip_line():
    assert _parse().instances_skip == ["Bold Italic"]


def test_quoted_source_name_and_layer_keep_their_spaces():
    doc = _parse(name='"My  Font.ufo"', layer=' @layer="bold  layer"')
    assert doc.sources[0].filename == "My  Font.ufo"
    assert doc.sources[0].layer == "bold  layer"


def test_tokenizer_agrees():
    tokens = tokenize("axes  hidden\n    XOUC 0:100:200")
    assert [(t.text, t.type) for t in tokens[:2]] == [("axes", KEYWORD), ("hidden", KEYWORD)]
