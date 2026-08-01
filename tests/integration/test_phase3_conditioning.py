r"""Phase-3 cross-cut: turbulence, kinematics, metric conditioning, detection range.

The four Phase-3 arms of the Geometry Flexibility plan (§4 Phase 3) land in four
separate module families, each with its own unit and per-arm integration suite.
*This* file is the seam between them — the end-to-end proof that the arms compose
correctly on real scenes, and that composing them changes nothing for scenes that
predate the phase.

Five claims, one section each:

**A. Ground-to-space SST, VIS, HV-5/7 turbulence** (Gap 110).  A ground observer
looking up the full column at a satellite gets a *profile-driven* Fried
parameter, the turbulence blur reaches the PSF, every metric stays finite, and
the direct ``atmosphere.r0_m`` input still overrides the profile (with the
CU-093 agreement check catching a contradiction).

**B. Air-to-air level arm with a crossing target** (Gap 111).  A constant-altitude
scene with a transiting target smears by the *relative* line-of-sight rate; the
direct-rate door (K1) and the target-velocity door (K2) reach the same number,
and a disagreement between them raises rather than silently picking one.

**C. Metric conditioning per scene class** (guardrail G3).  A ground-target scene's
default metric set is *exactly* the pre-phase set (differential proof: the same
run with the relevance map neutralised produces an identical metric dict plus
only the brand-new target-plane keys); a non-ground-target scene defaults the
ground-projection family off and the target-plane family on; an explicit metric
flag still wins.

**D. Derived-scene-class assertion** (ADR-0011 decision 8).  The optional
``geometry.scene_class`` assertion passes silently when it agrees with the
derivation and raises a ``GeometrySpecificationError`` naming *both* labels when
it does not.

**E. Path-aware detection range** (finding GF-15; extended to the ``down``
topology and re-anchored on the shot-consistent criterion by CU-263,
2026-08-01).  Every topology is bounded above by the vacuum inverse-square
answer ``R_ref √(S_ref/S*)``; the bound is *attained* when the receding leg
already lies outside the modelled column (up-looking above ``h_atm_top``, and
every spaceborne down-looking sensor), and is strictly below it when the ray
keeps accruing optical depth.  The level arm additionally reproduces the
constant-α Beer-Lambert solver to sub-metre agreement — the two models are the
same model on a constant-density path.

Every numeric assertion here is an independent hand calculation (recorded beside
it), never a value produced by another RADIANT module.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere.errors import TurbulenceSpecificationError
from radiant.core.parameters import ParameterSet
from radiant.geometry.errors import GeometrySpecificationError
from radiant.io.results import ChainResult
from radiant.performance.detection_beer_lambert import detection_range_beer_lambert
from radiant.performance.path_optical_depth import resolve_path_optical_depth
from radiant.performance.scene_relevance import (
    GROUND_PROJECTION_METRICS,
    TARGET_PLANE_METRICS,
)

VIS_WL = np.linspace(0.45, 0.80, 71)
MWIR_WL = np.linspace(3.5, 5.0, 61)

#: Band-centre wavelength of ``VIS_WL`` — the reference wavelength
#: ``r0_resolution`` quotes the Fried parameter at (``wavelength_um[n // 2]``).
VIS_BAND_CENTRE_UM = 0.625

# ---------------------------------------------------------------------------
# Scene builders.  Deliberately explicit: every number a claim depends on is
# visible in the file that makes the claim.
# ---------------------------------------------------------------------------


def _seed_vis_optics(params: ParameterSet) -> None:
    """1 m / f-10 visible telescope, 10 µm pixels, 0.5 s stare."""
    params.set("optics.aperture_diameter_m", 1.0)
    params.set("optics.focal_length_m", 10.0)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 10.0)
    params.set("detector.pixel_pitch_y_um", 10.0)
    params.set("detector.qe_value", 0.80)
    params.set("detector.dark_rate_e_per_s", 100.0)
    params.set("spectral_integration.filter_min_um", 0.45)
    params.set("spectral_integration.filter_max_um", 0.80)
    params.set("spectral_integration.integration_time_s", 0.50)
    params.set("readout.read_noise_e_rms", 10.0)
    params.set("readout.gain_e_per_dn", 310.0)
    params.set("readout.adc_bits", 16)
    params.set("readout.full_well_capacity_e", 2.0e7)


def _seed_mwir_optics(params: ParameterSet) -> None:
    """0.3 m / f-5 MWIR imager, 15 µm pixels, 5 ms frame."""
    params.set("optics.aperture_diameter_m", 0.30)
    params.set("optics.focal_length_m", 1.50)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 15.0)
    params.set("detector.pixel_pitch_y_um", 15.0)
    params.set("detector.qe_value", 0.70)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", 3.5)
    params.set("spectral_integration.filter_max_um", 5.0)
    params.set("spectral_integration.integration_time_s", 0.005)
    params.set("readout.read_noise_e_rms", 30.0)
    params.set("readout.gain_e_per_dn", 20.0)
    params.set("readout.adc_bits", 16)
    params.set("readout.full_well_capacity_e", 5.0e6)


#: Lower-endpoint (ground-sensor) path zenith of the SST scene [rad] — ADR-0011
#: decision 3 puts the entered zenith at the path's lower endpoint.
SST_ZENITH_RAD = math.radians(20.0)


def sst_params(session: RadiantSession, **overrides: object) -> ParameterSet:
    """Ground site → 700 km satellite, sunlit VIS point source (matrix class E3)."""
    params = session.default_params()
    params.set("source.target.reflectance", 0.30)
    params.set("source.scene_type", "point_source")
    params.set("geometry.target.projected_area_m2", 2.0e-3)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 0.0)
    params.set("geometry.target_altitude_m", 7.0e5)
    params.set("geometry.path_zenith_rad", SST_ZENITH_RAD)
    params.set("geometry.solar_zenith_rad", math.radians(60.0))
    params.set("geometry.solar_azimuth_rad", math.radians(45.0))
    _seed_vis_optics(params)
    for name, value in overrides.items():
        params.set(name, value)
    params.resolve()
    return params


#: Air-to-air level arm: both endpoints at 10 km, 50 km apart.
A2A_ALTITUDE_M = 10_000.0
A2A_RANGE_M = 50_000.0
A2A_TARGET_SPEED_M_S = 250.0
A2A_T_INT_S = 0.005
A2A_FOCAL_M = 1.50


def air_to_air_params(session: RadiantSession, **overrides: object) -> ParameterSet:
    """10 km ↔ 10 km level MWIR point-target arm (matrix class E5)."""
    params = session.default_params()
    params.set("source.target.temperature", 500.0)
    params.set("source.target.emissivity", 0.90)
    params.set("source.scene_type", "point_source")
    params.set("geometry.target.projected_area_m2", 1.0e-4)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", A2A_ALTITUDE_M)
    params.set("geometry.target_altitude_m", A2A_ALTITUDE_M)
    params.set("geometry.target_range_m", A2A_RANGE_M)
    _seed_mwir_optics(params)
    for name, value in overrides.items():
        params.set(name, value)
    params.resolve()
    return params


def ground_to_ground_params(session: RadiantSession, **overrides: object) -> ParameterSet:
    """500 m mast → ground target, 60° path zenith (matrix class: horizontal short path)."""
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("source.scene_type", "extended")
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("geometry.target_altitude_m", 0.0)
    params.set("geometry.path_zenith_rad", math.radians(60.0))
    params.set("detector.n_pixels_cross", 640)
    _seed_mwir_optics(params)
    for name, value in overrides.items():
        params.set(name, value)
    params.resolve()
    return params


# ---------------------------------------------------------------------------
# A. Ground-to-space SST with a Cn² profile (Gap 110)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sst_hv() -> ChainResult:
    """SST scene with the HV-5/7 profile driving r₀."""
    session = RadiantSession(wavelength_um=VIS_WL)
    return session.run(sst_params(session, **{"atmosphere.cn2_profile": "hufnagel_valley"}))


@pytest.fixture(scope="module")
def sst_no_turbulence() -> ChainResult:
    """The identical scene with turbulence off — the differential reference."""
    session = RadiantSession(wavelength_um=VIS_WL)
    return session.run(sst_params(session))


@pytest.mark.level2
class TestGroundToSpaceTurbulence:
    """The SST class: an up-looking full column, r₀ from the profile."""

    def test_scene_is_ground_to_space_up_looking(self, sst_hv: ChainResult) -> None:
        geometry = sst_hv.stage_outputs["geometry"]
        assert geometry["scene_class"] == "ground_to_space"
        assert geometry["observer_class"] == "ground"
        assert geometry["target_class"] == "space"
        assert geometry["los_direction"] == "up"

    def test_r0_is_profile_driven(self, sst_hv: ChainResult) -> None:
        """The resolution record says ``profile`` and quotes the band centre."""
        resolution = sst_hv.stage_outputs["atmosphere"]["r0_resolution"]
        assert resolution.mode == "profile"
        assert resolution.profile_name == "hufnagel_valley"
        assert resolution.reference_wavelength_um == pytest.approx(VIS_BAND_CENTRE_UM, rel=1e-12)
        assert resolution.path is not None
        assert not resolution.path.negligible
        assert resolution.path.zeta_low_rad == pytest.approx(SST_ZENITH_RAD, rel=1e-12)

    def test_r0_matches_the_literature_hv_5_7_value(self, sst_hv: ChainResult) -> None:
        r"""Truth anchor: HV-5/7 is *defined* by r₀ ≈ 5 cm at 0.5 µm, zenith.

        The scene is at 0.625 µm and 20° from the zenith, where the standard
        plane-parallel scaling gives

            r₀ = 5 cm · (0.625/0.5)^(6/5) · cos(20°)^(3/5) = 6.296 cm.

        Hand-evaluated: 1.25^1.2 = 1.307057, cos(20°)^0.6 = 0.963365,
        5 · 1.307057 · 0.963365 = 6.2958 cm.  The path integral returns 6.246 cm
        — 0.8 % low, which is the gap between HV-5/7's *nominal* 5 cm label and
        the exact integral of its own analytic profile (4.9606 cm), not an error
        in the path weighting.
        """
        r0_m = sst_hv.stage_outputs["atmosphere"]["r0_m"]
        literature_m = 0.05 * (VIS_BAND_CENTRE_UM / 0.5) ** 1.2 * math.cos(SST_ZENITH_RAD) ** 0.6
        assert literature_m == pytest.approx(0.0629584, rel=1e-5)  # the hand calculation
        assert r0_m == pytest.approx(literature_m, rel=0.015)

    def test_r0_obeys_the_wavelength_and_zenith_scaling_exactly(self, sst_hv: ChainResult) -> None:
        r"""Cross-model: the path integral reproduces r₀ ∝ λ^(6/5) sec(ζ)^(−3/5).

        The plane-parallel scaling law is an *independent* closed form — it is
        not how ``r0_path`` computes anything (that module integrates
        Cn²(h) W(h) ds slab by slab).  Anchoring the same profile at 0.5 µm and
        zero zenith and scaling analytically must land on the chain's number.
        """
        from radiant.atmosphere.cn2_hufnagel_valley import HufnagelValleyCn2
        from radiant.atmosphere.r0_path import path_fried_parameter_from_los
        from radiant.core.los_geometry import LineOfSightGeometry

        vertical = path_fried_parameter_from_los(
            LineOfSightGeometry(h_tgt=7.0e5, h_sensor=0.0, theta_o=math.pi),
            HufnagelValleyCn2(),
            0.5e-6,
            "plane",
        )
        # 4.9606 cm — the exact vertical HV-5/7 integral at 0.5 µm.
        assert vertical.r0_m == pytest.approx(0.049606, rel=1e-4)
        scaled = vertical.r0_m * (VIS_BAND_CENTRE_UM / 0.5) ** 1.2 * math.cos(SST_ZENITH_RAD) ** 0.6
        assert sst_hv.stage_outputs["atmosphere"]["r0_m"] == pytest.approx(scaled, rel=1e-12)

    def test_turbulence_reaches_the_psf(
        self, sst_hv: ChainResult, sst_no_turbulence: ChainResult
    ) -> None:
        r"""Truth anchor: FWHM → 0.98 λ f / r₀ once turbulence dominates.

        r₀ = 6.246 cm at 0.625 µm with f = 10 m gives a Kolmogorov
        long-exposure blur of 0.98 · 0.625e-6 · 10 / 0.06246 = 98.07 µm — an
        order of magnitude past the 6.4 µm diffraction core, so the degraded
        PSF's FWHM must sit just above the pure-turbulence value.
        """
        r0_m = sst_hv.stage_outputs["atmosphere"]["r0_m"]
        fwhm_turb_m = 0.98 * VIS_BAND_CENTRE_UM * 1e-6 * 10.0 / r0_m
        assert fwhm_turb_m == pytest.approx(9.807e-5, rel=1e-3)  # hand calculation

        fwhm_with = sst_hv.metrics["fwhm_x_m"]
        fwhm_without = sst_no_turbulence.metrics["fwhm_x_m"]
        # Turbulence broadens: nearly an order of magnitude past the
        # diffraction-plus-pixel PSF (10.29 µm → 99.17 µm, a factor 9.64).
        assert fwhm_with > 9.0 * fwhm_without
        # And lands within 2 % of the analytic Kolmogorov width (the residual is
        # the diffraction core + pixel aperture adding in near-quadrature).
        assert fwhm_with == pytest.approx(fwhm_turb_m, rel=0.02)
        assert fwhm_with > fwhm_turb_m  # never narrower than turbulence alone

    def test_turbulence_degrades_rer_and_ee(
        self, sst_hv: ChainResult, sst_no_turbulence: ChainResult
    ) -> None:
        """Both spatial-domain metrics come off the one degraded PSF (Rule 4)."""
        assert sst_hv.metrics["rer"] < sst_no_turbulence.metrics["rer"]
        assert sst_hv.metrics["ee_3x3"] < sst_no_turbulence.metrics["ee_3x3"]

    def test_every_metric_is_finite(self, sst_hv: ChainResult) -> None:
        """A newly-opened scene class must not leak NaN/inf into any metric."""
        bad = {
            name: value
            for name, value in sst_hv.metrics.items()
            if isinstance(value, (int, float, np.floating)) and not math.isfinite(float(value))
        }
        assert bad == {}

    def test_dual_path_consistency_holds_under_turbulence(self, sst_hv: ChainResult) -> None:
        """CU-234 regression: the turbulence term must enter BOTH Rule-4 paths.

        Until 2026-07-27 `performance/stage.py` converted cycles/mrad →
        cycles/m with ``* 1e3`` instead of ``* 1e-3`` for the turbulence MTF
        term only (a 1e6 slip, pre-existing since the dual-path commit
        847a71b), so ``mtf_turbulence_*`` ≡ 1 and the MTF product carried no
        turbulence while the PSF path did.  This assertion was the strict-xfail
        tripwire that forced the fix to flip it.
        """
        consistency = sst_hv.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x and consistency.passed_y


@pytest.mark.level2
class TestDirectR0Override:
    """Rule 3 of the resolution policy: an entered r₀ is never silently replaced."""

    def test_direct_selector_ignores_the_profile_entirely(self) -> None:
        """``cn2_profile = 'direct'`` (the default) is the pre-Gap-110 path."""
        session = RadiantSession(wavelength_um=VIS_WL)
        result = session.run(sst_params(session, **{"atmosphere.r0_m": 0.25}))
        assert result.stage_outputs["atmosphere"]["r0_m"] == 0.25
        # No profile was evaluated, so no diagnostic record is published: a
        # scene that simply entered r0_m sees exactly the outputs it saw before.
        assert "r0_resolution" not in result.stage_outputs["atmosphere"]

    def test_explicit_r0_wins_over_an_agreeing_profile(self, sst_hv: ChainResult) -> None:
        """Within 1 % the entered number is used verbatim, profile attached."""
        profile_r0_m = sst_hv.stage_outputs["atmosphere"]["r0_m"]
        entered_m = profile_r0_m * 1.005  # 0.5 % — inside the agreement band
        session = RadiantSession(wavelength_um=VIS_WL)
        result = session.run(
            sst_params(
                session,
                **{"atmosphere.cn2_profile": "hufnagel_valley", "atmosphere.r0_m": entered_m},
            )
        )
        resolution = result.stage_outputs["atmosphere"]["r0_resolution"]
        assert resolution.mode == "direct"
        assert result.stage_outputs["atmosphere"]["r0_m"] == entered_m
        assert resolution.path is not None  # kept as the cross-check
        assert resolution.path.r0_m == pytest.approx(profile_r0_m, rel=1e-12)

    def test_disagreeing_r0_and_profile_raise(self, sst_hv: ChainResult) -> None:
        """Two live inputs for one quantity, > 1 % apart — CU-093 pattern."""
        profile_r0_m = sst_hv.stage_outputs["atmosphere"]["r0_m"]
        session = RadiantSession(wavelength_um=VIS_WL)
        with pytest.raises(TurbulenceSpecificationError) as excinfo:
            session.run(
                sst_params(
                    session,
                    **{
                        "atmosphere.cn2_profile": "hufnagel_valley",
                        "atmosphere.r0_m": 4.0 * profile_r0_m,
                    },
                )
            )
        message = str(excinfo.value)
        assert "atmosphere.r0_m" in message
        assert "hufnagel_valley" in message


# ---------------------------------------------------------------------------
# B. Air-to-air level arm with a crossing target (Gap 111)
# ---------------------------------------------------------------------------

#: ω = v⊥ / R = 250 m/s / 50 000 m.  Heading ψ = π/2 puts the target velocity on
#: ê_⊥, which is exactly perpendicular to the line of sight for every θ_o, so no
#: projection factor survives.
CROSSING_RATE_RAD_S = A2A_TARGET_SPEED_M_S / A2A_RANGE_M  # 5.000e-3 rad/s

#: s = ω · t_int · f = 5.0e-3 · 0.005 · 1.5 m.
CROSSING_SMEAR_M = CROSSING_RATE_RAD_S * A2A_T_INT_S * A2A_FOCAL_M  # 3.750e-5 m

_CROSSING_TARGET: dict[str, object] = {
    "geometry.target_speed_m_s": A2A_TARGET_SPEED_M_S,
    "geometry.target_heading_rad": math.pi / 2.0,
}


@pytest.mark.level2
class TestAirToAirCrossingTarget:
    """A level arm where the *target* supplies all of the relative motion."""

    @staticmethod
    def _run(**overrides: object) -> ChainResult:
        session = RadiantSession(wavelength_um=MWIR_WL)
        return session.run(air_to_air_params(session, **overrides))

    def test_scene_is_air_to_air_level(self) -> None:
        geometry = self._run().stage_outputs["geometry"]
        assert geometry["scene_class"] == "air_to_air"
        assert geometry["los_direction"] == "level"
        assert geometry["slant_range_m"] == pytest.approx(A2A_RANGE_M, rel=1e-9)

    def test_stationary_target_has_no_relative_rate(self) -> None:
        """Airborne platform, no ground speed, no target motion ⇒ ω = 0."""
        result = self._run()
        assert result.stage_outputs["geometry"]["los_angular_rate_rad_s"] == 0.0
        assert result.stage_outputs["geometry"]["los_rate_mode"].startswith("platform-only")
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0

    def test_kinematics_door_gives_the_hand_calculated_rate(self) -> None:
        """Truth anchor: ω = v/R = 250 / 50 000 = 5.000e-3 rad/s."""
        geometry = self._run(**_CROSSING_TARGET).stage_outputs["geometry"]
        assert geometry["los_rate_mode"] == "target velocity (K2)"
        assert geometry["los_angular_rate_rad_s"] == pytest.approx(5.0e-3, rel=1e-12)
        assert geometry["los_angular_rate_rad_s"] == pytest.approx(CROSSING_RATE_RAD_S, rel=1e-12)

    def test_smear_is_the_relative_rate_on_the_focal_plane(self) -> None:
        """Truth anchor: s = ω t f = 5.0e-3 · 0.005 · 1.5 = 37.50 µm (2.5 px)."""
        result = self._run(**_CROSSING_TARGET)
        smear_m = result.stage_outputs["platform"]["smear_width_m"]
        assert smear_m == pytest.approx(3.75e-5, rel=1e-12)
        assert smear_m == pytest.approx(CROSSING_SMEAR_M, rel=1e-12)
        assert smear_m / 15.0e-6 == pytest.approx(2.5, rel=1e-12)  # pixels

    def test_smear_degrades_the_along_track_spatial_metrics(self) -> None:
        """A 2.5-pixel smear must show up in the PSF-path metrics, along-track only."""
        moving = self._run(**_CROSSING_TARGET)
        still = self._run()
        broadening_y = moving.metrics["fwhm_y_m"] / still.metrics["fwhm_y_m"]
        broadening_x = moving.metrics["fwhm_x_m"] / still.metrics["fwhm_x_m"]
        assert moving.metrics["rer"] < still.metrics["rer"]
        # Along-track: 2.5 pixels of rect blur on a ~1.6-pixel PSF roughly
        # doubles the width.
        assert broadening_y > 1.5
        # Cross-track: the smear kernel is one-dimensional, so x is unchanged up
        # to the FWHM estimator's grid discretization (~2 %) — two orders of
        # magnitude less than the along-track effect.
        assert abs(broadening_x - 1.0) < 0.03
        assert broadening_y - 1.0 > 20.0 * abs(broadening_x - 1.0)

    def test_direct_rate_door_reaches_the_same_smear(self) -> None:
        """K1 and K2 are two doors on one quantity — same physics downstream."""
        via_velocity = self._run(**_CROSSING_TARGET)
        via_rate = self._run(**{"geometry.los_angular_rate_rad_s": CROSSING_RATE_RAD_S})
        assert via_rate.stage_outputs["geometry"]["los_rate_mode"] == (
            "geometry.los_angular_rate_rad_s"
        )
        assert via_rate.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            via_velocity.stage_outputs["platform"]["smear_width_m"], rel=1e-12
        )

    def test_both_doors_agreeing_is_accepted_and_labelled(self) -> None:
        result = self._run(
            **{**_CROSSING_TARGET, "geometry.los_angular_rate_rad_s": CROSSING_RATE_RAD_S}
        )
        mode = result.stage_outputs["geometry"]["los_rate_mode"]
        assert "consistent" in mode
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            CROSSING_SMEAR_M, rel=1e-12
        )

    def test_both_doors_disagreeing_raise_naming_both(self) -> None:
        """ADR-0006 rule 2: > 1 % apart is a specification error, not a choice."""
        with pytest.raises(GeometrySpecificationError) as excinfo:
            self._run(
                **{
                    **_CROSSING_TARGET,
                    "geometry.los_angular_rate_rad_s": 2.0 * CROSSING_RATE_RAD_S,
                }
            )
        message = str(excinfo.value)
        assert "geometry.los_angular_rate_rad_s" in message
        assert "target velocity (K2)" in message

    def test_receding_target_does_not_smear(self) -> None:
        """ψ = 0 puts the whole velocity along the LOS: range changes, not bearing."""
        result = self._run(
            **{
                "geometry.target_speed_m_s": A2A_TARGET_SPEED_M_S,
                "geometry.target_heading_rad": 0.0,
            }
        )
        rate = result.stage_outputs["geometry"]["los_angular_rate_rad_s"]
        # θ_o is within 0.3° of π/2 on this arm, so the residual perpendicular
        # component is |v| cos(θ_o) ≈ 250 · 2e-3 / 50 000, not exactly zero.
        assert abs(rate) < 0.02 * CROSSING_RATE_RAD_S


# ---------------------------------------------------------------------------
# C. Metric conditioning per scene class (guardrail G3)
# ---------------------------------------------------------------------------


def _run_with_map_neutralised(
    monkeypatch: pytest.MonkeyPatch,
    session: RadiantSession,
    params: ParameterSet,
) -> ChainResult:
    """Run *params* with the scene-relevance map forced to suppress nothing.

    This is the pre-Phase-3 selection: ``PerformanceStage`` called
    ``resolve_selection(_enabled_groups(params))`` with no suppression argument.
    Patching the map's *consumer* (rather than editing the map) keeps the
    differential honest — everything else in the chain is untouched.
    """
    import radiant.performance.stage as performance_stage

    monkeypatch.setattr(performance_stage, "suppressed_metrics", lambda scene, groups: frozenset())
    return session.run(params)


@pytest.mark.level2
class TestGroundTargetSelectionIsUnchanged:
    """Zero drift: a ground-target scene's metrics are the pre-phase metrics."""

    def test_scene_is_ground_to_ground(self) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        geometry = session.run(ground_to_ground_params(session)).stage_outputs["geometry"]
        assert geometry["scene_class"] == "ground_to_ground"
        assert geometry["los_direction"] == "down"

    def test_metric_set_equals_the_legacy_set_exactly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Differential proof, not a subset check.

        The only difference between "map applied" and "map neutralised" is the
        three target-plane keys — and those keys did not exist before this
        phase, so the legacy set is reproduced *exactly*.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        conditioned = session.run(ground_to_ground_params(session))
        unconditioned = _run_with_map_neutralised(
            monkeypatch, session, ground_to_ground_params(session)
        )

        legacy_keys = set(unconditioned.metrics) - TARGET_PLANE_METRICS
        assert set(conditioned.metrics) == legacy_keys
        assert set(unconditioned.metrics) - set(conditioned.metrics) == TARGET_PLANE_METRICS

    def test_every_legacy_metric_value_is_bit_identical(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        conditioned = session.run(ground_to_ground_params(session))
        unconditioned = _run_with_map_neutralised(
            monkeypatch, session, ground_to_ground_params(session)
        )
        for name, value in conditioned.metrics.items():
            other = unconditioned.metrics[name]
            if isinstance(value, float) and math.isnan(value):
                assert math.isnan(other), name
            else:
                assert value == other, name

    def test_ground_projection_metrics_are_present(self) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        metrics = session.run(ground_to_ground_params(session)).metrics
        for name in ("gsd_cross_track_m", "gsd_along_track_m", "ground_range_m"):
            assert name in metrics, name


@pytest.mark.level2
class TestNonGroundTargetSelection:
    """A ground-to-air scene: no ground plane at the target, so no GSD family."""

    @staticmethod
    def _params(session: RadiantSession, **overrides: object) -> ParameterSet:
        params = session.default_params()
        params.set("source.target.temperature", 500.0)
        params.set("source.target.emissivity", 0.90)
        params.set("source.scene_type", "point_source")
        params.set("geometry.target.projected_area_m2", 1.0e-6)
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 500.0)
        params.set("geometry.target_altitude_m", 10_000.0)
        params.set("geometry.path_zenith_rad", math.radians(30.0))
        _seed_mwir_optics(params)
        for name, value in overrides.items():
            params.set(name, value)
        params.resolve()
        return params

    def test_ground_projection_family_defaults_off(self) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        result = session.run(self._params(session))
        assert result.stage_outputs["geometry"]["scene_class"] == "ground_to_air"
        for name in GROUND_PROJECTION_METRICS:
            assert name not in result.metrics, name
        # Named individually so the three the task calls out cannot silently
        # drop out of the frozenset without this test noticing.
        for name in ("gsd_geometric_mean_m", "ground_range_m", "niirs"):
            assert name not in result.metrics, name

    def test_target_plane_sample_distance_is_on(self) -> None:
        """Truth anchor: d = pitch · R / f, the small-angle plate scale."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        result = session.run(self._params(session))
        slant_m = float(result.stage_outputs["geometry"]["slant_range_m"])
        expected_m = 15.0e-6 * slant_m / 1.50
        for name in TARGET_PLANE_METRICS:
            assert name in result.metrics, name
            assert result.metrics[name] == pytest.approx(expected_m, rel=1e-12)

    def test_angular_metrics_are_band_independent(self) -> None:
        """Nothing in the off-set is angular: those metrics stay on everywhere."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        metrics = session.run(self._params(session)).metrics
        assert "diffraction_limit_angular_urad" in metrics
        assert "q_center" in metrics

    def test_explicit_selection_overrides_the_map(self) -> None:
        """Provenance gate: a flag the analyst set wins — for computable metrics.

        Explicitly enabling ``sampling`` on an up-looking scene overrides the
        relevance map's default suppression, so the group's computable members
        (the target-plane metrics) appear.  GSD stays absent regardless: the
        LOS-direction gate (GUI cleanup batch 1, 5af0362) is a *computability*
        condition — GSD's ground-plane cos projection is undefined for
        ``incidence_angle_rad ≥ π/2`` — not a relevance default, so an
        explicit opt-in revives suppressed metrics but cannot conjure an
        undefined one (absent, not wrong; the ADR-B convention).
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        result = session.run(self._params(session, **{"performance.metrics.sampling": True}))
        for name in TARGET_PLANE_METRICS:
            assert name in result.metrics, name
        assert "gsd_cross_track_m" not in result.metrics
        assert "gsd_along_track_m" not in result.metrics

    def test_explicit_deselection_also_wins(self) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        result = session.run(self._params(session, **{"performance.metrics.sampling": False}))
        for name in TARGET_PLANE_METRICS:
            assert name not in result.metrics, name


# ---------------------------------------------------------------------------
# D. The optional scene-class assertion (ADR-0011 decision 8)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestSceneClassAssertion:
    def test_unset_assertion_is_the_default(self) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = ground_to_ground_params(session)
        assert params.get("geometry.scene_class") == "auto"

    def test_correct_assertion_passes_silently(self) -> None:
        """No error, no warning, and the metrics are untouched by asserting."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        baseline = session.run(ground_to_ground_params(session))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            asserted = session.run(
                ground_to_ground_params(session, **{"geometry.scene_class": "ground_to_ground"})
            )
        scene_class_warnings = [w for w in caught if "scene_class" in str(w.message)]
        assert scene_class_warnings == []
        assert asserted.metrics == baseline.metrics

    def test_wrong_assertion_raises_naming_both_labels(self) -> None:
        """The wrong-magnitude-altitude trap: 500 m entered where 500 km meant."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        with pytest.raises(GeometrySpecificationError) as excinfo:
            session.run(
                ground_to_ground_params(session, **{"geometry.scene_class": "space_to_ground"})
            )
        message = str(excinfo.value)
        assert "space_to_ground" in message  # asserted
        assert "ground_to_ground" in message  # derived
        assert excinfo.value.context["asserted"] == "space_to_ground"
        assert excinfo.value.context["derived"] == "ground_to_ground"
        assert excinfo.value.context["geometry.sensor_altitude_m"] == 500.0

    def test_assertion_catches_the_typo_on_a_new_class_too(self) -> None:
        session = RadiantSession(wavelength_um=MWIR_WL)
        with pytest.raises(GeometrySpecificationError, match="air_to_air"):
            session.run(air_to_air_params(session, **{"geometry.scene_class": "air_to_ground"}))


# ---------------------------------------------------------------------------
# E. Path-aware detection range (finding GF-15)
# ---------------------------------------------------------------------------


def _vacuum_bound_m(
    ref_range_m: float, signal_e: float, total_noise_e: float, threshold: float
) -> float:
    r"""R_vac = R_ref √(S_ref/S*) — the zero-extinction inverse-square answer.

    Re-anchored 2026-08-01 (CU-263): the detection criterion is shot-consistent,
    so the signal the threshold demands is the positive root of
    :math:`S^2 - T^2 S - T^2 N_0^2 = 0` with :math:`N_0^2 = \sigma_{ref}^2 -
    S_{ref}`, not the frozen-noise product :math:`T\sigma_{ref}`.
    """
    floor_sq = total_noise_e * total_noise_e - signal_e
    t2 = threshold * threshold
    signal_at_threshold = 0.5 * (t2 + math.sqrt(t2 * t2 + 4.0 * t2 * floor_sq))
    return ref_range_m * math.sqrt(signal_e / signal_at_threshold)


@pytest.mark.level2
class TestPathAwareDetectionRange:
    def test_up_looking_attains_the_vacuum_bound_above_the_column(
        self, sst_no_turbulence: ChainResult
    ) -> None:
        r"""The SST reference range is already outside the modelled column.

        τ stops accruing at ``h_atm_top``, so for every R beyond R_ref the ratio
        τ(R)/τ(R_ref) is exactly 1 and the solve degenerates to pure
        inverse-square.  Truth anchor: R = R_ref √(S_ref/S*).

        Run on the turbulence-free variant of the scene: an r₀ = 6 cm blur on a
        1 m aperture collapses EE_box by ~70×, which drops this point source
        below threshold at its own reference range — a fact about the target's
        brightness, not about the solver under test.
        """
        sst = sst_no_turbulence
        result = sst.stage_outputs["performance"]["detection_range_result"]
        assert result.ok, result.failure_reason
        ref_range_m = float(sst.stage_outputs["geometry"]["slant_range_m"])
        snr_result = sst.stage_outputs["performance"]["snr_result"]
        bound_m = _vacuum_bound_m(
            ref_range_m, float(snr_result.signal_e), float(snr_result.noise_e), 5.0
        )
        assert result.range_m == pytest.approx(bound_m, abs=1.0)  # solver tol_m
        assert result.range_m <= bound_m * (1.0 + 1e-9)

    def test_level_arm_is_strictly_inside_the_vacuum_bound(self) -> None:
        """A constant-altitude ray keeps attenuating, so it cannot reach R_vac."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        result = session.run(air_to_air_params(session))
        detection = result.stage_outputs["performance"]["detection_range_result"]
        assert detection.ok, detection.failure_reason
        snr_result = result.stage_outputs["performance"]["snr_result"]
        bound_m = _vacuum_bound_m(
            A2A_RANGE_M, float(snr_result.signal_e), float(snr_result.noise_e), 5.0
        )
        assert detection.range_m < bound_m
        # The attenuated answer is a fixed fraction of the vacuum bound for this
        # arm — a 14 % shortfall, not a rounding difference. CU-263 lengthened
        # both the bound and the attenuated answer (the target's own shot noise
        # is most of the noise power here), so the ratio barely moved: 0.864 →
        # 0.860 re-measured. The bar is the shortfall, and it survives.
        assert detection.range_m / bound_m == pytest.approx(0.860, rel=0.02)

    def test_level_arm_reproduces_the_constant_alpha_solver(self) -> None:
        r"""Cross-model: the level arm *is* the constant-extinction model.

        α = −ln(τ̄)/R_ref fed to the shipped Beer-Lambert solver must land on the
        path-aware answer to well inside the 1 m convergence tolerance — if it
        did not, one of the two would be wrong about the same physics.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        result = session.run(air_to_air_params(session))
        snr_result = result.stage_outputs["performance"]["snr_result"]

        tau = np.asarray(result.stage_outputs["atmosphere"]["tau_atm"])
        band = (MWIR_WL >= 3.5) & (MWIR_WL <= 5.0)
        tau_bar = float(np.mean(tau[band]))
        alpha_per_m = -math.log(tau_bar) / A2A_RANGE_M

        reference = detection_range_beer_lambert(
            signal_e_at_ref=float(snr_result.signal_e),
            noise_e=float(snr_result.noise_e),
            ref_range_m=A2A_RANGE_M,
            extinction_coeff=alpha_per_m,
            snr_threshold=5.0,
        )
        path_aware = result.stage_outputs["performance"]["detection_range_result"]
        assert reference.ok and path_aware.ok
        # The contract this test states is agreement "well inside the 1 m convergence
        # tolerance" — the two solvers integrate the same physics differently, so they
        # are expected to differ at the sub-metre level, not to be identical. The
        # literal was 0.05 m, an order of magnitude tighter than the stated bar, and
        # it pinned a coincidence of the *pre-CU-253* molecular optical depth: with the
        # Rayleigh coefficient corrected the residual moved from ~0.01 m to 0.48 m on a
        # 65.9 km answer (7 ppm) — still four times inside the documented 1 m bar and
        # far from the 14 % attenuation effect the sibling test measures. Asserting the
        # bar the docstring actually claims, with the measured residual recorded so a
        # genuine divergence is still visible.
        assert path_aware.range_m == pytest.approx(reference.range_m, abs=1.0)
        assert abs(path_aware.range_m - reference.range_m) < 0.6  # measured 0.48 m

    def test_down_looking_now_takes_the_path_aware_arm(self) -> None:
        """Scope, re-anchored 2026-08-01 (CU-263, folding ex-CU-236).

        The down arm used to be routed to the constant-α solver deliberately;
        it now goes through the path-aware one like every other topology. A
        spaceborne sensor sits above ``h_atm_top``, so its receding leg is
        vacuum and the profile's extinction is exactly zero — which is the
        physics ex-CU-236 said the constant-α extrapolation got wrong.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = session.default_params()
        params.set("source.target.temperature", 500.0)
        params.set("source.target.emissivity", 0.90)
        params.set("source.scene_type", "point_source")
        # 0.05 m² keeps the target unresolved (√A_t/d = 0.04·PSF_FWHM, inside the
        # 0.1 point-source guard) while putting it above threshold at the
        # reference range, which the shot-consistent solve needs to report a
        # range at all. The 1e-4 m² the scope-only version used sat at SNR 0.05.
        params.set("geometry.target.projected_area_m2", 0.05)
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 5.0e5)
        params.set("geometry.target_altitude_m", 0.0)
        params.set("geometry.path_zenith_rad", 0.2)
        _seed_mwir_optics(params)
        params.resolve()
        result = session.run(params)
        assert result.stage_outputs["geometry"]["los_direction"] == "down"
        detection = result.stage_outputs["performance"]["detection_range_result"]
        assert detection is not None
        assert detection.ok, detection.failure_reason

        los = result.stage_outputs["geometry"]["los_geometry"]
        ref_range_m = float(result.stage_outputs["source"]["range_m"])
        profile = resolve_path_optical_depth(los, ref_range_m, 0.5).profile
        assert profile is not None
        assert profile.topology == "down_vacuum_tail"

        # The answer is the vacuum bound: the receding leg accrues no further
        # optical depth, so the constant-α extrapolation it replaced is strictly
        # shorter (ex-CU-236's direction).
        snr_result = result.stage_outputs["performance"]["snr_result"]
        bound_m = _vacuum_bound_m(
            ref_range_m, float(snr_result.signal_e), float(snr_result.noise_e), 5.0
        )
        assert detection.range_m == pytest.approx(bound_m, abs=1.0)
