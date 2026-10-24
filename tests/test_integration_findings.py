"""What Font-Rover found while integrating 1.5.0 (fixed in 1.5.1)."""

from pathlib import Path

import pytest
from fontTools.designspaceLib import DesignSpaceDocument

import dssketch
from dssketch import codes, diagnose

EXAMPLES = Path(__file__).parent.parent / "examples"

# A designer's own scale: standard labels at user values of 0..1000
MUTATOR = """\
family M
axes
    wght 0:0:1000
        0 Light > 0 @elidable
        500 Regular > 500
        1000 Bold > 1000
    wdth 0:0:1000
        0 Condensed > 0 @elidable
        1000 Wide > 1000
sources [wght, wdth]
    M-LightCondensed [Light, Condensed] @base
    M-BoldCondensed [Bold, Condensed]
    M-LightWide [Light, Wide]
    M-BoldWide [Bold, Wide]
instances auto
"""

NONSTANDARD = codes.CODES["MAPPING_NONSTANDARD_USER"].id


def test_own_scale_is_one_warning_per_axis():
    found = [d for d in diagnose(MUTATOR) if d.code == NONSTANDARD]
    by_axis = {}
    for d in found:
        by_axis.setdefault(d.message.split("'")[1], []).append(d)
    assert set(by_axis) == {"weight", "width"}
    # one message per kind (label moved / value relabelled) and axis, at most
    assert all(len(ds) <= 2 for ds in by_axis.values())
    moved = next(d for d in by_axis["weight"] if "standard labels are at other user values" in d.message)
    assert "'Light' 0 (usually 300)" in moved.message and "'Bold' 1000 (usually 700)" in moved.message
    assert moved.line == 4 and MUTATOR.split("\n")[3][moved.column: moved.end_column] == "Light"


def test_a_single_case_keeps_the_old_message():
    one = MUTATOR.replace("500 Regular > 500", "Regular > 500").replace("1000 Bold > 1000", "Bold > 1000")
    found = [d.message for d in diagnose(one) if d.code == NONSTANDARD and "'weight'" in d.message]
    assert any("label 'Light' typically maps to user_value 300" in m for m in found)


def test_string_conversion_accepts_a_path():
    path = EXAMPLES / "SuperFont-6x2.designspace"
    from_path = dssketch.convert_designspace_to_dss_string(str(path))
    assert from_path == dssketch.convert_designspace_to_dss_string(DesignSpaceDocument.fromfile(str(path)))
    assert dssketch.convert_designspace_to_dss_string(path) == from_path  # a Path too


def test_anything_else_is_a_type_error():
    with pytest.raises(TypeError, match="DesignSpaceDocument or a path"):
        dssketch.convert_designspace_to_dss_string(42)
