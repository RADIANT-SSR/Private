"""Phase-2 integration tests — downstream stages consume published geometry.

Verifies the ADR-0006 data flow end-to-end: GeometryStage resolves the
input mode once, and SourceStage (LOS), PlatformStage (slant range),
and PerformanceStage (GSD / ground range / access rate) consume the
published values — including the alternate input modes (V2 off-nadir,
V6 circular orbit) that have no pre-ADR-0006 equivalent.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.los_geometry import theta_o_from_eta
from radiant.core.orbit import ground_track_speed_m_s
from radiant.core.parameters import ParameterSet

ALT = 500_000.0


def _run(**geometry_inputs: object):
    wl = np.linspace(3.8, 4.2, 16)
    session = RadiantSession(wavelength_um=wl)
    params: ParameterSet = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target.is_hot_target", True)
    params.set("optics.aperture_diameter_m", 0.3)
    params.set("optics.focal_length_m", 1.5)
    params.set("optics.transmission_scalar", 0.9)
    params.set("detector.pixel_pitch_x_um", 15.0)
    params.set("detector.pixel_pitch_y_um", 15.0)
    params.set("detector.qe_value", 0.7)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("detector.n_pixels_cross", 2048)
    params.set("geometry.sensor_altitude_m", ALT)
    params.set("spectral_integration.filter_min_um", 3.8)
    params.set("spectral_integration.filter_max_um", 4.2)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("readout.read_noise_e_rms", 50.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    for name, value in geometry_inputs.items():
        params.set(name, value)
    params.resolve()
    return session.run(params)


@pytest.mark.level2
class TestModeCoherence:
    """One input mode steers the whole chain — no stage re-derives."""

    def test_v2_off_nadir_reaches_atmosphere_los(self) -> None:
        eta = 0.5
        result = _run(**{"geometry.sensor_off_boresight_rad": eta})
        expected_theta_o = theta_o_from_eta(eta, ALT, 0.0)
        geo = result.stage_outputs["geometry"]
        assert geo["theta_o_rad"] == pytest.approx(expected_theta_o, rel=1e-12)
        # SourceStage adopted the published LOS (not a param rebuild,
        # which would have used the path_zenith default of 0).
        los = result.stage_outputs["source"]["los_geometry"]
        assert los.theta_o == pytest.approx(expected_theta_o, rel=1e-12)

    def test_v2_off_nadir_steers_gsd(self) -> None:
        eta = 0.5
        result = _run(**{"geometry.sensor_off_boresight_rad": eta})
        geo = result.stage_outputs["geometry"]
        # GSD consumed the published slant/incidence: cross-track GSD is
        # pitch × slant / f, NOT pitch × altitude / f (the nadir value).
        expected_cross = 15.0e-6 * geo["slant_range_m"] / 1.5
        assert result.metrics["gsd_cross_track_m"] == pytest.approx(expected_cross, rel=1e-12)
        assert result.metrics["gsd_cross_track_m"] > 15.0e-6 * ALT / 1.5  # off-nadir > nadir

    def test_v1_path_zenith_equivalent_gives_same_chain(self) -> None:
        """V2's eta and the equivalent V1 theta_o produce identical metrics."""
        eta = 0.4
        theta_o = theta_o_from_eta(eta, ALT, 0.0)
        r_eta = _run(**{"geometry.sensor_off_boresight_rad": eta})
        r_zen = _run(**{"geometry.path_zenith_rad": theta_o})
        assert r_eta.metrics["gsd_cross_track_m"] == pytest.approx(
            r_zen.metrics["gsd_cross_track_m"], rel=1e-12
        )
        assert r_eta.metrics["ground_range_m"] == pytest.approx(
            r_zen.metrics["ground_range_m"], rel=1e-12
        )
        assert r_eta.metrics["snr"] == pytest.approx(r_zen.metrics["snr"], rel=1e-9)

    def test_ground_range_metric_is_published_value(self) -> None:
        result = _run(**{"geometry.path_zenith_rad": 0.3})
        geo = result.stage_outputs["geometry"]
        assert result.metrics["ground_range_m"] == pytest.approx(geo["ground_range_m"], rel=1e-12)


@pytest.mark.level2
class TestCircularOrbitMode:
    """V6: one flag derives the kinematics — access rate with no manual speed."""

    def test_access_rate_from_orbit_flag(self) -> None:
        result = _run(**{"geometry.circular_orbit": True})
        v_expected = ground_track_speed_m_s(ALT)
        geo = result.stage_outputs["geometry"]
        assert geo["ground_speed_m_s"] == pytest.approx(v_expected, rel=1e-12)
        assert geo["orbital_period_s"] is not None
        # The access-rate metric consumed the derived speed.
        assert "access_rate_m2_s" in result.metrics
        assert result.metrics["access_rate_m2_s"] == pytest.approx(
            result.metrics["swath_width_m"] * v_expected, rel=1e-9
        )

    def test_no_orbit_flag_no_access_rate(self) -> None:
        result = _run()
        assert "access_rate_m2_s" not in result.metrics


@pytest.mark.level2
class TestNadirBackCompat:
    """Default nadir chain: published-geometry path reproduces legacy values."""

    def test_nadir_gsd_equals_legacy_formula(self) -> None:
        result = _run()
        assert result.metrics["gsd_cross_track_m"] == pytest.approx(15.0e-6 * ALT / 1.5, rel=1e-12)

    def test_nadir_ground_range_zero(self) -> None:
        result = _run()
        assert result.metrics["ground_range_m"] == pytest.approx(0.0, abs=1e-9)

    def test_smear_uses_published_slant(self) -> None:
        theta_o = 0.4
        result = _run(
            **{
                "geometry.path_zenith_rad": theta_o,
                "platform.ground_velocity_m_s": 6900.0,
            }
        )
        geo = result.stage_outputs["geometry"]
        # smear_width = v · t_int · f / slant  (platform/smear.py)
        expected = 6900.0 * 1e-3 * 1.5 / geo["slant_range_m"]
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(
            expected, rel=1e-12
        )
