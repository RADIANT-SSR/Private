#!/usr/bin/env python
"""Generate docs/guides/parameter_reference.md from the parameter registry.

Usage::

    python scripts/gen_param_reference.py          # write the file
    python scripts/gen_param_reference.py --check   # verify committed copy is current

``--check`` regenerates the reference in memory and diffs it against the
committed copy, exiting non-zero on any drift (CU-099 enforcement) — the same
fail-on-mismatch pattern as ``scripts/check_org_rules.py``.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# Ensure the src/ directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from radiant.api._param_registry import build_parameter_set  # noqa: E402

_OUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "guides" / "parameter_reference.md"


def render() -> str:
    """Render the full parameter-reference markdown from the live registry."""
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

    return "\n".join(lines)


def main() -> int:
    """Write the reference file, or (with --check) verify the committed copy."""
    check = "--check" in sys.argv[1:]
    output = render()
    if check:
        committed = _OUT_PATH.read_text(encoding="utf-8") if _OUT_PATH.exists() else ""
        if committed != output:
            print(
                "parameter_reference.md is STALE — regenerate with "
                "`python scripts/gen_param_reference.py` and commit (CU-099).",
                file=sys.stderr,
            )
            return 1
        print("parameter_reference.md: OK (matches the registry)")
        return 0
    _OUT_PATH.write_text(output, encoding="utf-8")
    print(f"Wrote {_OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
