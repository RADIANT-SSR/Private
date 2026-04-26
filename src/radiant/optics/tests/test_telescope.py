"""Tests for radiant.optics.telescope.

Category B validation for 2B.3 Mode 1 (scalar transmission):
construction with the (D, f, f/#) consistency group, flat-spectrum
throughput broadcast, area / solid-angle passthroughs, boundary
failures, and serialization round-trip.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.aperture import CircularAperture
from radiant.optics.telescope import ScalarTelescope


def _aperture(d: float = 0.5, eps: float = 0.0) -> CircularAperture:
    return CircularAperture(aperture_diameter_m=d, obscuration_ratio=eps)


# ---------------------------------------------------------------------------
# Construction / consistency group
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_scalar_telescope_basic_construction() -> None:
    scope = ScalarTelescope(aperture=_aperture(0.5), transmission_scalar=0.7, focal_length_m=2.5)
    assert scope.resolved_f_number == pytest.approx(5.0, rel=1e-12)
    assert scope.aperture_area_m2 == pytest.approx(math.pi * (0.25) ** 2, rel=1e-12)
    assert scope.solid_angle_sr == pytest.approx(math.pi / (4 * 25.0), rel=1e-12)


@pytest.mark.level0
def test_scalar_telescope_accepts_consistent_three_inputs() -> None:
    scope = ScalarTelescope(
        aperture=_aperture(0.4),
        transmission_scalar=0.6,
        focal_length_m=3.2,
        f_number=8.0,
    )
    assert scope.resolved_f_number == 8.0


@pytest.mark.level0
def test_scalar_telescope_rejects_inconsistent_three_inputs() -> None:
    with pytest.raises(ValueError, match="over-specified and inconsistent"):
        ScalarTelescope(
            aperture=_aperture(0.4),
            transmission_scalar=0.6,
            focal_length_m=3.2,
            f_number=10.0,  # implied is 8.0
        )


@pytest.mark.level0
def test_scalar_telescope_obscuration_reduces_area() -> None:
    scope_unobs = ScalarTelescope(
        aperture=_aperture(0.6, 0.0), transmission_scalar=0.8, focal_length_m=4.8
    )
    scope_obs = ScalarTelescope(
        aperture=_aperture(0.6, 0.3), transmission_scalar=0.8, focal_length_m=4.8
    )
    assert scope_obs.aperture_area_m2 < scope_unobs.aperture_area_m2
    # Area ratio equals (1 − ε²)
    ratio = scope_obs.aperture_area_m2 / scope_unobs.aperture_area_m2
    assert ratio == pytest.approx(1.0 - 0.3**2, rel=1e-12)


# ---------------------------------------------------------------------------
# Transmission output
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_transmission_is_flat_and_on_requested_grid() -> None:
    scope = ScalarTelescope(aperture=_aperture(0.3), transmission_scalar=0.65, focal_length_m=1.2)
    grid = np.linspace(0.4, 14.0, 201)
    tau = scope.transmission(grid)
    assert tau.unit == ""
    assert np.array_equal(tau.wavelength_um, grid)
    assert np.allclose(tau.values, 0.65, atol=0.0)


@pytest.mark.level0
def test_transmission_deterministic() -> None:
    scope = ScalarTelescope(aperture=_aperture(), transmission_scalar=0.5, focal_length_m=2.0)
    grid = np.linspace(1.0, 5.0, 64)
    a = scope.transmission(grid).values
    b = scope.transmission(grid).values
    assert np.array_equal(a, b)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_transmission_scalar_above_one_rejected() -> None:
    with pytest.raises(ValueError, match="transmission_scalar"):
        ScalarTelescope(aperture=_aperture(), transmission_scalar=1.01, focal_length_m=1.0)


@pytest.mark.level0
def test_transmission_scalar_negative_rejected() -> None:
    with pytest.raises(ValueError, match="transmission_scalar"):
        ScalarTelescope(aperture=_aperture(), transmission_scalar=-0.1, focal_length_m=1.0)


@pytest.mark.level0
def test_transmission_rejects_bad_grid() -> None:
    scope = ScalarTelescope(aperture=_aperture(), transmission_scalar=0.5, focal_length_m=2.0)
    with pytest.raises(ValueError, match="ascending"):
        scope.transmission(np.array([2.0, 1.0, 3.0]))
    with pytest.raises(ValueError, match="positive"):
        scope.transmission(np.array([0.0, 1.0]))
    with pytest.raises(ValueError, match="1-D"):
        scope.transmission(np.ones((3, 3)))
    with pytest.raises(ValueError, match="at least"):
        scope.transmission(np.array([1.0]))


@pytest.mark.level0
def test_zero_focal_length_rejected() -> None:
    with pytest.raises(ValueError, match="focal_length_m"):
        ScalarTelescope(aperture=_aperture(), transmission_scalar=0.5, focal_length_m=0.0)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_scalar_telescope_round_trip() -> None:
    scope = ScalarTelescope(
        aperture=_aperture(0.8, 0.2),
        transmission_scalar=0.72,
        focal_length_m=6.4,
        name="primary_telescope",
    )
    d = scope.to_dict()
    assert d["aperture"]["kind"] == "circular"
    scope2 = ScalarTelescope.from_dict(d)
    assert scope2.aperture.aperture_diameter_m == scope.aperture.aperture_diameter_m
    assert scope2.aperture.obscuration_ratio == scope.aperture.obscuration_ratio
    assert scope2.transmission_scalar == scope.transmission_scalar
    assert scope2.focal_length_m == scope.focal_length_m
    assert scope2.resolved_f_number == scope.resolved_f_number
    assert scope2.name == scope.name
