# Instance parameters in DesignSpace 4 and 5, and what DSSketch does with them

Sources: fontTools 4.60.1 `designspaceLib` (`InstanceDescriptor`, the XML
reader/writer, `statNames.py`, `split.py`), `varLib._add_fvar`, and ufo2ft 3.x
`instantiator.py`. fontmake delegates static instance generation to ufo2ft.

## What an `<instance>` can carry

| Field (XML) | DS | VF build (`fvar`) | Static build (ufo2ft) | Derivable from STAT (`getStatNames`) |
|---|---|---|---|---|
| `name` | 4, 5 | – | – | identifier only |
| `filename` | 4, 5 | – | output path | `Family-Style` |
| `<location>` `xvalue` / `yvalue` (anisotropic) | 4, 5 | coordinates | location (anisotropic → error) | – |
| `<location>` `uservalue` | 5 | same | same | – |
| `location="label"` (location label) | 5 | same | same | – |
| `familyname` + `<familyname xml:lang>` | 4, 5 | **unused** | `familyName`, nameID 16 per language | default source `familyname` + its localized names |
| `stylename` + `<stylename xml:lang>` | 4, 5 | subfamily of the named instance, per language | `styleName`, nameID 17 per language | axis labels (+`labelNames`), minus elidable ones, in `axisOrdering`; empty → `elidedFallbackName` |
| `postscriptfontname` | 4, 5 | postscriptNameID | `postscriptFontName` | `Family-Style` without spaces |
| `stylemapfamilyname` + `xml:lang` | 4, 5 | – | nameID 1 | family + the style of the RIBBI "regular" partner |
| `stylemapstylename` + `xml:lang` | 4, 5 | – | nameID 2, fsSelection | RIBBI via `linkedUserValue` (Regular→Bold on wght, Upright→Italic on ital/slnt) |
| `<lib>` incl. `public.fontInfo` | 4, 5 | – | **any fontinfo field**, highest priority | no |
| `<glyphs>`, `<kerning>`, `<info>` | 4 only | – | – | deprecated (MutatorMath) |

The root `<lib>` `public.fontInfo` applies to every instance, below the instance's
own fields.

## The key fact: in DS5, names are optional and derived

`splitInterpolable(makeNames=True)` is what fontmake and ufo2ft call. It fills any
name an instance lacks from `getStatNames()`: family, style, PostScript name,
style-map family/style, and every localization. An explicit field always wins.
So DS5's own model is "the labels describe, the names follow, and explicit values
are overrides". That is DSSketch's `instances auto` philosophy. DSSketch lacks
only part of the STAT vocabulary needed to express it.

## Where DSSketch diverges today

1. **No `linkedUserValue`, so no style linking.** For `SuperFont` after
   `splitInterpolable`:

   | instance | as generated today | with Regular→Bold, Upright→Italic linked |
   |---|---|---|
   | Bold | `SuperFont Bold` / regular | `SuperFont` / bold |
   | Italic | `SuperFont Italic` / regular | `SuperFont` / italic |
   | Bold Italic | `SuperFont Bold Italic` / regular | `SuperFont` / bold italic |
   | Black Italic | `SuperFont Black Italic` / regular | `SuperFont Black` / italic |

   Static fonts built from a sketch have no RIBBI linking at all.
2. **The naming rule differs from STAT.** DSSketch never elides the weight label
   ("Compressed Regular"), while `getStatNames` elides every `@elidable` label
   ("Compressed"). This gives 45 of 315 names in MegaFont. With nothing left,
   STAT needs `elidedFallbackName`, which DSSketch cannot express: SuperFont's
   Regular derives to `""`.
3. **Every instance gets explicit family/style/PS names**, which makes them
   overrides. The style-map names are never written.
4. **No localization.** Label names, family names and style-map names exist in
   English only.
5. `public.fontInfo` per instance, anisotropic locations and location labels are
   not expressible. They are reported on DS → DSS (1.3.0).

## Real files

- MegaFont, SuperFont, TestFont: `instances auto` reproduces every position. The
  names differ only as in point 2.
- GoogleSansFlex: the axes have no labels. 18 named instances lie on `wght` ×
  hidden `slnt`, with every other axis at its default. 17 positions are
  unreachable for `instances auto`. Every instance carries explicit style-map
  names.
