"""Tests for radiant.detector.qe."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.constants import c, h
from radiant.core.spectral import SpectralData
from radiant.detector.qe import QuantumEfficiency, photon_energy_joules

# ---------------------------------------------------------------------------
# Constant factory
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_constant_is_flat() -> None:
    qe = QuantumEfficiency.constant(0.7)
    out = qe.evaluate(np.array([0.4, 0.8, 1.5, 5.0, 12.0]))
    assert np.all(out == 0.7)


@pytest.mark.level0
def test_constant_stores_two_point_table() -> None:
    qe = QuantumEfficiency.constant(0.5, lam_min_um=0.2, lam_max_um=20.0)
    assert qe.table.wavelength_um.size == 2
    assert qe.table.wavelength_um[0] == pytest.approx(0.2, rel=1e-9)
    assert qe.table.wavelength_um[1] == pytest.approx(20.0, rel=1e-9)
    assert qe.mode == "constant"


@pytest.mark.level0
def test_constant_rejects_out_of_range_value() -> None:
    with pytest.raises(ValueError, match="value"):
        QuantumEfficiency.constant(1.2)
    with pytest.raises(ValueError, match="value"):
        QuantumEfficiency.constant(0.0)
    with pytest.raises(ValueError, match="value"):
        QuantumEfficiency.constant(-0.1)


@pytest.mark.level0
def test_constant_rejects_nonpositive_bounds() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        QuantumEfficiency.constant(0.5, lam_min_um=0.0, lam_max_um=10.0)
    with pytest.raises(ValueError, match="must be positive"):
        QuantumEfficiency.constant(0.5, lam_min_um=0.1, lam_max_um=-1.0)


@pytest.mark.level0
def test_constant_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError, match="lam_min_um"):
        QuantumEfficiency.constant(0.5, lam_min_um=5.0, lam_max_um=1.0)


@pytest.mark.level0
def test_constant_peak_qe_equals_value() -> None:
    qe = QuantumEfficiency.constant(0.42)
    assert qe.peak_qe == pytest.approx(0.42, rel=1e-12)


# ---------------------------------------------------------------------------
# from_spectral + evaluate
# ---------------------------------------------------------------------------


def _sample_spectral(lam: np.ndarray | None = None, vals: np.ndarray | None = None) -> SpectralData:
    if lam is None:
        lam = np.linspace(0.4, 1.1, 11)
    if vals is None:
        vals = np.full_like(lam, 0.6)
    return SpectralData(
        name="qe_table",
        wavelength_um=lam,
        values=vals,
        unit="",
        source="test",
    )


@pytest.mark.level1
def test_from_spectral_wraps_table() -> None:
    data = _sample_spectral()
    qe = QuantumEfficiency.from_spectral(data)
    out = qe.evaluate(np.array([0.5, 0.7, 1.0]))
    assert np.allclose(out, 0.6)


@pytest.mark.level1
def test_from_spectral_rejects_values_outside_unit_interval() -> None:
    lam = np.linspace(0.4, 1.1, 11)
    with pytest.raises(ValueError, match="out of"):
        QuantumEfficiency.from_spectral(_sample_spectral(lam, np.full_like(lam, 1.5)))
    with pytest.raises(ValueError, match="out of"):
        QuantumEfficiency.from_spectral(_sample_spectral(lam, np.full_like(lam, -0.1)))


@pytest.mark.level1
def test_evaluate_out_of_range_raises() -> None:
    qe = QuantumEfficiency.from_spectral(_sample_spectral())
    with pytest.raises(ValueError, match="outside the QE table range"):
        qe.evaluate(np.array([0.3, 0.5]))  # below
    with pytest.raises(ValueError, match="outside the QE table range"):
        qe.evaluate(np.array([0.5, 1.5]))  # above


@pytest.mark.level1
def test_evaluate_linear_interp() -> None:
    lam = np.array([0.4, 0.8, 1.2])
    vals = np.array([0.0, 0.8, 0.0])
    qe = QuantumEfficiency.from_spectral(_sample_spectral(lam, vals))
    mid = qe.evaluate(np.array([0.6]))[0]
    assert mid == pytest.approx(0.4, rel=1e-12)


@pytest.mark.level1
def test_band_averaged_qe_flat_top() -> None:
    # Flat 0.5 over [0.4, 1.1] → band avg over [0.5, 1.0] is exactly 0.5.
    qe = QuantumEfficiency.from_spectral(
        _sample_spectral(np.linspace(0.4, 1.1, 101), np.full(101, 0.5))
    )
    assert qe.band_averaged_qe(0.5, 1.0) == pytest.approx(0.5, rel=1e-12)


@pytest.mark.level1
def test_band_averaged_qe_rejects_inverted() -> None:
    qe = QuantumEfficiency.from_spectral(_sample_spectral())
    with pytest.raises(ValueError, match="lam_max_um"):
        qe.band_averaged_qe(1.0, 0.5)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_qe_constant_round_trip() -> None:
    qe = QuantumEfficiency.constant(0.65, name="flat_qe")
    d = qe.to_dict()
    restored = QuantumEfficiency.from_dict(d)
    assert restored.name == "flat_qe"
    assert restored.mode == "constant"
    assert np.allclose(restored.table.values, qe.table.values)
    assert np.allclose(restored.table.wavelength_um, qe.table.wavelength_um)


@pytest.mark.level1
def test_qe_spectral_round_trip() -> None:
    data = _sample_spectral(np.linspace(0.4, 1.1, 8), np.linspace(0.1, 0.9, 8))
    qe = QuantumEfficiency.from_spectral(data, name="measured")
    d = qe.to_dict()
    restored = QuantumEfficiency.from_dict(d)
    assert restored.name == "measured"
    assert restored.mode == "spectral"
    assert np.allclose(restored.table.values, qe.table.values)
    assert np.allclose(restored.table.wavelength_um, qe.table.wavelength_um)


# ---------------------------------------------------------------------------
# photon_energy_joules
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_photon_energy_truth_anchor() -> None:
    # Truth anchor: at λ = 0.5 µm, E = hc/λ.
    lam = np.array([0.5])
    e = photon_energy_joules(lam)
    expected = h * c / (0.5e-6)
    assert e[0] == pytest.approx(expected, rel=1e-12)


@pytest.mark.level0
def test_photon_energy_inverse_wavelength_scaling() -> None:
    lam = np.array([0.5, 1.0, 2.0])
    e = photon_energy_joules(lam)
    # E scales as 1/λ: ratios should be exact.
    assert e[0] / e[1] == pytest.approx(2.0, rel=1e-12)
    assert e[0] / e[2] == pytest.approx(4.0, rel=1e-12)


@pytest.mark.level0
def test_photon_energy_rejects_nonpositive() -> None:
    with pytest.raises(ValueError, match="non-positive"):
        photon_energy_joules(np.array([0.0, 0.5]))
    with pytest.raises(ValueError, match="non-positive"):
        photon_energy_joules(np.array([-0.1, 0.5]))
