"""Tests for the Gap 88 serialize/export surfaces (Tier-2 FW-B)."""

from __future__ import annotations

import csv
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api import Sensor

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"


def _sensor() -> Sensor:
    return Sensor.from_yaml(_EXAMPLE)


class TestToYaml:
    def test_inputs_scope_matches_save_bytes(self, tmp_path: Path) -> None:
        s = _sensor()
        text = s.to_yaml(scope="inputs")
        saved = tmp_path / "s.yaml"
        s.save(saved)
        on_disk = saved.read_text(encoding="utf-8")

        # Same body; only the header comment differs (to_yaml vs save).
        def strip(x: str) -> str:
            return "\n".join(ln for ln in x.splitlines() if not ln.startswith("#"))

        assert strip(text) == strip(on_disk)

    def test_resolved_scope_includes_defaults(self) -> None:
        s = _sensor()
        resolved = s.to_yaml(scope="resolved")
        inputs = s.to_yaml(scope="inputs")
        # A pure-default parameter appears only in the resolved export.
        assert "jitter_rms_urad" in resolved
        assert "jitter_rms_urad" not in inputs
        assert len(resolved) > len(inputs)

    def test_round_trips_through_loader(self, tmp_path: Path) -> None:
        s = _sensor()
        s.set_optical_elements(
            [
                {
                    "name": "M1",
                    "transfer_mode": "REFLECTIVE",
                    "reflectance": 0.97,
                    "temperature_K": 293.0,
                    "diameter_m": 0.3,
                    "distance_to_fpa_m": 1.0,
                }
            ]
        )
        text = s.to_yaml()
        p = tmp_path / "rt.yaml"
        p.write_text(text, encoding="utf-8")
        s2 = Sensor.load(p)
        assert s2.optical_elements() is not None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert s2.evaluate().metrics["snr"] == pytest.approx(
                s.evaluate().metrics["snr"], rel=1e-12
            )


class TestResultExports:
    def test_to_records_and_csv(self, tmp_path: Path) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = _sensor().evaluate()
        records = result.to_records()
        assert records and all({"name", "value", "unit", "description"} <= set(r) for r in records)
        out = result.to_csv(tmp_path / "metrics.csv")
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert rows[0] == ["name", "value", "unit", "description"]
        assert len(rows) - 1 == len(records)
        # Values round-trip losslessly through repr.
        by_name = {r[0]: float(r[1]) for r in rows[1:]}
        assert by_name["snr"] == result.metrics["snr"]


class TestSweepAndMcExports:
    def test_sweep_to_csv(self, tmp_path: Path) -> None:
        s = _sensor()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sweep = s.sweep(
                "optics.aperture_diameter_m", np.linspace(0.2, 0.4, 3), keep_results=True
            )
        out = sweep.to_csv(tmp_path / "sweep.csv")
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert rows[0][0] == "optics.aperture_diameter_m"
        assert len(rows) == 4  # header + 3 points
        assert "contrast_snr" in rows[0]  # kept results widen to all metrics

    def test_mc_to_csv(self, tmp_path: Path) -> None:
        s = _sensor().set_tolerance("detector.qe_value", "gaussian", std=0.02)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mc = s.monte_carlo(n_trials=5, seed=1)
        out = mc.to_csv(tmp_path / "mc.csv")
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert rows[0][0] == "trial"
        assert "detector.qe_value" in rows[0]
        assert len(rows) == 6


class TestGuiYamlPath:
    def test_inputs_scope_needs_no_temp_file(self) -> None:
        """Gap 88's contract, asserted where it lives (CU-217).

        The GUI's ``yaml_format.serialize_yaml`` shim used to round-trip through
        a temp file, and this test guarded that it no longer did. The shim became
        a one-line pass-through to ``Sensor.to_yaml`` and was deleted, so the
        contract is asserted directly on the public surface — which also drops an
        api-test → gui-module import that inverted the layering.
        """
        s = _sensor()
        text = s.to_yaml(scope="inputs")
        assert "optics" in text and "_radiant" in text
