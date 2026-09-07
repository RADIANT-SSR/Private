#!/usr/bin/env python3
"""Generate loadable RADIANT config files from the shipped FPA presets.

Gap 119 plan §3.1a mechanism (b): the preset YAML (datasheet-native units,
per-parameter attribution) is the single source of truth; this script renders
each part as a standard RADIANT config at
``src/radiant/data/tables/fpa/configs/<name>.yaml`` — values converted to
schema input units through the ordinary ``ParameterSet.set(..., unit=...)``
boundary (Rule 2) and written by ``radiant.io.config.save_config`` with
provenance as comment lines.

Usage::

    python scripts/gen_fpa_configs.py           # regenerate all configs
    python scripts/gen_fpa_configs.py --check   # exit 1 if any config is stale

``--check`` runs in the merge-gate battery (like ``gen_param_reference.py``);
``tests/test_fpa_configs_current.py`` enforces the same freshness in pytest.
"""

from __future__ import annotations

import argparse
import difflib
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from radiant.api.session import RadiantSession  # noqa: E402
from radiant.core.parameters import Provenance  # noqa: E402
from radiant.data.fpa import FPALibrary, FPAPreset  # noqa: E402
from radiant.io.config import save_config  # noqa: E402

CONFIG_DIR = REPO_ROOT / "src" / "radiant" / "data" / "tables" / "fpa" / "configs"


def render_config(part: FPAPreset) -> str:
    """Render one preset as loadable config-YAML text with provenance comments."""
    params = RadiantSession.default_params()
    for dotpath, entry in sorted(part.parameters.items()):
        params.set(
            dotpath,
            entry.value,
            provenance=Provenance.PRESET,
            source=f"fpa:{part.name}/{entry.source or 'assumed'}",
            unit=entry.unit,
        )
    lines = [
        f"# RADIANT config — generated from FPA preset '{part.name}' (format v1).",
        "# DO NOT EDIT: regenerate with `python scripts/gen_fpa_configs.py`.",
        f"# Part: {part.vendor} {part.model} ({part.part_class})",
        f"# Band: {part.band.label}, {part.band.cut_on_um}-{part.band.cut_off_um} um",
        "# Values are in RADIANT input units (converted from the datasheet-native",
        "# units recorded in the preset). Per-parameter provenance:",
    ]
    for dotpath, entry in sorted(part.parameters.items()):
        native = f"{entry.value}" + (f" {entry.unit}" if entry.unit else "")
        origin = entry.source or "assumed (see preset note)"
        lines.append(f"#   {dotpath} = {native} [{entry.basis}: {origin}]")
    lines.append("#")
    header = "\n".join(lines) + "\n"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "cfg.yaml"
        save_config(params, tmp, header=header, scope="inputs")
        return tmp.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed configs match regeneration; exit 1 on drift",
    )
    args = parser.parse_args()

    lib = FPALibrary()
    names = lib.names()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    expected = {f"{name}.yaml" for name in names}
    stale: list[str] = []

    for name in names:
        text = render_config(lib.part(name))
        dest = CONFIG_DIR / f"{name}.yaml"
        if args.check:
            current = dest.read_text(encoding="utf-8") if dest.exists() else ""
            if current != text:
                stale.append(name)
                diff = difflib.unified_diff(
                    current.splitlines(), text.splitlines(), str(dest), "regenerated", lineterm=""
                )
                print("\n".join(list(diff)[:40]))
        else:
            dest.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {dest.relative_to(REPO_ROOT)}")

    orphans = [p.name for p in CONFIG_DIR.glob("*.yaml") if p.name not in expected]
    if args.check:
        if stale or orphans:
            print(
                f"fpa configs: STALE ({', '.join(stale) or 'none'}); "
                f"orphans: {', '.join(orphans) or 'none'} — run scripts/gen_fpa_configs.py"
            )
            return 1
        print(f"fpa configs: OK ({len(names)} configs match the presets)")
        return 0
    for orphan in orphans:
        (CONFIG_DIR / orphan).unlink()
        print(f"removed orphan {orphan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
