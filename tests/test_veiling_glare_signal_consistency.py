"""Regression test for CU-062 — veiling-glare stray light vs signal.

For a uniform EXTENDED scene the veiling-glare stray electrons must equal
``vgf × signal_e``: veiling glare re-images a fraction ``vgf`` of the in-FOV
scene flux uniformly onto each pixel, and that flux is collected through the
same etendue (``A_collect · Ω_pixel``) onto the same pixel as the signal.

Before the fix the optics stage scaled the in-FOV irradiance by the pixel
IFOV solid angle ``Ω_pixel`` instead of the f-cone solid angle
``Ω_cone = A_collect / focal²`` — under-counting by ``A_collect / A_pixel ≈
(D/pitch)²·π/4`` and making the mode inert. This test would fail against that
bug (stray_e ~1e-7 of signal rather than ~vgf).
"""

from __future__ import annotations

import warnings

import pytest

from radiant.api import Sensor


def _run(vgf: float) -> dict[str, float]:
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", 300.0, unit="K")
    s.set("source.target.emissivity", 0.9)
    s.set("source.target.is_hot_target", True)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", 5000.0)
    s.set("optics.aperture_diameter_m", 0.20)
    s.set("optics.focal_length_m", 1.0)
    s.set("optics.transmission_scalar", 0.8)
    s.set("optics.stray.input_mode", "veiling_glare")
    s.set("optics.stray.veiling_glare_fraction", vgf)
    s.set("detector.pixel_pitch_x_um", 20.0)
    s.set("detector.pixel_pitch_y_um", 20.0)
    s.set("detector.qe_value", 0.7)
    s.set("detector.dark_rate_e_per_s", 1e4)
    s.set("detector.detector_temperature_K", 200.0)
    s.set("spectral_integration.filter_min_um", 8.0)
    s.set("spectral_integration.filter_max_um", 12.0)
    s.set("spectral_integration.integration_time_s", 1e-3)
    s.set("readout.read_noise_e_rms", 30.0)
    s.set("readout.full_well_capacity_e", 1e8)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = s.evaluate()
    return {
        "signal_e": r.stage_outputs["spectral_integration"]["signal_e"],
        "stray_e": r.stage_outputs["detector"]["stray_e"],
    }


class TestVeilingGlareSignalConsistency:
    @pytest.mark.level0
    @pytest.mark.parametrize("vgf", [0.01, 0.03, 0.10])
    def test_stray_equals_vgf_times_signal(self, vgf: float) -> None:
        out = _run(vgf)
        assert out["stray_e"] == pytest.approx(vgf * out["signal_e"], rel=1e-6)

    @pytest.mark.level0
    def test_zero_vgf_is_zero_stray(self) -> None:
        assert _run(0.0)["stray_e"] == pytest.approx(0.0, abs=1e-12)
