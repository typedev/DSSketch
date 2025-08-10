"""
DesignSpace to DSS converter

This module converts DesignSpace documents to DSS format.
"""

import json
from pathlib import Path
from typing import Optional

from fontTools.designspaceLib import (
    AxisDescriptor,
    DesignSpaceDocument,
    InstanceDescriptor,
    RuleDescriptor,
    SourceDescriptor,
)

from ..core.models import DSSAxis, DSSAxisMapping, DSSDocument, DSSInstance, DSSMaster, DSSRule


class DesignSpaceToDSS:
    """Convert DesignSpace to DSS format"""

    def __init__(self):
        self.font_resources = {}
        self.load_external_data()

    def load_external_data(self):
        """Load external font resource translations"""
        data_dir = Path(__file__).parent.parent / "data"

        try:
            with open(data_dir / "font-resources-translations.json", 'r') as f:
                self.font_resources = json.load(f)
        except FileNotFoundError:
            pass

    def convert_file(self, ds_path: str) -> DSSDocument:
        """Convert DesignSpace file to DSS document"""
        doc = DesignSpaceDocument()
        doc.read(ds_path)
        return self.convert(doc)

    def convert(self, ds_doc: DesignSpaceDocument) -> DSSDocument:
        """Convert DesignSpace document to DSS document"""
        dss_doc = DSSDocument(family=self._extract_family_name(ds_doc))

        # Determine common path for masters
        masters_path = self._determine_masters_path(ds_doc)
        if masters_path:
            dss_doc.path = masters_path

        # Convert axes
        for axis in ds_doc.axes:
            dss_axis = self._convert_axis(axis)
            dss_doc.axes.append(dss_axis)

        # Convert masters/sources
        for source in ds_doc.sources:
            dss_master = self._convert_source(source, ds_doc, masters_path)
            dss_doc.masters.append(dss_master)

        # Convert instances (optional - can be auto-generated)
        for instance in ds_doc.instances:
            dss_instance = self._convert_instance(instance, ds_doc)
            dss_doc.instances.append(dss_instance)

        # Convert rules
        for rule in ds_doc.rules:
            dss_rule = self._convert_rule(rule, ds_doc)
            if dss_rule:
                dss_doc.rules.append(dss_rule)

        return dss_doc

    def _extract_family_name(self, ds_doc: DesignSpaceDocument) -> str:
        """Extract family name from DesignSpace document"""
        if ds_doc.instances:
            return ds_doc.instances[0].familyName or "Unknown"
        elif ds_doc.sources:
            return ds_doc.sources[0].familyName or "Unknown"
        return "Unknown"

    def _determine_masters_path(self, ds_doc: DesignSpaceDocument) -> Optional[str]:
        """Determine common path for all masters"""
        if not ds_doc.sources:
            return None

        # Collect all master paths
        master_paths = []
        for source in ds_doc.sources:
            if source.filename:
                master_paths.append(Path(source.filename))

        if not master_paths:
            return None

        # Find common directory
        directories = set()
        for path in master_paths:
            if path.parent != Path('.'):
                directories.add(path.parent)

        # If all masters are in root directory (no parent path)
        if not directories:
            return None

        # If all masters are in the same directory
        if len(directories) == 1:
            common_dir = directories.pop()
            return str(common_dir).replace('\\', '/')

        # Masters are in different directories - return None
        return None

    def _convert_axis(self, axis: AxisDescriptor) -> DSSAxis:
        """Convert DesignSpace axis to DSS axis"""
        # Handle discrete axes (like italic)
        if hasattr(axis, 'values') and axis.values:
            values = list(axis.values)
            minimum = min(values)
            maximum = max(values)
            default = getattr(axis, 'default', minimum)
        else:
            minimum = getattr(axis, 'minimum', 0)
            maximum = getattr(axis, 'maximum', 1000)
            default = getattr(axis, 'default', minimum)

        dss_axis = DSSAxis(
            name=axis.name,
            tag=axis.tag,
            minimum=minimum,
            default=default,
            maximum=maximum
        )

        # Process mappings and labels
        mappings_dict = {}

        # Collect mappings
        if axis.map:
            for mapping in axis.map:
                if hasattr(mapping, 'inputLocation'):
                    user_val = mapping.inputLocation
                    design_val = mapping.outputLocation
                else:
                    user_val, design_val = mapping
                mappings_dict[user_val] = design_val

        # Collect labels and create mappings
        if axis.axisLabels:
            for label in axis.axisLabels:
                user_val = label.userValue
                design_val = mappings_dict.get(user_val, user_val)

                mapping = DSSAxisMapping(
                    user_value=user_val,
                    design_value=design_val,
                    label=label.name
                )
                dss_axis.mappings.append(mapping)

        # Sort mappings by user value
        dss_axis.mappings.sort(key=lambda m: m.user_value)

        return dss_axis

    def _convert_source(self, source: SourceDescriptor, ds_doc: DesignSpaceDocument, masters_path: Optional[str] = None) -> DSSMaster:
        """Convert DesignSpace source to DSS master"""
        filename = source.filename or ""
        name = Path(filename).stem

        # If we have a common masters path, strip it from the filename
        if masters_path and filename.startswith(masters_path):
            filename = filename[len(masters_path):].lstrip('/')

        # Determine if this is a base master
        is_base = bool(source.copyLib or source.copyInfo or
                      source.copyGroups or source.copyFeatures)

        return DSSMaster(
            name=name,
            filename=filename or f"{name}.ufo",
            location=dict(source.location),
            is_base=is_base,
            copy_lib=source.copyLib,
            copy_info=source.copyInfo,
            copy_groups=source.copyGroups,
            copy_features=source.copyFeatures
        )

    def _convert_instance(self, instance: InstanceDescriptor, ds_doc: DesignSpaceDocument) -> DSSInstance:
        """Convert DesignSpace instance to DSS instance"""
        return DSSInstance(
            name=instance.styleName or "",
            familyname=instance.familyName or "",
            stylename=instance.styleName or "",
            filename=instance.filename,
            location=dict(instance.location)
        )

    def _convert_rule(self, rule: RuleDescriptor, ds_doc: DesignSpaceDocument) -> Optional[DSSRule]:
        """Convert DesignSpace rule to DSS rule"""
        if not rule.subs:
            return None

        substitutions = []
        for sub in rule.subs:
            substitutions.append((sub[0], sub[1]))

        conditions = []
        if hasattr(rule, 'conditionSets') and rule.conditionSets:
            for condset in rule.conditionSets:
                for condition in condset:
                    conditions.append({
                        'axis': condition['name'],
                        'minimum': condition.get('minimum', 0),
                        'maximum': condition.get('maximum', 1000)
                    })
        elif hasattr(rule, 'conditions'):
            for condition in rule.conditions:
                conditions.append({
                    'axis': condition.name,
                    'minimum': condition.minimum,
                    'maximum': condition.maximum
                })

        return DSSRule(
            name=rule.name or "rule",
            substitutions=substitutions,
            conditions=conditions
        )

