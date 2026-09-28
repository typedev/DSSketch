"""
Two inputs DSSketch used to accept and quietly mishandle.

- Two mappings at one user value on one axis: the axis map got two outputs for
  one input and `instances auto` dropped one label and misplaced the other.
- Explicit instance lines: the parser dropped them without a word.
"""

from dssketch import DSSParser

AXIS = """\
family T
axes
    wght 100:400:900
        Thin > 100
        {extra}
        Regular > 400 @elidable
        Black > 900
sources [wght]
    A [Thin]
    B [Regular] @base
    C [Black]
"""


def _parse(text):
    parser = DSSParser(strict_mode=False)
    parser.parse(text)
    return parser.validator


def test_two_mappings_at_one_user_value_is_an_error():
    v = _parse(AXIS.format(extra="300 LightA > 250\n        300 LightB > 350"))
    errors = [e for e in v.errors if "mapped twice" in e]
    assert len(errors) == 1
    assert "LightA" in errors[0] and "LightB" in errors[0]


def test_distinct_user_values_are_fine():
    v = _parse(AXIS.format(extra="300 LightA > 250\n        350 LightB > 350"))
    assert not [e for e in v.errors if "mapped twice" in e]


def test_explicit_instance_line_is_reported():
    v = _parse(AXIS.format(extra="Light > 300") + "instances\n    Bold [Black]\n")
    warnings = [w for w in v.warnings if "Instance line ignored" in w]
    assert warnings and "'Bold [Black]'" in warnings[0]


def test_instances_auto_with_skip_reports_nothing():
    v = _parse(AXIS.format(extra="Light > 300") + "instances auto\n    skip\n        Black\n")
    assert not [w for w in v.warnings if "Instance line ignored" in w]
