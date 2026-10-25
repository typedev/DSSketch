"""Writing a changed DesignSpace back into the text (apply.py, 1.5.x)."""

from pathlib import Path

import pytest
from fontTools.designspaceLib import AxisLabelDescriptor, InstanceDescriptor, RuleDescriptor, SourceDescriptor

import dssketch
from dssketch import (
    APPLY_REFUSED,
    APPLY_RULE_KEPT,
    CATEGORY_APPLY,
    FontData,
    Sketch,
    apply_edits,
)

EXAMPLES = Path(__file__).parent.parent / "examples"

TEXT = """\
# Apply test font
family A  # the family
path masters

axes
    # weight first
    wght 100:400:900 "Weight"
        Thin > 100
        Regular > 400 @elidable  # default
        Black > 900
    ital discrete
        Upright @elidable
        Italic

sources [wght, ital]
    # the masters
    A-Thin [Thin, Upright]
    A-Regular [Regular, Upright] @base
    A-Black [Black, Upright]   # heavy
    A-Italic [Regular, Italic]

rules
    # alternates
    dollar > dollar.alt (weight >= Black) "heavy dollar"
    a* > .ss01 (Regular <= weight <= Black) "alternates"

instances auto
"""

GLYPHS = ["a", "aacute", "a.ss01", "aacute.ss01", "dollar", "dollar.alt", "b", "b.alt"]


class Host(FontData):
    def glyph_names(self, source):
        return GLYPHS

    def style_name(self, source):
        return source.rsplit("/", 1)[-1][2:-4]


def to_ds(text=TEXT):
    return dssketch.convert_dss_string_to_designspace(text, font_data=Host())


def apply(ds, text=TEXT):
    result, report = Sketch.parse(text).apply_designspace(ds)
    assert apply_edits(text, result.edits) == result.text
    assert not [d for d in result.sketch.diagnostics if d.severity == "error"], result.text
    return result, report


def applied(report):
    return [(i.code, i.description) for i in report if i.category == CATEGORY_APPLY]


def changed(old, new):
    import difflib

    return [
        line for line in difflib.unified_diff(old.splitlines(), new.splitlines(), n=0, lineterm="")
        if line[:1] in "+-" and not line.startswith(("---", "+++"))
    ]


def source(ds, name):
    return next(s for s in ds.sources if s.filename.endswith(name + ".ufo"))


def axis(ds, tag):
    return next(a for a in ds.axes if a.tag == tag)


# -- nothing changed ----------------------------------------------------------------


def test_unchanged_designspace_changes_nothing():
    result, report = apply(to_ds())
    assert result.edits == [] and result.text == TEXT and applied(report) == []


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.dssketch")), ids=lambda p: p.name)
def test_examples_round_trip_without_edits(path):
    text = path.read_text(encoding="utf-8")
    ds = dssketch.convert_to_designspace(str(path))
    result, report = Sketch.parse(text).apply_designspace(ds)
    assert result.edits == [] and applied(report) == []


# -- sources ------------------------------------------------------------------------


def test_moved_source():
    ds = to_ds()
    source(ds, "A-Black").location["Weight"] = 850
    result, _ = apply(ds)
    assert changed(TEXT, result.text) == [
        "-    A-Black [Black, Upright]   # heavy", "+    A-Black [850, Upright]   # heavy",
    ]


def test_added_and_removed_sources():
    ds = to_ds()
    ds.sources.remove(source(ds, "A-Black"))
    new = SourceDescriptor()
    new.filename = "masters/A-Medium.ufo"
    new.location = {"Weight": 600, "italic": 0}
    new.familyName, new.styleName = "A", "Medium"
    ds.addSource(new)
    result, _ = apply(ds)
    assert changed(TEXT, result.text) == ["-    A-Black [Black, Upright]   # heavy", "+    A-Medium [600, Upright]"]


# -- axes ---------------------------------------------------------------------------


def test_moved_mapping_and_new_label():
    ds = to_ds()
    wght = axis(ds, "wght")
    wght.map = [(100, 100), (400, 420), (900, 900)]
    wght.map.insert(2, (700, 650))
    wght.axisLabels.insert(2, AxisLabelDescriptor(name="Bold", userValue=700))
    for s in ds.sources:  # the masters at Regular move with it, and the rule
        if s.location["Weight"] == 400:
            s.location["Weight"] = 420
    next(r for r in ds.rules if r.name == "alternates").conditionSets[0][0]["minimum"] = 420
    result, _ = apply(ds)
    assert changed(TEXT, result.text) == [
        "-        Regular > 400 @elidable  # default",
        "+        Regular > 420 @elidable  # default",
        "+        Bold > 650",  # 700 is Bold's standard user value: not written
    ]


def test_renamed_label_follows_into_its_uses():
    ds = to_ds()
    for label in axis(ds, "wght").axisLabels:
        if label.name == "Black":
            label.name = "Heavy"
    result, _ = apply(ds)
    assert "        900 Heavy > 900\n" in result.text
    assert "A-Black [Heavy, Upright]   # heavy" in result.text
    assert "(weight >= Heavy)" in result.text


def test_axis_range():
    ds = to_ds()
    wght = axis(ds, "wght")
    wght.maximum = 1000
    wght.map.append((1000, 1000))
    result, _ = apply(ds)
    assert '    wght 100:400:1000 "Weight"' in result.text
    assert "        1000 > 1000\n" in result.text


# -- rules --------------------------------------------------------------------------


def test_rule_condition_changed():
    ds = to_ds()
    rule = next(r for r in ds.rules if r.name == "heavy dollar")
    rule.conditionSets[0][0]["minimum"] = 700
    result, _ = apply(ds)
    assert changed(TEXT, result.text) == [
        '-    dollar > dollar.alt (weight >= Black) "heavy dollar"',
        '+    dollar > dollar.alt (weight >= 700) "heavy dollar"',
    ]


def test_rule_added_and_removed():
    ds = to_ds()
    ds.rules = [r for r in ds.rules if r.name != "heavy dollar"]
    rule = RuleDescriptor()
    rule.name = "b alt"
    rule.subs = [("b", "b.alt")]
    rule.conditionSets = [[{"name": "Weight", "minimum": 400, "maximum": None}]]
    ds.addRule(rule)
    result, _ = apply(ds)
    assert '    b > b.alt (weight >= Regular) "b alt"' in result.text
    assert "heavy dollar" not in result.text
    assert "    # alternates\n" not in result.text  # its leading comment went with it


def test_pattern_rule_kept_when_its_glyphs_fit():
    ds = to_ds()
    rule = next(r for r in ds.rules if r.name == "alternates")
    rule.subs = [("a", "a.ss01")]  # a glyph left out: still the same pattern
    result, report = apply(ds)
    assert result.edits == [] and applied(report) == []
    rule.subs = [("a", "a.salt")]
    result, report = apply(ds)
    assert result.edits == [] and [c for c, _ in applied(report)] == [APPLY_RULE_KEPT]


# -- instances ----------------------------------------------------------------------


def test_removed_instances_become_skip_entries():
    ds = to_ds()
    ds.instances = ds.instances[:2]  # Thin, Thin Italic
    result, report = apply(ds)
    assert changed(TEXT, result.text) == [
        "+    skip", "+        Regular", "+        Italic", "+        Black", "+        Black Italic",
    ]
    assert applied(report) == []


def test_untouched_instances_follow_a_new_label():
    ds = to_ds()
    axis(ds, "wght").axisLabels.insert(2, AxisLabelDescriptor(name="Bold", userValue=700))
    axis(ds, "wght").map = [(100, 100), (400, 400), (700, 650), (900, 900)]
    result, _ = apply(ds)
    assert "skip" not in result.text  # Bold and Italic Bold are new instances, not skipped


def test_added_and_edited_instance_blocks():
    ds = to_ds()
    extra = InstanceDescriptor()
    extra.familyName, extra.styleName, extra.location = "A Display", "Book", {"Weight": 330, "italic": 0}
    ds.addInstance(extra)
    result, report = apply(ds)
    assert result.text.endswith(
        "instances auto\n"
        "    Book\n"
        "        location: wght=330, ital=Upright\n"
        "        family: A Display\n"
        "        style: Book\n"
    )  # the DesignSpace sets no PostScript name or file name: they stay derived
    assert applied(report) == []

    # the block written by hand without the derived keys: only what changed is set
    text = TEXT + "    Book\n        location: wght=330\n        family: A Display\n"
    ds = to_ds(text)
    ds.instances[-1].postScriptFontName = "ADisplay-BookPro"
    result, report = apply(ds, text)
    assert changed(text, result.text) == ["+        postscript: ADisplay-BookPro"]

    ds = to_ds(text)
    ds.instances = ds.instances[:-1]
    result, _ = apply(ds, text)
    assert result.text == TEXT


# -- not written ------------------------------------------------------------------


def avar2_of(ds):
    """Mappings modulo inputs at their axis default (left out = default)"""
    defaults = {a.name: a.map_forward(a.default) for a in ds.axes}

    def side(loc, drop=False):
        return sorted((k, float(v)) for k, v in loc.items() if not (drop and abs(v - defaults[k]) < 1e-9))
    return sorted(str((side(m.inputLocation, True), side(m.outputLocation))) for m in ds.axisMappings)


def test_avar2_is_written():
    path = EXAMPLES / "avar2.dssketch"
    text = path.read_text(encoding="utf-8")
    ds = dssketch.convert_to_designspace(str(path))
    ds.axisMappings[1].outputLocation["Weight"] = 333
    result, report = Sketch.parse(text).apply_designspace(ds)
    assert len(result.edits) == 1 and applied(report) == []
    assert "333" in result.text.split("\n")[result.edits[0].line - 1]
    back = dssketch.convert_dss_string_to_designspace(result.text, font_data=FontData())
    assert avar2_of(back) == avar2_of(ds)


def test_avar2_locations_added_and_removed():
    from fontTools.designspaceLib import AxisMappingDescriptor

    path = EXAMPLES / "avar2-RobotoDelta-Roman.dssketch"
    text = path.read_text(encoding="utf-8")
    ds = dssketch.convert_to_designspace(str(path))
    removed = ds.axisMappings.pop(3)
    added = AxisMappingDescriptor()
    added.inputLocation = dict(removed.inputLocation, wght=500)
    added.outputLocation = {"XOPQ": 120, "YTUC": 700}
    ds.axisMappings.append(added)
    ds.axisMappings[0].outputLocation["XOPQ"] = 77
    result, report = Sketch.parse(text).apply_designspace(ds)
    assert applied(report) == []
    back = dssketch.convert_dss_string_to_designspace(result.text, font_data=FontData())
    assert avar2_of(back) == avar2_of(ds)


def test_refused_edits_are_reported_and_the_rest_applied():
    ds = to_ds()
    labels = axis(ds, "wght").axisLabels
    for label in labels:
        if label.name == "Thin":
            label.name = "Regular"  # a second Regular: refused
    source(ds, "A-Black").location["Weight"] = 850
    result, report = apply(ds)
    assert "A-Black [850, Upright]" in result.text
    assert APPLY_REFUSED in [c for c, _ in applied(report)]


def test_comments_survive():
    ds = to_ds()
    source(ds, "A-Black").location["Weight"] = 850
    rule = next(r for r in ds.rules if r.name == "heavy dollar")
    rule.conditionSets[0][0]["minimum"] = 700
    result, _ = apply(ds)
    for comment in ("# Apply test font", "# the family", "# weight first", "# default", "# the masters",
                    "# heavy", "# alternates"):
        assert comment in result.text


def test_free_function():
    result, report = dssketch.apply_designspace(TEXT, to_ds())
    assert result.edits == []


def test_a_rule_the_designspace_left_behind_gets_numbers():
    ds = to_ds()
    axis(ds, "wght").map = [(100, 100), (400, 420), (900, 900)]
    for s in ds.sources:
        if s.location["Weight"] == 400:
            s.location["Weight"] = 420
    result, _ = apply(ds)
    # the rule still starts at design 400, which is no longer Regular
    assert '    a* > .ss01 (400 <= weight <= Black) "alternates"' in result.text
