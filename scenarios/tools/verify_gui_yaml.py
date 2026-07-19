"""Verify each emitted GUI YAML reloads and reproduces its snapshot.

This is the acceptance gate for the GUI-exercise artifacts. For every
scenario it opens ``inputs/<slug>.gui.yaml`` exactly as the GUI's
``File -> Open YAML`` would (``Sensor.from_yaml``), evaluates the chain, and
compares the headline metrics against ``inputs/<slug>.gui.expected.json``.

A PASS means the GUI-loadable artifact is faithful to the backend-validated
config. A FAIL means the YAML drifted, won't load, or evaluates differently.

Usage (from repo root)::

    python scenarios/tools/verify_gui_yaml.py           # all scenarios
    python scenarios/tools/verify_gui_yaml.py 1.1 1.2   # a subset by id
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui_baselines import REGISTRY, GuiScenario  # noqa: E402

from radiant.api import Sensor  # noqa: E402

# Relative tolerance for the reload-vs-snapshot comparison. The reload path is
# byte-identical config, so agreement should be ~machine precision; the loose
# bound only guards against non-determinism.
_REL_TOL = 1e-6


def _reload_metrics(scen: GuiScenario) -> dict[str, float | None]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = Sensor.from_yaml(scen.yaml_path)
        result = sensor.evaluate()
    metrics = result.metrics
    stage_outputs = result.stage_outputs
    out: dict[str, float | None] = {}
    for key in scen.metrics:
        val = metrics.get(key)
        out[key] = float(val) if isinstance(val, (int, float)) and math.isfinite(val) else None
    for dotted in scen.stage_scalars:
        stage, _, subkey = dotted.partition(".")
        val = stage_outputs.get(stage, {}).get(subkey)
        out[dotted] = float(val) if isinstance(val, (int, float)) and math.isfinite(val) else None
    return out


def verify_one(scen: GuiScenario) -> tuple[bool, str]:
    if not scen.yaml_path.is_file():
        return False, "YAML missing (run emit_gui_yaml.py)"
    if not scen.expected_path.is_file():
        return False, "expected.json missing (run emit_gui_yaml.py)"
    expected = json.loads(scen.expected_path.read_text(encoding="utf-8"))["metrics"]
    try:
        actual = _reload_metrics(scen)
    except Exception as exc:  # noqa: BLE001
        return False, f"reload/evaluate raised {type(exc).__name__}: {exc}"
    diffs: list[str] = []
    for key, exp in expected.items():
        act = actual.get(key)
        if exp is None and act is None:
            continue
        if exp is None or act is None:
            diffs.append(f"{key}: expected {exp} got {act}")
            continue
        if abs(act - exp) > _REL_TOL * max(1.0, abs(exp)):
            diffs.append(f"{key}: expected {exp:.6g} got {act:.6g}")
    if diffs:
        return False, "; ".join(diffs)
    shown = "  ".join(
        f"{k}={v:.4g}" if isinstance(v, float) else f"{k}=—" for k, v in actual.items()
    )
    return True, shown


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    scenarios = [s for s in REGISTRY if not wanted or s.id in wanted]
    if not scenarios:
        print(f"no registered scenarios match {sorted(wanted)}", file=sys.stderr)
        return 2
    n_pass = 0
    for scen in scenarios:
        ok, msg = verify_one(scen)
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {scen.id:>4}  {scen.slug}")
        print(f"        {msg}")
        n_pass += ok
    total = len(scenarios)
    print(f"\n{n_pass}/{total} scenarios PASS")
    return 0 if n_pass == total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
