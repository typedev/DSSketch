"""`instances auto` stops at MAX_AUTO_INSTANCES before generating anything.

A parametric font has many axes without labels; each counts its ends, its
default and its avar2 inputs, so the cartesian product reached 10^14 and the
generator exhausted memory (seen on a corpus run, 2026-10-24)."""

import resource
import sys
import time

import pytest
from fontTools.designspaceLib import AxisDescriptor, DesignSpaceDocument, InstanceDescriptor, SourceDescriptor

import dssketch
from dssketch import DSSParser, Sketch, diagnose
from dssketch.core.instances import MAX_AUTO_INSTANCES, TooManyInstances
from dssketch.core.report import CATEGORY_INSTANCES, INSTANCE_AUTO_TOO_MANY


def wide_designspace(axes=40, instances=3):
    doc = DesignSpaceDocument()
    for i in range(axes):
        axis = AxisDescriptor()
        axis.tag = axis.name = f"X{i:03d}"
        axis.minimum, axis.default, axis.maximum = 0, 50, 100
        doc.addAxis(axis)
    source = SourceDescriptor()
    source.filename, source.familyName, source.styleName = "A.ufo", "A", "Regular"
    source.location = {f"X{i:03d}": 50 for i in range(axes)}
    doc.addSource(source)
    for k in range(instances):
        inst = InstanceDescriptor()
        inst.familyName, inst.styleName = "A", f"S{k}"
        inst.location = {"X000": 25 * k}
        doc.addInstance(inst)
    return doc


TEXT = "family A\naxes\n" + "".join(f"    X{i:03d} 0:50:100\n" for i in range(40)) + \
    "sources\n    A @base\ninstances auto\n"


@pytest.fixture(autouse=True)
def memory_cap():
    """A regression must fail here, not take the machine down"""
    if sys.platform != "linux":
        yield
        return
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, hard))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


def test_ds_to_dss_lists_the_instances_as_blocks():
    start = time.time()
    text, report = dssketch.convert_designspace_to_dss_string(wide_designspace(), return_report=True)
    assert time.time() - start < 5
    issue = report.find(CATEGORY_INSTANCES, INSTANCE_AUTO_TOO_MANY)
    assert issue is not None and issue.raw_data["count"] == 3 ** 40
    section = text[text.index("\ninstances") + 1:]
    assert section.startswith("instances\n    S0\n") and "auto" not in section


def test_sketch_text_is_an_error_and_queries_stay_empty():
    found = [d for d in diagnose(TEXT) if d.code == "5.66"]
    assert len(found) == 1 and found[0].line == TEXT.count("\n") and "limit is 1000" in found[0].message
    assert Sketch.parse(TEXT).instances() == []
    with pytest.raises(ValueError, match="instances auto would generate"):
        DSSParser().parse(TEXT)


def test_dss_to_ds_generates_none_and_reports():
    doc = DSSParser(strict_mode=False).parse(TEXT)
    from dssketch.converters.dss_to_designspace import DSSToDesignSpace

    converter = DSSToDesignSpace()
    ds = converter.convert(doc)
    assert ds.instances == []
    assert converter.report.find(CATEGORY_INSTANCES, INSTANCE_AUTO_TOO_MANY) is not None


def test_limit_itself():
    assert MAX_AUTO_INSTANCES == 1000
    text = "family A\naxes\n" + "".join(f"    X{i:03d} 0:50:100\n" for i in range(6)) + "sources\n    A @base\ninstances auto\n"
    assert len(Sketch.parse(text).instances()) == 3 ** 6  # 729: under the limit
    assert str(TooManyInstances(2187)).startswith("instances auto would generate 2,187 instances")
