"""Golden regression test: MWIR LEO minimal scenario.

Loads the golden values from ``golden/mwir_leo_minimal.json`` and
compares against a fresh chain run. Tolerance is 0.1% (rel=1e-3),
reflecting floating-point reproducibility rather than physics accuracy.

If a golden value changes, do NOT adjust the tolerance. Instead:
1. Identify which code change caused the shift.
2. Verify the new value is physically correct.
3. Run ``scripts/update_golden.py --i-know-what-im-doing`` to update.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.io.config import load_config


GOLDEN_PATH = Path(__file__).parent / "golden" / "mwir_leo_minimal.json"
CONFIG_PATH = Path(__file__).parents[2] / "examples" / "mwir_leo_minimal.yaml"

# Tolerance: 0.1% — floating-point, not physics.
REL_TOL = 1e-3


@pytest.fixture(scope="module")
def golden() -> dict:
    """Load golden values."""
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def result():
    """Run the chain from the YAML config."""
    wl = np.linspace(3.5, 5.0, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(CONFIG_PATH, params)
    params.resolve()
    return session.run(params)


@pytest.mark.golden
class TestGoldenMWIRLeoMinimal:
    """Compare chain output against stored golden values."""

    def test_signal_e(self, result, golden) -> None:
        expected = golden["signal_e"]["value"]
        actual = result.frames["photoelectrons"].in_band_value
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_e_rate_per_s(self, result, golden) -> None:
        expected = golden["e_rate_per_s"]["value"]
        actual = result.stage_outputs["spectral_integration"]["e_rate_per_s"]
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_A_collect(self, result, golden) -> None:
        expected = golden["A_collect"]["value"]
        actual = result.stage_outputs["optics"]["A_collect"]
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_Omega_pixel(self, result, golden) -> None:
        expected = golden["Omega_pixel"]["value"]
        actual = result.stage_outputs["optics"]["Omega_pixel"]
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_noise_shot(self, result, golden) -> None:
        expected = golden["noise_shot"]["value"]
        actual = [n for n in result.noise_terms if n.name == "shot"][0].value_e
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_noise_dark_shot(self, result, golden) -> None:
        expected = golden["noise_dark_shot"]["value"]
        actual = [n for n in result.noise_terms if n.name == "dark_shot"][0].value_e
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_noise_read(self, result, golden) -> None:
        expected = golden["noise_read"]["value"]
        actual = [n for n in result.noise_terms if n.name == "read"][0].value_e
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_noise_quantization(self, result, golden) -> None:
        expected = golden["noise_quantization"]["value"]
        actual = [n for n in result.noise_terms if n.name == "quantization"][0].value_e
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_noise_rss(self, result, golden) -> None:
        expected = golden["noise_rss"]["value"]
        actual = math.sqrt(sum(n.value_e ** 2 for n in result.noise_terms))
        assert actual == pytest.approx(expected, rel=REL_TOL)

    def test_snr(self, result, golden) -> None:
        expected = golden["snr"]["value"]
        actual = result.metrics["snr"]
        assert actual == pytest.approx(expected, rel=REL_TOL)
