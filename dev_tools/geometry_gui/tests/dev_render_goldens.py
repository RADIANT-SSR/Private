"""Generate Phase-2 golden artifacts for the scene builder.

Run from the repo root:

    python -m dev_tools.geometry_gui.tests.dev_render_goldens

Produces, under `dev_tools/geometry_gui/tests/golden/`:
  * `scene_<shape>.json`  — trace-signature golden consumed by
    `test_scene_builder.py::test_golden_scene_signature` (always written).
  * `scene_<shape>.png`   — visual screenshot per Phase-2 report (only if
    `kaleido` is importable; skipped with a printed note otherwise).

This script is *not* a pytest test — it is a developer helper for
regenerating goldens after an intentional mesh change.
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from dev_tools.geometry_gui.app.scene_builder import build_scene
from dev_tools.geometry_gui.app.state import SceneState

GOLDEN_DIR = Path(__file__).parent / "golden"
SHAPES = ("sphere", "cylinder", "flat_plate", "box", "cone")


def fixed_state(shape: str) -> SceneState:
    return dataclasses.replace(
        SceneState.default(),
        observer_yaw_rad=math.radians(5.0),
        observer_pitch_rad=math.radians(-2.0),
        observer_roll_rad=math.radians(1.0),
        target_yaw_rad=math.radians(20.0),
        target_pitch_rad=math.radians(-10.0),
        target_roll_rad=math.radians(7.0),
        target_shape=shape,  # type: ignore[arg-type]
    )


def trace_signature(traces: list) -> dict:
    sig = {"traces": []}
    for t in traces:
        entry: dict = {"name": getattr(t, "name", None), "type": type(t).__name__}
        for axis in ("x", "y", "z"):
            vals = getattr(t, axis, None)
            if vals is None:
                entry[axis] = None
            else:
                entry[axis] = np.round(np.asarray(vals, dtype=np.float64), 9).tolist()
        for face_attr in ("i", "j", "k"):
            vals = getattr(t, face_attr, None)
            if vals is not None:
                entry[face_attr] = [int(v) for v in np.asarray(vals)]
        sig["traces"].append(entry)
    return sig


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import kaleido  # noqa: F401  — only checked for presence

        png_ok = True
    except ImportError:
        png_ok = False
        print("[info] `kaleido` not installed — JSON goldens only. "
              "Install with `pip install kaleido` to also write PNGs.")

    for shape in SHAPES:
        state = fixed_state(shape)
        traces = build_scene(state)

        # JSON golden — always.
        json_path = GOLDEN_DIR / f"scene_{shape}.json"
        with json_path.open("w") as fh:
            json.dump(trace_signature(traces), fh, indent=2, sort_keys=True)
        print(f"[ok]   wrote {json_path.relative_to(Path.cwd())}")

        # PNG screenshot — only if kaleido is available.
        if png_ok:
            fig = go.Figure(data=traces)
            fig.update_layout(
                scene={"aspectmode": "cube"},
                title=f"RADIANT geometry — {shape}",
                showlegend=False,
            )
            png_path = GOLDEN_DIR / f"scene_{shape}.png"
            fig.write_image(str(png_path), width=900, height=700)
            print(f"[ok]   wrote {png_path.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
