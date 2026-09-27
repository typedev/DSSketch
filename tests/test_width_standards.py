"""
Standard width values follow the OpenType spec.

OS/2 usWidthClass "% of normal", which the spec gives as the mapping to 'wdth'
values; CSS font-width keywords use the same percentages.
https://learn.microsoft.com/en-us/typography/opentype/spec/os2#uswidthclass
"""

import json
from pathlib import Path

import pytest
import yaml

from dssketch import DSSParser, Standards
from dssketch.utils.dss_validator import DSSValidator

DATA = Path(__file__).parent.parent / "src" / "dssketch" / "data"

SPEC = {
    "UltraCondensed": (1, 50),
    "ExtraCondensed": (2, 62.5),
    "Condensed": (3, 75),
    "SemiCondensed": (4, 87.5),
    "Normal": (5, 100),
    "SemiExpanded": (6, 112.5),
    "Expanded": (7, 125),
    "ExtraExpanded": (8, 150),
    "UltraExpanded": (9, 200),
}

ALIASES = {
    "Compressed": "UltraCondensed",
    "SemiCompressed": "ExtraCondensed",
    "Narrow": "SemiCondensed",
    "Wide": "SemiExpanded",
    "SemiExtended": "SemiExpanded",
    "Extended": "Expanded",
    "ExtraExtended": "ExtraExpanded",
    "UltraExtended": "UltraExpanded",
}


@pytest.mark.parametrize("name,expected", SPEC.items())
def test_spec_names(name, expected):
    os2, user = expected
    assert Standards.get_os2_value(name, "width") == os2
    assert Standards.get_user_space_value(name, "width") == user
    assert Standards.get_name_by_user_space(user, "width") == name


@pytest.mark.parametrize("alias,target", ALIASES.items())
def test_aliases(alias, target):
    assert Standards.get_user_space_value(alias, "width") == SPEC[target][1]


def test_json_fallback_matches_yaml():
    with open(DATA / "unified-mappings.yaml", encoding="utf-8") as f:
        from_yaml = yaml.safe_load(f)
    with open(DATA / "unified-mappings.json", encoding="utf-8") as f:
        from_json = json.load(f)
    assert from_json == from_yaml


def test_stylenames_classes_match():
    with open(DATA / "stylenames.json", encoding="utf-8") as f:
        width_names = json.load(f)["width_names"]
    for name, cls in width_names.items():
        assert cls == Standards.get_os2_value(name, "width"), name


def test_label_only_width_resolves_to_spec_value():
    doc = DSSParser().parse(
        """\
family T
axes
    wdth 75:100:125
        Condensed > 75
        Normal > 100 @elidable
        Expanded > 125
sources [wdth]
    T-Condensed [Condensed]
    T-Normal [Normal] @base
    T-Expanded [Expanded]
"""
    )
    assert [m.user_value for m in doc.axes[0].mappings] == [75, 100, 125]


def test_alias_is_not_reported_as_label_mismatch():
    doc = DSSParser().parse(
        """\
family T
axes
    wdth 50:100:100
        Compressed > 50
        Normal > 100 @elidable
    wght 200:400:400
        ExtraLight > 200
        Regular > 400 @elidable
sources [wdth, wght]
    T-A [Compressed, ExtraLight]
    T-B [Normal, Regular] @base
"""
    )
    validator = DSSValidator()
    validator.validate_document(doc)
    assert not [w for w in validator.warnings if "typically uses label" in w]
