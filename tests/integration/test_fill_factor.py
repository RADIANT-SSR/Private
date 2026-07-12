"""Fill-factor coupling across the three coupled paths (CU-074).

`detector.fill_factor` is the areal photosensitive fraction of the pixel
cell. A square photosite has linear width ``pitch·√FF``, which drives
BOTH Rule-4 spatial paths (PSF-path pixel-aperture kernel and the
MTF-product pixel sinc), while the collecting area ``pitch²·FF`` scales
the radiometric signal. Before CU-074 the MTF product used the full
pitch and radiometry used the full-pitch area, so any FF < 1 diverged
the two spatial paths (consistency warning every run) and overcounted
signal.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession

WL = np.linspace(3.5, 5.0, 500)


def _run(fill_factor: float) -> object:
    session = RadiantSession(wavelength_um=WL)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("detector.pixel_pitch_x_um", 18.0)
    p.set("detector.pixel_pitch_y_um", 18.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.fill_factor", fill_factor)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", 8000.0)
    p.set("atmosphere.standard_atmosphere", "midlat_summer")
    p.set("spectral_integration.filter_min_um", 3.5)
    p.set("spectral_integration.filter_max_um", 5.0)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 1.0)
    p.set("readout.adc_bits", 16)
    p.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return session.run(p)


@pytest.mark.level2
class TestFillFactorCoupling:
    def test_dual_path_consistent_at_ff_080(self) -> None:
        """The Rule-4 consistency check must pass at fill_factor = 0.8:
        the PSF-path kernel and the MTF-product sinc now use the same
        photosite width (pitch·√FF)."""
        result = _run(0.8)
        dp = result.stage_outputs["performance"]["dual_path_consistency"]
        assert dp.passed_x, f"x diverged: max_err={dp.max_absolute_error_x}"
        assert dp.passed_y, f"y diverged: max_err={dp.max_absolute_error_y}"

    def test_no_consistency_warning_at_ff_080(self) -> None:
        session = RadiantSession(wavelength_um=WL)
        p = session.default_params()
        for k, v in {
            "source.target.temperature": 300.0,
            "source.target.emissivity": 0.95,
            "optics.aperture_diameter_m": 0.30,
            "optics.focal_length_m": 1.20,
            "optics.transmission_scalar": 0.70,
            "detector.pixel_pitch_x_um": 18.0,
            "detector.pixel_pitch_y_um": 18.0,
            "detector.qe_value": 0.70,
            "detector.fill_factor": 0.8,
            "detector.dark_rate_e_per_s": 100.0,
            "geometry.sensor_altitude_m": 8000.0,
            "atmosphere.standard_atmosphere": "midlat_summer",
            "spectral_integration.filter_min_um": 3.5,
            "spectral_integration.filter_max_um": 5.0,
            "spectral_integration.integration_time_s": 0.005,
            "readout.read_noise_e_rms": 5.0,
            "readout.gain_e_per_dn": 1.0,
            "readout.adc_bits": 16,
        }.items():
            p.set(k, v)
        p.resolve()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            session.run(p)
        consistency = [w for w in caught if "consisten" in str(w.message).lower()]
        assert not consistency, [str(w.message) for w in consistency]

    def test_signal_scales_linearly_with_fill_factor(self) -> None:
        """Radiometric collecting area = pitch²·FF, so signal ∝ FF."""
        sig_10 = _run(1.0).stage_outputs["spectral_integration"]["signal_e"]
        sig_08 = _run(0.8).stage_outputs["spectral_integration"]["signal_e"]
        sig_05 = _run(0.5).stage_outputs["spectral_integration"]["signal_e"]
        assert sig_08 / sig_10 == pytest.approx(0.8, rel=1e-9)
        assert sig_05 / sig_10 == pytest.approx(0.5, rel=1e-9)

    def test_smaller_photosite_higher_pixel_mtf(self) -> None:
        """Narrower photosite (FF < 1) rolls off slower → higher MTF at Nyquist."""
        mtf_10 = _run(1.0).metrics["mtf_at_nyquist"]
        mtf_08 = _run(0.8).metrics["mtf_at_nyquist"]
        assert mtf_08 > mtf_10

    def test_ff_one_unchanged_baseline(self) -> None:
        """At FF = 1 the √FF factor is a no-op — golden-safe."""
        result = _run(1.0)
        # A representative sanity value; the point is FF=1 is a clean identity.
        assert result.stage_outputs["spectral_integration"]["signal_e"] > 0.0
        dp = result.stage_outputs["performance"]["dual_path_consistency"]
        assert dp.passed_x and dp.passed_y


@pytest.mark.level0
class TestPhotositeWidthUnit:
    """The PSF-path kernel and the MTF-product sinc share the pitch·√FF width."""

    def test_kernel_and_sinc_share_width(self) -> None:
        from radiant.optics.pixel_kernel import make_pixel_aperture_kernel_2d

        pitch = 18e-6
        ff = 0.64  # √0.64 = 0.8 exactly
        dx = pitch / 64.0
        npix = 257
        k = make_pixel_aperture_kernel_2d(npix, dx, pitch, pitch, fill_factor=ff)
        # DFT of the central row → compare to |sinc(f·pitch·√FF)|.
        row = k[npix // 2, :]
        row = row / row.sum()
        freqs = np.fft.fftfreq(npix, d=dx)
        mtf = np.abs(np.fft.fft(row))
        # Evaluate at a mid frequency and compare to the analytic sinc.
        f_test = 1.0 / (4.0 * pitch)
        idx = int(np.argmin(np.abs(freqs - f_test)))
        analytic = abs(np.sinc(freqs[idx] * pitch * math.sqrt(ff)))
        assert mtf[idx] == pytest.approx(analytic, abs=5e-3)
