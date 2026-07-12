"""Tests for pushbroom/TDI dwell-time feasibility (Gap 74, minimum slice)."""

from __future__ import annotations

import pytest

from radiant.performance.scan_feasibility import scan_feasibility


class TestScanFeasibility:
    @pytest.mark.level0
    def test_dwell_time_is_gsd_over_velocity(self) -> None:
        """t_dwell = GSD_along / v_ground (hand calculation)."""
        f = scan_feasibility(
            gsd_along_track_m=9.0, ground_velocity_m_s=7000.0, integration_time_s=1e-4
        )
        assert f.max_integration_time_s == pytest.approx(9.0 / 7000.0, rel=1e-12)

    @pytest.mark.level0
    def test_feasible_when_within_dwell(self) -> None:
        f = scan_feasibility(9.0, 7000.0, 1e-4)  # 0.1 ms < 1.29 ms dwell
        assert f.feasible is True
        assert f.smear_pixels < 1.0

    @pytest.mark.level0
    def test_infeasible_when_over_dwell(self) -> None:
        f = scan_feasibility(9.0, 7000.0, 5e-3)  # 5 ms > 1.29 ms dwell
        assert f.feasible is False
        assert f.smear_pixels == pytest.approx(5e-3 / (9.0 / 7000.0), rel=1e-12)

    @pytest.mark.level0
    def test_boundary_exactly_one_pixel(self) -> None:
        dwell = 9.0 / 7000.0
        f = scan_feasibility(9.0, 7000.0, dwell)
        assert f.feasible is True
        assert f.smear_pixels == pytest.approx(1.0, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize(
        "gsd,v,t",
        [(0.0, 7000.0, 1e-4), (9.0, 0.0, 1e-4), (9.0, 7000.0, 0.0), (-1.0, 7000.0, 1e-4)],
    )
    def test_nonpositive_inputs_raise(self, gsd: float, v: float, t: float) -> None:
        with pytest.raises(ValueError):
            scan_feasibility(gsd, v, t)


class TestScanFeasibilityInChain:
    """Gap 74: the performance stage warns on infeasible TDI timing and
    stores max_integration_time_s."""

    @staticmethod
    def _run(v_ground: float, t_int: float):
        import warnings

        import numpy as np

        from radiant.api.session import RadiantSession

        wl = np.linspace(3.5, 5.0, 100)
        session = RadiantSession(wavelength_um=wl)
        p = session.default_params()
        p.set("source.target.temperature", 300.0)
        p.set("source.target.emissivity", 0.95)
        p.set("optics.aperture_diameter_m", 0.30)
        p.set("optics.focal_length_m", 1.20)
        p.set("optics.transmission_scalar", 0.70)
        p.set("detector.pixel_pitch_x_um", 18.0)
        p.set("detector.pixel_pitch_y_um", 18.0)
        p.set("detector.qe_value", 0.70)
        p.set("detector.dark_rate_e_per_s", 100.0)
        p.set("geometry.sensor_altitude_m", 600_000.0)
        p.set("platform.ground_velocity_m_s", v_ground)
        p.set("readout.n_tdi", 32)
        p.set("atmosphere.standard_atmosphere", "midlat_summer")
        p.set("spectral_integration.filter_min_um", 3.5)
        p.set("spectral_integration.filter_max_um", 5.0)
        p.set("spectral_integration.integration_time_s", t_int)
        p.set("readout.read_noise_e_rms", 5.0)
        p.set("readout.gain_e_per_dn", 1.0)
        p.set("readout.adc_bits", 16)
        p.resolve()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = session.run(p)
        scan_warns = [w for w in caught if "ScanFeasibility" in str(w.message)]
        return result, scan_warns

    @pytest.mark.level2
    def test_metric_stored(self) -> None:
        result, _ = self._run(7000.0, 1e-4)
        assert "max_integration_time_s" in result.metrics
        # GSD_along = 18e-6/1.2 × 600 km = 9 m; dwell = 9/7000.
        assert result.metrics["max_integration_time_s"] == pytest.approx(9.0 / 7000.0, rel=1e-6)

    @pytest.mark.level2
    def test_feasible_no_warning(self) -> None:
        _, scan_warns = self._run(7000.0, 1e-4)  # 0.1 ms < 1.29 ms dwell
        assert not scan_warns

    @pytest.mark.level2
    def test_infeasible_warns(self) -> None:
        _, scan_warns = self._run(7000.0, 5e-3)  # 5 ms > 1.29 ms dwell
        assert len(scan_warns) == 1
        assert "exceeds the per-line dwell" in str(scan_warns[0].message)

    @pytest.mark.level2
    def test_no_velocity_no_metric(self) -> None:
        """Without a ground velocity the guard is inert (parameter-gated)."""
        result, scan_warns = self._run(0.0, 5e-3)
        assert "max_integration_time_s" not in result.metrics
        assert not scan_warns
