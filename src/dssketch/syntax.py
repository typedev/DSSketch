"""
Syntax support for editors: tokens for highlighting, diagnostics with positions.

The knowledge of the DSSketch syntax lives here, next to the parser, so an editor
only maps token types to styles. Stdlib only (plus what the parser loads): an
editor calls this on every keystroke.

Token types are a contract: editors key their styles on them, so a type is never
renamed or removed, only added.

The tokenizer follows the parser's own decisions, not an idealised grammar: a
comment starts at the first `#` on the line (quotes included), section keywords
count only at the start of a line, and the section checks run in the parser's
order.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .utils.dss_validator import DSSValidator

# =============================================================================
# Token types (append-only)
# =============================================================================

KEYWORD = "keyword"          # family, axes, hidden, sources, auto, skip, discrete, outputs …
AXIS_NAME = "axis-name"      # weight, CONTRAST in an axis definition
AXIS_TAG = "axis-tag"        # wght; also every reference to an axis
LABEL = "label"              # Regular, Condensed, Italic …
NUMBER = "number"            # 400, -20, 0.5
SOURCE = "source"            # a source's file name or path
GLYPH = "glyph"              # rule pattern and target: dollar, A*, .rvrn
TEXT = "text"                # free values: family name, path, suffix, lang codes
STRING = "string"            # anything in quotes
FLAG = "flag"                # @base, @sparse, @elidable, @layer
VARIABLE = "variable"        # avar2 $XOUC, and $ (axis default)
OPERATOR = "operator"        # > >= <= == &&
PUNCTUATION = "punctuation"  # [ ] ( ) { } , : = and - (no value, avar2 matrix)
COMMENT = "comment"          # from the first # to the end of the line
UNKNOWN = "unknown"          # outside any section, or not understood

TOKEN_TYPES = (
    KEYWORD, AXIS_NAME, AXIS_TAG, LABEL, NUMBER, SOURCE, GLYPH, TEXT, STRING,
    FLAG, VARIABLE, OPERATOR, PUNCTUATION, COMMENT, UNKNOWN,
)


@dataclass(frozen=True)
class Token:
    """A span of one line. `column` counts characters from 0; `line` from 1."""

    line: int
    column: int
    length: int
    type: str
    text: str


@dataclass(frozen=True)
class Diagnostic:
    """A parser message placed in the text.

    `line` is None for a message about the document as a whole (no base
    source, no axes, no family).
    `end_column` is exclusive.
    """

    severity: str  # "error" | "warning"
    message: str
    line: Optional[int]
    column: int = 0
    end_column: int = 0


# =============================================================================
# Tokenizer
# =============================================================================

_ATOM = re.compile(
    r"""
    (?P<string>"[^"]*"?|'[^']*'?)
    |(?P<flag>@[A-Za-z_]+)
    |(?P<variable>\$[A-Za-z0-9_]*)
    |(?P<operator>>=|<=|==|&&|[<>])
    |(?P<punct>[\[\](){},:=])
    |(?P<word>[^\s\[\](){},:="'@$<>=&][^\s\[\](){},:="@$<>=&]*)
    |(?P<other>\S)
    """,
    re.VERBOSE,
)

_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")

# Human-readable names the parser accepts for registered axes
_AXIS_ALIASES = {
    "wght": "weight",
    "wdth": "width",
    "ital": "italic",
    "slnt": "slant",
    "opsz": "optical",
}


@dataclass
class _Atom:
    kind: str  # string, flag, variable, operator, punct, word, other
    start: int
    end: int
    text: str


def _atoms(code: str) -> List[_Atom]:
    return [
        _Atom(m.lastgroup, m.start(), m.end(), m.group())
        for m in _ATOM.finditer(code)
    ]


def _is_number(text: str) -> bool:
    return bool(_NUMBER.match(text))


def _value_type(text: str) -> str:
    """A coordinate, range end or condition value: a number or a label"""
    return NUMBER if _is_number(text) else LABEL


def _default_type(atom: _Atom) -> str:
    """The type an atom has wherever its section gives it no other meaning"""
    return {
        "string": STRING,
        "flag": FLAG,
        "variable": VARIABLE,
        "operator": OPERATOR,
        "punct": PUNCTUATION,
    }.get(atom.kind, UNKNOWN)


class _Tokenizer:
    def __init__(self):
        self.section = None
        self.in_skip = False
        # Every name and tag of a declared axis, lower case: rule conditions
        # and avar2 refer to axes by either
        self.axis_refs: Set[str] = set(_AXIS_ALIASES) | set(_AXIS_ALIASES.values())

    # -- one line -------------------------------------------------------------

    def line(self, raw: str, line_no: int) -> List[Token]:
        hash_at = raw.find("#")
        code = raw if hash_at < 0 else raw[:hash_at]
        out: List[Tuple[int, int, str]] = []  # (start, end, type)

        if code.strip():
            atoms = _atoms(code)
            # The parser keeps the indentation for its section checks
            # The parser's section checks run on the normalized line
            out = self._classify(DSSValidator.normalize_whitespace(code), atoms)

        if hash_at >= 0:
            comment_end = len(raw.rstrip())
            out.append((hash_at, comment_end, COMMENT))

        return [
            Token(line_no, start, end - start, kind, raw[start:end])
            for start, end, kind in sorted(out)
            if end > start
        ]

    # -- sections ---------------------------------------------------------------

    def _classify(self, line: str, atoms: List[_Atom]):
        header = self._header(line, atoms)
        if header is not None:
            return header

        handler = {
            "axes_hidden": self._axis_line,
            "axes": self._axis_line,
            "sources": self._source_line,
            "instances": self._instance_line,
            "rules": self._rule_line,
            "avar2_vars": self._avar2_line,
            "avar2": self._avar2_line,
            "avar2_matrix": self._avar2_matrix_line,
        }.get(self.section)
        if handler is None:
            # Outside any section the parser only checks for keyword typos
            return [(a.start, a.end, UNKNOWN) for a in atoms]
        if handler == self._instance_line:
            return handler(line, atoms)
        return handler(atoms)

    def _header(self, line: str, atoms: List[_Atom]):
        """Section and document keywords, in the parser's order (`_parse_line`)"""
        first = atoms[0]

        def keywords(*words):
            return [
                (a.start, a.end, KEYWORD if a.kind == "word" and a.text in words else _default_type(a))
                for a in atoms
            ]

        def keyword_then_value():
            rest = atoms[1:]
            out = [(first.start, first.end, KEYWORD)]
            if len(rest) == 1 and rest[0].kind == "string":
                out.append((rest[0].start, rest[0].end, STRING))
            elif rest:
                out.append((rest[0].start, rest[-1].end, TEXT))
            return out

        if line.startswith("family ") or line == "family":
            self.section = "family"
            return keyword_then_value()
        if line.startswith("suffix ") or line.startswith("path "):
            return keyword_then_value()
        if line.startswith("lang ") or line == "lang":
            return [(first.start, first.end, KEYWORD)] + [
                (a.start, a.end, TEXT if a.kind == "word" else _default_type(a)) for a in atoms[1:]
            ]
        if line == "axes hidden" or line.startswith("axes hidden "):
            self.section = "axes_hidden"
            return keywords("axes", "hidden")
        if line == "axes" or line.startswith("axes "):
            self.section = "axes"
            return keywords("axes")
        if line == "sources" or line.startswith("sources "):
            self.section = "sources"
            out = [(first.start, first.end, KEYWORD)]
            for a in atoms[1:]:
                out.append((a.start, a.end, AXIS_TAG if a.kind == "word" else _default_type(a)))
            return out
        if line == "instances" or line.startswith("instances "):
            self.section = "instances"
            self.in_skip = False
            return keywords("instances", "auto", "off")
        if line == "rules" or line.startswith("rules "):
            self.section = "rules"
            self.in_skip = False
            return keywords("rules")
        if line == "avar2 vars" or line.startswith("avar2 vars "):
            self.section = "avar2_vars"
            return keywords("avar2", "vars")
        if line.startswith("avar2 matrix"):
            self.section = "avar2_matrix"
            # avar2 matrix "name", or a plain name
            return keywords("avar2", "matrix")[:2] + [
                (a.start, a.end, TEXT if a.kind == "word" else _default_type(a)) for a in atoms[2:]
            ]
        if line == "avar2" or (line.startswith("avar2 ") and "vars" not in line and "matrix" not in line):
            self.section = "avar2"
            return keywords("avar2")
        return None

    # -- axes -------------------------------------------------------------------

    def _axis_line(self, atoms: List[_Atom]):
        body = list(atoms)
        out = []
        # A display name closes an axis definition: opsz 8:14:144 "Optical size"
        if body and body[-1].kind == "string":
            display = body.pop()
            out.append((display.start, display.end, STRING))

        has_map_arrow = any(a.kind == "operator" and a.text == ">" for a in body)
        range_at = None
        if not has_map_arrow and body:
            if body[-1].kind == "word" and body[-1].text in ("discrete", "binary"):
                range_at = len(body) - 1
            else:
                colons = [i for i, a in enumerate(body) if a.kind == "punct" and a.text == ":"]
                if colons and colons[0] > 0:
                    range_at = colons[0] - 1

        if range_at is None:
            return out + self._mapping_line(body)

        head = body[:range_at]
        for i, a in enumerate(head):
            if a.kind != "word":
                out.append((a.start, a.end, _default_type(a)))
                continue
            last = i == len(head) - 1
            kind = AXIS_TAG if last and len(a.text) == 4 else AXIS_NAME
            out.append((a.start, a.end, kind))
            self.axis_refs.add(a.text.lower())
        for a in body[range_at:]:
            if a.kind == "word":
                kind = KEYWORD if a.text in ("discrete", "binary") else _value_type(a.text)
                out.append((a.start, a.end, kind))
            else:
                out.append((a.start, a.end, _default_type(a)))
        return out

    def _mapping_line(self, atoms: List[_Atom]):
        """`300 Light > 295 @elidable`, `Light > 295`, `100 > 100`, `Upright @elidable`"""
        out = []
        after_arrow = False
        first_word = True
        for a in atoms:
            if a.kind == "operator" and a.text == ">":
                after_arrow = True
                out.append((a.start, a.end, OPERATOR))
            elif a.kind == "word":
                if after_arrow:
                    kind = NUMBER if _is_number(a.text) else UNKNOWN
                elif first_word and _is_number(a.text):
                    kind = NUMBER
                else:
                    kind = LABEL
                first_word = False
                out.append((a.start, a.end, kind))
            else:
                out.append((a.start, a.end, _default_type(a)))
        return out

    # -- sources ----------------------------------------------------------------

    def _source_line(self, atoms: List[_Atom]):
        out = []
        rest = []
        i = 0
        while i < len(atoms):
            a = atoms[i]
            if a.kind == "flag":
                out.append((a.start, a.end, FLAG))
                if a.text == "@layer":
                    # @layer="name", @layer 'name', @layer=name
                    j = i + 1
                    if j < len(atoms) and atoms[j].kind == "punct" and atoms[j].text == "=":
                        out.append((atoms[j].start, atoms[j].end, PUNCTUATION))
                        j += 1
                    if j < len(atoms) and atoms[j].kind in ("string", "word"):
                        kind = STRING if atoms[j].kind == "string" else TEXT
                        out.append((atoms[j].start, atoms[j].end, kind))
                        j += 1
                    i = j
                    continue
            else:
                rest.append(a)
            i += 1

        open_at = next((k for k, a in enumerate(rest) if a.kind == "punct" and a.text == "["), None)
        if open_at is not None:
            name = rest[:open_at]
            if name:
                out.append((name[0].start, name[-1].end, SOURCE))
            closed = False
            for a in rest[open_at:]:
                if closed:
                    out.append((a.start, a.end, UNKNOWN))
                elif a.kind == "word":
                    out.append((a.start, a.end, _value_type(a.text)))
                else:
                    out.append((a.start, a.end, _default_type(a)))
                    closed = a.kind == "punct" and a.text == "]"
            return out

        # Named: Source wght=400, wdth=Bold
        eq_at = next((k for k, a in enumerate(rest) if a.kind == "punct" and a.text == "="), None)
        if eq_at is not None and eq_at >= 2:
            name = rest[: eq_at - 1]
            out.append((name[0].start, name[-1].end, SOURCE))
            return out + self._assignments(rest[eq_at - 1 :])

        if rest:
            out.append((rest[0].start, rest[-1].end, SOURCE))
        return out

    def _assignments(self, atoms: List[_Atom]):
        """`axis=value, axis=value` (named sources, avar2 inputs and outputs)"""
        out = []
        for k, a in enumerate(atoms):
            if a.kind == "word":
                nxt = atoms[k + 1] if k + 1 < len(atoms) else None
                if nxt is not None and nxt.kind == "punct" and nxt.text == "=":
                    out.append((a.start, a.end, AXIS_TAG))
                elif a.text == "-":
                    out.append((a.start, a.end, PUNCTUATION))
                else:
                    out.append((a.start, a.end, _value_type(a.text)))
            else:
                out.append((a.start, a.end, _default_type(a)))
        return out

    # -- instances --------------------------------------------------------------

    def _instance_line(self, line: str, atoms: List[_Atom]):
        if line.strip().startswith("skip"):
            self.in_skip = True
            return [(a.start, a.end, KEYWORD if k == 0 else UNKNOWN) for k, a in enumerate(atoms)]
        if self.in_skip:
            if line.startswith("    "):
                return [
                    (a.start, a.end, LABEL if a.kind == "word" else _default_type(a)) for a in atoms
                ]
            self.in_skip = False
        if line.strip() == "auto":
            return [(atoms[0].start, atoms[0].end, KEYWORD)]
        # An explicit instance: the parser warns and ignores it
        return [(a.start, a.end, UNKNOWN) for a in atoms]

    # -- rules ------------------------------------------------------------------

    def _rule_line(self, atoms: List[_Atom]):
        arrow = next(
            (k for k, a in enumerate(atoms) if a.kind == "operator" and a.text == ">"), None
        )
        if arrow is None:
            return [(a.start, a.end, UNKNOWN) for a in atoms]

        out = []
        depth = 0
        after_condition = False
        for k, a in enumerate(atoms):
            if k == arrow:
                out.append((a.start, a.end, OPERATOR))
            elif a.kind == "punct" and a.text == "(":
                depth += 1
                out.append((a.start, a.end, PUNCTUATION))
            elif a.kind == "punct" and a.text == ")":
                depth -= 1
                after_condition = depth <= 0
                out.append((a.start, a.end, PUNCTUATION))
            elif a.kind == "word":
                if depth > 0:
                    if _is_number(a.text):
                        kind = NUMBER
                    elif a.text.lower() in self.axis_refs:
                        kind = AXIS_TAG
                    else:
                        kind = LABEL
                elif after_condition:
                    kind = UNKNOWN
                else:
                    kind = GLYPH
                out.append((a.start, a.end, kind))
            else:
                out.append((a.start, a.end, _default_type(a)))
        return out

    # -- avar2 ------------------------------------------------------------------

    def _avar2_line(self, atoms: List[_Atom]):
        """Linear mappings, `{ }` blocks and `$name = value`"""
        return self._assignments(atoms)

    def _avar2_matrix_line(self, atoms: List[_Atom]):
        first = atoms[0]
        if first.kind == "word" and first.text.startswith("outputs"):
            return [(first.start, first.end, KEYWORD)] + [
                (a.start, a.end, AXIS_TAG if a.kind == "word" else _default_type(a))
                for a in atoms[1:]
            ]
        return self._assignments(atoms)


def tokenize(text: str) -> List[Token]:
    """Split a .dssketch text into typed tokens, line by line.

    Every non-blank character belongs to exactly one token. Tokens come in
    order: by line, then by column.
    """
    tokenizer = _Tokenizer()
    tokens: List[Token] = []
    for line_no, raw in enumerate(text.split("\n"), 1):
        tokens.extend(tokenizer.line(raw, line_no))
    return tokens


# =============================================================================
# Diagnostics
# =============================================================================

_QUOTED = re.compile(r"'([^']+)'")


def _span(message: str, line_tokens: List[Token], raw: str) -> Tuple[int, int]:
    """Columns of the part of the line a message is about.

    A message that quotes something ('Bolt') points at the token with that
    text, a source name only when nothing else matches; otherwise the whole
    line, without indentation and comment.
    """
    matches = [
        token
        for quoted in _QUOTED.findall(message)
        for token in line_tokens
        if token.type != COMMENT
        and (
            token.text.strip("\"'") == quoted
            # "Axis 'weight'" on a line that writes the tag
            or token.type == AXIS_TAG and _AXIS_ALIASES.get(token.text.lower()) == quoted.lower()
        )
    ]
    # "Invalid coordinate in source 'X': Label 'Bolt' not found" is about the
    # label: the source name is only context
    matches.sort(key=lambda token: token.type == SOURCE)
    if matches:
        return matches[0].column, matches[0].column + matches[0].length
    code = [t for t in line_tokens if t.type != COMMENT]
    if code:
        return code[0].column, code[-1].column + code[-1].length
    stripped = raw.strip()
    start = raw.find(stripped) if stripped else 0
    return start, start + len(stripped)


def diagnose(text: str) -> List[Diagnostic]:
    """Every error and warning the parser finds in a .dssketch text.

    Never raises: a line that fails becomes an error and parsing goes on, so an
    editor gets all problems at once. A message about an axis, mapping,
    source, rule or avar2 mapping is placed on the line that declares it, and
    the result is in text order. What belongs to no line (no base source, no
    axes, no family) comes last with `line=None`.
    """
    from .parsers.dss_parser import DSSParser
    from .utils.dss_validator import DSSValidationError

    parser = DSSParser(strict_mode=False, recover=True)
    crash = None
    try:
        parser.parse(text)
    except Exception as e:  # critical errors are already in validator.errors
        if not isinstance(e.__cause__, DSSValidationError):
            crash = e

    lines = text.split("\n")
    by_line: Dict[int, List[Token]] = {}
    for token in tokenize(text):
        by_line.setdefault(token.line, []).append(token)

    def placed(severity: str, message: str, line_no: Optional[int]) -> Diagnostic:
        if line_no is None or not 1 <= line_no <= len(lines):
            return Diagnostic(severity, message, None)
        column, end = _span(message, by_line.get(line_no, []), lines[line_no - 1])
        return Diagnostic(severity, message, line_no, column, end)

    result = [placed(*entry) for entry in parser.line_messages]

    # validate_document() keeps the line messages first; the rest it found in
    # the document, each placed at the axis, mapping or source it is about.
    # If it failed half-way the lists hold only its own messages
    validator = parser.validator
    n_errors, n_warnings = parser.line_phase_counts
    line_errors = [m for s, m, _ in parser.line_messages if s == "error"]
    line_warnings = [m for s, m, _ in parser.line_messages if s == "warning"]
    for severity, messages, n, line_messages, at_lines in (
        ("error", validator.errors, n_errors, line_errors, validator.document_error_lines),
        ("warning", validator.warnings, n_warnings, line_warnings, validator.document_warning_lines),
    ):
        found = messages[n:] if messages[:n] == line_messages else messages
        if len(at_lines) != len(found):
            at_lines = [None] * len(found)
        result.extend(placed(severity, m, line) for m, line in zip(found, at_lines))

    # In text order; what has no place (no base source, no axes …) comes last
    result.sort(key=lambda d: (d.line is None, d.line or 0, d.column))
    if crash is not None:
        result.append(Diagnostic("error", str(crash), None))
    return result
