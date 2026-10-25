"""Stable codes for the parser's and validator's messages

Every `syntax.Diagnostic` carries a `code` from this table, so an editor can
key quick fixes and documentation on it instead of on the wording. A code is
`"5.N"`: category 5 (Sketch) of the `ConversionReport` scheme, and N its
number here. `"5.0"` is a message without a code of its own.

**Codes are append-only**: never renumber or reuse one, callers switch on
them. A new message gets a new entry at the end; its pattern must match it
(`tests/test_diagnostic_codes.py` produces each one).

The messages come from many places (`DSSParser`, `DSSValidator`), so the
table recognises them by their wording; the first entry that matches wins.

Light: stdlib only.
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

CATEGORY = 5  # core.report.CATEGORY_SKETCH


@dataclass(frozen=True)
class Code:
    number: int
    name: str
    description: str

    @property
    def id(self) -> str:
        return f"{CATEGORY}.{self.number}"


# (number, name, pattern, description). Patterns are searched (re.search)
_TABLE: Tuple[Tuple[int, str, str, str], ...] = (
    (0, "UNCLASSIFIED", r"", "A message without a code of its own"),
    # -- document structure ----------------------------------------------------
    (1, "NO_AXES", r"^(?:CRITICAL: )?No axes found", "The sketch declares no axis"),
    (2, "NO_SOURCES", r"^No sources found", "The sketch declares no source"),
    (3, "NO_BASE", r"^(?:CRITICAL: )?No base source found", "No source has @base"),
    (4, "MULTIPLE_BASE", r"^(?:CRITICAL: )?Multiple base sources", "More than one source has @base"),
    (5, "BASE_NOT_AT_DEFAULT", r"^(?:CRITICAL: )?Base source '.*' coordinates", "The base source is not at the axis defaults"),
    (6, "AXIS_RANGE_EMPTY", r"^(?:CRITICAL: )?Axis '.*' (?:has invalid range|does not vary)", "An axis with min = max"),
    (7, "AXIS_INCOMPLETE", r"^(?:CRITICAL: )?Axis \d+ missing name or tag", "An axis without name or tag"),
    (8, "DUPLICATE_LABEL", r"^(?:CRITICAL: )?Mapping label '.*' is used in multiple axes", "A label used on two axes"),
    (9, "BASE_AUTO_DETECTED", r"^Auto-detected base source", "No @base; the source at the defaults was taken"),
    # -- header lines ----------------------------------------------------------
    (10, "FAMILY_EMPTY", r"^Family name is empty|^No family name specified", "No family name"),
    (11, "PATH_EMPTY", r"^Path value is empty", "`path` without a value"),
    (12, "LANG_INVALID", r"^lang: '.*' is not a language code|^lang: no language given", "A bad `lang` code"),
    (13, "LANG_EN", r"^lang: 'en' is always written", "`en` listed in `lang`"),
    # -- keywords and lines ----------------------------------------------------
    (14, "KEYWORD_TYPO", r"^Unknown keyword '.*'\. Did you mean", "A misspelt keyword"),
    (15, "KEYWORD_NON_ASCII", r"^Invalid section keyword", "A keyword with non-ASCII characters"),
    (16, "KEYWORD_UNPROCESSED", r"^Possible section keyword", "A keyword where it is not read"),
    (17, "UNRECOGNIZED_LINE", r"^Unrecognized line", "A line outside any section"),
    (18, "BRACKETS", r"^Bracket issues", "Unbalanced or wrong brackets"),
    # -- axes ------------------------------------------------------------------
    (19, "AXIS_TAG_TYPO", r"^Axis tag '.*' looks like a typo", "A misspelt registered axis tag"),
    (20, "AXIS_RANGE_INVALID", r"^Invalid axis range for", "A range that does not parse or is not ordered"),
    (21, "AXIS_RANGE_LABEL", r"Label '.*' not found in standard .* mappings|Label-based ranges only supported", "A range label that is not standard"),
    (22, "MAPPING_LABEL_TYPO", r"mapping label '.*' looks like a typo", "A label close to a standard one"),
    (23, "MAPPING_OUT_OF_RANGE", r"^Axis '.*': mapping '.*' has user_value .* outside the axis range", "A mapping outside the axis range"),
    (24, "MAPPING_EXTREME_MISSING", r"missing mapping for (minimum|maximum) value", "No mapping at an end of the axis"),
    (25, "NO_ELIDABLE", r"has no @elidable mapping", "An axis without an @elidable label"),
    (26, "MAPPING_INCOMPLETE", r"has incomplete mapping", "A mapping without values"),
    (27, "MAPPING_NONSTANDARD_USER", r"typically maps to user_value|typically uses|standard labels are at other user values|user values have other labels than usual", "A standard label at another user value"),
    (28, "MAPPING_USER_TWICE", r"is mapped twice", "One user value mapped twice"),
    (29, "BARE_LABEL_CONTINUOUS", r"^Simplified label format only supported", "A bare label on a continuous axis"),
    (30, "HIDDEN_AXIS_INVALID", r"^Invalid hidden axis|^Non-numeric value in hidden axis", "A hidden axis line that does not parse"),
    # -- sources ---------------------------------------------------------------
    (31, "SOURCE_COORD_COUNT", r"^Source '.*' has \d+ coordinates, expected", "Too few or too many coordinates"),
    (32, "SOURCE_UNKNOWN_LABEL", r"Label '.*' not found in axis '.*' mappings|^Unknown label '.*' for axis", "A coordinate label the axis does not have"),
    (33, "SOURCE_UNKNOWN_AXIS", r"^Unknown axis '.*' in source|^Invalid named coordinate format", "A named coordinate for no axis"),
    (34, "SOURCE_COORD_INVALID", r"^Invalid coordinates? in source|^Invalid coordinate value|^Invalid value '.*' for axis|^Coordinate index", "A coordinate that does not parse"),
    (35, "SOURCE_OFF_MAPPING", r"does not sit on a mapped point", "A master between mapped points (legal)"),
    (36, "SOURCE_EXTREME_MISSING", r"^No source at (minimum|maximum) mapping", "No master at an end of the axis"),
    # -- rules -----------------------------------------------------------------
    (37, "RULE_SYNTAX", r"^Invalid rule syntax", "A rule that does not parse"),
    (38, "RULE_CONDITION", r"^Invalid condition value|^Rule references axis '.*' which is not defined", "A condition with an unknown axis or label"),
    # -- instances -------------------------------------------------------------
    (39, "INSTANCE_LINE_IGNORED", r"^Instance line ignored", "An explicit instance line"),
    # -- avar2 -----------------------------------------------------------------
    (40, "AVAR2_MATRIX_ROW_LENGTH", r"^avar2 matrix: expected \d+ values", "A matrix row with the wrong number of cells"),
    (41, "AVAR2_UNDEFINED_VAR", r"undefined variable", "A $variable not defined in `avar2 vars`"),
    (42, "AVAR2_UNKNOWN_AXIS", r"cannot use \$ for unknown axis|^Axis '.*' not found in document|^avar2 mapping names axis '.*', which is not defined", "An avar2 reference to no axis"),
    (43, "AVAR2_INVALID_VALUE", r"invalid numeric value|^Non-numeric variable value|requires numeric values", "An avar2 value that is not a number"),
    (44, "AVAR2_UNKNOWN_LABEL", r"^avar2: unknown label", "An avar2 input label the axis does not have"),
    (45, "AVAR2_INPUT_OUT_OF_RANGE", r"^avar2 input .* is outside the axis range", "An avar2 input outside the user range (a design value: error; else clamped)"),
    (46, "AVAR2_SYNTAX", r"^avar2( matrix| vars| input| output)?: |^Variable name must start", "An avar2 line that does not parse"),
    # -- 1.5.x ------------------------------------------------------------------
    (47, "SKIP_UNKNOWN_LABEL", r"^Skip rule '.*' contains label", "A skip entry word that is no axis label"),
    (48, "ELIDED_FALLBACK_EMPTY", r"^elidedfallback: no name given", "`elidedfallback` without a name"),
    # -- font data (fontdata.py; only with a provider) --------------------------
    (49, "SOURCE_UFO_MISSING", r"^Source UFO '.*' not found", "A source's UFO does not exist"),
    (50, "SOURCE_LAYER_MISSING", r"^Source '.*': layer '.*' not found in", "A source's layer is not in its UFO"),
    (51, "RULE_GLYPH_MISSING", r": glyph '.*' is not in the default master", "A rule glyph the default master lacks"),
    (52, "RULE_TARGET_MISSING", r": target glyph '.*' is not in the default master", "A rule target the default master lacks"),
    (53, "RULE_MATCHES_NOTHING", r"matches no glyph whose target exists", "A wildcard rule that substitutes nothing"),
    # -- avar2 checks (1.5.x) ---------------------------------------------------
    (54, "AVAR2_DEFAULT_INPUT", r"^avar2 mapping at the default location sets", "A row at the default location that moves an output"),
    (55, "AVAR2_OUTPUT_OUT_OF_RANGE", r"^avar2 output .* is outside the axis range", "An avar2 output outside the axis's design range"),
    (56, "AVAR2_DUPLICATE_INPUT", r"^avar2 mapping \[.*\] has the same input location", "Two avar2 rows at one input location"),
    (57, "AVAR2_OUTPUT_ONLY_VISIBLE", r"^Axis '.*' is visible but only avar2 outputs drive it", "A visible axis driven only by avar2"),
    (58, "AVAR2_HIDDEN_INPUT", r"^avar2 input uses hidden axis", "A hidden axis as an avar2 input"),
    (59, "RULES_MODE_UNKNOWN", r"^rules: unknown mode", "A rules header mode other than `last`"),
    # -- explicit instances (1.5.x) ---------------------------------------------
    (60, "INSTANCE_FIELD_INVALID", r"^Instance '.*': (expected 'key: value'|unknown key|key '.*' (given twice|has no value))",
     "A malformed, unknown, repeated or empty key in an instance block"),
    (61, "INSTANCE_LOCATION_INVALID", r"^Instance '.*': (location expects|unknown axis|unknown label|axis '.*' given twice)",
     "An instance location naming an unknown axis or label, or malformed"),
    (62, "INSTANCE_NO_LOCATION", r"^Instance '.*' has no location", "An instance block without a location"),
    (63, "INSTANCE_OFF_IGNORED", r"^Instance '.*' is ignored: instances off", "An instance block under `instances off`"),
    (64, "INSTANCE_DUPLICATE", r"^Instance '.*' has the family and style name of", "Two instance blocks with one family and style name"),
    (65, "INSTANCE_SHADOWS_AUTO", r"^Instance '.*' is at the location of '.*', which instances auto",
     "An instance block where `instances auto` puts an instance too"),
    (66, "INSTANCES_AUTO_TOO_MANY", r"^instances auto would generate [\d,]+ instances",
     "`instances auto` past its limit of 1000 instances"),
    # -- checks from the Sept 2026 research (1.5.x) -------------------------------
    (67, "MAP_NOT_MONOTONIC", r"^Axis '.*': design values fall as user values grow", "An axis map whose design values fall"),
    (68, "SOURCE_OUT_OF_RANGE", r"^Source '.*': .* is outside the axis's design range", "A master outside the axis's design range"),
    (69, "SOURCE_DUPLICATE_LOCATION", r"^Sources '.*' and '.*' are at the same location", "Two masters at one location"),
    (70, "RULE_CONDITION_EMPTY", r"condition on '.*' has minimum .* above maximum", "A rule condition with minimum above maximum"),
    (71, "SOURCE_UPM_MISMATCH", r"^Source '.*' has [\d.]+ units per em; the base source", "A master on another UPM than the base (font data)"),
    # -- variable fonts (1.6.x) --------------------------------------------------
    (72, "VARIABLE_FONT_INVALID", r"^Variable font '.*': (expected 'key: value'|unknown key|key '.*' (given twice|has no value)|axes expects|unknown axis|unknown label|axis '.*' given twice|discrete axis '.*' takes one value|'.*' is not a value or a range)",
     "A malformed key or axis in a variable font block"),
    (73, "VARIABLE_FONTS_MODE_UNKNOWN", r"^variable-fonts: unknown mode", "A variable-fonts header mode other than `auto`"),
    (74, "VARIABLE_FONT_LINE_IGNORED", r"^Variable font line ignored", "Text at column 0 in the variable-fonts section"),
    (75, "VARIABLE_FONT_DUPLICATE", r"^Variable font '.*' is named twice", "Two variable fonts with one name"),
    (76, "VARIABLE_FONT_NO_AXES", r"^Variable font '.*' has no axes", "A variable font block without axes"),
    (77, "VARIABLE_FONT_VALUE_INVALID", r"^Variable font '.*': .* (is not a value of the discrete axis|goes outside the axis range|range must be ordered)",
     "A variable font value off its axis"),
    (78, "VARIABLE_FONT_DISCRETE_UNLISTED", r"^Variable font '.*' does not list discrete axis", "A discrete axis a variable font leaves out"),
)

# Checked before the rest: messages that wrap another one ("Invalid condition
# value: Label 'X' not found …" is about a rule, not a source)
_FIRST = ("RULE_CONDITION", "AXIS_RANGE_LABEL", "INSTANCE_FIELD_INVALID", "INSTANCE_LOCATION_INVALID",
          "VARIABLE_FONT_INVALID")

CODES: Dict[str, Code] = {}
_PATTERNS = []
for number, name, pattern, description in _TABLE:
    code = Code(number, name, description)
    CODES[name] = code
    if pattern:
        _PATTERNS.append((re.compile(pattern), code))
_PATTERNS.sort(key=lambda entry: entry[1].name not in _FIRST)

UNCLASSIFIED = CODES["UNCLASSIFIED"]
BY_ID: Dict[str, Code] = {code.id: code for code in CODES.values()}


def classify(message: str) -> Code:
    """The code of a parser or validator message"""
    for pattern, code in _PATTERNS:
        if pattern.search(message):
            return code
    return UNCLASSIFIED


def code_id(message: str) -> str:
    return classify(message).id


def plain_message(message: str) -> str:
    """A message as an editor shows it: without the validator's "CRITICAL: "
    prefix, which the severity already says (classify() reads both forms)"""
    return message[len("CRITICAL: "):] if message.startswith("CRITICAL: ") else message


def lookup(code: str) -> Optional[Code]:
    """A code by id ("5.31") or name ("SOURCE_COORD_COUNT")"""
    return BY_ID.get(code) or CODES.get(code)
