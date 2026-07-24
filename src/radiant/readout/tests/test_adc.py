"""Tests for radiant.readout.adc."""

from __future__ import annotations

import math

import pytest

from radiant.readout.adc import AnalogToDigital


@pytest.mark.level0
def test_max_dn_truth_anchor() -> None:
    assert AnalogToDigital(gain_e_per_dn=1.0, n_bits=16).max_dn == 65535
    assert AnalogToDigital(gain_e_per_dn=1.0, n_bits=8).max_dn == 255
    assert AnalogToDigital(gain_e_per_dn=1.0, n_bits=12).max_dn == 4095


@pytest.mark.level0
def test_full_scale_e() -> None:
    adc = AnalogToDigital(gain_e_per_dn=2.5, n_bits=14)
    assert adc.full_scale_e == pytest.approx(2.5 * 16383, rel=1e-12)


@pytest.mark.level0
def test_quantization_noise_truth_anchor() -> None:
    # σ_quant = LSB/√12.
    adc = AnalogToDigital(gain_e_per_dn=1.0, n_bits=16)
    assert adc.quantization_noise_e() == pytest.approx(1.0 / math.sqrt(12.0), rel=1e-12)


@pytest.mark.level0
def test_adc_14bit_100ke_a3_anchor() -> None:
    """Track A3 §4d anchor: 14-bit ADC, 100 ke⁻ full well.

    g = N_fullwell / 2ⁿ = 100000 / 16384 = 6.10351562 e⁻/DN;
    σ_ADC = g/√12 = 1.76193316 e⁻ RMS. Pins the g/√12 convention against the
    wrong divisor g/12 (which would give 0.508626, 3.4641× low).
    """
    gain = 100_000.0 / 2**14  # 6.10351562 e-/DN
    assert gain == pytest.approx(6.10351562, rel=1e-8)
    adc = AnalogToDigital(gain_e_per_dn=gain, n_bits=14)
    assert adc.quantization_noise_e() == pytest.approx(1.76193316, rel=1e-6)

    adc2 = AnalogToDigital(gain_e_per_dn=5.0, n_bits=14)
    assert adc2.quantization_noise_e() == pytest.approx(5.0 / math.sqrt(12.0), rel=1e-12)


@pytest.mark.level0
def test_e_to_dn_linear() -> None:
    adc = AnalogToDigital(gain_e_per_dn=2.0, n_bits=16)
    assert adc.e_to_dn(0.0) == 0.0
    assert adc.e_to_dn(2.0) == pytest.approx(1.0, rel=1e-12)
    assert adc.e_to_dn(1000.0) == pytest.approx(500.0, rel=1e-12)


@pytest.mark.level0
def test_e_to_dn_hard_clips_at_max() -> None:
    adc = AnalogToDigital(gain_e_per_dn=1.0, n_bits=8)
    # full scale = 255 e-, anything bigger saturates.
    assert adc.e_to_dn(1000.0) == 255.0
    assert adc.e_to_dn(255.0) == 255.0
    assert adc.e_to_dn(254.0) == 254.0


@pytest.mark.level0
@pytest.mark.parametrize("bad", [0.0, -1.0, math.inf, math.nan])
def test_invalid_gain_raises(bad: float) -> None:
    with pytest.raises(ValueError, match="gain_e_per_dn"):
        AnalogToDigital(gain_e_per_dn=bad, n_bits=16)


@pytest.mark.level0
@pytest.mark.parametrize("bad", [0, -1, 1.5])
def test_invalid_n_bits_raises(bad: object) -> None:
    with pytest.raises(ValueError, match="n_bits"):
        AnalogToDigital(gain_e_per_dn=1.0, n_bits=bad)  # type: ignore[arg-type]


@pytest.mark.level0
def test_e_to_dn_rejects_invalid_input() -> None:
    adc = AnalogToDigital(gain_e_per_dn=1.0, n_bits=16)
    with pytest.raises(ValueError, match="electrons"):
        adc.e_to_dn(-1.0)
    with pytest.raises(ValueError, match="electrons"):
        adc.e_to_dn(math.nan)
    with pytest.raises(ValueError, match="electrons"):
        adc.e_to_dn(math.inf)


@pytest.mark.level1
def test_round_trip() -> None:
    adc = AnalogToDigital(gain_e_per_dn=1.25, n_bits=12, name="test_adc")
    restored = AnalogToDigital.from_dict(adc.to_dict())
    assert restored == adc
