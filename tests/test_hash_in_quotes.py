"""`#` inside a closed quoted string is text, not a comment (1.5.0)."""

import pytest

from dssketch import DSSParser
from dssketch.utils.comments import comment_start


@pytest.mark.parametrize(
    "line, at",
    [
        ("family Sans # note", 12),
        ('family "A#B" # note', 13),
        ('family "A#B"', -1),
        ('family "A # note', 10),
        ("    F.ufo [400] @layer='v#2' # x", 29),
        ("family Joe's #1", 13),
        ("# whole line", 0),
        ("", -1),
    ],
)
def test_comment_start(line, at):
    assert comment_start(line) == at


SKETCH = """family "Sans #1"  # the family
axes
    wght 100:400:900 "Weight #A"
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    Master [Regular] @base
    Master [Black] @layer="black #2"  # a layer
rules
    dollar > dollar.alt (weight >= Black) "dollar #1"
instances off
"""


def test_parser_keeps_hash_in_quoted_values():
    doc = DSSParser().parse(SKETCH)
    assert doc.family == "Sans #1"
    assert doc.axes[0].display_name == "Weight #A"
    assert doc.sources[1].layer == "black #2"
    assert doc.rules[0].name == "dollar #1"
