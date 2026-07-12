"""Coordinate system, rotation matrices, and viewing geometry.

Conventions (RADIANT_Conventions.md §1 and §5):
  - Right-handed coordinate system. +Z toward target (along boresight).
    +X cross-track. +Y along-track.
  - Euler convention: ZYX (3-2-1). Yaw → Pitch → Roll.
    R = R_x(roll) @ R_y(pitch) @ R_z(yaw)
  - Pixel indexing: [row, col] = [y, x], 0-indexed.
  - All angles stored internally in radians.
  - Distances in meters.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import CoreValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mean Earth radius [m] — spherical approximation (consistent with US
# Standard 1976 and the atmosphere module's EARTH_RADIUS_M).
EARTH_RADIUS_M: float = 6_371_000.0

# ---------------------------------------------------------------------------
# Spherical-Earth geometry helpers
# ---------------------------------------------------------------------------
#
# These compute geometric slant range and ground incidence angle for a
# sensor at altitude h looking at off-nadir angle θ toward the Earth's
# surface.  They use ray-sphere intersection geometry:
#
#   Sensor at distance (R_E + h) from Earth center, line of sight at
#   angle θ from nadir.  The LOS intersects the sphere of radius R_E
#   at the near solution of the quadratic:
#
#     t² − 2(R_E+h)cos(θ)·t + [(R_E+h)² − R_E²] = 0
#
# NOTE: The atmosphere module (atmosphere/protocol.py) has its own
# slant-path computation for atmospheric transmission.  That formula
# computes the path length THROUGH an atmospheric shell, which is a
# different geometric problem.  These two implementations are
# intentionally independent.


def slant_range_spherical_m(altitude_m: float, zenith_rad: float) -> float:
    """Geometric slant range from sensor to Earth surface [m].

    Uses ray-sphere intersection on a spherical Earth of radius R_E.
    At zenith_rad=0, returns altitude_m exactly (nadir).

    Parameters
    ----------
    altitude_m : float
        Sensor altitude above the Earth surface [m].  Must be >= 0.
    zenith_rad : float
        Off-nadir look angle [rad].  Must be >= 0.  Must be less than
        the horizon angle arcsin(R_E / (R_E + h)).

    Returns
    -------
    float
        Line-of-sight distance from sensor to the target on the
        Earth surface [m].

    Raises
    ------
    ValueError
        If zenith_rad < 0 or the line of sight misses the Earth
        (beyond the horizon).
    """
    if zenith_rad < 0.0:
        raise CoreValidationError(
            f"slant_range_spherical_m: zenith_rad = {zenith_rad:.4f} rad "
            f"is negative.  Off-nadir angle must be >= 0."
        )
    if altitude_m <= 0.0:
        return 0.0

    R = EARTH_RADIUS_M
    Rh = R + altitude_m
    sin_zen = math.sin(zenith_rad)
    cos_zen = math.cos(zenith_rad)

    # Discriminant of the ray-sphere quadratic:
    #   disc = R_E² − (R_E + h)² sin²(θ)
    # Negative discriminant means the LOS misses the Earth (below horizon).
    disc = R * R - Rh * Rh * sin_zen * sin_zen
    if disc < 0.0:
        # Compute the horizon angle for the error message.
        horizon_deg = math.degrees(math.asin(R / Rh))
        raise CoreValidationError(
            f"slant_range_spherical_m: zenith_rad = {zenith_rad:.4f} rad "
            f"({math.degrees(zenith_rad):.2f}°) is beyond the horizon.  "
            f"At altitude {altitude_m / 1000:.1f} km, the maximum off-nadir "
            f"angle is {horizon_deg:.2f}°.  Reduce zenith_rad or increase "
            f"altitude."
        )

    return Rh * cos_zen - math.sqrt(disc)


def incidence_angle_rad(altitude_m: float, zenith_rad: float) -> float:
    """Incidence angle at the ground for a sensor at altitude h [rad].

    The incidence angle is the angle between the line of sight and the
    local surface normal at the target point.  Due to Earth curvature,
    the incidence angle exceeds the sensor's off-nadir angle:

        sin(incidence) = (R_E + h) / R_E × sin(zenith)

    At nadir (zenith=0), incidence = 0.  At 45° from 600 km,
    incidence ≈ 50.7° (5.7° larger than zenith).

    Parameters
    ----------
    altitude_m : float
        Sensor altitude above Earth surface [m].  Must be >= 0.
    zenith_rad : float
        Off-nadir look angle [rad].  Must be >= 0.

    Returns
    -------
    float
        Ground incidence angle [rad].

    Raises
    ------
    ValueError
        If zenith_rad < 0 or the incidence would exceed 90° (below horizon).
    """
    if zenith_rad < 0.0:
        raise CoreValidationError(
            f"incidence_angle_rad: zenith_rad = {zenith_rad:.4f} rad "
            f"is negative.  Off-nadir angle must be >= 0."
        )
    if altitude_m <= 0.0 or zenith_rad == 0.0:
        return 0.0 if zenith_rad == 0.0 else zenith_rad

    R = EARTH_RADIUS_M
    sin_inc = (R + altitude_m) / R * math.sin(zenith_rad)

    if sin_inc > 1.0:
        horizon_deg = math.degrees(math.asin(R / (R + altitude_m)))
        raise CoreValidationError(
            f"incidence_angle_rad: zenith_rad = {zenith_rad:.4f} rad "
            f"({math.degrees(zenith_rad):.2f}°) produces an incidence "
            f"angle beyond 90° (below horizon).  At altitude "
            f"{altitude_m / 1000:.1f} km, the maximum off-nadir angle "
            f"is {horizon_deg:.2f}°."
        )

    return math.asin(sin_inc)


# ---------------------------------------------------------------------------
# Rotation matrix utilities
# ---------------------------------------------------------------------------


def euler_to_rotation_matrix(
    yaw_rad: float, pitch_rad: float, roll_rad: float
) -> npt.NDArray[np.float64]:
    """ZYX Euler angles to 3×3 rotation matrix.

    Convention: R = R_z(yaw) @ R_y(pitch) @ R_x(roll)
    This is the standard ZYX (3-2-1) body-fixed rotation sequence: a vector
    in the body frame is first rolled (X), then pitched (Y), then yawed (Z)
    to produce the inertial-frame vector.  Equivalently, reading right-to-left,
    the rotation is applied as: first roll about X'', then pitch about Y', then
    yaw about Z.

    The extraction formulas (rotation_matrix_to_euler) are consistent with
    this product order and match scipy Rotation.from_euler('ZYX', ...).

    Args:
        yaw_rad:   Rotation about Z-axis [rad].
        pitch_rad: Rotation about Y'-axis [rad].
        roll_rad:  Rotation about X''-axis [rad].

    Returns:
        (3, 3) float64 rotation matrix with det = 1 and R @ R.T = I.
    """
    cy, sy = math.cos(yaw_rad), math.sin(yaw_rad)
    cp, sp = math.cos(pitch_rad), math.sin(pitch_rad)
    cr, sr = math.cos(roll_rad), math.sin(roll_rad)

    R_z = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    R_y = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=np.float64)
    R_x = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=np.float64)

    return R_z @ R_y @ R_x


def rotation_matrix_to_euler(
    R: npt.NDArray[np.float64],
) -> tuple[float, float, float]:
    """Extract ZYX Euler angles from a 3×3 rotation matrix.

    Standard ZYX decomposition:
        pitch = arcsin(-R[2, 0])
        yaw   = arctan2(R[1, 0], R[0, 0])
        roll  = arctan2(R[2, 1], R[2, 2])

    Gimbal lock (pitch = ±90°) is not disambiguated — the returned yaw/roll
    may combine into a sum that is still correct for reconstruction purposes.

    Args:
        R: (3, 3) rotation matrix.

    Returns:
        (yaw_rad, pitch_rad, roll_rad)

    Raises:
        ValueError: If R is not a valid rotation matrix (det ≠ 1 or not orthogonal).
    """
    R = np.asarray(R, dtype=np.float64)
    if R.shape != (3, 3):
        raise CoreValidationError(
            f"rotation_matrix_to_euler: R must be (3, 3), got shape {R.shape}."
        )

    det = float(np.linalg.det(R))
    if abs(det - 1.0) > 1e-6:
        raise CoreValidationError(
            f"rotation_matrix_to_euler: R is not a valid rotation matrix. "
            f"det(R) = {det:.6f}, expected 1.0. "
            f"Check that R was constructed from euler_to_rotation_matrix or an equivalent."
        )

    ortho_err = float(np.max(np.abs(R @ R.T - np.eye(3))))
    if ortho_err > 1e-6:
        raise CoreValidationError(
            f"rotation_matrix_to_euler: R is not orthogonal. "
            f"max|R @ R.T - I| = {ortho_err:.2e}. "
            f"Check that R was constructed from euler_to_rotation_matrix or an equivalent."
        )

    pitch_rad = float(np.arcsin(np.clip(-R[2, 0], -1.0, 1.0)))
    yaw_rad = float(np.arctan2(R[1, 0], R[0, 0]))
    roll_rad = float(np.arctan2(R[2, 1], R[2, 2]))

    return yaw_rad, pitch_rad, roll_rad


# ---------------------------------------------------------------------------
# History (CU-094, ADR-0006 Phase 4)
# ---------------------------------------------------------------------------
# The ObserverGeometry / TargetGeometry / SceneGeometry dataclasses that
# lived here (flat-Earth scene model with unused attitude fields) were
# deleted 2026-07-12: zero consumers outside their own tests, superseded by
# GeometryStage (radiant.geometry) + the spherical solutions in
# core/viewing_triangle.py.  One canonical geometry model (Rule 27).
