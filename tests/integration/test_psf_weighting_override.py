"""Integration: Gap 17 — arbitrary source spectrum for PSF weighting.

Injecting optics_config["psf_weighting_spectrum"] must change the
polychromatic PSF weighting without touching the radiometric chain
(SNR, signal identical), and the weighting source must be recorded.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.spectral import SpectralData

FILTER_MIN = 3.5
FILTER_MAX = 5.0


def _spectrum(kind: str) -> SpectralData:
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 100)
    if kind == "blue":  # weight the short-wavelength edge
        vals = np.exp(-((wl - FILTER_MIN) / 0.3) ** 2)
    else:  # red: weight the long-wavelength edge
        vals = np.exp(-((wl - FILTER_MAX) / 0.3) ** 2)
    return SpectralData(
        name=f"{kind}_override",
        wavelength_um=wl,
        values=vals + 1e-9,
        unit="W/m^2/sr/um",
        source="test override",
    )


def _run(override: SpectralData | None):
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 300)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("optics.psf_n_wavelengths", 5)
    p.set("detector.pixel_pitch_x_um", 18.0)
    p.set("detector.pixel_pitch_y_um", 18.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", 8000.0)
    p.set("atmosphere.standard_atmosphere", "midlat_summer")
    p.set("spectral_integration.filter_min_um", FILTER_MIN)
    p.set("spectral_integration.filter_max_um", FILTER_MAX)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 32.0)
    p.set("readout.adc_bits", 16)
    p.resolve()
    extra = (
        {"optics_config": {"psf_weighting_spectrum": override}} if override is not None else None
    )
    return session.run(p, extra_stage_outputs=extra)


@pytest.fixture(scope="module")
def scene():
    return _run(None)


@pytest.fixture(scope="module")
def blue():
    return _run(_spectrum("blue"))


@pytest.fixture(scope="module")
def red():
    return _run(_spectrum("red"))


@pytest.mark.level2
class TestPsfWeightingOverride:
    def test_weighting_source_recorded(self, scene, blue) -> None:
        assert scene.stage_outputs["optics"]["psf_weighting_source"] == "post_optics"
        assert blue.stage_outputs["optics"]["psf_weighting_source"] == "override:blue_override"

    def test_override_shifts_effective_wavelength(self, blue, red) -> None:
        """Blue-weighted ePSF must sit at shorter effective λ than red."""
        wl_blue = blue.stage_outputs["optics"]["effective_psf"].wavelength_um
        wl_red = red.stage_outputs["optics"]["effective_psf"].wavelength_um
        assert wl_blue < wl_red

    def test_override_changes_psf_width(self, blue, red) -> None:
        """Diffraction scales with λ: red-weighted PSF is wider."""
        fwhm_blue = blue.metrics["fwhm_x_m"]
        fwhm_red = red.metrics["fwhm_x_m"]
        assert fwhm_red > fwhm_blue

    def test_radiometry_untouched(self, scene, blue) -> None:
        """PSF weighting must never change the radiometric signal path."""
        s0 = scene.stage_outputs["spectral_integration"]["signal_e"]
        s1 = blue.stage_outputs["spectral_integration"]["signal_e"]
        assert s1 == pytest.approx(s0, rel=1e-12)

    def test_disjoint_override_grid_raises(self) -> None:
        wl = np.linspace(8.0, 12.0, 20)  # LWIR grid vs MWIR band
        bad = SpectralData(
            name="disjoint",
            wavelength_um=wl,
            values=np.ones_like(wl),
            unit="W/m^2/sr/um",
            source="test",
        )
        with pytest.raises(ValueError, match="does not overlap"):
            _run(bad)
