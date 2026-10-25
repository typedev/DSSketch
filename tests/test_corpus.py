"""The local corpus of real avar2/HOI DesignSpaces (tests/corpus/, not in git;
see notes) round-trips: axes, sources, instances, avar2 and rules come back
the same, and apply_designspace makes no edits. Skipped without the corpus."""

import resource
import sys
from pathlib import Path

import pytest

CORPUS = Path(__file__).parent / "corpus"

# Real fonts and tool test data; the lint/repro probes are broken on purpose
CLEAN = [
    "local/amstelvar-Italic.designspace", "local/amstelvar-Roman-src.designspace",
    "local/amstelvar-Roman_v2.designspace", "local/robotodelta-Italic.designspace",
    "local/robotodelta-Roman-src.designspace", "remote/cmu-avar2-Italic.designspace",
    "remote/cmu-avar2-Roman.designspace", "remote/fencer-AmstelvarA2-Roman_avar2_v2.designspace",
    "remote/ffhoi-FRBFontForgeHOIExample.designspace", "remote/fontra-DemoAvar2.designspace",
    "remote/fontra-DemoAvar2-NLI.designspace", "remote/fonttools-BuildAvar2.designspace",
    "remote/fonttools-test_avar2.designspace", "remote/norad-with_mappings.designspace",
]


@pytest.fixture(autouse=True)
def memory_cap():
    if sys.platform != "linux":
        yield
        return
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3, hard))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


def _round(v):
    return None if v is None else round(float(v), 4)


def _summary(ds):
    from dssketch.converters.designspace_to_dss import DesignSpaceToDSS

    defaults = {a.name: a.map_forward(a.default) for a in ds.axes}

    def full(item):
        loc = DesignSpaceToDSS._full_location(ds, item)
        return tuple(sorted((k, _round(v)) for k, v in dict(defaults, **{k: v for k, v in loc.items() if k in defaults}).items()))

    axes = sorted((a.tag, a.name, bool(a.hidden), tuple(_round(v) for v in getattr(a, "values", None) or ()),
                   tuple(_round(a.map_forward(a.minimum + (a.maximum - a.minimum) * k / 32)) for k in range(33))
                   if not getattr(a, "values", None) else ()) for a in ds.axes)
    sources = sorted((s.filename or "", s.layerName or "", full(s)) for s in ds.sources)
    instances = sorted((i.familyName or "", i.styleName or "", full(i)) for i in ds.instances)
    avar2 = sorted((tuple(sorted((k, _round(v)) for k, v in m.inputLocation.items() if _round(v) != _round(defaults[k]))),
                    tuple(sorted((k, _round(v)) for k, v in m.outputLocation.items()))) for m in ds.axisMappings)
    return axes, sources, instances, avar2


@pytest.mark.parametrize("name", CLEAN)
def test_round_trip(name):
    path = CORPUS / name
    if not path.exists():
        pytest.skip("corpus not present")
    from fontTools.designspaceLib import DesignSpaceDocument

    import dssketch
    from dssketch import Sketch

    ds = DesignSpaceDocument.fromfile(path)
    text = dssketch.convert_designspace_to_dss_string(ds)
    back = dssketch.convert_dss_string_to_designspace(text, font_data=dssketch.FontData())
    assert _summary(back) == _summary(ds)
    result, report = Sketch.parse(text).apply_designspace(ds)
    assert result.edits == [] and not [i for i in report if i.category == 6]


def test_every_file_converts_without_crashing():
    from fontTools.designspaceLib import DesignSpaceDocument

    import dssketch

    files = sorted(CORPUS.rglob("*.designspace")) if CORPUS.exists() else []
    if not files:
        pytest.skip("corpus not present")
    for path in files:
        try:
            ds = DesignSpaceDocument.fromfile(path)
        except Exception:
            continue  # fontTools rejects it: not ours to read
        dssketch.convert_designspace_to_dss_string(ds)
