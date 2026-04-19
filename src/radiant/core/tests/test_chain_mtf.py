"""Tests for ChainState MTF-related methods.

Validates with_mtf(), with_spatial_freq(), and their interaction.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 10)


class TestWithSpatialFreq:
    def test_sets_frequency_grid(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        freq = np.linspace(0, 100, 50)
        new_state = state.with_spatial_freq(freq)

        assert new_state.spatial_freq_cycles_per_mrad is not None
        np.testing.assert_array_equal(new_state.spatial_freq_cycles_per_mrad, freq)

    def test_original_unchanged(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        freq = np.linspace(0, 100, 50)
        _ = state.with_spatial_freq(freq)

        assert state.spatial_freq_cycles_per_mrad is None

    def test_default_is_none(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        assert state.spatial_freq_cycles_per_mrad is None


class TestWithMTFAccumulation:
    def test_multiple_terms_accumulate(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        mtf_a = np.ones(50)
        mtf_b = np.ones(50) * 0.8

        state = state.with_mtf("mtf_optics_x", mtf_a)
        state = state.with_mtf("mtf_jitter_x", mtf_b)

        assert "mtf_optics_x" in state.mtf_terms
        assert "mtf_jitter_x" in state.mtf_terms
        np.testing.assert_array_equal(state.mtf_terms["mtf_optics_x"], mtf_a)
        np.testing.assert_array_equal(state.mtf_terms["mtf_jitter_x"], mtf_b)

    def test_with_mtf_does_not_clobber(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        mtf_a = np.ones(50)

        state1 = state.with_mtf("mtf_optics_x", mtf_a)
        assert len(state.mtf_terms) == 0  # original unchanged
        assert len(state1.mtf_terms) == 1

    def test_both_axes_stored(self, wl: np.ndarray) -> None:
        state = ChainState(wavelength_um=wl)
        freq = np.linspace(0, 100, 50)
        mtf_x = np.ones(50)
        mtf_y = np.ones(50) * 0.9

        state = state.with_spatial_freq(freq)
        state = state.with_mtf("mtf_optics_x", mtf_x)
        state = state.with_mtf("mtf_optics_y", mtf_y)

        assert state.spatial_freq_cycles_per_mrad is not None
        assert len(state.mtf_terms) == 2
        np.testing.assert_array_equal(state.mtf_terms["mtf_optics_x"], mtf_x)
        np.testing.assert_array_equal(state.mtf_terms["mtf_optics_y"], mtf_y)
