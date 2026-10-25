"""Localized names in explicit instance blocks (1.6.0): `style.de: Fett`,
`family.de`, `stylemapstyle.de`, `stylemapfamily.de`; `lang` derives the rest,
language by language.
"""

import pytest

import dssketch
from dssketch import DSSParser, Sketch, apply_edits, complete, diagnose, tokenize
from dssketch.structure import build

TEXT = """\
family T
lang de, ru
axes
    wght 100:400:900
        Thin > 100
        Regular > 400 @elidable
        Bold > 700
        Black > 900
sources [wght]
    A [Thin]
    B [Regular] @base
    C [Black]
instances auto
    Book
        location: wght=350
        family.ru: Т Текст
        style: Book
        style.de: Buchtext
"""


def back(text=TEXT):
    return dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())


def by_style(ds):
    return {i.styleName: i for i in ds.instances}


def test_parsed():
    block = DSSParser().parse(TEXT).instances[0]
    assert block.localized == {"style": {"de": "Buchtext"}, "family": {"ru": "Т Текст"}}


def test_explicit_wins_lang_derives_the_rest():
    book = by_style(back())["Book"]
    assert book.localisedStyleName["de"] == "Buchtext"      # its own
    assert book.localisedStyleName["ru"]                    # from the dictionary
    assert book.localisedFamilyName == {"ru": "Т Текст"}
    assert by_style(back())["Bold"].localisedStyleName["de"]  # generated ones as before


@pytest.mark.parametrize("line, part", [
    ("        style.d3: X\n", "not a language code"),
    ("        style.de: X\n", "given twice"),
    ("        postscript.de: X\n", "unknown key"),
])
def test_errors(line, part):
    found = [d for d in diagnose(TEXT + line) if d.code == "5.60"]
    assert found and part in found[0].message


def test_round_trip():
    ds = back()
    out = dssketch.convert_designspace_to_dss_string(ds)
    assert "lang de, ru" in out
    assert "        style.de: Buchtext\n" in out and "        family.ru: Т Текст\n" in out
    assert "style.ru" not in out  # the dictionary gives it
    names = lambda d: {i.styleName: (dict(i.localisedStyleName), dict(i.localisedFamilyName)) for i in d.instances}
    assert names(back(out)) == names(ds)


def test_a_few_hand_translations_keep_lang():
    ds = back(TEXT.split("    Book\n")[0])
    by_style(ds)["Bold"].localisedStyleName["de"] = "Kräftig"
    out, report = dssketch.convert_designspace_to_dss_string(ds, return_report=True)
    assert "lang de, ru" in out
    section = out[out.index("\ninstances"):]
    assert "    Bold\n" in section and "        style.de: Kräftig\n" in section
    assert "    skip\n        Bold\n" in section  # the generated Bold gives way to the block
    assert by_style(back(out))["Bold"].localisedStyleName["de"] == "Kräftig"


def test_tokens_structure_and_completion():
    tokens = [(t.text, t.type) for t in tokenize(TEXT) if t.line == 18]
    assert tokens[:2] == [("style.de", "keyword"), (":", "punctuation")]
    line = build(TEXT).line(18)
    assert line.values["key"] == "style.de" and line.values["value"] == "Buchtext"
    text = TEXT + "        "
    offered = [c.text for c in complete(text, 19, 8)]
    assert "style.ru" in offered and "style.de" not in offered


def test_sketch_operations():
    sk = Sketch.parse(TEXT)
    r = sk.set_instance_field(0, "style.ru", "Книжный")
    keys = [ln.strip().split(":")[0] for ln in r.text.splitlines()[14:]]
    assert keys == ["location", "family.ru", "style", "style.de", "style.ru"]
    r = sk.set_instance_field(0, "style.de", None)
    assert "style.de" not in r.text
    with pytest.raises(dssketch.EditError):
        sk.set_instance_field(0, "style.x1", "X")
    assert sk.item_at(18, 12) == ("instance", 0, "style.de")
    r = sk.add_instance("Light", {"wght": 300}, **{"style.de": "Leicht"})
    assert r.text.endswith("    Light\n        location: wght=300\n        style.de: Leicht\n")


def test_apply_writes_a_changed_localized_name():
    ds = back()
    by_style(ds)["Book"].localisedStyleName["de"] = "Buchschrift"
    result, report = Sketch.parse(TEXT).apply_designspace(ds)
    assert [i for i in report if i.category == 6] == []
    assert "        style.de: Buchschrift\n" in result.text
    assert apply_edits(TEXT, result.edits) == result.text
    result, _ = Sketch.parse(TEXT).apply_designspace(back())
    assert result.edits == []
