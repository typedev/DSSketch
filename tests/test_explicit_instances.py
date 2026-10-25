"""Explicit instances (1.5.x).

DS -> DSS leaves to `instances auto` every instance it reproduces (same design
position, style and family name, PostScript name, no style-map names), writes a
`skip` entry for each generated position the DesignSpace lacks, and lists every
other instance as an explicit block under `instances`:

    instances auto
        skip
            Display Thin
        Display Bold
            location: opsz=Display, wght=700
            family: A Display
            style: Bold
            postscript: ADisplay-Bold
            filename: instances/ADisplay-Bold.ufo

Locations are design space; a label stands for its design value.
"""

import json
from pathlib import Path

import pytest
from fontTools.designspaceLib import (
    AxisDescriptor,
    AxisLabelDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    SourceDescriptor,
)

import dssketch
from dssketch import DSSParser, Sketch, diagnose, tokenize
from dssketch.converters.designspace_to_dss import DesignSpaceToDSS
from dssketch.core.report import CATEGORY_INSTANCES, INSTANCE_EXTRA, INSTANCE_FIELDS_DROPPED
from dssketch.structure import build

EXAMPLES = Path(__file__).parent.parent / "examples"


def build_designspace(instances) -> DesignSpaceDocument:
    """A one-axis document whose labels generate exactly Regular and Bold
    (design 380 and 650)."""
    doc = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = "wght", "weight"
    axis.minimum, axis.default, axis.maximum = 400, 400, 700
    axis.map = [(400, 380), (700, 650)]
    axis.axisLabels = [
        AxisLabelDescriptor(name="Regular", userValue=400, elidable=True),
        AxisLabelDescriptor(name="Bold", userValue=700),
    ]
    doc.addAxis(axis)
    for coord, style in ((380, "Regular"), (650, "Bold")):
        src = SourceDescriptor()
        src.filename, src.familyName, src.styleName = f"T-{style}.ufo", "T", style
        src.location = {"weight": coord}
        doc.addSource(src)
    for style, coord in instances:
        inst = InstanceDescriptor()
        inst.familyName, inst.styleName = "T", style
        inst.postScriptFontName, inst.filename = f"T-{style}", f"instances/T-{style}.ufo"
        inst.location = {"weight": coord}
        doc.addInstance(inst)
    return doc


def to_dss(doc):
    return dssketch.convert_designspace_to_dss_string(doc)


def back(text):
    return dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())


def described(doc):
    return sorted(
        (i.familyName, i.styleName, i.postScriptFontName, i.styleMapFamilyName, i.styleMapStyleName,
         tuple(sorted(i.getFullDesignLocation(doc).items())))
        for i in doc.instances
    )


def instances_section(text):
    return text[text.index("\ninstances") + 1:]


# -- DS -> DSS ----------------------------------------------------------------------


def test_reproduced_instances_stay_auto():
    text = to_dss(build_designspace([("Regular", 380), ("Bold", 650)]))
    assert instances_section(text) == "instances auto"


def test_omitted_dimension_equals_the_default():
    doc = build_designspace([("Regular", 380), ("Bold", 650)])
    doc.instances[0].location = {}
    assert instances_section(to_dss(doc)) == "instances auto"


def test_filtered_designspace_gets_skip():
    doc = build_designspace([("Regular", 380)])
    text = to_dss(doc)
    assert instances_section(text) == "instances auto\n    skip\n        Bold"
    assert described(back(text)) == described(doc)


def test_unreachable_position_becomes_a_block():
    doc = build_designspace([("Regular", 380), ("SemiBold", 500), ("Bold", 650)])
    text = to_dss(doc)
    assert instances_section(text) == (
        "instances auto\n"
        "    SemiBold\n"
        "        location: wght=500\n"
        "        family: T\n"
        "        style: SemiBold\n"
        "        postscript: T-SemiBold\n"
        "        filename: instances/T-SemiBold.ufo"
    )
    assert described(back(text)) == described(doc)


def test_renamed_instance_skips_the_generated_one():
    doc = build_designspace([("Book", 380), ("Bold", 650)])
    text = to_dss(doc)
    section = instances_section(text)
    assert section.startswith("instances auto\n    skip\n        Regular\n    Book\n        location: wght=Regular\n")
    assert described(back(text)) == described(doc)


@pytest.mark.parametrize("field, value, line", [
    ("familyName", "T Display", "family: T Display"),
    ("postScriptFontName", "TPro-Heavy", "postscript: TPro-Heavy"),
    ("styleMapStyleName", "bold", "stylemapstyle: bold"),
    ("styleMapFamilyName", "T Bold", "stylemapfamily: T Bold"),
])
def test_hand_set_names_make_a_block(field, value, line):
    doc = build_designspace([("Regular", 380), ("Bold", 650)])
    setattr(doc.instances[1], field, value)
    if field == "familyName":
        doc.instances[1].postScriptFontName = "TDisplay-Bold"
    text = to_dss(doc)
    assert f"        {line}\n" in text + "\n"
    assert "    skip\n        Bold\n" in text
    assert described(back(text)) == described(doc)


def test_nothing_reproduced_lists_all_without_auto():
    doc = build_designspace([("Book", 380), ("Heavy", 650)])
    text = to_dss(doc)
    section = instances_section(text)
    assert section.startswith("instances\n    Book\n") and "skip" not in section
    assert described(back(text)) == described(doc)


def test_skip_cannot_name_a_kept_instance():
    doc = build_designspace([("Regular", 380), ("Bold", 650)])
    doc.instances[1].styleName = "Regular"  # Bold's position under Regular's name
    converter = DesignSpaceToDSS()
    dss = converter.convert(doc)
    # Bold's position holds an explicit "Regular"; auto's Bold is skipped
    assert dss.instances_skip == ["Bold"]
    assert [i.stylename for i in dss.instances] == ["Regular"]
    assert not converter.report.find(CATEGORY_INSTANCES, INSTANCE_EXTRA)


def test_failing_generator_leaves_every_instance_explicit(monkeypatch):
    monkeypatch.setattr(
        "dssketch.converters.designspace_to_dss.createInstances",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    dss = DesignSpaceToDSS().convert(build_designspace([("Regular", 380)]))
    assert not dss.instances_auto and [i.stylename for i in dss.instances] == ["Regular"]


def test_no_instances_is_instances_off():
    assert instances_section(to_dss(build_designspace([]))) == "instances off"


def test_report_stays_clean_and_serialises():
    doc = build_designspace([("Regular", 380), ("SemiBold", 500)])
    doc.instances[1].lib = {"com.example": 1}
    text, report = dssketch.convert_designspace_to_dss_string(doc, return_report=True)
    assert [i.id for i in report] == [f"{CATEGORY_INSTANCES}.{INSTANCE_FIELDS_DROPPED}"]
    json.dumps(report.to_dict())


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.designspace")), ids=lambda p: p.name)
def test_examples_keep_their_instances(path):
    doc = DesignSpaceDocument.fromfile(path)
    text = to_dss(doc)
    assert described(back(text)) == described(doc)


# -- parsing and DSS -> DS ------------------------------------------------------------

TEXT = """\
family A
axes
    opsz 8:14:144
        Text > 14
        Display > 144
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Black > 900
axes hidden
    XOPQ 0:50:100
sources
    A-Thin wght=Thin
    A-Regular @base
    A-Black wght=Black
    A-DisplayBlack opsz=Display, wght=Black
instances auto
    skip
        Display Thin
    Display Bold  # hand-made
        location: opsz=Display, wght=700, XOPQ=80
        family: "A Display"
        postscript: ADisplay-Bold
    "Wide # one"
        location: opsz=Text, wght=600
"""


def test_parse_block():
    doc = DSSParser().parse(TEXT)
    bold, wide = doc.instances
    assert bold.name == "Display Bold" and bold.familyname == "A Display" and bold.stylename == ""
    assert bold.location == {"optical": 144.0, "weight": 700.0, "XOPQ": 80.0}
    assert bold.postscriptname == "ADisplay-Bold" and bold.line == 20
    assert wide.name == "Wide # one" and wide.location == {"optical": 14.0, "weight": 600.0}
    assert doc.instances_skip == ["Display Thin"]


def test_dss_to_ds_derives_what_a_block_leaves_out():
    ds = back(TEXT)
    names = [i.styleName for i in ds.instances]
    assert "Display Thin" not in names and names[-2:] == ["Display Bold", "Wide # one"]
    bold, wide = ds.instances[-2:]
    assert (bold.familyName, bold.postScriptFontName, bold.filename) == (
        "A Display", "ADisplay-Bold", "instances/ADisplay-Bold.ufo")
    assert bold.location == {"optical": 144.0, "weight": 700.0, "XOPQ": 80.0}
    assert (wide.familyName, wide.postScriptFontName) == ("A", "A-Wide#one")


def test_written_back_quoted_and_read_again():
    ds = back(TEXT)
    text = to_dss(ds)
    assert '    "Wide # one"\n' in text
    assert described(back(text)) == described(ds)


def test_plain_instances_section_has_only_blocks():
    text = TEXT.replace("instances auto\n    skip\n        Display Thin\n", "instances\n")
    assert [i.styleName for i in back(text).instances] == ["Display Bold", "Wide # one"]


def test_instances_off_ignores_blocks():
    text = TEXT.replace("instances auto", "instances off")
    assert back(text).instances == []
    assert any(d.code == "5.63" for d in diagnose(text))


def test_skip_entries_stay_under_skip():
    # a line at skip's own indent opens a block, it is no longer a skip entry
    doc = DSSParser(strict_mode=False).parse(TEXT.replace("        Display Thin", "    Display Thin"))
    assert doc.instances_skip == [] and doc.instances[0].name == "Display Thin"


def test_diagnostics():
    bad = TEXT + "    Narrow\n        location: opsz=Text, wght=Black\n        famly: X\n    Lost\n        style: X\n"
    found = {(d.code, d.line) for d in diagnose(bad)}
    assert ("5.65", 26) in found  # Narrow sits on Text Black, which auto generates
    assert ("5.60", 28) in found and ("5.62", 29) in found
    assert not [d for d in diagnose(TEXT) if d.severity == "error"]


# -- editor views --------------------------------------------------------------------


def test_tokens():
    tokens = [(t.text, t.type) for t in tokenize(TEXT) if t.line in (20, 21, 22)]
    assert tokens == [
        ("Display Bold", "text"), ("# hand-made", "comment"),
        ("location", "keyword"), (":", "punctuation"), ("opsz", "axis-tag"), ("=", "punctuation"),
        ("Display", "label"), (",", "punctuation"), ("wght", "axis-tag"), ("=", "punctuation"),
        ("700", "number"), (",", "punctuation"), ("XOPQ", "axis-tag"), ("=", "punctuation"), ("80", "number"),
        ("family", "keyword"), (":", "punctuation"), ('"A Display"', "string"),
    ]


def test_structure():
    st = build(TEXT)
    block = st.line(20)
    assert block.kind == "instance" and block.values["name"] == "Display Bold"
    location = st.line(21)
    assert location.kind == "instance-field" and location.parent == 20
    assert location.values["location.wght"] == "700"
    assert st.line(22).values["value"] == "A Display"
    assert st.owned_lines(20) == (20, 23)
    assert st.line(24).values["name"] == "Wide # one"


# -- Sketch: queries, outline, operations, fixes, completion ------------------------


def test_sketch_instances_lists_blocks_after_the_generated():
    infos = Sketch.parse(TEXT).instances()
    blocks = [i for i in infos if i.explicit]
    assert [i.name for i in blocks] == ["Display Bold", "Wide # one"]
    bold = blocks[0]
    assert bold.index == len([i for i in infos if not i.skipped]) - 2
    assert bold.family_name == "A Display" and bold.style_name == "Display Bold"
    assert bold.design_location == {"optical": 144.0, "weight": 700.0, "XOPQ": 80.0}
    assert bold.span.line == 20
    # the same instances, in the same order, as DSS -> DS
    ds = back(TEXT)
    assert [i.name for i in infos if not i.skipped][-2:] == [i.styleName for i in ds.instances][-2:]


def test_outline_and_item_at():
    sk = Sketch.parse(TEXT)
    section = next(s for s in sk.outline() if s.name == "instances")
    assert [(c.kind, c.name, c.path) for c in section.children] == [
        ("skip", "Display Thin", ("skip", "Display Thin")),
        ("instance", "Display Bold", ("instance", 0)),
        ("instance", "Wide # one", ("instance", 1)),
    ]
    assert sk.item_at(20, 6) == ("instance", 0, "name")
    assert sk.item_at(21, 25) == ("instance", 0, "location", "opsz")
    assert sk.item_at(22, 18) == ("instance", 0, "family")
    assert sk.span(("instance", 0, "location", "wght")).col == 37


def test_operations():
    sk = Sketch.parse(TEXT)
    r = sk.add_instance("Display Black Wide", {"opsz": "Display", "wght": 850}, family="A Display")
    assert r.text.endswith("    Display Black Wide\n        location: opsz=Display, wght=850\n        family: A Display\n")
    r = r.sketch.set_instance_field(0, "filename", "a/b.ufo")
    assert "        postscript: ADisplay-Bold\n        filename: a/b.ufo\n" in r.text
    r = r.sketch.set_instance_field(0, "family", None)
    assert 'family: "A Display"' not in r.text
    r = r.sketch.set_instance_name(1, "Wide # two")
    assert '    "Wide # two"\n' in r.text
    r = r.sketch.set_instance_field(1, "location", "opsz=Text, wght=Black")
    assert "        location: opsz=Text, wght=Black\n" in r.text
    with pytest.raises(dssketch.EditError):
        r.sketch.set_instance_field(1, "location", "wght=Bolt")
    with pytest.raises(dssketch.EditError):
        r.sketch.set_instance_field(1, "location", None)
    r = r.sketch.remove_instance(0)
    assert "Display Bold" not in r.text and "# hand-made" not in r.text


def test_add_instance_creates_a_plain_section():
    text = TEXT[:TEXT.index("instances auto")]
    r = Sketch.parse(text).add_instance("Bold", {"wght": 700})
    assert r.text.endswith("instances\n    Bold\n        location: wght=700\n")
    assert [i.styleName for i in back(r.text).instances] == ["Bold"]


def test_instances_mode_none_drops_auto():
    r = Sketch.parse(TEXT).set_instances_mode(None)
    assert "\ninstances\n    skip\n" in r.text


def _apply_first_fix(text, code):
    d = next(d for d in Sketch.parse(text).diagnostics if d.code == code)
    return dssketch.apply_edits(text, d.fixes[0].edits)


def test_fixes():
    text = TEXT.replace("family: \"A Display\"", "famly: \"A Display\"")
    assert 'family: "A Display"' in _apply_first_fix(text, "5.60")
    text = TEXT.replace("wght=600", "wght=Blak")
    assert "wght=Black" in _apply_first_fix(text, "5.61")
    text = TEXT.replace("opsz=Text, wght=600", "opsz=Text, wght=Black")
    fixed = _apply_first_fix(text, "5.65")
    assert "        Display Thin\n        Text Black\n" in fixed
    assert not [d for d in Sketch.parse(fixed).diagnostics if d.code == "5.65"]


def test_completion():
    def offered(text, line, column):
        return [c.text for c in dssketch.complete(text, line, column)]

    lines = TEXT.split("\n")
    text = "\n".join(lines[:23] + ["        "] + lines[23:])
    keys = offered(text, 24, 8)
    assert "style" in keys and "location" not in keys and "family" not in keys
    text = "\n".join(lines[:24] + ["        location: "] + lines[24:])
    assert offered(text, 25, 18)[:2] == ["opsz", "wght"]
    text = "\n".join(lines[:24] + ["        location: wght="] + lines[24:])
    assert "Black" in offered(text, 25, 23)
    assert offered(TEXT + "    ", 26, 4) == ["skip"]
