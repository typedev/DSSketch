"""The layout of a .dssketch text: what each line is, and where its parts are

DSSketch is line-oriented, so the structure of a text is a list of lines, each
classified (an axis, a mapping, a source, a comment …) with the column spans
of its parts ("fields"). It is built from `syntax.tokenize()`'s tokens, which
mirror the parser line for line, and never raises.

This is what an editor needs to read positions from and to write minimal
edits into a hand-written text (`sketch.py`). It says nothing about meaning:
values are text, labels are not resolved. The meaning comes from the parser,
whose models carry the line they were declared on; `Sketch` joins the two.

Comment ownership (used when a line is removed or moved):
- a trailing comment belongs to its line;
- full-line comments directly above an item, with no blank line between,
  belong to that item ("leading" comments);
- any other comment belongs to the section.

Light: stdlib and PyYAML only (`tests/test_light_imports.py`).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import syntax
from .syntax import (
    AXIS_NAME,
    AXIS_TAG,
    COMMENT,
    FLAG,
    KEYWORD,
    LABEL,
    NUMBER,
    OPERATOR,
    PUNCTUATION,
    SOURCE,
    STRING,
    TEXT,
    UNKNOWN,
    VARIABLE,
    Token,
)

# =============================================================================
# Positions
# =============================================================================


@dataclass(frozen=True)
class Span:
    """A range of text: lines from 1, columns from 0, `end_col` exclusive"""

    line: int
    col: int
    end_line: int
    end_col: int

    def contains(self, line: int, col: int) -> bool:
        """Whether the position lies in the span (its end included, as a cursor)"""
        if (line, col) < (self.line, self.col):
            return False
        return (line, col) <= (self.end_line, self.end_col)


def _token_span(token: Token) -> Span:
    return Span(token.line, token.column, token.line, token.column + token.length)


def _join(first: Token, last: Token) -> Span:
    return Span(first.line, first.column, last.line, last.column + last.length)


# =============================================================================
# Line kinds (what Line.kind holds)
# =============================================================================

BLANK = "blank"
COMMENT_LINE = "comment"
FAMILY = "family"
SUFFIX = "suffix"
ELIDED_FALLBACK = "elidedfallback"
PATH = "path"
LANG = "lang"
SECTION = "section"            # axes, axes hidden, sources, rules, instances, avar2 …
AXIS = "axis"
MAPPING = "mapping"
SOURCE_LINE = "source"
SKIP = "skip"                  # the `skip` keyword line
SKIP_ENTRY = "skip-entry"
INSTANCE = "instance"          # an explicit instance block's name line
INSTANCE_FIELD = "instance-field"  # `key: value` under it
RULE = "rule"
AVAR2_VAR = "avar2-var"
AVAR2_ROW = "avar2-row"        # a linear mapping or a matrix data row
AVAR2_BLOCK = "avar2-block"    # a line inside a linear mapping's { } block
AVAR2_HEADER = "avar2-header"  # the matrix `outputs` line
OTHER = "other"                # not understood (the parser warns or errors)

ITEM_KINDS = frozenset({
    FAMILY, SUFFIX, ELIDED_FALLBACK, PATH, LANG, AXIS, MAPPING, SOURCE_LINE, SKIP, SKIP_ENTRY, RULE,
    AVAR2_VAR, AVAR2_ROW, AVAR2_HEADER, INSTANCE, INSTANCE_FIELD,
})

# Section names (Line.section), as the parser keeps them
SECTION_NAMES = (
    "family", "axes", "axes_hidden", "sources", "instances", "rules",
    "avar2_vars", "avar2", "avar2_matrix",
)


@dataclass
class Line:
    """One line of the text

    `fields` maps a field name to its span; `values` to its text as written
    (quotes stripped from strings). Field names by kind:

    - family / suffix / elidedfallback / path: `value`; lang: `value`, `code.0`, `code.1` …
    - section: `keyword`; sources adds `order` (the brackets) and `order.0` …;
      instances adds `mode` (auto / off), rules `mode` (first / last)
    - axis: `name`, `tag`, `min`, `default`, `max`, `discrete`, `display_name`
      (`range` covers min..max or `discrete`)
    - mapping: `user`, `label`, `design`, `flag.elidable`
    - source: `name`, `coords` (with brackets) and `coord.0` … for positional
      coordinates, `coord.<axis>` for named ones (the axis as written);
      `flag.base`, `flag.sparse`, `flag.layer` (the flag through its value),
      `layer` (the value)
    - skip-entry: `value`
    - instance: `name` (quotes stripped from the value); instance-field: `key`,
      `value` and, for `location`, `location.<axis as written>` (the value)
    - rule: `pattern`, `target`, `conditions` (every group with its
      parentheses), `group.0` …, `condition.0` … (numbered across groups), `name`
    - avar2-var: `name` (with $), `value`
    - avar2-row: `name`, `inputs` (with brackets), `input.<axis>`,
      `output.<axis>` (value; for a matrix, the cell of that column)
    - avar2-header: `cell.<axis>`
    """

    number: int
    kind: str
    section: Optional[str]
    indent: str
    span: Optional[Span]                     # the code: no indentation, no comment
    comment: Optional[Span] = None           # trailing (or whole-line) comment
    fields: Dict[str, Span] = field(default_factory=dict)
    values: Dict[str, str] = field(default_factory=dict)
    tokens: List[Token] = field(default_factory=list, repr=False)
    parent: Optional[int] = None             # mapping -> its axis line, block -> its row
    leading: List[int] = field(default_factory=list)  # owned comment lines above
    owner: Optional[int] = None              # comment line -> the item it leads, if any
    end_line: int = 0                        # last line of the item (an avar2 { } block)
    raw: str = field(default="", repr=False)  # the line as written

    def set(self, name: str, span: Span, value: str) -> None:
        self.fields[name] = span
        self.values[name] = value

    def put(self, name: str, first: Token, last: Optional[Token] = None) -> None:
        """A field from `first` to `last`, its value the text as written"""
        last = last or first
        self.set(name, _join(first, last), self.raw[first.column: last.column + last.length])

    def text(self, name: str) -> str:
        """A field's text exactly as written (quotes included)"""
        span = self.fields[name]
        return self.raw[span.col: span.end_col]


@dataclass
class Structure:
    """Every line of a text, classified"""

    lines: List[Line]
    text_lines: List[str]
    indent_unit: str
    has_final_newline: bool

    def line(self, number: int) -> Optional[Line]:
        if 1 <= number <= len(self.lines):
            return self.lines[number - 1]
        return None

    def of_kind(self, kind: str, section: Optional[str] = None) -> List[Line]:
        return [
            ln for ln in self.lines
            if ln.kind == kind and (section is None or ln.section == section)
        ]

    def section_header(self, section: str) -> Optional[Line]:
        for ln in self.lines:
            if ln.kind == SECTION and ln.values.get("section") == section:
                return ln
        return None

    def children(self, parent: int) -> List[Line]:
        return [ln for ln in self.lines if ln.parent == parent]

    def owned_lines(self, number: int) -> Tuple[int, int]:
        """First and last line an item occupies with what it owns

        Its leading comments, the item, an avar2 block, and for an axis its
        mappings (with their leading comments).
        """
        item = self.lines[number - 1]
        first = item.leading[0] if item.leading else number
        last = max(item.end_line, number)
        for child in self.children(number):
            last = max(last, child.end_line, child.number)
        return first, last


# =============================================================================
# Building
# =============================================================================


def build(text: str) -> Structure:
    """Classify every line of `text`. Never raises"""
    text_lines = text.split("\n")
    tokenizer = syntax._Tokenizer()
    lines: List[Line] = []
    state = _State()

    for number, raw in enumerate(text_lines, 1):
        before = tokenizer.section
        try:
            tokens = tokenizer.line(raw, number)
        except Exception:  # never: the tokenizer does not raise; be safe anyway
            tokens = []
        section_after = tokenizer.section
        indent = raw[: len(raw) - len(raw.lstrip())]
        line = _classify(number, raw, indent, tokens, before, section_after, state)
        lines.append(line)

    _link(lines)
    has_final_newline = text.endswith("\n")
    return Structure(lines, text_lines, _indent_unit(lines), has_final_newline)


class _State:
    """What a line needs from the lines above it"""

    def __init__(self):
        self.axis_line: Optional[int] = None
        self.axis_indent: str = ""
        self.in_block: Optional[int] = None  # the avar2 row whose { } is open
        self.in_skip = False
        self.instance_line: Optional[int] = None  # the explicit instance block open


def _code_tokens(tokens: List[Token]) -> List[Token]:
    return [t for t in tokens if t.type != COMMENT]


def _classify(number, raw, indent, tokens, before, section, state) -> Line:
    code = _code_tokens(tokens)
    comment = next((_token_span(t) for t in tokens if t.type == COMMENT), None)
    span = _join(code[0], code[-1]) if code else None

    def make(kind, sec=section):
        return Line(number, kind, sec, indent, span, comment, tokens=tokens, end_line=number, raw=raw)

    if not code:
        return make(COMMENT_LINE if comment else BLANK, before)

    first = code[0]
    # Document and section lines start at column 0 (the tokenizer agrees)
    if first.column == 0 and first.type == KEYWORD:
        line = _header_line(make, code, section, state)
        if line is not None:
            return line
    if first.column == 0 and first.type in (TEXT, STRING):  # never: a value needs a keyword
        return make(OTHER)

    handler = {
        "axes": _axis_or_mapping,
        "axes_hidden": _axis_or_mapping,
        "sources": _source_line,
        "instances": _instances_line,
        "rules": _rule_line,
        "avar2_vars": _avar2_var_line,
        "avar2": _avar2_line,
        "avar2_matrix": _avar2_matrix_line,
    }.get(section)
    if handler is None:
        return make(OTHER)
    return handler(make, code, state)


def _header_line(make, code, section, state) -> Optional[Line]:
    first = code[0]
    word = first.text
    rest = code[1:]

    if word in ("family", "suffix", "elidedfallback", "path"):
        kind = {"family": FAMILY, "suffix": SUFFIX, "elidedfallback": ELIDED_FALLBACK, "path": PATH}[word]
        line = make(kind, None)
        if rest:
            line.put("value", rest[0], rest[-1])
            if len(rest) == 1 and rest[0].type == STRING:
                line.values["value"] = rest[0].text[1:-1] if len(rest[0].text) > 1 else ""
        return line
    if word == "lang":
        line = make(LANG, None)
        codes = [t for t in rest if t.type == TEXT]
        if rest:
            line.put("value", rest[0], rest[-1])
        for i, t in enumerate(codes):
            line.put(f"code.{i}", t)
        return line

    if section not in SECTION_NAMES or section == "family":
        return None
    state.axis_line = None
    state.in_block = None
    state.in_skip = False
    state.instance_line = None
    line = make(SECTION, section)
    line.values["section"] = section
    two_words = section in ("axes_hidden", "avar2_vars", "avar2_matrix") and len(code) > 1
    line.put("keyword", first, code[1] if two_words else first)
    if section == "sources":
        opening = next((t for t in rest if t.text == "["), None)
        closing = next((t for t in rest if t.text == "]"), None)
        if opening is not None:
            end = closing if closing is not None else rest[-1]
            line.put("order", opening, end)
            for i, t in enumerate(t for t in rest if t.type == AXIS_TAG):
                line.put(f"order.{i}", t)
    elif section == "instances":
        mode = next((t for t in rest if t.type == KEYWORD and t.text in ("auto", "off")), None)
        if mode is not None:
            line.put("mode", mode)
    elif section == "rules":
        mode = next((t for t in rest if t.type == KEYWORD and t.text in ("first", "last")), None)
        if mode is not None:
            line.put("mode", mode)
    elif section == "avar2_matrix" and len(code) > 2:
        name = code[2:]
        line.put("name", name[0], name[-1])
        line.values["name"] = line.values["name"].strip("\"'")
    return line


# -- axes ---------------------------------------------------------------------


def _axis_or_mapping(make, code, state) -> Line:
    is_axis = any(t.type in (AXIS_NAME, AXIS_TAG) for t in code) or any(
        t.type == KEYWORD and t.text in ("discrete", "binary") for t in code
    )
    if is_axis:
        line = make(AXIS)
        state.axis_line = line.number
        state.axis_indent = line.indent
        names = [t for t in code if t.type == AXIS_NAME]
        tag = next((t for t in code if t.type == AXIS_TAG), None)
        if names:
            line.put("name", names[0], names[-1])
        if tag is not None:
            line.put("tag", tag)
        elif names and len(names) == 1:
            # `weight 100:400:900`: a human name stands for the tag
            line.put("tag", names[0])
        discrete = next((t for t in code if t.type == KEYWORD and t.text in ("discrete", "binary")), None)
        if discrete is not None:
            line.put("discrete", discrete)
            line.put("range", discrete)
        else:
            parts = [t for t in code if t.type in (NUMBER, LABEL)]
            if len(parts) == 3:
                for key, t in zip(("min", "default", "max"), parts):
                    line.put(key, t)
            elif len(parts) == 2:
                line.put("min", parts[0])
                line.put("max", parts[1])
            if parts:
                line.put("range", parts[0], parts[-1])
        display = next((t for t in code if t.type == STRING), None)
        if display is not None:
            line.set("display_name", _token_span(display), display.text.strip("\"'"))
        return line

    line = make(MAPPING)
    if state.axis_line is not None and len(line.indent) > len(state.axis_indent):
        line.parent = state.axis_line
    arrow = next((i for i, t in enumerate(code) if t.type == OPERATOR and t.text == ">"), None)
    head = code if arrow is None else code[:arrow]
    tail = [] if arrow is None else code[arrow + 1:]
    words = [t for t in head if t.type in (NUMBER, LABEL)]
    if words and words[0].type == NUMBER and (len(words) > 1 or arrow is not None):
        line.put("user", words[0])
        words = words[1:]
    labels = [t for t in words if t.type == LABEL]
    if labels:
        line.put("label", labels[0], labels[-1])
    elif words and arrow is None:
        line.put("label", words[0])
    design = next((t for t in tail if t.type != FLAG), None)
    if design is not None:
        line.put("design", design)
    for t in code:
        if t.type == FLAG:
            line.put(f"flag.{t.text[1:]}", t)
    return line


# -- sources ------------------------------------------------------------------


def _source_line(make, code, state) -> Line:
    line = make(SOURCE_LINE)
    name = next((t for t in code if t.type == SOURCE), None)
    if name is not None:
        line.set("name", _token_span(name), name.text.strip("\"'"))

    i = 0
    while i < len(code):
        t = code[i]
        if t.type == FLAG:
            flag = t.text[1:]
            last = t
            if flag == "layer":
                j = i + 1
                if j < len(code) and code[j].type == PUNCTUATION and code[j].text == "=":
                    last = code[j]
                    j += 1
                if j < len(code) and code[j].type in (STRING, TEXT):
                    last = code[j]
                    line.set("layer", _token_span(code[j]), code[j].text.strip("\"'"))
                    j += 1
                line.put("flag.layer", t, last)
                i = j
                continue
            line.put(f"flag.{flag}", t)
        i += 1

    opening = next((k for k, t in enumerate(code) if t.type == PUNCTUATION and t.text == "["), None)
    if opening is not None:
        closing = next(
            (k for k in range(opening, len(code)) if code[k].type == PUNCTUATION and code[k].text == "]"),
            None,
        )
        inner = code[opening + 1: closing if closing is not None else len(code)]
        end = code[closing] if closing is not None else (inner[-1] if inner else code[opening])
        line.set("coords", _join(code[opening], end), "")
        position = 0
        for t in inner:
            if t.type == PUNCTUATION and t.text == ",":
                position += 1
            elif t.type in (NUMBER, LABEL):
                line.put(f"coord.{position}", t)
        line.values["coords"] = "positional"
        return line

    # Named: Source wght=400, CNTR=Sharp
    named = _assignment_fields(code)
    if named:
        first = min(named.values(), key=lambda pair: (pair[0].line, pair[0].col))[0]
        last = max(named.values(), key=lambda pair: (pair[1].end_line, pair[1].end_col))[1]
        line.set("coords", Span(first.line, first.col, last.end_line, last.end_col), "")
        line.values["coords"] = "named"
        for axis, (_, value_span, value) in ((a, (p[0], p[1], p[2])) for a, p in named.items()):
            line.set(f"coord.{axis}", value_span, value)
    return line


def _assignment_fields(code: List[Token]) -> Dict[str, Tuple[Span, Span, str]]:
    """`axis=value, …` -> axis: (span of the pair, span of the value, value)"""
    out = {}
    for k, t in enumerate(code):
        if t.type != AXIS_TAG:
            continue
        if k + 2 < len(code) and code[k + 1].text == "=":
            value = code[k + 2]
            out[t.text] = (_join(t, value), _token_span(value), value.text)
    return out


# -- instances ----------------------------------------------------------------


def _instances_line(make, code, state) -> Line:
    first = code[0]
    if first.type == KEYWORD and first.text == "skip":
        state.in_skip = True
        state.instance_line = None
        line = make(SKIP)
        line.put("keyword", first)
        return line
    if state.in_skip and all(t.type == LABEL for t in code):
        line = make(SKIP_ENTRY)
        line.put("value", code[0], code[-1])
        return line
    state.in_skip = False
    if (state.instance_line is not None and len(code) > 1 and first.type in (KEYWORD, UNKNOWN)
            and code[1].type == PUNCTUATION and code[1].text == ":"):
        line = make(INSTANCE_FIELD)
        line.parent = state.instance_line
        line.put("key", first)
        rest = code[2:]
        if rest:
            line.put("value", rest[0], rest[-1])
            if len(rest) == 1 and rest[0].type == STRING:
                line.values["value"] = rest[0].text[1:-1] if len(rest[0].text) > 1 else ""
        if first.text == "location":
            for k, t in enumerate(rest):
                if t.type == AXIS_TAG and k + 2 < len(rest) and rest[k + 1].text == "=":
                    line.put(f"location.{t.text}", rest[k + 2])
        return line
    if first.column > 0 and len(code) == 1 and first.type in (TEXT, STRING):
        line = make(INSTANCE)
        line.put("name", first)
        if first.type == STRING:
            line.values["name"] = first.text[1:-1] if len(first.text) > 1 else ""
        state.instance_line = line.number
        return line
    state.instance_line = None
    return make(OTHER)


# -- rules --------------------------------------------------------------------


def _rule_line(make, code, state) -> Line:
    line = make(RULE)
    arrow = next((i for i, t in enumerate(code) if t.type == OPERATOR and t.text == ">"), None)
    if arrow is None:
        line.kind = OTHER
        return line
    pattern = [t for t in code[:arrow] if t.type != PUNCTUATION]
    if pattern:
        line.put("pattern", pattern[0], pattern[-1])
    opening = next((k for k in range(arrow, len(code)) if code[k].text == "("), None)
    target = [t for t in code[arrow + 1: opening if opening is not None else len(code)] if t.type != STRING]
    if target:
        line.put("target", target[0], target[-1])
    if opening is not None:
        # condition groups `( … ) || ( … )`: `conditions` spans them all,
        # `group.G` each, `condition.N` numbers the conditions across groups
        groups: List[Tuple[int, Optional[int]]] = []
        k = opening
        while k is not None and k < len(code) and code[k].text == "(":
            depth, closing = 0, None
            for j in range(k, len(code)):
                if code[j].text == "(":
                    depth += 1
                elif code[j].text == ")":
                    depth -= 1
                    if depth == 0:
                        closing = j
                        break
            groups.append((k, closing))
            if closing is None or closing + 2 >= len(code) or code[closing + 1].text != "||":
                break
            k = closing + 2
        last_open, last_close = groups[-1]
        end = code[last_close] if last_close is not None else code[-1]
        line.set("conditions", _join(code[opening], end), "")
        number = 0
        for g, (start, stop) in enumerate(groups):
            line.set(f"group.{g}", _join(code[start], code[stop] if stop is not None else code[-1]), "")
            parts: List[List[Token]] = [[]]
            for t in code[start + 1: stop if stop is not None else len(code)]:
                if t.type == OPERATOR and t.text == "&&":
                    parts.append([])
                elif t.text in ("(", ")"):
                    continue
                else:
                    parts[-1].append(t)
            for part in (p for p in parts if p):
                line.put(f"condition.{number}", part[0], part[-1])
                number += 1
    name = next((t for t in reversed(code) if t.type == STRING), None)
    if name is not None:
        line.set("name", _token_span(name), name.text.strip("\"'"))
    return line


# -- avar2 --------------------------------------------------------------------


def _avar2_var_line(make, code, state) -> Line:
    line = make(AVAR2_VAR)
    var = next((t for t in code if t.type == VARIABLE), None)
    if var is not None:
        line.put("name", var)
    value = next((t for t in code if t.type == NUMBER), None)
    if value is not None:
        line.put("value", value)
    return line


def _avar2_inputs(line: Line, code: List[Token]) -> int:
    """Fields of `"name" [axis=value, …]`; the index after the closing bracket"""
    if code and code[0].type == STRING:
        line.set("name", _token_span(code[0]), code[0].text.strip("\"'"))
    opening = next((k for k, t in enumerate(code) if t.text == "["), None)
    if opening is None:
        return 0
    closing = next((k for k in range(opening, len(code)) if code[k].text == "]"), len(code) - 1)
    line.set("inputs", _join(code[opening], code[closing]), "")
    for axis, (pair, value, text) in _assignment_fields(code[opening:closing + 1]).items():
        line.set(f"input.{axis}", value, text)
    return closing + 1


def _avar2_line(make, code, state) -> Line:
    if state.in_block is not None:
        line = make(AVAR2_BLOCK)
        line.parent = state.in_block
        if code[0].text == "}":
            state.in_block = None
        for axis, (pair, value, text) in _assignment_fields(code).items():
            line.set(f"output.{axis}", value, text)
        return line
    line = make(AVAR2_ROW)
    after = _avar2_inputs(line, code)
    rest = code[after:]
    for axis, (pair, value, text) in _assignment_fields(rest).items():
        line.set(f"output.{axis}", value, text)
    if rest and rest[-1].text == "{":
        state.in_block = line.number
    return line


def _avar2_matrix_line(make, code, state) -> Line:
    first = code[0]
    if first.type == KEYWORD and first.text.startswith("outputs"):
        line = make(AVAR2_HEADER)
        state.matrix_columns = [t.text for t in code[1:] if t.type == AXIS_TAG]
        for t in code[1:]:
            if t.type == AXIS_TAG:
                line.put(f"cell.{t.text}", t)
        return line
    line = make(AVAR2_ROW)
    after = _avar2_inputs(line, code)
    columns = getattr(state, "matrix_columns", [])
    cells = code[after:]
    for axis, cell in zip(columns, cells):
        line.put(f"output.{axis}", cell)
    return line


# =============================================================================
# Links between lines
# =============================================================================


def _link(lines: List[Line]) -> None:
    """Leading comments, owners, and the end of avar2 blocks"""
    pending: List[int] = []
    for line in lines:
        if line.kind == COMMENT_LINE and line.number and _is_full_line_comment(line):
            pending.append(line.number)
            continue
        if line.kind == BLANK:
            pending = []
            continue
        if line.kind in ITEM_KINDS:
            line.leading = pending
            for number in pending:
                lines[number - 1].owner = line.number
        pending = []
        if line.kind == AVAR2_BLOCK and line.parent is not None:
            row = lines[line.parent - 1]
            row.end_line = max(row.end_line, line.number)


def _is_full_line_comment(line: Line) -> bool:
    return line.span is None and line.comment is not None


def _indent_unit(lines: List[Line]) -> str:
    """The document's indentation step, from its first indented item"""
    for line in lines:
        if line.kind in (AXIS, SOURCE_LINE, RULE, SKIP, AVAR2_ROW, AVAR2_VAR, AVAR2_HEADER) and line.indent:
            return line.indent
    return "    "
