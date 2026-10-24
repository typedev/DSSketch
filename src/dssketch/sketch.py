"""Editing a .dssketch text: an immutable snapshot with minimal-edit operations

The text is the source of truth. `Sketch.parse(text)` reads it once (the
parser, in recover mode, and the line structure, `structure.py`); every
operation returns an `EditResult`: the minimal `TextEdit`s, the new text, and
the new `Sketch`. Nothing is regenerated, so comments, blank lines,
indentation and the spelling of untouched values survive, and an unchanged
sketch gives back its text byte for byte.

    sk = Sketch.parse(text)
    result = sk.set_source_coordinate("Font-Bold.ufo", "wght", 700)
    buffer.apply(result.edits)          # or: text = result.text
    sk = result.sketch

Objects are addressed by stable keys, never by line number:

- an axis by its tag (`"wght"`), hidden axes too;
- a mapping by its axis tag and label (`"wght", "Bold"`), an unnamed map
  point by its user value (`"wght", 100`);
- a source by `SourceKey(filename, layer)`, or by a string when that names one
  source (file name with or without `.ufo`, or the name as written);
- a skip entry by its text.

An operation is all or nothing. A request that cannot be carried out (an
unknown key, a value the parser rejects, a second `@base`) raises `EditError`
and changes nothing: after building the edits, the new text is parsed and any
error it has that the old text had not refuses the operation. An operation
whose target line already has an error is refused too. Everything else never
raises on bad text: `item_at`, `span`, `diagnostics` and the queries work on
any text, errors elsewhere included.

Light: stdlib and PyYAML only, no fontTools or defcon
(`tests/test_light_imports.py`).
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from . import structure as st
from .core.mappings import Standards
from .core.models import DSSAxis, DSSAxisMapping, DSSDocument, DSSSource
from .structure import Span

Number = Union[int, float]
Value = Union[int, float, str]

PREFER_VALUES = ("keep", "label", "number")


# =============================================================================
# Results
# =============================================================================


@dataclass(frozen=True)
class TextEdit:
    """Replace `line:col`..`end_line:end_col` with `new_text`

    Lines from 1, columns from 0 (as `syntax.Token`), the end exclusive. An
    insertion has start == end.
    """

    line: int
    col: int
    end_line: int
    end_col: int
    new_text: str


@dataclass
class EditResult:
    """What an operation did: edits (non-overlapping, in document order)
    against the old text, and the text after them"""

    edits: List[TextEdit]
    text: str
    _sketch: Optional["Sketch"] = field(default=None, repr=False)
    _font_data: Any = field(default=None, repr=False)

    @property
    def sketch(self) -> "Sketch":
        """The new text, parsed (shares the parse the operation verified)"""
        if self._sketch is None:
            self._sketch = Sketch.parse(self.text, font_data=self._font_data)
        return self._sketch


class EditError(ValueError):
    """An operation refused, with nothing changed

    `code` says why, stable for callers to switch on:

    - `unknown-key`: no axis / mapping / source / skip entry with that key
    - `ambiguous-key`: a string names more than one source
    - `duplicate`: the new object (label, tag, skip entry …) exists already
    - `invalid-value`: a value that cannot be written (not a number or label)
    - `target-has-errors`: the target line does not parse
    - `in-use`: removing it would leave references to it (rules, avar2, skip)
    - `not-applicable`: the operation does not apply here (a range on a
      discrete axis …)
    - `rejected`: the parser rejects the result; `messages` holds its errors
    """

    def __init__(self, code: str, message: str, messages: Sequence[str] = ()):
        super().__init__(message)
        self.code = code
        self.message = message
        self.messages = list(messages)


@dataclass(frozen=True)
class SourceKey:
    """A source: its file name (as `DSSSource.filename`) and UFO layer"""

    filename: str
    layer: Optional[str] = None


# =============================================================================
# Text helpers
# =============================================================================


def apply_edits(text: str, edits: Iterable[TextEdit]) -> str:
    """The text after `edits` (non-overlapping; any order)"""
    lines = text.split("\n")
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)

    def offset(line: int, col: int) -> int:
        line = max(1, min(line, len(lines)))
        return starts[line - 1] + min(col, len(lines[line - 1]))

    out = text
    for edit in sorted(edits, key=lambda e: (e.line, e.col, e.end_line, e.end_col), reverse=True):
        start, end = offset(edit.line, edit.col), offset(edit.end_line, edit.end_col)
        out = out[:start] + edit.new_text + out[end:]
    return out


def format_number(value: Number) -> str:
    """400.0 -> "400", 0.5 -> "0.5" (as the writer formats numbers)"""
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return repr(value)


def _quote_if_needed(value: str) -> str:
    """A name in quotes when it would not survive unquoted"""
    if not value or value != value.strip() or any(c in value for c in ' #"\t[]=,') or value[0] in "'@$":
        return '"' + value + '"'
    return value


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


# =============================================================================
# Parsing
# =============================================================================


def _parse(text: str):
    """The parser after reading `text` in recover mode, and what crashed it"""
    from .parsers.dss_parser import DSSParser
    from .utils.dss_validator import DSSValidationError

    parser = DSSParser(strict_mode=False, recover=True)
    crash = None
    try:
        parser.parse(text)
    except Exception as e:  # critical errors are already in validator.errors
        if not isinstance(e.__cause__, DSSValidationError):
            crash = e
    return parser, crash


_QUOTED = None


def _error_key(message: str):
    """What identifies an error across an edit: its code and the names it
    quotes, not its wording (which lists context such as the labels an axis
    has, and that changes when a label is added)"""
    global _QUOTED
    import re

    from .codes import UNCLASSIFIED, classify

    if _QUOTED is None:
        _QUOTED = re.compile(r"'([^']*)'")
    code = classify(message)
    if code is UNCLASSIFIED:
        return message
    head = message.split(". Available", 1)[0]
    return (code.number, tuple(_QUOTED.findall(head)))


def _errors(parser, crash) -> Counter:
    messages = list(parser.validator.errors)
    if crash is not None:
        messages.append(str(crash))
    return Counter(_error_key(m) for m in messages)


def _new_errors(old, new) -> List[str]:
    """The messages of `new` (parser, crash) whose errors `old` did not have"""
    from .codes import plain_message

    added = _errors(*new) - _errors(*old)
    out = []
    messages = list(new[0].validator.errors) + ([str(new[1])] if new[1] is not None else [])
    for message in messages:
        key = _error_key(message)
        if added.get(key, 0) > 0:
            added[key] -= 1
            out.append(plain_message(message))
    return out


# =============================================================================
# The snapshot
# =============================================================================


class Sketch:
    """An immutable, parsed .dssketch text with editing operations"""

    def __init__(self, text: str, _parsed=None, font_data=None):
        self._text = text
        self.font_data = font_data  # fontdata.FontDataProvider, or None
        self._parsed = _parsed  # (parser, crash) when the caller already parsed it
        self._structure: Optional[st.Structure] = None
        self._diagnostics = None
        self._spans_done = False
        self._verify = True  # False: a fixer clone, see _unverified()

    @classmethod
    def parse(cls, text: str, font_data=None) -> "Sketch":
        """Read a text. Never raises: errors are in `diagnostics`

        font_data: a fontdata.FontDataProvider; with it the diagnostics also
        check what the fonts say (missing UFO or layer, rule glyphs)
        """
        return cls(text, font_data=font_data)

    # -- what it holds ----------------------------------------------------------

    @property
    def text(self) -> str:
        """The text, exactly as given"""
        return self._text

    @property
    def structure(self) -> st.Structure:
        if self._structure is None:
            self._structure = st.build(self._text)
        return self._structure

    @property
    def _parser(self):
        if self._parsed is None:
            self._parsed = _parse(self._text)
        return self._parsed[0]

    @property
    def document(self) -> DSSDocument:
        """The parsed document (recovered: what parsed, errors aside)

        Its axes, mappings, sources, rules and avar2 mappings carry `span`
        (the code of their line) and `spans` (their fields; see `span()`).
        """
        doc = self._parser.document
        if not self._spans_done:
            self._spans_done = True
            try:
                self._attach_spans(doc)
            except Exception:  # positions are a convenience; never break a read
                pass
        return doc

    @property
    def diagnostics(self):
        """`syntax.Diagnostic`s for the text, as `syntax.diagnose()` gives them"""
        if self._diagnostics is None:
            from .syntax import _diagnostics_for

            self._diagnostics = _diagnostics_for(
                self._text, self._parser, self._parsed[1], self.structure, self
            )
        return self._diagnostics

    def _unverified(self) -> "Sketch":
        """This sketch, sharing its parse, whose operations skip the re-parse
        (quick fixes are suggestions; fixes.py)"""
        self.document  # spans attached once, on the shared models
        clone = Sketch(self._text, _parsed=self._parsed, font_data=self.font_data)
        clone._structure = self.structure
        clone._spans_done = True
        clone._verify = False
        return clone

    # -- keys -------------------------------------------------------------------

    def _all_axes(self) -> List[DSSAxis]:
        doc = self.document
        return list(doc.axes) + list(doc.hidden_axes)

    def axis(self, tag: str) -> DSSAxis:
        """The axis (or hidden axis) with this tag; EditError if none"""
        for axis in self._all_axes():
            if axis.tag == tag:
                return axis
        lowered = tag.lower()
        for axis in self._all_axes():
            if axis.name.lower() == lowered or (axis.display_name or "").lower() == lowered:
                return axis
        raise EditError("unknown-key", f"No axis '{tag}'")

    def _is_hidden(self, axis: DSSAxis) -> bool:
        return any(a is axis for a in self.document.hidden_axes)

    def mapping(self, tag: str, key: Value) -> DSSAxisMapping:
        """The mapping of axis `tag` with label `key` (a number: the user value
        of an unnamed map point); EditError if none"""
        axis = self.axis(tag)
        for mapping in axis.mappings:
            if isinstance(key, str) and mapping.label == key:
                return mapping
        if not isinstance(key, str) or _is_number(key):
            value = float(key)
            for mapping in axis.mappings:
                if not mapping.label and mapping.user_value == value:
                    return mapping
        raise EditError("unknown-key", f"Axis '{axis.tag}' has no mapping '{key}'")

    def source(self, key: Union[SourceKey, str]) -> DSSSource:
        """The source a key names; EditError if none or (a string) several"""
        sources = self.document.sources
        if isinstance(key, SourceKey):
            found = [s for s in sources if s.filename == key.filename and s.layer == key.layer]
        else:
            candidates = {key, key + ".ufo"}
            found = [s for s in sources if s.filename in candidates]
            if not found:
                found = [s for s in sources if s.name == key or self._written_name(s) == key]
        if not found:
            raise EditError("unknown-key", f"No source '{key}'")
        if len(found) > 1:
            raise EditError(
                "ambiguous-key",
                f"'{key}' names {len(found)} sources; use SourceKey(filename, layer)",
            )
        return found[0]

    @staticmethod
    def source_key(source: DSSSource) -> SourceKey:
        return SourceKey(source.filename, source.layer)

    def _written_name(self, source: DSSSource) -> Optional[str]:
        line = self._line_of(source)
        return line.values.get("name") if line is not None else None

    def _line_of(self, obj) -> Optional[st.Line]:
        number = getattr(obj, "line", None)
        return self.structure.line(number) if number else None

    def _axis_ref_tag(self, ref: str) -> Optional[str]:
        """The tag of the axis a written reference means (tag, name, display
        name or registered human name, any case)"""
        from .syntax import _AXIS_ALIASES

        lowered = ref.lower()
        for axis in self._all_axes():
            if ref == axis.tag:
                return axis.tag
        for axis in self._all_axes():
            names = {axis.tag.lower(), axis.name.lower(), (axis.display_name or "").lower()}
            if lowered in names:
                return axis.tag
        for tag, human in _AXIS_ALIASES.items():
            if lowered in (tag, human):
                for axis in self._all_axes():
                    if axis.tag == tag:
                        return tag
        return None

    def _source_order(self) -> List[str]:
        """Tags in the order positional coordinates are written"""
        header = self.structure.section_header("sources")
        if header is not None and "order" in header.fields:
            tags = []
            i = 0
            while f"order.{i}" in header.values:
                tags.append(self._axis_ref_tag(header.values[f"order.{i}"]) or header.values[f"order.{i}"])
                i += 1
            return tags
        # Without an order the parser reads the visible axes in their order
        return [a.tag for a in self.document.axes]

    # -- positions --------------------------------------------------------------

    def _attach_spans(self, doc: DSSDocument) -> None:
        order = None
        for axis in self._all_axes():
            line = self._line_of(axis)
            if line is None:
                continue
            axis.span = line.span
            axis.spans = dict(line.fields)
            for mapping in axis.mappings:
                mline = self._line_of(mapping)
                if mline is None:
                    continue
                mapping.span = mline.span
                mapping.spans = {
                    ("elidable" if k == "flag.elidable" else k): v for k, v in mline.fields.items()
                }
        for source in doc.sources:
            line = self._line_of(source)
            if line is None:
                continue
            if order is None:
                order = self._source_order()
            source.span = line.span
            spans = {}
            for name, span in line.fields.items():
                if name.startswith("coord."):
                    ref = name[6:]
                    if ref.isdigit():
                        position = int(ref)
                        tag = order[position] if position < len(order) else ref
                    else:
                        tag = self._axis_ref_tag(ref) or ref
                    spans[f"coord.{tag}"] = span
                elif name.startswith("flag."):
                    spans[name[5:] if name != "flag.layer" else "layer"] = span
                elif name == "layer":
                    spans["layer_name"] = span
                else:
                    spans[name] = span
            source.spans = spans
        for rule in doc.rules:
            line = self._line_of(rule)
            if line is not None:
                rule.span = line.span
                rule.spans = dict(line.fields)
        for mapping in doc.avar2_mappings:
            line = self._line_of(mapping)
            if line is None:
                continue
            end = self.structure.line(line.end_line)
            if line.span is not None and end is not None and end.span is not None:
                mapping.span = Span(line.span.line, line.span.col, end.span.end_line, end.span.end_col)
            else:
                mapping.span = line.span
            spans = {}
            for number in range(line.number, line.end_line + 1):
                for name, span in self.structure.line(number).fields.items():
                    head, _, ref = name.partition(".")
                    if head in ("input", "output") and ref:
                        spans[f"{head}.{self._axis_ref_tag(ref) or ref}"] = span
                    elif number == line.number:
                        spans[name] = span
            mapping.spans = spans

    def span(self, path: Sequence[Any]) -> Optional[Span]:
        """The span of an item path (as `item_at` returns), None if absent"""
        try:
            return self._span(tuple(path))
        except Exception:
            return None

    def _span(self, path: tuple) -> Optional[Span]:
        kind = path[0]
        field_name = path[-1] if len(path) > 1 else None
        doc = self.document
        if kind in ("family", "suffix", "elidedfallback", "path", "lang"):
            line = next(iter(self.structure.of_kind(kind)), None)
            if line is None:
                return None
            return line.fields.get(path[1]) if len(path) > 1 else line.span
        if kind == "axis":
            axis = self.axis(path[1])
            return axis.spans.get(path[2]) if len(path) > 2 else axis.span
        if kind == "mapping":
            mapping = self.mapping(path[1], path[2])
            return mapping.spans.get(path[3]) if len(path) > 3 else mapping.span
        if kind == "source":
            source = self.source(path[1])
            if len(path) > 3 and path[2] == "coord":
                return source.spans.get(f"coord.{path[3]}")
            return source.spans.get(path[2]) if len(path) > 2 else source.span
        if kind == "rule":
            rule = doc.rules[path[1]]
            return rule.spans.get(path[2]) if len(path) > 2 else rule.span
        if kind == "avar2":
            mapping = doc.avar2_mappings[path[1]]
            if len(path) > 3:
                return mapping.spans.get(f"{path[2]}.{path[3]}")
            return mapping.spans.get(path[2]) if len(path) > 2 else mapping.span
        if kind == "avar2_var":
            line = self._var_line(path[1])
            if line is None:
                return None
            return line.fields.get(path[2]) if len(path) > 2 else line.span
        if kind == "instances":
            header = self.structure.section_header("instances")
            if header is None:
                return None
            return header.fields.get("mode") if field_name == "mode" else header.span
        if kind == "skip":
            line = self._skip_line(path[1])
            return line.span if line is not None else None
        if kind == "section":
            header = self.structure.section_header(path[1])
            return header.span if header is not None else None
        return None

    def _var_line(self, name: str) -> Optional[st.Line]:
        wanted = name if name.startswith("$") else "$" + name
        for line in self.structure.of_kind(st.AVAR2_VAR):
            if line.values.get("name") == wanted:
                return line
        return None

    def _skip_line(self, entry: str) -> Optional[st.Line]:
        wanted = " ".join(entry.split())
        for line in self.structure.of_kind(st.SKIP_ENTRY):
            if " ".join(line.values.get("value", "").split()) == wanted:
                return line
        return None

    # -- what it means, in numbers (queries.py, 1.5.1) ----------------------------
    # Never raise; axes are keyed by their DesignSpace name (display name, else
    # name) and accepted by that name, the tag or the sketch's own name

    def user_to_design(self, axis: str, value) -> Optional[float]:
        """A user value or label on an axis, in design space (None: unknown)"""
        from . import queries

        return queries._user_to_design(self.document, axis, value)

    def design_to_user(self, axis: str, value) -> Optional[float]:
        """A design value or label on an axis, in user space (None: unknown)"""
        from . import queries

        return queries._design_to_user(self.document, axis, value)

    def source_locations(self) -> list:
        """queries.SourceLocation per source: SourceKey, name, user and
        design location on every axis (an unwritten one at its default)"""
        from . import queries

        return queries._source_locations(self.document)

    def rule_regions(self) -> list:
        """queries.RuleRegion per rule: design-space (min, max) per axis it names"""
        from . import queries

        return queries._rule_regions(self.document)

    def substitutions_at(self, location, glyph_names=None, space: str = "design") -> Dict[str, str]:
        """{glyph: replacement} the rules make at `location` (axis -> value;
        a missing axis at its default; `space="user"` for user values).
        Pattern rules expand against `glyph_names`, or the default master's
        glyphs from the font data when not given"""
        from . import queries

        if glyph_names is None and self.font_data is not None:
            from .fontdata import default_master_glyphs

            try:
                glyph_names = default_master_glyphs(self.font_data, self.document)
            except Exception:
                glyph_names = None
        return queries._substitutions_at(self.document, location, glyph_names, space)

    def instances(self) -> list:
        """queries.InstanceInfo per instance `instances auto` generates (the
        DesignSpace's order and locations) and per one a `skip` entry removes"""
        from . import queries

        if getattr(self, "_instances", None) is None:
            family = None
            if not self.document.family and self.font_data is not None:
                from .fontdata import _call

                family = _call(self.font_data, "family_name")
            self._instances = queries._instances(self.document, self.structure, family)
        return list(self._instances)

    def hover(self, line: int, col: int) -> Optional[str]:
        """A line of explanation for the word under the cursor (1-based line,
        0-based column), or None: a label's user and design value, an axis's
        ranges, a number in the other space, a source's location, what a skip
        entry removes, where a rule applies and — with font data — which glyphs
        a pattern swaps. Never raises"""
        from . import queries

        try:
            return queries._hover(self, line, col)
        except Exception:
            return None

    def item_at(self, line: int, col: int) -> Optional[tuple]:
        """The object and field under a cursor, as a path; None outside any

        Paths:
          ("family" | "suffix" | "elidedfallback" | "path" | "lang", field?)
          ("section", name)
          ("axis", tag, field?)                 field: name tag min default max
                                                 range discrete display_name
          ("mapping", tag, label, field?)       field: user label design elidable
                                                 (an unnamed point: its user value)
          ("source", SourceKey, field?)         field: name base sparse layer
          ("source", SourceKey, "coord", tag)
          ("rule", index, field?)               field: pattern target conditions
                                                 condition.N name
          ("instances", "mode"?)
          ("skip", entry)
          ("avar2_var", name, field?)           field: name value
          ("avar2", index, "input" | "output", tag) / ("avar2", index, field?)
        Never raises.
        """
        try:
            return self._item_at(line, col)
        except Exception:
            return None

    def _item_at(self, line_no: int, col: int) -> Optional[tuple]:
        line = self.structure.line(line_no)
        if line is None or line.span is None or not line.span.contains(line_no, col):
            return None  # off the code: indentation, comment, past the end

        def field_at(fields: Dict[str, Span], skip=("range", "coords", "conditions", "inputs", "order")):
            hits = [
                name for name, span in fields.items()
                if span.contains(line_no, col) and name not in skip
            ]
            if not hits:
                hits = [name for name, span in fields.items() if span.contains(line_no, col)]
            if not hits:
                return None
            # the narrowest field
            return min(hits, key=lambda n: (fields[n].end_line - fields[n].line, fields[n].end_col - fields[n].col))

        doc = self.document
        kind = line.kind
        if kind in (st.FAMILY, st.SUFFIX, st.ELIDED_FALLBACK, st.PATH, st.LANG):
            name = field_at(line.fields)
            return (kind, name) if name else (kind,)
        if kind == st.SECTION:
            section = line.values.get("section")
            if section == "instances":
                name = field_at(line.fields)
                return ("instances", "mode") if name == "mode" else ("instances",)
            return ("section", section)
        if kind == st.AXIS:
            axis = next((a for a in self._all_axes() if a.line == line_no), None)
            if axis is None:
                return None
            name = field_at(axis.spans)
            return ("axis", axis.tag, name) if name else ("axis", axis.tag)
        if kind == st.MAPPING:
            for axis in self._all_axes():
                for mapping in axis.mappings:
                    if mapping.line == line_no:
                        key = mapping.label if mapping.label else mapping.user_value
                        name = field_at(mapping.spans)
                        return ("mapping", axis.tag, key, name) if name else ("mapping", axis.tag, key)
            return None
        if kind == st.SOURCE_LINE:
            source = next((s for s in doc.sources if s.line == line_no), None)
            if source is None:
                return None
            key = self.source_key(source)
            name = field_at(source.spans)
            if name and name.startswith("coord."):
                return ("source", key, "coord", name[6:])
            if name == "layer_name":
                name = "layer"
            return ("source", key, name) if name else ("source", key)
        if kind == st.RULE:
            index = next((i for i, r in enumerate(doc.rules) if r.line == line_no), None)
            if index is None:
                return None
            name = field_at(doc.rules[index].spans)
            return ("rule", index, name) if name else ("rule", index)
        if kind in (st.SKIP_ENTRY,):
            return ("skip", " ".join(line.values.get("value", "").split()))
        if kind == st.SKIP:
            return ("instances",)
        if kind == st.AVAR2_VAR:
            name = field_at(line.fields)
            var = line.values.get("name", "")
            return ("avar2_var", var.lstrip("$"), name) if name else ("avar2_var", var.lstrip("$"))
        if kind in (st.AVAR2_ROW, st.AVAR2_BLOCK):
            row = line.number if kind == st.AVAR2_ROW else line.parent
            index = next((i for i, m in enumerate(doc.avar2_mappings) if m.line == row), None)
            if index is None:
                return None
            name = field_at(doc.avar2_mappings[index].spans)
            if name and "." in name:
                head, _, tag = name.partition(".")
                return ("avar2", index, head, tag)
            return ("avar2", index, name) if name else ("avar2", index)
        return None

    # =========================================================================
    # Editing machinery
    # =========================================================================

    def _result(self, edits: List[TextEdit], targets: Sequence[int] = ()) -> EditResult:
        """Check the edits and wrap them; refuse what the parser rejects"""
        edits = sorted(edits, key=lambda e: (e.line, e.col, e.end_line, e.end_col))
        for a, b in zip(edits, edits[1:]):
            if (b.line, b.col) < (a.end_line, a.end_col):
                raise EditError("rejected", "internal: overlapping edits")  # never
        new_text = apply_edits(self._text, edits)
        if not self._verify:
            return EditResult(edits, new_text, _font_data=self.font_data)
        parsed = _parse(new_text)
        messages = _new_errors((self._parser, self._parsed[1]), parsed)
        if messages:
            raise EditError("rejected", messages[0], messages)
        return EditResult(edits, new_text, Sketch(new_text, _parsed=parsed, font_data=self.font_data), self.font_data)

    def _check_target(self, line: Optional[st.Line]) -> None:
        if line is None or not self._verify:  # a fix targets the faulty line itself
            return
        for severity, _, number in self._parser.line_messages:
            if severity == "error" and number == line.number:
                raise EditError("target-has-errors", f"Line {line.number} has errors; fix it first")

    def _replace(self, span: Span, new_text: str) -> TextEdit:
        return TextEdit(span.line, span.col, span.end_line, span.end_col, new_text)

    def _insert_lines(self, after: int, texts: List[str]) -> TextEdit:
        """New lines after line `after` (0: at the top)"""
        raw = self.structure.text_lines
        joined = "\n".join(texts)
        if after < len(raw):
            return TextEdit(after + 1, 0, after + 1, 0, joined + "\n")
        last = len(raw)
        if raw[last - 1] == "":  # the text ends with a newline: line `last` is empty
            return TextEdit(last, 0, last, 0, joined + "\n")
        return TextEdit(last, len(raw[last - 1]), last, len(raw[last - 1]), "\n" + joined)

    def _delete_lines(self, first: int, last: int) -> TextEdit:
        raw = self.structure.text_lines
        if last < len(raw):
            return TextEdit(first, 0, last + 1, 0, "")
        if first > 1:
            return TextEdit(first - 1, len(raw[first - 2]), last, len(raw[last - 1]), "")
        return TextEdit(1, 0, last, len(raw[last - 1]), "")

    def _remove_item(self, line: st.Line) -> TextEdit:
        first, last = self.structure.owned_lines(line.number)
        return self._delete_lines(first, last)

    def _line_code_end(self, line: st.Line) -> Tuple[int, int]:
        """Where to append to a line's code (before a trailing comment)"""
        return line.number, line.span.end_col if line.span else len(line.raw)

    def _append_to_line(self, line: st.Line, text: str) -> TextEdit:
        number, col = self._line_code_end(line)
        return TextEdit(number, col, number, col, text)

    def _remove_field(self, line: st.Line, name: str) -> TextEdit:
        """Remove a field and the whitespace before it"""
        span = line.fields[name]
        start = span.col
        while start > 0 and line.raw[start - 1] in " \t":
            start -= 1
        return TextEdit(line.number, start, line.number, span.end_col, "")

    def _child_indent(self, parent: st.Line) -> str:
        children = [c for c in self.structure.children(parent.number) if c.kind == st.MAPPING]
        if children:
            return children[0].indent
        unit = self.structure.indent_unit
        return parent.indent + (unit if unit.strip() == "" else "    ")

    def _item_indent(self, section: str) -> str:
        for line in self.structure.lines:
            if line.section == section and line.kind in st.ITEM_KINDS and line.kind != st.SKIP_ENTRY and line.indent:
                return line.indent
        return self.structure.indent_unit

    def _section_lines(self, section: str) -> List[st.Line]:
        header = self.structure.section_header(section)
        if header is None:
            return []
        out = []
        for line in self.structure.lines[header.number:]:
            if line.kind == st.SECTION or line.kind in (st.FAMILY, st.SUFFIX, st.ELIDED_FALLBACK, st.PATH, st.LANG):
                break
            out.append(line)
        return out

    def _section_end(self, section: str) -> int:
        """The last item line of a section (its header if it has none)"""
        header = self.structure.section_header(section)
        last = header.number
        for line in self._section_lines(section):
            if line.kind not in (st.BLANK, st.COMMENT_LINE) or line.owner is not None:
                last = max(last, line.end_line)
        return last

    def _new_section(self, section: str, header: str, body: List[str]) -> TextEdit:
        """A section that does not exist yet, at its place in the usual order"""
        order = ["axes", "axes_hidden", "sources", "rules", "instances", "avar2_vars", "avar2", "avar2_matrix"]
        rank = order.index(section)
        after = 0
        for line in self.structure.lines:
            if line.kind in (st.FAMILY, st.SUFFIX, st.ELIDED_FALLBACK, st.PATH, st.LANG):
                after = max(after, line.number)
            elif line.kind == st.SECTION and order.index(line.values["section"]) < rank:
                after = max(after, self._section_end(line.values["section"]))
        before_next = next(
            (ln for ln in self.structure.lines
             if ln.kind == st.SECTION and order.index(ln.values["section"]) > rank and ln.number > after),
            None,
        )
        texts = [header] + body
        raw = self.structure.text_lines
        if after == 0 and before_next is None:
            after = len(raw)
            while after > 0 and raw[after - 1].strip() == "":
                after -= 1
        if before_next is not None:
            first = before_next.leading[0] if before_next.leading else before_next.number
            return self._insert_lines(first - 1, texts + [""])
        if after == 0:
            return self._insert_lines(0, texts)
        # after a blank line that follows the previous section, keep it as the
        # separator; otherwise make one
        if after < len(raw) and raw[after].strip() == "" and after + 1 < len(raw):
            following = raw[after + 1:]
            if any(line.strip() for line in following):
                texts = texts + [""]
            return self._insert_lines(after + 1, texts)
        return self._insert_lines(after, [""] + texts)

    def _format_value(self, axis: DSSAxis, value: Value, prefer: str, written: Iterable[str] = ()) -> str:
        """A design-space value for a coordinate: a number or the label at it"""
        if prefer not in PREFER_VALUES:
            raise EditError("invalid-value", f"prefer must be one of {PREFER_VALUES}")
        if isinstance(value, str) and not _is_number(value):
            if not any(m.label == value for m in axis.mappings):
                raise EditError("invalid-value", f"Axis '{axis.tag}' has no label '{value}'")
            if prefer != "number":
                return value
            value = next(m.design_value for m in axis.mappings if m.label == value)
        number = float(value)
        label = next((m.label for m in axis.mappings if m.label and m.design_value == number), None)
        if prefer == "keep":
            written = list(written)
            labels = sum(1 for w in written if w and not _is_number(w))
            use_label = labels * 2 > len(written) if written else False
        else:
            use_label = prefer == "label"
        if use_label and label:
            return label
        return format_number(number)

    # =========================================================================
    # Header: family, suffix, elidedfallback, path, lang
    # =========================================================================

    _HEADER_ORDER = (st.FAMILY, st.SUFFIX, st.ELIDED_FALLBACK, st.PATH, st.LANG)

    def _set_header(self, kind: str, value: Optional[str]) -> EditResult:
        quotable = (st.FAMILY, st.ELIDED_FALLBACK)  # names: quotes keep a # or spaces at the ends
        line = next(iter(self.structure.of_kind(kind)), None)
        if value is None or value == "":
            if line is None:
                return EditResult([], self._text, self)
            return self._result([self._remove_item(line)])
        if line is not None:
            self._check_target(line)
            if "value" in line.fields:
                old = line.text("value")
                new = value
                if kind in quotable and (old.startswith('"') or old.startswith("'")):
                    new = old[0] + value + old[0]
                elif kind in quotable and ("#" in value or value != value.strip()):
                    new = '"' + value + '"'
                return self._result([self._replace(line.fields["value"], new)])
            return self._result([self._append_to_line(line, " " + value)])
        # a new line, at its place among the header lines
        if kind in quotable and ("#" in value or value != value.strip()):
            value = '"' + value + '"'
        new_line = f"{kind} {value}"
        rank = self._HEADER_ORDER.index(kind)
        present = [ln for ln in self.structure.lines if ln.kind in self._HEADER_ORDER]
        before = [ln for ln in present if self._HEADER_ORDER.index(ln.kind) < rank]
        if before:
            return self._result([self._insert_lines(before[-1].number, [new_line])])
        after = [ln for ln in present if self._HEADER_ORDER.index(ln.kind) > rank]
        anchor = after[0] if after else next(
            (ln for ln in self.structure.lines if ln.kind == st.SECTION or ln.kind in st.ITEM_KINDS), None
        )
        if anchor is None:
            return self._result([self._insert_lines(len(self.structure.text_lines), [new_line])])
        first = anchor.leading[0] if anchor.leading else anchor.number
        texts = [new_line] if after else [new_line, ""]
        return self._result([self._insert_lines(first - 1, texts)])

    def set_family(self, value: Optional[str]) -> EditResult:
        """Set the family name; None or "" removes the line"""
        return self._set_header(st.FAMILY, value)

    def set_elided_fallback(self, value: Optional[str]) -> EditResult:
        """Set the name where every label is elided (`elidedfallback Book`,
        DesignSpace elidedFallbackName); None or "" removes the line, and the
        name is derived again (the weight's elidable label, else Regular)"""
        return self._set_header(st.ELIDED_FALLBACK, value)

    def set_suffix(self, value: Optional[str]) -> EditResult:
        return self._set_header(st.SUFFIX, value)

    def set_path(self, value: Optional[str]) -> EditResult:
        return self._set_header(st.PATH, value)

    def set_lang(self, codes: Optional[Sequence[str]]) -> EditResult:
        """Set the `lang` codes; None or [] removes the line"""
        return self._set_header(st.LANG, ", ".join(codes) if codes else None)

    # =========================================================================
    # Axes
    # =========================================================================

    def _axis_line(self, tag: str) -> Tuple[DSSAxis, st.Line]:
        axis = self.axis(tag)
        line = self._line_of(axis)
        if line is None:
            raise EditError("unknown-key", f"Axis '{tag}' has no line in the text")
        self._check_target(line)
        return axis, line

    def _range_text(self, axis: DSSAxis, minimum: Number, default: Number, maximum: Number,
                    written: Optional[st.Line], prefer: str) -> str:
        values = (float(minimum), float(default), float(maximum))
        two_part = written is not None and "default" not in written.fields and "min" in written.fields
        old_labels = written is not None and any(
            not _is_number(written.values.get(k, "0")) for k in ("min", "default", "max")
        )
        axis_type = {"wght": "weight", "wdth": "width"}.get(axis.tag)
        use_labels = axis_type is not None and (prefer == "label" or (prefer == "keep" and old_labels))
        if use_labels:
            names = []
            for v in values:
                name = Standards.get_name_by_user_space(v, axis_type)
                if not Standards.has_mapping(name, axis_type) or Standards.get_user_space_value(name, axis_type) != v:
                    names = None
                    break
                names.append(name)
            if names:
                return ":".join(names)
        if two_part and values[0] == values[1]:
            return f"{format_number(values[0])}:{format_number(values[2])}"
        return ":".join(format_number(v) for v in values)

    def add_axis(
        self,
        tag: str,
        minimum: Number = 0,
        default: Number = 0,
        maximum: Number = 1,
        *,
        name: Optional[str] = None,
        display_name: Optional[str] = None,
        discrete: bool = False,
        hidden: bool = False,
        index: Optional[int] = None,
    ) -> EditResult:
        """Add an axis (`hidden=True`: a hidden avar2 axis) at `index` among
        its section's axes (default: last). Mappings: `add_mapping()`"""
        if any(a.tag == tag for a in self._all_axes()):
            raise EditError("duplicate", f"Axis '{tag}' exists already")
        if not tag or len(tag) != 4 or " " in tag:
            raise EditError("invalid-value", f"An axis tag has four characters: '{tag}'")
        section = "axes_hidden" if hidden else "axes"
        parts = []
        if name and not hidden:
            parts.append(name)
        parts.append(tag)
        if discrete and not hidden:
            parts.append("discrete")
        else:
            parts.append(":".join(format_number(v) for v in (minimum, default, maximum)))
        if display_name and not hidden:
            parts.append('"' + display_name + '"')
        header = self.structure.section_header(section)
        axes = [ln for ln in self._section_lines(section) if ln.kind == st.AXIS]
        if index is None or index > len(axes):
            index = len(axes)
        index = max(index, 0)
        edits = [] if hidden else self._add_axis_coordinates(tag, minimum, default, maximum, discrete, index)
        if header is None:
            body = ["    " + " ".join(parts)]
            edits.append(self._new_section(section, "axes hidden" if hidden else "axes", body))
            return self._result(edits)
        text = self._item_indent(section) + " ".join(parts)
        if index >= len(axes):
            after = self._section_end(section) if not axes else self.structure.owned_lines(axes[-1].number)[1]
            edits.append(self._insert_lines(after, [text]))
        else:
            first, _ = self.structure.owned_lines(axes[index].number)
            edits.append(self._insert_lines(first - 1, [text]))
        return self._result(edits)

    def _add_axis_coordinates(self, tag, minimum, default, maximum, discrete, index) -> List[TextEdit]:
        """A new visible axis's column: its default in every positional source
        (and its tag in `sources [order]`)"""
        value = format_number(minimum if discrete else default)
        header = self.structure.section_header("sources")
        if header is not None and "order" in header.fields:
            count = len(self._source_order())
            edits = [self._insert_list_item(header, "order", count, tag)]
            position = count
        else:
            edits = []
            position = index
        for source in self.document.sources:
            line = self._line_of(source)
            if line is not None and line.values.get("coords") == "positional":
                edits.append(self._insert_list_item(line, "coord", position, value))
        return edits

    def _insert_list_item(self, line: st.Line, prefix: str, position: int, text: str) -> TextEdit:
        """Insert into a comma list (`order.N` / `coord.N`) at `position`"""
        count = 0
        while f"{prefix}.{count}" in line.fields:
            count += 1
        if position < count:
            span = line.fields[f"{prefix}.{position}"]
            return TextEdit(line.number, span.col, line.number, span.col, text + ", ")
        if count:
            span = line.fields[f"{prefix}.{count - 1}"]
            return TextEdit(line.number, span.end_col, line.number, span.end_col, ", " + text)
        brackets = line.fields["order" if prefix == "order" else "coords"]
        return TextEdit(line.number, brackets.col + 1, line.number, brackets.col + 1, text)

    def _references(self, axis: DSSAxis) -> List[str]:
        """What refers to an axis besides source coordinates: rules, avar2, skip"""
        refs = []
        names = {axis.name.lower(), axis.tag.lower(), (axis.display_name or "").lower()}
        for i, rule in enumerate(self.document.rules):
            if any(str(c.get("axis", "")).lower() in names for c in rule.conditions):
                refs.append(f"rule {i + 1}")
        for i, mapping in enumerate(self.document.avar2_mappings):
            keys = {k.lower() for k in list(mapping.input) + list(mapping.output)}
            if keys & names:
                refs.append(f"avar2 mapping {i + 1}")
        labels = {m.label for m in axis.mappings if m.label}
        for entry in self.document.instances_skip:
            if labels & set(entry.split()):
                refs.append(f"skip '{entry}'")
        return refs

    def remove_axis(self, tag: str) -> EditResult:
        """Remove an axis with its mappings and owned comments, and its
        coordinate from every source and from `sources [order]`. Refused
        (`in-use`) while rules, avar2 or skip entries refer to it"""
        axis, line = self._axis_line(tag)
        refs = self._references(axis)
        if refs:
            raise EditError("in-use", f"Axis '{axis.tag}' is used by {', '.join(refs)}", refs)
        edits = [self._remove_item(line)]
        edits += self._drop_axis_coordinates(axis)
        return self._result(edits)

    def _drop_axis_coordinates(self, axis: DSSAxis) -> List[TextEdit]:
        edits = []
        order = self._source_order()
        header = self.structure.section_header("sources")
        if axis.tag not in order:
            position = None
        else:
            position = order.index(axis.tag)
        if header is not None and position is not None and f"order.{position}" in header.fields:
            edits.append(self._remove_list_item(header, "order", position))
        for source in self.document.sources:
            sline = self._line_of(source)
            if sline is None:
                continue
            if sline.values.get("coords") == "positional" and position is not None and f"coord.{position}" in sline.fields:
                edits.append(self._remove_list_item(sline, "coord", position))
            elif sline.values.get("coords") == "named":
                for name in list(sline.fields):
                    if name.startswith("coord.") and self._axis_ref_tag(name[6:]) == axis.tag:
                        edits.append(self._remove_named(sline, name))
        return edits

    def _remove_list_item(self, line: st.Line, prefix: str, position: int) -> TextEdit:
        """Remove item `position` of a comma list (`order.N` / `coord.N`) with
        its separator"""
        span = line.fields[f"{prefix}.{position}"]
        nxt = line.fields.get(f"{prefix}.{position + 1}")
        if nxt is not None:
            return TextEdit(line.number, span.col, line.number, nxt.col, "")
        prev = line.fields.get(f"{prefix}.{position - 1}") if position > 0 else None
        if prev is not None:
            return TextEdit(line.number, prev.end_col, line.number, span.end_col, "")
        return TextEdit(line.number, span.col, line.number, span.end_col, "")

    def _remove_named(self, line: st.Line, name: str) -> TextEdit:
        """Remove `axis=value` from a named source line, with its comma"""
        value = line.fields[name]
        raw = line.raw
        start = raw.rfind(name[6:], 0, value.col)
        end = value.end_col
        rest = raw[end:]
        stripped = rest.lstrip()
        if stripped.startswith(","):
            end += len(rest) - len(stripped) + 1
            while end < len(raw) and raw[end] in " \t":
                end += 1
        else:
            before = raw[:start].rstrip()
            if before.endswith(","):
                start = len(before) - 1
        return TextEdit(line.number, start, line.number, end, "")

    def move_axis(self, tag: str, index: int) -> EditResult:
        """Move an axis (with mappings and comments) to `index` among the
        axes of its section. Positional coordinates keep their meaning: a
        `sources` line without an axis order gets the old order written"""
        axis, line = self._axis_line(tag)
        section = line.section
        axes = [ln for ln in self._section_lines(section) if ln.kind == st.AXIS]
        current = next(i for i, ln in enumerate(axes) if ln.number == line.number)
        index = max(0, min(index, len(axes) - 1))
        if index == current:
            return EditResult([], self._text, self)
        first, last = self.structure.owned_lines(line.number)
        block = self.structure.text_lines[first - 1: last]
        remaining = [ln for ln in axes if ln.number != line.number]
        edits = [self._delete_lines(first, last)]
        if index >= len(remaining):
            anchor_last = self.structure.owned_lines(remaining[-1].number)[1]
            edits.append(self._insert_lines(anchor_last, block))
        else:
            target_first = self.structure.owned_lines(remaining[index].number)[0]
            edits.append(self._insert_lines(target_first - 1, block))
        header = self.structure.section_header("sources")
        if section == "axes" and header is not None and "order" not in header.fields and self.document.sources:
            positional = any(
                (self._line_of(s) or st.Line(0, "", None, "", None)).values.get("coords") == "positional"
                for s in self.document.sources
            )
            if positional:
                order = ", ".join(a.tag for a in self.document.axes)
                edits.append(self._append_to_line(header, f" [{order}]"))
        # the deletion and insertion may touch the same line boundary: apply
        # them as one replacement of the whole region
        return self._result(_merge_line_moves(edits, self.structure.text_lines))

    def set_axis_tag(self, tag: str, new_tag: str) -> EditResult:
        """Change an axis tag, and every reference that writes the old tag
        (sources order, named coordinates, rule conditions, avar2)"""
        axis, line = self._axis_line(tag)
        if new_tag == axis.tag:
            return EditResult([], self._text, self)
        if any(a.tag == new_tag for a in self._all_axes()):
            raise EditError("duplicate", f"Axis '{new_tag}' exists already")
        if len(new_tag) != 4 or " " in new_tag:
            raise EditError("invalid-value", f"An axis tag has four characters: '{new_tag}'")
        if "tag" not in line.fields:
            raise EditError("not-applicable", f"Axis '{tag}' line writes no tag")
        edits = [self._replace(line.fields["tag"], new_tag)]
        edits += self._rename_axis_refs({axis.tag}, new_tag, skip_line=line.number)
        if "name" not in line.fields:
            # the name comes from the tag (`wght` -> "weight"): references
            # that write it follow too
            old_name, new_name = axis.name, _default_axis_name(new_tag)
            if old_name.lower() not in (axis.tag.lower(), new_name.lower()):
                edits += self._rename_axis_refs({old_name}, new_name, skip_line=line.number, case_insensitive=True)
        return self._result(edits)

    def _rename_axis_refs(self, old: set, new: str, skip_line: int = 0, case_insensitive=False) -> List[TextEdit]:
        from .syntax import AXIS_TAG

        def matches(text):
            return text.lower() in {o.lower() for o in old} if case_insensitive else text in old

        edits = []
        for line in self.structure.lines:
            if line.number == skip_line or line.kind not in (
                st.SECTION, st.SOURCE_LINE, st.RULE, st.AVAR2_ROW, st.AVAR2_BLOCK, st.AVAR2_HEADER,
            ):
                continue
            for token in line.tokens:
                if token.type == AXIS_TAG and matches(token.text):
                    edits.append(TextEdit(line.number, token.column, line.number, token.column + token.length, new))
        return edits

    def set_axis_name(self, tag: str, name: Optional[str]) -> EditResult:
        """Set (None: remove) the name written before the tag
        (`CONTRAST CNTR 0:0:100`). References that write the old name follow"""
        axis, line = self._axis_line(tag)
        if "name" in line.fields and "tag" in line.fields and line.fields["name"] == line.fields["tag"]:
            raise EditError("not-applicable", f"Axis '{tag}' is written by its human name only")
        edits = []
        if name:
            if "name" in line.fields:
                edits.append(self._replace(line.fields["name"], name))
            else:
                span = line.fields["tag"]
                edits.append(TextEdit(span.line, span.col, span.line, span.col, name + " "))
        elif "name" in line.fields:
            span = line.fields["name"]
            end = line.fields["tag"].col
            edits.append(TextEdit(span.line, span.col, span.line, end, ""))
        else:
            return EditResult([], self._text, self)
        old_name = axis.name
        new_effective = name or _default_axis_name(axis.tag)
        if old_name.lower() != new_effective.lower():
            edits += self._rename_axis_refs({old_name}, new_effective, skip_line=line.number, case_insensitive=True)
        return self._result(edits)

    def set_axis_display_name(self, tag: str, display_name: Optional[str]) -> EditResult:
        """Set (None: remove) the quoted DesignSpace name of an axis"""
        axis, line = self._axis_line(tag)
        if display_name:
            quoted = '"' + display_name + '"'
            if "display_name" in line.fields:
                return self._result([self._replace(line.fields["display_name"], quoted)])
            return self._result([self._append_to_line(line, " " + quoted)])
        if "display_name" in line.fields:
            return self._result([self._remove_field(line, "display_name")])
        return EditResult([], self._text, self)

    def set_axis_range(
        self,
        tag: str,
        minimum: Optional[Number] = None,
        default: Optional[Number] = None,
        maximum: Optional[Number] = None,
        prefer: str = "keep",
    ) -> EditResult:
        """Set an axis's user-space range (a value left None stays). The
        spelling follows the line (`Thin:Regular:Black` stays labels while
        standard labels exist; `min:max` stays two parts while default = min)"""
        axis, line = self._axis_line(tag)
        if axis.is_discrete or "discrete" in line.fields:
            raise EditError("not-applicable", f"Axis '{tag}' is discrete; it has no range")
        if "range" not in line.fields:
            raise EditError("target-has-errors", f"Axis '{tag}' line has no range")
        values = (
            axis.minimum if minimum is None else minimum,
            axis.default if default is None else default,
            axis.maximum if maximum is None else maximum,
        )
        if not values[0] <= values[1] <= values[2]:
            raise EditError("invalid-value", f"Range must be ordered: {values}")
        text = self._range_text(axis, *values, written=line, prefer=prefer)
        return self._result([self._replace(line.fields["range"], text)])

    def set_axis_discrete(self, tag: str, discrete: bool) -> EditResult:
        """`ital discrete` <-> `ital 0:0:1`"""
        axis, line = self._axis_line(tag)
        if self._is_hidden(axis):
            raise EditError("not-applicable", "A hidden axis cannot be discrete")
        if discrete:
            if "discrete" in line.fields:
                return EditResult([], self._text, self)
            return self._result([self._replace(line.fields["range"], "discrete")])
        if "discrete" not in line.fields:
            return EditResult([], self._text, self)
        text = ":".join(format_number(v) for v in (axis.minimum, axis.default, axis.maximum))
        return self._result([self._replace(line.fields["discrete"], text)])

    # =========================================================================
    # Mappings
    # =========================================================================

    def _mapping_line(self, tag: str, key: Value) -> Tuple[DSSAxis, DSSAxisMapping, st.Line]:
        axis = self.axis(tag)
        mapping = self.mapping(tag, key)
        line = self._line_of(mapping)
        if line is None:
            raise EditError("unknown-key", f"Mapping '{key}' has no line in the text")
        self._check_target(line)
        return axis, mapping, line

    @staticmethod
    def _inferred_user(axis: DSSAxis, label: str, design: float) -> float:
        if label and Standards.has_mapping(label, axis.name):
            return Standards.get_user_value_for_name(label, axis.name)
        return design

    def _mapping_text(self, axis: DSSAxis, label: str, design: Optional[Number],
                      user: Optional[Number], elidable: bool) -> str:
        if axis.is_discrete and design is None:
            text = label
        else:
            if design is None:
                raise EditError("invalid-value", "A mapping needs a design value")
            design = float(design)
            explicit = user is not None and (not label or self._inferred_user(axis, label, design) != float(user))
            head = (format_number(user) + " " + label).strip() if explicit else label
            if not head:
                raise EditError("invalid-value", "A mapping needs a label or a user value")
            text = f"{head} > {format_number(design)}"
        if elidable:
            text += " @elidable"
        return text

    def add_mapping(
        self,
        tag: str,
        label: str,
        design: Optional[Number] = None,
        user: Optional[Number] = None,
        *,
        elidable: bool = False,
        index: Optional[int] = None,
    ) -> EditResult:
        """Add `[user] label > design [@elidable]` to an axis

        `user` None: inferred (the standard value of a standard label, else
        the design value); it is written only when it differs from that. On a
        discrete axis a bare label (`Italic`) needs no design value. `label`
        "" adds an unnamed map point (needs `user`). Placed by user value
        unless `index` is given."""
        axis, line = self._axis_line(tag)
        if label and any(m.label == label for a in self._all_axes() for m in a.mappings):
            raise EditError("duplicate", f"Label '{label}' exists already")
        text = self._mapping_text(axis, label, design, user, elidable)
        indent = self._child_indent(line)
        children = [self._line_of(m) for m in axis.mappings]
        children = [c for c in children if c is not None]
        if index is None:
            new_user = float(user) if user is not None else (
                self._inferred_user(axis, label, float(design)) if design is not None else None
            )
            index = len(axis.mappings)
            if new_user is not None:
                for i, m in enumerate(axis.mappings):
                    if m.user_value is not None and m.user_value > new_user:
                        index = i
                        break
        if index >= len(children):
            after = self.structure.owned_lines(line.number)[1]
            return self._result([self._insert_lines(after, [indent + text])])
        target = children[max(index, 0)]
        first = target.leading[0] if target.leading else target.number
        return self._result([self._insert_lines(first - 1, [indent + text])])

    def remove_mapping(self, tag: str, key: Value) -> EditResult:
        """Remove a mapping (with its owned comments). Its label's uses are
        not touched: the parser reports any left behind and refuses"""
        _, _, line = self._mapping_line(tag, key)
        return self._result([self._remove_item(line)])

    def set_mapping_label(self, tag: str, key: Value, label: str) -> EditResult:
        """Change a mapping's label on its line only (`rename_label` also
        rewrites its uses)"""
        axis, mapping, line = self._mapping_line(tag, key)
        if label == mapping.label:
            return EditResult([], self._text, self)
        if label and any(m.label == label for a in self._all_axes() for m in a.mappings):
            raise EditError("duplicate", f"Label '{label}' exists already")
        return self._result([self._relabel(axis, mapping, line, label)])

    def _relabel(self, axis: DSSAxis, mapping: DSSAxisMapping, line: st.Line, label: str) -> TextEdit:
        """The mapping line with a new label and the same values: the user
        value is written out when the new label would infer another one"""
        bare = axis.is_discrete and "design" not in line.fields
        if bare:
            return self._replace(line.fields["label"], label)
        user = mapping.user_value
        if not mapping.user_value_explicit and self._inferred_user(axis, label, mapping.design_value) == user:
            return self._replace(line.fields["label"], label)
        if "user" in line.fields:
            return self._replace(line.fields["label"], label)
        span = line.fields["label"]
        return TextEdit(span.line, span.col, span.end_line, span.end_col, f"{format_number(user)} {label}")

    def set_mapping_user(self, tag: str, key: Value, user: Optional[Number]) -> EditResult:
        """Set a mapping's user value; None makes it inferred again"""
        axis, mapping, line = self._mapping_line(tag, key)
        design = mapping.design_value if "design" in line.fields or not axis.is_discrete else None
        if design is None:
            raise EditError("not-applicable", "A bare discrete label has no user value to set")
        text = self._mapping_text(axis, mapping.label, design, user, mapping.elidable)
        return self._result([self._replace(line.span, text)])

    def set_mapping_design(self, tag: str, key: Value, design: Number) -> EditResult:
        """Set a mapping's design value (its user value stays what it is)"""
        axis, mapping, line = self._mapping_line(tag, key)
        if "design" in line.fields:
            return self._result([self._replace(line.fields["design"], format_number(design))])
        user = mapping.user_value if mapping.user_value_explicit else None
        text = self._mapping_text(axis, mapping.label, design, user if user is not None else mapping.user_value, mapping.elidable)
        return self._result([self._replace(line.span, text)])

    def set_mapping_elidable(self, tag: str, key: Value, elidable: bool) -> EditResult:
        _, mapping, line = self._mapping_line(tag, key)
        if elidable == ("flag.elidable" in line.fields):
            return EditResult([], self._text, self)
        if elidable:
            return self._result([self._append_to_line(line, " @elidable")])
        return self._result([self._remove_field(line, "flag.elidable")])

    def rename_label(self, tag: str, old: str, new: str) -> EditResult:
        """Rename a label and every use of it: source coordinates, rule
        conditions, skip entries, avar2 inputs"""
        from .syntax import LABEL

        axis, mapping, line = self._mapping_line(tag, old)
        if not new or " " in new:
            raise EditError("invalid-value", f"A label is one word: '{new}'")
        if any(m.label == new for a in self._all_axes() for m in a.mappings):
            raise EditError("duplicate", f"Label '{new}' exists already")
        edits = [self._relabel(axis, mapping, line, new)]
        order = self._source_order()
        for other in self.structure.lines:
            if other.number == line.number:
                continue
            if other.kind == st.SOURCE_LINE:
                for name, span in other.fields.items():
                    if not name.startswith("coord.") or other.values[name] != old:
                        continue
                    ref = name[6:]
                    target = order[int(ref)] if ref.isdigit() and int(ref) < len(order) else self._axis_ref_tag(ref)
                    if target == axis.tag:
                        edits.append(self._replace(span, new))
            elif other.kind in (st.RULE, st.SKIP_ENTRY, st.AVAR2_ROW):
                for token in other.tokens:
                    if token.type == LABEL and token.text == old:
                        if other.kind == st.AVAR2_ROW and not other.fields.get("inputs", Span(0, 0, 0, 0)).contains(other.number, token.column):
                            continue
                        edits.append(TextEdit(other.number, token.column, other.number, token.column + token.length, new))
        return self._result(edits)

    # =========================================================================
    # Sources
    # =========================================================================

    def _source_line(self, key) -> Tuple[DSSSource, st.Line]:
        source = self.source(key)
        line = self._line_of(source)
        if line is None:
            raise EditError("unknown-key", f"Source '{key}' has no line in the text")
        self._check_target(line)
        return source, line

    def _column_written(self, position: int) -> List[str]:
        """How the sources write coordinate `position` (for prefer="keep")"""
        out = []
        for source in self.document.sources:
            line = self._line_of(source)
            if line is not None and f"coord.{position}" in line.values:
                out.append(line.values[f"coord.{position}"])
        return out

    def _named_written(self, tag: str) -> List[str]:
        out = []
        for source in self.document.sources:
            line = self._line_of(source)
            if line is None:
                continue
            for name, value in line.values.items():
                if name.startswith("coord.") and not name[6:].isdigit() and self._axis_ref_tag(name[6:]) == tag:
                    out.append(value)
        return out

    def add_source(
        self,
        name: str,
        location: Optional[Dict[str, Value]] = None,
        *,
        base: bool = False,
        sparse: bool = False,
        layer: Optional[str] = None,
        prefer: str = "keep",
        index: Optional[int] = None,
    ) -> EditResult:
        """Add a source. `location`: design-space values (numbers or labels)
        by axis tag; an axis left out sits at its default. Written in the
        form the other sources use (positional or named)"""
        location = dict(location or {})
        resolved = {}
        for ref, value in location.items():
            tag = self._axis_ref_tag(ref)
            if tag is None:
                raise EditError("unknown-key", f"No axis '{ref}'")
            resolved[tag] = value
        lines = [self._line_of(s) for s in self.document.sources]
        lines = [ln for ln in lines if ln is not None]
        named = bool(lines) and all(ln.values.get("coords") == "named" for ln in lines if ln.values.get("coords"))
        named = named and any(ln.values.get("coords") == "named" for ln in lines)
        parts = [_quote_if_needed(name)]
        if named:
            pairs = []
            for tag, value in resolved.items():
                axis = self.axis(tag)
                pairs.append(f"{tag}={self._format_value(axis, value, prefer, self._named_written(tag))}")
            if pairs:
                parts.append(", ".join(pairs))
        else:
            coords = []
            for position, tag in enumerate(self._source_order()):
                try:
                    axis = self.axis(tag)
                except EditError:
                    continue
                value = resolved.get(tag, axis.design_default)
                coords.append(self._format_value(axis, value, prefer, self._column_written(position)))
            parts.append("[" + ", ".join(coords) + "]")
        if base:
            parts.append("@base")
        if sparse:
            parts.append("@sparse")
        if layer:
            parts.append(f'@layer="{layer}"')
        text = " ".join(parts)
        header = self.structure.section_header("sources")
        if header is None:
            return self._result([self._new_section("sources", "sources", ["    " + text])])
        text = self._item_indent("sources") + text
        if index is None or index >= len(lines):
            after = self.structure.owned_lines(lines[-1].number)[1] if lines else self._section_end("sources")
            return self._result([self._insert_lines(after, [text])])
        target = lines[max(index, 0)]
        first = target.leading[0] if target.leading else target.number
        return self._result([self._insert_lines(first - 1, [text])])

    def remove_source(self, key) -> EditResult:
        _, line = self._source_line(key)
        return self._result([self._remove_item(line)])

    def rename_source(self, key, name: str) -> EditResult:
        """Change the file a source names, as written (keeps `.ufo` off if
        the line left it off)"""
        _, line = self._source_line(key)
        old = line.text("name")
        new = name
        if old.startswith(('"', "'")):
            new = old[0] + name + old[0]
        else:
            new = _quote_if_needed(name)
        return self._result([self._replace(line.fields["name"], new)])

    def set_source_coordinate(self, key, tag: str, value: Value, prefer: str = "keep") -> EditResult:
        """Set one coordinate of a source (design space: a number or a label)"""
        source, line = self._source_line(key)
        axis_tag = self._axis_ref_tag(tag)
        if axis_tag is None:
            raise EditError("unknown-key", f"No axis '{tag}'")
        axis = self.axis(axis_tag)
        form = line.values.get("coords")
        if form == "positional":
            order = self._source_order()
            if axis_tag not in order:
                raise EditError("unknown-key", f"Axis '{tag}' has no column in the sources")
            position = order.index(axis_tag)
            if f"coord.{position}" not in line.fields:
                raise EditError("target-has-errors", f"Source '{key}' has no coordinate {position + 1}")
            written = self._column_written(position)
            text = self._format_value(axis, value, prefer, written)
            return self._result([self._replace(line.fields[f"coord.{position}"], text)])
        written = self._named_written(axis_tag)
        text = self._format_value(axis, value, prefer, written)
        for name in line.fields:
            if name.startswith("coord.") and self._axis_ref_tag(name[6:]) == axis_tag:
                return self._result([self._replace(line.fields[name], text)])
        pair = f"{axis_tag}={text}"
        if form == "named":
            last = max(
                (span for name, span in line.fields.items() if name.startswith("coord.")),
                key=lambda s: s.end_col,
            )
            return self._result([TextEdit(line.number, last.end_col, line.number, last.end_col, ", " + pair)])
        name_span = line.fields["name"]
        return self._result([TextEdit(line.number, name_span.end_col, line.number, name_span.end_col, " " + pair)])

    def _flag_insert_point(self, line: st.Line) -> Tuple[int, int]:
        """After the coordinates (or the name), before the first flag"""
        flags = [span for name, span in line.fields.items() if name.startswith("flag.")]
        if flags:
            first = min(flags, key=lambda s: s.col)
            return line.number, first.col
        return self._line_code_end(line)

    def _add_flag(self, line: st.Line, flag: str) -> TextEdit:
        number, col = self._flag_insert_point(line)
        flags = [span for name, span in line.fields.items() if name.startswith("flag.")]
        if flags:
            return TextEdit(number, col, number, col, flag + " ")
        return TextEdit(number, col, number, col, " " + flag)

    def set_base(self, key) -> EditResult:
        """Make a source the base, taking `@base` from the source it replaces
        (with discrete axes: the base with the same discrete coordinates)"""
        source, line = self._source_line(key)
        edits = []
        if "flag.base" not in line.fields:
            edits.append(self._add_flag(line, "@base"))
        discrete = [a for a in self.document.axes if a.is_discrete]
        for other in self.document.sources:
            if other is source or not other.is_base:
                continue
            if any(other.location.get(a.name) != source.location.get(a.name) for a in discrete):
                continue
            oline = self._line_of(other)
            if oline is not None and "flag.base" in oline.fields:
                edits.append(self._remove_field(oline, "flag.base"))
        if not edits:
            return EditResult([], self._text, self)
        return self._result(edits)

    def set_sparse(self, key, sparse: bool) -> EditResult:
        _, line = self._source_line(key)
        if sparse == ("flag.sparse" in line.fields):
            return EditResult([], self._text, self)
        if sparse:
            return self._result([self._add_flag(line, "@sparse")])
        return self._result([self._remove_field(line, "flag.sparse")])

    def set_layer(self, key, layer: Optional[str]) -> EditResult:
        """Set (None: remove) a source's UFO layer"""
        _, line = self._source_line(key)
        if layer:
            if "layer" in line.fields:
                old = line.text("layer")
                quote = old[0] if old[:1] in ("'", '"') else ('"' if any(c in layer for c in " #'\"") else "")
                return self._result([self._replace(line.fields["layer"], f"{quote}{layer}{quote}")])
            if "flag.layer" in line.fields:
                return self._result([self._replace(line.fields["flag.layer"], f'@layer="{layer}"')])
            number, col = self._line_code_end(line)
            return self._result([TextEdit(number, col, number, col, f' @layer="{layer}"')])
        if "flag.layer" in line.fields:
            return self._result([self._remove_field(line, "flag.layer")])
        return EditResult([], self._text, self)

    # =========================================================================
    # Instances and skip
    # =========================================================================

    def set_instances_mode(self, mode: str) -> EditResult:
        """`instances auto` or `instances off` (adds the section if missing)"""
        if mode not in ("auto", "off"):
            raise EditError("invalid-value", "mode is 'auto' or 'off'")
        header = self.structure.section_header("instances")
        if header is None:
            return self._result([self._new_section("instances", f"instances {mode}", [])])
        if "mode" in header.fields:
            if header.values["mode"] == mode:
                return EditResult([], self._text, self)
            return self._result([self._replace(header.fields["mode"], mode)])
        return self._result([self._append_to_line(header, " " + mode)])

    def _labels(self) -> Dict[str, str]:
        return {m.label: a.tag for a in self.document.axes for m in a.mappings if m.label}

    def add_skip(self, entry: str) -> EditResult:
        """Add a `skip` entry (a final instance name, its words axis labels)"""
        words = entry.split()
        if not words:
            raise EditError("invalid-value", "An empty skip entry")
        labels = self._labels()
        unknown = [w for w in words if w not in labels]
        if unknown:
            raise EditError("invalid-value", f"Not an axis label: {', '.join(unknown)}", unknown)
        entry = " ".join(words)
        if self._skip_line(entry) is not None:
            raise EditError("duplicate", f"Skip entry '{entry}' exists already")
        header = self.structure.section_header("instances")
        if header is None:
            return self._result([self._new_section("instances", "instances auto", ["    skip", "        " + entry])])
        if header.values.get("mode") == "off":
            raise EditError("not-applicable", "instances off generates nothing to skip")
        section = self._section_lines("instances")
        skip = next((ln for ln in section if ln.kind == st.SKIP), None)
        entries = [ln for ln in section if ln.kind == st.SKIP_ENTRY]
        if skip is None:
            unit = self.structure.indent_unit
            return self._result([self._insert_lines(self._section_end("instances"), [unit + "skip", unit * 2 + entry])])
        indent = entries[0].indent if entries else skip.indent + self.structure.indent_unit
        after = entries[-1].number if entries else skip.number
        return self._result([self._insert_lines(after, [indent + entry])])

    def remove_skip(self, entry: str) -> EditResult:
        """Remove a `skip` entry (and the `skip` line when it was the last)"""
        line = self._skip_line(entry)
        if line is None:
            raise EditError("unknown-key", f"No skip entry '{entry}'")
        section = self._section_lines("instances")
        entries = [ln for ln in section if ln.kind == st.SKIP_ENTRY]
        skip = next((ln for ln in section if ln.kind == st.SKIP), None)
        if len(entries) == 1 and skip is not None and skip.comment is None:
            first, _ = self.structure.owned_lines(skip.number)
            _, last = self.structure.owned_lines(line.number)
            if all(
                ln.kind in (st.SKIP, st.SKIP_ENTRY) or ln.owner == line.number
                for ln in self.structure.lines[first - 1: last]
            ):
                return self._result([self._delete_lines(first, last)])
        return self._result([self._remove_item(line)])


def _default_axis_name(tag: str) -> str:
    from .parsers.dss_parser import DSSParser

    return DSSParser.TAG_TO_NAME.get(tag, tag.upper())


def _merge_line_moves(edits: List[TextEdit], text_lines: List[str]) -> List[TextEdit]:
    """Edits that may share a boundary (a deletion of whole lines and an
    insertion at its edge) made safe to apply together

    An insertion exactly at the start of a deleted range would land inside
    it; it is folded into the deletion's replacement text.
    """
    out: List[TextEdit] = []
    deletions = [e for e in edits if (e.line, e.col) != (e.end_line, e.end_col)]
    insertions = [e for e in edits if (e.line, e.col) == (e.end_line, e.end_col)]
    for ins in insertions:
        host = next(
            (d for d in deletions if (d.line, d.col) <= (ins.line, ins.col) <= (d.end_line, d.end_col)),
            None,
        )
        if host is None:
            out.append(ins)
            continue
        deletions.remove(host)
        if (ins.line, ins.col) == (host.line, host.col):
            deletions.append(TextEdit(host.line, host.col, host.end_line, host.end_col, ins.new_text + host.new_text))
        else:
            deletions.append(TextEdit(host.line, host.col, host.end_line, host.end_col, host.new_text + ins.new_text))
    return sorted(out + deletions, key=lambda e: (e.line, e.col))
