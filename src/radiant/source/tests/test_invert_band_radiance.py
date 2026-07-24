"""Tests for the band-integrated Planck inversion helper.

Step 2.2 (S12) — the inversion harness must recover T from L_band for
three bracketed parity cases (LWIR, MWIR, visible Wien) and reject
malformed inputs.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.parameters import ParameterBoundsError
from radiant.source.converters.invert_band_radiance import (
    integrate_planck_over_band,
    invert_band_radiance_to_temperature,
)


class TestForwardIntegralMonotone:
    @pytest.mark.level0
    def test_integral_strictly_increasing_in_T(self) -> None:
        """Band integral must be monotone in T (required by the solver)."""
        band = (8.0, 12.0)
        Ts = np.array([50.0, 100.0, 200.0, 300.0, 500.0, 1000.0])
        Ls = np.array(
            [integrate_planck_over_band(T, band) for T in Ts],
            dtype=np.float64,
        )
        diffs = np.diff(Ls)
        assert np.all(diffs > 0.0), f"Band integral not monotone in T: L={Ls}, diffs={diffs}"

    @pytest.mark.level0
    def test_forward_integral_absolute_anchor(self) -> None:
        """Absolute value anchor for the forward band integral (Track A1 §3d).

        Closes B2-3 (assurance audit 2026-07): before this, no test anywhere
        pinned an absolute value for ``integrate_planck_over_band`` — the
        round-trip anchors below cancel any scale error in the forward model.
        ∫₈¹² B(λ, 300 K) dλ = 38.5004239 W/m²/sr, blind-derived by adaptive
        quadrature independent of RADIANT. The default 201-pt trapezoid grid
        lands ~1.6e-6 relative below the exact value, comfortably inside 1e-3.
        """
        assert integrate_planck_over_band(300.0, (8.0, 12.0)) == pytest.approx(
            38.5004239, rel=1e-3
        )


class TestRoundTripAnchors:
    @pytest.mark.level0
    def test_anchor_1_LWIR_300K(self) -> None:
        """Anchor 1: 300 K, 8–12 µm LWIR band → recover 300 K to 1e-3 K."""
        T_true = 300.0
        band = (8.0, 12.0)
        L_band = integrate_planck_over_band(T_true, band)
        T_rec = invert_band_radiance_to_temperature(L_band, band)
        assert abs(T_rec - T_true) < 1.0e-3, f"LWIR round-trip: {T_rec} K vs {T_true} K"

    @pytest.mark.level0
    def test_anchor_2_MWIR_500K(self) -> None:
        """Anchor 2: 500 K, 3–5 µm MWIR band → recover 500 K to 1e-3 K."""
        T_true = 500.0
        band = (3.0, 5.0)
        L_band = integrate_planck_over_band(T_true, band)
        T_rec = invert_band_radiance_to_temperature(L_band, band)
        assert abs(T_rec - T_true) < 1.0e-3, f"MWIR round-trip: {T_rec} K vs {T_true} K"

    @pytest.mark.level0
    def test_anchor_3_visible_Wien_2000K(self) -> None:
        """Anchor 3: 2000 K, 0.7–1.0 µm (Wien tail) → recover 2000 K to 1e-3 K."""
        T_true = 2000.0
        band = (0.7, 1.0)
        L_band = integrate_planck_over_band(
            T_true, band, n_quad=401
        )  # denser grid — Wien curvature
        T_rec = invert_band_radiance_to_temperature(L_band, band, n_quad=401)
        assert abs(T_rec - T_true) < 1.0e-3, f"Wien round-trip: {T_rec} K vs {T_true} K"


class TestValidation:
    @pytest.mark.level0
    def test_inverted_band_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="inverted|degenerate"):
            invert_band_radiance_to_temperature(1.0, (12.0, 8.0))

    @pytest.mark.level0
    def test_non_positive_band_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="non-positive"):
            invert_band_radiance_to_temperature(1.0, (0.0, 8.0))

    @pytest.mark.level0
    def test_non_positive_L_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="non-positive"):
            invert_band_radiance_to_temperature(0.0, (8.0, 12.0))

    @pytest.mark.level0
    def test_nan_L_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="not finite"):
            invert_band_radiance_to_temperature(float("nan"), (8.0, 12.0))

    @pytest.mark.level0
    def test_L_above_bracket_raises(self) -> None:
        """L_band far above L(10 000 K) → clear bracket error."""
        band = (8.0, 12.0)
        L_above = integrate_planck_over_band(9_500.0, band) * 1.0e6
        with pytest.raises(ParameterBoundsError, match="bracket"):
            invert_band_radiance_to_temperature(L_above, band)
