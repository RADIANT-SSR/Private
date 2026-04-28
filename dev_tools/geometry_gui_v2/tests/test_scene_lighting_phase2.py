"""Phase 2 acceptance — sun lighting drives a visible terminator.

PLAN_v2.md §10 acceptance:
  * "Sphere target shows a clear terminator that rotates with the sun
    slider."
  * "Image diff vs Phase 1 goldens shows the expected lighting and shadow
    changes; no other unexplained pixel movement." — covered by the
    re-locked goldens in ``test_scene_goldens_phase1.py``.

The test below renders the default sphere scene at two sun-zenith values,
extracts the brightness of the lit-side and dark-side hemispheres of the
target, and asserts the lit/dark contrast is large enough to read as a
terminator (>= ``MIN_TERMINATOR_CONTRAST``). It then rotates the sun
azimuth by 180° and asserts the lit/dark sides flip.

Skips cleanly when PyVista is not installed.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

pytest.importorskip("pyvista")

import pyvista as pv  # noqa: E402

from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.scene.builder import build_scene  # noqa: E402

# Brightness contrast (mean RGB) between the lit hemisphere and the dark
# hemisphere of the sphere. With PBR + the configured sun + ambient fill,
# the lit side should average notably brighter than the dark side. 15
# grayscale levels is the conservative floor; in practice the contrast is
# 40+ levels.
MIN_TERMINATOR_CONTRAST = 15.0
WINDOW = (480, 360)


def _render_with_camera_at_y_minus(state: SceneState) -> np.ndarray:
    """Render the scene from a fixed camera position along -Y looking +Y.

    The camera sits close to the target so the sphere fills most of the
    viewport — we want sphere pixels to dominate so that hemisphere
    brightness is a clean signal, not background noise.

    With this camera, the +X half of the rendered image corresponds to
    the +X side of the target (lit when sun azimuth points +X), and the
    -X half corresponds to the -X side (dark when sun is +X).
    """
    p = pv.Plotter(off_screen=True, window_size=WINDOW)
    try:
        build_scene(state, plotter=p)
        p.camera_position = [(0.0, -3.5, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        p.show(auto_close=False)
        img = p.screenshot(return_img=True)
    finally:
        p.close()
    return np.asarray(img)


def _hemisphere_brightness(image: np.ndarray) -> tuple[float, float]:
    """Return (target-pixel mean on the -X side, target-pixel mean on the
    +X side). The mask isolates the *target body* (teal #2EC4B6) and
    excludes both viewport background and white screen-space labels.

    Mask criterion: green − red ≥ 20. The target (#2EC4B6 → 196−46=150
    in fully-lit pixels, ~30+ even in deep shade) clears this; the
    background (#1F242B → 36−31=5) and white text (R=G=B) do not.
    """
    h, w = image.shape[:2]
    band = image[h // 4 : 3 * h // 4, :]
    is_teal = band[..., 1].astype(np.int32) - band[..., 0].astype(np.int32) >= 20
    left_mask = is_teal.copy()
    left_mask[:, w // 2 :] = False
    right_mask = is_teal.copy()
    right_mask[:, : w // 2] = False
    if not left_mask.any() or not right_mask.any():
        return 0.0, 0.0
    left = band[left_mask].mean()
    right = band[right_mask].mean()
    return float(left), float(right)


def test_sun_at_plus_x_lights_plus_x_hemisphere() -> None:
    """Sun at azimuth 0 (along +X) → +X hemisphere brighter than -X."""
    # solar zenith = 70° so the sun is well above the horizon and the
    # azimuth direction is meaningful (cos 70° = 0.34 in +Z, sin 70° = 0.94
    # in +X).
    state = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=math.radians(70.0),
        relative_azimuth_rad=0.0,  # sun azimuth = 0 → along +X
    )
    image = _render_with_camera_at_y_minus(state)
    left, right = _hemisphere_brightness(image)
    contrast = right - left
    assert contrast >= MIN_TERMINATOR_CONTRAST, (
        f"Sun along +X did not produce a terminator: +X side {right:.1f}, "
        f"-X side {left:.1f}, contrast {contrast:.1f} < "
        f"{MIN_TERMINATOR_CONTRAST}"
    )


def test_sun_at_minus_x_lights_minus_x_hemisphere() -> None:
    """Rotating sun azimuth by 180° flips the lit hemisphere."""
    state = dataclasses.replace(
        SceneState.default(),
        solar_zenith_rad=math.radians(70.0),
        relative_azimuth_rad=math.pi,  # sun azimuth = 180° → along -X
    )
    image = _render_with_camera_at_y_minus(state)
    left, right = _hemisphere_brightness(image)
    contrast = left - right
    assert contrast >= MIN_TERMINATOR_CONTRAST, (
        f"Sun along -X did not produce a terminator on -X side: -X "
        f"side {left:.1f}, +X side {right:.1f}, contrast {contrast:.1f} "
        f"< {MIN_TERMINATOR_CONTRAST}"
    )
