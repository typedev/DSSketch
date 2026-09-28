"""
Translations of style and axis names, for the `lang` command.

`lang de, ru` in a sketch asks DSS -> DS to write every name it derives from
labels in those languages as well: instance style names (fvar subfamily,
nameID 17), STAT axis labels and axis names. The words come from
data/font-resources-translations.json, which a user can override with
`dssketch-data copy font-resources-translations.json`.

A style name is translated word by word, each word being a label, in the order
and with the elisions of the English name - the same way the English name is
built. A word without a translation stays in English.

Stdlib + the data loader only: this module is on the parse path.
"""

import re
from typing import Dict, List, Optional

_SECTIONS = ("WEIGHT_LANG_VARIANTS", "WIDTH_LANG_VARIANTS", "ITALICS_LANG_VARIANTS")

# Labels that name the same style as a dictionary entry under another word
_ALIASES = {
    "roman": "upright",
    "slant": "slanted",
    "extrablack": "black",  # no entry of its own; better than English
    "semicompressed": "extracondensed",
}

# Registered axis tags -> English axis name keys in the dictionary
_AXIS_KEYS = {
    "wght": "weight",
    "wdth": "width",
    "opsz": "opticalsize",
    "slnt": "slant",
    "ital": "italic",
}


def _norm(name: str) -> str:
    """Compare names ignoring case, spaces, hyphens and underscores:
    ExtraLight = Extralight = Extra Light = extra-light"""
    return re.sub(r"[\s_\-]", "", name).lower()


class Translations:
    """Lookup of label and axis-name translations"""

    _labels: Optional[Dict[str, Dict[str, str]]] = None
    _axes: Optional[Dict[str, Dict[str, str]]] = None

    @classmethod
    def _load(cls) -> None:
        if cls._labels is not None:
            return
        from ..config import load_translations

        data = load_translations() or {}
        cls._labels = {}
        for section in _SECTIONS:
            for name, by_language in (data.get(section) or {}).items():
                cls._labels[_norm(name)] = dict(by_language)
        cls._axes = {_norm(name): dict(v) for name, v in (data.get("AXIS_LANG_VARIANTS") or {}).items()}

    @classmethod
    def reset(cls) -> None:
        """Forget the loaded data (tests, or after editing the user override)"""
        cls._labels = cls._axes = None

    @classmethod
    def languages(cls) -> List[str]:
        """Every language the dictionary has at least one word for"""
        cls._load()
        found = set()
        for table in (cls._labels, cls._axes):
            for by_language in table.values():
                found.update(by_language)
        return sorted(found)

    @classmethod
    def label(cls, label: str, language: str) -> Optional[str]:
        """Translation of one label (one word of a style name), or None"""
        cls._load()
        key = _norm(label)
        entry = cls._labels.get(key)
        if entry is None and key in _ALIASES:
            entry = cls._labels.get(_ALIASES[key])
        if entry is None:
            entry = cls._labels.get(_standard_alias_target(label) or "")
        return entry.get(language) if entry else None

    @classmethod
    def axis_name(cls, tag: str, name: str, language: str) -> Optional[str]:
        """Translation of an axis name, by registered tag or by English name"""
        cls._load()
        for key in (_AXIS_KEYS.get(tag), _norm(name or ""), _norm(tag)):
            if key and key in cls._axes:
                return cls._axes[key].get(language)
        return None

    @classmethod
    def style_name(cls, style_name: str, language: str) -> "tuple[str, List[str]]":
        """Translate a style name word by word.

        Returns the translated name and the words that had no translation
        (kept in English). Words that are not labels at all, such as the
        `wght400` of an unlabeled axis, are kept and not reported.
        """
        words = style_name.split()
        out, missing = [], []
        for word in words:
            translated = cls.label(word, language)
            if translated is None:
                out.append(word)
                if not re.match(r"^[a-z]{4}-?\d", word, re.IGNORECASE):
                    missing.append(word)
            else:
                out.append(translated)
        return " ".join(out), missing


def _standard_alias_target(label: str) -> Optional[str]:
    """The canonical standard name an alias label stands for (Compressed ->
    UltraCondensed), normalized; None if the label is not a standard alias"""
    from .mappings import Standards

    Standards._load_mappings()
    for axis_type in ("weight", "width"):
        entry = (Standards.MAPPINGS.get(axis_type) or {}).get(label)
        if entry and "alias_of" in entry:
            return _norm(entry["alias_of"])
    return None


LANGUAGE_CODE = re.compile(r"^[a-zA-Z]{2,3}(-[A-Za-z0-9]{2,8})*$")
