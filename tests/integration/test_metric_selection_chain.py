"""Integration: full-chain metric selection and dependency closure (Gap 96).

Drives the real signal chain (``examples/mwir_leo_minimal.yaml``) with metric
groups toggled off and asserts the Gap-96 contract end-to-end:

* default (all groups on) surfaces every metric the chain can compute
  (regression: the selection is additive);
* enabling only Interpretability surfaces niirs but NOT its prerequisites
  (snr/rer/gsd), which are still computed — so niirs equals its all-on value;
* disabling a group removes exactly its metrics and leaves the others'
  values bit-identical.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.io.config import load_config
from radiant.performance.metric_selection import GROUP_PARAMS, METRIC_GROUPS

YAML_PATH = Path(__file__).parents[2] / "examples" / "mwir_leo_minimal.yaml"
_GROUPS = tuple(GROUP_PARAMS)


def _run(overrides: dict[str, object] | None = None):
    wl = np.linspace(3.5, 5.0, 200)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(YAML_PATH, params)
    # These tests exercise Gap 96 group *selection*; the example config is
    # outside the GIQE-5 envelope (SNR ~978), so opt into extrapolated NIIRS
    # (CU-166 gate) to keep `niirs` in the computed set the assertions cover.
    params.set("performance.niirs.allow_extrapolated", True)
    for key, value in (overrides or {}).items():
        params.set(key, value)
    params.resolve()
    return session.run(params)


def _only(group: str) -> dict[str, object]:
    """Overrides enabling exactly *group*, all other groups off."""
    return {GROUP_PARAMS[g]: (g == group) for g in _GROUPS}


def _without(group: str) -> dict[str, object]:
    """Overrides with every group on except *group*."""
    return {GROUP_PARAMS[group]: False}


@pytest.fixture(scope="module")
def default_result():
    return _run()


@pytest.mark.level2
class TestMetricSelectionChain:
    def test_default_surfaces_full_metric_set(self, default_result) -> None:
        """All-on default: every registered metric the chain can compute is
        surfaced (the change is additive — Gap 96 default)."""
        keys = set(default_result.metrics)
        # Core metrics from every group are present for this LEO scenario.
        for present in ("snr", "rer", "niirs", "gsd_along_track_m", "well_margin_dB"):
            assert present in keys

    def test_interpretability_only_hides_prereqs(self, default_result) -> None:
        """Enable only Interpretability → niirs surfaced, snr/rer/gsd computed
        (closure) but NOT surfaced, and niirs equals its all-on value."""
        result = _run(_only("interpretability"))
        keys = set(result.metrics)

        assert keys == set(METRIC_GROUPS["interpretability"]) & set(default_result.metrics)
        assert "niirs" in keys
        # Prerequisites are hidden...
        for hidden in ("snr", "rer", "gsd_along_track_m", "gsd_cross_track_m"):
            assert hidden not in keys
        # ...yet niirs is computed correctly from them (closure ran the deps).
        assert result.metrics["niirs"] == default_result.metrics["niirs"]

    def test_disabling_saturation_drops_only_its_metrics(self, default_result) -> None:
        """Turn off Saturation: its metrics vanish; all others are unchanged."""
        result = _run(_without("saturation"))
        keys = set(result.metrics)

        # Saturation metrics gone.
        assert keys.isdisjoint(METRIC_GROUPS["saturation"])
        # Everything else identical in both presence and value.
        expected = set(default_result.metrics) - METRIC_GROUPS["saturation"]
        assert keys == expected
        for key in expected:
            assert result.metrics[key] == default_result.metrics[key]

    def test_all_groups_off_yields_no_metrics(self) -> None:
        """Deselecting every group computes and surfaces nothing."""
        result = _run({GROUP_PARAMS[g]: False for g in _GROUPS})
        assert set(result.metrics) == set()

    def test_disabling_radiometric_keeps_interpretability(self, default_result) -> None:
        """Radiometric off but Interpretability on: snr is a hidden prereq of
        niirs, so niirs still matches, but snr itself is not surfaced."""
        result = _run(_without("radiometric"))
        keys = set(result.metrics)
        assert "snr" not in keys  # radiometric group off
        assert "niirs" in keys  # interpretability still on
        assert result.metrics["niirs"] == default_result.metrics["niirs"]


@pytest.mark.level2
class TestMetricSelectionPersistence:
    """The metric-group selection is a parameter: it survives save/load."""

    def test_selection_survives_sensor_roundtrip(self, tmp_path) -> None:
        from radiant.api.sensor import Sensor

        s = Sensor.from_yaml(YAML_PATH)
        s.set("performance.metrics.saturation", False)
        s.set("performance.metrics.sampling", False)
        path = s.save(tmp_path / "sensor.yaml")

        reloaded = Sensor.load(path)
        assert reloaded.get("performance.metrics.saturation") is False
        assert reloaded.get("performance.metrics.sampling") is False
        # The reloaded sensor evaluates with the reduced surface.
        r = reloaded.evaluate()
        assert set(r.metrics).isdisjoint(METRIC_GROUPS["saturation"])
        assert set(r.metrics).isdisjoint(METRIC_GROUPS["sampling"])
        assert "snr" in r.metrics  # radiometric still on
