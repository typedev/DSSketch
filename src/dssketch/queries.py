"""What a sketch means, in numbers: for an editor's panels (1.5.1)

All of these work on a parsed (possibly recovered) document, without UFOs and
without fontTools, and never raise: an axis, label or value they cannot
resolve gives None (or is left out). Axes are named as the DesignSpace names
them — the display name, else the name (`"Weight"`, `"weight"`, `"opsz"`) —
which is what fontTools and an interpolator use; a query also accepts the tag
or the sketch's own name for an axis.

- `user_to_design(axis, value)` / `design_to_user(axis, value)`: the axis map
  (piecewise linear, as fontTools); `value` may be a label
- `source_locations()`: every source's location in user and design space
- `rule_regions()`: each rule's region as design-space intervals per axis
- `substitutions_at(location, glyph_names)`: what the rules swap there
- `instances()`: what `instances auto` generates, with what `skip` removed
- `outline()`: the tree of sections and items, for a structure panel
- `hover(line, column)`: a line of explanation for what is under the cursor

`Sketch` has them as methods (on its cached parse); the functions here take
a `Sketch` or a text. Light: stdlib + PyYAML.
"""

from dataclasses import dataclass
from typing import Collection, Dict, List, Mapping, Optional, Tuple, Union

from .core.instances import dss_axis_name, instance_axis_order, plan_instances, spec_from_dss_axis
from .core.models import DSSAxis, DSSDocument


@dataclass(frozen=True)
class SourceLocation:
    """A source and where it sits"""

    key: "object"  # sketch.SourceKey(filename, layer)
    name: str
    user_location: Dict[str, float]  # axis name -> user value
    design_location: Dict[str, float]  # axis name -> design value
    is_base: bool = False
    line: Optional[int] = None


@dataclass(frozen=True)
class RuleRegion:
    """Where a rule applies: per axis it names, the design-space interval
    (an open end is the axis's end). Axes it does not name are unconstrained.
    A rule with `||` groups applies in `region` or in any of `alternatives`"""

    index: int  # position in the rules section (from 0)
    name: str
    region: Dict[str, Tuple[float, float]]  # axis name -> (minimum, maximum), design space
    line: Optional[int] = None
    alternatives: Tuple[Dict[str, Tuple[float, float]], ...] = ()  # the further `||` groups


@dataclass(frozen=True)
class InstanceInfo:
    """One instance `instances auto` generates, one a `skip` entry removed, or
    an explicit instance block (`explicit`, after the generated ones)"""

    index: Optional[int]  # position among the DesignSpace's instances; None when skipped
    name: str  # what a `skip` entry writes to remove it (= style_name); a block's name
    style_name: str
    family_name: Optional[str]  # None when neither the sketch nor the font data says
    user_location: Dict[str, float]  # axis name -> user value (visible axes)
    design_location: Dict[str, float]  # axis name -> design value, as the DesignSpace has it
    skipped: bool = False
    skip_entry: Optional[str] = None  # the `skip` entry that removed it
    skip_span: Optional["object"] = None  # structure.Span of that entry
    group: Tuple[str, ...] = ()  # its labels on discrete axes (("Italic",)): one per VF
    explicit: bool = False  # an explicit instance block
    span: Optional["object"] = None  # structure.Span of the block's name line


# -- axes -----------------------------------------------------------------------


def all_axes(doc: DSSDocument) -> List[DSSAxis]:
    return list(doc.axes) + list(doc.hidden_axes)


def find_axis(doc: DSSDocument, key) -> Optional[DSSAxis]:
    """The axis a key names: DesignSpace name, tag or the sketch's name"""
    if not isinstance(key, str):
        return None
    axes = all_axes(doc)
    for axis in axes:
        if key in (axis.tag, axis.name, axis.display_name):
            return axis
    lowered = key.lower()
    for axis in axes:
        if lowered in (axis.tag.lower(), axis.name.lower(), (axis.display_name or "").lower()):
            return axis
    return None


def axis_name(axis: DSSAxis) -> str:
    """The name the DesignSpace gives the axis"""
    return dss_axis_name(axis)


def _label(axis: DSSAxis, value: str):
    for mapping in axis.mappings:
        if mapping.label == value:
            return mapping
    return None


def _number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _user_to_design(doc: DSSDocument, axis_key, value) -> Optional[float]:
    """A user value (or label) on an axis, in design space"""
    try:
        axis = find_axis(doc, axis_key)
        if axis is None:
            return None
        number = _number(value)
        if number is None:
            mapping = _label(axis, value) if isinstance(value, str) else None
            return None if mapping is None else mapping.design_value
        return axis.get_design_value(number)
    except Exception:
        return None


def _design_to_user(doc: DSSDocument, axis_key, value) -> Optional[float]:
    """A design value (or label) on an axis, in user space"""
    try:
        axis = find_axis(doc, axis_key)
        if axis is None:
            return None
        number = _number(value)
        if number is None:
            mapping = _label(axis, value) if isinstance(value, str) else None
            return None if mapping is None else mapping.user_value
        return axis.get_user_value(number)
    except Exception:
        return None


def _design_range(axis: DSSAxis) -> Tuple[float, float]:
    ends = axis.get_design_value(axis.minimum), axis.get_design_value(axis.maximum)
    return min(ends), max(ends)


# -- sources --------------------------------------------------------------------


def _source_locations(doc: DSSDocument) -> List[SourceLocation]:
    """Every source, in order, with its location on every axis (an axis it does
    not write sits at its default)"""
    from .sketch import SourceKey

    out = []
    try:
        axes = all_axes(doc)
        for source in doc.sources:
            design = {axis_name(axis): axis.design_default for axis in axes}
            for key, value in source.location.items():
                axis = find_axis(doc, key)
                if axis is not None and value is not None:
                    design[axis_name(axis)] = value
            user = {}
            for axis in axes:
                name = axis_name(axis)
                user[name] = axis.default if design[name] == axis.design_default else axis.get_user_value(design[name])
            out.append(SourceLocation(
                key=SourceKey(source.filename, source.layer),
                name=source.name,
                user_location=user,
                design_location=design,
                is_base=source.is_base,
                line=source.line,
            ))
    except Exception:
        pass
    return out


# -- rules ----------------------------------------------------------------------


def _region(doc: DSSDocument, rule, conditions=None) -> Dict[str, Tuple[float, float]]:
    """The region of one condition group (the first when none is given)"""
    region: Dict[str, Tuple[float, float]] = {}
    for condition in (rule.conditions if conditions is None else conditions) or ():
        axis = find_axis(doc, condition.get("axis"))
        if axis is None:
            continue
        low, high = _design_range(axis)
        minimum = condition.get("minimum")
        maximum = condition.get("maximum")
        minimum = low if minimum is None else minimum
        maximum = high if maximum is None else maximum
        name = axis_name(axis)
        if name in region:  # two conditions on one axis: both hold
            minimum = max(minimum, region[name][0])
            maximum = min(maximum, region[name][1])
        region[name] = (minimum, maximum)
    return region


def _rule_regions(doc: DSSDocument) -> List[RuleRegion]:
    out = []
    try:
        for index, rule in enumerate(doc.rules):
            out.append(RuleRegion(index, rule.name or "", _region(doc, rule), rule.line,
                                  tuple(_region(doc, rule, group) for group in rule.alternatives)))
    except Exception:
        pass
    return out


def _rule_pairs(rule, glyph_names: Optional[Collection[str]]) -> List[Tuple[str, str]]:
    """The substitutions DSS -> DS writes for a rule: a pattern rule's pairs
    whose glyph and target the font has, an explicit rule's as written"""
    if not rule.pattern or not rule.to_pattern:
        return list(rule.substitutions)
    if glyph_names is None:
        return []
    from .fontdata import expand_rule

    glyphs = set(glyph_names)
    return [(a, b) for a, b, exists in expand_rule(rule, glyphs) if exists and a in glyphs]


def _substitutions_at(
    doc: DSSDocument,
    location: Mapping[str, float],
    glyph_names: Optional[Collection[str]] = None,
    space: str = "design",
) -> Dict[str, str]:
    """{glyph: replacement} the rules make at a location

    `location` is keyed by axis (any name or the tag); an axis left out is at
    its default. `space="user"` reads its values as user space. Rules apply
    in order, each to the result of the ones before (as fontTools'
    processRules). Pattern rules need `glyph_names` (the default master's) to
    expand; explicit rules apply without them.
    """
    try:
        design: Dict[str, float] = {}
        for axis in all_axes(doc):
            design[axis_name(axis)] = axis.design_default
        for key, value in (location or {}).items():
            axis = find_axis(doc, key)
            number = _number(value)
            if axis is None or number is None:
                continue
            design[axis_name(axis)] = axis.get_design_value(number) if space == "user" else number

        names = list(glyph_names) if glyph_names is not None else []
        current = {name: name for name in names}
        for rule in doc.rules:
            regions = [_region(doc, rule, group) for group in rule.condition_sets]
            if not any(all(low <= design.get(name, low) <= high for name, (low, high) in region.items())
                       for region in regions):
                continue
            swaps = dict(_rule_pairs(rule, glyph_names))
            if glyph_names is None:
                for source in swaps:
                    current.setdefault(source, source)
            for original, now in list(current.items()):
                if now in swaps:
                    current[original] = swaps[now]
        return {original: now for original, now in current.items() if now != original}
    except Exception:
        return {}


# -- instances ------------------------------------------------------------------


def _instances(doc: DSSDocument, structure=None, family_name: Optional[str] = None) -> List[InstanceInfo]:
    """What `instances auto` generates — the same names and locations as DSS ->
    DS — and what its `skip` entries remove (marked skipped, with the entry),
    then the explicit instance blocks. Empty for `instances off`"""
    try:
        if doc.instances_off or not doc.axes:
            return []
        family = doc.family or family_name or None
        out = []
        index = 0
        if doc.instances_auto:
            specs = [spec_from_dss_axis(axis) for axis in all_axes(doc)]
            order = instance_axis_order(doc, [spec.name for spec in specs])
            discrete = {spec.name for spec in specs if spec.discrete}
            _, planned = plan_instances(specs, order, list(doc.instances_skip), doc)

            lines = list(doc.instances_skip_lines) + [None] * len(doc.instances_skip)
            entry_lines = dict(zip(doc.instances_skip, lines))
            for item in planned:
                span = None
                if item.skipped and structure is not None:
                    line = structure.line(entry_lines.get(item.style_name)) if entry_lines.get(item.style_name) else None
                    span = line.span if line is not None else None
                out.append(InstanceInfo(
                    index=None if item.skipped else index,
                    name=item.style_name,
                    style_name=item.style_name,
                    family_name=family,
                    user_location=dict(item.user_location),
                    design_location=dict(item.design_location),
                    skipped=item.skipped,
                    skip_entry=item.style_name if item.skipped else None,
                    skip_span=span,
                    group=tuple(label for name, label in zip(order, item.labels) if name in discrete),
                ))
                if not item.skipped:
                    index += 1
        for instance in doc.instances:
            if not instance.location:
                continue  # the block is in error; DSS -> DS would fail
            user, design, group = {}, {}, []
            for axis in doc.axes:
                value = instance.location.get(axis.name, axis.get_design_value(axis.default))
                design[axis_name(axis)] = value
                user[axis_name(axis)] = axis.get_user_value(value)
                if axis.is_discrete:
                    mapping = next((m for m in axis.mappings if m.design_value == value and m.label), None)
                    if mapping is not None:
                        group.append(mapping.label)
            for axis in doc.hidden_axes:
                if axis.name in instance.location:
                    design[axis_name(axis)] = instance.location[axis.name]
            line = structure.line(instance.line) if structure is not None and instance.line else None
            out.append(InstanceInfo(
                index=index,
                name=instance.name,
                style_name=instance.stylename or instance.name,
                family_name=instance.familyname or family,
                user_location=user,
                design_location=design,
                group=tuple(group),
                explicit=True,
                span=line.span if line is not None else None,
            ))
            index += 1
        return out
    except Exception:
        return []


# -- outline --------------------------------------------------------------------


@dataclass(frozen=True)
class Symbol:
    """One entry of the structure panel

    kind: family, suffix, elidedfallback, path, lang, section, axis, mapping,
    source, rule, skip, instance, avar2-var, avar2-row. `span` covers the item with what
    it owns (an axis with its mappings, a section with its items); `name_span`
    the word to select. `path` is the item path `Sketch.span()` / `item_at()`
    use (None where there is none)."""

    kind: str
    name: str
    span: "object"
    name_span: Optional["object"] = None
    detail: str = ""
    path: Optional[tuple] = None
    children: Tuple["Symbol", ...] = ()


_HEADER_KINDS = ("family", "suffix", "elidedfallback", "path", "lang")


def _outline(sketch) -> List[Symbol]:
    """The tree of a text: header lines, then sections with their items"""
    from . import structure as st
    from .structure import Span

    structure = sketch.structure
    doc = sketch.document
    lines = structure.lines

    def whole(first: st.Line, last_no: int) -> Span:
        last = lines[last_no - 1]
        end = last.span if last.span is not None else first.span
        return Span(first.number, first.span.col, end.end_line, end.end_col)

    def by_line(objects):
        return {o.line: o for o in objects if getattr(o, "line", None)}

    axes = by_line(all_axes(doc))
    mappings = {m.line: (a, m) for a in all_axes(doc) for m in a.mappings if m.line}
    sources = by_line(doc.sources)
    rules = {r.line: i for i, r in enumerate(doc.rules) if r.line}
    instances = {x.line: i for i, x in enumerate(doc.instances) if x.line}
    avar2 = {m.line: i for i, m in enumerate(doc.avar2_mappings) if m.line}

    def item(line: st.Line) -> Optional[Symbol]:
        v = line.values
        if line.kind in _HEADER_KINDS:
            return Symbol(line.kind, v.get("value", ""), line.span, line.fields.get("value"),
                          path=(line.kind,))
        if line.kind == st.AXIS:
            axis = axes.get(line.number)
            children = tuple(
                c for c in (item(ch) for ch in structure.children(line.number) if ch.kind == st.MAPPING) if c
            )
            name = v.get("tag") or v.get("name", "")
            detail = v.get("range", "")
            if axis is not None:
                detail = f"{axis_name(axis)} {detail}".strip()
            _, last = structure.owned_lines(line.number)
            return Symbol("axis", name, whole(line, last), line.fields.get("tag") or line.fields.get("name"),
                          detail, ("axis", axis.tag) if axis is not None else None, children)
        if line.kind == st.MAPPING:
            found = mappings.get(line.number)
            if found is None:
                return Symbol("mapping", v.get("label") or v.get("user", ""), line.span, line.fields.get("label"))
            axis, mapping = found
            key = mapping.label if mapping.label else mapping.user_value
            detail = f"user {_g(mapping.user_value)} → design {_g(mapping.design_value)}"
            if mapping.elidable:
                detail += " @elidable"
            return Symbol("mapping", mapping.label or _g(mapping.user_value), line.span,
                          line.fields.get("label") or line.fields.get("user"), detail,
                          ("mapping", axis.tag, key))
        if line.kind == st.SOURCE_LINE:
            from .sketch import SourceKey

            source = sources.get(line.number)
            flags = " ".join(v[f] for f in ("flag.base", "flag.sparse", "flag.layer") if f in v)
            coords = line.fields.get("coords")
            detail = " ".join(x for x in (structure.text_lines[line.number - 1][coords.col:coords.end_col] if coords else "", flags) if x)
            path = ("source", SourceKey(source.filename, source.layer)) if source is not None else None
            return Symbol("source", v.get("name", ""), line.span, line.fields.get("name"), detail, path)
        if line.kind == st.RULE:
            index = rules.get(line.number)
            detail = f"{v.get('pattern', '')} > {v.get('target', '')}"
            conditions = [v[k] for k in sorted(v) if k.startswith("condition.")]
            if conditions:
                detail += f" ({' && '.join(conditions)})"
            name = v.get("name") or v.get("pattern", "")
            return Symbol("rule", name, line.span, line.fields.get("name") or line.fields.get("pattern"),
                          detail, ("rule", index) if index is not None else None)
        if line.kind == st.SKIP_ENTRY:
            entry = " ".join(v.get("value", "").split())
            return Symbol("skip", entry, line.span, line.fields.get("value"), path=("skip", entry))
        if line.kind == st.INSTANCE:
            index = instances.get(line.number)
            fields = {c.values.get("key"): c.values.get("value", "") for c in structure.children(line.number)}
            _, last = structure.owned_lines(line.number)
            return Symbol("instance", v.get("name", ""), whole(line, last), line.fields.get("name"),
                          fields.get("location", ""), ("instance", index) if index is not None else None)
        if line.kind == st.AVAR2_VAR:
            return Symbol("avar2-var", v.get("name", ""), line.span, line.fields.get("name"), v.get("value", ""),
                          ("avar2_var", v.get("name", "").lstrip("$")))
        if line.kind == st.AVAR2_ROW:
            index = avar2.get(line.number)
            inputs = ", ".join(f"{k[6:]}={v[k]}" for k in v if k.startswith("input."))
            outputs = ", ".join(f"{k[7:]}={v[k]}" for k in v if k.startswith("output."))
            _, last = structure.owned_lines(line.number)
            return Symbol("avar2-row", v.get("name") or f"[{inputs}]", whole(line, last),
                          line.fields.get("name") or line.fields.get("inputs"), outputs,
                          ("avar2", index) if index is not None else None)
        return None

    out: List[Symbol] = []
    current = None  # (header line, children list)

    def close():
        if current is None:
            return
        header, children = current
        last = header.number
        for child in children:
            last = max(last, child.span.end_line)
        end = lines[last - 1].span or header.span
        detail = header.values.get("mode", "") or header.values.get("order", "")
        out.append(Symbol("section", header.values.get("keyword", ""), Span(header.number, header.span.col,
                          end.end_line, end.end_col), header.fields.get("keyword"), detail,
                          ("section", header.values.get("section")), tuple(children)))

    for line in lines:
        if line.span is None:
            continue
        if line.kind == st.SECTION:
            close()
            current = (line, [])
            continue
        if line.kind in _HEADER_KINDS:
            close()
            current = None
            symbol = item(line)
            if symbol is not None:
                out.append(symbol)
            continue
        if line.kind == st.MAPPING or line.parent is not None:
            continue  # inside its axis / avar2 block
        symbol = item(line)
        if symbol is None:
            continue
        if current is None:
            out.append(symbol)
        else:
            current[1].append(symbol)
    close()
    return out


# -- hover ----------------------------------------------------------------------


def _g(value) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _label_owner(doc: DSSDocument, label: str):
    for axis in all_axes(doc):
        for mapping in axis.mappings:
            if mapping.label == label:
                return axis, mapping
    return None, None


def _describe_label(axis: DSSAxis, mapping) -> str:
    text = f"{mapping.label} ({axis_name(axis)}): user {_g(mapping.user_value)}, design {_g(mapping.design_value)}"
    if mapping.elidable:
        text += ", elidable"
    if not mapping.user_value_explicit and mapping.label:
        from .core.mappings import Standards

        if Standards.has_mapping(mapping.label, axis.name):
            text += " (user value from the standard table)"
    return text


def _describe_axis(doc: DSSDocument, axis: DSSAxis) -> str:
    hidden = any(a is axis for a in doc.hidden_axes)
    kind = "hidden axis" if hidden else ("discrete axis" if axis.is_discrete else "axis")
    if axis.is_discrete:
        values = ", ".join(_g(v) for v in axis.values or ())
        text = f"{axis_name(axis)} ({axis.tag}), {kind}: values {values}, default {_g(axis.default)}"
    else:
        low, high = _design_range(axis)
        text = (
            f"{axis_name(axis)} ({axis.tag}), {kind}: user {_g(axis.minimum)}…{_g(axis.maximum)}, "
            f"default {_g(axis.default)}; design {_g(low)}…{_g(high)}, default {_g(axis.design_default)}"
        )
    labels = [m.label for m in axis.mappings if m.label]
    if labels:
        text += f"; {len(labels)} labels"
    return text


def _describe_location(location: Dict[str, float], user: Dict[str, float]) -> str:
    parts = []
    for name, design in location.items():
        if user.get(name) is not None and abs(user[name] - design) > 1e-9:
            parts.append(f"{name} {_g(user[name])} (design {_g(design)})")
        else:
            parts.append(f"{name} {_g(design)}")
    return ", ".join(parts)


def _hover(sketch, line_no: int, col: int) -> Optional[str]:
    """A line of explanation for what is under the cursor, or None"""
    from .syntax import AXIS_NAME, AXIS_TAG, COMMENT, GLYPH, LABEL, NUMBER, SOURCE

    line = sketch.structure.line(line_no)
    if line is None:
        return None
    token = next(
        (t for t in line.tokens if t.type != COMMENT and t.column <= col < t.column + t.length),
        None,
    )
    if token is None:
        return None
    doc = sketch.document
    path = sketch.item_at(line_no, col) or ()
    kind = path[0] if path else None

    if kind == "skip":
        entry = path[1]
        for info in sketch.instances():
            if info.skip_entry == entry:
                return f"Removes the instance '{entry}' at " + _describe_location(info.design_location, info.user_location)
        return (
            f"'{entry}' matches no generated instance: a skip entry names the final style name, "
            f"after elidable labels are dropped"
        )

    if token.type == LABEL:
        axis, mapping = _label_owner(doc, token.text)
        return _describe_label(axis, mapping) if mapping is not None else None

    if token.type in (AXIS_TAG, AXIS_NAME):
        axis = find_axis(doc, token.text)
        return _describe_axis(doc, axis) if axis is not None else None

    if token.type == NUMBER:
        try:
            value = float(token.text)
        except ValueError:
            return None
        if kind == "source" and len(path) > 3 and path[2] == "coord":
            axis = find_axis(doc, path[3])
            if axis is not None:
                return f"{axis_name(axis)}: design {_g(value)} = user {_g(axis.get_user_value(value))}"
        if kind == "mapping":
            axis = find_axis(doc, path[1])
            if axis is not None and path[-1] == "user":
                return f"{axis_name(axis)}: user {_g(value)} → design {_g(axis.get_design_value(value))}"
            if axis is not None and path[-1] == "design":
                return f"{axis_name(axis)}: design {_g(value)} = user {_g(axis.get_user_value(value))}"
        if kind == "axis":
            axis = find_axis(doc, path[1])
            if axis is not None:
                return f"{axis_name(axis)}: user {_g(value)} → design {_g(axis.get_design_value(value))}"
        if kind == "rule" and len(path) > 2 and str(path[2]).startswith("condition."):
            rule = doc.rules[path[1]]
            index = int(str(path[2]).split(".")[1])
            flat = [c for group in rule.condition_sets for c in group]
            if index < len(flat):
                axis = find_axis(doc, flat[index].get("axis"))
                if axis is not None:
                    return f"{axis_name(axis)}: design {_g(value)} = user {_g(axis.get_user_value(value))}"
        return None

    if kind == "source" and token.type == SOURCE:
        key = path[1]
        for found in _source_locations(doc):
            if found.key == key:
                base = " (base source)" if found.is_base else ""
                return f"{found.name}{base}: " + _describe_location(found.design_location, found.user_location)
        return None

    if kind == "rule":
        rule = doc.rules[path[1]]
        region = _region(doc, rule)
        where = ", ".join(f"{name} {_g(low)}…{_g(high)}" for name, (low, high) in region.items())
        where = f"applies at {where} (design space)" if where else "applies everywhere"
        if token.type == GLYPH and rule.pattern and rule.to_pattern:
            glyphs = None
            if sketch.font_data is not None:
                from .fontdata import default_master_glyphs

                glyphs = default_master_glyphs(sketch.font_data, doc)
            if glyphs is None:
                return f"{rule.pattern} > {rule.to_pattern}: {where}; the glyphs it swaps need the fonts"
            pairs = _rule_pairs(rule, glyphs)
            shown = ", ".join(f"{a} → {b}" for a, b in pairs[:8])
            more = f" and {len(pairs) - 8} more" if len(pairs) > 8 else ""
            if not pairs:
                return f"Swaps nothing in the default master ({where})"
            count = "1 glyph" if len(pairs) == 1 else f"{len(pairs)} glyphs"
            return f"Swaps {count} ({where}): {shown}{more}"
        if token.type == GLYPH and rule.substitutions:
            shown = ", ".join(f"{a} → {b}" for a, b in rule.substitutions[:8])
            return f"{shown}: {where}"
        name = f"Rule '{rule.name}'" if rule.name else "Rule"
        return f"{name} {where}"
    return None


# -- the functions on a Sketch or a text ------------------------------------------


def _sketch(sketch_or_text):
    from .sketch import Sketch

    if isinstance(sketch_or_text, Sketch):
        return sketch_or_text
    return Sketch.parse(sketch_or_text or "")


def user_to_design(sketch_or_text, axis, value) -> Optional[float]:
    """`Sketch.user_to_design()` on a Sketch or a text"""
    return _sketch(sketch_or_text).user_to_design(axis, value)


def design_to_user(sketch_or_text, axis, value) -> Optional[float]:
    """`Sketch.design_to_user()` on a Sketch or a text"""
    return _sketch(sketch_or_text).design_to_user(axis, value)


def source_locations(sketch_or_text) -> List[SourceLocation]:
    """`Sketch.source_locations()` on a Sketch or a text"""
    return _sketch(sketch_or_text).source_locations()


def rule_regions(sketch_or_text) -> List[RuleRegion]:
    """`Sketch.rule_regions()` on a Sketch or a text"""
    return _sketch(sketch_or_text).rule_regions()


def substitutions_at(sketch_or_text, location, glyph_names=None, space: str = "design") -> Dict[str, str]:
    """`Sketch.substitutions_at()` on a Sketch or a text"""
    return _sketch(sketch_or_text).substitutions_at(location, glyph_names, space)


def apply_designspace(sketch_or_text, ds_doc):
    """`Sketch.apply_designspace()` on a Sketch or a text: (EditResult, ConversionReport)"""
    return _sketch(sketch_or_text).apply_designspace(ds_doc)


def outline(sketch_or_text) -> List[Symbol]:
    """`Sketch.outline()` on a Sketch or a text"""
    return _sketch(sketch_or_text).outline()


def hover(sketch_or_text, line: int, column: int) -> Optional[str]:
    """`Sketch.hover()` on a Sketch or a text"""
    return _sketch(sketch_or_text).hover(line, column)


def expand_instances(sketch_or_text) -> List[InstanceInfo]:
    """`Sketch.instances()` on a Sketch or a text"""
    return _sketch(sketch_or_text).instances()
