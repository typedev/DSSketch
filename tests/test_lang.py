"""
`lang de, ru`: derived names in more languages, from the translation dictionary.

DSS -> DS writes localized instance style names, STAT label names and axis
names. DS -> DSS writes `lang` only when the document's localized names are
exactly what the dictionary gives; otherwise it reports the difference.
"""

import pytest

import dssketch
from dssketch import (
    CATEGORY_DOCUMENT,
    DOCUMENT_TRANSLATION_MISSING,
    DOCUMENT_TRANSLATIONS_DIFFER,
    DSSParser,
    DSSWriter,
)
from dssketch.core.translations import Translations

SKETCH = """\
family T
lang {langs}
axes
    wght 100:400:900
        Thin > 100
        ExtraLight > 200
        Regular > 400 @elidable
        Bold > 700
        Black > 900
    ital discrete
        Upright @elidable
        Italic
sources [wght, ital]
    A [Thin, Upright]
    B [Regular, Upright] @base
    C [Black, Upright]
    D [Regular, Italic] @base
instances auto
"""


def _convert(langs="ru, de"):
    return dssketch.convert_dss_string_to_designspace(SKETCH.format(langs=langs), return_report=True)


def test_parse_and_write_lang():
    parser = DSSParser(strict_mode=False)
    doc = parser.parse(SKETCH.format(langs="de, ru es-419"))
    assert doc.languages == ["de", "ru", "es-419"]
    assert "lang de, ru, es-419" in DSSWriter().write(doc)


def test_bad_codes_and_en():
    parser = DSSParser(strict_mode=False)
    doc = parser.parse(SKETCH.format(langs="en, ru, 12"))
    assert doc.languages == ["ru"]
    assert any("'12' is not a language code" in e for e in parser.validator.errors)
    assert any("'en' is always written" in w for w in parser.validator.warnings)


def test_instance_style_names_are_translated_word_by_word():
    ds, _ = _convert()
    by_name = {i.styleName: i.localisedStyleName for i in ds.instances}
    assert by_name["Bold Italic"] == {"ru": "Жирный Курсив", "de": "Fett Kursiv"}
    # ExtraLight (label) matches the dictionary's "Extralight"
    assert by_name["ExtraLight"]["ru"] == "Экстра-светлый"


def test_stat_labels_and_axis_names_are_translated():
    ds, _ = _convert()
    wght = next(a for a in ds.axes if a.tag == "wght")
    assert wght.labelNames["ru"] == "Вес"
    assert {label.name: label.labelNames.get("de") for label in wght.axisLabels}["Bold"] == "Fett"
    ital = next(a for a in ds.axes if a.tag == "ital")
    assert {label.name: label.labelNames.get("ru") for label in ital.axisLabels} == {
        "Upright": "Прямой", "Italic": "Курсив"
    }


def test_missing_words_stay_english_and_are_reported():
    text = SKETCH.format(langs="ru").replace("Black > 900", "900 Ultra > 900").replace("[Black, Upright]", "[Ultra, Upright]")
    ds, report = dssketch.convert_dss_string_to_designspace(text, return_report=True)
    assert {i.styleName: i.localisedStyleName["ru"] for i in ds.instances}["Ultra Italic"] == "Ultra Курсив"
    issue = report.find(CATEGORY_DOCUMENT, DOCUMENT_TRANSLATION_MISSING)
    assert issue.raw_data == {"language": "ru", "words": ["Ultra"]}


def test_unknown_language_is_reported_and_left_out():
    ds, report = _convert("ru, xx")
    assert all("xx" not in i.localisedStyleName for i in ds.instances)
    assert report.find(CATEGORY_DOCUMENT, DOCUMENT_TRANSLATION_MISSING).raw_data["language"] == "xx"


def test_designspace_generated_with_lang_roundtrips_to_lang():
    ds, _ = _convert()
    sketch, report = dssketch.convert_designspace_to_dss_string(ds, return_report=True)
    assert "lang de, ru" in sketch
    assert not report.find(CATEGORY_DOCUMENT, DOCUMENT_TRANSLATIONS_DIFFER)
    assert not [i for i in report if "localized" in i.description]


def test_hand_made_translation_is_not_replaced():
    ds, _ = _convert()
    next(i for i in ds.instances if i.styleName == "Bold").localisedStyleName["ru"] = "Полужирный"
    sketch, report = dssketch.convert_designspace_to_dss_string(ds, return_report=True)
    assert "lang" not in sketch.split("axes")[0]
    issue = report.find(CATEGORY_DOCUMENT, DOCUMENT_TRANSLATIONS_DIFFER)
    assert issue and any("Полужирный" in d for d in issue.raw_data["differences"])


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Hairline", "Волосяной"),
        ("Heavy", "Тяжёлый"),
        ("UltraCondensed", "Ультраузкий"),
        ("ExtraCondensed", "Экстра-узкий"),
        ("SemiCompressed", "Экстра-узкий"),  # alias of ExtraCondensed
        ("UltraExpanded", "Ультра Раздвинутый"),
        ("Upright", "Прямой"),
        ("Roman", "Прямой"),
        ("Slant", "Наклонённый"),
        ("Semibold", "Полужирный"),
        ("SemiBold", "Полужирный"),
    ],
)
def test_dictionary_covers_standard_labels(label, expected):
    assert Translations.label(label, "ru") == expected


def test_every_language_has_every_word():
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).parent.parent / "src/dssketch/data/font-resources-translations.json").read_text()
    )
    sections = [s for s in data if s != "WEIGHT_EN_DEFAULTS"]
    languages = {lang for s in sections for entry in data[s].values() for lang in entry}
    assert len(languages) >= 40
    gaps = [(s, key, lang) for s in sections for key, entry in data[s].items() for lang in languages if lang not in entry]
    assert gaps == []


@pytest.mark.parametrize("language", ["it", "pl", "cs", "pt-PT", "sr-Latn", "bg", "vi"])
def test_new_languages_translate_style_names(language):
    ds, report = _convert(language)
    assert all(language in i.localisedStyleName for i in ds.instances)
    assert not report.find(CATEGORY_DOCUMENT, DOCUMENT_TRANSLATION_MISSING)
