import itertools

from fontTools.designspaceLib import DesignSpaceDocument, InstanceDescriptor

# from icecream import ic

# ruff: noqa: E402
# import tdFontFamilyMapper
# importlib.reload(tdFontFamilyMapper)
# from tdFontFamilyMapper import getInstancesMapping

ELIDABLE_MAJOR_AXIS = "weight"
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
- icecream (for debugging)

Main Functions:
- createInstances: Creates all possible instance combinations from given axes
- sortAxisOrder: Sorts axes according to predefined order
- getElidabledNames: Generates variations of elidable style names
- removeInstances: Clears instances from designspace
- copyDS: Creates a copy of designspace document
- createInstance: Creates a single instance descriptor

Constants:
ELIDABLE_MAJOR_AXIS = 'weight' - Axis that shouldn't be elidable by default
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


def getInstancesMapping(designSpaceDocument: DesignSpaceDocument, axisName="weight", logger=None):
    """
    Extracts the mapping of the axis values to the user values from the designspace document.
    """
    axisDescriptor = designSpaceDocument.getAxis(axisName)
    if not axisDescriptor:
        axisNames = [axis.name for axis in designSpaceDocument.axes]
        axisDescriptor = designSpaceDocument.getAxis(axisNames[0])
        if logger:
            logger.warning(
                f"Axis {axisName} not found in the designspace, using {axisNames[0]} instead"
            )

    axisMap = axisDescriptor.map
    if not axisMap:
        if logger:
            logger.warning(
                f"there is no map, use the axis labels and their user values {axisDescriptor.axisLabels}"
            )
        axisMap = []
        for axisLabel in axisDescriptor.axisLabels:
            axisMap.append((axisLabel.userValue, axisLabel.userValue))

    reverseMap = {}
    axisLabelsList = {}
    # logger.warning(f'axisMap: {axisMap}')
    for item in axisMap:
        uservalue, axisvalue = item
        labelName = None
        # logger.warning(f'axisDescriptor.axisLabels: {axisDescriptor.axisLabels}')
        for axisLabel in axisDescriptor.axisLabels:
            # logger.warning(f"loop:{axisLabel.userValue}, {uservalue}")
            if axisLabel.userValue == uservalue:
                labelName = axisLabel.name
                axisLabelsList[labelName] = uservalue
                break
        if not labelName:
            if logger:
                logger.warning(
                    f"Label for {axisvalue} not found in the designspace. User value: {uservalue}"
                )

        reverseMap[axisvalue] = uservalue
    # logger.warning(f'reverseMap: {reverseMap}')
    return dict(reverseMap=reverseMap, axisLabels=axisLabelsList)


def createInstance(location: dict, familyName: str, styleName: str, defaultFolder="instances"):
    instance = InstanceDescriptor()
    instance.familyName = familyName
    instance.styleName = styleName
    instance.location = location
    instance.postScriptFontName = f"{familyName.replace(' ', '')}-{styleName.replace(' ', '')}"
    # instance.path = os.path.join('instances', f"{instance.postScriptFontName}.ufo")
    instance.filename = f"{defaultFolder}/{instance.postScriptFontName}.ufo"
    return instance


def combineFilters(filter: dict):
    values = filter.values()
    return [" ".join(combination) for combination in itertools.product(*values)]


def createInstances(
    dssource: DesignSpaceDocument,
    defaultFolder="instances",
    skipFilter: dict = {},
    filter: dict = {},
):
    """
    Creates all possible instance combinations from the designspace with given axis order.

    Args:
        dssource (DesignSpaceDocument): Source designspace document
        defaultFolder (str): Output folder for instances (default: 'instances')
        skipFilter (dict): Dictionary of style combinations to skip (default: None)
        filter (dict): Dictionary of style combinations to include (default: None) not used yet

    Returns:
        DesignSpaceDocument: Designspace document with instances
        list: Report of created instances with their locations and style names
    """

    ds = DesignSpaceDocument()
    copyDS(dssource, ds, copyInstances=False)

    axisOrder = sortAxisOrder(ds)
    elidableStyleNames = getElidabledNames(ds, axisOrder, ignoreAxis=["weight"])

    defaultSource = ds.findDefault()
    if not defaultSource and ds.sources:
        # If no default source is found, use the first source
        defaultSource = ds.sources[0]

    if defaultSource:
        defaultFamilyName = defaultSource.familyName
    else:
        # Fallback to document family name if no sources
        defaultFamilyName = "UnknownFamily"
    locations = {}
    labelsmap = []
    report = []
    for axisname in axisOrder:
        mapAxis = getInstancesMapping(ds, axisname)
        locations[axisname] = mapAxis["reverseMap"]
        labelsmap.append(mapAxis["axisLabels"])

    combinations = [
        {key: value for key, value in combination}
        for combination in itertools.product(*[d.items() for d in labelsmap])
    ]

    skippedInstances = []
    if skipFilter:
        skippedInstances = combineFilters(skipFilter)

    for item in combinations:
        itemlist = list(item.items())

        styleNameInstance = " ".join([name for name, _ in itemlist])
        if skippedInstances:
            if styleNameInstance in skippedInstances:
                continue
        if elidableStyleNames:
            for removeStyleName in elidableStyleNames:
                if removeStyleName in styleNameInstance:
                    styleNameInstance = styleNameInstance.replace(removeStyleName, "").strip()
                    # break
        styleNameInstance = " ".join(styleNameInstance.split())
        if "Regular Italic" in styleNameInstance:  # just replace -Regular Italic- to -Italic-
            # TODO need check Slants, Obliques, etc.
            styleNameInstance = styleNameInstance.replace("Regular Italic", "Italic")

        locationsInstance = {}
        mapUserValues = [uservalue for _, uservalue in itemlist]
        for i, uservalue in enumerate(mapUserValues):
            axisName = axisOrder[i]
            axisDescriptor = ds.getAxis(axisName)
            mapAxis = dict(axisDescriptor.map)
            if not mapAxis:
                # if no map, then use user values
                mapAxis = {}
                for axisLabel in axisDescriptor.axisLabels:
                    mapAxis[axisLabel.userValue] = axisLabel.userValue
            locationsInstance[axisName] = mapAxis[uservalue]
        report.append(dict(styleName=styleNameInstance, location=locationsInstance))

        ds.addInstance(
            createInstance(
                location=locationsInstance,
                familyName=defaultFamilyName,
                styleName=styleNameInstance,
                defaultFolder=defaultFolder,
            )
        )
    return ds, report


def sortAxisOrder(ds: DesignSpaceDocument):
    """
    Sorts axes in designspace according to DEFAULT_AXIS_ORDER.
    Updates axisOrdering values in the designspace document.

    Args:
        ds (DesignSpaceDocument): Source designspace document

    Returns:
        list: Sorted list of axis names
    """
    # TODO need think how to get the axis order from profile yaml file instead of DEFAULT_AXIS_ORDER
    axisNames = [axis.name for axis in ds.axes]
    orderAxis = []
    for axisname in DEFAULT_AXIS_ORDER:
        if axisname in axisNames:
            orderAxis.append(axisname)
    for axisname in axisNames:
        if axisname not in orderAxis:
            orderAxis.insert(0, axisname)
    for idx, axisname in enumerate(orderAxis):
        axis = ds.getAxis(axisname)
        axis.axisOrdering = idx
    return orderAxis


def getElidabledNames(ds: DesignSpaceDocument, axisOrder: list = [], ignoreAxis: list = []):
    """
    Generates variations of elidable style names for the designspace.

    Args:
        ds (DesignSpaceDocument): Source designspace document
        axisOrder (list): Order of axes for processing
        ignoreAxis (list): Axes to ignore when generating elidable names (default: ['weight'])

    Returns:
        list: List of elidable style name combinations
    """
    elidabledAxis = {}
    ignoreAxis = ignoreAxis or [ELIDABLE_MAJOR_AXIS]
    for axisDescriptor in ds.axes:
        if axisDescriptor.name not in ignoreAxis:
            for axisLabel in axisDescriptor.axisLabels:
                if axisLabel.elidable:
                    elidabledAxis[axisDescriptor.name] = axisLabel.name

    elidabledNamesList = [
        " ".join(
            elidabledAxis[axisName] for axisName in axisOrder if axisName in elidabledAxis
        ).strip()
    ]

    for axisName in axisOrder:
        if axisName in elidabledAxis and elidabledAxis[axisName] not in elidabledNamesList:
            elidabledNamesList.append(elidabledAxis[axisName])

    return elidabledNamesList


def removeInstances(ds: DesignSpaceDocument, filter=None):
    """
    remove instances from the designspace by the given filter
    """
    ds.instances.clear()
