"""Spans, item_at and lossless reading of hand-written texts (1.5.0)."""

import time
from pathlib import Path

import pytest

from dssketch import DSSParser, Sketch, SourceKey, Span, syntax
from dssketch import structure as st

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.dssketch"))

EVERY_FORM = """\
family "Sans #1"  # note
suffix VF
lang de, ru
path sources
axes
    weight wght 100:400:900 "Weight"
        100 > 100
        200 Thin > 175
        Regular > 400 @elidable
        Black > 900
    CONTRAST CNTR 0:0:100
        0 Flat > 0 @elidable
        100 Sharp > 100
    ital discrete
        Upright @elidable
        Italic
axes hidden
    XOUC 0:100:200
sources [wght, CNTR, ital]
    upright/Font-Thin.ufo [Thin, Flat, Upright]
    "My Font Light.ufo" [100, 0, 0] @sparse
    Font-Regular [Regular, Flat, Upright] @base
    Font-Bold.ufo [Black, Sharp, Italic] @layer="fg #2"
rules
    dollar cent* > .rvrn (Regular <= weight <= Black && CONTRAST >= 50) "heavy"
instances auto
    skip
        Black Italic
avar2 vars
    $XO = 50
avar2
    "x" [wght=Black] > XOUC=$XO
    [wght=100] > {
        XOUC=20
    }
avar2 matrix
    outputs XOUC
    [CNTR=Sharp]  84
"""


def at(text, line, needle, offset=0):
    """(line, column) of `needle` on a line, for item_at"""
    return line, text.split("\n")[line - 1].index(needle) + offset


def field_text(text, span):
    line = text.split("\n")[span.line - 1]
    return line[span.col: span.end_col]


@pytest.fixture(scope="module")
def sk():
    return Sketch.parse(EVERY_FORM)


# -- structure ----------------------------------------------------------------


def test_every_line_is_classified(sk):
    kinds = [line.kind for line in sk.structure.lines]
    assert st.OTHER not in kinds
    assert kinds[:4] == [st.FAMILY, st.SUFFIX, st.LANG, st.PATH]
    assert kinds.count(st.AXIS) == 4 and kinds.count(st.MAPPING) == 8
    assert kinds.count(st.SOURCE_LINE) == 4 and kinds.count(st.AVAR2_BLOCK) == 2


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_structure(path):
    text = path.read_text(encoding="utf-8")
    sketch = Sketch.parse(text)
    assert sketch.text == text
    kinds = {line.kind for line in sketch.structure.lines}
    assert st.OTHER not in kinds
    doc = sketch.document
    # every parsed object found its line and got spans
    for axis in list(doc.axes) + list(doc.hidden_axes):
        assert axis.span is not None and "tag" in axis.spans
        for mapping in axis.mappings:
            assert mapping.span is not None
    for source in doc.sources:
        assert "name" in source.spans
        assert source.span is not None
    for rule in doc.rules:
        assert "pattern" in rule.spans
    for mapping in doc.avar2_mappings:
        assert mapping.span is not None


# -- spans --------------------------------------------------------------------


def test_axis_field_spans(sk):
    axis = sk.axis("wght")
    assert axis.span == Span(6, 4, 6, 36)
    assert {k: field_text(EVERY_FORM, v) for k, v in axis.spans.items()} == {
        "name": "weight", "tag": "wght", "min": "100", "default": "400", "max": "900",
        "range": "100:400:900", "display_name": '"Weight"',
    }
    assert field_text(EVERY_FORM, sk.axis("ital").spans["discrete"]) == "discrete"


def test_mapping_field_spans(sk):
    thin = sk.mapping("wght", "Thin")
    assert {k: field_text(EVERY_FORM, v) for k, v in thin.spans.items()} == {
        "user": "200", "label": "Thin", "design": "175",
    }
    regular = sk.mapping("wght", "Regular")
    assert field_text(EVERY_FORM, regular.spans["elidable"]) == "@elidable"
    unnamed = sk.mapping("wght", 100)
    assert set(unnamed.spans) == {"user", "design"}


def test_source_field_spans_by_axis_tag(sk):
    bold = sk.source("Font-Bold.ufo")
    texts = {k: field_text(EVERY_FORM, v) for k, v in bold.spans.items()}
    assert texts["coord.wght"] == "Black" and texts["coord.CNTR"] == "Sharp" and texts["coord.ital"] == "Italic"
    assert texts["layer"] == '@layer="fg #2"' and texts["layer_name"] == '"fg #2"'
    assert texts["name"] == "Font-Bold.ufo"
    light = sk.source("My Font Light.ufo")
    assert field_text(EVERY_FORM, light.spans["name"]) == '"My Font Light.ufo"'
    assert field_text(EVERY_FORM, light.spans["sparse"]) == "@sparse"


def test_rule_spans(sk):
    rule = sk.document.rules[0]
    texts = {k: field_text(EVERY_FORM, v) for k, v in rule.spans.items()}
    assert texts["pattern"] == "dollar cent*"
    assert texts["target"] == ".rvrn"
    assert texts["condition.0"] == "Regular <= weight <= Black"
    assert texts["condition.1"] == "CONTRAST >= 50"
    assert texts["name"] == '"heavy"'


def test_avar2_spans(sk):
    linear, block, matrix = sk.document.avar2_mappings
    assert field_text(EVERY_FORM, linear.spans["input.wght"]) == "Black"
    assert field_text(EVERY_FORM, linear.spans["output.XOUC"]) == "$XO"
    assert block.span.line == 33 and block.span.end_line == 35
    assert field_text(EVERY_FORM, block.spans["output.XOUC"]) == "20"
    assert field_text(EVERY_FORM, matrix.spans["output.XOUC"]) == "84"
    assert field_text(EVERY_FORM, matrix.spans["input.CNTR"]) == "Sharp"


def test_span_paths(sk):
    assert field_text(EVERY_FORM, sk.span(("family", "value"))) == '"Sans #1"'
    assert field_text(EVERY_FORM, sk.span(("source", "Font-Bold.ufo", "coord", "CNTR"))) == "Sharp"
    assert field_text(EVERY_FORM, sk.span(("skip", "Black Italic"))) == "Black Italic"
    assert field_text(EVERY_FORM, sk.span(("avar2_var", "XO", "value"))) == "50"
    assert field_text(EVERY_FORM, sk.span(("instances", "mode"))) == "auto"
    assert sk.span(("source", "Nope")) is None
    assert sk.span(("nonsense",)) is None


# -- item_at ------------------------------------------------------------------


@pytest.mark.parametrize(
    "line, needle, expected",
    [
        (1, "Sans", ("family", "value")),
        (6, "wght", ("axis", "wght", "tag")),
        (6, "400", ("axis", "wght", "default")),
        (6, "Weight", ("axis", "wght", "display_name")),
        (8, "Thin", ("mapping", "wght", "Thin", "label")),
        (8, "175", ("mapping", "wght", "Thin", "design")),
        (7, "100 >", ("mapping", "wght", 100.0, "user")),
        (9, "@elidable", ("mapping", "wght", "Regular", "elidable")),
        (18, "XOUC", ("axis", "XOUC", "tag")),
        (20, "Flat", ("source", SourceKey("upright/Font-Thin.ufo"), "coord", "CNTR")),
        (22, "@base", ("source", SourceKey("Font-Regular.ufo"), "base")),
        (23, "fg", ("source", SourceKey("Font-Bold.ufo", "fg #2"), "layer")),
        (25, "cent", ("rule", 0, "pattern")),
        (25, "CONTRAST", ("rule", 0, "condition.1")),
        (26, "auto", ("instances", "mode")),
        (28, "Black", ("skip", "Black Italic")),
        (30, "50", ("avar2_var", "XO", "value")),
        (32, "Black", ("avar2", 0, "input", "wght")),
        (34, "20", ("avar2", 1, "output", "XOUC")),
        (38, "84", ("avar2", 2, "output", "XOUC")),
        (37, "XOUC", None),
    ],
)
def test_item_at(sk, line, needle, expected):
    assert sk.item_at(*at(EVERY_FORM, line, needle, 1)) == expected


def test_item_at_outside_anything(sk):
    assert sk.item_at(1, 20) is None  # in the comment
    assert sk.item_at(999, 0) is None
    assert sk.item_at(-1, 0) is None


def test_item_at_and_span_agree(sk):
    for line_no, raw in enumerate(EVERY_FORM.split("\n"), 1):
        for col in range(len(raw)):
            path = sk.item_at(line_no, col)
            if path is None or len(path) < 3:
                continue
            span = sk.span(path)
            assert span is not None and span.contains(line_no, col), (path, line_no, col)


# -- lossless: comments in every position ------------------------------------


def _meaning(text):
    """What a text says, comments aside"""
    parser = DSSParser(strict_mode=False, recover=True)
    try:
        doc = parser.parse(text)
    except Exception:
        doc = parser.document
    return doc, sorted(parser.validator.errors)


def _with_comments(text, trailing=True, full=True):
    out = []
    for i, line in enumerate(text.split("\n")):
        if full and i and line.strip():
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}# before line {i + 1} [x] (y) {{z}} > @base \"q\"")
        out.append(line + (f"  # after {i + 1} > @layer=x" if trailing and line.strip() and "#" not in line else ""))
    return "\n".join(out)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_comments_everywhere_change_nothing(path):
    text = path.read_text(encoding="utf-8")
    commented = _with_comments(text)
    sketch = Sketch.parse(commented)
    assert sketch.text == commented
    plain_doc, plain_errors = _meaning(text)
    doc, errors = _meaning(commented)
    assert doc == plain_doc
    assert errors == plain_errors
    plain_kinds = [ln.kind for ln in st.build(text).lines]
    kinds = [ln.kind for ln in sketch.structure.lines if ln.kind != st.COMMENT_LINE]
    assert kinds == [k for k in plain_kinds if k != st.COMMENT_LINE]


def test_comment_at_each_position_of_every_line():
    base = EVERY_FORM
    plain_doc, plain_errors = _meaning(base)
    lines = base.split("\n")
    for i, line in enumerate(lines):
        variants = [lines[:i] + ["# c"] + lines[i:]]
        if line.strip():
            variants.append(lines[:i] + [line + " # c"] + lines[i + 1:])
        for variant in variants:
            text = "\n".join(variant)
            doc, errors = _meaning(text)
            assert doc == plain_doc, (i, line)
            assert errors == plain_errors, (i, line)


def test_edits_keep_every_comment():
    text = _with_comments(EVERY_FORM, full=False)
    sketch = Sketch.parse(text)
    before = text.count("# after")
    for result in (
        sketch.set_family("Other"),
        sketch.set_source_coordinate("Font-Bold.ufo", "wght", 900, prefer="number"),
        sketch.add_mapping("wght", "Bold", 700),
        sketch.set_axis_display_name("wght", "W"),
        sketch.add_source("New", {"wght": 400}),
        sketch.set_mapping_elidable("wght", "Regular", False),
        sketch.rename_label("CNTR", "Sharp", "Crisp"),
    ):
        assert result.text.count("# after") == before


def test_remove_takes_only_owned_comments():
    text = (
        "family T\n"
        "axes\n"
        "    wght 100:400:900\n"
        "        Thin > 100\n"
        "        Regular > 400\n"
        "        # leads Bold\n"
        "        Bold > 700  # trailing Bold\n"
        "\n"
        "        # section comment\n"
        "\n"
        "        Black > 900\n"
        "sources [wght]\n"
        "    A [Regular] @base\n"
    )
    result = Sketch.parse(text).remove_mapping("wght", "Bold")
    assert "Bold" not in result.text
    assert "# section comment" in result.text


# -- diagnostics through the snapshot -----------------------------------------


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_sketch_diagnostics_match_diagnose(path):
    text = path.read_text(encoding="utf-8")
    assert Sketch.parse(text).diagnostics == syntax.diagnose(text)


def test_never_raises_on_garbage():
    for text in ["", "\n\n", "axes\n    ]]]\n", "sources [\n  [ > ( {", "\x00\x01", "avar2\n    [x=] > {"]:
        sketch = Sketch.parse(text)
        sketch.structure
        sketch.document
        sketch.diagnostics
        for line in range(0, 4):
            for col in range(0, 6):
                sketch.item_at(line, col)


# -- speed ----------------------------------------------------------------------


def test_benchmark_largest_example():
    """parse + diagnose of the largest example (~350 lines) well under 50 ms
    on a desktop; the bound here is loose for slow CI machines"""
    path = max(EXAMPLES, key=lambda p: len(p.read_text(encoding="utf-8").splitlines()))
    text = path.read_text(encoding="utf-8")
    best = None
    for _ in range(5):
        start = time.perf_counter()
        sketch = Sketch.parse(text)
        sketch.diagnostics
        elapsed = time.perf_counter() - start
        best = elapsed if best is None else min(best, elapsed)
    print(f"\n{path.name}: {len(text.splitlines())} lines, parse + diagnose {best * 1000:.1f} ms")
    assert best < 0.25

    sketch = Sketch.parse(text)
    sketch.diagnostics
    source = sketch.document.sources[3]
    start = time.perf_counter()
    sketch.set_sparse(Sketch.source_key(source), True)
    edit = time.perf_counter() - start
    print(f"one edit on a parsed sketch: {edit * 1000:.1f} ms")
    assert edit < 0.25
