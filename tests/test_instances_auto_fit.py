"""
Tests for the `instances auto` fit report in DS → DSSketch conversion.

The sketch normally says `instances auto` rather than listing instances, on the
assumption that the generator rebuilds them from the axis labels. The converter
checks that assumption against the DesignSpace it read and reports three
distinct outcomes:

  * a declared position the generator never reaches  -> WARNING (a real loss)
  * the same position under a different style name   -> WARNING (naming drift)
  * positions the generator adds                     -> INFO    (a `skip` block)

Instances are matched by design-space position, never by style name.

The report is purely diagnostic: it must not alter the converted document, and
it must never synthesise a `skip` block — `skip` is an instruction to the
generator, and a DesignSpace records only the result of applying it.
"""

import logging

import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    SourceDescriptor,
)

from dssketch.converters.designspace_to_dss import DesignSpaceToDSS
from dssketch.utils.logging import DSSketchLogger


def build_designspace(instances) -> DesignSpaceDocument:
    """A one-axis document whose labels generate exactly Regular and Bold."""
    doc = DesignSpaceDocument()

    axis = AxisDescriptor()
    axis.tag, axis.name = "wght", "weight"
    axis.minimum, axis.default, axis.maximum = 400, 400, 700
    axis.map = [(400, 400), (700, 700)]
    axis.axisLabels = [
        AxisLabelDescriptor(name="Regular", userValue=400),
        AxisLabelDescriptor(name="Bold", userValue=700),
    ]
    doc.addAxis(axis)

    for coord, style in ((400, "Regular"), (700, "Bold")):
        src = SourceDescriptor()
        src.filename, src.familyName, src.styleName = f"T-{style}.ufo", "T", style
        src.location = {"weight": coord}
        if coord == 400:
            src.copyLib = src.copyInfo = True
        doc.addSource(src)

    for style, coord in instances:
        inst = InstanceDescriptor()
        inst.familyName, inst.styleName = "T", style
        inst.location = {"weight": coord}
        doc.addInstance(inst)

    return doc


@pytest.fixture(autouse=True)
def active_logger(caplog):
    """DSSketchLogger is a no-op until setup_logger() runs, which only the CLI
    does. Attach the shared 'dssketch' logger so caplog can see the report."""
    previous = DSSketchLogger._logger
    DSSketchLogger._logger = logging.getLogger("dssketch")
    caplog.set_level(logging.DEBUG, logger="dssketch")
    yield
    DSSketchLogger._logger = previous


def convert(doc, caplog):
    return DesignSpaceToDSS().convert(doc), caplog.text


class TestReportedOutcomes:
    def test_exact_match_is_silent(self, caplog):
        doc = build_designspace([("Regular", 400), ("Bold", 700)])
        _, log = convert(doc, caplog)
        assert "does not reach" not in log
        assert "named differently" not in log
        assert "beyond the" not in log

    def test_unreachable_position_warns(self, caplog):
        """An instance between the labelled points cannot be generated."""
        doc = build_designspace(
            [("Regular", 400), ("SemiBold", 550), ("Bold", 700)]
        )
        _, log = convert(doc, caplog)
        assert "does not reach 1 of the 3" in log
        assert "'SemiBold'" in log

    def test_extra_instances_are_reported_as_info_not_a_loss(self, caplog):
        """The DesignSpace was filtered; that is what a `skip` block expresses."""
        doc = build_designspace([("Regular", 400)])
        _, log = convert(doc, caplog)
        assert "generates 1 instance(s) beyond the 1" in log
        assert "'Bold'" in log
        assert "does not reach" not in log

    def test_renamed_instance_warns_without_claiming_a_loss(self, caplog):
        """Same position, different name — naming drift, not a missing point."""
        doc = build_designspace([("Book", 400), ("Bold", 700)])
        _, log = convert(doc, caplog)
        assert "named differently" in log
        assert "'Book' -> 'Regular'" in log
        assert "does not reach" not in log


class TestMatchingRules:
    def test_position_matching_ignores_dimensions_at_their_default(self, caplog):
        """An omitted dimension means the axis default, so both compare equal."""
        doc = build_designspace([("Regular", 400), ("Bold", 700)])
        doc.instances[0].location = {}  # weight omitted == weight at 400
        _, log = convert(doc, caplog)
        assert "does not reach" not in log
        assert "named differently" not in log


class TestReportIsDiagnosticOnly:
    def test_document_is_not_modified(self):
        """No `skip` is synthesised and the instances are carried across as-is."""
        doc = build_designspace([("Regular", 400)])
        dss = DesignSpaceToDSS().convert(doc)
        assert dss.instances_skip == []
        assert [i.stylename for i in dss.instances] == ["Regular"]
        assert dss.instances_off is False

    def test_conversion_survives_a_failing_report(self, monkeypatch, caplog):
        """A diagnostic must never be able to break a conversion."""
        monkeypatch.setattr(
            "dssketch.converters.designspace_to_dss.createInstances",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        caplog.set_level(logging.DEBUG, logger="dssketch")
        dss = DesignSpaceToDSS().convert(build_designspace([("Regular", 400)]))
        assert len(dss.instances) == 1
        assert "Could not verify" in caplog.text

    def test_document_without_instances_is_not_analysed(self, caplog):
        doc = build_designspace([])
        dss, log = convert(doc, caplog)
        assert dss.instances_off is True
        assert "beyond the" not in log
