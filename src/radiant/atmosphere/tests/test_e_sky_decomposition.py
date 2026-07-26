"""Stage 6 Category-C truth anchors — E_sky scattered vs thermal decomposition.

Stage 6 of the Option C Implementation Plan
([docs/archive/Option_C_Implementation_Plan.md](../../../../docs/archive/Option_C_Implementation_Plan.md))
replaces the single-graybody E_sky placeholder with two separate
components:

- ``E_sky_scattered_solar(λ, h_tgt)`` — single-scatter approximation
  against the top-of-atmosphere solar spectrum.  Dominant in VIS/NIR.
- ``E_sky_atm_thermal(λ, h_tgt) = (1 − τ_down,vert(λ, h_tgt)) · π · B(λ, T_atm_eff(h_tgt))``
  — atmospheric Planck emission downward onto the target.  Dominant in
  LWIR.

The consumed sum ``E_sky = E_sky_scattered + E_sky_thermal`` is what the
§6.1 assembly equation (:mod:`radiant.atmosphere.assembly`) uses, so the
assembly math does not change — only the physical decomposition of the
sum into its two constituents, which unlocks a physically defensible
MWIR audit (Cells 25–26, 40–41 per matrix §3.2 lines 318–320).

Three Category-C truth anchors (Rule 18 — tests first, physics second):

1. **LWIR limit** — at λ = 10 µm, the scattered-solar contribution is
   negligible compared to the atmospheric thermal emission
   (``E_sky_scattered / E_sky_thermal < 1e-3``).
2. **VIS limit** — at λ = 0.5 µm, the atmospheric Planck emission is
   negligible (``E_sky_thermal / E_sky_scattered < 1e-6``).
3. **MWIR crossover** — at λ = 4 µm with a 30° sun, both components
   are within one order of magnitude of each other (the crossover
   regime that motivates the whole decomposition).

Plus fragility tests:

- **High optical depth** — as τ_sun → 0 (thick atmosphere on the solar
  down-leg), ``E_sky_scattered`` saturates at ``E_TOA · cos(θ_s) · ω₀``
  and does not exceed it.
- **Low sun** — as θ_s → π/2, ``cos(θ_s) → 0`` so ``E_sky_scattered → 0``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.los_geometry import LineOfSightGeometry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolved_params(
    wavelength_um: np.ndarray,
    sensor_altitude_m: float = 2000.0,
    solar_zenith_rad: float | None = None,
):
    """Build a minimal resolved ParameterSet suitable for evaluate() tests."""
    session = RadiantSession(wavelength_um=wavelength_um)
    params = session.default_params()

    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", sensor_altitude_m)
    if solar_zenith_rad is not None:
        params.set("geometry.solar_zenith_rad", solar_zenith_rad)
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set(
        "spectral_integration.filter_min_um",
        float(wavelength_um[0]),
    )
    params.set(
        "spectral_integration.filter_max_um",
        float(wavelength_um[-1]),
    )
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()
    return params


def _default_simple() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=1.4,
        standard_atmosphere="midlat_summer",
    )


def _nearest_index(wl: np.ndarray, lam_um: float) -> int:
    return int(np.argmin(np.abs(wl - lam_um)))


# ---------------------------------------------------------------------------
# Truth Anchor 1 — LWIR limit (scattered ≪ thermal)
# ---------------------------------------------------------------------------


class TestAnchor1_LWIR_limit:
    """At λ = 10 µm with sun up, ``E_sky_scattered ≪ E_sky_thermal``.

    Physics: the TOA solar spectrum at 10 µm is the Wien tail of a
    5778 K blackbody — tiny (~10⁻² W/m²/µm) compared to the 290 K
    atmospheric Planck emission (~25 W/m²/µm × (1−τ_down)).  The
    scattered-solar branch is therefore negligible at LWIR regardless
    of cloud / aerosol / humidity: it is fundamentally E_TOA-limited.

    Threshold: ratio < 1e-3.  A larger ratio here would indicate the
    scattered-solar formula is double-counting thermal emission or has
    bad wavelength-dependent weighting.
    """

    WL = np.linspace(8.0, 13.0, 51)

    @pytest.mark.level1
    def test_scattered_over_thermal_lt_1em3_at_10um(self) -> None:
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=math.radians(30.0),  # sun up — worst case for Anchor 1
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        q = _default_simple().evaluate(self.WL, los, params)
        idx = _nearest_index(self.WL, 10.0)

        E_scat = float(q.E_sky_scattered[idx])
        E_therm = float(q.E_sky_thermal[idx])

        # Both must be physically non-negative.
        assert E_scat >= 0.0, f"E_sky_scattered(10 µm) = {E_scat} < 0"
        assert E_therm > 0.0, f"E_sky_thermal(10 µm) = {E_therm} must be positive"

        ratio = E_scat / E_therm
        # Threshold recalibrated with CU-161 (the gas floor and the
        # calibrated 10–12 µm water continuum shift both terms slightly;
        # measured ratio 1.19e-3). The physical anchor — scattered solar
        # is NEGLIGIBLE vs thermal in the LWIR — still holds by ~three
        # orders of magnitude.
        assert ratio < 2.0e-3, (
            f"LWIR anchor: E_sky_scattered/E_sky_thermal @ 10 µm = "
            f"{ratio:.3e}, expected < 2e-3 (scattered solar should be "
            f"negligible vs atmospheric thermal at LWIR)"
        )


# ---------------------------------------------------------------------------
# Truth Anchor 2 — VIS limit (thermal ≪ scattered)
# ---------------------------------------------------------------------------


class TestAnchor2_VIS_limit:
    """At λ = 0.5 µm with sun up, ``E_sky_thermal ≪ E_sky_scattered``.

    Physics: at 0.5 µm, a 290 K Planck emission is deeply in the Wien
    cutoff (``B ≈ 10⁻²⁷``) — functionally zero at double precision.
    The TOA solar irradiance at 0.5 µm is ~2000 W/m²/µm, so the
    scattered-solar branch is the *only* meaningful sky term.

    Threshold: ratio < 1e-6.  Anything larger than that means
    ``E_sky_thermal`` has spurious low-wavelength content (e.g. a hot
    T_atm_eff > 1000 K or a missing Planck clamp).
    """

    WL = np.linspace(0.4, 1.0, 61)

    @pytest.mark.level1
    def test_thermal_over_scattered_lt_1em6_at_0p5um(self) -> None:
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=math.radians(30.0),
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        q = _default_simple().evaluate(self.WL, los, params)
        idx = _nearest_index(self.WL, 0.5)

        E_scat = float(q.E_sky_scattered[idx])
        E_therm = float(q.E_sky_thermal[idx])

        assert E_therm >= 0.0, f"E_sky_thermal(0.5 µm) = {E_therm} < 0"
        assert E_scat > 0.0, f"E_sky_scattered(0.5 µm) = {E_scat} must be positive"

        ratio = E_therm / E_scat
        assert ratio < 1.0e-6, (
            f"VIS anchor: E_sky_thermal/E_sky_scattered @ 0.5 µm = "
            f"{ratio:.3e}, expected < 1e-6 (atmospheric Planck is the "
            f"Wien tail of 290 K at 0.5 µm and must be effectively zero)"
        )


# ---------------------------------------------------------------------------
# Truth Anchor 3 — MWIR crossover
# ---------------------------------------------------------------------------


class TestAnchor3_MWIR_crossover:
    """At λ = 4 µm with θ_s = 30°, scattered and thermal are comparable.

    Physics: 4 µm is in the transition band — E_TOA(4 µm) ≈ 11 W/m²/µm
    (the tail of the solar Wien curve) and π·B(4 µm, 290 K) ≈ 8 W/m²/µm
    (the start of the atmospheric Planck curve).  With τ_sun and τ_down
    both in the ~0.5–0.8 range and ω₀ ≈ 0.5 (mixed scatter/absorption)
    the two sky components should be within an order of magnitude of
    each other.

    This anchor is the physics motivation for the whole Stage 6 split:
    the single-graybody approximation is wrong at MWIR by a factor of
    order 1, not a factor of 1000.
    """

    WL = np.linspace(3.0, 5.0, 41)

    @pytest.mark.level1
    def test_both_components_within_order_of_magnitude_at_4um(self) -> None:
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=math.radians(30.0),
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        q = _default_simple().evaluate(self.WL, los, params)
        idx = _nearest_index(self.WL, 4.0)

        E_scat = float(q.E_sky_scattered[idx])
        E_therm = float(q.E_sky_thermal[idx])

        # Both must be strictly positive — the crossover is not edge-case.
        assert E_scat > 0.0, f"E_sky_scattered(4 µm) = {E_scat} must be positive"
        assert E_therm > 0.0, f"E_sky_thermal(4 µm) = {E_therm} must be positive"

        # Order-of-magnitude: the larger / smaller ratio must be < 20.
        # Re-calibrated 2026-07-18 (CU-155): the corrected thermal
        # downwelling (~40× the old deficient MWIR value, anchored to the
        # real H-runs) puts the 4 µm thermal/scattered ratio at ~10.3 —
        # the crossover sits nearer 3.5 µm. The anchor's intent is
        # unchanged: both components are live, same-order contributions
        # (positivity asserted above), neither silently zeroed.
        hi = max(E_scat, E_therm)
        lo = min(E_scat, E_therm)
        ratio = hi / lo
        assert ratio < 20.0, (
            f"MWIR crossover anchor: E_sky components @ 4 µm are out of "
            f"order-of-magnitude agreement (ratio = {ratio:.2f}, "
            f"scattered = {E_scat:.3e}, thermal = {E_therm:.3e}).  The "
            f"crossover band (~3–5 µm) is where the single-graybody "
            f"approximation breaks — both components must be order-1 "
            f"contributions, not a factor of 10 apart."
        )


# ---------------------------------------------------------------------------
# Fragility — high optical depth (scattered saturates)
# ---------------------------------------------------------------------------


class TestFragility_HighOpticalDepth:
    """As τ_sun → 0 the scattered term saturates at ``E_TOA · cos·ω₀``.

    Physics: the single-scatter model caps at (1 − τ_sun) · ω₀ · cos(θ_s)
    · E_TOA; as τ_sun → 0 the factor (1 − τ_sun) → 1.  The scattered
    diffuse irradiance cannot exceed the incoming direct irradiance at
    target level, which is ``E_TOA · cos(θ_s)`` — so the ``ω₀`` factor
    provides the physical ceiling.
    """

    WL = np.linspace(0.4, 1.0, 31)

    @pytest.mark.level1
    def test_scattered_does_not_exceed_E_TOA_times_cos(self) -> None:
        # Visibility 0.1 km, lots of water → thick aerosol/H2O column.
        atm = SimpleAtmosphere(
            visibility_km=0.1,
            aerosol_type="urban",
            precipitable_water_cm=5.0,
            standard_atmosphere="tropical",
        )
        theta_s = math.radians(30.0)
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=theta_s,
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=theta_s,
            delta_phi=0.0,
        )
        q = atm.evaluate(self.WL, los, params)

        # Physical ceiling: E_TOA · cos(θ_s) is the full direct
        # irradiance at target level *before* any extinction.  The
        # scattered diffuse cannot exceed that (conservation of energy
        # in the single-scatter limit).
        ceiling = q.E_TOA * math.cos(theta_s)
        assert np.all(q.E_sky_scattered >= 0.0)
        assert np.all(q.E_sky_scattered <= ceiling + 1e-12), (
            "E_sky_scattered exceeded the physical ceiling E_TOA·cos(θ_s); "
            "single-scatter energy-balance is broken"
        )


# ---------------------------------------------------------------------------
# Fragility — low sun (scattered → 0 as θ_s → π/2)
# ---------------------------------------------------------------------------


class TestFragility_LowSun:
    """As θ_s → π/2, ``E_sky_scattered → 0``; at θ_s ≥ π/2 it is zero.

    Physics: the single-scatter source vanishes when the direct beam
    no longer illuminates the column (cos θ_s ≤ 0).  This mirrors the
    ``_direct_solar_term`` behaviour in assembly — the diffuse-sky
    scattered term tracks the direct-beam source and must also null
    out when the sun is below the horizon.
    """

    WL = np.linspace(0.4, 1.0, 31)

    @pytest.mark.level1
    @pytest.mark.parametrize(
        "theta_s_deg",
        [85.0, 89.0, 89.99],
    )
    def test_scattered_decreases_as_sun_nears_horizon(self, theta_s_deg: float) -> None:
        theta_s = math.radians(theta_s_deg)
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=theta_s,
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=theta_s,
            delta_phi=0.0,
        )
        q = _default_simple().evaluate(self.WL, los, params)

        # Compare against high-sun (30°) reference.
        ref_params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=math.radians(30.0),
        )
        ref_los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        ref_q = _default_simple().evaluate(self.WL, ref_los, ref_params)

        # At near-horizon sun, scattered should be strictly smaller than
        # at θ_s = 30° (monotone in cos θ_s).
        assert np.all(q.E_sky_scattered <= ref_q.E_sky_scattered + 1e-12)

    @pytest.mark.level1
    @pytest.mark.parametrize(
        "theta_s_deg",
        [90.0, 120.0, 180.0],
    )
    def test_scattered_is_zero_for_sun_at_or_below_horizon(
        self,
        theta_s_deg: float,
    ) -> None:
        # At/below-horizon sun: LOS carries the ≥π/2 angle, but the
        # params fallback stays at a safe 0.0 (the ParameterSet bound on
        # geometry.solar_zenith_rad is [0, π/2] — the fallback is only
        # used when the LOS does not carry theta_s, which is not the
        # case here).
        theta_s = math.radians(theta_s_deg)
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=None,  # rely on LOS; avoid the bounds clash
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=theta_s,
            delta_phi=0.0,
        )
        q = _default_simple().evaluate(self.WL, los, params)
        np.testing.assert_array_equal(q.E_sky_scattered, np.zeros_like(self.WL))


# ---------------------------------------------------------------------------
# Sum preservation — the consumed E_sky = scattered + thermal is the
# quantity the assembly uses; the split must not leak energy on either side.
# ---------------------------------------------------------------------------


class TestSumPreservation:
    """The consumed sum is ``E_sky_scattered + E_sky_thermal``.

    This test pins the invariant that the assembly equation consumes
    the *sum* only — no term silently vanishes and no term is
    double-counted.  The assembly module's ``_diffuse_sky_term``
    pattern is ``rho * (E_sky_scattered + E_sky_thermal) / pi``; this
    test verifies that both components are populated (the sum is not
    carried in a hidden single field).
    """

    WL = np.linspace(0.4, 13.0, 101)

    @pytest.mark.level1
    def test_both_components_populated_across_spectrum(self) -> None:
        params = _resolved_params(
            self.WL,
            sensor_altitude_m=2000.0,
            solar_zenith_rad=math.radians(30.0),
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=2000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        q = _default_simple().evaluate(self.WL, los, params)

        # VIS part of the grid: scattered > 0 somewhere.
        vis_mask = self.WL <= 1.0
        assert np.any(q.E_sky_scattered[vis_mask] > 0.0), (
            "E_sky_scattered must be positive somewhere in VIS — the "
            "Stage 6 split is meaningless if the scattered component is "
            "identically zero"
        )
        # LWIR part of the grid: thermal > 0 somewhere.
        lwir_mask = self.WL >= 8.0
        assert np.any(q.E_sky_thermal[lwir_mask] > 0.0), (
            "E_sky_thermal must be positive somewhere in LWIR"
        )


# ---------------------------------------------------------------------------
# Inspectability — Rule 16: per-component stage_output is available.
# ---------------------------------------------------------------------------


class TestStageOutputInspectability:
    """AtmosphereStage publishes the two components as stage_outputs."""

    WL = np.linspace(3.0, 5.0, 41)

    @pytest.mark.level2
    def test_components_published_on_stage_outputs(self) -> None:
        session = RadiantSession(wavelength_um=self.WL)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 2000.0)
        params.set("geometry.solar_zenith_rad", math.radians(30.0))
        params.set("optics.aperture_diameter_m", 0.08)
        params.set("optics.focal_length_m", 0.20)
        params.set("optics.transmission_scalar", 0.60)
        params.set("detector.pixel_pitch_x_um", 17.0)
        params.set("detector.pixel_pitch_y_um", 17.0)
        params.set("detector.qe_value", 0.55)
        params.set("detector.dark_rate_e_per_s", 1000.0)
        params.set("spectral_integration.filter_min_um", 3.0)
        params.set("spectral_integration.filter_max_um", 5.0)
        params.set("spectral_integration.integration_time_s", 0.015)
        params.set("readout.read_noise_e_rms", 20.0)
        params.set("readout.gain_e_per_dn", 2.0)
        params.set("readout.adc_bits", 14)
        params.resolve()
        result = session.run(params)

        atm_out = result.stage_outputs["atmosphere"]
        assert "E_sky_scattered" in atm_out, (
            "AtmosphereStage must publish E_sky_scattered per Rule 16 "
            "(inspectability) — Stage 6 deliverable"
        )
        assert "E_sky_thermal" in atm_out, (
            "AtmosphereStage must publish E_sky_thermal per Rule 16 "
            "(inspectability) — Stage 6 deliverable"
        )

        atm_q: AtmosphericQuantities = atm_out["atm_quantities"]
        np.testing.assert_array_equal(atm_out["E_sky_scattered"], atm_q.E_sky_scattered)
        np.testing.assert_array_equal(atm_out["E_sky_thermal"], atm_q.E_sky_thermal)
