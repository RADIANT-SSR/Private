"""Tests for the S4 / S5 / S6 reflectance → T2Reflective inferrer wiring.

Step 3.2 of the Target Definition Matrix Implementation Plan: the
inferrer routes a user-supplied scalar reflectance (S4) or albedo alias
(S6) through :func:`radiant.source.converters.reflectance_to_descriptor`
and emits a :class:`~radiant.core.descriptors.T2Reflective` descriptor.
The S5 tabulated path (``reflectance_path``) is recognised but deferred
alongside the S11 ``brightness_temperature_path`` CSV loader.

Truth anchors
-------------
1. **Pure Lambertian identity** — scalar ρ routed through the inferrer
   gives a T2Reflective whose ρ exactly recovers
   ``L_refl(λ) = ρ · E_sun(λ) / π`` when evaluated through the existing
   :class:`~radiant.source.brdf_lambertian.LambertianBRDF`.
2. **Heaviside ρ(λ) propagation** — a tabulated ρ with a sharp step at
   0.5 µm is passed straight through the boundary converter (no
   smoothing, no grid interpolation) — tests the Rule-19 scope of the
   converter module.
3. **Kirchhoff cross-model consistency** — a T2Reflective built from
   ρ=0.3 and a T3Mixed built from ε=0.7 on the same grid satisfy
   ``T2.rho + T3.epsilon ≡ 1`` pointwise (Rule 5 sanity check at the
   descriptor layer).

Also covered: mutual-exclusion guards (ρ + (ε, T), ρ + S11/S12), the
MWIR non-mixed warning (Rule 17 handoff), and isinstance assertions.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import T1Thermal, T2Reflective, T3Mixed
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import infer_descriptors
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.converters.reflectance import reflectance_to_descriptor

_WL_VIS = np.linspace(0.4, 0.8, 21)
_WL_MWIR = np.linspace(3.0, 5.0, 11)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reflective_params() -> ParameterSet:
    """Return a ParameterSet configured for the reflective fast-path.

    Sets the minimum fields required for ``params.resolve()`` to succeed
    and for ``infer_descriptors`` to run (optics consistency group,
    atmosphere backend, explicit scene_type so the IFOV discriminator
    stays inert).  Legacy ε / T are left at their Provenance.DEFAULT
    schema values so the inferrer's ``_is_user_set`` guard returns False
    on them and the reflective branch is reachable.
    """
    params = build_parameter_set()
    # Optics f-number consistency group — supply two of three.
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    params.set("atmosphere.model", "simple")
    # Other required (default=None) fields — values are placeholders; the
    # inferrer reads only pixel_pitch / focal_length / atmosphere.model /
    # source.* for the reflective branch.
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", 0.4)
    params.set("spectral_integration.filter_max_um", 0.9)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)
    # Skip the IFOV discriminator — explicit scene wins.
    params.set("source.scene_type", "extended")
    params.set("source.target_location", "terrestrial")
    return params


# ---------------------------------------------------------------------------
# Truth Anchor 1 — pure Lambertian identity at the descriptor layer
# ---------------------------------------------------------------------------


class TestTruthAnchorLambertianIdentity:
    """Scalar ρ routed through the inferrer recovers L = ρ·E_sun/π.

    The inferrer's contract is: "given a scalar ρ on the schema, emit a
    T2Reflective whose ρ(λ) is the same value on the chain grid."  The
    downstream Lambertian identity L_refl = ρ·E_sun/π is intrinsic to
    :class:`LambertianBRDF` and :class:`ReflectedSolarSource`; this
    anchor confirms that the descriptor's ρ feeds the existing solar
    path unchanged.
    """

    def test_scalar_rho_flat_on_chain_grid(self) -> None:
        params = _reflective_params()
        params.set("source.target.reflectance", 0.5)
        # Reflective pathway must not inherit legacy (ε, T) from template.
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        # Constant-ρ lift: every grid point equals 0.5 exactly.
        np.testing.assert_array_equal(
            target.rho.values, np.full_like(_WL_VIS, 0.5)
        )
        # Grid equality (no resampling — Rule 2 boundary).
        np.testing.assert_array_equal(target.rho.wavelength_um, _WL_VIS)

    def test_lambertian_identity_recovers_rho_times_E_over_pi(self) -> None:
        """L_refl(λ) = ρ·E_sun(λ)/π reconstructed from the descriptor's ρ."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.5)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)
        assert isinstance(target, T2Reflective)
        assert target.rho is not None

        E_sun = toa_solar_spectral_irradiance(_WL_VIS)

        # Path A: direct analytic identity from descriptor's ρ.
        L_direct = target.rho.values * E_sun / math.pi

        # Path B: Lambertian BRDF evaluated at θ_sun = 0 ⇒ L = BRDF·E·cos0.
        brdf = LambertianBRDF(reflectance=target.rho.values)
        L_brdf = brdf.evaluate(_WL_VIS) * E_sun * math.cos(0.0)

        np.testing.assert_allclose(L_brdf, L_direct, rtol=1e-12, atol=0.0)

        # Sanity: descriptor ρ = 0.5 ⇒ L = 0.5·E_sun/π (no hidden factor).
        expected = 0.5 * E_sun / math.pi
        np.testing.assert_allclose(L_direct, expected, rtol=1e-12, atol=0.0)


# ---------------------------------------------------------------------------
# Truth Anchor 2 — Heaviside ρ(λ) through the boundary converter
# ---------------------------------------------------------------------------


class TestTruthAnchorHeavisideSpectrum:
    """Tabulated ρ with a step at 0.5 µm propagates unaltered.

    The inferrer only scalar-lifts today (S5 CSV loader lands with the
    S11 T_B path); the spectral path is exercised directly via the
    converter, which the inferrer will call once the loader arrives.
    The invariant under test is identical on both paths: the converter
    never resamples or smooths ρ.
    """

    def test_heaviside_step_preserved_in_descriptor(self) -> None:
        step_edge_um = 0.5
        wl = np.linspace(0.3, 0.9, 25)
        rho_vals = np.where(wl < step_edge_um, 0.0, 1.0).astype(np.float64)
        rho_sd = SpectralData(
            name="test.heaviside_rho",
            wavelength_um=wl,
            values=rho_vals,
            unit="",
            source="test_inferrer_reflective::heaviside",
        )

        target = reflectance_to_descriptor(
            rho=rho_sd,
            wavelength_um=wl,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        # Converter must be pass-through: no interpolation, no clipping.
        np.testing.assert_array_equal(target.rho.values, rho_vals)
        np.testing.assert_array_equal(target.rho.wavelength_um, wl)
        # Step semantics preserved: below 0.5 µm all zero, above all one.
        below = wl < step_edge_um
        above = wl >= step_edge_um
        assert np.all(target.rho.values[below] == 0.0)
        assert np.all(target.rho.values[above] == 1.0)


# ---------------------------------------------------------------------------
# Truth Anchor 3 — Kirchhoff ρ = 1 − ε cross-model consistency
# ---------------------------------------------------------------------------


class TestTruthAnchorKirchhoffConsistency:
    """T2Reflective(ρ) and T3Mixed(ε=1−ρ) satisfy ρ + ε ≡ 1 pointwise.

    Rule 5: for opaque Lambertian surfaces ρ + ε = 1 exactly.  Building
    T2 and T3 from complementary spectra on the same grid must give
    descriptors whose ρ and ε are algebraic complements — verifying the
    boundary converter and the descriptor dataclasses agree on the
    Kirchhoff identity at construction time.  (The downstream
    ``L = ε·B(T) + ρ·E_down·τ/π`` assembly lives in AtmosphereStage and
    is tested there.)
    """

    def test_rho_plus_epsilon_is_one_pointwise(self) -> None:
        rho_scalar = 0.3
        eps_scalar = 1.0 - rho_scalar  # 0.7
        wl = np.linspace(0.5, 2.5, 41)

        # Build T2Reflective from scalar ρ via the converter.
        t2 = reflectance_to_descriptor(
            rho=rho_scalar,
            wavelength_um=wl,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(t2, T2Reflective)

        # Build T3Mixed from complementary scalar ε on the same grid.
        epsilon_sd = SpectralData(
            name="test.complement_epsilon",
            wavelength_um=wl,
            values=np.full_like(wl, eps_scalar),
            unit="",
            source="test_inferrer_reflective::kirchhoff",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            t3 = T3Mixed(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                epsilon=epsilon_sd,
                T_t=300.0,
            )

        assert t2.rho is not None
        assert t3.epsilon is not None
        # Kirchhoff identity at the descriptor layer.
        np.testing.assert_allclose(
            t2.rho.values + t3.epsilon.values,
            np.ones_like(wl),
            rtol=1e-12,
            atol=0.0,
        )


# ---------------------------------------------------------------------------
# Inferrer happy-path — isinstance + mutual-exclusion rejection
# ---------------------------------------------------------------------------


class TestInferrerReflectiveDispatch:
    """The inferrer dispatches scalar ρ / albedo to T2Reflective."""

    def test_scalar_reflectance_produces_T2Reflective(self) -> None:
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert not isinstance(target, (T1Thermal, T3Mixed))

    def test_albedo_alias_produces_T2Reflective(self) -> None:
        """S6 albedo alias collapses onto the same T2Reflective surface."""
        params = _reflective_params()
        params.set("source.target.albedo", 0.4)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        np.testing.assert_array_equal(
            target.rho.values, np.full_like(_WL_VIS, 0.4)
        )


# ---------------------------------------------------------------------------
# Negative cases (Rule 16 / 17 — over-specified, ambiguous, deferred)
# ---------------------------------------------------------------------------


class TestInferrerReflectiveRejections:
    def test_reflectance_plus_temperature_raises(self) -> None:
        """ρ + (ε, T) over-specifies the target; must raise."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.7)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    def test_reflectance_plus_brightness_temperature_raises(self) -> None:
        """Reflective S4/S5/S6 and thermal S11 are mutually exclusive."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.brightness_temperature_K", 290.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    def test_reflectance_plus_radiance_temperature_raises(self) -> None:
        """Reflective S4/S5/S6 and thermal S12 are mutually exclusive."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.radiance_temperature_K", 290.0)
        params.set("source.target.radiance_temperature_band_lo_um", 8.0)
        params.set("source.target.radiance_temperature_band_hi_um", 12.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    def test_reflectance_plus_albedo_raises(self) -> None:
        """Reflectance + albedo (both scalar surfaces) over-specifies ρ."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.albedo", 0.3)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="over-specified"):
            infer_descriptors(params, _WL_VIS)

    def test_reflectance_path_deferred(self) -> None:
        """S5 CSV path is recognised but raises a clear deferral error."""
        params = _reflective_params()
        params.set(
            "source.target.reflectance_path", "scenes/reflectance.csv"
        )
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="not yet wired"):
            infer_descriptors(params, _WL_VIS)

    def test_reflectance_at_aperture_raises(self) -> None:
        """ρ is meaningless at S9 (at-aperture) — converter must reject."""
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            reflectance_to_descriptor(
                rho=0.3,
                wavelength_um=_WL_VIS,
                scene_type="extended",
                target_location="at_aperture",
            )

    def test_reflectance_mwir_emits_warning(self) -> None:
        """S4 with MWIR grid triggers the T2 non-mixed Rule-17 warning.

        Matrix §3.2: ambient-temperature MWIR scenes should use T3Mixed.
        The T2Reflective ``__post_init__`` fires the warning; this test
        asserts the inferrer does not suppress it (Rule 17 pass-through).
        """
        params = _reflective_params()
        params.set("source.target.reflectance", 0.5)
        params.resolve()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_MWIR)

        assert isinstance(target, T2Reflective)
        mwir_msgs = [
            w
            for w in caught
            if "MWIR" in str(w.message) and "T2Reflective" in str(w.message)
        ]
        assert mwir_msgs, (
            "Expected T2Reflective MWIR non-mixed warning to propagate; "
            f"got warnings: {[str(w.message) for w in caught]}"
        )
