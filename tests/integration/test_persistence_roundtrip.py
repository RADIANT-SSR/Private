"""Full-chain persistence round trips (Gap 67).

Sensor.save/load and ChainResult.save/load against a real evaluated
chain: reloaded objects must reproduce the originals exactly (bitwise
metric equality — the same inputs resolve to the same values; no
tolerance is appropriate here).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api.sensor import Sensor
from radiant.io.results import ChainResult

_EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def sensor() -> Sensor:
    s = Sensor.from_yaml(_EXAMPLE)
    s.set_tolerance("detector.qe_value", "gaussian", std=0.02)
    return s


def _evaluate(s: Sensor) -> ChainResult:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NIIRS extrapolation warning, unrelated
        return s.evaluate()


@pytest.mark.level2
class TestSensorRoundTrip:
    def test_metrics_identical_after_save_load(self, sensor: Sensor, tmp_path: Path) -> None:
        r1 = _evaluate(sensor)
        path = sensor.save(tmp_path / "sensor.yaml")
        r2 = _evaluate(Sensor.load(path))
        assert dict(r1.metrics) == dict(r2.metrics)  # exact — same inputs, same chain

    def test_resolution_state_identical(self, sensor: Sensor, tmp_path: Path) -> None:
        _evaluate(sensor)
        path = sensor.save(tmp_path / "sensor.yaml")
        s2 = Sensor.load(path)
        _evaluate(s2)
        rv1 = sensor._params.all_resolved()
        rv2 = s2._params.all_resolved()
        assert set(rv1) == set(rv2)
        for name in rv1:
            assert rv1[name].value == rv2[name].value, name
            # Defaulted/derived parameters keep their provenance class;
            # explicit inputs become config_file on reload (by design).
            if rv1[name].provenance.value in ("default", "derived"):
                assert rv2[name].provenance.value == rv1[name].provenance.value, name

    def test_tolerances_survive(self, sensor: Sensor, tmp_path: Path) -> None:
        path = sensor.save(tmp_path / "sensor.yaml")
        s2 = Sensor.load(path)
        tols = s2._params.tolerances()
        assert tols["detector.qe_value"].distribution == "gaussian"
        assert tols["detector.qe_value"].params == {"std": 0.02}

    def test_wavelength_points_survive(self, tmp_path: Path) -> None:
        s = Sensor.from_yaml(_EXAMPLE, wavelength_points=137)
        path = s.save(tmp_path / "sensor.yaml")
        assert Sensor.load(path)._wl_points == 137

    def test_saved_file_loads_via_from_yaml(self, sensor: Sensor, tmp_path: Path) -> None:
        """The saved file is a normal config — _radiant block tolerated."""
        path = sensor.save(tmp_path / "sensor.yaml")
        r = _evaluate(Sensor.from_yaml(path))
        assert "snr" in r.metrics


@pytest.mark.level2
class TestChainResultRoundTrip:
    def test_full_state_round_trip(self, sensor: Sensor, tmp_path: Path) -> None:
        r1 = _evaluate(sensor)
        path = r1.save(tmp_path / "run.radiant")
        r2 = ChainResult.load(path)

        assert dict(r1.metrics) == dict(r2.metrics)
        assert r1.history == r2.history
        assert r1.noise_terms == r2.noise_terms
        assert set(r1.frames) == set(r2.frames)
        for name in r1.frames:
            f1, f2 = r1.frames[name], r2.frames[name]
            np.testing.assert_array_equal(f1.wavelength_um, f2.wavelength_um)
            for attr in ("spectral_radiance", "spectral_irradiance", "photon_rate"):
                a1, a2 = getattr(f1, attr), getattr(f2, attr)
                assert (a1 is None) == (a2 is None)
                if a1 is not None:
                    np.testing.assert_array_equal(a1, a2)
            assert f1.in_band_value == f2.in_band_value
        assert set(r1.state.mtf_terms) == set(r2.state.mtf_terms)
        for term in r1.state.mtf_terms:
            np.testing.assert_array_equal(r1.state.mtf_terms[term], r2.state.mtf_terms[term])

    def test_no_values_skipped_for_shipped_chain(self, sensor: Sensor, tmp_path: Path) -> None:
        """Every stage output of the shipped chain must be archivable."""
        r1 = _evaluate(sensor)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)  # a skip-warning fails the test
            r1.save(tmp_path / "run.radiant")

    def test_backward_queries_work_after_reload(self, sensor: Sensor, tmp_path: Path) -> None:
        r1 = _evaluate(sensor)
        path = r1.save(tmp_path / "run.radiant")
        r2 = ChainResult.load(path)
        assert r2.signal_at("at_aperture").value == r1.signal_at("at_aperture").value
        assert r2.noise_at("photoelectrons").value == r1.noise_at("photoelectrons").value

    def test_provenance_frozen_at_save_time(self, sensor: Sensor, tmp_path: Path) -> None:
        r1 = _evaluate(sensor)
        prov1 = r1.to_provenance_record()
        path = r1.save(tmp_path / "run.radiant")
        prov2 = ChainResult.load(path).to_provenance_record()
        # The reloaded record describes the original run (run_id, versions,
        # parameters), not the loading environment.
        assert prov2["run_id"] == prov1["run_id"]
        assert prov2["parameter_set"] == prov1["parameter_set"]
        assert prov2["active_models"] == prov1["active_models"]
