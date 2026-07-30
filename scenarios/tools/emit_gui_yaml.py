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


class UnreloadableBaselineError(RuntimeError):
    """A baseline would be emitted pointing at a file that is not committed."""


def _repoint_generated_inputs(sensor: object, scen: GuiScenario) -> list[str]:
    """Point file-path parameters at committed ``inputs/``, not generated ``outputs/`` (CU-273).

    A scenario runner naturally holds the *working* path for anything it
    derived — ``<scenario>/outputs/derived/foo.csv``. That directory is
    gitignored (Rule 26), so relativising it into the baseline (CU-177) emits
    ``user_radiance_path: ../outputs/derived/foo.csv``: correct in the tree that
    just ran the scenario, and unreloadable anywhere else. The failure is
    invisible to whoever regenerates — the file exists for them — and surfaces
    only for the next cold checkout or for CI. That is exactly how a live
    regression reached ``main`` in the CU-253 baseline refresh under a green
    6023-test suite (``d169feb``, repaired by ``962bc8e``).

    So before serialising, every ``is_file_path`` value that resolves inside the
    scenario's ``outputs/`` tree is rewritten to the same-named file under its
    ``inputs/`` tree. If no committed counterpart exists we **raise** rather
    than emit a baseline that cannot be reloaded — the whole point of CU-177 /
    CU-180 is that these artifacts are portable, and a silent unreloadable one
    is worse than a loud failure (Rule 17).

    Returns the dot-paths that were repointed, for the caller to report.
    """
    scenario_root = scen.yaml_path.parent.parent
    outputs_root = (scenario_root / "outputs").resolve()
    inputs_root = (scenario_root / "inputs").resolve()

    defs = sensor.parameter_defs()  # type: ignore[attr-defined]
    inputs = dict(sensor.inputs())  # type: ignore[attr-defined]
    repointed: list[str] = []

    for dotpath, value in inputs.items():
        pdef = defs.get(dotpath)
        if pdef is None or not getattr(pdef, "is_file_path", False):
            continue
        if not isinstance(value, str) or not value:
            continue
        resolved = Path(value).resolve()
        if not resolved.is_relative_to(outputs_root):
            continue  # already a committed input, or outside the scenario entirely

        committed = inputs_root / resolved.name
        if not committed.exists():
            raise UnreloadableBaselineError(
                f"{scen.id}: {dotpath} points into the scenario's generated outputs tree "
                f"({resolved}), which is gitignored, and there is no committed counterpart "
                f"at {committed}.\n"
                "  Emitting this baseline would produce a .gui.yaml that reloads only in a "
                "tree that has just run the scenario (CU-273).\n"
                "  Fix: commit the derived file under the scenario's inputs/ directory (see "
                "CU-180 for the precedent) and name its generator in the scenario MANIFEST, "
                "then re-run this emitter."
            )
        sensor.set(dotpath, str(committed))  # type: ignore[attr-defined]
        repointed.append(dotpath)

    return repointed


def emit_one(scen: GuiScenario) -> dict[str, float | None]:
    scen.yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensor = scen.build()
        result = sensor.evaluate()
        # CU-273: repoint generated inputs at their committed counterparts
        # BEFORE relativising, so the emitted path is one a cold checkout has.
        # Done after evaluate() so the numbers come from the scenario exactly as
        # it ran; the two files are identical in content, so this cannot move a
        # metric — only the string that gets written.
        repointed = _repoint_generated_inputs(sensor, scen)
        # CU-177: relative_to the YAML's own directory so file-path parameters
        # (e.g. emissivity_path, user_radiance_path) are stored portably.
        yaml_text = sensor.to_yaml(scope="inputs", relative_to=scen.yaml_path.parent)
    for dotpath in repointed:
        print(f"       {scen.id}: repointed {dotpath} -> inputs/ (CU-273)")
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
