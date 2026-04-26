"""Tests for radiant.detector.pixel."""

from __future__ import annotations

import math

import pytest

from radiant.detector.pixel import PixelGeometry


@pytest.mark.level0
def test_basic_square_pixel() -> None:
    px = PixelGeometry(pitch_x_m=10e-6, pitch_y_m=10e-6)
    assert px.cell_area_m2 == pytest.approx(1e-10, rel=1e-12)
    assert px.photosensitive_area_m2 == pytest.approx(1e-10, rel=1e-12)
    assert px.is_square is True


@pytest.mark.level0
def test_rectangular_pixel() -> None:
    px = PixelGeometry(pitch_x_m=10e-6, pitch_y_m=20e-6)
    assert px.cell_area_m2 == pytest.approx(2e-10, rel=1e-12)
    assert px.is_square is False


@pytest.mark.level0
def test_fill_factor_reduces_photosensitive_area() -> None:
    px = PixelGeometry(pitch_x_m=10e-6, pitch_y_m=10e-6, fill_factor=0.5)
    assert px.photosensitive_area_m2 == pytest.approx(0.5 * 1e-10, rel=1e-12)


@pytest.mark.level0
def test_ifov_truth_anchor() -> None:
    # 10 µm pitch on a 100 mm focal length → IFOV = 1e-4 rad exactly.
    px = PixelGeometry(pitch_x_m=10e-6, pitch_y_m=10e-6)
    ifov = px.ifov_rad(focal_length_m=0.1)
    assert ifov == pytest.approx((1e-4, 1e-4), rel=1e-12)


@pytest.mark.level0
def test_solid_angle_truth_anchor() -> None:
    # pitch_x·pitch_y / f² = (10e-6)²/(0.1)² = 1e-8 sr.
    px = PixelGeometry(pitch_x_m=10e-6, pitch_y_m=10e-6)
    omega = px.solid_angle_sr(focal_length_m=0.1)
    assert omega == pytest.approx(1e-8, rel=1e-12)


@pytest.mark.level0
def test_rectangular_ifov() -> None:
    px = PixelGeometry(pitch_x_m=8e-6, pitch_y_m=16e-6)
    ifov_x, ifov_y = px.ifov_rad(focal_length_m=0.2)
    assert ifov_x == pytest.approx(4e-5, rel=1e-12)
    assert ifov_y == pytest.approx(8e-5, rel=1e-12)


@pytest.mark.level0
@pytest.mark.parametrize("bad", [0.0, -1e-6, math.inf, math.nan])
def test_invalid_pitch_raises(bad: float) -> None:
    with pytest.raises(ValueError, match="pitch"):
        PixelGeometry(pitch_x_m=bad, pitch_y_m=10e-6)
    with pytest.raises(ValueError, match="pitch"):
        PixelGeometry(pitch_x_m=10e-6, pitch_y_m=bad)


@pytest.mark.level0
@pytest.mark.parametrize("ff", [0.0, -0.1, 1.1, 2.0])
def test_invalid_fill_factor_raises(ff: float) -> None:
    with pytest.raises(ValueError, match="fill_factor"):
        PixelGeometry(pitch_x_m=10e-6, pitch_y_m=10e-6, fill_factor=ff)


@pytest.mark.level0
def test_invalid_charge_diffusion_raises() -> None:
    with pytest.raises(ValueError, match="charge_diffusion_length_m"):
        PixelGeometry(
            pitch_x_m=10e-6,
            pitch_y_m=10e-6,
            charge_diffusion_length_m=-1e-6,
        )


@pytest.mark.level0
@pytest.mark.parametrize("bad_f", [0.0, -0.1, math.inf, math.nan])
def test_ifov_rejects_bad_focal_length(bad_f: float) -> None:
    px = PixelGeometry(pitch_x_m=10e-6, pitch_y_m=10e-6)
    with pytest.raises(ValueError, match="focal_length_m"):
        px.ifov_rad(bad_f)
    with pytest.raises(ValueError, match="focal_length_m"):
        px.solid_angle_sr(bad_f)


@pytest.mark.level1
def test_round_trip() -> None:
    px = PixelGeometry(
        pitch_x_m=6.5e-6,
        pitch_y_m=6.5e-6,
        fill_factor=0.8,
        charge_diffusion_length_m=2e-6,
        name="cmos",
    )
    d = px.to_dict()
    restored = PixelGeometry.from_dict(d)
    assert restored == px
