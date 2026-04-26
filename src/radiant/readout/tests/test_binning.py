"""Tests for readout.binning — on-chip and off-chip pixel binning."""

from __future__ import annotations

import math

import pytest

from radiant.readout.binning_offchip import (
    offchip_scale_fpn,
    offchip_scale_read_noise,
    offchip_scale_shot_noise,
    offchip_scale_signal,
)
from radiant.readout.binning_onchip import (
    onchip_scale_fpn,
    onchip_scale_read_noise,
    onchip_scale_shot_noise,
    onchip_scale_signal,
)


class TestOnchipSignal:
    @pytest.mark.level0
    def test_2x2(self) -> None:
        assert onchip_scale_signal(1000.0, 2, 2) == pytest.approx(4000.0, rel=1e-12)

    @pytest.mark.level0
    def test_1x1_identity(self) -> None:
        assert onchip_scale_signal(1000.0, 1, 1) == pytest.approx(1000.0, rel=1e-12)

    @pytest.mark.level0
    def test_asymmetric(self) -> None:
        assert onchip_scale_signal(1000.0, 2, 3) == pytest.approx(6000.0, rel=1e-12)

    @pytest.mark.level0
    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="binning factors"):
            onchip_scale_signal(1000.0, 0, 2)


class TestOnchipShot:
    @pytest.mark.level0
    def test_2x2(self) -> None:
        assert onchip_scale_shot_noise(10.0, 2, 2) == pytest.approx(20.0, rel=1e-12)


class TestOnchipRead:
    @pytest.mark.level0
    def test_unchanged(self) -> None:
        """On-chip binning: single readout → read noise unchanged."""
        assert onchip_scale_read_noise(5.0) == pytest.approx(5.0, rel=1e-12)


class TestOnchipFPN:
    @pytest.mark.level0
    def test_linear_scaling(self) -> None:
        assert onchip_scale_fpn(10.0, 2, 2) == pytest.approx(40.0, rel=1e-12)


class TestOffchipSignal:
    @pytest.mark.level0
    def test_2x2(self) -> None:
        assert offchip_scale_signal(1000.0, 2, 2) == pytest.approx(4000.0, rel=1e-12)


class TestOffchipShot:
    @pytest.mark.level0
    def test_2x2(self) -> None:
        assert offchip_scale_shot_noise(10.0, 2, 2) == pytest.approx(20.0, rel=1e-12)


class TestOffchipRead:
    @pytest.mark.level0
    def test_scales_sqrt(self) -> None:
        """Off-chip: each pixel read independently → √(P) scaling."""
        expected = 5.0 * math.sqrt(4)
        assert offchip_scale_read_noise(5.0, 2, 2) == pytest.approx(expected, rel=1e-12)


class TestOffchipFPN:
    @pytest.mark.level0
    def test_linear_scaling(self) -> None:
        assert offchip_scale_fpn(10.0, 2, 2) == pytest.approx(40.0, rel=1e-12)


class TestBinningInteraction:
    @pytest.mark.level1
    def test_onchip_plus_offchip_signal(self) -> None:
        """Combined 2×2 on-chip + 3×3 off-chip = 36× signal."""
        s = 100.0
        s1 = onchip_scale_signal(s, 2, 2)
        s2 = offchip_scale_signal(s1, 3, 3)
        assert s2 == pytest.approx(100.0 * 4 * 9, rel=1e-12)

    @pytest.mark.level1
    def test_read_noise_only_offchip(self) -> None:
        """On-chip doesn't scale read noise; off-chip does."""
        rn = 5.0
        rn1 = onchip_scale_read_noise(rn)
        assert rn1 == pytest.approx(5.0, rel=1e-12)
        rn2 = offchip_scale_read_noise(rn1, 2, 2)
        assert rn2 == pytest.approx(5.0 * 2.0, rel=1e-12)
