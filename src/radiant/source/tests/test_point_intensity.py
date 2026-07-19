"""Level-0 tests for point-source intensity convenience converters (Gap B).

``blackbody_point_intensity`` and ``scalar_band_intensity`` build I(λ) [W/sr/µm]
for an unresolved target — pure functions, no chain.

Truth anchors:
  1. Blackbody: I(λ) = ε·A·B(λ,T) equals ε·A × the Planck radiance directly.
  2. Scalar: the defining property ∫ I(λ) dλ = band_W_per_sr over the band.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.parameters import ParameterBoundsError
from radiant.source.converters.point_intensity import (
    blackbody_point_intensity,
    scalar_band_intensity,
)
from radiant.source.errors import SourceValidationError

_trapz = np.trapezoid  # numpy ≥ 2.0 (np.trapz removed)


class TestBlackbodyPointIntensity:
    @pytest.mark.level0
    def test_equals_eps_area_times_planck(self) -> None:
        lam = np.linspace(3.5, 5.0, 200)
        eps, A, T = 0.85, 8.0, 290.0
        got = blackbody_point_intensity(lam, T, A, eps)
        expected = eps * A * planck_spectral_radiance(lam, T)
        np.testing.assert_allclose(got, expected, rtol=1e-12)

    @pytest.mark.level0
    def test_scales_linearly_with_area_and_emissivity(self) -> None:
        lam = np.linspace(3.5, 5.0, 50)
        base = blackbody_point_intensity(lam, 300.0, 5.0, 0.5)
        np.testing.assert_allclose(
            blackbody_point_intensity(lam, 300.0, 10.0, 0.5), 2.0 * base, rtol=1e-12
        )
        np.testing.assert_allclose(
            blackbody_point_intensity(lam, 300.0, 5.0, 1.0), 2.0 * base, rtol=1e-12
        )

    @pytest.mark.level0
    def test_zero_area_rejected(self) -> None:
        with pytest.raises(SourceValidationError):  # delegated to BlackbodyIntensitySource
            blackbody_point_intensity(np.array([4.0, 4.5]), 300.0, 0.0, 1.0)


class TestScalarBandIntensity:
    @pytest.mark.level0
    def test_band_integral_recovers_the_scalar(self) -> None:
        """The defining property: ∫ I(λ) dλ over the band = band_W_per_sr.

        Evaluated on the band grid (all points in-band → constant density), so the
        trapezoid is exact — no step-edge ramp artifacts (those are a discretization
        detail of *where* the grid straddles the edges, not the flat-density model).
        """
        lam = np.linspace(3.5, 5.0, 2000)  # the filter band
        intensity = scalar_band_intensity(lam, 8.443, 3.5, 5.0)
        assert float(_trapz(intensity, lam)) == pytest.approx(8.443, rel=1e-9)

    @pytest.mark.level0
    def test_flat_inside_zero_outside(self) -> None:
        lam = np.array([3.0, 3.5, 4.25, 5.0, 5.5])
        intensity = scalar_band_intensity(lam, 3.0, 3.5, 5.0)
        density = 3.0 / (5.0 - 3.5)
        assert intensity[0] == 0.0  # below band
        assert intensity[-1] == 0.0  # above band
        for v in intensity[1:-1]:  # inside band edges (inclusive)
            assert v == pytest.approx(density, rel=1e-12)

    @pytest.mark.level0
    def test_inverted_band_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError):
            scalar_band_intensity(np.array([4.0]), 1.0, 5.0, 3.5)

    @pytest.mark.level0
    def test_negative_intensity_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError):
            scalar_band_intensity(np.array([4.0]), -1.0, 3.5, 5.0)
