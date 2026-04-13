"""Tests for radiant.optics.element.

Category C validation for OpticalElement:
- Kirchhoff identity: epsilon + T + R == 1 for all element types
- Gold mirror emissivity from known reflectance
- Solid angle geometry calculations
- Violation detection for T + R > 1, mirror with nonzero T
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.optics.element import (
    ElementKind,
    KirchhoffViolationError,
    OpticalElement,
    make_lumped_element,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WL = np.linspace(3.0, 5.0, 50)


def _flat_spectral(value: float, name: str = "test") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=WL.copy(),
        values=np.full_like(WL, value),
        unit="",
        source="test fixture",
    )


# ---------------------------------------------------------------------------
# Level 0 — Key equations
# ---------------------------------------------------------------------------


class TestKirchhoffIdentity:
    """Verify epsilon + T + R == 1 for all element types."""

    def test_mirror_kirchhoff(self) -> None:
        """Mirror: epsilon = 1 - R, T = 0."""
        R = 0.98
        elem = OpticalElement(
            name="gold_mirror",
            kind=ElementKind.MIRROR,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.0, "tau"),
            reflectance=_flat_spectral(R, "rho"),
            diameter_m=0.3,
            distance_to_fpa_m=1.2,
        )
        eps = elem.emissivity.values
        np.testing.assert_allclose(
            eps + elem.reflectance.values,
            1.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(eps, 1.0 - R, atol=1e-12)

    def test_lens_kirchhoff(self) -> None:
        """Transmissive element: epsilon = 1 - T - R."""
        T, R = 0.95, 0.01
        elem = OpticalElement(
            name="coated_lens",
            kind=ElementKind.LENS,
            temperature_K=290.0,
            transmittance=_flat_spectral(T, "tau"),
            reflectance=_flat_spectral(R, "rho"),
            diameter_m=0.05,
            distance_to_fpa_m=0.3,
        )
        eps = elem.emissivity.values
        total = eps + elem.transmittance.values + elem.reflectance.values
        np.testing.assert_allclose(total, 1.0, atol=1e-12)
        np.testing.assert_allclose(eps, 1.0 - T - R, atol=1e-12)

    def test_gold_mirror_emissivity(self) -> None:
        """Truth anchor: gold mirror R=0.98 -> epsilon=0.02."""
        elem = OpticalElement(
            name="gold",
            kind=ElementKind.MIRROR,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.0),
            reflectance=_flat_spectral(0.98),
            diameter_m=0.3,
            distance_to_fpa_m=1.0,
        )
        np.testing.assert_allclose(
            elem.emissivity.values, 0.02, atol=1e-12,
        )

    def test_coated_lens_emissivity(self) -> None:
        """Truth anchor: T=0.95, R=0.01 -> epsilon=0.04."""
        elem = OpticalElement(
            name="lens",
            kind=ElementKind.LENS,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.95),
            reflectance=_flat_spectral(0.01),
            diameter_m=0.05,
            distance_to_fpa_m=0.2,
        )
        np.testing.assert_allclose(
            elem.emissivity.values, 0.04, atol=1e-12,
        )


class TestNetTransmittance:
    """Verify net_transmittance dispatches correctly."""

    def test_mirror_returns_reflectance(self) -> None:
        elem = OpticalElement(
            name="m",
            kind=ElementKind.MIRROR,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.0),
            reflectance=_flat_spectral(0.98),
            diameter_m=0.3,
            distance_to_fpa_m=1.0,
        )
        np.testing.assert_array_equal(
            elem.net_transmittance.values, elem.reflectance.values
        )

    def test_lens_returns_transmittance(self) -> None:
        elem = OpticalElement(
            name="l",
            kind=ElementKind.LENS,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.95),
            reflectance=_flat_spectral(0.01),
            diameter_m=0.05,
            distance_to_fpa_m=0.3,
        )
        np.testing.assert_array_equal(
            elem.net_transmittance.values, elem.transmittance.values
        )


# ---------------------------------------------------------------------------
# Solid angle
# ---------------------------------------------------------------------------


class TestSolidAngle:
    """Verify nearfield solid angle calculation."""

    def test_known_geometry(self) -> None:
        """Truth anchor: D=0.10m, d=0.50m -> Omega = pi*(0.05)^2/0.25 = 0.03142 sr."""
        elem = OpticalElement(
            name="test",
            kind=ElementKind.WINDOW,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.95),
            reflectance=_flat_spectral(0.01),
            diameter_m=0.10,
            distance_to_fpa_m=0.50,
        )
        expected = math.pi * (0.05) ** 2 / (0.50) ** 2
        assert elem.nearfield_solid_angle_sr == pytest.approx(expected, rel=1e-10)

    def test_large_geometry(self) -> None:
        """D=0.30m, d=1.20m -> Omega = pi*(0.15)^2/(1.44) = 0.04909 sr."""
        elem = OpticalElement(
            name="test",
            kind=ElementKind.MIRROR,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.0),
            reflectance=_flat_spectral(0.98),
            diameter_m=0.30,
            distance_to_fpa_m=1.20,
        )
        expected = math.pi * (0.15) ** 2 / (1.20) ** 2
        assert elem.nearfield_solid_angle_sr == pytest.approx(expected, rel=1e-10)

    def test_clipping_at_2pi(self) -> None:
        """Very large element very close to FPA clips at 2*pi."""
        elem = OpticalElement(
            name="close",
            kind=ElementKind.WINDOW,
            temperature_K=290.0,
            transmittance=_flat_spectral(0.95),
            reflectance=_flat_spectral(0.01),
            diameter_m=1.0,
            distance_to_fpa_m=0.01,
        )
        assert elem.nearfield_solid_angle_sr == pytest.approx(
            2.0 * math.pi, rel=1e-10,
        )


# ---------------------------------------------------------------------------
# Validation / error cases
# ---------------------------------------------------------------------------


class TestKirchhoffViolations:
    """Detect and reject Kirchhoff violations."""

    def test_mirror_nonzero_transmittance(self) -> None:
        with pytest.raises(KirchhoffViolationError, match="mirrors must have zero"):
            OpticalElement(
                name="bad_mirror",
                kind=ElementKind.MIRROR,
                temperature_K=290.0,
                transmittance=_flat_spectral(0.05),
                reflectance=_flat_spectral(0.90),
                diameter_m=0.3,
                distance_to_fpa_m=1.0,
            )

    def test_t_plus_r_exceeds_one(self) -> None:
        with pytest.raises(KirchhoffViolationError, match="T \\+ R"):
            OpticalElement(
                name="bad_lens",
                kind=ElementKind.LENS,
                temperature_K=290.0,
                transmittance=_flat_spectral(0.8),
                reflectance=_flat_spectral(0.3),
                diameter_m=0.05,
                distance_to_fpa_m=0.3,
            )


class TestValidation:
    """Input validation for OpticalElement."""

    def test_grid_mismatch(self) -> None:
        tau = SpectralData(
            name="tau",
            wavelength_um=np.linspace(3.0, 5.0, 50),
            values=np.full(50, 0.9),
            unit="",
            source="test",
        )
        rho = SpectralData(
            name="rho",
            wavelength_um=np.linspace(3.0, 6.0, 50),
            values=np.full(50, 0.01),
            unit="",
            source="test",
        )
        with pytest.raises(ValueError, match="wavelength grid"):
            OpticalElement(
                name="mismatch",
                kind=ElementKind.LENS,
                temperature_K=290.0,
                transmittance=tau,
                reflectance=rho,
                diameter_m=0.05,
                distance_to_fpa_m=0.3,
            )

    def test_negative_temperature(self) -> None:
        with pytest.raises(ValueError, match="temperature_K"):
            OpticalElement(
                name="cold",
                kind=ElementKind.WINDOW,
                temperature_K=-10.0,
                transmittance=_flat_spectral(0.95),
                reflectance=_flat_spectral(0.01),
                diameter_m=0.05,
                distance_to_fpa_m=0.3,
            )

    def test_zero_diameter(self) -> None:
        with pytest.raises(ValueError, match="diameter_m"):
            OpticalElement(
                name="zero",
                kind=ElementKind.WINDOW,
                temperature_K=290.0,
                transmittance=_flat_spectral(0.95),
                reflectance=_flat_spectral(0.01),
                diameter_m=0.0,
                distance_to_fpa_m=0.3,
            )

    def test_zero_distance(self) -> None:
        with pytest.raises(ValueError, match="distance_to_fpa_m"):
            OpticalElement(
                name="zero_d",
                kind=ElementKind.WINDOW,
                temperature_K=290.0,
                transmittance=_flat_spectral(0.95),
                reflectance=_flat_spectral(0.01),
                diameter_m=0.05,
                distance_to_fpa_m=0.0,
            )

    def test_transmittance_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="transmittance values"):
            OpticalElement(
                name="bad",
                kind=ElementKind.LENS,
                temperature_K=290.0,
                transmittance=_flat_spectral(1.1),
                reflectance=_flat_spectral(0.01),
                diameter_m=0.05,
                distance_to_fpa_m=0.3,
            )


# ---------------------------------------------------------------------------
# Lumped element factory
# ---------------------------------------------------------------------------


class TestMakeLumpedElement:
    """Verify the lumped element factory."""

    def test_basic(self) -> None:
        tau = _flat_spectral(0.7, "tau")
        elem = make_lumped_element(tau, 290.0, 0.3, 1.0)
        assert elem.kind == ElementKind.LUMPED
        np.testing.assert_allclose(elem.transmittance.values, 0.7, atol=1e-12)
        np.testing.assert_allclose(elem.reflectance.values, 0.0, atol=1e-12)
        np.testing.assert_allclose(elem.emissivity.values, 0.3, atol=1e-12)

    def test_kirchhoff_holds(self) -> None:
        tau = _flat_spectral(0.5, "tau")
        elem = make_lumped_element(tau, 300.0, 0.1, 0.5)
        total = elem.emissivity.values + elem.transmittance.values + elem.reflectance.values
        np.testing.assert_allclose(total, 1.0, atol=1e-12)
