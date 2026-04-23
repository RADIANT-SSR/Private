"""Category C truth-anchor tests for the Option C §6.1 assembly functions.

These are Level-0 tests per Rule 18: they verify the key assembly equation
against hand-computed analytic values before any backend's ``evaluate()``
is implemented.  ``assembly.assemble_target_at_aperture`` and
``assembly.assemble_background_at_aperture`` are pure arithmetic on a
descriptor and a pre-built :class:`AtmosphericQuantities` — tests construct
those inputs directly.

Three anchors (the minimum required by Category C):

1. **LWIR thermal (T1)** — ε = 0.95, T_t = 300 K, midlat-summer-style
   τ and L_path at 10 µm.  Hand computation matches to better than 1e-12.

2. **VIS reflective (T2)** — ρ = 0.3, θ_s = 30°, τ_sun = 0.8, τ_up = 0.9,
   E_TOA = 1400 W/m²/µm, E_sky = 120 W/m²/µm.  Two-leg reflective arm.

3. **T5 pass-through (Decision #6)** — user-supplied L_t_aperture goes
   through unchanged when atmosphere is trivial; warns when it isn't.

Plus failure-mode checks:

- Missing LOS for T1/T2/T3 → :class:`ParameterBoundsError`
- Descriptor grid mismatch vs atm grid → :class:`ParameterBoundsError`
- T5 + non-trivial atmosphere → :class:`UserWarning` emitted (Decision #6)
- Ground background without LOS → :class:`ParameterBoundsError`
- None background → returns ``None`` (Decision #13)
- Cold-space background → returns zeros
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_target_at_aperture,
)
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.descriptors import (
    AtApertureBackground,
    ColdSpaceBackground,
    GroundBackground,
    T1Thermal,
    T2Reflective,
    T3Mixed,
    T5AtAperture,
    T6TabulatedAtSource,
    UserSpectralBackground,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trivial_atm(wl: np.ndarray) -> AtmosphericQuantities:
    """τ ≡ 1, L_path ≡ 0, E_TOA = 0 — vacuum / exo-style bundle."""
    ones = np.ones_like(wl)
    zeros = np.zeros_like(wl)
    return AtmosphericQuantities(
        wavelength_um=wl,
        tau_sun=ones,
        tau_up=ones,
        tau_full_up=ones,
        E_TOA=zeros,
        E_sky_scattered=zeros,
        E_sky_thermal=zeros,
        L_path_up=zeros,
        L_path_full=zeros,
    )


def _const_sd(wl: np.ndarray, value: float, name: str, unit: str = "dimensionless") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=wl,
        values=np.full_like(wl, value, dtype=np.float64),
        unit=unit,
        source="test fixture",
    )


# ---------------------------------------------------------------------------
# Truth Anchor 1 — LWIR thermal (T1)
# ---------------------------------------------------------------------------


class TestAnchor1_LWIR_Thermal_T1:
    """Anchor 1 — LWIR thermal graybody (T1), hand calculation.

    Source: hand calculation via Planck (CODATA 2018) at λ = 10 µm, T = 300 K.

    At 10 µm, 300 K Planck spectral radiance is ≈ 9.902 W/m²/sr/µm.
    With ε = 0.95, τ_up = 0.85, L_path_up = 0.5 W/m²/sr/µm, the §6.1 T1 arm
    yields::

        L_t,aperture = ε · B(T_t) · τ_up + L_path_up
                     = 0.95 · 9.902... · 0.85 + 0.5
                     = ~8.5 W/m²/sr/µm

    This anchor is exact to the precision of Planck (6+ digits).
    """

    WL = np.array([8.0, 10.0, 12.0], dtype=np.float64)

    def test_analytic_match_at_10um(self) -> None:
        eps = 0.95
        T_t = 300.0
        tau_up = np.array([0.80, 0.85, 0.82])
        L_path_up = np.array([0.40, 0.50, 0.55])

        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.ones_like(self.WL),
            tau_up=tau_up,
            tau_full_up=tau_up,
            E_TOA=np.zeros_like(self.WL),
            E_sky_scattered=np.zeros_like(self.WL),
            E_sky_thermal=np.zeros_like(self.WL),
            L_path_up=L_path_up,
            L_path_full=L_path_up,
        )

        eps_sd = _const_sd(self.WL, eps, "epsilon", "dimensionless")
        target = T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_sd,
            T_t=T_t,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)  # nadir, no sun

        L = assemble_target_at_aperture(target, atm, los)

        # Hand computation on the full grid.
        B = planck_spectral_radiance(self.WL, T_t)
        L_expected = eps * B * tau_up + L_path_up

        np.testing.assert_allclose(L, L_expected, rtol=1e-12, atol=0.0)

    def test_matches_legacy_formula_bit_exact(self) -> None:
        """T1 with the legacy-path inputs (no sun) should reproduce the old
        L_target · τ + L_path scalar formula bit-exactly.  This is the core
        reason Cell 28 and Cell 58 anchors survive Stage 3."""
        eps = 1.0
        T_t = 285.0
        tau_up = np.array([0.72, 0.76, 0.77])
        L_path_up = np.array([0.12, 0.18, 0.21])

        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.ones_like(self.WL),
            tau_up=tau_up,
            tau_full_up=tau_up,
            E_TOA=np.zeros_like(self.WL),
            E_sky_scattered=np.zeros_like(self.WL),
            E_sky_thermal=np.zeros_like(self.WL),
            L_path_up=L_path_up,
            L_path_full=L_path_up,
        )
        eps_sd = _const_sd(self.WL, eps, "epsilon")
        target = T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_sd,
            T_t=T_t,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        L = assemble_target_at_aperture(target, atm, los)
        B = planck_spectral_radiance(self.WL, T_t)
        # Legacy: L_target = ε·B; assembly = L_target·τ + L_path.
        legacy = (eps * B) * tau_up + L_path_up
        np.testing.assert_array_equal(L, legacy)


# ---------------------------------------------------------------------------
# Truth Anchor 2 — VIS reflective two-leg (T2)
# ---------------------------------------------------------------------------


class TestAnchor2_VIS_Reflective_T2:
    """Anchor 2 — pure reflective Lambertian at VIS, hand calculation.

    Source: hand-derived from §6.1 (ε ≡ 0 branch)::

        L = ρ · [τ_sun · E_TOA · cos(θ_s)/π + (E_sky_sca + E_sky_ther)/π] · τ_up
            + L_path_up

    Numbers chosen for clean arithmetic:
        ρ = 0.3 (dimensionless)
        θ_s = 60° ⇒ cos = 0.5 exactly
        E_TOA = 1400 W/m²/µm
        τ_sun = 0.8
        τ_up = 0.9
        E_sky = 120 W/m²/µm (all scattered)
        L_path_up = 2.5 W/m²/sr/µm

    Expected::

        direct  = 0.3 · 0.8 · 1400 · 0.5 / π  =  168 / π  ≈ 53.4676...
        diffuse = 0.3 · 120 / π               =   36 / π  ≈ 11.4592...
        L = (53.4676 + 11.4592) · 0.9 + 2.5    ≈ 58.434 + 2.5 = 60.935 W/m²/sr/µm

    Exact expression (single float formula)::

        (0.3 * 0.8 * 1400 * 0.5 / pi + 0.3 * 120 / pi) * 0.9 + 2.5
    """

    WL = np.array([0.5, 0.6, 0.7], dtype=np.float64)

    def test_two_leg_analytic(self) -> None:
        rho = 0.3
        theta_s = math.pi / 3.0  # 60° → cos = 0.5
        E_TOA = 1400.0
        tau_sun = 0.8
        tau_up = 0.9
        E_sky = 120.0
        L_path = 2.5

        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, tau_sun),
            tau_up=np.full_like(self.WL, tau_up),
            tau_full_up=np.full_like(self.WL, tau_up),
            E_TOA=np.full_like(self.WL, E_TOA),
            E_sky_scattered=np.full_like(self.WL, E_sky),
            E_sky_thermal=np.zeros_like(self.WL),
            L_path_up=np.full_like(self.WL, L_path),
            L_path_full=np.full_like(self.WL, L_path),
        )
        rho_sd = _const_sd(self.WL, rho, "rho")
        target = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=rho_sd,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=theta_s)

        L = assemble_target_at_aperture(target, atm, los)

        cos_ts = math.cos(theta_s)
        direct = rho * tau_sun * E_TOA * cos_ts / math.pi
        diffuse = rho * E_sky / math.pi
        expected = (direct + diffuse) * tau_up + L_path
        np.testing.assert_allclose(L, expected, rtol=1e-14, atol=0.0)

    def test_sun_below_horizon_zeros_direct(self) -> None:
        """cos(θ_s) ≤ 0 must null the direct-solar term."""
        rho = 0.3
        theta_s = math.pi  # 180°: cos = -1, sun on the far side
        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, 0.8),
            tau_up=np.full_like(self.WL, 0.9),
            tau_full_up=np.full_like(self.WL, 0.9),
            E_TOA=np.full_like(self.WL, 1400.0),
            E_sky_scattered=np.zeros_like(self.WL),
            E_sky_thermal=np.zeros_like(self.WL),
            L_path_up=np.zeros_like(self.WL),
            L_path_full=np.zeros_like(self.WL),
        )
        rho_sd = _const_sd(self.WL, rho, "rho")
        target = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=rho_sd,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=theta_s)

        L = assemble_target_at_aperture(target, atm, los)
        np.testing.assert_allclose(L, 0.0, atol=0.0)

    def test_no_sun_zeros_direct(self) -> None:
        """theta_s = None must null the direct-solar term."""
        rho = 0.3
        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, 0.8),
            tau_up=np.full_like(self.WL, 0.9),
            tau_full_up=np.full_like(self.WL, 0.9),
            E_TOA=np.full_like(self.WL, 1400.0),
            E_sky_scattered=np.zeros_like(self.WL),
            E_sky_thermal=np.zeros_like(self.WL),
            L_path_up=np.zeros_like(self.WL),
            L_path_full=np.zeros_like(self.WL),
        )
        rho_sd = _const_sd(self.WL, rho, "rho")
        target = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=rho_sd,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=None)

        L = assemble_target_at_aperture(target, atm, los)
        np.testing.assert_allclose(L, 0.0, atol=0.0)


# ---------------------------------------------------------------------------
# Truth Anchor 3 — T5 pass-through (Decision #6)
# ---------------------------------------------------------------------------


class TestAnchor3_T5_PassThrough:
    """Anchor 3 — T5AtAperture pass-through behavior (Decision #6).

    Source: specification in ``docs/Option_C_Implementation_Plan.md``
    Stage 3 Decision #6.

    - Trivial atmosphere (τ_up ≡ 1, L_path ≡ 0) → pass through bit-exactly,
      no warning.
    - Non-trivial atmosphere → pass through bit-exactly, **but** emit a
      :class:`UserWarning` so the user sees that the atmosphere is ignored
      (Rule 17 — no silent bypass).
    """

    WL = np.linspace(3.0, 5.0, 21)

    def test_trivial_atm_passes_through_without_warning(self) -> None:
        """When τ_up = 1 and L_path_up = 0, the pass-through is silent."""
        L_user = np.linspace(1.0, 2.0, self.WL.size)
        L_sd = SpectralData(
            name="L_t_aperture",
            wavelength_um=self.WL,
            values=L_user,
            unit="W/m²/sr/µm",
            source="test user spectrum",
        )
        target = T5AtAperture(
            scene_type="extended",
            target_location="at_aperture",
            L_t_aperture=L_sd,
        )
        atm = _trivial_atm(self.WL)

        with warnings.catch_warnings():
            warnings.simplefilter("error")  # promote UserWarning to error
            L = assemble_target_at_aperture(target, atm, los=None)

        np.testing.assert_array_equal(L, L_user)

    def test_nontrivial_atm_warns_but_passes_through(self) -> None:
        """τ_up < 1 anywhere → UserWarning, but the spectrum is still passed through."""
        L_user = np.linspace(1.0, 2.0, self.WL.size)
        L_sd = SpectralData(
            name="L_t_aperture",
            wavelength_um=self.WL,
            values=L_user,
            unit="W/m²/sr/µm",
            source="test user spectrum",
        )
        target = T5AtAperture(
            scene_type="extended",
            target_location="at_aperture",
            L_t_aperture=L_sd,
        )
        # Non-trivial atmosphere: τ_up = 0.5 throughout.
        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.ones_like(self.WL),
            tau_up=np.full_like(self.WL, 0.5),
            tau_full_up=np.full_like(self.WL, 0.5),
            E_TOA=np.zeros_like(self.WL),
            E_sky_scattered=np.zeros_like(self.WL),
            E_sky_thermal=np.zeros_like(self.WL),
            L_path_up=np.full_like(self.WL, 0.1),
            L_path_full=np.full_like(self.WL, 0.1),
        )

        with pytest.warns(UserWarning, match="pass-through arm ignores the atmosphere"):
            L = assemble_target_at_aperture(target, atm, los=None)
        # Pass-through is bit-exact even with the warning.
        np.testing.assert_array_equal(L, L_user)


# ---------------------------------------------------------------------------
# T3 mixed emit+reflect (Kirchhoff) — bonus equation check
# ---------------------------------------------------------------------------


class TestT3Kirchhoff:
    """T3 = T1 + T2 with ρ = 1 − ε (Kirchhoff) — equation check only.

    Stage 6 (Option C) — MWIR-mixed anchor: the ``E_sky`` consumed by
    ``_diffuse_sky_term`` is the exact sum of the two published
    per-component fields (scattered-solar + atmospheric-thermal).  The
    equation math is otherwise unchanged; the decomposition only unlocks
    per-component audits (matrix cells 25/26/40/41).
    """

    WL = np.array([3.5, 4.0, 4.5])

    def test_t3_equals_t1_plus_t2_with_kirchhoff(self) -> None:
        eps_val = 0.6
        T_t = 310.0
        # MWIR-mixed pinning (Stage 6): both diffuse components are
        # non-zero and of the same order — the crossover regime that
        # motivates the decomposition.  10 and 5 W/m²/µm are arbitrary
        # hand-picked magnitudes; what matters is the Kirchhoff equation
        # consumes their *sum* via _diffuse_sky_term.
        E_sky_scattered = np.full_like(self.WL, 10.0)
        E_sky_thermal = np.full_like(self.WL, 5.0)
        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, 0.5),
            tau_up=np.full_like(self.WL, 0.7),
            tau_full_up=np.full_like(self.WL, 0.7),
            E_TOA=np.full_like(self.WL, 200.0),
            E_sky_scattered=E_sky_scattered,
            E_sky_thermal=E_sky_thermal,
            L_path_up=np.full_like(self.WL, 0.3),
            L_path_full=np.full_like(self.WL, 0.3),
        )
        eps_sd = _const_sd(self.WL, eps_val, "epsilon")
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=math.pi / 4.0)

        target = T3Mixed(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_sd,
            T_t=T_t,
        )
        L = assemble_target_at_aperture(target, atm, los)

        # Hand-computed reference: same §6.1 equation, evaluated directly.
        cos_ts = math.cos(math.pi / 4.0)
        rho = 1.0 - eps_val
        B = planck_spectral_radiance(self.WL, T_t)
        L_self = eps_val * B
        direct = rho * atm.tau_sun * atm.E_TOA * cos_ts / math.pi
        # Stage 6: the MWIR-mixed anchor asserts that the assembly math
        # consumes E_sky_scattered + E_sky_thermal — not either term in
        # isolation.  This guards against a future refactor silently
        # dropping one of the two components.
        E_sky_sum = atm.E_sky_scattered + atm.E_sky_thermal
        diffuse = rho * E_sky_sum / math.pi
        expected = (L_self + direct + diffuse) * atm.tau_up + atm.L_path_up
        np.testing.assert_allclose(L, expected, rtol=1e-14, atol=0.0)

    def test_report_components_sums_back_to_total(self) -> None:
        """Stage 6 (Option C) introspection — AssemblyComponents reconstructs L.

        When ``report_components=True``, :func:`assemble_target_at_aperture`
        returns the per-term arrays alongside the total.  This test
        verifies the arithmetic identity::

            total = (self_emission
                     + direct_solar
                     + diffuse_sky_scattered
                     + diffuse_sky_thermal) · τ_up
                  + L_path_up

        so that users auditing the MWIR crossover can trust the
        per-component breakdown matches the summed radiance bit-for-bit.
        """
        eps_val = 0.6
        T_t = 310.0
        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, 0.5),
            tau_up=np.full_like(self.WL, 0.7),
            tau_full_up=np.full_like(self.WL, 0.7),
            E_TOA=np.full_like(self.WL, 200.0),
            E_sky_scattered=np.full_like(self.WL, 10.0),
            E_sky_thermal=np.full_like(self.WL, 5.0),
            L_path_up=np.full_like(self.WL, 0.3),
            L_path_full=np.full_like(self.WL, 0.3),
        )
        eps_sd = _const_sd(self.WL, eps_val, "epsilon")
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=math.pi / 4.0)
        target = T3Mixed(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_sd,
            T_t=T_t,
        )
        comps = assemble_target_at_aperture(target, atm, los, report_components=True)
        # All four pre-τ branches must be individually non-negative and
        # their τ_up-weighted sum + path_up must equal ``total``.
        reconstructed = (
            (
                comps.self_emission
                + comps.direct_solar
                + comps.diffuse_sky_scattered
                + comps.diffuse_sky_thermal
            )
            * comps.tau_up_factor
            + comps.path_up
        )
        np.testing.assert_allclose(comps.total, reconstructed, rtol=1e-14, atol=0.0)
        # MWIR mixed: T3 with sun up has all three non-path branches > 0.
        assert np.all(comps.self_emission > 0.0)
        assert np.all(comps.direct_solar > 0.0)
        assert np.all(comps.diffuse_sky_scattered > 0.0)
        assert np.all(comps.diffuse_sky_thermal > 0.0)


# ---------------------------------------------------------------------------
# Failure-mode coverage (Category C requirement)
# ---------------------------------------------------------------------------


class TestFailureModes:
    WL = np.array([8.0, 10.0, 12.0], dtype=np.float64)

    def _make_t1(self) -> T1Thermal:
        eps_sd = _const_sd(self.WL, 0.9, "epsilon")
        return T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_sd,
            T_t=300.0,
        )

    def test_t1_without_los_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="requires a LineOfSightGeometry"):
            assemble_target_at_aperture(self._make_t1(), _trivial_atm(self.WL), los=None)

    def test_descriptor_grid_mismatch_raises(self) -> None:
        # Build a T1 whose epsilon lives on a shifted grid.
        bad_grid = self.WL + 0.5
        eps_sd = _const_sd(bad_grid, 0.9, "epsilon")
        target = T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_sd,
            T_t=300.0,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="does not match"):
            assemble_target_at_aperture(target, _trivial_atm(self.WL), los)

    def test_ground_background_without_los_raises(self) -> None:
        eps_g_sd = _const_sd(self.WL, 0.95, "epsilon_g")
        bg = GroundBackground(epsilon_g=eps_g_sd, T_g=290.0)
        with pytest.raises(ParameterBoundsError, match="GroundBackground requires"):
            assemble_background_at_aperture(bg, _trivial_atm(self.WL), los=None)

    def test_none_background_returns_none(self) -> None:
        # Decision #13: SpectralIntegrationStage handles the computed-extended
        # background photon term itself; assembly passes None through.
        result = assemble_background_at_aperture(None, _trivial_atm(self.WL), los=None)
        assert result is None

    def test_cold_space_background_zeros(self) -> None:
        bg = ColdSpaceBackground()
        L = assemble_background_at_aperture(bg, _trivial_atm(self.WL), los=None)
        assert L is not None
        np.testing.assert_array_equal(L, np.zeros_like(self.WL))

    def test_at_aperture_background_none_radiance_zeros(self) -> None:
        """Decision #14: missing L_bg_aperture → treated as zero."""
        bg = AtApertureBackground(L_bg_aperture=None)
        L = assemble_background_at_aperture(bg, _trivial_atm(self.WL), los=None)
        assert L is not None
        np.testing.assert_array_equal(L, np.zeros_like(self.WL))

    def test_at_aperture_background_passes_through(self) -> None:
        values = np.full_like(self.WL, 3.14)
        L_sd = SpectralData(
            name="L_bg_aperture",
            wavelength_um=self.WL,
            values=values,
            unit="W/m²/sr/µm",
            source="test",
        )
        bg = AtApertureBackground(L_bg_aperture=L_sd)
        L = assemble_background_at_aperture(bg, _trivial_atm(self.WL), los=None)
        assert L is not None
        np.testing.assert_array_equal(L, values)

    def test_user_spectral_background_passes_through(self) -> None:
        values = np.full_like(self.WL, 2.0)
        L_sd = SpectralData(
            name="L_bg",
            wavelength_um=self.WL,
            values=values,
            unit="W/m²/sr/µm",
            source="test",
        )
        bg = UserSpectralBackground(L_bg=L_sd)
        L = assemble_background_at_aperture(bg, _trivial_atm(self.WL), los=None)
        assert L is not None
        np.testing.assert_array_equal(L, values)


# ---------------------------------------------------------------------------
# Ground-background assembly — equation check
# ---------------------------------------------------------------------------


class TestGroundBackgroundAssembly:
    WL = np.array([8.0, 10.0, 12.0], dtype=np.float64)

    def test_ground_background_matches_T3_formula_at_h0(self) -> None:
        """GroundBackground is modeled as T3 Kirchhoff at h = 0, using
        τ_full_up and L_path_full."""
        eps_g = 0.95
        T_g = 290.0
        atm = AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, 0.85),
            tau_up=np.full_like(self.WL, 0.82),
            tau_full_up=np.full_like(self.WL, 0.78),
            E_TOA=np.full_like(self.WL, 0.0),
            E_sky_scattered=np.full_like(self.WL, 0.0),
            E_sky_thermal=np.full_like(self.WL, 4.0),
            L_path_up=np.full_like(self.WL, 0.8),
            L_path_full=np.full_like(self.WL, 1.2),
        )
        eps_g_sd = _const_sd(self.WL, eps_g, "epsilon_g")
        bg = GroundBackground(epsilon_g=eps_g_sd, T_g=T_g)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)  # no sun

        L = assemble_background_at_aperture(bg, atm, los)
        assert L is not None

        rho_g = 1.0 - eps_g
        B = planck_spectral_radiance(self.WL, T_g)
        diffuse = rho_g * (atm.E_sky_scattered + atm.E_sky_thermal) / math.pi
        expected = (eps_g * B + diffuse) * atm.tau_full_up + atm.L_path_full
        np.testing.assert_allclose(L, expected, rtol=1e-14, atol=0.0)


# ---------------------------------------------------------------------------
# T6TabulatedAtSource assembly (ADR-0003)
# ---------------------------------------------------------------------------


class TestT6Assembly:
    """T6 tabulated-at-source: L_source·τ_up + L_path_up exactly."""

    WL = np.array([8.0, 10.0, 12.0, 14.0], dtype=np.float64)

    def _atm(self) -> AtmosphericQuantities:
        return AtmosphericQuantities(
            wavelength_um=self.WL,
            tau_sun=np.full_like(self.WL, 1.0),
            tau_up=np.array([0.8, 0.7, 0.6, 0.5], dtype=np.float64),
            tau_full_up=np.array([0.8, 0.7, 0.6, 0.5], dtype=np.float64),
            E_TOA=np.full_like(self.WL, 1400.0),
            E_sky_scattered=np.full_like(self.WL, 0.0),
            E_sky_thermal=np.full_like(self.WL, 5.0),
            L_path_up=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64),
            L_path_full=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64),
        )

    def _L_source(self, values: np.ndarray) -> SpectralData:
        return SpectralData(
            name="L_t_source",
            wavelength_um=self.WL,
            values=np.asarray(values, dtype=np.float64),
            unit="W/m^2/sr/um",
            source="test_t6_assembly",
        )

    def test_assembly_math_matches_closed_form(self) -> None:
        """L_t_source · τ_up + L_path_up — no reflective terms, no ε/B."""
        atm = self._atm()
        L_src_vals = np.array([2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        target = T6TabulatedAtSource(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_source=self._L_source(L_src_vals),
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        L_aperture = assemble_target_at_aperture(target, atm, los)

        expected = L_src_vals * atm.tau_up + atm.L_path_up
        np.testing.assert_allclose(
            L_aperture, expected, rtol=1e-14, atol=0.0,
        )

    def test_trivial_atmosphere_is_identity(self) -> None:
        """τ ≡ 1, L_path ≡ 0 — T6 returns L_source unchanged."""
        atm = _trivial_atm(self.WL)
        L_src_vals = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
        target = T6TabulatedAtSource(
            scene_type="extended",
            target_location="no_atmosphere",
            no_atmosphere_subcase="space",
            h_tgt=0.0,
            L_t_source=self._L_source(L_src_vals),
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        L_aperture = assemble_target_at_aperture(target, atm, los)

        np.testing.assert_allclose(
            L_aperture, L_src_vals, rtol=1e-14, atol=0.0,
        )

    def test_components_report(self) -> None:
        """report_components puts L_source under self_emission; ρ-terms zero."""
        atm = self._atm()
        L_src_vals = np.array([2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        target = T6TabulatedAtSource(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_source=self._L_source(L_src_vals),
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

        comp = assemble_target_at_aperture(
            target, atm, los, report_components=True,
        )

        np.testing.assert_allclose(comp.self_emission, L_src_vals)
        np.testing.assert_allclose(comp.direct_solar, np.zeros_like(self.WL))
        np.testing.assert_allclose(
            comp.diffuse_sky_scattered, np.zeros_like(self.WL),
        )
        np.testing.assert_allclose(
            comp.diffuse_sky_thermal, np.zeros_like(self.WL),
        )
        np.testing.assert_allclose(comp.tau_up_factor, atm.tau_up)
        np.testing.assert_allclose(comp.path_up, atm.L_path_up)
        np.testing.assert_allclose(
            comp.total, L_src_vals * atm.tau_up + atm.L_path_up,
        )

    def test_grid_mismatch_raises(self) -> None:
        atm = self._atm()
        bad = SpectralData(
            name="L_t_source",
            wavelength_um=np.array([3.0, 5.0], dtype=np.float64),  # MWIR grid
            values=np.array([1.0, 1.0], dtype=np.float64),
            unit="W/m^2/sr/um",
            source="test_t6_assembly",
        )
        target = T6TabulatedAtSource(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_source=bad,
        )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(
            ParameterBoundsError, match=r"grid does not match",
        ):
            assemble_target_at_aperture(target, atm, los)

    def test_missing_los_raises(self) -> None:
        atm = self._atm()
        target = T6TabulatedAtSource(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_source=self._L_source(np.ones_like(self.WL)),
        )
        with pytest.raises(
            ParameterBoundsError, match=r"requires a LineOfSightGeometry",
        ):
            assemble_target_at_aperture(target, atm, None)


__all__: list[str] = []
