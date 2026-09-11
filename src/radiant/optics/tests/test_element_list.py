"""Tests for radiant.optics.element_list.

Category C validation for system transmission and nearfield irradiance:
- Two-mirror system tau = R1 * R2
- Single-element nearfield hand calculation against the étendue cone
- Two-element downstream attenuation
- Zero-temperature element contributes nothing
- Nearfield scales linearly with Omega_cone (Gap 128)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.spectral import SpectralData
from radiant.optics.element import ElementKind, OpticalElement
from radiant.optics.element_factories import (
    make_lumped_element,
    make_reflective_element,
    make_refractive_cavity_element,
    make_refractive_element,
)
from radiant.optics.nearfield_irradiance import (
    NearfieldResult,
    compute_downstream_transmission,
    compute_nearfield_irradiance,
)
from radiant.optics.system_transmission import compute_system_transmission

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WL = np.linspace(3.0, 5.0, 50)

# The one geometry the near-field model has (Gap 128): the étendue acceptance
# cone at f/6. 2π(1 − cos(arctan(1/12))) = 0.0217031… sr — see etendue_cone.py.
OMEGA_F6_SR = 2.0 * math.pi * (1.0 - math.cos(math.atan(1.0 / 12.0)))


def _flat_spectral(value: float, name: str = "test") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=WL.copy(),
        values=np.full_like(WL, value),
        unit="",
        source="test fixture",
    )


def _mirror(R: float, T_K: float, name: str = "m") -> OpticalElement:
    return OpticalElement(
        name=name,
        kind=ElementKind.MIRROR,
        temperature_K=T_K,
        transmittance=_flat_spectral(0.0, f"{name}.tau"),
        reflectance=_flat_spectral(R, f"{name}.rho"),
    )


def _window(T: float, R: float, T_K: float, name: str = "w") -> OpticalElement:
    return OpticalElement(
        name=name,
        kind=ElementKind.WINDOW,
        temperature_K=T_K,
        transmittance=_flat_spectral(T, f"{name}.tau"),
        reflectance=_flat_spectral(R, f"{name}.rho"),
    )


# ---------------------------------------------------------------------------
# System transmission
# ---------------------------------------------------------------------------


class TestSystemTransmission:
    """Verify system transmission is the product of net transmittances."""

    @pytest.mark.level1
    def test_two_mirrors(self) -> None:
        """Two mirrors R=0.98 each: tau_system = 0.98^2 = 0.9604."""
        m1 = _mirror(0.98, 290.0, "primary")
        m2 = _mirror(0.98, 290.0, "secondary")
        tau = compute_system_transmission((m1, m2), WL)
        np.testing.assert_allclose(tau.values, 0.98**2, atol=1e-12)

    @pytest.mark.level1
    def test_mirror_plus_window(self) -> None:
        """Mirror R=0.98, window T=0.95: system tau = 0.98 * 0.95 = 0.931."""
        m = _mirror(0.98, 290.0)
        w = _window(0.95, 0.01, 290.0)
        tau = compute_system_transmission((m, w), WL)
        np.testing.assert_allclose(tau.values, 0.98 * 0.95, atol=1e-12)

    @pytest.mark.level1
    def test_single_element(self) -> None:
        m = _mirror(0.97, 290.0)
        tau = compute_system_transmission((m,), WL)
        np.testing.assert_allclose(tau.values, 0.97, atol=1e-12)

    @pytest.mark.level1
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_system_transmission((), WL)


# ---------------------------------------------------------------------------
# Downstream transmission
# ---------------------------------------------------------------------------


class TestDownstreamTransmission:
    """Verify downstream transmission for element ordering."""

    @pytest.mark.level1
    def test_last_element_is_ones(self) -> None:
        m1 = _mirror(0.98, 290.0)
        m2 = _mirror(0.95, 290.0)
        tau_down = compute_downstream_transmission((m1, m2), 1, WL)
        np.testing.assert_allclose(tau_down, 1.0, atol=1e-12)

    @pytest.mark.level1
    def test_first_element_has_second_downstream(self) -> None:
        m1 = _mirror(0.98, 290.0)
        m2 = _mirror(0.95, 290.0)
        tau_down = compute_downstream_transmission((m1, m2), 0, WL)
        np.testing.assert_allclose(tau_down, 0.95, atol=1e-12)

    @pytest.mark.level1
    def test_three_elements(self) -> None:
        m1 = _mirror(0.98, 290.0)
        m2 = _mirror(0.95, 290.0)
        w = _window(0.90, 0.01, 290.0)
        # Downstream of m1: m2 * w = 0.95 * 0.90 = 0.855
        tau_down = compute_downstream_transmission((m1, m2, w), 0, WL)
        np.testing.assert_allclose(tau_down, 0.95 * 0.90, atol=1e-12)


# ---------------------------------------------------------------------------
# Nearfield irradiance
# ---------------------------------------------------------------------------


class TestNearfieldIrradiance:
    """Verify nearfield emission calculations."""

    @pytest.mark.level1
    def test_single_mirror_hand_calc(self) -> None:
        """Truth anchor 1: single 290 K mirror seen through the f/6 cone.

        R = 0.98 ⇒ ε = 0.02 [-]; Ω_cone = 2π(1 − cos(arctan(1/12))) sr;
        τ_downstream = 1 [-] (last element).
        E_nf(λ) = Ω_cone · ε · B(λ, 290 K) · 1.0   [W/m²/µm]
        """
        m = _mirror(0.98, 290.0, "primary")
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)

        eps = 0.02
        b_lam = planck_spectral_radiance(WL, 290.0)
        expected = OMEGA_F6_SR * eps * b_lam

        np.testing.assert_allclose(result.total.values, expected, rtol=1e-10)

    @pytest.mark.level1
    def test_two_elements_downstream_attenuation(self) -> None:
        """Truth anchor 2: mirror emission attenuated by downstream window.

        Element 1: mirror R=0.98 (eps=0.02), D=0.3m, d=1.2m
        Element 2: window T=0.90 R=0.01 (eps=0.0, simple refractive), D=0.05m, d=0.1m

        Simple refractive window has eps=0 (absorption unknown), so only
        the mirror contributes to nearfield:
        E_nf = eps1 * B(T1) * Omega1 * tau2
        """
        m = _mirror(0.98, 290.0, "primary")
        w = _window(0.90, 0.01, 290.0, "window")

        result = compute_nearfield_irradiance((m, w), WL, OMEGA_F6_SR)

        b_lam = planck_spectral_radiance(WL, 290.0)

        eps1 = 0.02
        tau_down_1 = 0.90  # window transmittance

        # Window eps=0 (simple refractive), contributes nothing.
        expected = OMEGA_F6_SR * eps1 * b_lam * tau_down_1

        np.testing.assert_allclose(result.total.values, expected, rtol=1e-10)

    @pytest.mark.level1
    def test_zero_temperature_no_contribution(self) -> None:
        """T=0 K element contributes zero nearfield."""
        m = _mirror(0.98, 0.0)
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        np.testing.assert_allclose(result.total.values, 0.0, atol=1e-30)

    @pytest.mark.level1
    def test_scales_linearly_with_cone(self) -> None:
        """Nearfield scales linearly with Ω_cone [sr] — the only geometry (Gap 128)."""
        m = _mirror(0.98, 290.0)
        full = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        half = compute_nearfield_irradiance((m,), WL, 0.5 * OMEGA_F6_SR)
        np.testing.assert_allclose(half.total.values, full.total.values * 0.5, rtol=1e-12)

    @pytest.mark.level1
    def test_lumped_element_zero_nearfield(self) -> None:
        """Lumped element (simple refractive) has eps=0, zero nearfield.

        Simple refractive elements have unknown absorption, so eps=0.
        Nearfield emission is zero regardless of temperature.
        """
        tau_sd = _flat_spectral(0.7, "tau")
        lumped = make_lumped_element(tau_sd, 290.0)

        result = compute_nearfield_irradiance((lumped,), WL, OMEGA_F6_SR)
        np.testing.assert_allclose(result.total.values, 0.0, atol=1e-30)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge-case validation."""

    @pytest.mark.level1
    def test_empty_list_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_nearfield_irradiance((), WL, OMEGA_F6_SR)

    @pytest.mark.level1
    def test_cone_beyond_hemisphere_raises(self) -> None:
        """Ω_cone > 2π sr is not a solid angle a focal plane can accept."""
        m = _mirror(0.98, 290.0)
        with pytest.raises(ValueError, match="omega_cone_sr"):
            compute_nearfield_irradiance((m,), WL, 7.0)

    @pytest.mark.level1
    def test_zero_cone_raises(self) -> None:
        m = _mirror(0.98, 290.0)
        with pytest.raises(ValueError, match="omega_cone_sr"):
            compute_nearfield_irradiance((m,), WL, 0.0)

    @pytest.mark.level1
    def test_nearfield_nonnegative(self) -> None:
        """Nearfield must always be >= 0."""
        m = _mirror(0.98, 290.0)
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        assert np.all(result.total.values >= 0.0)

    @pytest.mark.level1
    def test_unit_is_irradiance(self) -> None:
        m = _mirror(0.98, 290.0)
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        assert "W/m" in result.total.unit


# ---------------------------------------------------------------------------
# Mixed-train tests (reflective + refractive elements)
# ---------------------------------------------------------------------------


class TestMixedTrain:
    """Verify mixed-train element list with reflective and refractive elements."""

    @pytest.mark.level1
    def test_system_transmission_mixed(self) -> None:
        """3-mirror + 1-lens: tau_system = R1 * R2 * R3 * T_lens."""
        m1 = make_reflective_element(
            "primary",
            0.98,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        m2 = make_reflective_element(
            "secondary",
            0.98,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        m3 = make_reflective_element(
            "fold",
            0.97,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        lens = make_refractive_element(
            "field_lens",
            0.92,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        elements = (m1, m2, m3, lens)
        tau = compute_system_transmission(elements, WL)
        expected = 0.98 * 0.98 * 0.97 * 0.92
        np.testing.assert_allclose(tau.values, expected, rtol=1e-10)

    @pytest.mark.level1
    def test_nearfield_mirrors_only_emit(self) -> None:
        """In mixed train, only reflective elements contribute nearfield.

        Simple refractive elements have eps=0.
        """
        m = make_reflective_element(
            "mirror",
            0.98,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        lens = make_refractive_element(
            "lens",
            0.90,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        result = compute_nearfield_irradiance((m, lens), WL, OMEGA_F6_SR)

        # Only mirror contributes; downstream lens has T=0.90.
        b_lam = planck_spectral_radiance(WL, 290.0)
        eps_mirror = 0.02
        tau_down = 0.90  # lens transmittance
        expected = OMEGA_F6_SR * eps_mirror * b_lam * tau_down

        np.testing.assert_allclose(result.total.values, expected, rtol=1e-10)

    @pytest.mark.level1
    def test_cavity_element_emits_in_nearfield(self) -> None:
        """Cavity element with absorption has nonzero nearfield emission."""
        m = make_reflective_element(
            "mirror",
            0.98,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        cavity_lens = make_refractive_cavity_element(
            "lens",
            R1=0.04,
            T1=0.96,
            R2=0.04,
            T2=0.96,
            alpha=10.0,
            n_refr=1.5,
            thickness_m=0.003,
            wavelength_um=WL,
            temperature_K=290.0,
        )
        result = compute_nearfield_irradiance((m, cavity_lens), WL, OMEGA_F6_SR)

        # Both elements contribute (cavity lens has nonzero eps).
        b_lam = planck_spectral_radiance(WL, 290.0)

        # Mirror contribution (attenuated by cavity lens transmittance).
        eps_m = 0.02
        tau_down_m = cavity_lens.net_transmittance.values
        mirror_term = OMEGA_F6_SR * eps_m * b_lam * tau_down_m

        # Cavity lens contribution (last element, no downstream). Same cone:
        # proximity to the focal plane buys an element no extra solid angle.
        eps_lens = cavity_lens.emissivity.values
        lens_term = OMEGA_F6_SR * eps_lens * b_lam

        expected = mirror_term + lens_term
        np.testing.assert_allclose(result.total.values, expected, rtol=1e-10)


# ---------------------------------------------------------------------------
# Per-element nearfield breakdown (NearfieldResult)
# ---------------------------------------------------------------------------


class TestNearfieldPerElement:
    """Verify per-element nearfield breakdown in NearfieldResult."""

    @pytest.mark.level1
    def test_returns_nearfield_result(self) -> None:
        """compute_nearfield_irradiance returns NearfieldResult."""
        m = _mirror(0.98, 290.0, "primary")
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        assert isinstance(result, NearfieldResult)

    @pytest.mark.level1
    def test_single_element_per_element_matches_total(self) -> None:
        """For one element, per_element[name] == total."""
        m = _mirror(0.98, 290.0, "primary")
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        assert "primary" in result.per_element
        np.testing.assert_allclose(
            result.per_element["primary"].values,
            result.total.values,
            rtol=1e-12,
        )

    @pytest.mark.level1
    def test_sum_of_per_element_equals_total(self) -> None:
        """Sum of all per-element contributions must equal total."""
        m1 = _mirror(0.98, 290.0, "primary")
        m2 = _mirror(0.95, 290.0, "secondary")
        result = compute_nearfield_irradiance((m1, m2), WL, OMEGA_F6_SR)

        summed = np.zeros_like(WL)
        for sd in result.per_element.values():
            summed += sd.values
        np.testing.assert_allclose(summed, result.total.values, rtol=1e-12)

    @pytest.mark.level1
    def test_per_element_keys_match_element_names(self) -> None:
        """per_element dict keys are the element names."""
        m1 = _mirror(0.98, 290.0, "primary")
        m2 = _mirror(0.95, 290.0, "secondary")
        result = compute_nearfield_irradiance((m1, m2), WL, OMEGA_F6_SR)
        assert set(result.per_element.keys()) == {"primary", "secondary"}

    @pytest.mark.level1
    def test_zero_temp_element_excluded_from_per_element(self) -> None:
        """T=0 K element does not appear in per_element."""
        m_warm = _mirror(0.98, 290.0, "warm")
        m_cold = _mirror(0.98, 0.0, "cold")
        result = compute_nearfield_irradiance((m_warm, m_cold), WL, OMEGA_F6_SR)
        assert "warm" in result.per_element
        assert "cold" not in result.per_element

    @pytest.mark.level1
    def test_cone_scales_per_element(self) -> None:
        """Ω_cone [sr] scales each per-element contribution."""
        m = _mirror(0.98, 290.0, "primary")
        full = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        half = compute_nearfield_irradiance((m,), WL, 0.5 * OMEGA_F6_SR)
        np.testing.assert_allclose(
            half.per_element["primary"].values,
            full.per_element["primary"].values * 0.5,
            rtol=1e-12,
        )

    @pytest.mark.level1
    def test_per_element_units(self) -> None:
        """Each per-element SpectralData has irradiance units."""
        m = _mirror(0.98, 290.0, "primary")
        result = compute_nearfield_irradiance((m,), WL, OMEGA_F6_SR)
        assert "W/m" in result.per_element["primary"].unit

    @pytest.mark.level1
    def test_per_element_hand_calc_two_mirrors(self) -> None:
        """Verify per-element values match hand calculation for two mirrors.

        M1: R=0.98 (eps=0.02), T=290 K
        M2: R=0.95 (eps=0.05), T=300 K
        Both are seen through the SAME Omega_cone (Gap 128).

        M1 contribution: Omega_cone * eps1 * B(290) * tau_down(M2=0.95)
        M2 contribution: Omega_cone * eps2 * B(300) * 1.0  (last element)
        """
        m1 = _mirror(0.98, 290.0, "primary")
        m2 = _mirror(0.95, 300.0, "secondary")
        result = compute_nearfield_irradiance((m1, m2), WL, OMEGA_F6_SR)

        b_290 = planck_spectral_radiance(WL, 290.0)
        b_300 = planck_spectral_radiance(WL, 300.0)

        eps1, eps2 = 0.02, 0.05

        expected_m1 = OMEGA_F6_SR * eps1 * b_290 * 0.95  # attenuated by M2
        expected_m2 = OMEGA_F6_SR * eps2 * b_300 * 1.0  # nothing downstream

        np.testing.assert_allclose(
            result.per_element["primary"].values,
            expected_m1,
            rtol=1e-10,
        )
        np.testing.assert_allclose(
            result.per_element["secondary"].values,
            expected_m2,
            rtol=1e-10,
        )


class TestNearfieldMirrorEmission:
    """Gap 127 Level 0: emission derives only from defined elements.

    A lump never emits; a warm mirror emits Ω_cone·ε·B(λ,T) with ε = 1 − R.
    """

    @pytest.mark.level0
    def test_hand_computed_mirror_irradiance(self) -> None:
        """E_nf = Omega_cone * (1 - R) * B(lam, T) for a single warm mirror.

        Hand anchor: R = 0.95 -> eps = 0.05 [-], T = 295 K, f/6 cone
        -> Omega_cone = 0.0217031... sr.
        """
        mirror = make_reflective_element(
            "m1",
            0.95,
            wavelength_um=WL,
            temperature_K=295.0,
        )
        result = compute_nearfield_irradiance((mirror,), WL, OMEGA_F6_SR)

        expected = OMEGA_F6_SR * 0.05 * planck_spectral_radiance(WL, 295.0)
        np.testing.assert_allclose(result.total.values, expected, rtol=1e-12)
        assert float(result.total.values.max()) > 0.0

    @pytest.mark.level0
    def test_lump_stays_dark(self) -> None:
        """Gap 127: a lump is bookkeeping, not a surface — it never emits."""
        tau = _flat_spectral(0.7, "tau")
        lump = make_lumped_element(tau, 295.0)
        result = compute_nearfield_irradiance((lump,), WL, OMEGA_F6_SR)
        np.testing.assert_array_equal(result.total.values, 0.0)
