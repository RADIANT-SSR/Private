"""Tests for radiant.core.geometry — coordinate system and viewing geometry.

All tests are Level 0: verified against analytic / independent values.
pytest.approx always uses explicit rel= or abs= tolerance.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.geometry import (
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
    Ry = euler_to_rotation_matrix(0.1, 0.0, 0.0)  # yaw only
    Rp = euler_to_rotation_matrix(0.0, 0.2, 0.0)  # pitch only
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


# ObserverGeometry / SceneGeometry tests removed with the dataclasses (CU-094).
