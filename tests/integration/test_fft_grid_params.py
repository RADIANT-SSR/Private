"""Integration tests for the CU-288 FFT-grid parameters across the full chain.

Two things must hold when ``optics.pupil_npix`` / ``optics.psf_oversample``
move off their defaults:

1. The Rule-4 dual-path consistency invariant (|FT{PSF}| vs MTF product,
   tolerance 2e-2 per CU-045) holds across the schema's supported range —
   the CU-288 acceptance condition for making the grid tuneable at all.
2. Explicitly setting the defaults is indistinguishable from not setting
   them (set-vs-default identity), so the parameterization cannot have
   forked the code path.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession


def _run(pupil_npix: int | None = None, psf_oversample: int | None = None):
    wl = np.linspace(3.5, 5.0, 200)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("optics.aperture_diameter_m", 0.30)
    params.set("optics.focal_length_m", 1.20)
    params.set("optics.transmission_scalar", 0.70)
    params.set("detector.pixel_pitch_x_um", 18.0)
    params.set("detector.pixel_pitch_y_um", 18.0)
    params.set("detector.qe_value", 0.70)
    params.set("detector.dark_rate_e_per_s", 100.0)
    params.set("geometry.sensor_altitude_m", 8000.0)
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("spectral_integration.filter_min_um", 3.5)
    params.set("spectral_integration.filter_max_um", 5.0)
    params.set("spectral_integration.integration_time_s", 0.005)
    params.set("readout.read_noise_e_rms", 5.0)
    params.set("readout.gain_e_per_dn", 32.0)
    params.set("readout.adc_bits", 16)
    params.set("readout.full_well_capacity_e", 2000000.0)
    params.set("platform.jitter_rms_urad", 5.0)
    params.set("platform.smear_length_um", 5.0)
    if pupil_npix is not None:
        params.set("optics.pupil_npix", pupil_npix)
    if psf_oversample is not None:
        params.set("optics.psf_oversample", psf_oversample)
    params.resolve()
    return session.run(params)


@pytest.mark.level2
class TestConsistencyAcrossTheGrid:
    """Rule-4 dual-path consistency holds over the supported parameter range."""

    # Bounds corners measured during CU-288 (reference MWIR config):
    #   (32,4) 0.0075 / (32,16) 0.0003 / (512,4) 0.0074 / (512,16) 0.0003 — pass
    #   oversample 2–3 breaches: 0.032 when the padded grid lands at exactly
    #   2× the pupil width (why the schema floor is 4, not compute_sampling's 2).
    # The two expensive corners (512-npix) are exercised once here at the cheap
    # oversample; the 512/16 corner (12.6 s) is left to the CU-288 record.
    @pytest.mark.parametrize(
        ("npix", "oversample"),
        [(32, 4), (32, 16), (64, 4), (256, 8), (512, 4)],
        ids=["low-corner", "low-npix-high-os", "coarse", "fine-pupil", "high-npix-corner"],
    )
    def test_dual_path_consistency_holds(self, npix: int, oversample: int) -> None:
        result = _run(pupil_npix=npix, psf_oversample=oversample)
        cons = result.stage_outputs["performance"]["dual_path_consistency"]
        assert cons.passed_x, (
            f"npix={npix}, oversample={oversample}: x-axis error "
            f"{cons.max_absolute_error_x:.3e} > tol {cons.tolerance:g}"
        )
        assert cons.passed_y, (
            f"npix={npix}, oversample={oversample}: y-axis error "
            f"{cons.max_absolute_error_y:.3e} > tol {cons.tolerance:g}"
        )

    def test_pupil_grid_reaches_the_diagnostic_maps(self) -> None:
        result = _run(pupil_npix=64, psf_oversample=4)
        assert result.stage_outputs["optics"]["pupil_amplitude"].shape == (64, 64)


@pytest.mark.level2
class TestSetVsDefaultIdentity:
    """Setting the schema defaults explicitly changes nothing at all."""

    def test_snr_is_bit_identical(self) -> None:
        baseline = _run()
        explicit = _run(pupil_npix=128, psf_oversample=8)
        assert explicit.metrics["snr"] == baseline.metrics["snr"]
        cons_b = baseline.stage_outputs["performance"]["dual_path_consistency"]
        cons_e = explicit.stage_outputs["performance"]["dual_path_consistency"]
        assert cons_e.max_absolute_error_x == cons_b.max_absolute_error_x
        assert cons_e.max_absolute_error_y == cons_b.max_absolute_error_y
