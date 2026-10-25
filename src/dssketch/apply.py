"""Write a changed DesignSpace back into a sketch's text (1.5.x)

`Sketch.apply_designspace(ds_doc)` gives the edits that make the text describe
`ds_doc`, made with the Sketch's own operations, so comments, blank lines and
the spelling of everything untouched survive. The DesignSpace is first read as
a sketch (DS -> DSS); the two documents are compared item by item:

- header: family (when the text has a `family` line), `elidedfallback`, `lang`
- axes by tag: range, discrete, DesignSpace name, mappings by user value
  (label, design value, @elidable; a renamed label follows into its uses),
  axes added and removed, the order of the axes
- sources by path and layer: coordinates, @base, @sparse; added and removed
- rules by name: conditions, an explicit rule's glyphs; added, removed, order.
  A pattern rule (`a* > .ss01`) is kept as long as the DesignSpace's
  substitutions fit its pattern

Not written, and said so in the report: avar2 (not edited yet), instances and
`skip` (DSSketch-level; a DesignSpace records only their result), an axis that
moved between `axes` and `axes hidden`, an edit the sketch refuses (the rest is
applied). What DS -> DSS itself cannot carry (document lib, …) is reported as
the converter reports it.

Needs fontTools (it reads a DesignSpaceDocument); imported only when called.
"""

import difflib
import posixpath
from typing import Dict, List, Optional, Tuple

from .core.models import DSSAxis, DSSDocument, DSSRule, elided_fallback_name
from .core.report import (
    APPLY_AVAR2_NOT_APPLIED,
    APPLY_HIDDEN_CHANGED,
    APPLY_INSTANCES_NOT_APPLIED,
    APPLY_REFUSED,
    APPLY_RULE_KEPT,
    CATEGORY_APPLY,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    ConversionIssue,
    ConversionReport,
)
from .sketch import EditError, EditResult, Sketch, SourceKey, TextEdit

_EPSILON = 1e-6


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) < _EPSILON


class _Applier:
    def __init__(self, sketch: Sketch, target: DSSDocument, report: ConversionReport):
        self.sketch = sketch
        self.target = target
        self.report = report
        self.deferred: List[Tuple[str, object, EditError]] = []

    # -- running operations -------------------------------------------------------

    def run(self, description: str, op) -> bool:
        """Apply `op(sketch)`. A refused one is retried after the others (a new
        maximum needs the mapping at it, which needs the new maximum); what
        still fails goes to the report (`finish`)"""
        try:
            result = op(self.sketch)
        except EditError as error:
            self.deferred.append((description, op, error))
            return False
        if result.edits:
            self.sketch = result.sketch
        return True

    def finish(self):
        """Retry the refused operations while any of them succeeds; report the rest"""
        progress = True
        while self.deferred and progress:
            progress = False
            pending, self.deferred = self.deferred, []
            for description, op, _ in pending:
                if self.run(description, op):
                    progress = True
            if not progress and len(self.deferred) > 1:
                # each needs another (a new maximum and the mapping at it): all at once
                try:
                    result = self.sketch._apply_together([op for _, op, _ in self.deferred])
                except EditError:
                    break
                self.sketch = result.sketch
                self.deferred = []
        for description, _, error in self.deferred:
            self.report.add(ConversionIssue(
                CATEGORY_APPLY, APPLY_REFUSED, SEVERITY_WARNING,
                f"Not applied: {description}",
                details=error.message,
                raw_data={"operation": description, "code": error.code, "messages": list(error.messages)},
            ))

    @property
    def doc(self) -> DSSDocument:
        return self.sketch.document

    def note(self, code: int, severity: int, description: str, details: str = "", **raw):
        self.report.add(ConversionIssue(CATEGORY_APPLY, code, severity, description, details=details, raw_data=raw))

    # -- helpers ------------------------------------------------------------------

    @staticmethod
    def axis_of(doc: DSSDocument, key) -> Optional[DSSAxis]:
        from .queries import find_axis

        return find_axis(doc, key)

    def axes_by_tag(self, doc: DSSDocument, hidden: bool) -> Dict[str, DSSAxis]:
        return {a.tag: a for a in (doc.hidden_axes if hidden else doc.axes)}

    # -- header -------------------------------------------------------------------

    def header(self):
        target = self.target
        if self.doc.family and target.family and target.family != self.doc.family:
            self.run(f"family {target.family}", lambda sk: sk.set_family(target.family))
        wanted = elided_fallback_name(target)
        if elided_fallback_name(self.doc) != wanted:
            value = wanted if target.elided_fallback else None
            if value is None and elided_fallback_name(self._without_elided()) != wanted:
                value = wanted
            self.run(f"elidedfallback {wanted}", lambda sk: sk.set_elided_fallback(value))
        if list(self.doc.languages or []) != list(target.languages or []):
            codes = list(target.languages or []) or None
            self.run(f"lang {', '.join(codes or [])}", lambda sk: sk.set_lang(codes))

    def _without_elided(self) -> DSSDocument:
        import copy

        doc = copy.copy(self.doc)
        doc.elided_fallback = None
        return doc

    # -- axes ---------------------------------------------------------------------

    def axes(self):
        for hidden in (False, True):
            current = self.axes_by_tag(self.doc, hidden)
            wanted = self.axes_by_tag(self.target, hidden)
            other = self.axes_by_tag(self.doc, not hidden)
            for tag in current:
                if tag not in wanted and tag in self.axes_by_tag(self.target, not hidden):
                    self.note(APPLY_HIDDEN_CHANGED, SEVERITY_WARNING,
                              f"Axis '{tag}' is {'visible' if hidden else 'hidden'} in the DesignSpace; not moved",
                              axis=tag)
            for tag, axis in wanted.items():
                if tag in other:
                    continue  # reported above, from the other side
                if tag not in current:
                    self.add_axis(axis, hidden)
            for tag in list(current):
                if tag not in wanted and tag not in self.axes_by_tag(self.target, not hidden):
                    self.run(f"remove axis {tag}", lambda sk, tag=tag: sk.remove_axis(tag))
            for tag, axis in wanted.items():
                if tag in self.axes_by_tag(self.doc, hidden):
                    self.update_axis(axis)
        self.order_axes()

    def add_axis(self, axis: DSSAxis, hidden: bool):
        from .queries import axis_name

        display = axis_name(axis)
        ok = self.run(
            f"add axis {axis.tag}",
            lambda sk: sk.add_axis(
                axis.tag, axis.minimum, axis.default, axis.maximum,
                display_name=display if display != _default_name(axis.tag) else None,
                discrete=axis.is_discrete and not hidden, hidden=hidden,
            ),
        )
        if ok:
            for mapping in axis.mappings:
                self.add_mapping(axis.tag, mapping)

    def add_mapping(self, tag: str, mapping):
        self.run(
            f"add mapping {mapping.label or mapping.user_value} on {tag}",
            lambda sk: sk.add_mapping(tag, mapping.label, mapping.design_value, user=mapping.user_value,
                                      elidable=mapping.elidable),
        )

    def update_axis(self, axis: DSSAxis):
        from .core.instances import spec_from_dss_axis
        from .queries import axis_name

        tag = axis.tag
        current = self.sketch.axis(tag)
        if current.is_discrete != axis.is_discrete:
            self.run(f"discrete {tag}", lambda sk: sk.set_axis_discrete(tag, axis.is_discrete))
            current = self.sketch.axis(tag)
        if not current.is_discrete and not (
            _same(current.minimum, axis.minimum) and _same(current.default, axis.default)
            and _same(current.maximum, axis.maximum)
        ):
            self.run(
                f"range of {tag} {axis.minimum:g}:{axis.default:g}:{axis.maximum:g}",
                lambda sk: sk.set_axis_range(tag, axis.minimum, axis.default, axis.maximum),
            )
            current = self.sketch.axis(tag)
        if axis_name(current) != axis_name(axis):
            name = axis_name(axis)
            self.run(f"name of {tag} {name}", lambda sk: sk.set_axis_display_name(tag, name))
            current = self.sketch.axis(tag)

        # what the mappings mean (labels, map) is the same: leave them as written
        a, b = spec_from_dss_axis(current), spec_from_dss_axis(axis)
        if _pairs_equal(a.map, b.map) and _labels_equal(a.labels, b.labels):
            return
        have = {m.user_value: m for m in current.mappings}
        want = {m.user_value: m for m in axis.mappings}
        for user, mapping in have.items():
            if not any(_same(user, u) for u in want):
                key = mapping.label if mapping.label else user
                self.run(f"remove mapping {key} on {tag}", lambda sk, key=key: sk.remove_mapping(tag, key))
        for user, mapping in want.items():
            old = next((m for u, m in have.items() if _same(u, user)), None)
            if old is None:
                continue
            key = old.label if old.label else old.user_value
            if mapping.label != old.label:
                if old.label and mapping.label:
                    self.run(f"rename {old.label} to {mapping.label} on {tag}",
                             lambda sk, o=old.label, n=mapping.label: sk.rename_label(tag, o, n))
                else:
                    self.run(f"label {mapping.label!r} at user {user:g} on {tag}",
                             lambda sk, k=key, n=mapping.label: sk.set_mapping_label(tag, k, n))
                key = mapping.label if mapping.label else user
            if not _same(old.design_value, mapping.design_value):
                self.run(f"design value of {key} on {tag}",
                         lambda sk, k=key, d=mapping.design_value: sk.set_mapping_design(tag, k, d))
            if bool(old.elidable) != bool(mapping.elidable) and mapping.label:
                self.run(f"@elidable on {mapping.label}",
                         lambda sk, n=mapping.label, e=mapping.elidable: sk.set_mapping_elidable(tag, n, e))
        for user, mapping in want.items():
            if not any(_same(user, u) for u in have):
                self.add_mapping(tag, mapping)

    def order_axes(self):
        for hidden in (False, True):
            wanted = [a.tag for a in (self.target.hidden_axes if hidden else self.target.axes)]
            for index, tag in enumerate(wanted):
                current = [a.tag for a in (self.doc.hidden_axes if hidden else self.doc.axes)]
                if tag in current and current.index(tag) != index:
                    self.run(f"move axis {tag} to {index}", lambda sk, t=tag, i=index: sk.move_axis(t, i))

    # -- sources ------------------------------------------------------------------

    @staticmethod
    def full_path(doc: DSSDocument, filename: str) -> str:
        path = (doc.path or "").replace("\\", "/")
        return posixpath.normpath(posixpath.join(path, filename.replace("\\", "/")))

    def design_location(self, doc: DSSDocument, source) -> Dict[str, float]:
        out = {a.tag: a.design_default for a in doc.axes + doc.hidden_axes}
        for key, value in source.location.items():
            axis = self.axis_of(doc, key)
            if axis is not None and value is not None:
                out[axis.tag] = value
        return out

    def sources(self):
        def keyed(doc):
            return {(self.full_path(doc, s.filename), s.layer): s for s in doc.sources}

        current = keyed(self.doc)
        wanted = keyed(self.target)
        for key, source in current.items():
            if key not in wanted:
                skey = SourceKey(source.filename, source.layer)
                self.run(f"remove source {source.name}", lambda sk, k=skey: sk.remove_source(k))
        for key, source in wanted.items():
            if key not in current:
                self.add_source(key[0], source)
        current = keyed(self.doc)
        for key, source in wanted.items():
            mine = current.get(key)
            if mine is None:
                continue
            skey = SourceKey(mine.filename, mine.layer)
            have = self.design_location(self.doc, mine)
            for tag, value in self.design_location(self.target, source).items():
                if tag in have and not _same(have[tag], value):
                    self.run(f"{tag} of {mine.name} to {value:g}",
                             lambda sk, t=tag, v=value: sk.set_source_coordinate(skey, t, v))
            if source.is_sparse != mine.is_sparse:
                self.run(f"@sparse on {mine.name}", lambda sk, s=source.is_sparse: sk.set_sparse(skey, s))
        # A DesignSpace has one default source: the one at every axis default.
        # DS -> DSS marks one per discrete value, which the text need not write
        current = keyed(self.doc)
        defaults = {a.tag: a.design_default for a in self.target.axes + self.target.hidden_axes}
        for key, source in wanted.items():
            mine = current.get(key)
            location = self.design_location(self.target, source)
            at_default = all(_same(location.get(tag), value) for tag, value in defaults.items())
            if mine is not None and source.is_base and at_default and not mine.is_base:
                skey = SourceKey(mine.filename, mine.layer)
                self.run(f"@base on {mine.name}", lambda sk, k=skey: sk.set_base(k))

    def add_source(self, full: str, source):
        base = (self.doc.path or "").replace("\\", "/").strip("/")
        relative = posixpath.relpath(full, base) if base else full
        if relative.startswith(".."):
            relative = full
        written = [ln.values.get("name", "") for ln in self.sketch.structure.of_kind("source")]
        if relative.endswith(".ufo") and written and not any(w.endswith(".ufo") for w in written):
            relative = relative[:-4]
        location = {}
        for key, value in source.location.items():
            axis = self.axis_of(self.target, key)
            if axis is not None:
                location[axis.tag] = value
        self.run(
            f"add source {relative}",
            lambda sk: sk.add_source(relative, location, base=source.is_base, sparse=source.is_sparse,
                                     layer=source.layer),
        )

    # -- rules --------------------------------------------------------------------

    def conditions(self, doc: DSSDocument, rule: DSSRule) -> List[Tuple[str, Optional[float], Optional[float]]]:
        out = []
        for condition in rule.conditions or ():
            axis = self.axis_of(doc, condition.get("axis"))
            tag = axis.tag if axis is not None else str(condition.get("axis"))
            out.append((tag, condition.get("minimum"), condition.get("maximum")))
        return sorted(out, key=lambda c: c[0])

    def _spelled(self, rule: DSSRule) -> DSSRule:
        """A target rule with its condition axes named as the text names them"""
        import copy

        rule = copy.copy(rule)
        conditions = []
        for condition in rule.conditions or ():
            condition = dict(condition)
            axis = self.axis_of(self.doc, condition.get("axis"))
            if axis is not None:
                condition["axis"] = axis.name
            conditions.append(condition)
        rule.conditions = conditions
        return rule

    def _format(self, rule: DSSRule) -> List[str]:
        from .writers.dss_writer import DSSWriter

        return DSSWriter()._format_rule(self._spelled(rule), self.doc.axes + self.doc.hidden_axes)

    def condition_texts(self, rule: DSSRule) -> List[str]:
        """The conditions of a target rule as the writer spells them"""
        line = self._format(rule)[0]
        inside = line[line.index("(") + 1: line.rindex(")")]
        return [part.strip() for part in inside.split("&&")]

    @staticmethod
    def fits(rule: DSSRule, pairs) -> bool:
        """Whether glyph pairs are ones a pattern rule makes"""
        from .utils.patterns import PatternMatcher

        words = rule.pattern.split()
        for source, target in pairs:
            if not PatternMatcher.find_matching_glyphs(words, [source]) and source not in words:
                return False
            wanted = source + rule.to_pattern if rule.to_pattern.startswith(".") else rule.to_pattern
            if target != wanted:
                return False
        return True

    def rules(self):
        def keyed(rules):
            out, seen = {}, {}
            for rule in rules:
                n = seen.get(rule.name, 0)
                seen[rule.name] = n + 1
                out[(rule.name, n)] = rule
            return out

        current = keyed(self.doc.rules)
        wanted = keyed(self.target.rules)
        for key in reversed(list(current)):
            if key not in wanted:
                index = list(keyed(self.doc.rules)).index(key)
                self.run(f"remove rule {key[0]}", lambda sk, i=index: sk.remove_rule(i))
        for key, rule in wanted.items():
            keys = list(keyed(self.doc.rules))
            if key not in keys:
                self.add_rule(rule)
                continue
            index = keys.index(key)
            mine = self.doc.rules[index]
            if self.conditions(self.doc, mine) != self.conditions(self.target, rule):
                self.set_conditions(index, rule)
            self.update_glyphs(index, mine, rule)
        order = list(wanted)
        for position, key in enumerate(order):
            keys = list(keyed(self.doc.rules))
            if key in keys and keys.index(key) != position:
                self.run(f"move rule {key[0]}", lambda sk, i=keys.index(key), p=position: sk.move_rule(i, p))
        last = self.target.rules_processing_last
        if self.target.rules and self.doc.rules_processing_last != last:
            self.run("rules last" if last else "rules", lambda sk: sk.set_rules_processing(last))

    def add_rule(self, rule: DSSRule):
        name = None if (rule.name.startswith("rule") and rule.name[4:].isdigit()) else rule.name
        texts = self.condition_texts(rule)
        lines = self._format(rule)
        for line in lines:
            head = line.strip().split(" (", 1)[0]
            pattern, _, target = head.partition(" > ")
            self.run(f"add rule {rule.name}",
                     lambda sk, p=pattern, t=target: sk.add_rule(p, t, texts, name=name))
            name = None  # the name goes on the first line only

    def set_conditions(self, index: int, rule: DSSRule):
        texts = self.condition_texts(rule)
        count = len(self.doc.rules[index].conditions or ())
        for position, text in enumerate(texts):
            if position < count:
                self.run(f"condition {position} of rule {rule.name}",
                         lambda sk, p=position, t=text: sk.set_rule_condition(index, p, t))
            else:
                self.run(f"condition of rule {rule.name}", lambda sk, t=text: sk.add_rule_condition(index, t))
        for position in range(count - 1, len(texts) - 1, -1):
            self.run(f"remove condition {position} of rule {rule.name}",
                     lambda sk, p=position: sk.remove_rule_condition(index, p))

    def update_glyphs(self, index: int, mine: DSSRule, rule: DSSRule):
        pairs = sorted(rule.substitutions)
        if mine.pattern and mine.to_pattern:
            if pairs and not self.fits(mine, pairs):
                self.note(APPLY_RULE_KEPT, SEVERITY_WARNING,
                          f"Rule '{mine.name}' kept as written ({mine.pattern} > {mine.to_pattern}): "
                          f"the DesignSpace swaps glyphs it does not describe",
                          rule=mine.name, substitutions=[list(p) for p in pairs])
            return
        if sorted(mine.substitutions) == pairs:
            return
        if len(pairs) == 1:
            source, target = pairs[0]
            if mine.substitutions and mine.substitutions[0][0] != source:
                self.run(f"pattern of rule {rule.name}", lambda sk: sk.set_rule_pattern(index, source))
            self.run(f"target of rule {rule.name}", lambda sk: sk.set_rule_target(index, target))
            return
        self.note(APPLY_RULE_KEPT, SEVERITY_WARNING,
                  f"Rule '{mine.name}' kept as written: the DesignSpace swaps {len(pairs)} glyph pairs",
                  rule=mine.name, substitutions=[list(p) for p in pairs])

    # -- what is not written ------------------------------------------------------

    def avar2(self):
        def normal(doc):
            out = []
            for mapping in doc.avar2_mappings:
                def side(values):
                    items = []
                    for key, value in values.items():
                        axis = self.axis_of(doc, key)
                        items.append((axis.tag if axis is not None else key, round(float(value), 4)))
                    return tuple(sorted(items))
                out.append((side(mapping.input), side(mapping.output)))
            return sorted(out)

        if normal(self.doc) != normal(self.target):
            self.note(APPLY_AVAR2_NOT_APPLIED, SEVERITY_WARNING,
                      "The avar2 mappings differ; avar2 is not edited, the text keeps its own",
                      current=len(self.doc.avar2_mappings), designspace=len(self.target.avar2_mappings))

    def instances(self, ds_doc):
        """Instances are DSSketch-level: compare what the text generates (its
        `skip` applied) with the DesignSpace's, by name and position"""
        def key(name, location):
            return name, tuple(sorted((k, round(float(v), 4)) for k, v in location.items()))

        mine = self.sketch.instances()
        if self.doc.instances_off or self.doc.instances_auto:
            ours = {key(i.style_name, i.design_location) for i in mine if not i.skipped}
        else:
            ours = None  # explicit instances: not generated, nothing to compare
        theirs = {key(i.styleName or "", dict(i.location)) for i in ds_doc.instances}
        if ours is None or ours == theirs:
            return
        missing = sorted(name for name, _ in theirs - ours)
        extra = sorted(name for name, _ in ours - theirs)
        self.note(
            APPLY_INSTANCES_NOT_APPLIED, SEVERITY_WARNING,
            f"Instances differ from what the text generates ({len(missing)} only in the DesignSpace, "
            f"{len(extra)} only in the text); instances and skip entries are not rewritten",
            details="Edit the axes' labels, `instances auto/off` or the `skip` entries to match.",
            only_designspace=missing, only_text=extra,
        )


def _default_name(tag: str) -> str:
    from .parsers.dss_parser import DSSParser

    return DSSParser.TAG_TO_NAME.get(tag, tag.upper())


def _pairs_equal(a, b) -> bool:
    return len(a) == len(b) and all(_same(x[0], y[0]) and _same(x[1], y[1]) for x, y in zip(a, b))


def _labels_equal(a, b) -> bool:
    return len(a) == len(b) and all(
        x[0] == y[0] and _same(x[1], y[1]) and bool(x[2]) == bool(y[2]) for x, y in zip(a, b)
    )


def line_edits(old: str, new: str) -> List[TextEdit]:
    """Whole-line edits turning `old` into `new` (non-overlapping, in order)"""
    a = old.split("\n")
    b = new.split("\n")
    edits = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        replacement = b[j1:j2]
        if i2 < len(a):
            # lines i1..i2-1 become `replacement`, each with its newline
            edits.append(TextEdit(i1 + 1, 0, i2 + 1, 0, "".join(line + "\n" for line in replacement)))
        elif i1 < i2:
            # up to the end of the text: no newline after the last line
            start_line, start_col = (i1, len(a[i1 - 1])) if i1 > 0 else (1, 0)
            text = "\n".join(replacement)
            if i1 > 0:
                text = ("\n" + text) if replacement else ""
            edits.append(TextEdit(start_line, start_col, len(a), len(a[-1]), text))
        else:  # insertion at the very end
            edits.append(TextEdit(len(a), len(a[-1]), len(a), len(a[-1]), "\n" + "\n".join(replacement)))
    return edits


def apply_designspace(sketch: Sketch, ds_doc) -> Tuple[EditResult, ConversionReport]:
    """The edits that make `sketch`'s text describe `ds_doc`, and a report of
    what was not written (see the module docstring)"""
    from .converters.designspace_to_dss import DesignSpaceToDSS

    converter = DesignSpaceToDSS()
    target = converter.convert(ds_doc)
    report = ConversionReport()
    for issue in converter.report:
        report.add(issue)

    applier = _Applier(sketch, target, report)
    applier.axes()
    applier.sources()
    applier.rules()
    applier.header()
    applier.finish()
    applier.avar2()
    applier.instances(ds_doc)

    final = applier.sketch
    if final.text == sketch.text:
        return EditResult([], sketch.text, sketch, sketch.font_data), report
    edits = line_edits(sketch.text, final.text)
    return EditResult(edits, final.text, final, sketch.font_data), report
