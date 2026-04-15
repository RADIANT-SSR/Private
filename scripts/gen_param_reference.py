#!/usr/bin/env python
"""Generate docs/guides/parameter_reference.md from the parameter registry.

Usage::

    python scripts/gen_param_reference.py > docs/guides/parameter_reference.md

Or simply run it to write the file directly:

    python scripts/gen_param_reference.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# Ensure the src/ directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from radiant.api._param_registry import build_parameter_set  # noqa: E402


def main() -> None:
    ps = build_parameter_set()
    defs = ps._defs  # dict[str, ParameterDef]

    # Group by top-level namespace
    groups: dict[str, list] = defaultdict(list)
    for name, pdef in sorted(defs.items()):
        top = name.split(".")[0]
        groups[top].append(pdef)

    lines: list[str] = []
    lines.append("# Parameter Reference")
    lines.append("")
    lines.append("*Auto-generated from the parameter registry. "
                 "Do not edit by hand --- re-run "
                 "`python scripts/gen_param_reference.py` to update.*")
    lines.append("")
    lines.append(f"**Total parameters: {len(defs)}**")
    lines.append("")

    stage_order = [
        "source", "atmosphere", "geometry", "optics",
        "detector", "spectral_integration", "readout",
    ]

    for stage in stage_order:
        if stage not in groups:
            continue
        pdefs = groups[stage]
        lines.append(f"## {stage}")
        lines.append("")
        lines.append("| Parameter | Type | Default | Input Unit | Bounds | Description |")
        lines.append("|-----------|------|---------|------------|--------|-------------|")

        for pdef in pdefs:
            dtype = pdef.dtype.__name__ if hasattr(pdef.dtype, "__name__") else str(pdef.dtype)
            default = pdef.default if pdef.default is not None else "**required**"
            unit = pdef.input_unit or "---"
            bounds = f"{pdef.bounds}" if pdef.bounds is not None else "---"
            desc = getattr(pdef, "description", "") or ""
            lines.append(f"| `{pdef.name}` | {dtype} | {default} | {unit} | {bounds} | {desc} |")

        lines.append("")

    # Consistency groups
    lines.append("## Consistency Groups")
    lines.append("")
    if hasattr(ps, "_consistency_groups") and ps._consistency_groups:
        for cg in ps._consistency_groups:
            members = ", ".join(f"`{m}`" for m in cg.members)
            lines.append(f"- **{cg.name}**: {members}")
            if hasattr(cg, "relation"):
                lines.append(f"  - Relation: `{cg.relation}`")
        lines.append("")
    else:
        lines.append("See `optics.f_number` = `optics.focal_length_m / "
                     "optics.aperture_diameter_m`.")
        lines.append("")

    output = "\n".join(lines)

    # Write to file
    out_path = Path(__file__).resolve().parent.parent / "docs" / "guides" / "parameter_reference.md"
    out_path.write_text(output, encoding="utf-8")
    print(f"Wrote {out_path} ({len(defs)} parameters)")


if __name__ == "__main__":
    main()
