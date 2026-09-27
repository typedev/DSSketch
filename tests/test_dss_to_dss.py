"""
DSSketch → DSSParser → DSSWriter → DSSketch keeps what the source wrote.

DSSketch sits above DesignSpace: a wildcard rule or an explicit user value is a
DSS-level statement. On the way to DesignSpace it is resolved (against UFOs, or
the standards table); on the way back to DSSketch it must survive as written.
"""

import os
import subprocess
import sys
import textwrap

import pytest

from dssketch import DSSParser, DSSWriter

SKETCH = """\
family Test
axes
    wght 100:400:900
        Thin > 100
        300 Light > 280
        Regular > 400 @elidable
        Bold > 700
        Black > 900
        MyCustom > 850
sources [wght]
    Test-Thin [Thin]
    Test-Regular [Regular] @base
    Test-Black [Black]
rules
    A > A.alt (weight >= Bold) "single"
    dollar cent > .heavy (weight >= Bold)
    * > .rvrn (weight >= Bold)
    A* > .alt (weight <= Regular)
    dollar* cent* > .rvrn (weight >= Bold) "heavy alternates"
    a b > a.x b.x (weight >= Bold)
instances auto
"""


def _rules(doc):
    return [(r.name, r.pattern, r.to_pattern, r.substitutions, r.conditions) for r in doc.rules]


def test_pattern_rules_survive_write():
    doc = DSSParser().parse(SKETCH)
    out = DSSWriter().write(doc)  # used to raise IndexError on the first pattern rule

    assert "    dollar cent > .heavy " in out
    assert "    * > .rvrn " in out
    assert "    A* > .alt " in out
    assert '    dollar* cent* > .rvrn (weight >= Bold) "heavy alternates"' in out
    assert "    a b > a.x b.x " in out
    assert _rules(DSSParser().parse(out)) == _rules(doc)


def test_user_value_explicit_flag():
    doc = DSSParser().parse(SKETCH)
    flags = {m.label: m.user_value_explicit for m in doc.axes[0].mappings}
    assert flags == {
        "Thin": False,  # standards table
        "Light": True,  # written: 300 Light > 280
        "Regular": False,
        "Bold": False,
        "Black": False,
        "MyCustom": False,  # user = design
    }


def test_explicit_user_value_is_written_back_even_if_standard():
    # 400 is the standard value for Regular; the source still pinned it
    sketch = SKETCH.replace("Regular > 400 @elidable", "400 Regular > 400 @elidable")
    out = DSSWriter().write(DSSParser().parse(sketch))
    assert "        400 Regular > 400 @elidable" in out
    assert "        Thin > 100" in out  # inferred ones stay compact


def test_designspace_origin_keeps_compact_form():
    from dssketch import DesignSpaceToDSS
    from dssketch.converters.dss_to_designspace import DSSToDesignSpace

    sketch = SKETCH.split("rules")[0] + "instances off\n"
    ds = DSSToDesignSpace().convert(DSSParser().parse(sketch))
    dss_doc = DesignSpaceToDSS().convert(ds)
    assert not any(m.user_value_explicit for a in dss_doc.axes for m in a.mappings)
    assert "        Thin > 100" in DSSWriter().write(dss_doc)


def test_parse_creates_no_user_data_dir(tmp_path):
    data_dir = tmp_path / "dssketch-data"
    script = textwrap.dedent(
        f"""
        from dssketch import DSSParser
        DSSParser().parse({SKETCH!r}.replace("wght 100:400:900", "ital discrete\\n        Upright\\n        Italic\\n    wght 100:400:900").replace("[Thin]", "[Upright, Thin]").replace("[Regular]", "[Upright, Regular]").replace("[Black]", "[Upright, Black]").replace("sources [wght]", "sources [ital, wght]"))
        """
    )
    env = dict(os.environ, DSSKETCH_DATA_DIR=str(data_dir))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert not data_dir.exists()


def test_writing_user_data_creates_dir(tmp_path, monkeypatch):
    from dssketch.config import DataManager

    data_dir = tmp_path / "dssketch-data"
    monkeypatch.setenv("DSSKETCH_DATA_DIR", str(data_dir))
    dm = DataManager()
    assert not data_dir.exists()
    assert dm.copy_package_to_user("discrete-axis-labels.yaml")
    assert (data_dir / "discrete-axis-labels.yaml").is_file()


def test_one_sided_conditions_stay_open():
    doc = DSSParser().parse(SKETCH)
    by_name = {r.name: r.conditions for r in doc.rules}
    assert by_name["single"] == [{"axis": "weight", "minimum": 700.0, "maximum": None}]
    assert by_name["rule4"] == [{"axis": "weight", "minimum": None, "maximum": 400.0}]

    out = DSSWriter().write(doc)
    assert '    A > A.alt (weight >= Bold) "single"' in out
    assert "    A* > .alt (weight <= Regular)" in out


def test_open_condition_reaches_designspace_open(tmp_path):
    from fontTools.designspaceLib import DesignSpaceDocument

    from dssketch import DesignSpaceToDSS
    from dssketch.converters.dss_to_designspace import DSSToDesignSpace

    sketch = SKETCH.split("rules")[0] + 'rules\n    A > A.alt (weight >= Bold) "single"\ninstances off\n'
    ds = DSSToDesignSpace().convert(DSSParser().parse(sketch))
    path = tmp_path / "t.designspace"
    ds.write(str(path))

    xml = path.read_text()
    assert '<condition name="weight" minimum="700"/>' in xml  # no invented maximum

    reread = DesignSpaceDocument.fromfile(str(path))
    assert reread.rules[0].conditionSets == [[{"name": "weight", "minimum": 700, "maximum": None}]]
    assert "(weight >= Bold)" in DSSWriter().write(DesignSpaceToDSS().convert(reread))
