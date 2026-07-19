"""Emit a GUI-loadable YAML + an expected-metrics snapshot per scenario.

For each registered scenario this:

1. builds the baseline :class:`Sensor` from the validated runner,
2. evaluates it and records the headline metrics,
3. writes ``inputs/<slug>.gui.yaml`` (``Sensor.to_yaml(scope="inputs")`` —
   exactly what ``File -> Open YAML`` consumes), and
4. writes ``inputs/<slug>.gui.expected.json`` (the snapshot the verify gate
   re-checks after a clean reload).

Usage (from repo root)::

    python scenarios/tools/emit_gui_yaml.py            # all scenarios
    python scenarios/tools/emit_gui_yaml.py 1.1 1.2    # a subset by id
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

# Allow ``from _runner_import import ...`` / ``from gui_baselines import ...``
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui_baselines import REGISTRY, GuiScenario  # noqa: E402


def _snapshot(sensor_result: object, scen: GuiScenario) -> dict[str, float | None]:
    metrics = getattr(sensor_result, "metrics", {})
    snap: dict[str, float | None] = {}
    for key in scen.metrics:
        val = metrics.get(key)
        snap[key] = float(val) if isinstance(val, (int, float)) and math.isfinite(val) else None
    stage_outputs = getattr(sensor_result, "stage_outputs", {})
    for dotted in scen.stage_scalars:
        stage, _, subkey = dotted.partition(".")
        val = stage_outputs.get(stage, {}).get(subkey)
        snap[dotted] = float(val) if isinstance(val, (int, float)) and math.isfinite(val) else None
    return snap


def emit_one(scen: GuiScenario) -> dict[str, float | None]:
    scen.yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = scen.build()
        result = sensor.evaluate()
        yaml_text = sensor.to_yaml(scope="inputs")
    scen.yaml_path.write_text(yaml_text, encoding="utf-8", newline="\n")
    snap = _snapshot(result, scen)
    payload = {
        "id": scen.id,
        "title": scen.title,
        "metrics": snap,
        "notes": scen.notes,
    }
    scen.expected_path.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return snap


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    scenarios = [s for s in REGISTRY if not wanted or s.id in wanted]
    if not scenarios:
        print(f"no registered scenarios match {sorted(wanted)}", file=sys.stderr)
        return 2
    for scen in scenarios:
        try:
            snap = emit_one(scen)
        except Exception as exc:  # noqa: BLE001 — surface which scenario broke
            print(f"[FAIL] {scen.id:>4}  {type(exc).__name__}: {exc}")
            continue
        metric_str = "  ".join(
            f"{k}={v:.4g}" if isinstance(v, float) else f"{k}=—" for k, v in snap.items()
        )
        rel = scen.yaml_path.relative_to(Path(__file__).resolve().parents[2])
        print(f"[ ok ] {scen.id:>4}  ->  {rel}   ({metric_str})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
