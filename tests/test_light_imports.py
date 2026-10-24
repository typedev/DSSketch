"""
The parse path must not import the UFO stack (issue #7).

A diff tool reads a .dssketch from git, where the UFOs it names are not on
disk, so it needs DSSParser -> DSSDocument and nothing more. Each check runs in
a fresh interpreter: sys.modules in the test process is already polluted.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HEAVY = ("defcon", "fontParts", "fontTools")
MEGAFONT = str(Path(__file__).parent.parent / "examples" / "MegaFont-WithSkip.dssketch")


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
        "from dssketch.syntax import tokenize, diagnose",
        "from dssketch.gtksourceview import language_spec",
        "from dssketch import Sketch; Sketch.parse('family T\\naxes\\n    wght 1:2:3\\nsources\\n    A @base').diagnostics",
        "from dssketch import Sketch; Sketch.parse('family T').set_family('U')",
        "import dssketch.codes, dssketch.structure, dssketch.fixes, dssketch.fontdata",
        "from dssketch import diagnose, FontData, DefconFontData; diagnose('sources\\n    A @base', font_data=FontData()); DefconFontData('.').glyph_names('nope.ufo')",
        "from dssketch import diagnose; diagnose('familly T\\naxes\\n    wgjt 1:2:3')",
        "import dssketch.queries, dssketch.core.instances",
        f"from dssketch import Sketch; s = Sketch.parse(open({MEGAFONT!r}).read()); s.instances(); s.source_locations(); s.rule_regions(); s.substitutions_at({{'weight': 900}}, ['dollar', 'dollar.rvrn']); s.user_to_design('wght', 700)",
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


def test_editor_calls_are_light():
    code = f"""
        from dssketch import tokenize, diagnose
        assert tokenize({SKETCH!r})
        assert not [d for d in diagnose({SKETCH!r}) if d.severity == "error"]
        from dssketch import complete
        assert complete({SKETCH!r}, 8, 16)
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
