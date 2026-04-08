"""Tests for radiant.core.geometry — coordinate system and viewing geometry.

All tests are Level 0: verified against analytic / independent values.
pytest.approx always uses explicit rel= or abs= tolerance.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.geometry import (
    ObserverGeometry,
    SceneGeometry,
    TargetGeometry,
    euler_to_rotation_matrix,
    rotation_matrix_to_euler,
)

# ---------------------------------------------------------------------------
# Rotation matrix tests (Tests 1–9)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_rotation_matrix_identity() -> None:
    """Euler (0, 0, 0) → identity matrix."""
    R = euler_to_rotation_matrix(0.0, 0.0, 0.0)
    assert pytest.approx(np.eye(3), abs=1e-15) == R


@pytest.mark.level0
def test_rotation_matrix_yaw_90() -> None:
    """Yaw 90° about Z: x→y, y→-x, z unchanged."""
    R = euler_to_rotation_matrix(math.pi / 2, 0.0, 0.0)
    expected = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    assert pytest.approx(expected, abs=1e-15) == R


@pytest.mark.level0
def test_rotation_matrix_pitch_90() -> None:
    """Pitch 90° about Y: z→x, x→-z, y unchanged."""
    R = euler_to_rotation_matrix(0.0, math.pi / 2, 0.0)
    expected = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    assert pytest.approx(expected, abs=1e-15) == R


@pytest.mark.level0
def test_rotation_matrix_roll_90() -> None:
    """Roll 90° about X: y→z, z→-y, x unchanged."""
    R = euler_to_rotation_matrix(0.0, 0.0, math.pi / 2)
    expected = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
    assert pytest.approx(expected, abs=1e-15) == R


@pytest.mark.level0
def test_rotation_matrix_orthogonality() -> None:
    """R @ R.T == I for arbitrary angles."""
    R = euler_to_rotation_matrix(0.3, -0.7, 1.1)
    product = R @ R.T
    assert product == pytest.approx(np.eye(3), abs=1e-14)


@pytest.mark.level0
def test_rotation_matrix_determinant() -> None:
    """det(R) == 1 for arbitrary angles (proper rotation, no reflection)."""
    R = euler_to_rotation_matrix(0.3, -0.7, 1.1)
    assert float(np.linalg.det(R)) == pytest.approx(1.0, abs=1e-14)


@pytest.mark.level0
def test_rotation_matrix_non_commutativity() -> None:
    """Matrix multiplication is non-commutative for different rotation axes."""
    Ry = euler_to_rotation_matrix(0.1, 0.0, 0.0)   # yaw only
    Rp = euler_to_rotation_matrix(0.0, 0.2, 0.0)   # pitch only
    AB = Ry @ Rp
    BA = Rp @ Ry
    # They must differ; any element difference proves non-commutativity
    assert not np.allclose(AB, BA, atol=1e-15)


@pytest.mark.level0
def test_rotation_matrix_round_trip() -> None:
    """euler → matrix → euler reproduces original angles."""
    yaw_in, pitch_in, roll_in = 0.3, 0.1, -0.2
    R = euler_to_rotation_matrix(yaw_in, pitch_in, roll_in)
    yaw_out, pitch_out, roll_out = rotation_matrix_to_euler(R)
    assert yaw_out == pytest.approx(yaw_in, abs=1e-12)
    assert pitch_out == pytest.approx(pitch_in, abs=1e-12)
    assert roll_out == pytest.approx(roll_in, abs=1e-12)


@pytest.mark.level0
def test_rotation_matrix_to_euler_rejects_non_orthogonal() -> None:
    """rotation_matrix_to_euler raises ValueError for a non-orthogonal matrix."""
    bad = np.array([[2.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    with pytest.raises(ValueError):
        rotation_matrix_to_euler(bad)


# ---------------------------------------------------------------------------
# ObserverGeometry tests (Tests 10–13)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_observer_geometry_nadir_construction() -> None:
    """Valid nadir geometry constructs without error."""
    obs = ObserverGeometry(altitude_m=500_000.0, look_angle_rad=0.0)
    assert obs.altitude_m == pytest.approx(500_000.0, rel=1e-12)
    assert obs.look_angle_rad == pytest.approx(0.0, abs=1e-15)


@pytest.mark.level0
def test_observer_geometry_negative_altitude_raises() -> None:
    """Negative altitude raises ValueError mentioning 'altitude_m'."""
    with pytest.raises(ValueError, match="altitude_m"):
        ObserverGeometry(altitude_m=-1.0, look_angle_rad=0.0)


@pytest.mark.level0
def test_observer_geometry_look_angle_at_horizon_raises() -> None:
    """look_angle_rad == π/2 raises ValueError mentioning 'horizon'."""
    with pytest.raises(ValueError, match="horizon"):
        ObserverGeometry(altitude_m=500_000.0, look_angle_rad=math.pi / 2)


@pytest.mark.level0
def test_observer_geometry_serialization() -> None:
    """to_dict / from_dict round-trip preserves all fields."""
    obs = ObserverGeometry(
        altitude_m=500_000.0,
        look_angle_rad=0.2,
        yaw_rad=0.01,
        pitch_rad=-0.005,
        roll_rad=0.003,
    )
    d = obs.to_dict()
    obs2 = ObserverGeometry.from_dict(d)
    assert obs2.altitude_m == pytest.approx(obs.altitude_m, rel=1e-15)
    assert obs2.look_angle_rad == pytest.approx(obs.look_angle_rad, rel=1e-15)
    assert obs2.yaw_rad == pytest.approx(obs.yaw_rad, rel=1e-15)
    assert obs2.pitch_rad == pytest.approx(obs.pitch_rad, rel=1e-15)
    assert obs2.roll_rad == pytest.approx(obs.roll_rad, rel=1e-15)


# ---------------------------------------------------------------------------
# SceneGeometry tests (Tests 14–24)
# ---------------------------------------------------------------------------


def _make_scene(
    observer_alt_m: float,
    look_angle_rad: float,
    target_alt_m: float = 0.0,
) -> SceneGeometry:
    obs = ObserverGeometry(altitude_m=observer_alt_m, look_angle_rad=look_angle_rad)
    tgt = TargetGeometry(altitude_m=target_alt_m)
    return SceneGeometry(observer=obs, target=tgt)


@pytest.mark.level0
def test_slant_range_nadir() -> None:
    """At nadir (look_angle=0), slant_range == altitude."""
    scene = _make_scene(600_000.0, 0.0)
    assert scene.slant_range_m == pytest.approx(600_000.0, abs=1e-10)


@pytest.mark.level0
def test_slant_range_45deg() -> None:
    """At 45°, slant_range == altitude * sqrt(2).

    cos(45°) = 1/√2 → slant = altitude / (1/√2) = altitude * √2.
    """
    alt = 600_000.0
    scene = _make_scene(alt, math.radians(45.0))
    assert scene.slant_range_m == pytest.approx(alt * math.sqrt(2.0), rel=1e-12)


@pytest.mark.level0
def test_slant_range_60deg() -> None:
    """At 60°, slant_range == altitude * 2.

    cos(60°) = 0.5 → slant = altitude / 0.5 = 2 * altitude.
    """
    alt = 600_000.0
    scene = _make_scene(alt, math.radians(60.0))
    assert scene.slant_range_m == pytest.approx(2.0 * alt, rel=1e-12)


@pytest.mark.level0
def test_ground_range_nadir() -> None:
    """At nadir, ground_range == 0."""
    scene = _make_scene(600_000.0, 0.0)
    assert scene.ground_range_m == pytest.approx(0.0, abs=1e-10)


@pytest.mark.level0
def test_ground_range_45deg() -> None:
    """At 45°, ground_range == altitude.

    tan(45°) = 1 → ground_range = altitude * 1 = altitude.
    """
    alt = 600_000.0
    scene = _make_scene(alt, math.radians(45.0))
    assert scene.ground_range_m == pytest.approx(alt, rel=1e-12)


@pytest.mark.level0
def test_gsd_nadir() -> None:
    """GSD at nadir: observer 600 km, fl=1.2 m, pitch=18 µm → 9.0 m.

    Analytic: GSD = 18e-6 * 600_000 / 1.2 = 9.0 m.
    """
    scene = _make_scene(600_000.0, 0.0)
    gsd = scene.gsd_m(focal_length_m=1.2, pixel_pitch_m=18e-6)
    assert gsd == pytest.approx(9.0, rel=1e-12)


@pytest.mark.level0
def test_gsd_invalid_focal_length() -> None:
    """gsd_m raises ValueError for focal_length_m == 0."""
    scene = _make_scene(600_000.0, 0.0)
    with pytest.raises(ValueError, match="focal_length_m"):
        scene.gsd_m(focal_length_m=0.0, pixel_pitch_m=18e-6)


@pytest.mark.level0
def test_gsd_invalid_pixel_pitch() -> None:
    """gsd_m raises ValueError for pixel_pitch_m == 0."""
    scene = _make_scene(600_000.0, 0.0)
    with pytest.raises(ValueError, match="pixel_pitch_m"):
        scene.gsd_m(focal_length_m=1.2, pixel_pitch_m=0.0)


@pytest.mark.level0
def test_ifov() -> None:
    """IFOV: fl=1.2 m, pitch=18 µm → 15 µrad.

    Analytic: IFOV = 18e-6 / 1.2 = 15e-6 rad.
    """
    scene = _make_scene(600_000.0, 0.0)
    ifov = scene.ifov_rad(focal_length_m=1.2, pixel_pitch_m=18e-6)
    assert ifov == pytest.approx(15e-6, rel=1e-12)


@pytest.mark.level0
def test_altitude_difference_with_target_elevation() -> None:
    """altitude_difference_m = observer.altitude_m - target.altitude_m."""
    obs = ObserverGeometry(altitude_m=500_000.0, look_angle_rad=0.0)
    tgt = TargetGeometry(altitude_m=1_000.0)
    scene = SceneGeometry(observer=obs, target=tgt)
    assert scene.altitude_difference_m == pytest.approx(499_000.0, rel=1e-15)


@pytest.mark.level0
def test_scene_geometry_serialization() -> None:
    """to_dict / from_dict round-trip preserves observer and target fields."""
    obs = ObserverGeometry(altitude_m=500_000.0, look_angle_rad=0.3)
    tgt = TargetGeometry(altitude_m=250.0)
    scene = SceneGeometry(observer=obs, target=tgt)

    d = scene.to_dict()
    scene2 = SceneGeometry.from_dict(d)

    assert scene2.observer.altitude_m == pytest.approx(obs.altitude_m, rel=1e-15)
    assert scene2.observer.look_angle_rad == pytest.approx(obs.look_angle_rad, rel=1e-15)
    assert scene2.target.altitude_m == pytest.approx(tgt.altitude_m, rel=1e-15)
