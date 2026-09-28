"""
An unquoted value with spaces is taken whole, never cut to its first word.

Quoting stays valid, but "family Sans Pro" is an ordinary way to write a name,
and truncating it was silent: three sources "My Font Light.ufo", "My Font
Regular.ufo" and "My Font Black" all became the same "My.ufo".
"""

from dssketch import DSSParser, DSSWriter

SKETCH = """\
family Sans Pro  # a trailing comment is not part of the name
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    My Font Light.ufo [Thin]
    My Font Regular.ufo [Regular] @base @layer="fg"
    My Font Black @sparse
"""


def _parse(text):
    return DSSParser(strict_mode=False).parse(text)


def test_unquoted_family_keeps_every_word():
    assert _parse(SKETCH).family == "Sans Pro"


def test_quoted_family_unchanged():
    assert _parse(SKETCH.replace("family Sans Pro", 'family "Sans Pro"')).family == "Sans Pro"


def test_unquoted_source_names_keep_every_word():
    doc = _parse(SKETCH)
    assert [(s.filename, s.layer, s.is_base, s.is_sparse) for s in doc.sources] == [
        ("My Font Light.ufo", None, False, False),
        ("My Font Regular.ufo", "fg", True, False),
        ("My Font Black.ufo", None, False, True),
    ]


def test_roundtrip_quotes_names_with_spaces():
    doc = _parse(SKETCH)
    out = DSSWriter().write(doc)
    assert 'family "Sans Pro"' in out
    again = _parse(out)
    assert again.family == doc.family
    assert [s.filename for s in again.sources] == [s.filename for s in doc.sources]
