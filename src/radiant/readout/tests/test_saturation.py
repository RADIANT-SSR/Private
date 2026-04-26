"""Tests for readout.saturation — dual saturation checks."""

from __future__ import annotations

import pytest

from radiant.readout.saturation import (
    SaturationStatus,
    check_adc_saturation,
    check_well_saturation,
)


class TestWellSaturation:
    @pytest.mark.level0
    def test_below_fwc(self) -> None:
        sig, status = check_well_saturation(50000.0, 100000.0)
        assert sig == pytest.approx(50000.0, rel=1e-12)
        assert status == SaturationStatus.OK

    @pytest.mark.level0
    def test_at_fwc(self) -> None:
        sig, status = check_well_saturation(100000.0, 100000.0)
        assert sig == pytest.approx(100000.0, rel=1e-12)
        assert status == SaturationStatus.OK

    @pytest.mark.level0
    def test_above_fwc(self) -> None:
        sig, status = check_well_saturation(150000.0, 100000.0)
        assert sig == pytest.approx(100000.0, rel=1e-12)
        assert status == SaturationStatus.CLIPPED

    @pytest.mark.level0
    def test_invalid_fwc_raises(self) -> None:
        with pytest.raises(ValueError, match="full_well_capacity_e"):
            check_well_saturation(1000.0, 0.0)


class TestAdcSaturation:
    @pytest.mark.level0
    def test_below_max(self) -> None:
        dn, status = check_adc_saturation(30000.0, 65535)
        assert dn == pytest.approx(30000.0, rel=1e-12)
        assert status == SaturationStatus.OK

    @pytest.mark.level0
    def test_at_max(self) -> None:
        dn, status = check_adc_saturation(65535.0, 65535)
        assert dn == pytest.approx(65535.0, rel=1e-12)
        assert status == SaturationStatus.OK

    @pytest.mark.level0
    def test_above_max(self) -> None:
        dn, status = check_adc_saturation(70000.0, 65535)
        assert dn == pytest.approx(65535.0, rel=1e-12)
        assert status == SaturationStatus.CLIPPED

    @pytest.mark.level0
    def test_8bit(self) -> None:
        """8-bit ADC: max_dn = 255."""
        dn, status = check_adc_saturation(300.0, 255)
        assert dn == pytest.approx(255.0, rel=1e-12)
        assert status == SaturationStatus.CLIPPED

    @pytest.mark.level0
    def test_invalid_max_raises(self) -> None:
        with pytest.raises(ValueError, match="max_dn"):
            check_adc_saturation(100.0, 0)


class TestSaturationScenarios:
    @pytest.mark.level1
    def test_well_saturates_first(self) -> None:
        """100K FWC, 14-bit ADC, 1 e-/DN → well saturates at 100K, ADC at 16383."""
        signal_e = 120000.0
        fwc = 100000.0
        gain = 1.0
        max_dn = (1 << 14) - 1  # 16383

        clipped_e, well_status = check_well_saturation(signal_e, fwc)
        signal_dn = clipped_e / gain
        clipped_dn, adc_status = check_adc_saturation(signal_dn, max_dn)

        assert well_status == SaturationStatus.CLIPPED
        assert adc_status == SaturationStatus.CLIPPED  # 100K > 16383

    @pytest.mark.level1
    def test_adc_saturates_first(self) -> None:
        """1M FWC, 8-bit ADC, 100 e-/DN → ADC saturates at 255 (25500 e-)."""
        signal_e = 30000.0
        fwc = 1_000_000.0
        gain = 100.0
        max_dn = 255

        clipped_e, well_status = check_well_saturation(signal_e, fwc)
        signal_dn = clipped_e / gain  # 300 DN
        clipped_dn, adc_status = check_adc_saturation(signal_dn, max_dn)

        assert well_status == SaturationStatus.OK
        assert adc_status == SaturationStatus.CLIPPED
        assert clipped_dn == pytest.approx(255.0, rel=1e-12)
