"""Build minimal probe .designspace files for DSSketch expressibility research.
Each probe isolates ONE feature family from the DesignSpace 5 spec.
Run with: uv run python build_probes.py   (from the DSSketch repo, or anywhere with dssketch installed)
"""
import os
from fontTools.designspaceLib import (
    DesignSpaceDocument, AxisDescriptor, DiscreteAxisDescriptor, AxisLabelDescriptor,
    LocationLabelDescriptor, VariableFontDescriptor, RangeAxisSubsetDescriptor,
    ValueAxisSubsetDescriptor, SourceDescriptor, InstanceDescriptor, RuleDescriptor,
    AxisMappingDescriptor,
)

OUT = os.path.dirname(os.path.abspath(__file__))


def base_axis(tag="wght", name="weight", minimum=100, default=400, maximum=900):
    a = AxisDescriptor()
    a.tag, a.name, a.minimum, a.default, a.maximum = tag, name, minimum, default, maximum
    a.map = [(minimum, minimum), (default, default), (maximum, maximum)]
    a.axisLabels = [
        AxisLabelDescriptor(name="Regular", userValue=default, elidable=True),
        AxisLabelDescriptor(name="Bold", userValue=maximum),
    ]
    return a


def write(doc, fname):
    path = os.path.join(OUT, fname)
    doc.write(path)
    print("wrote", path)


# ---------------------------------------------------------------------------
# 1. Axis STAT-label richness: userMinimum/userMaximum (format 2), linkedUserValue
#    (format 3), olderSibling, elidable, localized labelname (axis + label),
#    plus axis-level labelNames (display name localization) and axisOrdering.
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
a = AxisDescriptor()
a.tag, a.name = "wght", "weight"
a.minimum, a.default, a.maximum = 100, 400, 900
a.map = [(100, 100), (400, 400), (700, 700), (900, 900)]
a.axisOrdering = 3
a.labelNames = {"en": "Weight", "fr": "Graisse", "de": "Schriftstärke"}
a.axisLabels = [
    AxisLabelDescriptor(
        name="Light", userValue=300, userMinimum=100, userMaximum=349,
        labelNames={"fr": "Léger"},
    ),
    AxisLabelDescriptor(
        name="Regular", userValue=400, userMinimum=350, userMaximum=549,
        elidable=True, labelNames={"fr": "Normal"},
    ),
    AxisLabelDescriptor(
        name="Bold", userValue=700, userMinimum=550, userMaximum=849,
        linkedUserValue=400,  # format 3: Bold links back to Regular (900-shaped "bold checkbox")
    ),
    AxisLabelDescriptor(
        name="Black", userValue=900, userMinimum=850, userMaximum=900,
        olderSibling=True,
    ),
]
doc.addAxis(a)
s1 = SourceDescriptor(); s1.filename = "Regular.ufo"; s1.name = "S1"; s1.location = {"weight": 400}; s1.copyInfo = True; s1.familyName = "Probe"; s1.styleName = "Regular"
s2 = SourceDescriptor(); s2.filename = "Bold.ufo"; s2.name = "S2"; s2.location = {"weight": 900}; s2.familyName = "Probe"; s2.styleName = "Bold"
doc.addSource(s1); doc.addSource(s2)
i1 = InstanceDescriptor(); i1.familyName = "Probe"; i1.styleName = "Regular"; i1.location = {"weight": 400}
doc.addInstance(i1)
write(doc, "probe_axis_stat_labels.designspace")

# ---------------------------------------------------------------------------
# 2. Axis hidden flag (explicit, format 5), discrete axis with values + labels,
#    axisOrdering across mixed continuous/discrete axes.
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
wght.axisOrdering = 0
doc.addAxis(wght)

hidden_axis = AxisDescriptor()
hidden_axis.tag, hidden_axis.name = "GRAD", "GRAD"
hidden_axis.minimum, hidden_axis.default, hidden_axis.maximum = -200, 0, 150
hidden_axis.hidden = True
hidden_axis.axisOrdering = 1
doc.addAxis(hidden_axis)

ital = DiscreteAxisDescriptor()
ital.tag, ital.name = "ital", "italic"
ital.values = [0, 1]
ital.default = 0
ital.axisOrdering = 2
ital.axisLabels = [
    AxisLabelDescriptor(name="Upright", userValue=0, elidable=True),
    AxisLabelDescriptor(name="Italic", userValue=1),
]
doc.addAxis(ital)

for name, loc in [
    ("Regular-Upright", {"weight": 400, "GRAD": 0, "italic": 0}),
    ("Bold-Upright", {"weight": 900, "GRAD": 0, "italic": 0}),
    ("Regular-Italic", {"weight": 400, "GRAD": 0, "italic": 1}),
    ("Bold-Italic", {"weight": 900, "GRAD": 0, "italic": 1}),
]:
    s = SourceDescriptor(); s.filename = f"{name}.ufo"; s.name = name; s.location = loc
    if loc["weight"] == 400 and loc["italic"] == 0:
        s.copyInfo = True
        s.familyName = "Probe"
        s.styleName = "Regular"
    doc.addSource(s)
write(doc, "probe_hidden_discrete_ordering.designspace")

# ---------------------------------------------------------------------------
# 3. Document-level location labels (<labels>/<label>, STAT format 4)
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
wdth = AxisDescriptor(); wdth.tag = "wdth"; wdth.name = "width"; wdth.minimum = 75; wdth.default = 100; wdth.maximum = 125
wdth.map = [(75, 75), (100, 100), (125, 125)]
wdth.axisLabels = [AxisLabelDescriptor(name="Condensed", userValue=75), AxisLabelDescriptor(name="Normal", userValue=100, elidable=True)]
doc.addAxis(wght); doc.addAxis(wdth)
doc.locationLabels.append(LocationLabelDescriptor(name="Bold Condensed", userLocation={"weight": 900, "width": 75}))
doc.locationLabels.append(LocationLabelDescriptor(name="Reading", userLocation={"weight": 400}, elidable=True, labelNames={"fr": "Lecture"}))
s1 = SourceDescriptor(); s1.filename = "Regular.ufo"; s1.location = {"weight": 400, "width": 100}; s1.copyInfo = True
s1.familyName = "Probe"; s1.styleName = "Regular"
s2 = SourceDescriptor(); s2.filename = "Bold-Condensed.ufo"; s2.location = {"weight": 900, "width": 75}
s2.familyName = "Probe"; s2.styleName = "Bold Condensed"
doc.addSource(s1); doc.addSource(s2)
write(doc, "probe_location_labels.designspace")

# ---------------------------------------------------------------------------
# 4. variable-fonts / axis-subsets, including a discrete value-subset
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
doc.addAxis(wght)
ital = DiscreteAxisDescriptor(); ital.tag = "ital"; ital.name = "italic"; ital.values = [0, 1]; ital.default = 0
ital.axisLabels = [AxisLabelDescriptor(name="Upright", userValue=0, elidable=True), AxisLabelDescriptor(name="Italic", userValue=1)]
doc.addAxis(ital)
for name, loc in [("Regular", {"weight": 400, "italic": 0}), ("Bold", {"weight": 900, "italic": 0}),
                   ("Italic", {"weight": 400, "italic": 1}), ("BoldItalic", {"weight": 900, "italic": 1})]:
    s = SourceDescriptor(); s.filename = f"{name}.ufo"; s.location = loc
    if name == "Regular":
        s.copyInfo = True
        s.familyName = "Probe"
        s.styleName = "Regular"
    doc.addSource(s)
vf_roman = VariableFontDescriptor(
    name="ProbeVF-Roman",
    filename="ProbeVF-Roman.ttf",
    axisSubsets=[RangeAxisSubsetDescriptor(name="weight"), ValueAxisSubsetDescriptor(name="italic", userValue=0)],
)
vf_italic = VariableFontDescriptor(
    name="ProbeVF-Italic",
    filename="ProbeVF-Italic.ttf",
    axisSubsets=[RangeAxisSubsetDescriptor(name="weight", userMinimum=400, userMaximum=900, userDefault=400),
                 ValueAxisSubsetDescriptor(name="italic", userValue=1)],
    lib={"com.example.note": "italic cut"},
)
doc.addVariableFont(vf_roman)
doc.addVariableFont(vf_italic)
write(doc, "probe_variable_fonts.designspace")

# ---------------------------------------------------------------------------
# 5. Source-level richness: name attr distinct from filename stem, familyName/
#    styleName override, localisedFamilyName, muteInfo, muteKerning,
#    mutedGlyphNames, copy* flags, userLocation.
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
doc.addAxis(wght)
s1 = SourceDescriptor()
s1.filename = "Regular.ufo"
s1.name = "master.regular"
s1.location = {"weight": 400}
s1.copyInfo = True; s1.copyLib = True; s1.copyGroups = True; s1.copyFeatures = True
s1.familyName = "Probe"; s1.styleName = "Regular"
doc.addSource(s1)
s2 = SourceDescriptor()
s2.filename = "Bold.ufo"
s2.name = "master.bold.correction"
s2.location = {"weight": 900}
s2.familyName = "Probe Special"
s2.styleName = "Bold Correction"
s2.localisedFamilyName = {"fr": "Probe Spécial"}
s2.muteInfo = True
s2.muteKerning = True
s2.mutedGlyphNames = ["A", "Z"]
doc.addSource(s2)
write(doc, "probe_source_richness.designspace")

# ---------------------------------------------------------------------------
# 6. Instance richness: postScriptFontName, styleMap*, localised*, lib,
#    locationLabel reference, userLocation (vs designLocation), glyphs (per-
#    instance glyph masters override).
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
doc.addAxis(wght)
doc.locationLabels.append(LocationLabelDescriptor(name="Reading", userLocation={"weight": 400}))
s1 = SourceDescriptor(); s1.filename = "Regular.ufo"; s1.location = {"weight": 400}; s1.copyInfo = True
s1.familyName = "Probe"; s1.styleName = "Regular"
s2 = SourceDescriptor(); s2.filename = "Bold.ufo"; s2.location = {"weight": 900}
s2.familyName = "Probe"; s2.styleName = "Bold"
doc.addSource(s1); doc.addSource(s2)
i1 = InstanceDescriptor()
i1.familyName = "Probe"
i1.styleName = "Regular"
i1.postScriptFontName = "Probe-Regular"
i1.styleMapFamilyName = "Probe"
i1.styleMapStyleName = "regular"
i1.localisedFamilyName = {"fr": "Sonde"}
i1.localisedStyleName = {"fr": "Normal"}
i1.lib = {"com.example.note": "hello"}
i1.userLocation = {"weight": 400}
doc.addInstance(i1)
i2 = InstanceDescriptor()
i2.name = "reading-instance"
i2.locationLabel = "Reading"
i2.familyName = "Probe"
i2.styleName = "Reading Style"
doc.addInstance(i2)
write(doc, "probe_instance_richness.designspace")

# ---------------------------------------------------------------------------
# 7. Rules: processing="last" (document level), multiple conditionsets (OR
#    semantics) inside one rule, rule name, one-sided conditions (already
#    fixed per notes/roundtrip-fidelity-issues.md — probe only confirms).
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
wdth = AxisDescriptor(); wdth.tag = "wdth"; wdth.name = "width"; wdth.minimum = 75; wdth.default = 100; wdth.maximum = 125
wdth.map = [(75, 75), (100, 100), (125, 125)]
doc.addAxis(wght); doc.addAxis(wdth)
s1 = SourceDescriptor(); s1.filename = "Regular.ufo"; s1.location = {"weight": 400, "width": 100}; s1.copyInfo = True
s1.familyName = "Probe"; s1.styleName = "Regular"
s2 = SourceDescriptor(); s2.filename = "Bold.ufo"; s2.location = {"weight": 900, "width": 100}
s2.familyName = "Probe"; s2.styleName = "Bold"
doc.addSource(s1); doc.addSource(s2)
doc.rulesProcessingLast = True
rule = RuleDescriptor()
rule.name = "orRule"
rule.conditionSets = [
    [{"name": "weight", "minimum": 700}],          # set A: bold OR
    [{"name": "width", "minimum": 0, "maximum": 80}],  # set B: condensed
]
rule.subs = [("dollar", "dollar.alt")]
doc.addRule(rule)
write(doc, "probe_rules_or_processing.designspace")

# ---------------------------------------------------------------------------
# 8. Document-level <lib>, formatVersion, elidedFallbackName
# ---------------------------------------------------------------------------
doc = DesignSpaceDocument()
wght = base_axis()
doc.addAxis(wght)
doc.elidedFallbackName = "Regular"
doc.lib = {"com.example.buildNotes": "handle with care", "com.github.fonttools.varLib.featureVarsFeatureTag": "rvrn"}
s1 = SourceDescriptor(); s1.filename = "Regular.ufo"; s1.location = {"weight": 400}; s1.copyInfo = True
s1.familyName = "Probe"; s1.styleName = "Regular"
s2 = SourceDescriptor(); s2.filename = "Bold.ufo"; s2.location = {"weight": 900}
s2.familyName = "Probe"; s2.styleName = "Bold"
doc.addSource(s1); doc.addSource(s2)
write(doc, "probe_doclevel_lib.designspace")

print("done")
