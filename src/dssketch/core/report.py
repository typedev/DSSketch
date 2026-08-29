"""
Structured report for conversion diagnostics.

Conversion problems reach the log as prose, which is fine for a human reading a
terminal and useless to a caller that wants to act on them. This module gives
those problems a machine-readable shape: a category, a numeric code, a severity,
and typed details, alongside the human-readable description.

The layout follows the DesignSpace validator in Font Rover, so a caller that
already consumes those results can consume these the same way:

    category  what part of the document the issue is about
    code      which issue within that category — stable, safe to switch on
    severity  ERROR / WARNING / INFO
    details   longer explanation, may be empty
    raw_data  escape hatch for anything not worth a typed field

Issue identity is the ``(category, code)`` pair, rendered as ``"2.0"``. Codes are
append-only: never renumber one, because callers key off them.

Example:
    import dssketch

    sketch, report = dssketch.convert_designspace_to_dss_string(
        ds, return_report=True
    )
    for issue in report.warnings:
        print(issue.id, issue.description)
        for ref in issue.instances:
            print("   ", ref.style_name, ref.location)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# =============================================================================
# Categories
# =============================================================================

CATEGORY_AXES = 0
CATEGORY_SOURCES = 1
CATEGORY_INSTANCES = 2
CATEGORY_RULES = 3

CATEGORY_NAMES = {
    CATEGORY_AXES: "Axes",
    CATEGORY_SOURCES: "Sources",
    CATEGORY_INSTANCES: "Instances",
    CATEGORY_RULES: "Rules",
}

# =============================================================================
# Severity
# =============================================================================

SEVERITY_ERROR = 0  # the sketch will not describe the source document
SEVERITY_WARNING = 1  # the sketch differs from the source in a way worth knowing
SEVERITY_INFO = 2  # expected difference, reported so it is not a surprise

SEVERITY_NAMES = {
    SEVERITY_ERROR: "error",
    SEVERITY_WARNING: "warning",
    SEVERITY_INFO: "info",
}

# =============================================================================
# Issue codes — CATEGORY_INSTANCES
# =============================================================================

#: A declared instance sits at a position `instances auto` never generates, so
#: the sketch cannot describe the design space completely.
INSTANCE_UNREACHABLE = 0

#: The generator reaches the position but names it differently. Usually means
#: the source document predates a change in the elidable naming rules.
INSTANCE_RENAMED = 1

#: The generator produces positions the source document does not declare — the
#: document was filtered. Expected; an `instances auto` / `skip` block is how a
#: sketch expresses that, and it cannot be recovered from a DesignSpace.
INSTANCE_EXTRA = 2


# =============================================================================
# Typed details
# =============================================================================


@dataclass
class InstanceRef:
    """One instance, identified by name and design-space position."""

    style_name: str
    location: Dict[str, float] = field(default_factory=dict)
    #: Set when the same position carries a different name in the other document.
    other_style_name: Optional[str] = None

    def to_dict(self) -> dict:
        data: Dict[str, Any] = {
            "style_name": self.style_name,
            "location": dict(self.location),
        }
        if self.other_style_name is not None:
            data["other_style_name"] = self.other_style_name
        return data


# =============================================================================
# Issue and report
# =============================================================================


@dataclass
class ConversionIssue:
    """A single problem found while converting."""

    category: int
    code: int
    severity: int
    description: str
    details: str = ""
    suggested_fix: str = ""
    #: Instances this issue is about, when it is about instances.
    instances: List[InstanceRef] = field(default_factory=list)
    #: Anything not worth a typed field.
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Stable identifier, e.g. ``"2.0"``. Safe to compare against."""
        return f"{self.category}.{self.code}"

    @property
    def category_name(self) -> str:
        return CATEGORY_NAMES.get(self.category, str(self.category))

    @property
    def severity_name(self) -> str:
        return SEVERITY_NAMES.get(self.severity, str(self.severity))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "category_name": self.category_name,
            "code": self.code,
            "severity": self.severity,
            "severity_name": self.severity_name,
            "description": self.description,
            "details": self.details,
            "suggested_fix": self.suggested_fix,
            "instances": [ref.to_dict() for ref in self.instances],
            "raw_data": dict(self.raw_data),
        }


@dataclass
class ConversionReport:
    """Everything one conversion found.

    An empty report means the conversion had nothing to say — not that it did
    not run.
    """

    issues: List[ConversionIssue] = field(default_factory=list)

    def add(self, issue: ConversionIssue) -> ConversionIssue:
        self.issues.append(issue)
        return issue

    def __len__(self) -> int:
        return len(self.issues)

    def __iter__(self):
        return iter(self.issues)

    def __bool__(self) -> bool:
        """True when anything was reported, so ``if report:`` reads naturally."""
        return bool(self.issues)

    # -- filtered views ----------------------------------------------------

    def of_severity(self, severity: int) -> List[ConversionIssue]:
        return [i for i in self.issues if i.severity == severity]

    @property
    def errors(self) -> List[ConversionIssue]:
        return self.of_severity(SEVERITY_ERROR)

    @property
    def warnings(self) -> List[ConversionIssue]:
        return self.of_severity(SEVERITY_WARNING)

    @property
    def infos(self) -> List[ConversionIssue]:
        return self.of_severity(SEVERITY_INFO)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def of_category(self, category: int) -> List[ConversionIssue]:
        return [i for i in self.issues if i.category == category]

    def find(self, category: int, code: int) -> Optional[ConversionIssue]:
        """The first issue with this exact identity, or None."""
        for issue in self.issues:
            if issue.category == category and issue.code == code:
                return issue
        return None

    def to_dict(self) -> dict:
        return {
            "issues": [issue.to_dict() for issue in self.issues],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.infos),
        }
