"""Integration test: load YAML config and run the full chain.

Loads ``examples/mwir_leo_minimal.yaml``, runs the chain, and verifies
that the result matches the reference case from
``tests/integration/test_chain_extended.py``.

This test serves as a golden regression anchor for the YAML I/O path.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.io.config import load_config

YAML_PATH = Path(__file__).parents[2] / "examples" / "mwir_leo_minimal.yaml"

# Golden values from the reference case (test_chain_extended.py constants).
D = 0.30
F = 1.20
A_COLLECT = math.pi / 4.0 * D**2
OMEGA_PIXEL = (18e-6) ** 2 / F**2
T_INT = 0.005
QE = 0.70
DARK_RATE = 100.0
READ_NOISE = 5.0
GAIN = 1.0
FILTER_MIN = 3.5
FILTER_MAX = 5.0


@pytest.fixture()
def result():
    """Load YAML config, run the chain, return ChainResult."""
    wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(YAML_PATH, params)
    params.resolve()
    return session.run(params)


@pytest.mark.level2
class TestMWIRLeoMinimal:
    """Validate YAML-driven chain matches reference case."""

    def test_history_complete(self, result) -> None:
        assert result.history == (
            "source", "atmosphere", "optics", "platform",
            "spectral_integration", "detector", "readout",
            "performance",
        )

    def test_frames_present(self, result) -> None:
        # Stage 4 Option C: at_target is removed; at_aperture_target
        # replaces it.  (at_aperture_background may also be present when
        # the background descriptor is non-None.)
        expected = {
            "at_aperture_target",
            "at_aperture",
            "post_optics",
            "photoelectrons",
        }
        assert expected <= set(result.frames.keys())

    def test_A_collect(self, result) -> None:
        assert result.stage_outputs["optics"]["A_collect"] == pytest.approx(
            A_COLLECT, rel=1e-6
        )

    def test_Omega_pixel(self, result) -> None:
        assert result.stage_outputs["optics"]["Omega_pixel"] == pytest.approx(
            OMEGA_PIXEL, rel=1e-6
        )

    def test_photoelectrons_positive(self, result) -> None:
        pe = result.frames["photoelectrons"].in_band_value
        assert pe is not None and pe > 0.0

    def test_snr_positive_finite(self, result) -> None:
        snr = result.metrics["snr"]
        assert snr > 0.0
        assert math.isfinite(snr)

    def test_snr_formula_consistency(self, result) -> None:
        """SNR = signal_e_final / RSS(noise) — cross-check."""
        signal_e = result.stage_outputs["readout"]["signal_e_final"]
        noise_sq = sum(n.value_e**2 for n in result.noise_terms)
        expected_snr = signal_e / math.sqrt(noise_sq)
        assert result.metrics["snr"] == pytest.approx(expected_snr, rel=1e-10)

    def test_noise_terms_present(self, result) -> None:
        names = {n.name for n in result.noise_terms}
        # 16-term noise budget: all terms present (many may be zero)
        assert {"signal_shot", "dark_shot", "read_noise", "quantization"}.issubset(names)
        assert len(names) == 16

    def test_shot_noise_formula(self, result) -> None:
        # Shot noise is √(signal_e_final) — capped at well capacity
        # when the accumulated signal exceeds FWC.
        signal_e_final = result.stage_outputs["readout"]["signal_e_final"]
        shot = [n for n in result.noise_terms if n.name == "signal_shot"][0]
        assert shot.value_e == pytest.approx(math.sqrt(signal_e_final), rel=1e-10)

    def test_determinism(self, result) -> None:
        """Run again with same config — values must be identical."""
        wl = np.linspace(FILTER_MIN, FILTER_MAX, 500)
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        load_config(YAML_PATH, params)
        params.resolve()
        r2 = session.run(params)

        assert result.metrics["snr"] == r2.metrics["snr"]
        assert result.frames["photoelectrons"].in_band_value == (
            r2.frames["photoelectrons"].in_band_value
        )
