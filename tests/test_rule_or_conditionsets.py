"""
A DesignSpace rule with several conditionsets means OR; DS -> DSS must keep it.

It used to merge every conditionset into one AND-ed condition, so
"(weight >= 700) OR (width <= 80)" became "(weight >= 700) AND (width <= 80)".
"""

import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    RuleDescriptor,
    SourceDescriptor,
    evaluateRule,
)

import dssketch


def _doc():
    d = DesignSpaceDocument()
    for name, tag, lo, df, hi in (("weight", "wght", 100, 400, 900), ("width", "wdth", 75, 100, 125)):
        a = AxisDescriptor()
        a.name, a.tag, a.minimum, a.default, a.maximum = name, tag, lo, df, hi
        d.addAxis(a)
    for n, loc in (("A", {"weight": 400, "width": 100}), ("B", {"weight": 900, "width": 100}), ("C", {"weight": 400, "width": 75})):
        s = SourceDescriptor()
        s.filename, s.location = f"{n}.ufo", loc
        d.addSource(s)
    r = RuleDescriptor()
    r.name = "or-rule"
    r.subs = [("a", "a.alt")]
    r.conditionSets = [
        [{"name": "weight", "minimum": 700, "maximum": 900}],
        [{"name": "width", "minimum": 75, "maximum": 80}],
    ]
    d.addRule(r)
    return d, r


def test_each_conditionset_becomes_its_own_rule():
    d, _ = _doc()
    sketch = dssketch.convert_designspace_to_dss_string(d)
    lines = [line.strip() for line in sketch.splitlines() if "a.alt" in line]
    assert lines == [
        'a > a.alt (700 <= weight <= 900) "or-rule"',
        'a > a.alt (75 <= width <= 80) "or-rule"',
    ]


@pytest.mark.parametrize(
    "location",
    [
        {"weight": 800, "width": 100},  # first conditionset only
        {"weight": 400, "width": 78},  # second only
        {"weight": 800, "width": 78},  # both
        {"weight": 400, "width": 100},  # neither
    ],
)
def test_roundtrip_applies_where_the_original_applies(location):
    d, original = _doc()
    back = dssketch.convert_dss_string_to_designspace(dssketch.convert_designspace_to_dss_string(d))
    assert any(evaluateRule(rule, location) for rule in back.rules) == evaluateRule(original, location)
