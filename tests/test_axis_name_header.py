"""An axis header written with the axis name and a numeric range
(`weight 100:450:900`) resolves to the tag instead of crashing."""

import pytest

from dssketch import DSSParser
from dssketch.sketch import Sketch

TEXT = """family F
axes
    {header}
        Thin > 100
        Regular > 400 @elidable
        Black > 900
sources [wght]
    A [Regular] @base
"""


@pytest.mark.parametrize("header", ["weight 100:400:900", "Weight 100:400:900", "wght 100:400:900"])
def test_name_form_numeric_range(header):
    doc = DSSParser(strict_mode=False).parse(TEXT.format(header=header))
    (axis,) = doc.axes
    assert axis.tag == "wght"
    assert (axis.minimum, axis.default, axis.maximum) == (100, 400, 900)


def test_name_form_in_sketch():
    sketch = Sketch.parse(TEXT.format(header="weight 100:400:900"))
    assert [a.tag for a in sketch.document.axes] == ["wght"]
    assert not [d for d in sketch.diagnostics if d.severity == "error"]


@pytest.mark.parametrize("header,tag", [("width 75:100:125", "wdth"), ("optical 6:12:72", "opsz"), ("contrast 0:0:100", "CONT")])
def test_other_names(header, tag):
    text = f"family F\naxes\n    {header}\nsources\n    A [{header.split()[1].split(':')[1]}] @base\n"
    (axis,) = DSSParser(strict_mode=False).parse(text).axes
    assert axis.tag == tag
