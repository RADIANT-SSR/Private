"""Shared helpers for geometric primitive shapes.

Used by all shape modules in this package. Not part of the public API.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.core.geometry import euler_to_rotation_matrix
from radiant.source.errors import SourceValidationError


def validate_positive(name: str, value: float, field: str) -> None:
    """Raise ValueError if value is not strictly positive."""
    if value <= 0.0:
        raise SourceValidationError(
            f"{name}: {field} must be positive, got {value}. All dimensions are in meters."
        )


def view_to_body(
    view_direction: npt.NDArray[np.float64],
    yaw: float,
    pitch: float,
    roll: float,
) -> npt.NDArray[np.float64]:
    """Transform a scene-frame view direction into the body frame.

    R transforms body → scene, so R.T transforms scene → body.
    """
    v = np.asarray(view_direction, dtype=np.float64)
    if yaw == 0.0 and pitch == 0.0 and roll == 0.0:
        return v
    R = euler_to_rotation_matrix(yaw, pitch, roll)
    return R.T @ v
