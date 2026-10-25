"""OR in rule conditions (1.6.0): condition groups joined by `||`, each a
DesignSpace conditionset.

    dollar > dollar.alt (weight >= Bold) || (width <= Condensed && weight >= 600) "heavy"
"""

import pytest
from fontTools.designspaceLib import evaluateRule

import dssketch
from dssketch import DSSParser, Sketch, apply_edits, complete, diagnose, tokenize
from dssketch.structure import build

TEXT = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
    wdth 75:100:125
        Condensed > 75
        Normal > 100 @elidable
        Expanded > 125
sources [wght, wdth]
    A [Regular, Normal] @base
    B [Black, Normal]
    C [Regular, Condensed]
    D [Thin, Normal]
rules
    dollar > dollar.alt (weight >= Black) || (width <= Condensed && weight >= 600) "heavy"  # note
    a > a.alt (weight >= 700)
instances off
"""

RULE = 17


def back(text):
    return dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())


def test_parsed_as_groups():
    rule = DSSParser().parse(TEXT).rules[0]
    assert rule.conditions == [{"axis": "weight", "minimum": 900.0, "maximum": None}]
    assert rule.alternatives == [[{"axis": "width", "minimum": None, "maximum": 75.0},
                                  {"axis": "weight", "minimum": 600.0, "maximum": None}]]
    assert len(rule.condition_sets) == 2


@pytest.mark.parametrize("location, applies", [
    ({"weight": 900, "width": 100}, True),   # first group
    ({"weight": 650, "width": 75}, True),    # second group
    ({"weight": 650, "width": 100}, False),
    ({"weight": 500, "width": 75}, False),   # second group, weight too low
])
def test_designspace_applies_where_either_group_holds(location, applies):
    rule = back(TEXT).rules[0]
    assert len(rule.conditionSets) == 2
    assert evaluateRule(rule, location) == applies


def test_round_trip_keeps_one_rule():
    out = dssketch.convert_designspace_to_dss_string(back(TEXT))
    lines = [line.strip() for line in out.splitlines() if "dollar.alt" in line]
    assert lines == ['dollar > dollar.alt (weight >= Black) || (width <= Condensed && weight >= 600) "heavy"']


def test_bounds_are_written_as_stored():
    # a lower bound of 0 used to be dropped as if open (and an upper bound >= 1000)
    text = TEXT.replace("(weight >= 700)", "(0 <= weight <= 450)").replace("Thin > 100", "Thin > 0")
    text = text.replace("Black > 900", "Black > 1200")
    out = dssketch.convert_designspace_to_dss_string(back(text))
    assert "a > a.alt (Thin <= weight <= 450)" in out


def test_malformed_groups_are_errors():
    bad = TEXT.replace("|| (width", "(width")
    found = [d for d in diagnose(bad) if d.severity == "error" and d.line == RULE]
    assert found and "Join condition groups with `||`" in found[0].message
    assert DSSParser(strict_mode=False).parse(bad).rules[0].alternatives == []


def test_unknown_axis_in_a_later_group():
    bad = TEXT.replace("width <= Condensed", "wdht <= 80")
    assert any(d.code == "5.38" and d.line == RULE for d in diagnose(bad))


def test_tokens_and_structure():
    tokens = [(t.text, t.type) for t in tokenize(TEXT) if t.line == RULE]
    assert ("||", "operator") in tokens
    assert ("width", "axis-tag") in tokens and ("Condensed", "label") in tokens
    line = build(TEXT).line(RULE)
    assert line.text("group.0") == "(weight >= Black)"
    assert line.text("group.1") == "(width <= Condensed && weight >= 600)"
    assert [line.text(f"condition.{i}") for i in range(3)] == [
        "weight >= Black", "width <= Condensed", "weight >= 600"]
    assert line.text("conditions").startswith("(weight") and line.text("conditions").endswith("600)")
    assert line.values["name"] == "heavy"


def test_queries():
    sk = Sketch.parse(TEXT)
    region = sk.rule_regions()[0]
    assert region.region == {"weight": (900.0, 900.0)}
    assert region.alternatives == ({"width": (75.0, 75.0), "weight": (600.0, 900.0)},)
    glyphs = ["dollar", "dollar.alt", "a", "a.alt"]
    assert sk.substitutions_at({"weight": 650, "width": 75}, glyphs).get("dollar") == "dollar.alt"
    assert "dollar" not in sk.substitutions_at({"weight": 650, "width": 100}, glyphs)


def test_operations():
    sk = Sketch.parse(TEXT)
    r = sk.add_rule_group(1, "width <= 80")
    assert "    a > a.alt (weight >= 700) || (width <= 80)\n" in r.text
    r = sk.add_rule_condition(0, "weight <= 800", group=1)
    assert "(width <= Condensed && weight >= 600 && weight <= 800)" in r.text
    r = sk.remove_rule_condition(0, 0)  # the only condition of the first group: the group goes
    assert '    dollar > dollar.alt (width <= Condensed && weight >= 600) "heavy"  # note\n' in r.text
    r = sk.remove_rule_group(0, 1)
    assert '    dollar > dollar.alt (weight >= Black) "heavy"  # note\n' in r.text
    with pytest.raises(dssketch.EditError):
        r.sketch.remove_rule_group(0, 0)
    r = sk.set_rule_conditions(1, [["weight >= 700"], ["width <= 80", "weight >= 300"]])
    assert "    a > a.alt (weight >= 700) || (width <= 80 && weight >= 300)\n" in r.text
    r = sk.add_rule("b", "b.alt", "weight >= 700", alternatives=["width <= 80"])
    assert "    b > b.alt (weight >= 700) || (width <= 80)\n" in r.text
    column = TEXT.splitlines()[RULE - 1].index("Condensed")
    assert sk.item_at(RULE, column) == ("rule", 0, "condition.1")


def test_apply_writes_a_new_conditionset():
    ds = back(TEXT)
    ds.rules[1].conditionSets.append([{"name": "Width", "minimum": None, "maximum": 80}])
    result, report = Sketch.parse(TEXT).apply_designspace(ds)
    assert [i for i in report if i.category == 6] == []
    assert "    a > a.alt (weight >= 700) || (width <= 80)\n" in result.text
    assert apply_edits(TEXT, result.edits) == result.text
    # and unchanged, nothing
    result, _ = Sketch.parse(TEXT).apply_designspace(back(TEXT))
    assert result.edits == []


def test_completion_in_a_later_group():
    line = TEXT.splitlines()[RULE - 1]
    column = line.index("width") + 2
    offered = [c.text for c in complete(TEXT, RULE, column)]
    assert "width" in offered
