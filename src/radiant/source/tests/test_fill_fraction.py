"""Level-0 tests for sub-pixel fill fraction from projected area (Gap 97).

``fill_fraction_from_area`` inverts the Path-3 relation
``projected_area = fill_fraction × Ω_pixel × range²`` — pure geometry, no chain.

Truth anchors (hand calculation):
  Ω_pixel = (p_x·p_y)/f²;  Ω_target = A/R²;  ff = min(1, Ω_target/Ω_pixel).
"""

from __future__ import annotations

import pytest

from radiant.source.fill_fraction import fill_fraction_from_area

# Maritime-scenario geometry (scenario 1.1).
_R = 532088.886237956
_PX = 15e-6
_PY = 15e-6
_F = 0.75
_OMEGA_PIXEL = (_PX * _PY) / (_F * _F)  # 4.0e-10 sr


class TestFillFractionFromArea:
    @pytest.mark.level0
    def test_matches_areal_ratio(self) -> None:
        """ff = (A/R²) / Ω_pixel for a sub-pixel target."""
        A = 24.0
        expected = (A / (_R * _R)) / _OMEGA_PIXEL
        assert fill_fraction_from_area(A, _R, _PX, _PY, _F) == pytest.approx(expected, rel=1e-12)
        assert 0.0 < expected < 1.0  # genuinely sub-pixel

    @pytest.mark.level0
    def test_clamps_to_one_when_overfilling(self) -> None:
        """A target larger than the pixel footprint clamps to 1.0."""
        # 240 m² overfills the 113 m² footprint (Ω_target/Ω_pixel ≈ 2.12).
        assert fill_fraction_from_area(240.0, _R, _PX, _PY, _F) == 1.0

    @pytest.mark.level0
    def test_scales_linearly_below_clamp(self) -> None:
        """Doubling the area doubles the fill fraction (until it clamps)."""
        ff1 = fill_fraction_from_area(24.0, _R, _PX, _PY, _F)
        ff2 = fill_fraction_from_area(48.0, _R, _PX, _PY, _F)
        assert ff2 == pytest.approx(2.0 * ff1, rel=1e-12)

    @pytest.mark.level0
    def test_ff_times_omega_pixel_recovers_omega_target(self) -> None:
        """The whole point: ff·Ω_pixel = A/R² = Ω_target (point-source solid angle)."""
        A = 30.0
        ff = fill_fraction_from_area(A, _R, _PX, _PY, _F)
        assert ff is not None
        assert ff * _OMEGA_PIXEL == pytest.approx(A / (_R * _R), rel=1e-12)

    @pytest.mark.level0
    def test_rectangular_pixel_uses_both_pitches(self) -> None:
        """Ω_pixel uses p_x·p_y — a rectangular pixel differs from a square one."""
        A = 24.0
        square = fill_fraction_from_area(A, _R, 15e-6, 15e-6, _F)
        rect = fill_fraction_from_area(A, _R, 15e-6, 30e-6, _F)
        assert rect == pytest.approx(square / 2.0, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize(
        "area,rng,px,py,f",
        [
            (0.0, _R, _PX, _PY, _F),  # no area
            (24.0, 0.0, _PX, _PY, _F),  # no range
            (24.0, _R, 0.0, _PY, _F),  # no pitch_x
            (24.0, _R, _PX, 0.0, _F),  # no pitch_y
            (24.0, _R, _PX, _PY, 0.0),  # no focal length
        ],
    )
    def test_insufficient_geometry_returns_none(
        self, area: float, rng: float, px: float, py: float, f: float
    ) -> None:
        """Non-positive inputs → None so the caller falls back to the ff parameter."""
        assert fill_fraction_from_area(area, rng, px, py, f) is None
