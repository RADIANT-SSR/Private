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

    R_z = np.array(
        [[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    R_y = np.array(
        [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=np.float64
    )
    R_x = np.array(
        [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=np.float64
    )

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
        raise ValueError(
            f"rotation_matrix_to_euler: R must be (3, 3), got shape {R.shape}."
        )

    det = float(np.linalg.det(R))
    if abs(det - 1.0) > 1e-6:
        raise ValueError(
            f"rotation_matrix_to_euler: R is not a valid rotation matrix. "
            f"det(R) = {det:.6f}, expected 1.0. "
            f"Check that R was constructed from euler_to_rotation_matrix or an equivalent."
        )

    ortho_err = float(np.max(np.abs(R @ R.T - np.eye(3))))
    if ortho_err > 1e-6:
        raise ValueError(
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
            raise ValueError(
                f"ObserverGeometry: altitude_m = {self.altitude_m} m is negative. "
                f"Observer must be above the reference plane. "
                f"Set altitude_m >= 0."
            )
        if not (0.0 <= self.look_angle_rad < math.pi / 2):
            raise ValueError(
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
            raise ValueError(
                f"gsd_m: focal_length_m must be > 0, got {focal_length_m}. "
                f"Set focal_length_m to the effective focal length of the optics in meters."
            )
        if pixel_pitch_m <= 0:
            raise ValueError(
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
            raise ValueError(
                f"ifov_rad: focal_length_m must be > 0, got {focal_length_m}. "
                f"Set focal_length_m to the effective focal length of the optics in meters."
            )
        if pixel_pitch_m <= 0:
            raise ValueError(
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
