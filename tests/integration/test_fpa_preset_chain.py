"""Full-chain integration + goldens for FPA preset application (Gap 119 Phase 2).

Two ratified exit criteria (plan §5):

- a counting-class preset drives the Gap 117 digital-counting chain end to
  end (``dfpa-generic`` — the MIT LL DFPA paper anchor; research showed
  GeoSnap is CTIA + column ADC, i.e. ``analog_well``, so the DFPA part is the
  counting exemplar), and
- a scientific part runs through the ``fpa:`` config key with pinned metrics.

Golden values captured 2026-09-06 on the tranche-1 presets; a change here
means either the preset data or the chain physics moved — both are
results-affecting and must be deliberate (CHANGELOG Rule 29a).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml

from radiant.api.sensor import Sensor

_EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"


def _evaluate(s: Sensor):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NIIRS extrapolation warning, unrelated
        return s.evaluate()


def _example_dict() -> dict[str, Any]:
    return yaml.safe_load(_EXAMPLE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.mark.level2
class TestDfpaCountingChain:
    """dfpa-generic preset → digital-counting branch, over the MWIR example."""

    def _sensor(self) -> Sensor:
        s = Sensor.from_yaml(_EXAMPLE)
        # The example pins an analog FWC; the counting branch (by design)
        # rejects an explicit FWC, deriving capacity from counter x packet.
        s.reset("readout.full_well_capacity_e")
        s.apply_fpa("dfpa-generic")
        return s

    def test_counting_outputs_and_golden_snr(self) -> None:
        r = _evaluate(self._sensor())
        ro = r.stage_outputs["readout"]
        assert ro["architecture"] == "digital_counting"
        assert ro["saturation_mechanism"] == "none"
        # 2^16 counter x 3500 e-/count (llj2014 nominal LSB)
        assert ro["effective_well_e"] == pytest.approx(2**16 * 3500.0, rel=1e-12)
        names = set(ro["scaled_noise_terms"])
        assert "counting_quantization" in names
        assert "packet_reset" in names
        # Golden (2026-09-06): example scene + dfpa-generic preset.
        assert r.metrics["snr"] == pytest.approx(835.99771, rel=1e-5)

    def test_preset_respects_example_pixel_pitch(self) -> None:
        # The example pins 18 um pitch; the preset's 20 um must not displace it.
        s = self._sensor()
        report = s.fpa_applications[0]
        assert "detector.pixel_pitch_x_um" in report.skipped_existing
        s._params.resolve()
        # canonical units: metres
        assert s._params.get("detector.pixel_pitch_x_um") == pytest.approx(18.0e-6, rel=1e-12)


@pytest.mark.level2
class TestH2rgConfigKeyChain:
    """teledyne-h2rg-2p5 via the fpa: config key, SWIR band, full chain."""

    def _sensor(self) -> Sensor:
        data = _example_dict()
        # Let the preset own the detector/readout namespaces entirely.
        data.pop("detector", None)
        data.pop("readout", None)
        data["spectral_integration"].update({"filter_min_um": 1.5, "filter_max_um": 2.4})
        data["fpa"] = "teledyne-h2rg-2p5"
        return Sensor.from_dict(data)

    def test_preset_supplies_detector_and_readout(self) -> None:
        s = self._sensor()
        report = s.fpa_applications[0]
        assert report.skipped_existing == ()
        assert "readout.full_well_capacity_e" in report.applied
        s._params.resolve()
        assert s._params.get("readout.full_well_capacity_e") == pytest.approx(8.0e4, rel=1e-12)
        assert s._params.get("detector.dark_rate_e_per_s") == pytest.approx(0.05, rel=1e-12)

    def test_golden_snr(self) -> None:
        r = _evaluate(self._sensor())
        ro = r.stage_outputs["readout"]
        assert ro["architecture"] == "analog_well"
        # Golden (2026-09-06): 300 K extended scene, 1.5-2.4 um, H2RG preset.
        assert r.metrics["snr"] == pytest.approx(92.94717, rel=1e-5)
