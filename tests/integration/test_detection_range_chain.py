"""In-chain point-source detection range (Gap 77).

PerformanceStage bisects for the range where SNR falls to
performance.detection_snr_threshold, inverse-square with the extinction the path
actually has. Only computed in the point-source regime.

Re-anchored 2026-08-01 (CU-263, folding ex-CU-236). Two things moved:

* the criterion is now shot-consistent — ``S(R)/√(S(R) + N₀²) = threshold``
  rather than ``S(R)/σ_ref``, so the vacuum closed form is ``R_ref·√(S_ref/S*)``
  and not ``R_ref·√(SNR_ref/threshold)``;
* the down-looking arm goes through the path-aware solver, which **refuses** a
  continuation still inside the atmosphere (Rule 17). The reference geometry
  here therefore moved from an 8 km airborne sensor to a 500 km spaceborne one,
  whose receding leg is vacuum; the airborne refusal is asserted directly in
  :class:`TestAirborneDownLookingRefusal` instead of being the default case.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession

WL = np.linspace(3.5, 5.0, 200)

#: Spaceborne reference geometry: the sensor sits above ``h_atm_top``, so the leg
#: it recedes along is vacuum and the path-aware down arm resolves exactly.
SENSOR_ALT_M = 5.0e5
TARGET_RANGE_M = 5.2e5
#: 0.5 m² keeps √A_t/d at 0.077·PSF_FWHM — inside the point-source guard's 0.1.
TARGET_AREA_M2 = 0.5


def _point_source(
    atmosphere: str = "midlat_summer",
    threshold: float = 5.0,
    regime: str = "point_source",
    sensor_altitude_m: float = SENSOR_ALT_M,
    target_range_m: float = TARGET_RANGE_M,
):
    session = RadiantSession(wavelength_um=WL)
    p = session.default_params()
    p.set("source.target.temperature", 500.0)
    p.set("source.target.emissivity", 0.95)
    p.set("geometry.target.projected_area_m2", TARGET_AREA_M2)
    p.set("geometry.target_range_m", target_range_m)
    p.set("source.regime_override", regime)
    p.set("source.background.temperature", 250.0)
    p.set("source.background.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("detector.pixel_pitch_x_um", 18.0)
    p.set("detector.pixel_pitch_y_um", 18.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", sensor_altitude_m)
    if atmosphere == "exo":
        p.set("atmosphere.model", "exo")
    else:
        p.set("atmosphere.standard_atmosphere", atmosphere)
    p.set("spectral_integration.filter_min_um", 3.5)
    p.set("spectral_integration.filter_max_um", 5.0)
    p.set("spectral_integration.integration_time_s", 0.001)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 1.0)
    p.set("readout.adc_bits", 16)
    p.set("readout.full_well_capacity_e", 5.0e7)
    p.set("performance.detection_snr_threshold", threshold)
    p.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return session.run(p)


@pytest.mark.level2
class TestDetectionRangeInChain:
    def test_metric_present_and_converges_to_threshold(self) -> None:
        result = _point_source(threshold=5.0)
        assert "detection_range_m" in result.metrics
        dr = result.stage_outputs["performance"]["detection_range_result"]
        assert dr.ok
        assert dr.snr_at_range == pytest.approx(5.0, rel=1e-3)

    def test_extinction_shortens_range_vs_vacuum(self) -> None:
        """A real atmosphere (α > 0) detects at shorter range than vacuum."""
        atm = _point_source(atmosphere="midlat_summer")
        vac = _point_source(atmosphere="exo")
        assert atm.metrics["detection_range_m"] < vac.metrics["detection_range_m"]

    def test_vacuum_follows_the_shot_consistent_closed_form(self) -> None:
        """In vacuum, R = R_ref·√(S_ref/S*), S* = ½(T² + √(T⁴ + 4T²N₀²))."""
        r = _point_source(atmosphere="exo", threshold=5.0)
        signal_e = float(r.stage_outputs["readout"]["signal_e_final"])
        noise_e = float(r.stage_outputs["readout"]["sigma_total_e"])
        floor_sq = noise_e * noise_e - signal_e
        t2 = 25.0
        signal_at_threshold = 0.5 * (t2 + math.sqrt(t2 * t2 + 4.0 * t2 * floor_sq))
        expected = TARGET_RANGE_M * math.sqrt(signal_e / signal_at_threshold)
        assert r.metrics["detection_range_m"] == pytest.approx(expected, rel=1e-6)

    def test_shot_noise_decomposition_matches_the_chains_own_term(self) -> None:
        """σ² − S is the target-free floor because signal shot really is √S.

        The solvers derive N₀ from the (signal, total noise) pair; this asserts
        the assumption against the chain's own ``signal_shot`` noise term, after
        TDI and on-chip binning scaling.
        """
        r = _point_source(atmosphere="exo")
        signal_e = float(r.stage_outputs["readout"]["signal_e_final"])
        shot = next(t for t in r.noise_terms if t.name == "signal_shot")
        assert shot.value_e == pytest.approx(math.sqrt(signal_e), rel=1e-9)

    def test_higher_threshold_shortens_range(self) -> None:
        lo = _point_source(threshold=5.0).metrics["detection_range_m"]
        hi = _point_source(threshold=20.0).metrics["detection_range_m"]
        assert hi < lo

    def test_not_computed_in_extended_regime(self) -> None:
        result = _point_source(regime="extended")
        assert "detection_range_m" not in result.metrics


@pytest.mark.level2
class TestAirborneDownLookingRefusal:
    """CU-263 (ex-CU-236): the down arm inherits the path-aware refusal.

    An 8 km sensor recedes through 92 km of atmosphere before reaching
    ``h_atm_top``, and the metric layer has no altitude-resolved extinction
    profile for it. Rule 17: name the refusal, do not substitute the constant-α
    model that ex-CU-236 was filed against.
    """

    def test_attenuating_airborne_path_reports_a_named_failure(self) -> None:
        result = _point_source(sensor_altitude_m=8.0e3, target_range_m=5.0e4)
        assert result.stage_outputs["geometry"]["los_direction"] == "down"
        assert "detection_range_m" not in result.metrics
        dr = result.stage_outputs["performance"]["detection_range_result"]
        assert not dr.ok
        assert "down-looking" in dr.failure_reason
        assert "h_atm_top" in dr.failure_reason

    def test_transparent_airborne_path_still_resolves(self) -> None:
        """τ̄ = 1 ⇒ vacuum everywhere ⇒ nothing to refuse."""
        result = _point_source(atmosphere="exo", sensor_altitude_m=8.0e3, target_range_m=5.0e4)
        assert result.stage_outputs["geometry"]["los_direction"] == "down"
        assert result.metrics["detection_range_m"] > 5.0e4
