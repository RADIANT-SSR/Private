"""Tests for the ChainResult inspector."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.api.inspect import ResultPlotNamespace, inspect_result
from radiant.core.chain import ChainState
from radiant.core.radiometry import NoiseTerm
from radiant.io.results import ChainResult


def _make_result() -> ChainResult:
    """Build a minimal ChainResult for testing the inspector."""
    wl = np.linspace(3.5, 5.0, 10)
    state = ChainState(wavelength_um=wl)
    state = state.with_metric("snr", 47.3)
    state = state.with_metric("nedt", 0.023)
    state = state.with_stage_output("source", "regime_tentative", "extended")
    state = state.with_stage_output("optics", "regime", "extended")
    state = state.with_stage_output("optics", "ee_box", 0.82)
    state = state.with_noise(NoiseTerm(
        name="photon_shot",
        value_e=111.6,
        origin_frame="photoelectrons",
        physical_basis="Poisson",
    ))
    state = state.with_noise(NoiseTerm(
        name="dark_current_shot",
        value_e=89.2,
        origin_frame="photoelectrons",
        physical_basis="Poisson",
    ))
    state = state.with_history("source")
    state = state.with_history("optics")
    return ChainResult(state)


@pytest.mark.level1
class TestInspectFull:
    def test_full_tree_contains_metrics(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        assert "ChainResult" in tree
        assert "metrics" in tree
        assert "snr" in tree
        assert "47.3" in tree

    def test_full_tree_contains_noise(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        assert "noise_terms" in tree
        assert "photon_shot" in tree
        assert "111.6" in tree

    def test_full_tree_contains_stages(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        assert "source" in tree
        assert "optics" in tree

    def test_tree_structure_has_box_drawing(self) -> None:
        result = _make_result()
        tree = inspect_result(result)
        # Box-drawing characters should be present
        assert "\u251c" in tree or "\u2514" in tree


@pytest.mark.level1
class TestInspectStage:
    def test_single_stage(self) -> None:
        result = _make_result()
        text = inspect_result(result, "optics")
        assert "optics" in text
        assert "regime" in text
        assert "ee_box" in text

    def test_unknown_stage(self) -> None:
        result = _make_result()
        text = inspect_result(result, "nonexistent")
        assert "not found" in text
        assert "Available" in text


@pytest.mark.level1
class TestResultPlotNamespace:
    def test_namespace_creation(self) -> None:
        result = _make_result()
        ns = ResultPlotNamespace(result)
        assert hasattr(ns, "psf")
        assert hasattr(ns, "noise_budget")
        assert hasattr(ns, "mtf")

    def test_psf_raises_without_data(self) -> None:
        result = _make_result()
        ns = ResultPlotNamespace(result)
        with pytest.raises(ValueError, match="No effective PSF"):
            ns.psf()
