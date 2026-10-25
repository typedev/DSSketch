# avar2 / HOI test corpus

`tests/test_corpus.py` round-trips real DesignSpaces from `tests/corpus/`
(not in git: third-party files). Without the folder the tests skip.
Run any sweep over it under a memory cap (`ulimit -v 3000000`) and a timeout
per file: an unbounded `instances auto` once took the machine down.

## remote/ (public repositories)

| file | source |
|---|---|
| fontra-DemoAvar2(-NLI).designspace | fontra/fontra `test-py/data/avar2/` — NLI = HOI on hidden axes |
| cmu-avar2-Roman/Italic.designspace | gferreira/computer-modern-avar2 `Sources/` |
| fencer-AmstelvarA2-Roman_avar2_v2.designspace | Lorp/fencer `demos/04-parametric/` |
| fonttools-*.designspace | fonttools/fonttools `Tests/designspaceLib/data/test_avar2`, `Tests/varLib/data/BuildAvar*` |
| norad-with_mappings / v5.designspace | linebender/norad `testdata/` |
| ffhoi-FRBFontForgeHOIExample.designspace | ctrlcctrlv/FontForge-Higher-Order-Interpolation |

Fetch: `gh api repos/<repo>/contents/<path> --jq .download_url` and `curl`.

## local/

- googlefonts/roboto-delta sources: Roman, Italic, RobotoFlex1, fenceLocation
- googlefonts/amstelvar-avar2 sources: Roman, Roman_v2, Italic
- designspace-lint audit probes (`docs/audit/2026-09-coverage/probes/`), broken on purpose
- `notes/research-2026-09/repro/avar2/probe1-3`

## Status (2026-10-25)

All real fonts and tool test files round-trip (axes, sources, instances,
avar2) and `apply_designspace` makes no edits. What does not: files fontTools
itself rejects (4), and DesignSpaces fontTools could not build either — probes
of bad ranges and base sources, avar2 rows repeating an output or naming an
unknown axis (RobotoFlex1 names `Grade` for an axis called `GRAD`), rules on
undefined axes (norad v5), a mappings-only helper file (fenceLocation).
