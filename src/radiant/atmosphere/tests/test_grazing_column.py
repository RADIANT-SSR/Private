"""Level-0 tests for the grazing slant-column integral.

Three independent truth anchors for
:func:`radiant.atmosphere.grazing_column.grazing_slant_column_km`, none of them
computed by other RADIANT physics code (Rule 18):

1. **Chapman's analytic grazing limit** — ``S(r₀ → ∞) = e^{−h₀/H}·√(π r₀ H/2)``
   (Chapman 1931).
2. **The vertical limit** — a ray with a below-surface perigee and zero zenith
   reduces to ``∫ exp(−h/H) dh = H(e^{−h_lo/H} − e^{−h_hi/H})``, the closed-form
   column integral.
3. **Kasten & Young (1989) relative optical air mass** — the published
   empirical ``m(z)`` for a real atmosphere, compared against ``S/S_vertical``
   for the molecular scale height.
"""

from __future__ import annotations

import math

import pytest

import radiant.atmosphere.grazing_column as gc
from radiant.atmosphere.grazing_column import (
    chapman_grazing_limit_km,
    grazing_slant_column_km,
)
from radiant.atmosphere.simple import H_AER_M, H_H2O_M, H_MOL_M
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError


def _kasten_young_airmass(zenith_deg: float) -> float:
    """Kasten & Young (1989) relative optical air mass — literature formula."""
    z = math.radians(zenith_deg)
    return 1.0 / (math.cos(z) + 0.50572 * (96.07995 - zenith_deg) ** -1.6364)


class TestTruthAnchors:
    @pytest.mark.level0
    @pytest.mark.parametrize("scale_height_m", [H_MOL_M, H_AER_M, H_H2O_M])
    def test_anchor_1_chapman_grazing_limit(self, scale_height_m: float) -> None:
        """Anchor 1: a full tangent ray at the surface, out to 500 km [km].

        The Chapman identity is asymptotic in ``X = r₀/H`` (≈ 800 for air), so
        agreement is expected at the few-times-1e-4 level, not exactly.
        """
        computed = grazing_slant_column_km(R_EARTH_M, 0.0, 500_000.0, scale_height_m)
        expected = chapman_grazing_limit_km(R_EARTH_M, scale_height_m)
        assert computed == pytest.approx(expected, rel=1.0e-3)
        # ...and the sign of the residual is the known O(1/X) asymptotic error.
        assert computed > expected

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("h_low_m", "h_high_m"), [(0.0, 100_000.0), (3_000.0, 100_000.0), (0.0, 8_000.0)]
    )
    def test_anchor_2_vertical_limit_is_the_closed_form(
        self, h_low_m: float, h_high_m: float
    ) -> None:
        """Anchor 2: ζ = 0 (perigee at the Earth centre) [km].

        ``∫_{h_lo}^{h_hi} exp(−h/H) dh = H(e^{−h_lo/H} − e^{−h_hi/H})`` — hand
        integration, no RADIANT code involved.
        """
        H = H_MOL_M
        computed = grazing_slant_column_km(0.0, h_low_m, h_high_m, H)
        expected_m = H * (math.exp(-h_low_m / H) - math.exp(-h_high_m / H))
        assert computed == pytest.approx(expected_m / 1000.0, rel=1e-9)

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("zenith_deg", "tolerance"),
        # KY is an empirical fit and reads 0.99971 (not exactly 1) at zenith.
        [(0.0, 1e-3), (30.0, 5e-3), (60.0, 5e-3), (70.0, 5e-3), (80.0, 1e-2)],
    )
    def test_anchor_3_kasten_young_air_mass(self, zenith_deg: float, tolerance: float) -> None:
        """Anchor 3: relative optical air mass vs. Kasten-Young (1989).

        ``S(ζ)/S(0)`` for the molecular scale height is the relative optical
        air mass.  KY is fitted to a real (non-isothermal, refracting)
        atmosphere, so agreement is expected at the sub-percent level up to
        80° and to degrade beyond — which is exactly why the column model's
        89.5° ceiling exists and why this module takes over past it.
        """
        z = math.radians(zenith_deg)
        r_tan = R_EARTH_M * math.sin(z)
        slant = grazing_slant_column_km(r_tan, 0.0, 100_000.0, H_MOL_M)
        vertical = grazing_slant_column_km(0.0, 0.0, 100_000.0, H_MOL_M)
        assert slant / vertical == pytest.approx(_kasten_young_airmass(zenith_deg), rel=tolerance)

    @pytest.mark.level0
    def test_anchor_3_regime_note_refraction_gap_at_the_horizon(self) -> None:
        """At 89° the no-refraction model sits ~6 % below Kasten-Young.

        Documented, not fixed: refraction (ADR-0011 decision 5) is what closes
        that gap, and it is out of scope for v1.x.  Pinning the size of the
        discrepancy is what stops it drifting silently.
        """
        r_tan = R_EARTH_M * math.sin(math.radians(89.0))
        ratio = grazing_slant_column_km(r_tan, 0.0, 100_000.0, H_MOL_M) / grazing_slant_column_km(
            0.0, 0.0, 100_000.0, H_MOL_M
        )
        ky = _kasten_young_airmass(89.0)
        assert 0.90 < ratio / ky < 0.98


class TestQuadrature:
    @pytest.mark.level0
    @pytest.mark.parametrize("scale_height_m", [H_MOL_M, H_H2O_M])
    def test_converged_against_a_16x_finer_grid(self, scale_height_m: float) -> None:
        """The default interval count is converged to ~1e-12 relative."""
        args = (R_EARTH_M + 3_000.0, 3_000.0, 100_000.0, scale_height_m)
        coarse = grazing_slant_column_km(*args)
        original = gc.QUADRATURE_INTERVALS
        try:
            gc.QUADRATURE_INTERVALS = 16 * original
            fine = gc.grazing_slant_column_km(*args)
        finally:
            gc.QUADRATURE_INTERVALS = original
        assert coarse == pytest.approx(fine, rel=1e-10)

    @pytest.mark.level0
    def test_additivity_over_a_split_arc(self) -> None:
        """S(a→c) = S(a→b) + S(b→c) — the integral is an integral."""
        r0 = R_EARTH_M + 1_000.0
        whole = grazing_slant_column_km(r0, 1_000.0, 100_000.0, H_MOL_M)
        part1 = grazing_slant_column_km(r0, 1_000.0, 20_000.0, H_MOL_M)
        part2 = grazing_slant_column_km(r0, 20_000.0, 100_000.0, H_MOL_M)
        assert whole == pytest.approx(part1 + part2, rel=1e-6)

    @pytest.mark.level0
    def test_deterministic(self) -> None:
        """Same inputs → identical output, bit for bit (traceability)."""
        args = (R_EARTH_M + 500.0, 500.0, 100_000.0, H_H2O_M)
        assert grazing_slant_column_km(*args) == grazing_slant_column_km(*args)


class TestEdgeCases:
    @pytest.mark.level0
    def test_zero_length_arc_is_exactly_zero(self) -> None:
        assert grazing_slant_column_km(R_EARTH_M, 0.0, 0.0, H_MOL_M) == 0.0

    @pytest.mark.level0
    def test_tangent_at_the_near_end_starts_from_s_zero(self) -> None:
        """A perigee exactly at h_low is the tangent case — the largest column."""
        h = 5_000.0
        tangent = grazing_slant_column_km(R_EARTH_M + h, h, 100_000.0, H_MOL_M)
        steep = grazing_slant_column_km(0.0, h, 100_000.0, H_MOL_M)
        assert tangent > 20.0 * steep

    @pytest.mark.level0
    def test_one_ulp_of_tangent_overshoot_is_tolerated(self) -> None:
        """r₀ = r sin(ζ) rounds above r for ζ ≈ π/2; one ULP is snapped."""
        r_low = R_EARTH_M + 1_000.0
        assert grazing_slant_column_km(r_low * (1.0 + 1e-15), 1_000.0, 50_000.0, H_MOL_M) > 0.0

    @pytest.mark.level0
    def test_gross_tangent_overshoot_raises(self) -> None:
        with pytest.raises(ParameterBoundsError, match="exceeds the near-end radius"):
            grazing_slant_column_km(R_EARTH_M + 50_000.0, 1_000.0, 60_000.0, H_MOL_M)

    @pytest.mark.level0
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"r_tangent_m": float("nan")},
            {"scale_height_m": 0.0},
            {"scale_height_m": -1.0},
            {"h_low_m": -1.0},
            {"h_high_m": -5.0},
            {"r_tangent_m": -1.0},
        ],
    )
    def test_invalid_inputs_raise_actionably(self, kwargs: dict[str, float]) -> None:
        base = {
            "r_tangent_m": R_EARTH_M,
            "h_low_m": 0.0,
            "h_high_m": 50_000.0,
            "scale_height_m": H_MOL_M,
        }
        base.update(kwargs)
        with pytest.raises(ParameterBoundsError):
            grazing_slant_column_km(**base)  # type: ignore[arg-type]

    @pytest.mark.level0
    def test_never_returns_nan_or_inf(self) -> None:
        """Rule 16/17 — every legal input gives a finite, positive answer."""
        for h_low in (0.0, 100.0, 30_000.0):
            for zeta_deg in (0.0, 45.0, 89.0, 89.99, 90.0):
                r = R_EARTH_M + h_low
                r0 = min(r * math.sin(math.radians(zeta_deg)), r)
                val = grazing_slant_column_km(r0, h_low, 100_000.0, H_MOL_M)
                assert math.isfinite(val) and val > 0.0
