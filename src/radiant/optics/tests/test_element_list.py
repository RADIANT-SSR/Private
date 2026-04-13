"""Tests for radiant.optics.element_list.

Category C validation for system transmission and nearfield irradiance:
- Two-mirror system tau = R1 * R2
- Single-element nearfield hand calculation
- Two-element downstream attenuation
- Zero-temperature element contributes nothing
- Cold stop efficiency scales linearly
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.optics.element import ElementKind, OpticalElement, make_lumped_element
from radiant.optics.element_list import (
    compute_downstream_transmission,
    compute_nearfield_irradiance,
    compute_system_transmission,
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


def _mirror(R: float, T_K: float, D: float, d: float, name: str = "m") -> OpticalElement:
    return OpticalElement(
        name=name,
        kind=ElementKind.MIRROR,
        temperature_K=T_K,
        transmittance=_flat_spectral(0.0, f"{name}.tau"),
        reflectance=_flat_spectral(R, f"{name}.rho"),
        diameter_m=D,
        distance_to_fpa_m=d,
    )


def _window(T: float, R: float, T_K: float, D: float, d: float, name: str = "w") -> OpticalElement:
    return OpticalElement(
        name=name,
        kind=ElementKind.WINDOW,
        temperature_K=T_K,
        transmittance=_flat_spectral(T, f"{name}.tau"),
        reflectance=_flat_spectral(R, f"{name}.rho"),
        diameter_m=D,
        distance_to_fpa_m=d,
    )


# ---------------------------------------------------------------------------
# System transmission
# ---------------------------------------------------------------------------


class TestSystemTransmission:
    """Verify system transmission is the product of net transmittances."""

    def test_two_mirrors(self) -> None:
        """Two mirrors R=0.98 each: tau_system = 0.98^2 = 0.9604."""
        m1 = _mirror(0.98, 290.0, 0.3, 1.2, "primary")
        m2 = _mirror(0.98, 290.0, 0.1, 0.6, "secondary")
        tau = compute_system_transmission((m1, m2), WL)
        np.testing.assert_allclose(tau.values, 0.98**2, atol=1e-12)

    def test_mirror_plus_window(self) -> None:
        """Mirror R=0.98, window T=0.95: system tau = 0.98 * 0.95 = 0.931."""
        m = _mirror(0.98, 290.0, 0.3, 1.2)
        w = _window(0.95, 0.01, 290.0, 0.05, 0.1)
        tau = compute_system_transmission((m, w), WL)
        np.testing.assert_allclose(tau.values, 0.98 * 0.95, atol=1e-12)

    def test_single_element(self) -> None:
        m = _mirror(0.97, 290.0, 0.3, 1.0)
        tau = compute_system_transmission((m,), WL)
        np.testing.assert_allclose(tau.values, 0.97, atol=1e-12)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_system_transmission((), WL)


# ---------------------------------------------------------------------------
# Downstream transmission
# ---------------------------------------------------------------------------


class TestDownstreamTransmission:
    """Verify downstream transmission for element ordering."""

    def test_last_element_is_ones(self) -> None:
        m1 = _mirror(0.98, 290.0, 0.3, 1.2)
        m2 = _mirror(0.95, 290.0, 0.1, 0.6)
        tau_down = compute_downstream_transmission((m1, m2), 1, WL)
        np.testing.assert_allclose(tau_down, 1.0, atol=1e-12)

    def test_first_element_has_second_downstream(self) -> None:
        m1 = _mirror(0.98, 290.0, 0.3, 1.2)
        m2 = _mirror(0.95, 290.0, 0.1, 0.6)
        tau_down = compute_downstream_transmission((m1, m2), 0, WL)
        np.testing.assert_allclose(tau_down, 0.95, atol=1e-12)

    def test_three_elements(self) -> None:
        m1 = _mirror(0.98, 290.0, 0.3, 1.2)
        m2 = _mirror(0.95, 290.0, 0.1, 0.8)
        w = _window(0.90, 0.01, 290.0, 0.05, 0.1)
        # Downstream of m1: m2 * w = 0.95 * 0.90 = 0.855
        tau_down = compute_downstream_transmission((m1, m2, w), 0, WL)
        np.testing.assert_allclose(tau_down, 0.95 * 0.90, atol=1e-12)


# ---------------------------------------------------------------------------
# Nearfield irradiance
# ---------------------------------------------------------------------------


class TestNearfieldIrradiance:
    """Verify nearfield emission calculations."""

    def test_single_mirror_hand_calc(self) -> None:
        """Truth anchor 1: single 290K mirror.

        R=0.98, epsilon=0.02, D=0.30m, d=1.20m.
        Omega = pi*(0.15)^2 / (1.20)^2 = 0.04909 sr.
        tau_downstream = 1 (last element).
        E_nf(lam) = eps * B(lam, 290) * Omega * 1.0
        """
        m = _mirror(0.98, 290.0, 0.30, 1.20, "primary")
        e_nf = compute_nearfield_irradiance((m,), WL)

        eps = 0.02
        omega = math.pi * (0.15) ** 2 / (1.20) ** 2
        b_lam = planck_spectral_radiance(WL, 290.0)
        expected = eps * b_lam * omega

        np.testing.assert_allclose(e_nf.values, expected, rtol=1e-10)

    def test_two_elements_downstream_attenuation(self) -> None:
        """Truth anchor 2: element 1 emission attenuated by element 2.

        Element 1: mirror R=0.98 (eps=0.02), D=0.3m, d=1.2m
        Element 2: window T=0.90 R=0.01 (eps=0.09), D=0.05m, d=0.1m

        E_nf = eps1 * B(T1) * Omega1 * tau2 + eps2 * B(T2) * Omega2 * 1.0
        """
        m = _mirror(0.98, 290.0, 0.30, 1.20, "primary")
        w = _window(0.90, 0.01, 290.0, 0.05, 0.10, "window")

        e_nf = compute_nearfield_irradiance((m, w), WL)

        b_lam = planck_spectral_radiance(WL, 290.0)

        eps1 = 0.02
        omega1 = math.pi * (0.15) ** 2 / (1.20) ** 2
        tau_down_1 = 0.90  # window transmittance

        eps2 = 0.09
        omega2 = math.pi * (0.025) ** 2 / (0.10) ** 2
        tau_down_2 = 1.0  # last element

        expected = (
            eps1 * b_lam * omega1 * tau_down_1
            + eps2 * b_lam * omega2 * tau_down_2
        )

        np.testing.assert_allclose(e_nf.values, expected, rtol=1e-10)

    def test_zero_temperature_no_contribution(self) -> None:
        """T=0 K element contributes zero nearfield."""
        m = _mirror(0.98, 0.0, 0.30, 1.20)
        e_nf = compute_nearfield_irradiance((m,), WL)
        np.testing.assert_allclose(e_nf.values, 0.0, atol=1e-30)

    def test_cold_stop_efficiency_scales(self) -> None:
        """Nearfield should scale linearly with cold_stop_efficiency."""
        m = _mirror(0.98, 290.0, 0.30, 1.20)
        full = compute_nearfield_irradiance((m,), WL, cold_stop_efficiency=1.0)
        half = compute_nearfield_irradiance((m,), WL, cold_stop_efficiency=0.5)
        np.testing.assert_allclose(half.values, full.values * 0.5, rtol=1e-12)

    def test_lumped_element_consistency(self) -> None:
        """Truth anchor 3: lumped element at tau=0.7 should give eps=0.3.

        Compare with a WINDOW at T=0.7, R=0 (eps=0.3).
        """
        tau_sd = _flat_spectral(0.7, "tau")
        lumped = make_lumped_element(tau_sd, 290.0, 0.3, 1.0)

        w = _window(0.7, 0.0, 290.0, 0.3, 1.0, "equivalent")

        e_lumped = compute_nearfield_irradiance((lumped,), WL)
        e_window = compute_nearfield_irradiance((w,), WL)

        np.testing.assert_allclose(e_lumped.values, e_window.values, rtol=1e-12)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge-case validation."""

    def test_empty_list_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_nearfield_irradiance((), WL)

    def test_cold_stop_out_of_range(self) -> None:
        m = _mirror(0.98, 290.0, 0.3, 1.2)
        with pytest.raises(ValueError, match="cold_stop_efficiency"):
            compute_nearfield_irradiance((m,), WL, cold_stop_efficiency=1.5)

    def test_nearfield_nonnegative(self) -> None:
        """Nearfield must always be >= 0."""
        m = _mirror(0.98, 290.0, 0.3, 1.2)
        e_nf = compute_nearfield_irradiance((m,), WL)
        assert np.all(e_nf.values >= 0.0)

    def test_unit_is_irradiance(self) -> None:
        m = _mirror(0.98, 290.0, 0.3, 1.2)
        e_nf = compute_nearfield_irradiance((m,), WL)
        assert "W/m" in e_nf.unit
