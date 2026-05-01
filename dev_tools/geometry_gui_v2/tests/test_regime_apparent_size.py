"""Round-3 S7 — regime classifier matches apparent-size physics across
the (target size, target altitude, sensor params) parameter space.

Round-3 §0 defect 7: the round-three reel showed multiple frames where
a "physically large" target was tagged ``point_source``. Investigation
(``AUDIT_round3.md`` §10) confirmed the classifier is **not** wrong —
the targets in the orientation sweep (1–3 m linear extent) at the
default 600 km altitude with 1 m focal length and 10 µm pixel pitch
genuinely have angular extent ≤ 0.25·IFOV, which Rule 10 reads as
``point_source``. The apparent disagreement was a rendering-vs-reality
mismatch: the viewport renders at scene-meter scale so geometry stays
legible, while real apparent size is sub-pixel.

This file's job:

  1. Pin the rendering-vs-reality story with a concrete numeric anchor:
     the round-three default box at default altitude is point_source
     because its apparent size is ~0.22 px.
  2. Sweep the regime classifier over (size, altitude, sensor) so any
     future change that flips a branch threshold is caught.
  3. Verify the new ``target_apparent_size_pixels`` panel readout
     equals ``angular_extent / ifov`` and is unit-consistent with the
     classifier.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Final

import pytest

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.view_model import (
    _angular_extent_rad,
    classify_regime,
    target_apparent_size_pixels,
)


# Default state IFOV: 10 µm / 1.0 m = 10 µrad. The Rule-10 thresholds are
# 0.25·IFOV = 2.5 µrad and 2·IFOV = 20 µrad.
_DEFAULT_IFOV_RAD: Final[float] = 10e-6


def _state(**overrides: object) -> SceneState:
    return dataclasses.replace(SceneState.default(), **overrides)


# ---------------------------------------------------------------------------
# 1. Round-3 §0 defect 7 anchor — "large rendered box" really is point_source
# ---------------------------------------------------------------------------


def test_round3_default_box_classifies_as_point_source() -> None:
    """The round-three default box (1 m × 1 m × 2 m at 600 km, default
    sensor) classifies as ``point_source`` because its apparent size is
    ~0.22 px — well below the 0.25 threshold. The viewport renders the
    box at scene-meter scale (so geometry is legible), but the regime
    classifier is reading the *true* angular extent. There is no bug in
    the classifier; the on-screen "big box" is schematic.
    """
    state = _state(target_shape="box")
    regime, reason = classify_regime(state)
    apparent_px = target_apparent_size_pixels(state)

    assert regime is RadiometricRegime.POINT_SOURCE, (
        f"box default should be point_source ({reason}); got {regime.value}"
    )
    # 1×1×2 m box, view direction ~(-sin 20°, 0, cos 20°), default
    # observer attitude. Projected area = 2.0 m²; slant ≈ 638.5 km.
    # ang_ext = sqrt(2)/slant ≈ 2.21 µrad → 0.221 px at 10 µrad IFOV.
    assert apparent_px == pytest.approx(0.221, abs=0.01), (
        f"apparent size = {apparent_px:.4f} px; expected ~0.22 px (this "
        f"value is the rendering-vs-reality story for round-3 defect 7)"
    )


def test_round3_default_flat_plate_also_point_source() -> None:
    """Same story for the default 1×2 m flat plate."""
    state = _state(target_shape="flat_plate")
    regime, _ = classify_regime(state)
    assert regime is RadiometricRegime.POINT_SOURCE


# ---------------------------------------------------------------------------
# 2. Sweep the classifier across (size, altitude, sensor params)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alt_km, radius_m, focal_length_m, expected",
    [
        # Default sensor (f=1m, p=10µm → IFOV=10 µrad). Sweep target
        # altitude with a 1 m sphere — projected area is fixed (πr² =
        # 3.14 m²) so the boundary is altitude-driven.
        #   At 600 km slant ≈ 638.5 km, ang_ext = sqrt(πr²)/slant
        #   ≈ 2.78 µrad → ratio ≈ 0.278 → sub_pixel (0.25 < r < 2).
        #   At 2000 km, ang_ext ≈ 0.85 µrad → ratio ≈ 0.085 → point_source.
        (600, 1.0, 1.0, RadiometricRegime.SUB_PIXEL),
        (2000, 1.0, 1.0, RadiometricRegime.POINT_SOURCE),
        # Larger target: 5 m sphere at 600 km gives ang_ext ≈ 13.9 µrad
        # → ratio 1.39 → still sub_pixel (just below 2·IFOV). Going up
        # to a 10 m sphere clears the extended threshold.
        (600, 5.0, 1.0, RadiometricRegime.SUB_PIXEL),
        (600, 10.0, 1.0, RadiometricRegime.EXTENDED),
        # Longer focal length tightens IFOV. At f=10 m the IFOV
        # drops to 1.0 µrad. A 1 m sphere at 600 km (ang_ext 2.78
        # µrad → ratio 2.78) clears the 2·IFOV extended threshold.
        (600, 1.0, 10.0, RadiometricRegime.EXTENDED),
        # Shorter focal length widens IFOV. At f=0.5 m the IFOV is
        # 20 µrad and a 1 m sphere at 600 km falls to point_source.
        (600, 1.0, 0.5, RadiometricRegime.POINT_SOURCE),
    ],
)
def test_regime_sweep_size_altitude_sensor(
    alt_km: int,
    radius_m: float,
    focal_length_m: float,
    expected: RadiometricRegime,
) -> None:
    """The regime classifier produces the right Rule-10 branch across
    the parameter space the round-3 reel sweeps over. Any future change
    that flips a threshold is caught here."""
    state = _state(
        observer_altitude_m=float(alt_km) * 1_000.0,
        target_shape="sphere",
        target_radius_m=radius_m,
        focal_length_m=focal_length_m,
    )
    regime, reason = classify_regime(state)
    assert regime is expected, (
        f"alt={alt_km} km, R={radius_m} m, f={focal_length_m} m: "
        f"got {regime.value} ({reason}); expected {expected.value}"
    )


# ---------------------------------------------------------------------------
# 3. apparent_size_pixels readout is unit-consistent with the classifier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", ["sphere", "box", "cylinder", "cone", "flat_plate"])
def test_apparent_size_equals_ang_ext_over_ifov(shape: str) -> None:
    """The new panel readout (round-3 S7) is exactly ``ang_ext / ifov``
    for every shape. Catches a regression where the panel value drifts
    from the classifier's threshold computation."""
    state = _state(target_shape=shape)
    ang_ext = _angular_extent_rad(state)
    ifov = state.pixel_pitch_m / state.focal_length_m
    expected_px = ang_ext / ifov

    assert target_apparent_size_pixels(state) == pytest.approx(
        expected_px, rel=1e-12
    )


def test_apparent_size_inf_at_zero_slant() -> None:
    """Degenerate case: target stacked exactly under observer. Slant=0
    drives ang_ext to +inf (matches the classifier convention) and the
    panel formatter renders this as "∞ px"."""
    # Place the target at the observer's altitude and zero look angle
    # so slant collapses to zero.
    state = _state(
        target_altitude_m=600_000.0,
        observer_look_angle_rad=0.0,
    )
    assert math.isinf(target_apparent_size_pixels(state))


# ---------------------------------------------------------------------------
# 4. The "rendering-vs-reality" story holds across the orientation sweep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "yaw_deg, pitch_deg, roll_deg",
    [(0, 0, 0), (45, 0, 0), (0, 30, 0), (0, 0, 30), (45, 30, 15)],
)
def test_box_orientation_sweep_apparent_size_below_one_pixel(
    yaw_deg: float, pitch_deg: float, roll_deg: float
) -> None:
    """For every orientation in the round-three reel's box sweep, the
    box's true apparent size on the sensor is < 1 pixel (regardless of
    what the rendered viewport box appears to be). This is the
    documentation S7 ships in test form: defect 7 is not a classifier
    bug, it is a rendering-vs-reality story."""
    state = _state(
        target_shape="box",
        target_yaw_rad=math.radians(yaw_deg),
        target_pitch_rad=math.radians(pitch_deg),
        target_roll_rad=math.radians(roll_deg),
    )
    apparent_px = target_apparent_size_pixels(state)
    assert apparent_px < 1.0, (
        f"box (yaw={yaw_deg}, pitch={pitch_deg}, roll={roll_deg}): "
        f"apparent size = {apparent_px:.3f} px (expected < 1.0 — the "
        f"rendering-vs-reality mismatch is the round-3 §0 defect-7 story)"
    )
