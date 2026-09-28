"""
Where DSSketch fills in a default, it is the default's DESIGN value.

Source locations and avar2 outputs are design space. With `Regular > 420` on a
`wght Thin:Regular:Black` axis, the default is user 400 but design 420, and an
omitted coordinate or `$` used to get 400.
"""

import dssketch
from dssketch import DSSParser, DSSWriter
from dssketch.core.models import DSSAxis, DSSAxisMapping, _piecewise_linear

AXES = """\
family T
axes
    wght Thin:Regular:Black
        Thin > 0
        Regular > 420 @elidable
        Black > 1000
    ital discrete
        Upright @elidable
        Italic
"""


def _locations(sketch):
    ds = dssketch.convert_dss_string_to_designspace(sketch)
    return {s.filename: dict(s.location) for s in ds.sources}


def test_default_only_source_sits_at_design_default():
    sketch = AXES + "sources [wght, ital]\n    Regular @base\n    Black [Black, Upright]\ninstances off\n"
    assert _locations(sketch)["Regular.ufo"]["weight"] == 420


def test_named_source_omitting_an_axis_gets_design_default():
    sketch = AXES + (
        "sources [wght, ital]\n"
        "    Regular [Regular, Upright] @base\n"
        "    Thin [Thin, Upright]\n"
        "    Italic ital=Italic @base\n"
        "instances off\n"
    )
    loc = _locations(sketch)["Italic.ufo"]
    assert loc == {"weight": 420, "italic": 1}


def test_writer_omits_exactly_what_the_parser_fills_in():
    sketch = AXES + (
        "sources [wght, ital]\n"
        "    Regular [Regular, Upright] @base\n"
        "    Thin [Thin, Upright]\n"
        "    Italic ital=Italic @base\n"
        "instances off\n"
    )
    ds = dssketch.convert_dss_string_to_designspace(sketch)
    again = dssketch.convert_dss_string_to_designspace(dssketch.convert_designspace_to_dss_string(ds))
    assert {s.filename: dict(s.location) for s in again.sources} == {
        s.filename: dict(s.location) for s in ds.sources
    }


def test_avar2_dollar_is_design_default():
    sketch = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 420 @elidable
        Black > 900
axes hidden
    XHID 0:50:100
sources [wght, XHID]
    A [Thin, 50]
    B [Regular, 50] @base
    C [Black, 50]
avar2
    [wght=Black] > wght=$, XHID=80
instances off
"""
    ds = dssketch.convert_dss_string_to_designspace(sketch)
    assert ds.axisMappings[0].outputLocation["weight"] == 420
    assert ds.axisMappings[0].outputLocation["XHID"] == 80


def test_axis_design_value_interpolates_like_fonttools():
    from fontTools.varLib.models import piecewiseLinearMap

    points = [(100, 0), (300, 230), (400, 420), (700, 725), (900, 1000)]
    for v in (50, 100, 150, 350, 400, 550, 900, 1000):
        assert _piecewise_linear(v, points) == piecewiseLinearMap(v, dict(points))

    axis = DSSAxis("weight", "wght", 100, 400, 900, mappings=[DSSAxisMapping(u, d, "") for u, d in points])
    assert axis.design_default == 420
    assert axis.get_design_value(550) == 572.5
    assert axis.get_user_value(572.5) == 550
