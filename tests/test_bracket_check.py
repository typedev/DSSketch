"""The bracket check reads code only, not comments or quoted names (1.5.1)."""

import pytest

from dssketch import codes, diagnose

BASE = """\
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
    dollar > dollar.alt (weight >= Black) "d"
instances auto
"""

BRACKETS = codes.CODES["BRACKETS"].id


def brackets(text):
    return [d for d in diagnose(text) if d.code == BRACKETS]


@pytest.mark.parametrize(
    "old, new",
    [
        ("instances auto", '    # "A B" -> "A" (A, B elided)\ninstances auto'),
        ('(weight >= Black) "d"', '(weight >= Black) "heavy, dollar"'),
        ('(weight >= Black) "d"', '(weight >= Black) "[x]"'),
        ('(weight >= Black) "d"', '(weight >= Black)  # see (notes, p2) [old]'),
        ("T-Black [Black, Upright]", "T-Black [Black, Upright]  # black (final, v2)"),
    ],
)
def test_no_warning_for_text(old, new):
    assert old in BASE
    assert brackets(BASE.replace(old, new, 1)) == []


def test_wrong_brackets_on_coordinates_are_still_caught():
    text = BASE.replace("T-Black [Black, Upright]", "T-Black (Black, Upright)")
    assert brackets(text)


def test_examples_have_no_bracket_warnings():
    from pathlib import Path

    for path in (Path(__file__).parent.parent / "examples").glob("*.dssketch"):
        assert brackets(path.read_text(encoding="utf-8")) == [], path.name
