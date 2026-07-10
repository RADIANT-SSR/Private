"""Regression test for CU-058 — defocus and the Rule 4 dual-path invariant.

Before the fix, combining scalar-RMS WFE with nonzero defocus structurally
failed the dual-path consistency check (scenario 7.3 logged max_err ≈ 0.17
vs tolerance 0.05 on every run) because:

- the PSF path modeled defocus as a Gaussian spatial kernel, while
- the MTF product path folded defocus into the pupil as Zernike Z4 — and,
  worse, its ``_add_defocus_to_wfe`` discarded the scalar-RMS screen when
  doing so.

The fix folds defocus into the pupil WFE once (screen + Z4 in one phase)
before both paths, so FFT{PSF} equals the pupil autocorrelation by
Wiener–Khinchin and the consistency check passes. This test runs the
scenario-7.3 failure signature (0.07 waves RMS + 5 µm defocus, VNIR f/3)
through the full chain and asserts the check passes.
"""

from __future__ import annotations

import warnings

import pytest

from radiant.api import Sensor


def _run(wfe_waves: float, defocus_um: float):
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.reflectance", 0.3)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", 3000.0)
    s.set("geometry.solar_zenith_rad", 0.5)
    # f/6 with 5 µm pixels → Q ≈ 0.8: clear of the CU-003 rect-kernel
    # discretization floor (~0.055 at Q ≈ 0.2) that would mask the result.
    s.set("optics.aperture_diameter_m", 0.10)
    s.set("optics.focal_length_m", 0.60)
    s.set("optics.transmission_scalar", 0.8)
    s.set("optics.wfe_rms_waves", wfe_waves)
    s.set("optics.defocus_um", defocus_um)
    s.set("detector.pixel_pitch_x_um", 5.0)
    s.set("detector.pixel_pitch_y_um", 5.0)
    s.set("detector.qe_value", 0.6)
    s.set("detector.dark_rate_e_per_s", 1e3)
    s.set("detector.detector_temperature_K", 250.0)
    s.set("spectral_integration.filter_min_um", 0.5)
    s.set("spectral_integration.filter_max_um", 0.8)
    s.set("spectral_integration.integration_time_s", 1e-3)
    s.set("readout.read_noise_e_rms", 30.0)
    s.set("readout.full_well_capacity_e", 1e6)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return s.evaluate()


@pytest.mark.level2
class TestDefocusDualPath:
    def test_scalar_wfe_plus_defocus_passes_consistency(self) -> None:
        """The CU-058 failure signature now satisfies Rule 4."""
        res = _run(wfe_waves=0.07, defocus_um=5.0)
        consistency = res.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x, f"x max_err={consistency.max_absolute_error_x:.4f}"
        assert consistency.passed_y, f"y max_err={consistency.max_absolute_error_y:.4f}"

    def test_defocus_only_passes_consistency(self) -> None:
        res = _run(wfe_waves=0.0, defocus_um=5.0)
        consistency = res.stage_outputs["performance"]["dual_path_consistency"]
        assert consistency.passed_x and consistency.passed_y

    def test_defocus_degrades_mtf_at_nyquist(self) -> None:
        """Defocus via pupil Z4 is results-affecting in the right direction."""
        clean = _run(wfe_waves=0.07, defocus_um=0.0)
        defocused = _run(wfe_waves=0.07, defocus_um=5.0)
        assert defocused.metrics["mtf_at_nyquist"] < clean.metrics["mtf_at_nyquist"]
