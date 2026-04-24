"""Tests for SubPixelSource.

Truth anchors:
1. ff=1 → L_pixel = L_target (pure target)
2. ff→0 → L_pixel ≈ L_background
3. Linear mixing: L_pixel = ff·L_tgt + (1-ff)·L_bg

Cross-model consistency:
- SubPixelSource at ff=1 = ThermalSource with same T, ε (to 1e-10)

See RADIANT_Source_Target_System.md §6 Path 3.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.source.emitted import ThermalSource
from radiant.source.sub_pixel import SubPixelSource

WAV = np.linspace(3.0, 5.0, 200)


class TestSubPixelSource:
    def test_ff_1_equals_target(self) -> None:
        """ff=1 → L_pixel = L_target."""
        src = SubPixelSource(
            fill_fraction=1.0,
            target_temperature_K=350.0,
            target_emissivity=0.95,
            background_temperature_K=290.0,
            background_emissivity=0.90,
        )
        L = src.spectral_radiance(WAV)
        L_tgt = src.target_radiance(WAV)
        np.testing.assert_allclose(L, L_tgt, rtol=1e-12)

    def test_ff_1_matches_thermal_source(self) -> None:
        """ff=1 produces same result as ThermalSource directly."""
        T = 350.0
        eps = 0.95
        sub = SubPixelSource(
            fill_fraction=1.0,
            target_temperature_K=T,
            target_emissivity=eps,
            background_temperature_K=290.0,
            background_emissivity=0.9,
        )
        thermal = ThermalSource(temperature_K=T, emissivity=eps)
        L_sub = sub.spectral_radiance(WAV)
        L_thermal = thermal.spectral_radiance(WAV)
        np.testing.assert_allclose(L_sub, L_thermal, rtol=1e-10)

    def test_small_ff_approaches_background(self) -> None:
        """At very small ff, L_pixel ≈ L_background."""
        src = SubPixelSource(
            fill_fraction=1e-10,
            target_temperature_K=1000.0,
            target_emissivity=1.0,
            background_temperature_K=290.0,
            background_emissivity=0.95,
        )
        L = src.spectral_radiance(WAV)
        L_bg = src.background_radiance(WAV)
        np.testing.assert_allclose(L, L_bg, rtol=1e-4)

    def test_linear_mixing(self) -> None:
        """L_pixel = ff·L_tgt + (1-ff)·L_bg."""
        ff = 0.3
        src = SubPixelSource(
            fill_fraction=ff,
            target_temperature_K=400.0,
            target_emissivity=0.9,
            background_temperature_K=280.0,
            background_emissivity=0.95,
        )
        L = src.spectral_radiance(WAV)
        expected = ff * src.target_radiance(WAV) + (1 - ff) * src.background_radiance(WAV)
        np.testing.assert_allclose(L, expected, rtol=1e-12)

    def test_half_fill(self) -> None:
        """ff=0.5 → average of target and background."""
        src = SubPixelSource(
            fill_fraction=0.5,
            target_temperature_K=400.0,
            target_emissivity=1.0,
            background_temperature_K=300.0,
            background_emissivity=1.0,
        )
        L = src.spectral_radiance(WAV)
        L_tgt = src.target_radiance(WAV)
        L_bg = src.background_radiance(WAV)
        np.testing.assert_allclose(L, 0.5 * L_tgt + 0.5 * L_bg, rtol=1e-12)

    def test_ff_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="fill_fraction"):
            SubPixelSource(
                fill_fraction=0.0,
                target_temperature_K=300, target_emissivity=0.9,
                background_temperature_K=290, background_emissivity=0.9,
            )

    def test_ff_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="fill_fraction"):
            SubPixelSource(
                fill_fraction=1.5,
                target_temperature_K=300, target_emissivity=0.9,
                background_temperature_K=290, background_emissivity=0.9,
            )

    def test_negative_target_temp_raises(self) -> None:
        with pytest.raises(ValueError, match="target_temperature_K"):
            SubPixelSource(
                fill_fraction=0.5,
                target_temperature_K=-10, target_emissivity=0.9,
                background_temperature_K=290, background_emissivity=0.9,
            )

    def test_emissivity_gt_1_raises(self) -> None:
        with pytest.raises(ValueError, match="target_emissivity"):
            SubPixelSource(
                fill_fraction=0.5,
                target_temperature_K=300, target_emissivity=1.5,
                background_temperature_K=290, background_emissivity=0.9,
            )

    def test_frozen(self) -> None:
        src = SubPixelSource(
            fill_fraction=0.5,
            target_temperature_K=300, target_emissivity=0.9,
            background_temperature_K=290, background_emissivity=0.9,
        )
        with pytest.raises(AttributeError):
            src.fill_fraction = 0.3  # type: ignore[misc]
