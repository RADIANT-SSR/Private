"""End-to-end proof for the **direction-aware atmosphere** (Phase 2, ADR-0011).

Phase 1 made the *geometry core* direction-general; Phase 2 supplies the
radiometry.  ``AtmosphereStage`` now dispatches on the derived
``los.los_direction``: ``down`` takes the backend's own ``evaluate`` unchanged
and byte-identical, while ``up`` and ``level`` are served by path-segment
composition (``atmosphere/observer_leg.py`` → ``segment_simple.py`` /
``level_arm.py``, assembled by ``uplooking_quantities.py``).  Landing with it:
``SkyBackground`` (matrix B2) as the Rule-B default for an ascending LOS, and
the GF-9 per-altitude shadow-height illumination test.

Unit tests pin each of those pieces in isolation.  This module pins the
**scenes** — the four owner-priority classes of plan §8.3, each run through
the real ``RadiantSession`` from parameters to metrics:

1. :class:`TestGroundToAirMwirDetection` — worked example E2, priority 1.
2. :class:`TestAirToAirLevelMwir` — worked example E5, priority 2.
3. :class:`TestSunlitTargetOverDarkGround` — the GF-9 payoff, the scene family
   that was *inexpressible* before decision 21 widened ``solar_zenith_rad``.
4. :class:`TestProvisionalScatteredSkyWarning` — the §8.3 answer-3 band gate.
5. :class:`TestCrossModelAgreement` — simple vs the shipped MODTRAN-derived
   up-looking library, and simple vs the raw K4 tape7, with the disagreement
   **recorded as a number** rather than hidden behind a loose tolerance.
6. :class:`TestExoPathStillExactVacuum` — the Phase-1 LEO→GEO quick win must
   survive the deletion of ``evaluate_with_exo_target`` (guardrail G4).

Zero drift is not tested here: that every down-looking baseline is unchanged
is the whole golden suite's job (plan §3 principle 3).
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere.solar_shadow import shadow_height_m, sunlit
from radiant.core.constants import R_EARTH_M, c, h, k_B
from radiant.core.parameters import ParameterSet
from radiant.core.regime import RadiometricRegime

# ---------------------------------------------------------------------------
# Grids and scene constants
# ---------------------------------------------------------------------------

MWIR_WL = np.linspace(3.5, 5.0, 61)
LWIR_WL = np.linspace(8.0, 12.0, 81)
VIS_WL = np.linspace(0.45, 0.80, 71)

#: Hot-plume-like point target — the E2/E5 detection subject.
TARGET_T_K = 500.0
TARGET_EPS = 0.9
#: Small enough that the matrix §7 point-source guard is satisfied at every
#: range used here (√A_t/d ≤ 0.1·PSF_FWHM).
TARGET_AREA_M2 = 1.0e-6

_REAL_RUNS = Path(__file__).resolve().parents[2] / "modtran" / "real_runs"
_SHIPPED_UPLOOKING = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "radiant"
    / "data"
    / "tables"
    / "atmospheres"
    / "midlat_summer_uplooking_ladder"
)


# ---------------------------------------------------------------------------
# Scene builders
# ---------------------------------------------------------------------------


def _seed_system(params: ParameterSet, band: str) -> None:
    """Seed a physically sane imaging system for *band*.

    Nothing here is under test — these are the parameters ``resolve()``
    requires before any chain can run.  The readout chain is deliberately
    generous (5 Me- well, 16-bit at 20 e-/DN) so that no scene in this module
    saturates: a saturated pixel returns ``snr = 0`` and would mask the
    atmospheric physics the module is actually about.
    """
    if band == "VIS":
        params.set("optics.aperture_diameter_m", 0.30)
        params.set("optics.focal_length_m", 3.0)
        params.set("detector.pixel_pitch_x_um", 10.0)
        params.set("detector.pixel_pitch_y_um", 10.0)
        params.set("detector.qe_value", 0.75)
        params.set("detector.dark_rate_e_per_s", 50.0)
        params.set("spectral_integration.filter_min_um", 0.45)
        params.set("spectral_integration.filter_max_um", 0.80)
        params.set("spectral_integration.integration_time_s", 0.01)
    elif band == "LWIR":
        params.set("optics.aperture_diameter_m", 0.30)
        params.set("optics.focal_length_m", 1.5)
        params.set("detector.pixel_pitch_x_um", 20.0)
        params.set("detector.pixel_pitch_y_um", 20.0)
        params.set("detector.qe_value", 0.60)
        params.set("detector.dark_rate_e_per_s", 5000.0)
        params.set("spectral_integration.filter_min_um", 8.0)
        params.set("spectral_integration.filter_max_um", 12.0)
        params.set("spectral_integration.integration_time_s", 0.001)
    else:  # MWIR
        params.set("optics.aperture_diameter_m", 0.30)
        params.set("optics.focal_length_m", 1.5)
        params.set("detector.pixel_pitch_x_um", 15.0)
        params.set("detector.pixel_pitch_y_um", 15.0)
        params.set("detector.qe_value", 0.70)
        params.set("detector.dark_rate_e_per_s", 1000.0)
        params.set("spectral_integration.filter_min_um", 3.5)
        params.set("spectral_integration.filter_max_um", 5.0)
        params.set("spectral_integration.integration_time_s", 0.005)
    params.set("optics.transmission_scalar", 0.60)
    params.set("readout.read_noise_e_rms", 30.0)
    params.set("readout.gain_e_per_dn", 20.0)
    params.set("readout.adc_bits", 16)
    params.set("readout.full_well_capacity_e", 5.0e6)


def _deselect_ground_metrics(params: ParameterSet) -> None:
    """Turn off the metric groups that project onto the ground (Gap 96).

    GSD, ground range, swath, access rate (``sampling``) and NIIRS
    (``interpretability``) are defined against a *ground* target through
    ``incidence_angle_rad ∈ [0, π/2)``.  None of the scenes here has a ground
    target, so they are deselected exactly as the selection machinery intends.
    Phase 3's scene-class → relevance map (guardrail G3) is what will
    eventually make this the default rather than a per-test call.
    """
    params.set("performance.metrics.sampling", False)
    params.set("performance.metrics.interpretability", False)


def _run_scene(
    band: str,
    wavelength_um: np.ndarray,
    *,
    reflective: bool = False,
    **geometry: float | str,
) -> tuple[object, list[str]]:
    """Run one point-source scene end to end; return (result, warnings).

    Every keyword lands under the ``geometry.`` namespace.  Warnings are
    recorded rather than suppressed — several of the assertions below are
    *about* the warning surface.

    ``reflective=True`` specifies the target by reflectance alone
    (``T2Reflective``) instead of by the (ε, T) pair; the two surfaces are
    mutually exclusive.  That choice is not cosmetic: ``_inferrer`` strips
    ``theta_s`` from the descriptor-adjusted LOS for a T1 (pure-thermal)
    target — the CU-009 predicate — and since Phase 2 the LOS ``theta_s``
    also gates the **sky background's** scattered-solar component.  On a VIS
    grid the (ε, T) surface always classifies T1 (the T3 route is
    MWIR-overlap only), so a reflective target is the only way to reach the
    daytime VIS sky at all.  See the task report.
    """
    session = RadiantSession(wavelength_um=wavelength_um)
    params = session.default_params()
    if reflective:
        params.set("source.target.reflectance", 0.3)
    else:
        params.set("source.target.temperature", TARGET_T_K)
        params.set("source.target.emissivity", TARGET_EPS)
    params.set("source.scene_type", "point_source")
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.target.projected_area_m2", TARGET_AREA_M2)
    for name, value in geometry.items():
        params.set(f"geometry.{name}", value)
    _seed_system(params, band)
    _deselect_ground_metrics(params)
    params.resolve()

    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        result = session.run(params)
    return result, [str(record.message) for record in records]


def _planck_radiance(wavelength_um: np.ndarray, temperature_k: float) -> np.ndarray:
    """Blackbody spectral radiance [W/m²/sr/µm] — the reference envelope.

    Written out from ``constants`` rather than imported from a physics module:
    an integration test must not validate the chain against the chain
    (Rule 18).  ``× 1e-6`` converts the per-metre spectral density the Planck
    law produces in SI to the per-micron canonical unit.
    """
    lam_m = np.asarray(wavelength_um, dtype=np.float64) * 1.0e-6
    return (2.0 * h * c**2 / lam_m**5) / (np.expm1(h * c / (lam_m * k_B * temperature_k))) * 1.0e-6


def _band_mean(wavelength_um: np.ndarray, values: np.ndarray, lo_um: float, hi_um: float) -> float:
    """Band-mean of *values* over ``[lo, hi]`` µm — same unit as *values*."""
    band = (wavelength_um >= lo_um) & (wavelength_um <= hi_um)
    return float(np.trapezoid(values[band], wavelength_um[band]) / (hi_um - lo_um))


def _quantities(result: object) -> object:
    return result.stage_outputs["atmosphere"]["atm_quantities"]  # type: ignore[attr-defined]


def _assert_bundle_finite(result: object) -> None:
    """Rule 16/17: nothing silently non-finite reaches the assembly."""
    q = _quantities(result)
    for field in (
        "tau_sun",
        "tau_up",
        "tau_full_up",
        "E_TOA",
        "E_sky_scattered",
        "E_sky_thermal",
        "L_path_up",
        "L_path_full",
    ):
        values = np.asarray(getattr(q, field), dtype=np.float64)
        assert np.all(np.isfinite(values)), f"{field} carries NaN/inf"


# ---------------------------------------------------------------------------
# 1. Ground → air MWIR detection (worked example E2, owner priority 1)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestGroundToAirMwirDetection:
    """Ground site → 10 km airborne point target, MWIR, simple backend, day.

    This is the scene the whole phase was ordered around.  Before Phase 2 it
    reached ``AtmosphereStage`` and was refused as a pending capability; the
    assertions below are the contract that replaced that refusal.
    """

    ZETA_LOW_DEG = 30.0  # entered at the LOWER endpoint (the ground sensor)
    H_TARGET_M = 10_000.0

    def _run(self) -> tuple[object, list[str]]:
        return _run_scene(
            "MWIR",
            MWIR_WL,
            sensor_altitude_m=0.0,
            target_altitude_m=self.H_TARGET_M,
            path_zenith_rad=math.radians(self.ZETA_LOW_DEG),
            solar_illumination="day",
            solar_zenith_rad=math.radians(40.0),
        )

    def test_chain_completes_with_the_expected_topology(self) -> None:
        result, _ = self._run()
        geom = result.stage_outputs["geometry"]
        assert geom["los_direction"] == "up"
        assert geom["theta_o_rad"] > math.pi / 2.0
        assert geom["los_geometry"].h_sensor == 0.0
        # θ_o is DERIVED from the lower-endpoint entry, never entered:
        # θ_o = π − asin((R_E/(R_E + h_t))·sin ζ_low)  (law of sines).
        zeta_low = math.radians(self.ZETA_LOW_DEG)
        expected = math.pi - math.asin(
            (R_EARTH_M / (R_EARTH_M + self.H_TARGET_M)) * math.sin(zeta_low)
        )
        assert float(geom["theta_o_rad"]) == pytest.approx(expected, rel=1e-12)

    def test_sky_background_is_the_default(self) -> None:
        """Rule B, matrix B2 — no user switch, no explicit descriptor."""
        result, _ = self._run()
        background = result.stage_outputs["source"]["background"]
        assert type(background).__name__ == "SkyBackground"
        assert "at_aperture_background" in result.frames

    def test_background_radiance_is_physically_sensible(self) -> None:
        """Positive, and bounded above by an in-band 300 K blackbody.

        The bound is the physical one, not a fitted tolerance: the sky column
        the sensor looks through is optically thin and cooler than the surface
        air, so its emergent radiance is strictly below the blackbody of the
        warmest air it contains (~300 K at a midlat-summer surface).  A model
        that returned more than that would be emitting more than a blackbody
        at its own temperature — a Kirchhoff violation, not a tolerance miss.
        """
        result, _ = self._run()
        L_bg = np.asarray(result.frames["at_aperture_background"].spectral_radiance)
        assert np.all(np.isfinite(L_bg))
        assert np.all(L_bg > 0.0), "an emitting sky column cannot be dark in the MWIR"
        ceiling = _planck_radiance(MWIR_WL, 300.0)
        assert np.all(L_bg < ceiling), (
            f"sky radiance exceeds a 300 K blackbody (max ratio "
            f"{float((L_bg / ceiling).max()):.3f})"
        )

    def test_column_is_traversed_in_both_senses(self) -> None:
        """Attenuating (τ < 1 everywhere) and emitting (L_path > 0)."""
        result, _ = self._run()
        q = _quantities(result)
        assert float(q.tau_up.min()) > 0.0
        assert float(q.tau_up.max()) < 1.0
        assert float(q.L_path_up.min()) > 0.0
        _assert_bundle_finite(result)

    def test_metrics_are_finite_and_the_regime_is_point_source(self) -> None:
        result, _ = self._run()
        assert result.stage_outputs["optics"]["regime"] is RadiometricRegime.POINT_SOURCE
        snr = float(result.metrics["snr"])
        contrast = float(result.metrics["contrast_snr"])
        assert math.isfinite(snr) and snr > 0.0
        assert math.isfinite(contrast) and contrast > 0.0
        signal_e = float(result.stage_outputs["spectral_integration"]["signal_e"])
        background_e = float(result.stage_outputs["spectral_integration"]["background_e"])
        assert signal_e > 0.0
        # The sky background is a real photon term, not a silent zero — that
        # is the failure mode assembly._sky_background_source_emission guards.
        assert background_e > 0.0

    def test_ground_metrics_are_absent_because_they_were_deselected(self) -> None:
        """Gap 96 toggles, not a scene-class branch (guardrail G3 pending)."""
        result, _ = self._run()
        for metric in ("gsd_x_m", "gsd_y_m", "niirs", "ground_range_m"):
            assert metric not in result.metrics


# ---------------------------------------------------------------------------
# 2. Air → air level MWIR (worked example E5, owner priority 2)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestAirToAirLevelMwir:
    """Two 10 km platforms 150 km apart — the constant-altitude arm.

    150 km at 10 km sags Δh ≈ L²/8R_E ≈ 441 m: squarely inside the ratified
    100 m – 2 km warn shoulder (§8.3 answer 1), which is exactly the band the
    owner asked to keep *usable* at first delivery.  So the scene must both
    warn and produce numbers.
    """

    RANGE_M = 150_000.0
    ALTITUDE_M = 10_000.0

    def _run(self) -> tuple[object, list[str]]:
        return _run_scene(
            "MWIR",
            MWIR_WL,
            sensor_altitude_m=self.ALTITUDE_M,
            target_altitude_m=self.ALTITUDE_M,
            target_range_m=self.RANGE_M,
            solar_illumination="night",
        )

    def test_refraction_shoulder_warning_fires_and_quantifies_the_sag(self) -> None:
        _, messages = self._run()
        horizon = [m for m in messages if "horizon guard" in m]
        assert horizon, "a 150 km level arm must warn — it is in the shoulder band"
        message = horizon[0]
        assert "interior tangent" in message
        assert "refraction" in message
        # Quantified, not qualitative.  Compare against the independent
        # small-angle form Δh ≈ L²/8R_E (a hand calculation, not RADIANT code).
        dh_reported = float(message.split("interior tangent point ")[1].split(" m below")[0])
        dh_small_angle = self.RANGE_M**2 / (8.0 * R_EARTH_M)
        assert dh_reported == pytest.approx(dh_small_angle, rel=5e-3)
        assert 100.0 < dh_reported < 2000.0

    def test_level_arm_carries_the_observer_leg(self) -> None:
        """The observer leg is the constant-altitude arm, not a column.

        Two independent fingerprints of that: the geometry resolves as a level
        path whose slant range is the entered range exactly, and the arm is far
        more opaque than the *vertical* column through the same altitude — 150
        km of 10 km-altitude air versus the ~10 km of much thinner air above
        it.  A column-airmass fallback would have produced the latter.
        """
        result, _ = self._run()
        geom = result.stage_outputs["geometry"]
        assert geom["los_direction"] == "level"
        assert float(geom["slant_range_m"]) == pytest.approx(self.RANGE_M, rel=1e-9)

        q = _quantities(result)
        assert float(q.tau_up.max()) < 0.5, (
            "a 150 km horizontal MWIR arm at 10 km cannot be near-transparent; "
            "a value close to 1 would mean a vertical column was substituted"
        )
        assert float(q.tau_up.min()) > 0.0
        _assert_bundle_finite(result)

    def test_sky_background_and_finite_metrics(self) -> None:
        result, _ = self._run()
        assert type(result.stage_outputs["source"]["background"]).__name__ == "SkyBackground"
        for name in ("snr", "contrast_snr"):
            value = float(result.metrics[name])
            assert math.isfinite(value) and value > 0.0
        L_bg = np.asarray(result.frames["at_aperture_background"].spectral_radiance)
        assert np.all(np.isfinite(L_bg)) and np.all(L_bg > 0.0)


# ---------------------------------------------------------------------------
# 3. Sunlit target over dark ground (the GF-9 payoff)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestSunlitTargetOverDarkGround:
    """A target above the terminator shadow while the ground below is dark.

    This whole family was **inexpressible** before ADR-0011 decision 21: the
    old global ``θ_s < π/2`` bound rejected the scene at parameter entry.
    The physics that replaced it is one line —
    ``sunlit ⟺ (R_E + h)·sin θ_s ≥ R_E`` — with the observable consequence
    living on ``tau_sun``.

    Deviation from the task's illustrative ``θ_s = 92°``, stated per the
    reporting rule: at 92° the shadow height is only 3.88 km, so a 5 km target
    is still *lit* and the intended contrast does not exist.  The scenes below
    use **94°** (shadow height 15.56 km), the shallowest whole degree that
    puts 5 km in shadow and 50 km in sunlight simultaneously.  92° is retained
    as an explicit boundary assertion so the choice is auditable rather than
    silent.
    """

    THETA_S_DEG = 94.0
    ZETA_LOW_DEG = 20.0

    def _run(self, h_target_m: float) -> tuple[object, list[str]]:
        return _run_scene(
            "MWIR",
            MWIR_WL,
            sensor_altitude_m=0.0,
            target_altitude_m=h_target_m,
            path_zenith_rad=math.radians(self.ZETA_LOW_DEG),
            solar_illumination="day",
            solar_zenith_rad=math.radians(self.THETA_S_DEG),
        )

    def test_the_92_degree_boundary_is_why_94_is_used(self) -> None:
        """Records the deviation as an assertion, not a comment.

        Truth anchor (hand calculation): ``h_shadow = R_E(sec δ − 1)`` with
        ``δ = 2°`` gives ``6.371e6 × (1/cos 2° − 1) = 3.885e3 m``.
        """
        theta_92 = math.radians(92.0)
        expected = R_EARTH_M * (1.0 / math.cos(math.radians(2.0)) - 1.0)
        assert shadow_height_m(theta_92) == pytest.approx(expected, rel=1e-9)
        assert shadow_height_m(theta_92) == pytest.approx(3.885e3, rel=2e-3)
        assert sunlit(5_000.0, theta_92) is True  # ← why 92° does not work
        assert sunlit(50_000.0, theta_92) is True

    def test_shadow_height_ordering_at_94_degrees(self) -> None:
        theta_s = math.radians(self.THETA_S_DEG)
        h_shadow = shadow_height_m(theta_s)
        assert h_shadow == pytest.approx(
            R_EARTH_M * (1.0 / math.cos(math.radians(4.0)) - 1.0), rel=1e-9
        )
        assert 5_000.0 < h_shadow < 50_000.0
        assert sunlit(50_000.0, theta_s) is True
        assert sunlit(5_000.0, theta_s) is False
        assert sunlit(0.0, theta_s) is False, "the ground must be the dark half of the scene"

    def test_high_target_is_sunlit_and_carries_a_solar_leg(self) -> None:
        result, _ = self._run(50_000.0)
        q = _quantities(result)
        tau_sun = np.asarray(q.tau_sun, dtype=np.float64)
        assert np.all(tau_sun > 0.0), "a sunlit target must have a non-zero solar column"
        assert np.all(tau_sun <= 1.0)
        # It is a real twilight transit, not the vacuum identity: the beam
        # crosses a long grazing column, so it is attenuated everywhere.
        assert float(tau_sun.max()) < 1.0
        _assert_bundle_finite(result)
        assert math.isfinite(float(result.metrics["snr"]))

    def test_low_target_is_in_shadow_and_is_thermal_only(self) -> None:
        result, _ = self._run(5_000.0)
        q = _quantities(result)
        np.testing.assert_array_equal(
            np.asarray(q.tau_sun, dtype=np.float64), np.zeros_like(MWIR_WL)
        )
        # No scattered-solar sky either — the backend's cos θ_s guard already
        # zeroes it, and the shadow test must not resurrect it.
        np.testing.assert_array_equal(
            np.asarray(q.E_sky_scattered, dtype=np.float64), np.zeros_like(MWIR_WL)
        )
        # Thermal emission is untouched: the scene is still a warm 500 K target
        # against a warm sky, so it is detectable at night-time illumination.
        assert float(q.E_sky_thermal.max()) > 0.0
        _assert_bundle_finite(result)
        assert float(result.metrics["snr"]) > 0.0

    def test_the_sunlit_leg_is_monotonic_in_altitude(self) -> None:
        """The physical sense: higher ⇒ shorter grazing column ⇒ more τ_sun.

        Three altitudes above the terminator, so all three are lit and the
        comparison is of transit depth alone.
        """
        band_means = []
        for h_m in (20_000.0, 40_000.0, 60_000.0):
            result, _ = self._run(h_m)
            tau_sun = np.asarray(_quantities(result).tau_sun, dtype=np.float64)
            assert np.all(np.isfinite(tau_sun))
            band_means.append(_band_mean(MWIR_WL, tau_sun, 3.5, 5.0))
        assert all(a < b for a, b in zip(band_means, band_means[1:], strict=False)), band_means

    def test_a_ground_scene_at_the_same_sun_is_not_sunlit(self) -> None:
        """The other half of the payoff: the ground below is dark.

        Expressed as a real down-looking chain — the widened
        ``solar_zenith_rad`` bound must not have broken the existing
        below-horizon handling.  The backend's own ``cos θ_s ≤ 0`` guard
        zeroes the scattered-solar sky, and assembly's ``cos θ_s`` clamp
        zeroes the direct-solar reflection, so the *radiometry* is correct.

        **Known asymmetry, pinned rather than endorsed.**  The GF-9
        shadow-height test is applied only on the up/level arm
        (``uplooking_quantities._resolve_tau_sun``); the down-looking arm
        keeps the backend's own answer byte-for-byte, which for
        ``cos θ_s ≤ 0`` is ``airmass_sun = 1`` — a *vertical*-column
        ``τ_sun ≈ 0.5`` published for a target that is demonstrably in the
        Earth's shadow.  Nothing consumes it (the ``cos θ_s`` clamp kills the
        term), so no number moves, but it is an inspectable quantity (Rule 16)
        that disagrees with the up-looking arm for the same physical
        situation.  Widening the bound is what made the branch reachable.
        Reported, not fixed: zeroing it would touch the shared down-looking
        evaluate path this phase is required to leave untouched.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("source.scene_type", "extended")
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 500_000.0)
        params.set("geometry.target_altitude_m", 0.0)
        params.set("geometry.path_zenith_rad", math.radians(20.0))
        params.set("geometry.solar_illumination", "day")
        params.set("geometry.solar_zenith_rad", math.radians(self.THETA_S_DEG))
        _seed_system(params, "MWIR")
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        assert sunlit(0.0, math.radians(self.THETA_S_DEG)) is False
        q = _quantities(result)
        # The radiometry: no scattered-solar sky, and no direct-solar term.
        np.testing.assert_array_equal(
            np.asarray(q.E_sky_scattered, dtype=np.float64), np.zeros_like(MWIR_WL)
        )
        L_target = np.asarray(result.frames["at_aperture_target"].spectral_radiance)
        assert np.all(np.isfinite(L_target)) and np.all(L_target > 0.0)

        # The asymmetry, pinned: down-looking τ_sun is NOT zeroed the way the
        # up-looking arm zeroes it.  If a future PR unifies the two, this
        # assertion is the one that will fail and force the report to be read.
        tau_sun = np.asarray(q.tau_sun, dtype=np.float64)
        assert np.all(tau_sun > 0.0), (
            "down-looking tau_sun is expected to keep the backend's vertical-column "
            "value in shadow (documented asymmetry); a zero here means the arms were "
            "unified and this characterization must be replaced"
        )
        _assert_bundle_finite(result)
        assert math.isfinite(float(result.metrics["snr"]))


# ---------------------------------------------------------------------------
# 4. Band gating of the provisional scattered sky (§8.3 answer 3)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestProvisionalScatteredSkyWarning:
    """VIS/NIR sky computes but says so; MWIR/LWIR is first-class and silent."""

    _MARKER = "scattered-solar component of the sky"

    def test_vis_uplooking_scene_warns(self) -> None:
        _, messages = _run_scene(
            "VIS",
            VIS_WL,
            reflective=True,
            sensor_altitude_m=0.0,
            target_altitude_m=10_000.0,
            path_zenith_rad=math.radians(20.0),
            solar_illumination="day",
            solar_zenith_rad=math.radians(40.0),
        )
        provisional = [m for m in messages if self._MARKER in m]
        assert provisional, "a daytime VIS up-looking sky must carry the provisional flag"
        assert "multiple scattering" in provisional[0]
        assert "3 µm" in provisional[0]

    def test_mwir_uplooking_scene_is_silent(self) -> None:
        """Nothing below 3 µm on the grid ⇒ nothing provisional to declare.

        The *discriminating* silent case: an MWIR (ε, T) target routes to
        T3Mixed, so ``theta_s`` survives onto the LOS and the sun is genuinely
        in play — the warning is suppressed by the **band gate** alone, not by
        an absent solar geometry.
        """
        result, messages = _run_scene(
            "MWIR",
            MWIR_WL,
            sensor_altitude_m=0.0,
            target_altitude_m=10_000.0,
            path_zenith_rad=math.radians(20.0),
            solar_illumination="day",
            solar_zenith_rad=math.radians(40.0),
        )
        # The solar geometry really is present on this scene.
        assert result.stage_outputs["geometry"]["los_geometry"].theta_s is not None
        assert float(_quantities(result).tau_sun.max()) > 0.0
        assert [m for m in messages if self._MARKER in m] == []

    def test_lwir_uplooking_scene_is_silent(self) -> None:
        """LWIR-only grid: silent as well (the task's stated case)."""
        _, messages = _run_scene(
            "LWIR",
            LWIR_WL,
            sensor_altitude_m=0.0,
            target_altitude_m=10_000.0,
            path_zenith_rad=math.radians(20.0),
            solar_illumination="day",
            solar_zenith_rad=math.radians(40.0),
        )
        assert [m for m in messages if self._MARKER in m] == []

    def test_night_vis_scene_is_silent(self) -> None:
        """No sun above the horizon ⇒ no scattered component to be provisional
        about, even on a VIS grid."""
        _, messages = _run_scene(
            "VIS",
            VIS_WL,
            reflective=True,
            sensor_altitude_m=0.0,
            target_altitude_m=10_000.0,
            path_zenith_rad=math.radians(20.0),
            solar_illumination="night",
        )
        assert [m for m in messages if self._MARKER in m] == []

    def test_a_pure_thermal_target_suppresses_the_daytime_vis_sky(self) -> None:
        """Characterization of a real coupling defect — pinned, not endorsed.

        Two VIS scenes differing only in how the target is specified:
        ``(ε, T)`` — which on a VIS grid always classifies **T1Thermal** — and
        ``ρ`` — which classifies **T2Reflective**.

        ``_inferrer`` strips ``theta_s`` from the descriptor-adjusted LOS for
        a T1 (pure-thermal) target, on the CU-009 rationale that a thermal
        radiance has no solar leg.  That rationale was complete when the
        *target* was the only consumer of ``theta_s``.  Since Phase 2 the sky
        background is a second consumer, and its solar dependence has nothing
        to do with the target's material: the daytime VIS sky behind a
        pure-thermal object is still bright.

        Consequence, asserted here so it cannot change unnoticed: the same
        scene run with a T1 target produces **no** provisional warning and a
        thermal-only sky, while the T3 variant warns.  Reported, not fixed —
        the repair is a source/atmosphere coupling change well outside this
        task's scope.
        """
        geometry: dict[str, float | str] = {
            "sensor_altitude_m": 0.0,
            "target_altitude_m": 10_000.0,
            "path_zenith_rad": math.radians(20.0),
            "solar_illumination": "day",
            "solar_zenith_rad": math.radians(40.0),
        }
        thermal_result, thermal_messages = _run_scene("VIS", VIS_WL, reflective=False, **geometry)
        mixed_result, mixed_messages = _run_scene("VIS", VIS_WL, reflective=True, **geometry)

        assert [m for m in thermal_messages if self._MARKER in m] == []
        assert [m for m in mixed_messages if self._MARKER in m] != []

        # And the physical footprint of the defect: the T1 sky is strictly
        # darker in the visible, because its scattered-solar term is missing.
        L_thermal = np.asarray(thermal_result.frames["at_aperture_background"].spectral_radiance)
        L_mixed = np.asarray(mixed_result.frames["at_aperture_background"].spectral_radiance)
        assert np.all(L_thermal < L_mixed)


# ---------------------------------------------------------------------------
# 5. Cross-model agreement (Category C §7)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestCrossModelAgreement:
    """Simple-model segment τ vs the MODTRAN-derived up-looking products.

    Both sides are **pinned**: the reference number and the ratio envelope.
    An unexplained improvement fails as loudly as a regression, which is what
    keeps this a record rather than a rubber stamp.

    The comparison is at the *segment product* level rather than through two
    full chains, because the interpolated backend's up-looking family is not
    yet wired into ``uplooking_quantities.supports_uplooking`` (see the task
    report — reported, not fixed here).  The segment IS the observer leg the
    chain consumes, so the comparison is of the quantity that matters.
    """

    H_TARGET_M = 10_000.0
    #: MODTRAN deck settings for the K/L blocks (run-matrix rows K1–K7).
    VISIBILITY_KM = 23.0
    AEROSOL = "rural"

    @staticmethod
    def _simple_segment(wavelength_um: np.ndarray, h_high_m: float) -> object:
        from radiant.atmosphere.segment_simple import evaluate_column_segment
        from radiant.atmosphere.segments import ColumnSegmentSpec
        from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere

        atmosphere = SimpleAtmosphere(
            standard_atmosphere="midlat_summer",
            precipitable_water_cm=PROFILE_PWV_CM["midlat_summer"],
            visibility_km=TestCrossModelAgreement.VISIBILITY_KM,
            aerosol_type=TestCrossModelAgreement.AEROSOL,
        )
        return evaluate_column_segment(
            atmosphere,
            wavelength_um,
            ColumnSegmentSpec(h_low_m=0.0, h_high_m=h_high_m, zeta_low_rad=0.0),
        )

    @staticmethod
    def _uplooking_family() -> object:
        from radiant.atmosphere.interpolated import (
            UPLOOKING_RADIANCE_KEY,
            GeometryPoint,
            InterpolatedAtmosphere,
        )
        from radiant.core.spectral import SpectralData

        points = []
        for npz_file in sorted(_SHIPPED_UPLOOKING.glob("*.npz")):
            with np.load(npz_file, allow_pickle=True) as data:
                coords = data["geometry"].item()
                wl = np.asarray(data["wavelength_um"], dtype=np.float64)
                tau = np.asarray(data["transmittance"], dtype=np.float64)
                l_down = np.asarray(data[UPLOOKING_RADIANCE_KEY], dtype=np.float64)
            zeros = np.zeros_like(wl)
            points.append(
                GeometryPoint(
                    coordinates=coords,
                    transmittance=SpectralData(
                        name="tau",
                        wavelength_um=wl.copy(),
                        values=tau,
                        unit="",
                        source=str(npz_file),
                    ),
                    path_radiance=SpectralData(
                        name="L_toward_lower",
                        wavelength_um=wl.copy(),
                        values=l_down,
                        unit="W/m²/sr/µm",
                        source=str(npz_file),
                    ),
                    atm_emission_down=SpectralData(
                        name="unused",
                        wavelength_um=wl.copy(),
                        values=zeros,
                        unit="W/m²/sr/µm",
                        source=str(npz_file),
                    ),
                )
            )
        return InterpolatedAtmosphere(points, axes=["target_altitude_m"], family_direction="up")

    @pytest.mark.skipif(
        not _SHIPPED_UPLOOKING.exists(),
        reason="shipped up-looking family not present",
    )
    def test_simple_vs_shipped_interpolated_uplooking_tau(self) -> None:
        """Vertical ground → 10 km column, band-mean τ ratio (simple / MODTRAN).

        Measured 2026-07-26 on the shipped (slit-degraded) K4 rung:

            8–12 µm:  0.613 | 0.632  →  ratio 0.970
            3–5  µm:  0.503 | 0.428  →  ratio 1.174

        Tolerance justification — these are **not** free tolerances.  The LWIR
        3 % deficit and the MWIR 17 % excess are the documented CU-161
        band-model calibration residuals: the simple model's region-flat
        spectral shape is fitted to full columns, so it is systematically
        transparent in the MWIR where the 4.3 µm CO₂ band dominates the real
        column.  The envelopes below are ±0.03 around each measured ratio —
        tight enough that a physics change moves them, wide enough to absorb
        the interpolation and resampling of the shipped grid.
        """
        from radiant.core.los_geometry import LineOfSightGeometry

        family = self._uplooking_family()
        wavelength_um = np.linspace(3.0, 12.0, 901)
        los = LineOfSightGeometry(theta_o=math.pi, h_tgt=self.H_TARGET_M, h_sensor=0.0)
        modtran = family.uplooking_column_product(wavelength_um, los)
        simple = self._simple_segment(wavelength_um, self.H_TARGET_M)

        for lo, hi, tau_ref, ratio_ref in ((8.0, 12.0, 0.632, 0.970), (3.0, 5.0, 0.428, 1.174)):
            tau_modtran = _band_mean(wavelength_um, np.asarray(modtran.tau), lo, hi)
            tau_simple = _band_mean(wavelength_um, np.asarray(simple.tau), lo, hi)
            assert tau_modtran == pytest.approx(tau_ref, abs=0.01), f"{lo}–{hi} µm MODTRAN side"
            assert tau_simple / tau_modtran == pytest.approx(ratio_ref, abs=0.03), (
                f"{lo}–{hi} µm simple/MODTRAN τ ratio moved"
            )

    @pytest.mark.skipif(
        not _REAL_RUNS.exists(),
        reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored)",
    )
    def test_simple_vs_raw_k4_tape7_import(self) -> None:
        """Same column, read straight off the K4 tape7 — the un-degraded path.

        This is the independent leg of the cross-model check: the shipped
        library above is *derived* from K4 through a slit convolution and a
        resample, so agreeing with it does not prove agreement with MODTRAN.
        Reading the deck directly does, and it simultaneously pins the shipped
        library's fidelity to its own source (the two MODTRAN-side numbers
        below agree to 1 %).
        """
        from radiant.atmosphere.modtran import Tape7Reader

        native = Tape7Reader(_REAL_RUNS / "K4.tp7").parse()
        nu = native.wavenumber_cm1
        keep = nu > 0.0
        lam = 1.0e4 / nu[keep]
        order = np.argsort(lam)
        lam = lam[order]
        tau_modtran = native.total_transmittance[keep][order]

        simple = self._simple_segment(lam, self.H_TARGET_M)
        for lo, hi, tau_ref, ratio_ref in ((8.0, 12.0, 0.6307, 0.971), (3.0, 5.0, 0.4284, 1.173)):
            measured = _band_mean(lam, tau_modtran, lo, hi)
            assert measured == pytest.approx(tau_ref, rel=0.01)
            ratio = _band_mean(lam, np.asarray(simple.tau), lo, hi) / measured
            assert ratio == pytest.approx(ratio_ref, abs=0.03), f"{lo}–{hi} µm τ ratio {ratio:.3f}"


# ---------------------------------------------------------------------------
# 6. Exo regression — the Phase-1 quick win survives the G4 fold
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestExoPathStillExactVacuum:
    """LEO → GEO with ``evaluate_with_exo_target`` deleted (guardrail G4).

    The wrapper that used to serve this scene is gone; the topology dispatch
    expresses it as the ``G ∪ V`` segment composition instead.  The composition
    must reproduce the vacuum identities **exactly** — ``==``, not ``approx`` —
    because it is written as identities with no arithmetic.  A drift of even
    one ULP would mean an evaluator crept into a path that is supposed to be
    model-independent.
    """

    H_LEO_M = 500_000.0
    H_GEO_M = 35_786_000.0

    def test_uplooking_space_to_space_is_bit_exact_vacuum(self) -> None:
        session = RadiantSession(wavelength_um=VIS_WL)
        params = session.default_params()
        params.set("source.target.reflectance", 0.25)
        params.set("source.scene_type", "point_source")
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", self.H_LEO_M)
        params.set("geometry.target_altitude_m", self.H_GEO_M)
        params.set("geometry.solar_illumination", "day")
        params.set("geometry.solar_zenith_rad", 0.6)
        params.set("geometry.target.projected_area_m2", 20.0)
        _seed_system(params, "VIS")
        _deselect_ground_metrics(params)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        assert result.stage_outputs["geometry"]["theta_o_rad"] == math.pi
        assert result.stage_outputs["geometry"]["los_direction"] == "up"

        q = _quantities(result)
        ones = np.ones_like(VIS_WL)
        zeros = np.zeros_like(VIS_WL)
        np.testing.assert_array_equal(q.tau_sun, ones)
        np.testing.assert_array_equal(q.tau_up, ones)
        np.testing.assert_array_equal(q.tau_full_up, ones)
        np.testing.assert_array_equal(q.L_path_up, zeros)
        np.testing.assert_array_equal(q.L_path_full, zeros)
        np.testing.assert_array_equal(q.E_sky_scattered, zeros)
        np.testing.assert_array_equal(q.E_sky_thermal, zeros)

        # Cold space behind an exo target, not sky: the Rule-B classifier must
        # return "space-with-no-column", not the SkyBackground of an endo path.
        assert type(result.stage_outputs["source"]["background"]).__name__ == "ColdSpaceBackground"
        assert float(result.metrics["snr"]) > 0.0

    def test_down_looking_exo_target_still_composes_over_the_full_column(self) -> None:
        """The other half of the G4 fold: a GEO target seen from the ground.

        ``τ_up ≡ 1`` and ``L_path_up ≡ 0`` (the vacuum V segment) while the
        full-column terms carry the real ground→sensor column G — which is
        precisely what the deleted wrapper used to override into place.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.9)
        params.set("source.scene_type", "point_source")
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 800_000.0)
        params.set("geometry.target_altitude_m", 200_000.0)
        params.set("geometry.path_zenith_rad", math.radians(20.0))
        params.set("geometry.solar_illumination", "night")
        params.set("geometry.target.projected_area_m2", 1.0)
        _seed_system(params, "MWIR")
        _deselect_ground_metrics(params)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        assert result.stage_outputs["geometry"]["los_direction"] == "down"
        q = _quantities(result)
        np.testing.assert_array_equal(q.tau_up, np.ones_like(MWIR_WL))
        np.testing.assert_array_equal(q.L_path_up, np.zeros_like(MWIR_WL))
        np.testing.assert_array_equal(q.tau_sun, np.ones_like(MWIR_WL))
        # G is real: the full column through the whole atmosphere attenuates.
        assert float(q.tau_full_up.max()) < 1.0
        _assert_bundle_finite(result)
