"""Integration: Gap 48 — QE temperature dependence QE(T).

detector.qe_temperature_coeff_per_K applies a linear QE(T) factor. Default
0 leaves the scalar path exactly unchanged; a nonzero coefficient scales
the signal by 1 + coeff·(T_det − T_ref); QE is clamped to [0, 1] with a
warning.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession

BAND_MIN, BAND_MAX = 3.5, 5.0


def _run(coeff: float, t_det: float = 80.0, t_ref: float = 300.0, qe_value: float = 0.6):
    wl = np.linspace(BAND_MIN, BAND_MAX, 150)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.15)
    p.set("optics.focal_length_m", 0.5)
    p.set("optics.transmission_scalar", 0.8)
    p.set("detector.pixel_pitch_x_um", 25.0)
    p.set("detector.pixel_pitch_y_um", 25.0)
    p.set("detector.qe_value", qe_value)
    p.set("detector.detector_temperature_K", t_det)
    p.set("detector.qe_temperature_coeff_per_K", coeff)
    p.set("detector.qe_temperature_ref_K", t_ref)
    p.set("detector.dark_rate_e_per_s", 1e5)
    p.set("geometry.sensor_altitude_m", 3000.0)
    p.set("spectral_integration.filter_min_um", BAND_MIN)
    p.set("spectral_integration.filter_max_um", BAND_MAX)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 30.0)
    p.set("readout.gain_e_per_dn", 20.0)
    p.set("readout.adc_bits", 14)
    p.resolve()
    return session.run(p)


@pytest.mark.level2
class TestQeTemperature:
    def test_zero_coeff_no_scaling(self) -> None:
        """coeff = 0 ⇒ the QE the stage uses is the un-scaled scalar value."""
        res = _run(0.0, qe_value=0.6)
        qe_used = np.asarray(res.stage_outputs["spectral_integration"]["qe_curve"])
        assert np.allclose(qe_used, 0.6)  # no temperature factor applied

    def test_positive_coeff_scales_signal(self) -> None:
        """Signal scales by 1 + coeff·(T_det − T_ref)."""
        base = _run(0.0)
        # coeff 0.001/K, T_det 80, T_ref 300 → factor 1 + 0.001·(−220) = 0.78
        warmed = _run(0.001, t_det=80.0, t_ref=300.0)
        s0 = base.stage_outputs["spectral_integration"]["signal_e"]
        s1 = warmed.stage_outputs["spectral_integration"]["signal_e"]
        assert s1 == pytest.approx(0.78 * s0, rel=1e-3)

    def test_factor_unity_when_at_reference(self) -> None:
        """At T_det = T_ref the factor is 1 even with a nonzero coeff."""
        base = _run(0.0)
        at_ref = _run(0.002, t_det=300.0, t_ref=300.0)
        s0 = base.stage_outputs["spectral_integration"]["signal_e"]
        s1 = at_ref.stage_outputs["spectral_integration"]["signal_e"]
        # A flat curve equal to the scalar reproduces the scalar signal.
        assert s1 == pytest.approx(s0, rel=1e-5)

    def test_clamp_warns(self) -> None:
        """A factor pushing QE > 1 clamps with a UserWarning."""
        with pytest.warns(UserWarning, match="QE"):
            _run(0.01, t_det=300.0, t_ref=100.0, qe_value=0.9)  # factor 1+0.01·200 = 3
