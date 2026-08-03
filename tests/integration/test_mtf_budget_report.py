"""Integration: Gap 19 — MTF budget reporting layer.

Phase-0 re-audit showed the decomposition itself already exists
(MTFBudgetResult with per-contributor MTF-at-Nyquist and dominant
contributor); this covers the added reporting: table() and
result.plot.mtf_budget().
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.session import RadiantSession


@pytest.fixture(scope="module")
def result():
    wl = np.linspace(3.5, 5.0, 300)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
    p.set("platform.jitter_rms_urad", 2.0)
    p.set("detector.pixel_pitch_x_um", 18.0)
    p.set("detector.pixel_pitch_y_um", 18.0)
    p.set("detector.qe_value", 0.70)
    p.set("detector.dark_rate_e_per_s", 100.0)
    p.set("geometry.sensor_altitude_m", 8000.0)
    p.set("atmosphere.standard_atmosphere", "midlat_summer")
    p.set("spectral_integration.filter_min_um", 3.5)
    p.set("spectral_integration.filter_max_um", 5.0)
    p.set("spectral_integration.integration_time_s", 0.005)
    p.set("readout.read_noise_e_rms", 5.0)
    p.set("readout.gain_e_per_dn", 32.0)
    p.set("readout.adc_bits", 16)
    p.resolve()
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return session.run(p)


@pytest.mark.level2
class TestMtfBudgetReport:
    def test_table_lists_contributors_and_system(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        text = budget.table()
        assert "mtf_optics" in text
        assert "mtf_pixel_aperture" in text
        assert "mtf_jitter" in text
        assert "system (product)" in text
        assert "dominant:" in text

    def test_table_values_match_result_fields(self, result) -> None:
        budget = result.stage_outputs["performance"]["mtf_budget"]
        text = budget.table()
        assert f"{budget.system_mtf_at_nyquist_x:.4f}" in text
        assert budget.dominant_contributor_at_nyquist_x in text

    def test_plot_namespace_accessor(self, result) -> None:
        pytest.importorskip("matplotlib")
        import matplotlib

        matplotlib.use("Agg")
        from radiant.api.inspect import ResultPlotNamespace

        fig = ResultPlotNamespace(result).mtf_budget()
        assert fig is not None
        assert fig.axes[0].get_title(loc="left") == "MTF budget at Nyquist"
