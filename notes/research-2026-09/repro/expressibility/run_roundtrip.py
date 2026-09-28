import sys, os, io
pass  # run from the repo root with `uv run python`
import dssketch
from fontTools.designspaceLib import DesignSpaceDocument

HERE = os.path.dirname(os.path.abspath(__file__))

probes = [
    "probe_axis_stat_labels.designspace",
    "probe_hidden_discrete_ordering.designspace",
    "probe_location_labels.designspace",
    "probe_variable_fonts.designspace",
    "probe_source_richness.designspace",
    "probe_instance_richness.designspace",
    "probe_rules_or_processing.designspace",
    "probe_doclevel_lib.designspace",
]

for name in probes:
    path = os.path.join(HERE, name)
    print("=" * 80)
    print(name)
    print("=" * 80)
    ds = DesignSpaceDocument()
    ds.read(path)
    try:
        sketch, report = dssketch.convert_designspace_to_dss_string(ds, return_report=True)
    except Exception as e:
        print("CRASH on DS->DSS:", repr(e))
        continue

    dss_path = os.path.join(HERE, name.replace(".designspace", ".dssketch"))
    with open(dss_path, "w") as f:
        f.write(sketch)
    print("--- dssketch output ---")
    print(sketch)
    print("--- report ---")
    if report.warnings or report.infos if hasattr(report, "infos") else report.warnings:
        pass
    for issue in getattr(report, "warnings", []):
        print("WARNING", issue.id, issue.description)
    for issue in getattr(report, "infos", []):
        print("INFO", issue.id, issue.description)
    if not getattr(report, "warnings", []) and not getattr(report, "infos", []):
        print("(no report entries)")

    try:
        ds2 = dssketch.convert_dss_string_to_designspace(sketch, base_path=HERE)
    except Exception as e:
        print("CRASH on DSS->DS:", repr(e))
        continue

    out_path = os.path.join(HERE, name.replace(".designspace", ".roundtrip.designspace"))
    ds2.write(out_path)
    print("--- wrote roundtrip:", out_path)
