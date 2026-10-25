"""Fixes found by running a corpus of avar2/HOI DesignSpaces (2026-10-25):
hidden axis names, incomplete axis maps, a label off the map points, an axis
that does not vary, anisotropic locations, an unknown location label, data on
a hidden axis, a discrete default outside its values."""

from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
    DiscreteAxisDescriptor,
    InstanceDescriptor,
    SourceDescriptor,
)

import dssketch
from dssketch import diagnose
from dssketch.core.report import (
    AXIS_DISCRETE_DEFAULT_INVALID,
    AXIS_HIDDEN_DATA_DROPPED,
    CATEGORY_AXES,
    CATEGORY_DOCUMENT,
    DOCUMENT_ANISOTROPIC_DROPPED,
)


def axis(name, tag, lo, default, hi, hidden=False, map=None, labels=()):
    a = AxisDescriptor()
    a.name, a.tag, a.minimum, a.default, a.maximum, a.hidden = name, tag, lo, default, hi, hidden
    a.map = list(map or [])
    a.axisLabels = [AxisLabelDescriptor(name=n, userValue=v) for n, v in labels]
    return a


def doc(*axes, sources=None):
    d = DesignSpaceDocument()
    for a in axes:
        d.addAxis(a)
    for loc in sources or [{}]:
        s = SourceDescriptor()
        s.filename, s.familyName, s.styleName = f"A-{len(d.sources)}.ufo", "A", "R"
        s.location = dict(loc)
        d.addSource(s)
    return d


def back(d):
    text, report = dssketch.convert_designspace_to_dss_string(d, return_report=True)
    return text, report, dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())


def test_hidden_axis_keeps_its_designspace_name():
    d = doc(axis("Diagonal", "DIAG", 0, 0, 100), axis("Horizontal", "HORI", 0, 0, 100, hidden=True),
            sources=[{"Diagonal": 0, "Horizontal": 0}, {"Diagonal": 0, "Horizontal": 100}])
    text, _, ds = back(d)
    assert '    HORI 0:0:100 "Horizontal"' in text
    assert [a.name for a in ds.axes] == ["Diagonal", "Horizontal"]
    assert ds.sources[1].location["Horizontal"] == 100


def test_incomplete_map_is_completed_where_fonttools_puts_it():
    a = axis("Weight", "wght", 100, 400, 900, map=[(400, 400), (900, 800)])
    text, report, ds = back(doc(a))
    assert not [x for x in diagnose(text) if x.severity == "error"]
    w = ds.axes[0]
    for v in (100, 250, 400, 650, 900):
        assert abs(w.map_forward(v) - a.map_forward(v)) < 1e-9


def test_label_off_the_map_points_follows_the_map():
    a = axis("Weight", "wght", 100, 400, 900, map=[(100, 0), (900, 1000)], labels=[("Regular", 400)])
    text, _, ds = back(doc(a, sources=[{"Weight": 375}]))
    assert "Regular > 375" in text


def test_axis_that_does_not_vary_is_a_warning():
    d = doc(axis("Weight", "wght", 400, 400, 700), axis("Width", "wdth", 100, 100, 100))
    text, _, ds = back(d)
    found = [x for x in diagnose(text) if x.code == "5.6"]
    assert found and found[0].severity == "warning"
    assert ds.axes[1].minimum == ds.axes[1].maximum == 100


def test_anisotropic_locations_keep_x_and_report():
    d = doc(axis("Width", "wdth", 0, 0, 1000), sources=[{"Width": 0}, {"Width": (400, 300)}])
    text, report, ds = back(d)
    assert report.find(CATEGORY_DOCUMENT, DOCUMENT_ANISOTROPIC_DROPPED)
    assert ds.sources[1].location["Width"] == 400
    assert d.sources[1].location["Width"] == (400, 300)  # the caller's document is untouched


def test_unknown_location_label_does_not_crash():
    d = doc(axis("Weight", "wght", 100, 400, 900))
    inst = InstanceDescriptor()
    inst.styleName, inst.locationLabel = "X", "Bogus"
    d.addInstance(inst)
    dssketch.convert_designspace_to_dss_string(d)


def test_hidden_axis_map_and_labels_are_reported():
    d = doc(axis("Weight", "wght", 100, 400, 900),
            axis("Width", "wdth", 50, 100, 150, hidden=True, map=[(50, 20), (100, 100), (150, 900)],
                 labels=[("Normal", 100)]))
    text, report, ds = back(d)
    issue = report.find(CATEGORY_AXES, AXIS_HIDDEN_DATA_DROPPED)
    assert issue and issue.raw_data["labels"] == ["Normal"]
    assert not [x for x in diagnose(text) if x.severity == "error"]


def test_discrete_default_outside_its_values_is_reported():
    a = DiscreteAxisDescriptor()
    a.name, a.tag, a.values, a.default = "Italic", "ital", [0, 1], 2
    d = doc(axis("Weight", "wght", 100, 400, 900), a)
    _, report = dssketch.convert_designspace_to_dss_string(d, return_report=True)
    assert report.find(CATEGORY_AXES, AXIS_DISCRETE_DEFAULT_INVALID)
