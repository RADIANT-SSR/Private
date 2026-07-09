"""Integration: Gap 44 — spectral QE via detector.qe_table_path.

Setting detector.qe_table_path must load the wavelength-vs-QE curve and
apply it spectrally (superseding the scalar detector.qe_value). A flat
curve equal to the scalar reproduces the scalar result; a sloped curve
differs. No path ⇒ scalar behaviour unchanged.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession

BAND_MIN, BAND_MAX = 3.5, 5.0


def _write_qe_csv(path: Path, pairs: list[tuple[float, float]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("wavelength_um,QE_fraction\n")
        for wl, qe in pairs:
            fh.write(f"{wl},{qe}\n")


def _run(qe_path: str | None, qe_value: float = 0.6):
    wl = np.linspace(BAND_MIN, BAND_MAX, 200)
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
    if qe_path is not None:
        p.set("detector.qe_table_path", qe_path)
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
class TestQeTablePath:
    def test_flat_curve_matches_scalar(self, tmp_path: Path) -> None:
        """A flat QE = 0.6 curve reproduces the scalar-0.6 signal."""
        csv = tmp_path / "flat_qe.csv"
        _write_qe_csv(csv, [(3.0, 0.6), (5.5, 0.6)])
        scalar = _run(None, qe_value=0.6)
        curved = _run(str(csv), qe_value=0.6)
        s_scalar = scalar.stage_outputs["spectral_integration"]["signal_e"]
        s_curved = curved.stage_outputs["spectral_integration"]["signal_e"]
        assert s_curved == pytest.approx(s_scalar, rel=1e-6)

    def test_curve_is_used(self, tmp_path: Path) -> None:
        """The injected spectral curve appears in the stage outputs."""
        csv = tmp_path / "sloped_qe.csv"
        _write_qe_csv(csv, [(3.0, 0.3), (5.5, 0.9)])
        res = _run(str(csv))
        qe_curve = res.stage_outputs["spectral_integration"]["qe_curve"]
        assert np.asarray(qe_curve).size > 1
        assert not np.allclose(qe_curve, qe_curve[0])  # genuinely spectral

    def test_sloped_curve_differs_from_scalar(self, tmp_path: Path) -> None:
        csv = tmp_path / "sloped_qe.csv"
        _write_qe_csv(csv, [(3.0, 0.3), (5.5, 0.9)])
        scalar = _run(None, qe_value=0.6)
        curved = _run(str(csv), qe_value=0.6)
        s_scalar = scalar.stage_outputs["spectral_integration"]["signal_e"]
        s_curved = curved.stage_outputs["spectral_integration"]["signal_e"]
        assert s_curved != pytest.approx(s_scalar, rel=1e-3)

    def test_no_path_unchanged(self) -> None:
        """Absent a path, the scalar QE drives the signal (no crash, finite)."""
        res = _run(None, qe_value=0.6)
        assert np.isfinite(res.stage_outputs["spectral_integration"]["signal_e"])
