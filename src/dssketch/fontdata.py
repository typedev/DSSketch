"""Font data from the host: glyph, layer, family and style names

DSSketch needs a few facts from the fonts a sketch names: the family name
(when the sketch has no `family` line), each source's style name, glyph names
(to expand wildcard rules and check rule targets) and layer names. By default
DSS -> DS reads them from the UFOs on disk with defcon (`DefconFontData`). A
host that has the fonts open — unsaved edits included — passes its own
`FontDataProvider` instead, to the conversion, `diagnose()`, `complete()` and
`Sketch.parse()`.

A source is named by its path relative to the .dssketch, as the DesignSpace
writes it: `path` + file name (`sources/Font-Bold.ufo`). Every method may
return None, which means "unknown", never "empty": a check that needs the
fact is then skipped.

`diagnose()` and `complete()` never touch the disk on their own: they use font
data only when a provider is given.

Light: stdlib + PyYAML; defcon is imported only when DefconFontData opens a UFO.
"""

from pathlib import Path
from typing import Collection, Dict, List, Optional, Tuple

try:  # Python 3.8+: typing.Protocol
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object

from .core.models import DSSDocument, DSSRule, DSSSource
from .utils.patterns import PatternMatcher


class FontDataProvider(Protocol):
    """What DSSketch asks the host about the fonts (None = unknown)

    Optional: `source_exists(source) -> Optional[bool]`; with it a missing
    source UFO is reported.
    """

    def family_name(self) -> Optional[str]:
        """The family name to use when the sketch has no `family` line
        (DefconFontData: the base source's familyName)"""

    def style_name(self, source: str) -> Optional[str]:
        """A source's style name (UFO styleName)"""

    def glyph_names(self, source: str) -> Optional[Collection[str]]:
        """The glyph names of a source's default layer"""

    def layer_names(self, source: str) -> Optional[Collection[str]]:
        """The layer names of a source's font"""


class FontData:
    """A provider that knows nothing; subclass and override what you know"""

    def family_name(self) -> Optional[str]:
        return None

    def style_name(self, source: str) -> Optional[str]:
        return None

    def glyph_names(self, source: str) -> Optional[Collection[str]]:
        return None

    def layer_names(self, source: str) -> Optional[Collection[str]]:
        return None

    def source_exists(self, source: str) -> Optional[bool]:
        return None


class DefconFontData(FontData):
    """Font data read from the UFOs on disk with defcon (the default for
    DSS -> DS). Each UFO is opened once"""

    def __init__(self, base_path: Optional[Path] = None, base_source: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else None
        #: the base source's path, for family_name()
        self.base_source = base_source
        self._fonts: Dict[str, object] = {}

    def path(self, source: str) -> Path:
        """Where a source's UFO is (as UFOGlyphExtractor resolves it)"""
        source_path = Path(source)
        if source_path.is_absolute() or not self.base_path:
            return source_path
        if source_path.parts and source_path.parts[0] == self.base_path.name:
            # "sources/X.ufo" with base_path ".../sources": avoid sources/sources
            candidate = self.base_path / Path(*source_path.parts[1:])
            if candidate.exists():
                return candidate
        return self.base_path / source_path

    def _font(self, source: str):
        if source not in self._fonts:
            font = None
            path = self.path(source)
            if path.is_dir():
                try:
                    from defcon import Font

                    font = Font(str(path))
                except Exception:
                    font = None
            self._fonts[source] = font
        return self._fonts[source]

    def source_exists(self, source: str) -> Optional[bool]:
        return self.path(source).is_dir()

    def family_name(self) -> Optional[str]:
        if not self.base_source:
            return None
        font = self._font(self.base_source)
        return font.info.familyName if font is not None else None

    def style_name(self, source: str) -> Optional[str]:
        font = self._font(source)
        return font.info.styleName if font is not None else None

    def glyph_names(self, source: str) -> Optional[Collection[str]]:
        font = self._font(source)
        return set(font.keys()) if font is not None else None

    def layer_names(self, source: str) -> Optional[Collection[str]]:
        font = self._font(source)
        return list(font.layers.layerOrder) if font is not None else None


def source_path(doc: DSSDocument, source: DSSSource) -> str:
    """A source as the provider is asked about it: `path` + file name"""
    if doc.path:
        path = doc.path.replace("\\", "/")
        return path + ("" if path.endswith("/") else "/") + source.filename
    return source.filename


def _call(provider, method: str, *args):
    """A provider call that never raises (a host bug must not break a parse)"""
    if provider is None:
        return None
    fn = getattr(provider, method, None)
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception:
        return None


def default_master_glyphs(provider, doc: DSSDocument) -> Optional[set]:
    """Glyph names of the default master(s) (the @base sources; one per
    discrete value), or None when unknown"""
    names = None
    for source in doc.sources:
        if not source.is_base:
            continue
        glyphs = _call(provider, "glyph_names", source_path(doc, source))
        if glyphs is not None:
            names = (names or set()) | set(glyphs)
    return names


# =============================================================================
# Rules
# =============================================================================


def expand_rule(rule: DSSRule, glyph_names: Collection[str]) -> List[Tuple[str, str, bool]]:
    """What a rule substitutes in a font with these glyphs

    (source glyph, target glyph, target exists), sorted by source glyph. A
    pattern (`dollar*`, `*`) expands to the glyphs it matches; a suffix target
    (`.rvrn`) is appended to each (a glyph that already ends with it is left
    out). A plain glyph name in the pattern is listed even when the font lacks
    it. Rules without a pattern (from DS -> DSS) list their substitutions.
    """
    glyphs = set(glyph_names)
    if not rule.pattern or not rule.to_pattern:
        return [(a, b, b in glyphs) for a, b in rule.substitutions]
    words = rule.pattern.split()
    matched = set(PatternMatcher.find_matching_glyphs(words, glyphs))
    matched |= {w for w in words if "*" not in w}
    target = rule.to_pattern
    out = []
    for glyph in sorted(matched):
        if target.startswith("."):
            if glyph.endswith(target):
                continue
            new = glyph + target
        else:
            new = target
        out.append((glyph, new, new in glyphs))
    return out


# =============================================================================
# Checks for diagnose()
# =============================================================================


def check(doc: DSSDocument, provider) -> List[Tuple[str, str, Optional[int]]]:
    """(severity, message, line) for what the font data contradicts: a source
    UFO that does not exist, a layer the UFO lacks, a rule naming a glyph the
    default master lacks or matching nothing. Never raises"""
    if provider is None:
        return []
    out = []
    try:
        for source in doc.sources:
            path = source_path(doc, source)
            if _call(provider, "source_exists", path) is False:
                out.append(("warning", f"Source UFO '{path}' not found", source.line))
                continue
            if source.layer:
                layers = _call(provider, "layer_names", path)
                if layers is not None and source.layer not in layers:
                    out.append((
                        "warning",
                        f"Source '{source.name}': layer '{source.layer}' not found in '{path}'. "
                        f"Layers: {', '.join(layers)}",
                        source.line,
                    ))
        glyphs = default_master_glyphs(provider, doc)
        if glyphs is not None:
            for rule in doc.rules:
                out.extend(_check_rule(rule, glyphs))
    except Exception:
        pass
    return out


def _check_rule(rule: DSSRule, glyphs: set) -> List[Tuple[str, str, Optional[int]]]:
    out = []
    # the rule name in double quotes: a message is placed at the first word it
    # quotes in single ones, and that should be the glyph
    label = f'Rule "{rule.name}"' if rule.name else "Rule"
    if not rule.pattern or not rule.to_pattern:
        # an explicit rule (`dollar > dollar.alt`): its glyph pairs
        for source, target in rule.substitutions:
            if source not in glyphs:
                out.append(("warning", f"{label}: glyph '{source}' is not in the default master", rule.line))
            if target not in glyphs:
                out.append(("warning", f"{label}: target glyph '{target}' is not in the default master", rule.line))
        return out
    words = rule.pattern.split()
    plain = [w for w in words if "*" not in w]
    for word in plain:
        if word not in glyphs:
            out.append(("warning", f"{label}: glyph '{word}' is not in the default master", rule.line))
    expanded = expand_rule(rule, glyphs)
    if rule.to_pattern and not rule.to_pattern.startswith("."):
        if rule.to_pattern not in glyphs:
            out.append(("warning", f"{label}: target glyph '{rule.to_pattern}' is not in the default master", rule.line))
        return out
    present = [e for e in expanded if e[0] in glyphs]
    if words and len(plain) < len(words) and not any(e[2] for e in present):
        out.append(("warning", f"{label}: matches no glyph whose target exists; it would be left out", rule.line))
    for source, target, exists in present:
        if source in plain and not exists:
            out.append(("warning", f"{label}: target glyph '{target}' is not in the default master", rule.line))
    return out
