"""avar2 checks in the validator (1.5.x)."""

from pathlib import Path

import pytest

import dssketch
from dssketch import codes, diagnose

EXAMPLES = Path(__file__).parent.parent / "examples"

BASE = """\
family T
axes
    wght 100:400:900
        Thin > 100
        Regular > 420 @elidable
        700 Bold > 600
        Black > 900
axes hidden
    XOPQ 0:50:100
sources [wght]
    T-Thin [Thin]
    T-Regular [Regular] @base
    T-Black [Black]
instances off
"""


def with_avar2(rows, section="avar2"):
    return BASE + section + "\n" + "".join(f"    {row}\n" for row in rows)


def found(text, name):
    wanted = codes.CODES[name].id
    return [d for d in diagnose(text) if d.code == wanted]


def avar2_codes(text):
    return sorted(codes.lookup(d.code).name for d in diagnose(text) if codes.lookup(d.code).name.startswith("AVAR2"))


def test_clean_mappings_are_silent():
    text = with_avar2(["[wght=Regular] > XOPQ=$", "[wght=Black] > XOPQ=80", "[wght=Thin] > XOPQ=20"])
    assert avar2_codes(text) == []


# -- default location -----------------------------------------------------------


def test_default_input_moving_an_output_is_a_warning():
    text = with_avar2(["[wght=Regular] > XOPQ=60", "[wght=Black] > XOPQ=80"])
    (d,) = found(text, "AVAR2_DEFAULT_INPUT")
    assert d.severity == "warning" and d.line == 16
    assert text.split("\n")[15][d.column: d.end_column] == "XOPQ"
    assert "default 50" in d.message and "(+10)" in d.message


def test_default_input_compares_with_the_design_default():
    # wght default 400 sits at design 420; `$` and 420 are both the default
    assert not found(with_avar2(["[wght=Regular] > wght=420"]), "AVAR2_DEFAULT_INPUT")
    assert found(with_avar2(["[wght=Regular] > wght=400"]), "AVAR2_DEFAULT_INPUT")


def test_axes_written_at_their_default_count_as_left_out():
    text = with_avar2(["[wght=400, XOPQ=50] > XOPQ=70"])
    assert found(text, "AVAR2_DEFAULT_INPUT")


def test_default_input_does_not_stop_conversion():
    ds = dssketch.convert_dss_string_to_designspace(with_avar2(["[wght=Regular] > XOPQ=60"]))
    assert ds.axisMappings


def test_amstelvar_example_has_one():
    text = (EXAMPLES / "AmstelvarA2-Roman_avar2.dssketch").read_text(encoding="utf-8")
    (d,) = found(text, "AVAR2_DEFAULT_INPUT")
    assert "'YTOS' to 10" in d.message and "default 11" in d.message


# -- ranges ---------------------------------------------------------------------


def test_input_outside_the_range_is_clamped():
    (d,) = found(with_avar2(["[wght=1200] > XOPQ=80"]), "AVAR2_INPUT_OUT_OF_RANGE")
    assert d.severity == "warning" and "clamps it to 900" in d.message


def test_input_that_looks_like_a_design_value_is_an_error():
    text = BASE.replace("Thin > 100", "Thin > 50") + "avar2\n    [wght=60] > XOPQ=80\n"
    (d,) = found(text, "AVAR2_INPUT_OUT_OF_RANGE")
    assert d.severity == "error" and "design-space value" in d.message


def test_output_range_is_design_space():
    # wght user 100..900 is design 100..900 here; a hidden axis has no map
    (d,) = found(with_avar2(["[wght=Black] > XOPQ=120"]), "AVAR2_OUTPUT_OUT_OF_RANGE")
    assert d.severity == "warning" and "[0, 100]" in d.message and "clamps it to 100" in d.message
    mapped = BASE.replace("Black > 900", "Black > 1000")
    assert not found(mapped + "avar2\n    [wght=Black] > wght=950\n", "AVAR2_OUTPUT_OUT_OF_RANGE")


# -- unknown axes, duplicates ---------------------------------------------------


def test_unknown_axis_is_an_error_reported_once():
    text = with_avar2(["outputs XOQP", "[wght=Black] 80", "[wght=Thin] 20"], section="avar2 matrix")
    (d,) = found(text, "AVAR2_UNKNOWN_AXIS")
    assert d.severity == "error" and "Did you mean 'XOPQ'?" in d.message
    with pytest.raises(ValueError, match="XOQP"):
        dssketch.convert_dss_string_to_designspace(text)


def test_unknown_input_axis():
    (d,) = found(with_avar2(["[wdth=50] > XOPQ=80"]), "AVAR2_UNKNOWN_AXIS")
    assert "'wdth'" in d.message


def test_duplicate_locations():
    rows = ["[wght=Black] > XOPQ=80", "[wght=900, XOPQ=50] > XOPQ=85"]
    (d,) = found(with_avar2(rows), "AVAR2_DUPLICATE_INPUT")
    assert d.severity == "error" and d.line == 17 and "(line 16)" in d.message


def test_clamped_inputs_collide():
    rows = ["[wght=Black] > XOPQ=80", "[wght=1000] > XOPQ=85"]
    assert found(with_avar2(rows), "AVAR2_DUPLICATE_INPUT")


def test_several_no_op_rows_at_the_default_are_fine():
    # avar2.dssketch has [wght=400] > wght=$ and [wdth=100] > wdth=$
    assert not found(with_avar2(["[wght=400] > wght=$", "[XOPQ=50] > XOPQ=$"]), "AVAR2_DUPLICATE_INPUT")


# -- hidden and visible axes ----------------------------------------------------


def test_hidden_axis_as_input_is_warned_once():
    rows = ["[XOPQ=80] > wght=800", "[XOPQ=20] > wght=200"]
    (d,) = found(with_avar2(rows), "AVAR2_HIDDEN_INPUT")
    assert d.severity == "warning" and "do not chain" in d.message


def test_visible_axis_driven_only_by_outputs():
    text = BASE.replace("axes hidden\n", "").replace("    XOPQ 0:50:100\n", "")
    text = text.replace("        Black > 900\n", "        Black > 900\n    XOPQ 0:50:100\n")
    text += "avar2\n    [wght=Black] > XOPQ=80\n"
    (d,) = found(text, "AVAR2_OUTPUT_ONLY_VISIBLE")
    assert d.severity == "warning" and d.line == 8
    # an axis that is also an input is remapped on purpose (fontTools' avar2 example)
    assert not found(with_avar2(["[wght=Black] > wght=800"]), "AVAR2_OUTPUT_ONLY_VISIBLE")


@pytest.mark.parametrize(
    "name",
    ["avar2", "avar2Fences", "avar2OpticalSize", "avar2QuadraticRotation"],
)
def test_fonttools_examples_are_clean(name):
    for suffix in ("", "-linear"):
        text = (EXAMPLES / f"{name}{suffix}.dssketch").read_text(encoding="utf-8")
        assert avar2_codes(text) == [], name + suffix


def test_hidden_axis_coordinates_are_not_counted_as_extra():
    # Amstelvar: named coordinates fill in every axis, hidden ones included;
    # the source still has one coordinate per visible axis
    from pathlib import Path

    from dssketch import diagnose

    path = Path(__file__).parent.parent / "examples" / "AmstelvarA2-Roman_avar2.dssketch"
    assert not [d for d in diagnose(path.read_text(encoding="utf-8")) if d.code == "5.31"]
