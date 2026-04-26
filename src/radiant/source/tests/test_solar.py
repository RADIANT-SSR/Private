"""Tests for solar irradiance wrapper.

Truth anchors:
1. At 1 AU, matches core solar directly
2. At 2 AU, irradiance scales by 1/4
3. Distance scaling is inverse-square law

See RADIANT_Source_Target_System.md §3.3.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.source.solar import solar_irradiance_at_target

WAV = np.linspace(0.3, 5.0, 200)


class TestSolarIrradianceAtTarget:
    @pytest.mark.level0
    def test_1au_matches_core(self) -> None:
        """At 1 AU, result matches core solar directly."""
        from_wrapper = solar_irradiance_at_target(WAV, distance_au=1.0)
        from_core = toa_solar_spectral_irradiance(WAV)
        np.testing.assert_allclose(from_wrapper, from_core, rtol=1e-12)

    @pytest.mark.level0
    def test_inverse_square(self) -> None:
        """At 2 AU, irradiance is 1/4 of 1 AU."""
        e_1au = solar_irradiance_at_target(WAV, distance_au=1.0)
        e_2au = solar_irradiance_at_target(WAV, distance_au=2.0)
        np.testing.assert_allclose(e_2au, e_1au / 4.0, rtol=1e-12)

    @pytest.mark.level0
    def test_mars_distance(self) -> None:
        """At Mars (~1.524 AU), irradiance scales correctly."""
        d_mars = 1.524
        e_1au = solar_irradiance_at_target(WAV, distance_au=1.0)
        e_mars = solar_irradiance_at_target(WAV, distance_au=d_mars)
        np.testing.assert_allclose(e_mars, e_1au / d_mars**2, rtol=1e-12)

    @pytest.mark.level0
    def test_positive_everywhere(self) -> None:
        result = solar_irradiance_at_target(WAV)
        assert np.all(result > 0)

    @pytest.mark.level0
    def test_zero_distance_raises(self) -> None:
        with pytest.raises(ValueError, match="distance_au"):
            solar_irradiance_at_target(WAV, distance_au=0.0)

    @pytest.mark.level0
    def test_negative_distance_raises(self) -> None:
        with pytest.raises(ValueError, match="distance_au"):
            solar_irradiance_at_target(WAV, distance_au=-1.0)
