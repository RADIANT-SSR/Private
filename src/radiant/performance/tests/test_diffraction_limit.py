"""Level 0 tests for radiant.performance.diffraction_limit (Gap 49).

Truth anchors are hand calculations from the Rayleigh criterion (Rule 18):

- θ = 1.22 λ / D. For λ = 0.5 µm, D = 0.5 m: θ = 1.22e-6 rad = 1.22 µrad.
- Ground spot at R = 500 km: 1.22e-6 · 5e5 = 0.61 m.
- For λ = 10 µm, D = 0.2 m: θ = 1.22·10e-6/0.2 = 61 µrad.
"""

from __future__ import annotations

import pytest

from radiant.performance.diffraction_limit import (
    DiffractionLimitError,
    diffraction_limited_angular_rad,
    diffraction_limited_ground_m,
)


class TestAngular:
    def test_vnir_anchor(self) -> None:
        assert diffraction_limited_angular_rad(0.5e-6, 0.5) == pytest.approx(1.22e-6, rel=1e-9)

    def test_lwir_anchor(self) -> None:
        assert diffraction_limited_angular_rad(10e-6, 0.2) == pytest.approx(61e-6, rel=1e-9)

    def test_larger_aperture_finer(self) -> None:
        assert diffraction_limited_angular_rad(0.5e-6, 1.0) < diffraction_limited_angular_rad(
            0.5e-6, 0.5
        )


class TestGround:
    def test_ground_anchor(self) -> None:
        # 1.22 µrad × 500 km = 0.61 m
        assert diffraction_limited_ground_m(0.5e-6, 0.5, 500e3) == pytest.approx(0.61, rel=1e-9)

    def test_ground_scales_with_range(self) -> None:
        near = diffraction_limited_ground_m(0.5e-6, 0.5, 400e3)
        far = diffraction_limited_ground_m(0.5e-6, 0.5, 800e3)
        assert far == pytest.approx(2.0 * near, rel=1e-9)


class TestValidation:
    def test_zero_wavelength_raises(self) -> None:
        with pytest.raises(DiffractionLimitError, match="wavelength_m"):
            diffraction_limited_angular_rad(0.0, 0.5)

    def test_zero_aperture_raises(self) -> None:
        with pytest.raises(DiffractionLimitError, match="aperture_m"):
            diffraction_limited_angular_rad(0.5e-6, 0.0)

    def test_zero_range_raises(self) -> None:
        with pytest.raises(DiffractionLimitError, match="range_m"):
            diffraction_limited_ground_m(0.5e-6, 0.5, 0.0)
