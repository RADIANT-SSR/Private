"""Integration: Gap 54 — arbitrary pupil-mask injection end-to-end.

Injecting optics_config["pupil_mask_override"] must flow through the PSF
and MTF paths (Rule 4). A mask matching the parametric circular aperture
reproduces the default spatial metrics; a smaller custom aperture changes
them. No injection ⇒ results unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.optics.pupil_amplitude import make_pupil_amplitude


def _run(mask: np.ndarray | None):
    wl = np.linspace(0.45, 0.70, 120)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("detector.pixel_pitch_x_um", 8.0)
    p.set("detector.pixel_pitch_y_um", 8.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", 500000.0)
    p.set("spectral_integration.filter_min_um", 0.45)
    p.set("spectral_integration.filter_max_um", 0.70)
    p.set("spectral_integration.integration_time_s", 0.001)
    p.set("readout.read_noise_e_rms", 20.0)
    p.set("readout.gain_e_per_dn", 5.0)
    p.set("readout.adc_bits", 12)
    p.resolve()
    extra = {"optics_config": {"pupil_mask_override": mask}} if mask is not None else None
    return session.run(p, extra_stage_outputs=extra)


@pytest.mark.level2
class TestPupilMaskOverride:
    def test_matching_mask_reproduces_default(self) -> None:
        """A mask equal to the parametric circular pupil ⇒ same EE."""
        circular = make_pupil_amplitude(128, 0.0)
        base = _run(None)
        injected = _run(circular)
        assert injected.metrics["ee_3x3"] == pytest.approx(base.metrics["ee_3x3"], rel=1e-9)

    def test_smaller_aperture_lowers_ee(self) -> None:
        """A custom mask filling only the central half is a smaller
        effective aperture ⇒ wider PSF ⇒ lower 3×3 encircled energy."""
        small = make_pupil_amplitude(128, 0.0)
        # Zero everything outside a central disk of half the radius.
        n = small.shape[0]
        y, x = np.ogrid[:n, :n]
        r = np.hypot(x - n / 2 + 0.5, y - n / 2 + 0.5) / (n / 2)
        small = np.where(r <= 0.5, small, 0.0)
        base = _run(None)
        injected = _run(small)
        assert injected.metrics["ee_3x3"] < base.metrics["ee_3x3"]
