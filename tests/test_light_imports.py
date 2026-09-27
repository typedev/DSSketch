"""
The parse path must not import the UFO stack (issue #7).

A diff tool reads a .dssketch from git, where the UFOs it names are not on
disk, so it needs DSSParser -> DSSDocument and nothing more. Each check runs in
a fresh interpreter: sys.modules in the test process is already polluted.
"""

import subprocess
import sys
import textwrap

import pytest

HEAVY = ("defcon", "fontParts", "fontTools")


def _loaded_after(code: str) -> list:
    script = textwrap.dedent(code) + textwrap.dedent(
        f"""
        import sys
        print(",".join(m for m in {HEAVY!r} if m in sys.modules))
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return [m for m in out.split(",") if m]


@pytest.mark.parametrize(
    "code",
    [
        "import dssketch",
        "import dssketch.parsers.dss_parser",
        "from dssketch.parsers import DSSParser",
        "from dssketch import DSSParser, DSSWriter, DSSDocument, ConversionReport",
    ],
)
def test_import_is_light(code):
    assert _loaded_after(code) == []


SKETCH = """\
family Test
axes
    wght 100:400:900
        Thin > 100
        Regular > 400
        Black > 900
sources [wght]
    Test-Thin [Thin]
    Test-Regular [Regular] @base
    Test-Black [Black]
instances auto
"""


def test_parse_and_write_is_light():
    code = f"""
        from dssketch import DSSParser, DSSWriter
        doc = DSSParser().parse({SKETCH!r})
        assert len(doc.axes) == 1 and len(doc.sources) == 3
        DSSWriter().write(doc)
    """
    assert _loaded_after(code) == []


def test_heavy_names_still_importable_from_package_root():
    code = """
        from dssketch import (
            DSSToDesignSpace,
            DesignSpaceToDSS,
            UFOValidator,
            ValidationReport,
            convert_designspace_to_dss_string,
            convert_dss_string_to_designspace,
            convert_to_designspace,
            convert_to_dss,
        )
        import dssketch
        for name in dssketch.__all__:
            getattr(dssketch, name)
    """
    # Converters need designspaceLib, but defcon is only needed to open a UFO
    assert "defcon" not in _loaded_after(code)


def test_unknown_attribute_still_raises():
    import dssketch

    with pytest.raises(AttributeError):
        dssketch.no_such_thing
