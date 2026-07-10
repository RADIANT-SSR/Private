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
from dataclasses import dataclass

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
# ObserverGeometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObserverGeometry:
    """Observer platform geometry.

    All angles stored in radians. Altitudes in meters.

    Attributes:
        altitude_m:      Observer altitude above ground/sea level [m]. Must be >= 0.
        look_angle_rad:  Off-nadir look angle [rad]. 0 = nadir. Must be in [0, π/2).
        yaw_rad:         Platform yaw [rad]. Default 0.
        pitch_rad:       Platform pitch [rad]. Default 0.
        roll_rad:        Platform roll [rad]. Default 0.
    """

    altitude_m: float
    look_angle_rad: float
    yaw_rad: float = 0.0
    pitch_rad: float = 0.0
    roll_rad: float = 0.0

    def __post_init__(self) -> None:
        if self.altitude_m < 0:
            raise CoreValidationError(
                f"ObserverGeometry: altitude_m = {self.altitude_m} m is negative. "
                f"Observer must be above the reference plane. "
                f"Set altitude_m >= 0."
            )
        if not (0.0 <= self.look_angle_rad < math.pi / 2):
            raise CoreValidationError(
                f"ObserverGeometry: look_angle_rad = {self.look_angle_rad:.4f} rad "
                f"({math.degrees(self.look_angle_rad):.2f}°) is out of range [0, π/2). "
                f"Look angle must be between nadir (0) and horizon (π/2 exclusive)."
            )

    def to_dict(self) -> dict[str, float]:
        """Serialize to a plain dictionary.

        Returns:
            Dict with keys: altitude_m, look_angle_rad, yaw_rad, pitch_rad, roll_rad.
        """
        return {
            "altitude_m": self.altitude_m,
            "look_angle_rad": self.look_angle_rad,
            "yaw_rad": self.yaw_rad,
            "pitch_rad": self.pitch_rad,
            "roll_rad": self.roll_rad,
        }

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> ObserverGeometry:
        """Deserialize from a plain dictionary.

        Args:
            d: Dict with keys: altitude_m, look_angle_rad, and optionally
               yaw_rad, pitch_rad, roll_rad.

        Returns:
            ObserverGeometry instance.
        """
        return cls(
            altitude_m=float(d["altitude_m"]),
            look_angle_rad=float(d["look_angle_rad"]),
            yaw_rad=float(d.get("yaw_rad", 0.0)),
            pitch_rad=float(d.get("pitch_rad", 0.0)),
            roll_rad=float(d.get("roll_rad", 0.0)),
        )


# ---------------------------------------------------------------------------
# TargetGeometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetGeometry:
    """Target scene geometry.

    Attributes:
        altitude_m: Target altitude above sea level [m]. Default 0.
    """

    altitude_m: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Serialize to a plain dictionary.

        Returns:
            Dict with key: altitude_m.
        """
        return {"altitude_m": self.altitude_m}

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> TargetGeometry:
        """Deserialize from a plain dictionary.

        Args:
            d: Dict with key: altitude_m.

        Returns:
            TargetGeometry instance.
        """
        return cls(altitude_m=float(d.get("altitude_m", 0.0)))


# ---------------------------------------------------------------------------
# SceneGeometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SceneGeometry:
    """Derived geometry quantities for a sensor-target scenario.

    Computed from ObserverGeometry + TargetGeometry. All angles in radians,
    distances in meters. Uses a flat-Earth approximation.

    Attributes:
        observer: Platform observer geometry.
        target:   Target scene geometry.
    """

    observer: ObserverGeometry
    target: TargetGeometry

    @property
    def altitude_difference_m(self) -> float:
        """Height of observer above target [m]."""
        return self.observer.altitude_m - self.target.altitude_m

    @property
    def slant_range_m(self) -> float:
        """Line-of-sight distance from observer to target [m].

        Flat-Earth approximation:
            slant_range = altitude_difference / cos(look_angle)

        Valid for look_angle < π/2 (enforced by ObserverGeometry).
        """
        return self.altitude_difference_m / math.cos(self.observer.look_angle_rad)

    @property
    def ground_range_m(self) -> float:
        """Horizontal distance from observer nadir to target [m].

        ground_range = altitude_difference * tan(look_angle)
        """
        return self.altitude_difference_m * math.tan(self.observer.look_angle_rad)

    def gsd_m(self, focal_length_m: float, pixel_pitch_m: float) -> float:
        """Ground sample distance [m].

        GSD = pixel_pitch * slant_range / focal_length

        Args:
            focal_length_m: Effective focal length [m]. Must be > 0.
            pixel_pitch_m:  Detector pixel pitch [m]. Must be > 0.

        Returns:
            GSD [m] at the slant range (accounts for off-nadir look angle).

        Raises:
            ValueError: If focal_length_m or pixel_pitch_m <= 0.
        """
        if focal_length_m <= 0:
            raise CoreValidationError(
                f"gsd_m: focal_length_m must be > 0, got {focal_length_m}. "
                f"Set focal_length_m to the effective focal length of the optics in meters."
            )
        if pixel_pitch_m <= 0:
            raise CoreValidationError(
                f"gsd_m: pixel_pitch_m must be > 0, got {pixel_pitch_m}. "
                f"Set pixel_pitch_m to the detector pixel pitch in meters."
            )
        return pixel_pitch_m * self.slant_range_m / focal_length_m

    def ifov_rad(self, focal_length_m: float, pixel_pitch_m: float) -> float:
        """Instantaneous field of view [rad].

        IFOV = pixel_pitch / focal_length

        Args:
            focal_length_m: Effective focal length [m]. Must be > 0.
            pixel_pitch_m:  Detector pixel pitch [m]. Must be > 0.

        Returns:
            IFOV [rad].

        Raises:
            ValueError: If focal_length_m or pixel_pitch_m <= 0.
        """
        if focal_length_m <= 0:
            raise CoreValidationError(
                f"ifov_rad: focal_length_m must be > 0, got {focal_length_m}. "
                f"Set focal_length_m to the effective focal length of the optics in meters."
            )
        if pixel_pitch_m <= 0:
            raise CoreValidationError(
                f"ifov_rad: pixel_pitch_m must be > 0, got {pixel_pitch_m}. "
                f"Set pixel_pitch_m to the detector pixel pitch in meters."
            )
        return pixel_pitch_m / focal_length_m

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain dictionary.

        Returns:
            Dict with keys: observer (dict), target (dict).
        """
        return {
            "observer": self.observer.to_dict(),
            "target": self.target.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> SceneGeometry:
        """Deserialize from a plain dictionary.

        Args:
            d: Dict with keys: observer (dict), target (dict).

        Returns:
            SceneGeometry instance.
        """
        observer = ObserverGeometry.from_dict(d["observer"])  # type: ignore[arg-type]
        target = TargetGeometry.from_dict(d.get("target", {}))  # type: ignore[arg-type]
        return cls(observer=observer, target=target)
