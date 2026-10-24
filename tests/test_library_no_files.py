"""The library API never writes files next to its input (logs belong to the CLI)."""

import logging

import dssketch
from dssketch.utils.logging import DSSketchLogger

SKETCH = """family Test
axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900
sources [wght]
    Test-Thin [Thin]
    Test-Regular [Regular] @base
    Test-Black [Black]
instances off
"""


def test_convert_to_designspace_writes_no_log(tmp_path):
    DSSketchLogger.cleanup()
    path = tmp_path / "Test.dssketch"
    path.write_text(SKETCH, encoding="utf-8")

    ds = dssketch.convert_to_designspace(str(path))

    assert [a.tag for a in ds.axes] == ["wght"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Test.dssketch"]
    assert DSSketchLogger.get_logger() is None
    assert not logging.getLogger("dssketch").handlers
