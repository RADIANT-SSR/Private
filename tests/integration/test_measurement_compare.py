"""Integration: Gap 30 — measured-MTF comparison against a real chain run.

Runs one small MWIR chain (module-scoped, config mirrors
test_electronics_mtf_chain.py) and compares synthetic "measured" curves
built from the predicted curve plus a known offset, so every expected
statistic is hand-derivable (Rule 18): residual == offset exactly at
grid points because np.interp is exact there.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.compare import MtfComparisonError, compare_mtf
from radiant.api.session import RadiantSession
from radiant.core.chain import ChainState
from radiant.io.measurement import MeasuredCurve
from radiant.io.results import ChainResult

OFFSET = 0.02  # known measured-minus-predicted offset [dimensionless MTF]


def _run() -> ChainResult:
    wl = np.linspace(3.5, 5.0, 300)
    session = RadiantSession(wavelength_um=wl)
    p = session.default_params()
    p.set("source.target.temperature", 300.0)
    p.set("source.target.emissivity", 0.95)
    p.set("source.target.is_hot_target", True)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 1.20)
    p.set("optics.transmission_scalar", 0.70)
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
    return session.run(p)


@pytest.fixture(scope="module")
def result() -> ChainResult:
    return _run()


def _synthetic_measured(
    result: ChainResult,
    axis: str,
    offset: float,
    n_outside: int = 0,
) -> MeasuredCurve:
    """Measured curve = predicted MTF at a subset of grid points + offset.

    Optionally appends *n_outside* points beyond the predicted grid max
    (exclusion-path exercise).
    """
    perf = result.stage_outputs["performance"]
    freq = np.asarray(perf[f"mtf_freq_{axis}"], dtype=np.float64)
    mtf = np.asarray(perf[f"mtf_{axis}"], dtype=np.float64)
    idx = np.arange(1, freq.size - 1, 7)  # interior subset of grid points
    x = freq[idx]
    y = mtf[idx] + offset
    if n_outside:
        step = freq[-1] - freq[-2]
        extra = freq[-1] + step * np.arange(1, n_outside + 1)
        x = np.concatenate([x, extra])
        y = np.concatenate([y, np.full(n_outside, offset)])
    return MeasuredCurve(
        x=x,
        y=y,
        source_file="synthetic",
        x_unit="cy/m",
        n_points=int(x.size),
    )


@pytest.mark.level2
class TestCompareMtf:
    def test_known_offset_recovered(self, result: ChainResult) -> None:
        measured = _synthetic_measured(result, "x", OFFSET)
        cmp = compare_mtf(result, measured, axis="x", frequency_unit="cy/m")
        assert cmp.n_excluded == 0
        assert cmp.n_compared == measured.n_points
        # interp at exact grid points is exact -> residual == OFFSET everywhere
        assert cmp.rms_residual == pytest.approx(OFFSET, rel=1e-9)
        assert cmp.max_abs_residual == pytest.approx(OFFSET, rel=1e-9)
        np.testing.assert_allclose(cmp.residual, OFFSET, rtol=1e-9)

    def test_negative_offset_sign_convention(self, result: ChainResult) -> None:
        """residual = measured - predicted, so offset sign survives."""
        measured = _synthetic_measured(result, "x", -OFFSET)
        cmp = compare_mtf(result, measured, axis="x", frequency_unit="cy/m")
        np.testing.assert_allclose(cmp.residual, -OFFSET, rtol=1e-9)
        assert cmp.rms_residual == pytest.approx(OFFSET, rel=1e-9)

    def test_out_of_range_points_excluded(self, result: ChainResult) -> None:
        measured = _synthetic_measured(result, "x", OFFSET, n_outside=3)
        cmp = compare_mtf(result, measured, axis="x", frequency_unit="cy/m")
        assert cmp.n_excluded == 3
        assert cmp.n_compared == measured.n_points - 3
        assert cmp.rms_residual == pytest.approx(OFFSET, rel=1e-9)
        assert cmp.freq_cy_m.size == cmp.n_compared
        assert cmp.residual.size == cmp.n_compared

    def test_cy_per_mm_unit_conversion_matches(self, result: ChainResult) -> None:
        measured_m = _synthetic_measured(result, "x", OFFSET)
        measured_mm = MeasuredCurve(
            x=measured_m.x * 1e-3,  # cy/m -> cy/mm
            y=measured_m.y,
            source_file="synthetic",
            x_unit="cy/mm",
            n_points=measured_m.n_points,
        )
        cmp_m = compare_mtf(result, measured_m, frequency_unit="cy/m")
        cmp_mm = compare_mtf(result, measured_mm, frequency_unit="cy/mm")
        assert cmp_mm.n_compared == cmp_m.n_compared
        np.testing.assert_allclose(cmp_mm.freq_cy_m, cmp_m.freq_cy_m, rtol=1e-12)
        np.testing.assert_allclose(cmp_mm.residual, cmp_m.residual, rtol=1e-9)
        assert cmp_mm.rms_residual == pytest.approx(cmp_m.rms_residual, rel=1e-9)

    def test_y_axis_path(self, result: ChainResult) -> None:
        measured = _synthetic_measured(result, "y", OFFSET)
        cmp = compare_mtf(result, measured, axis="y", frequency_unit="cy/m")
        assert cmp.rms_residual == pytest.approx(OFFSET, rel=1e-9)

    def test_table_contains_statistics(self, result: ChainResult) -> None:
        measured = _synthetic_measured(result, "x", OFFSET, n_outside=2)
        cmp = compare_mtf(result, measured, axis="x", frequency_unit="cy/m")
        text = cmp.table()
        assert "RMS residual" in text
        assert "cy/m" in text
        assert f"points excluded : {cmp.n_excluded}" in text
        assert f"points compared : {cmp.n_compared}" in text


@pytest.mark.level2
class TestCompareMtfErrors:
    def test_invalid_axis(self, result: ChainResult) -> None:
        measured = _synthetic_measured(result, "x", OFFSET)
        with pytest.raises(MtfComparisonError, match="axis"):
            compare_mtf(result, measured, axis="z")

    def test_no_overlap(self, result: ChainResult) -> None:
        perf = result.stage_outputs["performance"]
        fmax = float(np.max(np.asarray(perf["mtf_freq_x"])))
        measured = MeasuredCurve(
            x=np.array([fmax * 10.0, fmax * 20.0]),
            y=np.array([0.1, 0.05]),
            source_file="synthetic",
            x_unit="cy/m",
            n_points=2,
        )
        with pytest.raises(MtfComparisonError, match="no overlap"):
            compare_mtf(result, measured, frequency_unit="cy/m")

    def test_missing_performance_outputs(self) -> None:
        bare = ChainResult(ChainState(wavelength_um=np.linspace(3.5, 5.0, 10)))
        measured = MeasuredCurve(
            x=np.array([1.0e4, 2.0e4]),
            y=np.array([0.9, 0.8]),
            source_file="synthetic",
            x_unit="cy/m",
            n_points=2,
        )
        with pytest.raises(MtfComparisonError, match="performance"):
            compare_mtf(bare, measured)

    def test_cy_mrad_requires_focal_length(self, result: ChainResult) -> None:
        from radiant.performance.frequency_units import FrequencyUnitError

        measured = _synthetic_measured(result, "x", OFFSET)
        with pytest.raises(FrequencyUnitError, match="focal_length_m"):
            compare_mtf(result, measured, frequency_unit="cy/mrad")
