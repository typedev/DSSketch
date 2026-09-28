# Style-name translations awaiting review

`src/dssketch/data/font-resources-translations.json` feeds `lang` (DSSketch
1.4+). Words in a font's name table are shown to users, so every language
should be checked by a native speaker, ideally one who knows type terminology.

## Added 2026-09-28, not yet reviewed

Weights, slopes and axis names were written word by word. Widths were composed
from a base word (Compressed, Condensed, Narrow, Normal, Wide, Extended,
Expanded) and a modifier (Extra, Semi, Ultra), following each language's
compounding rule. The generator is kept with the research notes.

| Confidence | Languages | Notes |
|---|---|---|
| higher | it, pl, cs, sk, sl, ro, nb, ca, bg, pt-PT | Bold and Italic follow Microsoft Office's terms (Grassetto/Corsivo, Pogrubiony/Kursywa, Tučné/Kurzíva, Krepko/Ležeče, Aldin/Cursiv, Fet/Kursiv, Negreta/Cursiva, Получер/Курсив). The rarer weights (Hairline, Book, Heavy) and the Ultra widths are my own choices |
| medium | hu, be, mk, et, lv, lt, is, vi, id | hu: "Félkövér" is used for Bold, as in Office, so Semibold became "Közepesen félkövér". Check this first |
| lower | ky, tt, uz, az | Turkic languages: the compounds (Өтө/Бик/Juda/Çox + base) and Hairline need a native check |
| derived | pt-PT, sr-Latn | pt-PT copies pt; sr-Latn is a mechanical transliteration of sr |

Deliberately left out: ba, tg, mn, eu, gl, and CJK, Arabic and Hebrew. My
translations were not reliable enough for these, and CJK and RTL families
localize the family name rather than style words.

`Book` stays in English for it, ro and ca, where no settled term exists.

## Known limitation outside DSSketch

`es-419` (Latin American Spanish) is valid: Windows LCID 0x580A, since
Windows 8.1. fontTools' language table, as of 4.66, lacks it, so a
fontTools-based compiler writes it as a language-less platform-0 record and
Windows never shows it. The other 39 languages are written as Windows records.
The fix belongs in fontTools (`_WINDOWS_LANGUAGES`) or in the compiler.
