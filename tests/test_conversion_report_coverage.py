"""
What a conversion drops or doubts is in the ConversionReport, in both directions.

DS -> DSS: DesignSpace data a sketch does not express is dropped by design, and
now reported instead of lost silently. The hidden-axis heuristic is gone: an
axis is hidden only when the DesignSpace says so, and a visible axis that only
avar2 drives is reported instead of being hidden behind the designer's back.

DSS -> DS: findings that only reached the log (which the plain API leaves
off) are in the report, together with the sketch's own validation messages.
"""

import defcon
import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    AxisMappingDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    LocationLabelDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)

import dssketch
from dssketch import (
    AVAR2_UNKNOWN_AXIS,
    AXIS_LABEL_DATA_DROPPED,
    AXIS_OUTPUT_ONLY_VISIBLE,
    CATEGORY_AXES,
    CATEGORY_DOCUMENT,
    CATEGORY_INSTANCES,
    CATEGORY_RULES,
    CATEGORY_SKETCH,
    CATEGORY_SOURCES,
    DOCUMENT_ELIDED_FALLBACK_DROPPED,
    DOCUMENT_FAMILY_UNKNOWN,
    DOCUMENT_LIB_DROPPED,
    DOCUMENT_LOCATION_LABELS_DROPPED,
    INSTANCE_FIELDS_DROPPED,
    RULE_DROPPED_EMPTY,
    RULE_GLYPH_NOT_IN_DEFAULT,
    RULE_SUBSTITUTIONS_SKIPPED,
    RULES_PROCESSING_LAST_DROPPED,
    SEVERITY_ERROR,
    SKETCH_VALIDATION_MESSAGE,
    SOURCE_FIELDS_DROPPED,
)


def _axis(name, tag, lo, df, hi, hidden=False):
    a = AxisDescriptor()
    a.name, a.tag, a.minimum, a.default, a.maximum, a.hidden = name, tag, lo, df, hi, hidden
    return a


def _base_doc():
    d = DesignSpaceDocument()
    d.addAxis(_axis("weight", "wght", 100, 400, 900))
    for name, w in (("Thin", 100), ("Regular", 400), ("Black", 900)):
        s = SourceDescriptor()
        s.filename, s.location, s.familyName = f"{name}.ufo", {"weight": w}, "Fam"
        d.addSource(s)
    return d


def _report(doc):
    _, report = dssketch.convert_designspace_to_dss_string(doc, return_report=True)
    return report


# -- DS -> DSS ------------------------------------------------------------------


def test_plain_document_reports_nothing():
    assert not _report(_base_doc())


def test_document_level_losses():
    d = _base_doc()
    d.lib = {"com.example.setting": 1}
    d.elidedFallbackName = "Book"  # the sketch would generate "Regular"
    d.locationLabels = [LocationLabelDescriptor(name="Reading", userLocation={"weight": 400})]
    r = _report(d)
    assert r.find(CATEGORY_DOCUMENT, DOCUMENT_LIB_DROPPED).raw_data["keys"] == ["com.example.setting"]
    assert r.find(CATEGORY_DOCUMENT, DOCUMENT_ELIDED_FALLBACK_DROPPED)
    assert r.find(CATEGORY_DOCUMENT, DOCUMENT_LOCATION_LABELS_DROPPED).raw_data["labels"] == ["Reading"]


def test_rules_processing_last_is_reported():
    d = _base_doc()
    rule = RuleDescriptor()
    rule.name, rule.subs = "r", [("a", "a.alt")]
    rule.conditionSets = [[{"name": "weight", "minimum": 600, "maximum": 900}]]
    d.addRule(rule)
    d.rulesProcessingLast = True
    assert _report(d).find(CATEGORY_RULES, RULES_PROCESSING_LAST_DROPPED)


def test_stat_label_extras_are_reported():
    d = _base_doc()
    d.axes[0].axisLabels = [
        AxisLabelDescriptor(name="Regular", userValue=400, userMinimum=350, userMaximum=450, linkedUserValue=700),
    ]
    issue = _report(d).find(CATEGORY_AXES, AXIS_LABEL_DATA_DROPPED)
    assert issue and "range" in issue.details and "linked value" in issue.details


def test_source_overrides_are_reported():
    d = _base_doc()
    d.sources[0].muteKerning = True
    d.sources[0].mutedGlyphNames = ["a"]
    issue = _report(d).find(CATEGORY_SOURCES, SOURCE_FIELDS_DROPPED)
    assert issue and "muted kerning" in issue.details and "1 muted glyphs" in issue.details


def test_instance_data_is_reported_but_generated_postscript_names_are_not():
    d = _base_doc()
    for style, w, ps in (("Thin", 100, "Fam-Thin"), ("Black", 900, "FamPro-Heavy")):
        inst = InstanceDescriptor()
        inst.familyName, inst.styleName, inst.location, inst.postScriptFontName = "Fam", style, {"weight": w}, ps
        d.addInstance(inst)
    d.instances[0].styleMapStyleName = "regular"
    issue = _report(d).find(CATEGORY_INSTANCES, INSTANCE_FIELDS_DROPPED)
    assert issue.raw_data["fields"] == {"postScriptFontName": 1, "styleMapStyleName": 1}


# -- hidden axes -------------------------------------------------------------------


def _avar2_doc(hidden_flag):
    d = DesignSpaceDocument()
    d.addAxis(_axis("weight", "wght", 100, 400, 900))
    d.addAxis(_axis("XOUC", "XOUC", 0, 50, 100, hidden=hidden_flag))
    m = AxisMappingDescriptor()
    m.inputLocation, m.outputLocation = {"weight": 900}, {"XOUC": 80}
    d.axisMappings = [m]
    s = SourceDescriptor()
    s.filename, s.location = "R.ufo", {"weight": 400, "XOUC": 50}
    d.addSource(s)
    return d


def test_output_only_axis_stays_visible_and_is_reported():
    sketch, report = dssketch.convert_designspace_to_dss_string(_avar2_doc(False), return_report=True)
    assert "axes hidden" not in sketch
    issue = report.find(CATEGORY_AXES, AXIS_OUTPUT_ONLY_VISIBLE)
    assert issue and issue.raw_data["axes"] == ["XOUC"]
    back = dssketch.convert_dss_string_to_designspace(sketch)
    assert not any(a.hidden for a in back.axes)


def test_declared_hidden_axis_stays_hidden_and_is_not_reported():
    sketch, report = dssketch.convert_designspace_to_dss_string(_avar2_doc(True), return_report=True)
    assert "axes hidden" in sketch
    assert not report.find(CATEGORY_AXES, AXIS_OUTPUT_ONLY_VISIBLE)
    back = dssketch.convert_dss_string_to_designspace(sketch)
    assert [a.tag for a in back.axes if a.hidden] == ["XOUC"]


def test_roboto_delta_keeps_its_zero_hidden_axes():
    ds = DesignSpaceDocument.fromfile("examples/avar2-RobotoDelta-Roman.designspace")
    assert not any(a.hidden for a in ds.axes)
    back = dssketch.convert_dss_string_to_designspace(dssketch.convert_designspace_to_dss_string(ds))
    assert not any(a.hidden for a in back.axes)


# -- DSS -> DS ---------------------------------------------------------------------

SKETCH = """\
family T
path sources
axes
    wght 400:400:700
        Regular > 400 @elidable
        Bold > 700
sources [wght]
    Regular [Regular] @base
    Bold [Bold]
rules
{rules}
instances off
"""


def _ufo(path, glyphs):
    font = defcon.Font()
    font.info.familyName = "T"
    for name in glyphs:
        font.newGlyph(name)
    font.save(str(path))


@pytest.fixture
def project(tmp_path):
    (tmp_path / "sources").mkdir()
    for name in ("Regular", "Bold"):
        _ufo(tmp_path / "sources" / f"{name}.ufo", ["a", "b", "b.alt"])
    return tmp_path


def _to_ds(text, **kw):
    return dssketch.convert_dss_string_to_designspace(text, return_report=True, **kw)


def test_rule_findings(project):
    rules = (
        '    a > a.alt (weight >= Bold) "explicit"\n'
        '    * > .alt (weight >= Bold) "wild"\n'
        '    zz* > .alt (weight >= Bold) "empty"'
    )
    ds, report = _to_ds(SKETCH.format(rules=rules), base_path=str(project))
    assert report.find(CATEGORY_RULES, RULE_GLYPH_NOT_IN_DEFAULT).raw_data == {"rule": "explicit", "glyphs": ["a.alt"]}
    skipped = report.find(CATEGORY_RULES, RULE_SUBSTITUTIONS_SKIPPED)
    assert skipped.raw_data["rule"] == "wild" and ["a", "a.alt"] in skipped.raw_data["skipped"]
    assert report.find(CATEGORY_RULES, RULE_DROPPED_EMPTY).raw_data == {"rule": "empty"}
    assert [r.name for r in ds.rules] == ["explicit", "wild"]


def test_unknown_avar2_axis_is_an_error():
    text = SKETCH.format(rules="").replace("rules\n\n", "") .replace(
        "instances off", "avar2\n    [wght=Bold] > XHDI=80\ninstances off"
    )
    _, report = _to_ds(text)
    issue = report.find(CATEGORY_AXES, AVAR2_UNKNOWN_AXIS)
    assert issue.severity == SEVERITY_ERROR and issue.raw_data == {"axis": "XHDI"}


def test_unknown_family_is_reported():
    text = SKETCH.format(rules="").replace("rules\n\n", "").replace("family T\n", "")
    ds, report = _to_ds(text)
    assert report.find(CATEGORY_DOCUMENT, DOCUMENT_FAMILY_UNKNOWN)


def test_sketch_validation_messages_come_first():
    text = SKETCH.format(rules="").replace("rules\n\n", "").replace("Regular > 400 @elidable", "Regular > 400")
    _, report = _to_ds(text)
    first = report.issues[0]
    assert (first.category, first.code) == (CATEGORY_SKETCH, SKETCH_VALIDATION_MESSAGE)
    assert "@elidable" in first.description


def test_without_return_report_the_api_is_unchanged():
    ds = dssketch.convert_dss_string_to_designspace(SKETCH.format(rules="").replace("rules\n\n", ""))
    assert ds.axes and not isinstance(ds, tuple)


def test_generated_elided_fallback_is_not_reported():
    d = _base_doc()
    d.elidedFallbackName = "Regular"
    assert not _report(d).find(CATEGORY_DOCUMENT, DOCUMENT_ELIDED_FALLBACK_DROPPED)
