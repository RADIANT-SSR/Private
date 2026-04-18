"""Tests for radiant.optics.element.

Category C validation for OpticalElement:
- Kirchhoff identity for mirrors (eps = 1 - R)
- Simple refractive emissivity (eps = 0)
- Cavity model: T_sys, R_sys, eps_eff, energy conservation
- Factory functions for reflective, refractive, and cavity elements
- Solid angle geometry calculations
- Violation detection for T + R > 1, mirror with nonzero T
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.optics.cavity_model import CavityModel
from radiant.optics.element import (
    ElementKind,
    ElementTransferMode,
    KirchhoffViolationError,
    OpticalElement,
)
from radiant.optics.element_factories import (
    make_lumped_element,
    make_reflective_element,
    make_refractive_cavity_element,
    make_refractive_element,
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

    def test_lens_simple_refractive_eps_zero(self) -> None:
        """Simple refractive element (no cavity): epsilon = 0.

        When only T is known, the remaining 1-T is predominantly
        reflection, not absorption.  eps = 0 is the honest answer.
        """
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
        np.testing.assert_allclose(eps, 0.0, atol=1e-12)

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

    def test_simple_refractive_eps_zero_regardless_of_R(self) -> None:
        """Simple refractive: eps = 0 even when R is specified."""
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
            elem.emissivity.values, 0.0, atol=1e-12,
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
        assert elem.resolved_transfer_mode == ElementTransferMode.REFRACTIVE
        np.testing.assert_allclose(elem.transmittance.values, 0.7, atol=1e-12)
        np.testing.assert_allclose(elem.reflectance.values, 0.0, atol=1e-12)
        # Simple refractive: eps = 0 (absorption unknown).
        np.testing.assert_allclose(elem.emissivity.values, 0.0, atol=1e-12)

    def test_net_transmittance_is_T(self) -> None:
        """Lumped element transfer factor is transmittance."""
        tau = _flat_spectral(0.5, "tau")
        elem = make_lumped_element(tau, 300.0, 0.1, 0.5)
        np.testing.assert_allclose(
            elem.net_transmittance.values, 0.5, atol=1e-12,
        )


# ---------------------------------------------------------------------------
# CavityModel — pure radiometric computation
# ---------------------------------------------------------------------------


class TestCavityModel:
    """Category C validation for refractive cavity physics."""

    def test_uncoated_glass_no_absorption(self) -> None:
        """Truth anchor 1: uncoated glass window, no bulk absorption.

        R1=R2=0.04, T1=T2=0.96, alpha=0, n=1.5, d=3mm.
        beer = exp(0) = 1
        denom = 1 - 0.04*0.04*1 = 1 - 0.0016 = 0.9984
        T_sys = 0.96*1*0.96 / 0.9984 = 0.9216/0.9984 ≈ 0.92288
        R_sys = 0.04 + 0.96^2*0.04*1 / 0.9984 = 0.04 + 0.036864/0.9984 ≈ 0.07693
        eps_eff = 0.96*1.5^2*(1-1)/0.9984 = 0  (no absorption → no emission)
        Energy: T_sys + R_sys + eps_eff ≈ 0.92288 + 0.07693 + 0 ≈ 0.99981
        """
        cavity = CavityModel(
            R1=_flat_spectral(0.04, "R1"),
            T1=_flat_spectral(0.96, "T1"),
            R2=_flat_spectral(0.04, "R2"),
            T2=_flat_spectral(0.96, "T2"),
            alpha=_flat_spectral(0.0, "alpha"),
            n_refr=_flat_spectral(1.5, "n"),
            thickness_m=0.003,
        )
        t_sys = cavity.T_sys.values
        r_sys = cavity.R_sys.values
        eps = cavity.eps_eff.values

        np.testing.assert_allclose(t_sys, 0.9216 / 0.9984, rtol=1e-10)
        np.testing.assert_allclose(r_sys, 0.04 + 0.96**2 * 0.04 / 0.9984, rtol=1e-10)
        np.testing.assert_allclose(eps, 0.0, atol=1e-14)
        # Energy conservation.
        np.testing.assert_allclose(t_sys + r_sys + eps, 1.0, atol=1e-10)

    def test_absorbing_glass(self) -> None:
        """Truth anchor 2: glass with bulk absorption.

        R1=R2=0.04, T1=T2=0.96, alpha=10 1/m, n=1.5, d=3mm.
        beer = exp(-10*0.003) = exp(-0.03) ≈ 0.97045
        denom = 1 - 0.04*0.04*0.97045^2 ≈ 0.998494
        T_sys = 0.96*0.97045*0.96 / 0.998494
        R_sys = 0.04 + 0.96^2*0.04*0.97045^2 / 0.998494
        A_total = 1 - T_sys - R_sys (Kirchhoff emissivity)
        """
        import math

        cavity = CavityModel(
            R1=_flat_spectral(0.04, "R1"),
            T1=_flat_spectral(0.96, "T1"),
            R2=_flat_spectral(0.04, "R2"),
            T2=_flat_spectral(0.96, "T2"),
            alpha=_flat_spectral(10.0, "alpha"),
            n_refr=_flat_spectral(1.5, "n"),
            thickness_m=0.003,
        )
        beer = math.exp(-10.0 * 0.003)
        denom = 1.0 - 0.04 * 0.04 * beer**2
        expected_t = 0.96 * beer * 0.96 / denom
        expected_r = 0.04 + 0.96**2 * 0.04 * beer**2 / denom

        t_sys = cavity.T_sys.values
        r_sys = cavity.R_sys.values

        np.testing.assert_allclose(t_sys, expected_t, rtol=1e-10)
        np.testing.assert_allclose(r_sys, expected_r, rtol=1e-10)
        # Absorptance > 0 (there is bulk absorption).
        absorptance = 1.0 - t_sys - r_sys
        assert np.all(absorptance > 0)
        # Energy conservation: T + R + A = 1.
        np.testing.assert_allclose(t_sys + r_sys + absorptance, 1.0, atol=1e-12)

    def test_high_absorption_limit(self) -> None:
        """High absorption: T_sys → 0, absorptance large."""
        cavity = CavityModel(
            R1=_flat_spectral(0.04, "R1"),
            T1=_flat_spectral(0.96, "T1"),
            R2=_flat_spectral(0.04, "R2"),
            T2=_flat_spectral(0.96, "T2"),
            alpha=_flat_spectral(1000.0, "alpha"),
            n_refr=_flat_spectral(1.5, "n"),
            thickness_m=0.01,  # 10mm at 1000/m → beer ≈ 0
        )
        t_sys = cavity.T_sys.values
        assert np.all(t_sys < 1e-3)
        # Energy conservation: T + R + A = 1.
        absorptance = 1.0 - t_sys - cavity.R_sys.values
        np.testing.assert_allclose(
            t_sys + cavity.R_sys.values + absorptance, 1.0, atol=1e-12,
        )

    def test_zero_thickness_surface_only(self) -> None:
        """d=0 → beer=1 → reduces to surface-only cavity (no bulk absorption)."""
        cavity = CavityModel(
            R1=_flat_spectral(0.04, "R1"),
            T1=_flat_spectral(0.96, "T1"),
            R2=_flat_spectral(0.04, "R2"),
            T2=_flat_spectral(0.96, "T2"),
            alpha=_flat_spectral(100.0, "alpha"),  # ignored when d=0
            n_refr=_flat_spectral(1.5, "n"),
            thickness_m=0.0,
        )
        # beer = exp(0) = 1, same as no-absorption case.
        np.testing.assert_allclose(cavity.beer, 1.0, atol=1e-14)
        np.testing.assert_allclose(cavity.eps_eff.values, 0.0, atol=1e-14)

    def test_energy_conservation_spectral(self) -> None:
        """T_sys + R_sys + A = 1 at every wavelength (non-flat inputs)."""
        wl = np.linspace(3.0, 5.0, 50)
        # Wavelength-dependent absorption.
        alpha_vals = np.linspace(5.0, 20.0, 50)
        cavity = CavityModel(
            R1=_flat_spectral(0.03, "R1"),
            T1=_flat_spectral(0.97, "T1"),
            R2=_flat_spectral(0.05, "R2"),
            T2=_flat_spectral(0.95, "T2"),
            alpha=SpectralData(
                name="alpha", wavelength_um=wl.copy(), values=alpha_vals,
                unit="1/m", source="test",
            ),
            n_refr=_flat_spectral(1.45, "n"),
            thickness_m=0.005,
        )
        t_sys = cavity.T_sys.values
        r_sys = cavity.R_sys.values
        absorptance = 1.0 - t_sys - r_sys
        # All non-negative.
        assert np.all(t_sys >= 0)
        assert np.all(r_sys >= 0)
        assert np.all(absorptance >= -1e-14)
        # Energy conservation.
        np.testing.assert_allclose(t_sys + r_sys + absorptance, 1.0, atol=1e-12)


class TestCavityModelValidation:
    """Error cases for CavityModel."""

    def test_surface_energy_violation(self) -> None:
        """R1 + T1 > 1 at surface 1."""
        with pytest.raises(KirchhoffViolationError, match="surface 1"):
            CavityModel(
                R1=_flat_spectral(0.5, "R1"),
                T1=_flat_spectral(0.6, "T1"),
                R2=_flat_spectral(0.04, "R2"),
                T2=_flat_spectral(0.96, "T2"),
                alpha=_flat_spectral(0.0, "alpha"),
                n_refr=_flat_spectral(1.5, "n"),
                thickness_m=0.003,
            )

    def test_negative_alpha(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            CavityModel(
                R1=_flat_spectral(0.04, "R1"),
                T1=_flat_spectral(0.96, "T1"),
                R2=_flat_spectral(0.04, "R2"),
                T2=_flat_spectral(0.96, "T2"),
                alpha=_flat_spectral(-1.0, "alpha"),
                n_refr=_flat_spectral(1.5, "n"),
                thickness_m=0.003,
            )

    def test_n_below_one(self) -> None:
        with pytest.raises(ValueError, match="n must be"):
            CavityModel(
                R1=_flat_spectral(0.04, "R1"),
                T1=_flat_spectral(0.96, "T1"),
                R2=_flat_spectral(0.04, "R2"),
                T2=_flat_spectral(0.96, "T2"),
                alpha=_flat_spectral(0.0, "alpha"),
                n_refr=_flat_spectral(0.9, "n"),
                thickness_m=0.003,
            )

    def test_negative_thickness(self) -> None:
        with pytest.raises(ValueError, match="thickness_m"):
            CavityModel(
                R1=_flat_spectral(0.04, "R1"),
                T1=_flat_spectral(0.96, "T1"),
                R2=_flat_spectral(0.04, "R2"),
                T2=_flat_spectral(0.96, "T2"),
                alpha=_flat_spectral(0.0, "alpha"),
                n_refr=_flat_spectral(1.5, "n"),
                thickness_m=-0.001,
            )

    def test_grid_mismatch(self) -> None:
        """All cavity spectral inputs must share the same wavelength grid."""
        wl2 = np.linspace(3.0, 6.0, 50)
        bad_alpha = SpectralData(
            name="alpha", wavelength_um=wl2, values=np.zeros(50),
            unit="1/m", source="test",
        )
        with pytest.raises(ValueError, match="wavelength grid"):
            CavityModel(
                R1=_flat_spectral(0.04, "R1"),
                T1=_flat_spectral(0.96, "T1"),
                R2=_flat_spectral(0.04, "R2"),
                T2=_flat_spectral(0.96, "T2"),
                alpha=bad_alpha,
                n_refr=_flat_spectral(1.5, "n"),
                thickness_m=0.003,
            )


# ---------------------------------------------------------------------------
# Factory: make_reflective_element
# ---------------------------------------------------------------------------


class TestMakeReflectiveElement:
    """Verify reflective element factory."""

    def test_scalar_reflectance(self) -> None:
        elem = make_reflective_element("primary", 0.98, wavelength_um=WL)
        assert elem.resolved_transfer_mode == ElementTransferMode.REFLECTIVE
        assert elem.kind == ElementKind.MIRROR
        np.testing.assert_allclose(elem.reflectance.values, 0.98, atol=1e-12)
        np.testing.assert_allclose(elem.transmittance.values, 0.0, atol=1e-12)
        np.testing.assert_allclose(elem.emissivity.values, 0.02, atol=1e-12)

    def test_spectral_reflectance(self) -> None:
        rho = _flat_spectral(0.95, "rho")
        elem = make_reflective_element("secondary", rho)
        np.testing.assert_allclose(elem.net_transmittance.values, 0.95, atol=1e-12)
        np.testing.assert_allclose(elem.emissivity.values, 0.05, atol=1e-12)

    def test_scalar_without_wavelength_raises(self) -> None:
        with pytest.raises(ValueError, match="wavelength_um is required"):
            make_reflective_element("bad", 0.98)

    def test_geometry_defaults(self) -> None:
        """Geometry parameters have defaults for pure radiometric use."""
        elem = make_reflective_element("m", 0.98, wavelength_um=WL)
        assert elem.temperature_K == 0.0
        assert elem.diameter_m == 1.0
        assert elem.distance_to_fpa_m == 1.0

    def test_geometry_override(self) -> None:
        elem = make_reflective_element(
            "m", 0.98, wavelength_um=WL,
            temperature_K=290.0, diameter_m=0.35, distance_to_fpa_m=1.2,
        )
        assert elem.temperature_K == 290.0
        assert elem.diameter_m == 0.35
        assert elem.distance_to_fpa_m == 1.2


# ---------------------------------------------------------------------------
# Factory: make_refractive_element (simple)
# ---------------------------------------------------------------------------


class TestMakeRefractiveElement:
    """Verify simple refractive element factory."""

    def test_scalar_transmittance(self) -> None:
        elem = make_refractive_element("window", 0.90, wavelength_um=WL)
        assert elem.resolved_transfer_mode == ElementTransferMode.REFRACTIVE
        assert elem.cavity is None
        np.testing.assert_allclose(elem.transmittance.values, 0.90, atol=1e-12)
        np.testing.assert_allclose(elem.emissivity.values, 0.0, atol=1e-12)

    def test_spectral_transmittance(self) -> None:
        tau = _flat_spectral(0.85, "tau")
        elem = make_refractive_element("filter", tau, kind=ElementKind.FILTER)
        assert elem.kind == ElementKind.FILTER
        np.testing.assert_allclose(elem.net_transmittance.values, 0.85, atol=1e-12)

    def test_mirror_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="not refractive"):
            make_refractive_element("bad", 0.90, kind=ElementKind.MIRROR, wavelength_um=WL)

    def test_scalar_without_wavelength_raises(self) -> None:
        with pytest.raises(ValueError, match="wavelength_um is required"):
            make_refractive_element("bad", 0.90)


# ---------------------------------------------------------------------------
# Factory: make_refractive_cavity_element
# ---------------------------------------------------------------------------


class TestMakeRefractiveCavityElement:
    """Verify cavity element factory with hand-calculated truth anchors."""

    def test_uncoated_glass_scalar_inputs(self) -> None:
        """Uncoated glass via factory with all-scalar inputs."""
        elem = make_refractive_cavity_element(
            "window",
            R1=0.04, T1=0.96, R2=0.04, T2=0.96,
            alpha=0.0, n_refr=1.5, thickness_m=0.003,
            wavelength_um=WL,
        )
        assert elem.resolved_transfer_mode == ElementTransferMode.REFRACTIVE
        assert elem.cavity is not None
        # T_sys from hand calc.
        np.testing.assert_allclose(
            elem.transmittance.values, 0.9216 / 0.9984, rtol=1e-10,
        )
        # eps_eff = 0 (no absorption).
        np.testing.assert_allclose(elem.emissivity.values, 0.0, atol=1e-14)

    def test_absorbing_glass_nonzero_eps(self) -> None:
        """Glass with absorption has nonzero emissivity via n^2 formula.

        eps_eff = T2 * n^2 * (1 - beer) / denom.
        For n > 1, eps_eff > absorptance (enhanced photon density of states).
        """
        import math
        elem = make_refractive_cavity_element(
            "lens",
            R1=0.04, T1=0.96, R2=0.04, T2=0.96,
            alpha=10.0, n_refr=1.5, thickness_m=0.003,
            wavelength_um=WL,
        )
        beer = math.exp(-10.0 * 0.003)
        denom = 1.0 - 0.04 * 0.04 * beer**2
        expected_eps = 0.96 * 1.5**2 * (1.0 - beer) / denom

        np.testing.assert_allclose(elem.emissivity.values, expected_eps, rtol=1e-10)
        assert np.all(elem.emissivity.values > 0)

    def test_eps_eff_matches_cavity_formula(self) -> None:
        """Cavity element eps matches T2 * n^2 * (1 - beer) / denom.

        For n > 1, eps_eff > absorptance = 1 - T - R due to the n^2
        enhancement factor (photon density of states inside dielectric).
        """
        import math
        elem = make_refractive_cavity_element(
            "lens",
            R1=0.03, T1=0.97, R2=0.05, T2=0.95,
            alpha=15.0, n_refr=1.5, thickness_m=0.005,
            wavelength_um=WL,
        )
        beer = math.exp(-15.0 * 0.005)
        denom = 1.0 - 0.03 * 0.05 * beer**2
        expected_eps = 0.95 * 1.5**2 * (1.0 - beer) / denom

        np.testing.assert_allclose(
            elem.emissivity.values, expected_eps, rtol=1e-10,
        )
        # eps_eff > absorptance for n > 1.
        absorptance = 1.0 - elem.transmittance.values - elem.reflectance.values
        assert np.all(elem.emissivity.values > absorptance)

    def test_mirror_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="not refractive"):
            make_refractive_cavity_element(
                "bad", R1=0.04, T1=0.96, R2=0.04, T2=0.96,
                alpha=0.0, n_refr=1.5, thickness_m=0.003,
                kind=ElementKind.MIRROR, wavelength_um=WL,
            )

    def test_net_transmittance_is_T_sys(self) -> None:
        """Transfer factor C_i = T_sys for cavity elements."""
        elem = make_refractive_cavity_element(
            "lens",
            R1=0.04, T1=0.96, R2=0.04, T2=0.96,
            alpha=10.0, n_refr=1.5, thickness_m=0.003,
            wavelength_um=WL,
        )
        np.testing.assert_array_equal(
            elem.net_transmittance.values, elem.transmittance.values,
        )
