"""
Every generated DesignSpace names the all-elided location.

Without elidedFallbackName, the STAT-derived name of the default style is empty.
fontmake/ufo2ft (splitInterpolable with makeNames) put that name into the
variable font's fvar, so its Regular named instance ended up unnamed.
"""

import logging

from fontTools.designspaceLib.split import splitInterpolable, splitVariableFonts

import dssketch

SKETCH = """\
family T
axes
    wght 100:400:700
        Thin > 100
        400 {regular} > 400 @elidable
        Bold > 700
    ital discrete
        Upright @elidable
        Italic
sources [wght, ital]
    A [Thin, Upright]
    B [{regular}, Upright] @base
    C [Bold, Upright]
    D [{regular}, Italic] @base
instances auto
"""


def _fvar_names(ds):
    """Named-instance names as varLib._add_fvar would take them after ufo2ft's split"""
    logging.disable(logging.WARNING)
    try:
        names = {}
        for _, sub in splitInterpolable(ds):
            for _, vf in splitVariableFonts(sub):
                for instance in vf.instances:
                    names[instance.styleName] = instance.localisedStyleName.get("en", instance.styleName)
        return names
    finally:
        logging.disable(logging.NOTSET)


def test_elided_fallback_is_the_elidable_weight_label():
    for regular in ("Regular", "Book"):
        ds = dssketch.convert_dss_string_to_designspace(SKETCH.format(regular=regular))
        assert ds.elidedFallbackName == regular


def test_default_named_instance_is_not_empty_after_split(tmp_path):
    ds = dssketch.convert_dss_string_to_designspace(SKETCH.format(regular="Regular"))
    path = tmp_path / "t.designspace"
    ds.write(str(path))
    from fontTools.designspaceLib import DesignSpaceDocument

    names = _fvar_names(DesignSpaceDocument.fromfile(str(path)))
    assert names["Regular"] == "Regular"
    assert all(names.values())
