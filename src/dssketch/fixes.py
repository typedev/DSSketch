"""Quick fixes for diagnostics

`fixes_for(sketch, diagnostic)` gives the fixes an editor can offer for one
`syntax.Diagnostic`: each a `Fix(title, edits)`, the edits made by the same
operations as `Sketch`'s editing API. They are suggestions: unlike an edit
operation, a fix is not re-parsed before it is offered (that would parse the
text once per message); applying it gives the text the title says.

Fixes exist for:
- a misspelt keyword, registered axis tag or standard label (the suggestion
  the message makes; a label rename rewrites its uses too);
- an unknown label in a source, rule condition, avar2 input or skip entry
  (the closest label of that axis, within two edits), and removing a bad
  skip entry;
- no base source (a source at the defaults), an auto-detected base, several
  base sources (keep one);
- a mapping outside the axis range (extend the range, or move the mapping);
- an axis without an @elidable label (mark the one at the default);
- a missing mapping at an end of the axis;
- a label used on two axes (remove the second use);
- `en` listed in `lang`;
- a rule condition on an unknown axis (the closest axis);
- with font data, a rule glyph or target the default master lacks (the
  closest glyph it has), and a pattern rule that swaps nothing (remove it).
- in an explicit instance block, a misspelt key, an unknown axis or label in
  the location (the closest one), and a block where `instances auto` puts an
  instance too (skip that one);
- avar2: an unknown axis (the close one the message names), a row at the
  default location that moves an output (set it to `$`, or remove the row),
  an output outside the axis range (the clamped value), a row that repeats
  an output at one location or reads a hidden axis (remove it);
- a master outside the axis's design range (the clamped value), two masters
  at one location (remove the later), a rule condition with minimum above
  maximum (swap them).

Never raises: a fix that cannot be built is left out. Light: stdlib + PyYAML.
"""

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .sketch import EditError, EditResult, Sketch, TextEdit

_QUOTED = re.compile(r"'([^']*)'")
_NUMBER = r"(-?\d+(?:\.\d+)?)"


@dataclass(frozen=True)
class Fix:
    """A quick fix: what it does, and the edits that do it (against the text
    the diagnostic was made for)"""

    title: str
    edits: Tuple[TextEdit, ...]


def fixes_for(sketch: Sketch, diagnostic) -> Tuple[Fix, ...]:
    """The fixes for one diagnostic of `sketch`'s text. Never raises"""
    from .codes import lookup

    code = lookup(diagnostic.code)
    handler = _HANDLERS.get(code.name) if code is not None else None
    if handler is None:
        return ()
    try:
        fixer = sketch._unverified()
        fixes = handler(fixer, diagnostic, _QUOTED.findall(diagnostic.message.split(". Available", 1)[0]))
    except Exception:
        return ()
    out = []
    for fix in fixes:
        if fix is not None and fix.edits:
            out.append(fix)
    return tuple(out)


def _fix(title: str, build: Callable[[], EditResult]) -> Optional[Fix]:
    try:
        result = build()
    except (EditError, KeyError, IndexError, ValueError):
        return None
    return Fix(title, tuple(result.edits))


def _replace_word(sketch: Sketch, line_no: Optional[int], old: str, new: str) -> Tuple[TextEdit, ...]:
    """Replace the tokens of a line whose text is `old` (outside comments)"""
    from .syntax import COMMENT

    line = sketch.structure.line(line_no) if line_no else None
    if line is None:
        return ()
    return tuple(
        TextEdit(line_no, t.column, line_no, t.column + t.length, new)
        for t in line.tokens
        if t.type != COMMENT and t.text == old
    )


def _closest(word: str, candidates, limit: int = 2) -> Optional[str]:
    from .utils.dss_validator import DSSValidator

    best, best_distance = None, limit + 1
    for candidate in sorted(candidates):
        distance = DSSValidator.levenshtein_distance(word.lower(), candidate.lower())
        if distance < best_distance:
            best, best_distance = candidate, distance
    return best


def _numbers(message: str) -> List[float]:
    return [float(n) for n in re.findall(_NUMBER, message)]


def _mapping_on_line(sketch: Sketch, line_no: Optional[int]):
    for axis in sketch._all_axes():
        for mapping in axis.mappings:
            if line_no is not None and mapping.line == line_no:
                return axis, mapping
    return None, None


def _key(mapping):
    return mapping.label if mapping.label else mapping.user_value


# -- handlers -----------------------------------------------------------------


def _keyword_typo(sk: Sketch, d, quoted):
    word, suggestion = quoted[0], quoted[1]
    edits = _replace_word(sk, d.line, word, suggestion)[:1]
    return [Fix(f"Change to '{suggestion}'", edits)]


def _axis_tag_typo(sk: Sketch, d, quoted):
    tag, suggestion = quoted[0], quoted[1]
    axis = next((a for a in sk._all_axes() if a.line == d.line), None)
    if axis is not None:
        return [_fix(f"Change to '{suggestion}'", lambda: sk.set_axis_tag(axis.tag, suggestion))]
    return [Fix(f"Change to '{suggestion}'", _replace_word(sk, d.line, tag, suggestion)[:1])]


def _label_typo(sk: Sketch, d, quoted):
    label, suggestion = quoted[-2], quoted[-1]
    axis, mapping = _mapping_on_line(sk, d.line)
    if mapping is None or mapping.label != label:
        return []
    return [_fix(f"Rename '{label}' to '{suggestion}'", lambda: sk.rename_label(axis.tag, label, suggestion))]


def _unknown_label(sk: Sketch, d, quoted):
    """"Label 'Bolt' not found in axis 'weight' …", "unknown label 'Bolt' for axis 'weight'" """
    message = d.message
    # "Rule references axis 'wdth' …" (a number) or, with a label, the parser's
    # "Invalid condition value: Axis 'wdth' not found in document"
    axis_match = re.search(r"(?:^Rule references axis|Invalid condition value: Axis) '([^']*)'", message)
    if axis_match:
        word = axis_match.group(1)
        names = {a.tag for a in sk._all_axes()} | {a.name for a in sk._all_axes()}
        suggestion = _closest(word, names)
        if suggestion is None:
            return []
        return [Fix(f"Change to '{suggestion}'", _replace_word(sk, d.line, word, suggestion))]
    match = re.search(r"[Ll]abel '([^']*)' (?:not found in axis|for axis) '([^']*)'", message)
    if not match:
        return []
    word, axis_ref = match.groups()
    try:
        axis = sk.axis(axis_ref)
    except EditError:
        return []
    labels = {m.label for m in axis.mappings if m.label}
    suggestion = _closest(word, labels)
    if suggestion is None:
        return []
    return [Fix(f"Change to '{suggestion}'", _replace_word(sk, d.line, word, suggestion))]


def _skip_unknown_label(sk: Sketch, d, quoted):
    entry, word = quoted[0], quoted[1]
    labels = {m.label for a in sk.document.axes for m in a.mappings if m.label}
    fixes = []
    suggestion = _closest(word, labels)
    if suggestion is not None:
        fixes.append(Fix(f"Change to '{suggestion}'", _replace_word(sk, d.line, word, suggestion)))
    fixes.append(_fix(f"Remove skip entry '{entry}'", lambda: sk.remove_skip(entry)))
    return fixes


def _at_defaults(sk: Sketch, source) -> bool:
    for axis in sk.document.axes:
        if axis.is_discrete:
            continue
        if source.location.get(axis.name) != axis.design_default:
            return False
    return True


def _no_base(sk: Sketch, d, quoted):
    return [
        _fix(f"Make '{s.name}' the base source", lambda s=s: sk.set_base(Sketch.source_key(s)))
        for s in sk.document.sources
        if _at_defaults(sk, s)
    ][:5]


def _base_auto_detected(sk: Sketch, d, quoted):
    for source in sk.document.sources:
        if source.name == quoted[0]:
            return [_fix(f"Mark '{source.name}' with @base", lambda: sk.set_base(Sketch.source_key(source)))]
    return []


def _multiple_base(sk: Sketch, d, quoted):
    bases = [s for s in sk.document.sources if s.is_base]
    fixes = []
    for keep in bases:
        edits = []
        for other in bases:
            line = sk._line_of(other)
            if other is not keep and line is not None and "flag.base" in line.fields:
                edits.append(sk._remove_field(line, "flag.base"))
        fixes.append(Fix(f"Keep @base only on '{keep.name}'", tuple(edits)))
    return fixes


def _mapping_out_of_range(sk: Sketch, d, quoted):
    axis, mapping = _mapping_on_line(sk, d.line)
    if mapping is None:
        return []
    value = mapping.user_value
    below = value < axis.minimum
    bound = axis.minimum if below else axis.maximum
    extend = {"minimum": value} if below else {"maximum": value}
    return [
        _fix(f"Extend the axis {'minimum' if below else 'maximum'} to {value:g}",
             lambda: sk.set_axis_range(axis.tag, **extend)),
        _fix(f"Move the mapping to user value {bound:g}",
             lambda: sk.set_mapping_user(axis.tag, _key(mapping), bound)),
    ]


def _no_elidable(sk: Sketch, d, quoted):
    try:
        axis = sk.axis(quoted[0])
    except EditError:
        return []
    for mapping in axis.mappings:
        if mapping.label and mapping.user_value == axis.default:
            return [_fix(f"Mark '{mapping.label}' @elidable",
                         lambda: sk.set_mapping_elidable(axis.tag, mapping.label, True))]
    return []


def _extreme_missing(sk: Sketch, d, quoted):
    from .core.mappings import Standards

    try:
        axis = sk.axis(quoted[0])
    except EditError:
        return []
    match = re.search(r"\((minimum|maximum)=" + _NUMBER + r"\)", d.message)
    if not match:
        return []
    value = float(match.group(2))
    design = axis.get_design_value(value)
    fixes = []
    used = {m.label for a in sk._all_axes() for m in a.mappings}
    label = quoted[-1] if len(quoted) > 1 else ""
    if label and label not in used and Standards.has_mapping(label, axis.name):
        fixes.append(_fix(f"Add '{label}' at {value:g}", lambda: sk.add_mapping(axis.tag, label, design, user=value)))
    fixes.append(_fix(f"Add an unnamed map point at {value:g}", lambda: sk.add_mapping(axis.tag, "", design, user=value)))
    return fixes


def _duplicate_label(sk: Sketch, d, quoted):
    axis, mapping = _mapping_on_line(sk, d.line)
    if mapping is None or mapping.label != quoted[0]:
        return []
    return [_fix(f"Remove '{mapping.label}' from axis '{axis.tag}'", lambda: sk.remove_mapping(axis.tag, mapping.label))]


def _lang_en(sk: Sketch, d, quoted):
    codes = [c for c in sk.document.languages if c != "en"]
    return [_fix("Remove 'en'", lambda: sk.set_lang(codes or None))]


def _rule_index(sk: Sketch, line_no: Optional[int]) -> Optional[int]:
    return next((i for i, r in enumerate(sk.document.rules) if line_no is not None and r.line == line_no), None)


def _rule_glyph_missing(sk: Sketch, d, quoted):
    """A glyph the default master lacks: the closest one it has (font data)"""
    from .fontdata import default_master_glyphs

    if sk.font_data is None or not quoted:
        return []
    glyphs = default_master_glyphs(sk.font_data, sk.document)
    if not glyphs:
        return []
    word = quoted[0]
    suggestion = _closest(word, glyphs)
    if suggestion is None or suggestion == word:
        return []
    return [Fix(f"Change to '{suggestion}'", _replace_word(sk, d.line, word, suggestion)[:1])]


def _rule_matches_nothing(sk: Sketch, d, quoted):
    index = _rule_index(sk, d.line)
    if index is None:
        return []
    return [_fix("Remove the rule", lambda: sk.remove_rule(index))]


def _instance_field(sk: Sketch, d, quoted):
    # Instance 'X': unknown key 'famly'. Did you mean 'family'?
    if "unknown key" not in d.message or len(quoted) < 3:
        return []
    return [Fix(f"Change to '{quoted[2]}'", _replace_word(sk, d.line, quoted[1], quoted[2])[:1])]


def _instance_location(sk: Sketch, d, quoted):
    doc = sk.document
    if "unknown label" in d.message and len(quoted) >= 3:
        try:
            axis = sk.axis(quoted[2])
        except EditError:
            return []
        suggestion = _closest(quoted[1], {m.label for m in axis.mappings if m.label})
    elif "unknown axis" in d.message and len(quoted) >= 2:
        suggestion = _closest(quoted[1], {a.tag for a in doc.axes + doc.hidden_axes})
    else:
        return []
    if suggestion is None:
        return []
    return [Fix(f"Change to '{suggestion}'", _replace_word(sk, d.line, quoted[1], suggestion)[:1])]


def _instance_shadows_auto(sk: Sketch, d, quoted):
    # Instance 'X' is at the location of 'Y', which instances auto generates too
    return [_fix(f"Add '{quoted[1]}' to skip", lambda: sk.add_skip(quoted[1]))] if len(quoted) >= 2 else []


def _avar2_index(sk: Sketch, line_no: Optional[int]) -> Optional[int]:
    return next((i for i, m in enumerate(sk.document.avar2_mappings) if line_no is not None and m.line == line_no), None)


def _avar2_unknown_axis(sk: Sketch, d, quoted):
    # avar2 mapping names axis 'XOCU', which is not defined. Did you mean 'XOUC'?
    if not quoted:
        return []
    doc = sk.document
    suggestion = quoted[1] if len(quoted) > 1 else _closest(quoted[0], {a.tag for a in doc.axes + doc.hidden_axes})
    index = _avar2_index(sk, d.line)
    if suggestion is None or index is None:
        return []
    mapping = doc.avar2_mappings[index]
    for number in range(mapping.line, (sk.structure.line(mapping.line).end_line or mapping.line) + 1):
        edits = _replace_word(sk, number, quoted[0], suggestion)
        if edits:
            return [Fix(f"Change to '{suggestion}'", edits)]
    return []


def _avar2_default_input(sk: Sketch, d, quoted):
    index = _avar2_index(sk, d.line)
    if index is None or not quoted:
        return []
    return [
        _fix(f"Set {quoted[0]} to its default ($)", lambda: sk.set_avar2_output(index, quoted[0], "$")),
        _fix("Remove the row", lambda: sk.remove_avar2_mapping(index)),
    ]


_OUT_OF_RANGE = re.compile(r"^avar2 output (\S+)=\S+ is outside the axis range .* clamps it to (\S+)\.")


def _avar2_output_out_of_range(sk: Sketch, d, quoted):
    index = _avar2_index(sk, d.line)
    match = _OUT_OF_RANGE.match(d.message)
    if index is None or match is None:
        return []
    axis, value = match.group(1), float(match.group(2))
    return [_fix(f"Set {axis} to {value:g}", lambda: sk.set_avar2_output(index, axis, value))]


def _avar2_remove_row(sk: Sketch, d, quoted):
    index = _avar2_index(sk, d.line)
    return [_fix("Remove the row", lambda: sk.remove_avar2_mapping(index))] if index is not None else []


_OUTSIDE = re.compile(r"^Source '(.*)': (\S+) \S+ is outside the axis's design range .* clamps it to (\S+)\.")


def _source_out_of_range(sk: Sketch, d, quoted):
    match = _OUTSIDE.match(d.message)
    if match is None:
        return []
    name, tag, value = match.group(1), match.group(2), float(match.group(3))
    source = next((s for s in sk.document.sources if s.line == d.line), None)
    if source is None:
        return []
    key = Sketch.source_key(source)
    return [_fix(f"Set {tag} to {value:g}", lambda: sk.set_source_coordinate(key, tag, value, prefer="number"))]


def _source_duplicate_location(sk: Sketch, d, quoted):
    source = next((s for s in sk.document.sources if s.line == d.line), None)
    if source is None:
        return []
    key = Sketch.source_key(source)
    return [_fix(f"Remove source '{source.name}'", lambda: sk.remove_source(key))]


def _rule_condition_empty(sk: Sketch, d, quoted):
    index = _rule_index(sk, d.line)
    if index is None:
        return []
    rule = sk.document.rules[index]
    for position, condition in enumerate(rule.conditions or ()):
        low, high = condition.get("minimum"), condition.get("maximum")
        if low is not None and high is not None and low > high:
            text = f"{high:g} <= {condition.get('axis')} <= {low:g}"
            return [_fix("Swap minimum and maximum", lambda p=position, t=text: sk.set_rule_condition(index, p, t))]
    return []


_HANDLERS: Dict[str, Callable] = {
    "KEYWORD_TYPO": _keyword_typo,
    "AXIS_TAG_TYPO": _axis_tag_typo,
    "MAPPING_LABEL_TYPO": _label_typo,
    "SOURCE_UNKNOWN_LABEL": _unknown_label,
    "RULE_CONDITION": _unknown_label,
    "AVAR2_UNKNOWN_LABEL": _unknown_label,
    "SKIP_UNKNOWN_LABEL": _skip_unknown_label,
    "NO_BASE": _no_base,
    "BASE_AUTO_DETECTED": _base_auto_detected,
    "MULTIPLE_BASE": _multiple_base,
    "MAPPING_OUT_OF_RANGE": _mapping_out_of_range,
    "NO_ELIDABLE": _no_elidable,
    "MAPPING_EXTREME_MISSING": _extreme_missing,
    "DUPLICATE_LABEL": _duplicate_label,
    "LANG_EN": _lang_en,
    "RULE_GLYPH_MISSING": _rule_glyph_missing,
    "RULE_TARGET_MISSING": _rule_glyph_missing,
    "RULE_MATCHES_NOTHING": _rule_matches_nothing,
    "INSTANCE_FIELD_INVALID": _instance_field,
    "INSTANCE_LOCATION_INVALID": _instance_location,
    "INSTANCE_SHADOWS_AUTO": _instance_shadows_auto,
    "AVAR2_UNKNOWN_AXIS": _avar2_unknown_axis,
    "AVAR2_DEFAULT_INPUT": _avar2_default_input,
    "AVAR2_OUTPUT_OUT_OF_RANGE": _avar2_output_out_of_range,
    "AVAR2_DUPLICATE_INPUT": _avar2_remove_row,
    "AVAR2_HIDDEN_INPUT": _avar2_remove_row,
    "SOURCE_OUT_OF_RANGE": _source_out_of_range,
    "SOURCE_DUPLICATE_LOCATION": _source_duplicate_location,
    "RULE_CONDITION_EMPTY": _rule_condition_empty,
}
