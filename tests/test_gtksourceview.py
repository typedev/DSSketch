"""The GtkSourceView language definition (data/dssketch.lang).

It is generated from DSSketch's tables, so the shipped file must equal the
generator's output. Where GtkSourceView 5 is installed (PyGObject, often only
in the system Python), the definition is loaded and its highlighting compared
with tokenize() on every example and on a sketch with every line form.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from dssketch import tokenize
from dssketch.gtksourceview import LANG_PATH, language_spec, language_spec_path
from dssketch.syntax import TOKEN_TYPES

HERE = os.path.dirname(__file__)
EXAMPLES = sorted(glob.glob(os.path.join(HERE, "..", "examples", "*.dssketch")))

EVERY_FORM = """\
family Sans Pro  # note
suffix VF
lang de, ru
path sources
axes
    weight wght 100:400:900 "Weight"
        100 > 100
        200 Thin > 175
        Regular > 400 @elidable
        Black > 900
    OPTICAL SIZE opsz 8:14:144
        Text > 14
    CONTRAST CNTR 0:0:100
        0 Flat > 0
        100 Sharp > 100
    ital discrete
        Upright @elidable
        Italic
    slnt -20:0:20
        -20 Reverse > -20
        0 Neutral > 0 @elidable
        20 Slant > 20
axes hidden
    XOUC 0:100:200
sources [wght, opsz, CNTR, ital, slnt]
    upright/Font-Thin.ufo [Thin, Text, Flat, Upright, Neutral]
    "My Font Light.ufo" [100, 14, 0, 0, 0] @sparse
    Font-Regular @base
    Font-Bold wght=900, CNTR=Sharp @layer 'bold#2'
    Font-Bold.ufo [Black, Text, Sharp, Italic, Slant] @layer=fg
rules
    dollar cent* > .rvrn (Regular <= weight <= Black && CONTRAST >= 50) "heavy #1"  # note
    a > a.alt (ital == 1)
instances auto
    skip
        Black Italic
avar2 vars
    $XO = 50
avar2
    "x" [wght=Black, opsz=Text] > XOUC=$XO, wght=$
    [wght=100] > {
        XOUC=-20
    }
avar2 matrix "m"
    outputs XOUC wght
    [opsz=Text]  84  -
"""


def test_shipped_file_is_generated():
    with open(LANG_PATH, encoding="utf-8") as f:
        assert f.read() == language_spec(), "run: python -m dssketch.gtksourceview --write"
    assert language_spec_path() == str(LANG_PATH)


def test_definition_is_consistent():
    root = ET.fromstring(language_spec().encode("utf-8"))
    assert root.get("id") == "dssketch"
    styles = [s.get("id") for s in root.iter("style")]
    assert styles == list(TOKEN_TYPES)

    contexts = root.find("definitions").findall("context")
    defined = {c.get("id") for c in contexts}
    for ref in root.iter("context"):
        if ref.get("ref"):
            assert ref.get("ref") in defined, ref.get("ref")
        if ref.get("style-ref"):
            assert ref.get("style-ref") in styles, ref.get("style-ref")
    assert "dssketch" in defined  # the main context carries the language id


# Run by a Python that has PyGObject: highlight with a scheme giving every
# style its own colour, read the colour at each token's first character
_CHECK = r"""
import json, os, sys, tempfile
import gi
gi.require_version("GtkSource", "5")
from gi.repository import GtkSource

data = json.load(open(sys.argv[1]))
GtkSource.init()
tmp = tempfile.mkdtemp()
colors = {t: "#%06x" % (i + 1) for i, t in enumerate(data["types"])}
with open(os.path.join(tmp, "probe.xml"), "w") as f:
    f.write('<?xml version="1.0"?>\n<style-scheme id="probe" name="probe" version="1.0">\n')
    for t, c in colors.items():
        f.write(f'  <style name="dssketch:{t}" foreground="{c}"/>\n')
    f.write("</style-scheme>\n")
by_color = {c: t for t, c in colors.items()}
lm = GtkSource.LanguageManager.new()
lm.set_search_path([data["lang_dir"]] + list(lm.get_search_path()))
lang = lm.get_language("dssketch")
assert lang is not None, "language did not load"
sm = GtkSource.StyleSchemeManager.new()
sm.set_search_path([tmp])
scheme = sm.get_scheme("probe")

def static_type(it):
    for tag in it.get_tags():
        if tag.props.foreground_set:
            c = tag.props.foreground_rgba
            key = "#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255))
            if key in by_color:
                return by_color[key]
    return None

wrong = []
for name, entry in data["files"].items():
    buf = GtkSource.Buffer.new_with_language(lang)
    buf.set_style_scheme(scheme)
    buf.set_text(entry["text"])
    buf.ensure_highlight(buf.get_start_iter(), buf.get_end_iter())
    for line, column, ttype, text in entry["tokens"]:
        got = static_type(buf.get_iter_at_line_offset(line - 1, column)[1])
        if got != ttype and {got, ttype} != {"axis-tag", "axis-name"}:
            wrong.append([name, line, text, ttype, got])
print(json.dumps(wrong))
"""


def _python_with_gtksource():
    candidates = [sys.executable, shutil.which("python3"), "/usr/bin/python3"]
    for python in dict.fromkeys(c for c in candidates if c):
        probe = subprocess.run(
            [python, "-c", "import gi; gi.require_version('GtkSource', '5')"],
            capture_output=True,
        )
        if probe.returncode == 0:
            return python
    return None


def test_highlighting_agrees_with_tokenize(tmp_path):
    python = _python_with_gtksource()
    if python is None:
        pytest.skip("GtkSourceView 5 (PyGObject) not installed")

    files = {os.path.basename(p): open(p, encoding="utf-8").read() for p in EXAMPLES}
    files["every-form"] = EVERY_FORM
    data = {
        "types": list(TOKEN_TYPES),
        "lang_dir": str(LANG_PATH.parent),
        "files": {
            name: {"text": text, "tokens": [[t.line, t.column, t.type, t.text] for t in tokenize(text)]}
            for name, text in files.items()
        },
    }
    data_path = tmp_path / "tokens.json"
    data_path.write_text(json.dumps(data))
    script = tmp_path / "check.py"
    script.write_text(_CHECK)

    result = subprocess.run([python, str(script), str(data_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    wrong = json.loads(result.stdout.strip().splitlines()[-1])
    assert wrong == [], wrong[:10]
