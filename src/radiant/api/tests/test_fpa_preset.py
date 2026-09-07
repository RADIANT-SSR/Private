"""Apply semantics for named FPA presets (Gap 119, plan §3.4 / Phase 2).

Contract under test: presets seed, explicit values win — regardless of entry
order — and the override report says exactly what happened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.api.fpa_preset import FPAApplyReport, apply_fpa_preset
from radiant.api.sensor import Sensor
from radiant.api.session import RadiantSession
from radiant.core.parameters import Provenance
from radiant.data.fpa import FPAPresetError
from radiant.io.config import ConfigError, load_config

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


class TestApplyFpaPreset:
    def test_applies_with_preset_provenance(self) -> None:
        params = RadiantSession.default_params()
        report = apply_fpa_preset(params, "geosnap-18")
        assert isinstance(report, FPAApplyReport)
        assert "detector.pixel_pitch_x_um" in report.applied
        assert report.skipped_existing == ()
        provs = params.input_provenances()
        assert provs["detector.pixel_pitch_x_um"] is Provenance.PRESET
        assert provs["readout.full_well_capacity_e"] is Provenance.PRESET

    def test_unknown_part_raises_actionable(self) -> None:
        params = RadiantSession.default_params()
        with pytest.raises(FPAPresetError, match="geosnap-18"):
            apply_fpa_preset(params, "no-such-part")


class TestSensorSurface:
    def test_explicit_config_values_win_and_are_reported(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        report = s.apply_fpa("geosnap-18")
        # The example pins these — the preset must not displace them.
        for kept in (
            "detector.pixel_pitch_x_um",
            "detector.qe_value",
            "readout.read_noise_e_rms",
            "readout.full_well_capacity_e",
            "readout.adc_bits",
        ):
            assert kept in report.skipped_existing
        # Values the example does not pin do apply.
        assert "detector.detector_temperature_K" in report.applied
        s._params.resolve()
        assert s._params.get("readout.read_noise_e_rms") == pytest.approx(5.0, rel=1e-12)
        assert s._params.get("detector.detector_temperature_K") == pytest.approx(110.0, rel=1e-12)
        rv = s._params.get_resolved("detector.detector_temperature_K")
        assert rv.provenance is Provenance.PRESET
        assert rv.source.startswith("fpa:geosnap-18/")

    def test_set_after_apply_overrides(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.apply_fpa("teledyne-h2rg-2p5")
        s.set("detector.detector_temperature_K", 40.0)
        s._params.resolve()
        assert s._params.get("detector.detector_temperature_K") == pytest.approx(40.0, rel=1e-12)

    def test_report_accumulation(self) -> None:
        s = Sensor()
        r1 = s.apply_fpa("teledyne-h2rg-2p5")
        assert "readout.full_well_capacity_e" in r1.applied
        assert s.fpa_applications == (r1,)

    def test_fpa_config_key_config_wins(self, tmp_path: Path) -> None:
        cfg = tmp_path / "with_fpa.yaml"
        cfg.write_text(
            _EXAMPLE.read_text(encoding="utf-8") + "\nfpa: geosnap-18\n", encoding="utf-8"
        )
        s = Sensor.from_yaml(cfg)
        report = s.fpa_applications[0]
        assert report.part == "geosnap-18"
        assert "readout.read_noise_e_rms" in report.skipped_existing
        assert "detector.detector_temperature_K" in report.applied
        s._params.resolve()
        assert s._params.get("readout.read_noise_e_rms") == pytest.approx(5.0, rel=1e-12)

    def test_bare_load_config_refuses_fpa_key(self) -> None:
        params = RadiantSession.default_params()
        with pytest.raises(ConfigError, match="fpa"):
            load_config({"fpa": "teledyne-h2rg-2p5"}, params)


class TestRemoveAndSwitch:
    def test_remove_clears_preset_keeps_explicit(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.apply_fpa("teledyne-h2rg-2p5")
        s.set("detector.detector_temperature_K", 40.0)  # post-apply override
        cleared = s.remove_fpa()
        assert cleared and all(p.startswith(("detector.", "readout.")) for p in cleared)
        assert "detector.detector_temperature_K" not in cleared  # override kept
        assert s.fpa_applications == ()
        provs = s._params.input_provenances()
        assert not any(p is Provenance.PRESET for p in provs.values())
        s._params.resolve()
        assert s._params.get("detector.detector_temperature_K") == pytest.approx(40.0, rel=1e-12)
        # Preset-seeded dark reverted to its schema default (0.05 -> 100 e-/s).
        assert s._params.get("detector.dark_rate_e_per_s") == pytest.approx(100.0, rel=1e-12)

    def test_remove_without_apply_is_empty(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        assert s.remove_fpa() == ()

    def test_part_switch_leaves_no_residue(self) -> None:
        s = Sensor.from_yaml(_EXAMPLE)
        s.apply_fpa("dfpa-generic")  # sets counter_bits/count_packet_e/architecture...
        report = s.apply_fpa("teledyne-h2rg-2p5")  # does NOT set counting params
        assert s.fpa_applications == (report,)
        provs = s._params.input_provenances()
        # dfpa-generic's counting knobs are gone, not carried into the H2RG state.
        assert "readout.counter_bits" not in provs
        assert "readout.count_packet_e" not in provs
        # And H2RG's values applied where the example config pins nothing
        # (the example's explicit FWC/read-noise pins correctly stay "kept").
        assert "detector.dark_reference_temperature_K" in report.applied
        assert "readout.full_well_capacity_e" in report.skipped_existing
