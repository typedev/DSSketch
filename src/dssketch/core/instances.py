import itertools

# Import DSSDocument for type hints
from typing import TYPE_CHECKING

from fontTools.designspaceLib import DesignSpaceDocument, InstanceDescriptor

if TYPE_CHECKING:
    from .models import DSSDocument

from ..utils.logging import DSSketchLogger

# Resolve human-readable axis names to tags
NAME_TO_TAG = {
    "weight": "wght",
    "width": "wdth",
    "italic": "ital",
    "slant": "slnt",
    "optical": "opsz",
}
DEFAULT_AXIS_ORDER = [
    "Optical",
    "optical",
    "Contrast",
    "contrast",
    "Width",
    "width",
    "Weight",
    "weight",
    "Italic",
    "italic",
    "Slant",
    "slant",
]
DEFAULT_INSTANCE_FOLDER = "instances"

"""
tdInstancesMapper - Type Design Instances Mapper Module

This module provides functionality for managing and creating font instances in a DesignSpace document.
It handles the creation, manipulation, and organization of font instances based on axis combinations
and style naming conventions.

Key Features:
- Creation of font instances from axis combinations
- Management of style names with elidable (removable) parts
- Axis ordering and sorting
- Designspace document copying and manipulation

Dependencies:
- fontTools.designspaceLib
- itertools

Main Functions:
- createInstances: Creates all possible instance combinations from given axes
- sortAxisOrder: Sorts axes according to predefined order
- getElidabledNames: Generates variations of elidable style names
- removeInstances: Clears instances from designspace
- copyDS: Creates a copy of designspace document
- createInstance: Creates a single instance descriptor

Constants:
DEFAULT_AXIS_ORDER = ['optical', 'contrast', 'width', 'weight', 'italic', 'slant'] - Standard axis ordering
DEFAULT_INSTANCE_FOLDER = 'instances' - Default folder for instance files
"""


def copyDS(
    sourceDesignspace, destinationDesignspace, copyInstances=True, copyLib=True, copyRules=True
):
    destinationDesignspace.axes = sourceDesignspace.axes.copy()
    destinationDesignspace.sources = sourceDesignspace.sources.copy()
    destinationDesignspace.variableFonts = sourceDesignspace.variableFonts.copy()

    if copyInstances:
        destinationDesignspace.instances = sourceDesignspace.instances.copy()
    if copyLib:
        destinationDesignspace.lib = sourceDesignspace.lib.copy()
    if copyRules:
        destinationDesignspace.rules = sourceDesignspace.rules.copy()


def _extract_avar2_points_for_axis(dss_doc: "DSSDocument", axis_tag: str) -> set:
    """
    Extract unique input points from avar2 mappings for a specific axis.

    Args:
        dss_doc: DSS document with avar2_mappings
        axis_tag: Axis tag to look for (e.g., 'wght', 'wdth')

    Returns:
        Set of unique float values from avar2 inputs for this axis
    """
    points = set()
    if not dss_doc or not dss_doc.avar2_mappings:
        return points

    for mapping in dss_doc.avar2_mappings:
        for input_axis, input_value in mapping.input.items():
            # Match by tag (case-insensitive)
            if input_axis.lower() == axis_tag.lower():
                points.add(input_value)
    return points


def _format_axis_value_label(axis_tag: str, value: float) -> str:
    """
    Format axis value as a label name for instances without defined labels.

    Args:
        axis_tag: Axis tag (e.g., 'wght', 'wdth')
        value: The axis value

    Returns:
        Formatted label like 'wght400' or 'wdth100'
    """
    # Format value: remove .0 for integers
    if isinstance(value, float) and value.is_integer():
        value_str = str(int(value))
    else:
        value_str = str(value)
    return f"{axis_tag.lower()}{value_str}"


def getInstancesMapping(
    designSpaceDocument: DesignSpaceDocument,
    axisName: str = "weight",
    dss_doc: "DSSDocument" = None,
):
    """
    Extracts the mapping of the axis values to the user values from the designspace document.

    If the axis has no labels, generates fallback points from:
    1. min, default, max values
    2. Unique input points from avar2 mappings (if dss_doc provided)

    Args:
        designSpaceDocument: The DesignSpace document
        axisName: Name of the axis to get mapping for
        dss_doc: Optional DSS document for avar2 points extraction
    """
    axisDescriptor = designSpaceDocument.getAxis(axisName)
    if not axisDescriptor:
        axisNames = [axis.name for axis in designSpaceDocument.axes]
        axisDescriptor = designSpaceDocument.getAxis(axisNames[0])
        DSSketchLogger.warning(
            f"Axis {axisName} not found in the designspace, using {axisNames[0]} instead"
        )

    axisMap = axisDescriptor.map
    has_labels = bool(axisDescriptor.axisLabels)

    # If no labels, always use fallback (even if map exists)
    # This handles avar2 cases where map exists but labels don't
    if not has_labels:
        DSSketchLogger.info(
            f"Axis '{axisName}' has no labels, generating instances from range + avar2"
        )
        return _generate_fallback_mapping(axisDescriptor, dss_doc)

    if not axisMap:
        # For discrete axes (like italic), no map is normal - user space = design space
        # Check if this is a discrete axis by looking for the 'values' attribute
        is_discrete = hasattr(axisDescriptor, 'values') and axisDescriptor.values is not None

        if not is_discrete:
            axis_labels_info = [(label.userValue, label.name) for label in axisDescriptor.axisLabels]
            DSSketchLogger.warning(
                f"Axis '{axisName}' has no map, using axis labels and their user values {axis_labels_info}"
            )
        else:
            DSSketchLogger.debug(
                f"Discrete axis '{axisName}' has no map (expected for discrete axes)"
            )

        axisMap = []
        for axisLabel in axisDescriptor.axisLabels:
            axisMap.append((axisLabel.userValue, axisLabel.userValue))

    reverseMap = {}
    axisLabelsList = {}
    for item in axisMap:
        uservalue, axisvalue = item
        labelName = None
        for axisLabel in axisDescriptor.axisLabels:
            if axisLabel.userValue == uservalue:
                labelName = axisLabel.name
                axisLabelsList[labelName] = uservalue
                break
        if not labelName:
            DSSketchLogger.warning(
                f"Label for {axisvalue} not found in the designspace. User value: {uservalue}"
            )

        reverseMap[axisvalue] = uservalue
    return {"reverseMap": reverseMap, "axisLabels": axisLabelsList}


def _generate_fallback_mapping(axisDescriptor, dss_doc: "DSSDocument" = None) -> dict:
    """
    Generate fallback mapping for axes without labels.

    Uses min:def:max as base points, plus unique avar2 input points.
    Labels are generated as tag+value (e.g., 'wght400').

    Args:
        axisDescriptor: The axis descriptor from DesignSpace
        dss_doc: Optional DSS document for avar2 points

    Returns:
        Dict with 'reverseMap' and 'axisLabels'
    """
    axis_tag = axisDescriptor.tag

    # Start with min, default, max
    points = {
        axisDescriptor.minimum,
        axisDescriptor.default,
        axisDescriptor.maximum,
    }

    # Add avar2 input points
    if dss_doc:
        avar2_points = _extract_avar2_points_for_axis(dss_doc, axis_tag)
        if avar2_points:
            DSSketchLogger.debug(
                f"Adding {len(avar2_points)} avar2 points for axis '{axis_tag}': {sorted(avar2_points)}"
            )
            points.update(avar2_points)

    # Sort points
    sorted_points = sorted(points)

    DSSketchLogger.info(
        f"Axis '{axisDescriptor.name}' ({axis_tag}): generated {len(sorted_points)} instance points: {sorted_points}"
    )

    # Generate mapping with tag+value labels
    reverseMap = {}
    axisLabelsList = {}
    for value in sorted_points:
        label = _format_axis_value_label(axis_tag, value)
        # For no-map axes, user value = design value
        reverseMap[value] = value
        axisLabelsList[label] = value

    return {"reverseMap": reverseMap, "axisLabels": axisLabelsList}


def createInstance(location: dict, familyName: str, styleName: str, defaultFolder="instances"):
    instance = InstanceDescriptor()
    instance.familyName = familyName
    instance.styleName = styleName
    instance.location = location
    instance.postScriptFontName = f"{familyName.replace(' ', '')}-{styleName.replace(' ', '')}"
    # instance.path = os.path.join('instances', f"{instance.postScriptFontName}.ufo")
    instance.filename = f"{defaultFolder}/{instance.postScriptFontName}.ufo"
    return instance


def combineFilters(filter_dict: dict):
    values = filter_dict.values()
    return [" ".join(combination) for combination in itertools.product(*values)]


def _validate_skip_labels(skipList: list, labelsmap: list, axisOrder: list) -> list:
    """
    Validate that all labels in skip rules exist in axis definitions.

    Note: Labels cannot contain spaces. Use camelCase for compound names
    (e.g., "ExtraLight", "SemiBold", not "Extra Light", "Semi Bold").

    Args:
        skipList: List of skip combinations (e.g., ["Bold Italic", "ExtraLight Condensed"])
        labelsmap: List of dicts with axis labels {label: user_value}
        axisOrder: List of axis names in order

    Returns:
        list: List of validation errors (empty if all valid)
    """
    errors = []

    # Collect all valid labels from all axes
    all_valid_labels = set()
    for axis_labels in labelsmap:
        all_valid_labels.update(axis_labels.keys())

    # Check each skip combination
    for skip_combo in skipList:
        # Split by spaces - each word must be a valid label
        labels_in_combo = skip_combo.split()

        for label in labels_in_combo:
            if label not in all_valid_labels:
                # Label not found in any axis - this is an ERROR
                errors.append(
                    f"Skip rule '{skip_combo}' contains label '{label}' which is not defined in any axis. "
                    f"Available labels: {', '.join(sorted(all_valid_labels))}"
                )
                break  # One error per skip combo is enough

    return errors


def createInstances(
    dssource: DesignSpaceDocument,
    dss_doc: "DSSDocument" = None,
    defaultFolder="instances",
    skipFilter: dict = {},
    skipList: list = None,
    filterInstances: dict = {},
):
    """
    Creates all possible instance combinations from the designspace with given axis order.

    Args:
        dssource (DesignSpaceDocument): Source designspace document
        dss_doc (DSSDocument): Original DSS document to get axes order from
        defaultFolder (str): Output folder for instances (default: 'instances')
        skipFilter (dict): Dictionary of style combinations to skip (legacy, generates cartesian product)
        skipList (list): List of specific instance combinations to skip (e.g., ["Bold Italic", "Light Italic"])
        filter (dict): Dictionary of style combinations to include (default: None) not used yet

    Returns:
        DesignSpaceDocument: Designspace document with instances
        list: Report of created instances with their locations and style names
    """

    ds = DesignSpaceDocument()
    copyDS(dssource, ds, copyInstances=False)

    axisOrder = sortAxisOrder(ds, dss_doc)
    elidableStyleNames = getElidabledNames(ds, axisOrder)

    defaultSource = ds.findDefault()
    if not defaultSource and ds.sources:
        # If no default source is found, use the first source
        defaultSource = ds.sources[0]

    # Fallback to document family name if no sources
    defaultFamilyName = defaultSource.familyName if defaultSource else "UnknownFamily"
    locations = {}
    labelsmap = []
    report = []
    for axisname in axisOrder:
        mapAxis = getInstancesMapping(ds, axisname, dss_doc=dss_doc)
        locations[axisname] = mapAxis["reverseMap"]
        labelsmap.append(mapAxis["axisLabels"])

    combinations = [
        {key: value for key, value in combination}
        for combination in itertools.product(*[d.items() for d in labelsmap])
    ]

    skippedInstances = []
    # Support both skipFilter (dict) and skipList (list)
    if skipFilter:
        skippedInstances = combineFilters(skipFilter)
    if skipList:
        # Validate skip labels BEFORE processing
        validation_errors = _validate_skip_labels(skipList, labelsmap, axisOrder)
        if validation_errors:
            for error in validation_errors:
                DSSketchLogger.error(error)
            raise ValueError(
                f"Skip rule validation failed: {len(validation_errors)} error(s) found. "
                "Check that all labels in skip rules are defined in axes section."
            )
        skippedInstances.extend(skipList)

    # Log skip information
    if skippedInstances:
        DSSketchLogger.info(f"Instance skip rules: {len(skippedInstances)} combinations will be skipped")
        for skip_combo in skippedInstances:
            DSSketchLogger.info(f"  - {skip_combo}")

    # Track which skip rules were actually used
    used_skip_rules = set()

    for item in combinations:
        itemlist = list(item.items())

        styleNameInstance = " ".join([name for name, _ in itemlist])

        # Apply elidable name cleanup BEFORE checking skip rules
        # Only elide from compound names — never remove the last remaining word
        if elidableStyleNames:
            words = styleNameInstance.split()
            if len(words) > 1:
                for removeStyleName in elidableStyleNames:
                    if removeStyleName in styleNameInstance:
                        cleaned = styleNameInstance.replace(removeStyleName, "").strip()
                        cleaned = " ".join(cleaned.split())
                        if cleaned:  # Don't elide if result would be empty
                            styleNameInstance = cleaned
        styleNameInstance = " ".join(styleNameInstance.split())
        if "Regular Italic" in styleNameInstance:  # just replace -Regular Italic- to -Italic-
            # TODO need check Slants, Obliques, etc.
            styleNameInstance = styleNameInstance.replace("Regular Italic", "Italic")

        # Check skip rules AFTER applying elidable cleanup
        if skippedInstances and styleNameInstance in skippedInstances:
            DSSketchLogger.info(f"Skipping instance: {styleNameInstance}")
            used_skip_rules.add(styleNameInstance)  # Track that this rule was used
            continue

        locationsInstance = {}
        mapUserValues = [uservalue for _, uservalue in itemlist]
        for i, uservalue in enumerate(mapUserValues):
            axisName = axisOrder[i]
            axisDescriptor = ds.getAxis(axisName)
            if axisDescriptor and axisDescriptor.map:
                # Use forward map (user → design) for instance locations
                forwardMap = dict(axisDescriptor.map)
                if uservalue in forwardMap:
                    locationsInstance[axisName] = forwardMap[uservalue]
                else:
                    locationsInstance[axisName] = uservalue
            else:
                # No map: user value = design value (discrete axes, etc.)
                locationsInstance[axisName] = uservalue
        report.append({"styleName": styleNameInstance, "location": locationsInstance})

        ds.addInstance(
            createInstance(
                location=locationsInstance,
                familyName=defaultFamilyName,
                styleName=styleNameInstance,
                defaultFolder=defaultFolder,
            )
        )

    # Validate that all skip rules were actually used (WARNING level)
    if skippedInstances:
        unused_skip_rules = set(skippedInstances) - used_skip_rules
        if unused_skip_rules:
            DSSketchLogger.warning(
                f"Skip validation: {len(unused_skip_rules)} skip rule(s) were never used. "
                "This may indicate a typo or that elidable cleanup changed the instance names."
            )
            for unused_rule in sorted(unused_skip_rules):
                DSSketchLogger.warning(f"  - Unused skip rule: '{unused_rule}'")

    return ds, report


def sortAxisOrder(ds: DesignSpaceDocument, dss_doc: "DSSDocument" = None):
    """
    Sorts axes using order from DSS axes section or fallback to DEFAULT_AXIS_ORDER.
    Updates axisOrdering values in the designspace document.

    Args:
        ds (DesignSpaceDocument): Source designspace document
        dss_doc (DSSDocument): Original DSS document to get axes order from

    Returns:
        list: Sorted list of axis names
    """
    if dss_doc and dss_doc.axes:
        # Use the exact order from DSS axes section (PUBLIC axes only)
        # Hidden axes are excluded from instance generation
        orderAxis = []
        for dss_axis in dss_doc.axes:
            # DesignSpace axis.name is set from display_name or name
            ds_name = dss_axis.display_name if dss_axis.display_name else dss_axis.name
            orderAxis.append(ds_name)

        # NOTE: We intentionally do NOT add hidden axes from ds.axes
        # Hidden axes (from dss_doc.hidden_axes) should not participate in instance generation
    else:
        # Fallback to DEFAULT_AXIS_ORDER logic for backward compatibility
        axisNames = [axis.name for axis in ds.axes]
        orderAxis = []
        for axisname in DEFAULT_AXIS_ORDER:
            if axisname in axisNames:
                orderAxis.append(axisname)
        for axisname in axisNames:
            if axisname not in orderAxis:
                orderAxis.append(axisname)  # Add missing to end, not beginning

    # Update axisOrdering values
    for idx, axisname in enumerate(orderAxis):
        axis = ds.getAxis(axisname)
        if axis:
            axis.axisOrdering = idx

    return orderAxis


def _resolve_axis_tag(name_or_tag: str) -> str:
    """Resolve axis name/tag to canonical tag (e.g., 'weight'/'Weight' → 'wght')"""
    lower = name_or_tag.lower()
    return NAME_TO_TAG.get(lower, lower)


def getElidabledNames(ds: DesignSpaceDocument, axisOrder: list = [], ignoreAxis: list = []):
    """
    Generates variations of elidable style names for the designspace.

    The @elidable flag works for ALL axes including weight. Single-word protection
    in createInstances() prevents removing the last remaining word from style names
    (e.g., standalone "Regular" is preserved, but "Compressed Regular" → "Compressed").

    Weight axis elidable label is placed LAST in the removal list so it survives
    when all labels are elidable (font naming convention: weight is the primary axis).

    Args:
        ds (DesignSpaceDocument): Source designspace document
        axisOrder (list): Order of axes for processing
        ignoreAxis (list): Axis names/tags to skip (default: empty — all axes participate).
            Accepts any form: 'wght', 'weight', 'Weight', etc.

    Returns:
        list: List of elidable style name combinations
    """
    elidabledAxis = {}
    ignoreTags = {_resolve_axis_tag(a) for a in ignoreAxis}
    for axisDescriptor in ds.axes:
        axis_tag = _resolve_axis_tag(axisDescriptor.tag if hasattr(axisDescriptor, 'tag') else axisDescriptor.name)
        if axis_tag not in ignoreTags:
            for axisLabel in axisDescriptor.axisLabels:
                if axisLabel.elidable:
                    elidabledAxis[axisDescriptor.name] = axisLabel.name

    # Full compound elidable name (all elidable labels joined)
    elidabledNamesList = [
        " ".join(
            elidabledAxis[axisName] for axisName in axisOrder if axisName in elidabledAxis
        ).strip()
    ]

    # Individual elidable names: weight axis LAST (survives when all are elidable)
    weight_elidable = None
    for axisName in axisOrder:
        if axisName in elidabledAxis and elidabledAxis[axisName] not in elidabledNamesList:
            axis_tag = _resolve_axis_tag(
                next((a.tag for a in ds.axes if a.name == axisName), axisName)
            )
            if axis_tag == "wght":
                weight_elidable = elidabledAxis[axisName]
            else:
                elidabledNamesList.append(elidabledAxis[axisName])

    # Weight elidable goes last — last to be tried for removal, first to survive
    if weight_elidable and weight_elidable not in elidabledNamesList:
        elidabledNamesList.append(weight_elidable)

    return elidabledNamesList


def removeInstances(ds: DesignSpaceDocument):
    """
    remove instances from the designspace by the given filter
    """
    ds.instances.clear()
