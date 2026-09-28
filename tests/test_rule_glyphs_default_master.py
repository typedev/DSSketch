"""
Rule glyphs are checked against the default master, the set varLib uses.

A wildcard used to be expanded against every source together, so a target that
existed only in a sparse master passed and the build then failed in varLib.
Explicit rules were not checked at all.
"""

import defcon
import pytest

import dssketch
from dssketch.converters import dss_to_designspace


def _ufo(path, glyphs):
    font = defcon.Font()
    font.info.familyName = "T"
    font.info.unitsPerEm = 1000
    for name in glyphs:
        font.newGlyph(name)
    font.save(str(path))


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
    Bold-sparse [Bold] @sparse
rules
    {rule}
instances off
"""


@pytest.fixture
def project(tmp_path):
    src = tmp_path / "sources"
    src.mkdir()
    _ufo(src / "Regular.ufo", ["a", "dollar", "cent", "cent.rvrn"])
    _ufo(src / "Bold.ufo", ["a", "dollar", "cent", "cent.rvrn"])
    _ufo(src / "Bold-sparse.ufo", ["dollar", "dollar.rvrn", "a.alt"])
    return tmp_path


def _convert(project, rule):
    return dssketch.convert_dss_string_to_designspace(SKETCH.format(rule=rule), base_path=str(project))


def test_wildcard_ignores_targets_only_in_a_sparse_master(project):
    ds = _convert(project, '* > .rvrn (weight >= Bold) "heavy"')
    # cent.rvrn is in the default master; dollar.rvrn only in the sparse one
    assert [r.subs for r in ds.rules] == [[("cent", "cent.rvrn")]]


def test_explicit_rule_with_glyph_missing_from_default_master_is_reported(project, monkeypatch):
    messages = []
    monkeypatch.setattr(dss_to_designspace.DSSketchLogger, "warning", staticmethod(messages.append))
    ds = _convert(project, 'a > a.alt (weight >= Bold) "alt"')
    assert [r.subs for r in ds.rules] == [[("a", "a.alt")]]  # kept as written
    assert any("'a.alt'" in m and "default master" in m for m in messages)


def test_explicit_rule_inside_default_master_is_quiet(project, monkeypatch):
    messages = []
    monkeypatch.setattr(dss_to_designspace.DSSketchLogger, "warning", staticmethod(messages.append))
    _convert(project, 'cent > cent.rvrn (weight >= Bold) "ok"')
    assert not [m for m in messages if "default master" in m]


def test_without_ufos_explicit_rules_convert_as_before():
    ds = dssketch.convert_dss_string_to_designspace(SKETCH.format(rule='a > a.alt (weight >= Bold) "alt"'))
    assert [r.subs for r in ds.rules] == [[("a", "a.alt")]]
