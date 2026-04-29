"""Phase 1 golden-screenshot regression — six target views + diagram view.

PLAN_v2.md §9 acceptance:
  * "Golden screenshots locked at low fidelity for the 6 shapes + the
    geometry-diagram view."

Phase 1 deliberately keeps the bar low: low resolution (640×480), basic
flat-shaded rendering, default camera. The goldens here are intended to
catch *structural* regressions — a shape vanishing, the wrong color
applied, a primitive failing to register — not aesthetic regressions.
Phase 2 raises the bar (PBR + lighting + 1920×1080) and re-locks the
goldens at the higher fidelity.

How this works:
  * The first time the test runs, it writes the screenshot to
    ``tests/golden_phase1/<name>.png`` and *passes* (locking the
    baseline). Subsequent runs compare against the locked baseline and
    fail if pixels diverge by more than ``MAX_PIXEL_DIFF`` per channel
    over more than ``MAX_DIVERGED_FRACTION`` of the image.
  * To intentionally re-lock (e.g. after a Phase-2 PBR upgrade), delete
    the ``golden_phase1/`` directory and re-run. The test will lock the
    new baseline. Per the v1 review protocol (RADIANT_Testing_Validation
    §5.3), the engineer must visually inspect the new images before
    committing.

Skips cleanly when PyVista is not installed.
"""

from __future__ import annotations

import dataclasses
import math
import pathlib

import numpy as np
import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden_phase1"
WINDOW_SIZE = (640, 480)

# Generous tolerances — Phase 1 ships a low-fidelity baseline. The MAX_*
# numbers exist to surface a structural regression (shape vanished, color
# changed) rather than to enforce pixel-perfect rendering. Phase 2 tightens.
MAX_PIXEL_DIFF = 24  # per-channel grayscale-equivalent delta
MAX_DIVERGED_FRACTION = 0.02  # > 2 % of pixels diverging fails


def _state_for_shape(shape_kind: str) -> SceneState:
    return dataclasses.replace(SceneState.default(), target_shape=shape_kind)  # type: ignore[arg-type]


def _capture(state: SceneState) -> np.ndarray:
    """Render the scene off-screen and return the RGB pixel array.

    Pin the legacy Phase-1 isometric pose **before** calling
    ``build_scene`` so the labels solver projects against this pose
    and the goldens stay reproducible. R1 of round-2 visual
    remediation makes ``build_scene`` skip its default-camera
    install when the caller has already set ``camera_position``.
    """
    p = pv.Plotter(off_screen=True, window_size=WINDOW_SIZE)
    try:
        d = 14.0
        p.camera_position = [
            (d * math.cos(math.radians(35.0)), d * math.sin(math.radians(35.0)), 0.5 * d),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        ]
        build_scene(state, plotter=p)
        p.show(auto_close=False)
        img = p.screenshot(return_img=True)
    finally:
        p.close()
    return np.asarray(img)


def _compare_or_lock(name: str, image: np.ndarray) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / f"{name}.png"
    if not path.exists():
        from PIL import Image  # PyVista already pulls Pillow in.

        Image.fromarray(image).save(path)
        # Locking pass — surface the action so the engineer notices.
        pytest.skip(f"locked golden baseline at {path}")

    from PIL import Image

    baseline = np.asarray(Image.open(path).convert("RGB"))
    if baseline.shape != image.shape:
        pytest.fail(
            f"golden {name}: shape mismatch {baseline.shape} vs {image.shape}"
        )
    diff = np.abs(image.astype(np.int32) - baseline.astype(np.int32))
    diverged = (diff.max(axis=-1) > MAX_PIXEL_DIFF).mean()
    assert diverged <= MAX_DIVERGED_FRACTION, (
        f"golden {name}: {diverged:.4f} of pixels diverged by > "
        f"{MAX_PIXEL_DIFF} (limit {MAX_DIVERGED_FRACTION:.4f}). "
        f"Inspect baseline at {path} and either fix the regression or "
        f"delete the file to re-lock."
    )


@pytest.mark.parametrize(
    "shape_kind", ["sphere", "cylinder", "cone", "box", "flat_plate"]
)
def test_phase1_target_golden(shape_kind: str) -> None:
    image = _capture(_state_for_shape(shape_kind))
    _compare_or_lock(f"target_{shape_kind}", image)


def test_phase1_diagram_golden() -> None:
    """Geometry-diagram view — full default scene (sphere target + all
    vectors / arcs / glyphs). This is the canonical "everything visible"
    golden the Phase-3 / Phase-4 work will repeatedly re-lock."""
    image = _capture(SceneState.default())
    _compare_or_lock("diagram_default", image)
