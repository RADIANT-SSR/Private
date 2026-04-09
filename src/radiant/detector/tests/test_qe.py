"""Tests for radiant.detector.qe."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.constants import c, h
from radiant.core.spectral import SpectralData
from radiant.detector.qe import QuantumEfficiency, photon_energy_joules

# ---------------------------------------------------------------------------
# Parametric factory
# ---------------------------------------------------------------------------


def test_parametric_peak_matches_requested() -> None:
    qe = QuantumEfficiency.parametric(peak=0.8, cuton_um=0.4, cutoff_um=1.1)
    # Mid-band: Fermi · Fermi product saturates to peak to within ~0.2%
    # (never exactly, since σ(x)→1 only asymptotically).
    mid = qe.evaluate(np.array([0.75]))[0]
    assert mid == pytest.approx(0.8, rel=3e-3)
    assert mid <= 0.8 + 1e-12  # strictly bounded above by peak


def test_parametric_plateau_is_flat() -> None:
    qe = QuantumEfficiency.parametric(peak=0.9, cuton_um=0.5, cutoff_um=1.0, rolloff_um=0.02)
    plateau = qe.evaluate(np.array([0.7, 0.75, 0.8, 0.85]))
    assert np.all(plateau > 0.89)
    assert plateau.max() - plateau.min() < 1e-3


def test_parametric_fermi_halfpoint() -> None:
    # Truth anchor 1: at λ = cuton, the short edge is σ(0) = 0.5.
    # The long edge is σ((cutoff-cuton)/w) ≈ 1 for well-separated edges,
    # so QE(cuton) ≈ peak·0.5.
    qe = QuantumEfficiency.parametric(peak=1.0, cuton_um=0.4, cutoff_um=1.1, rolloff_um=0.01)
    val = qe.evaluate(np.array([0.4]))[0]
    assert val == pytest.approx(0.5, abs=1e-3)


def test_parametric_out_of_band_near_zero() -> None:
    qe = QuantumEfficiency.parametric(peak=0.8, cuton_um=0.5, cutoff_um=1.0, rolloff_um=0.01)
    # Sample at the short edge of the table (pad = 8·rolloff = 0.08 µm
    # below cuton), where the Fermi product is < 1e-3 of peak.
    lam0 = qe.table.wavelength_um[0]
    low = qe.evaluate(np.array([lam0]))[0]
    assert low < 1e-3


def test_parametric_rejects_peak_out_of_range() -> None:
    with pytest.raises(ValueError, match="peak"):
        QuantumEfficiency.parametric(peak=1.2, cuton_um=0.4, cutoff_um=1.0)
    with pytest.raises(ValueError, match="peak"):
        QuantumEfficiency.parametric(peak=0.0, cuton_um=0.4, cutoff_um=1.0)


def test_parametric_rejects_inverted_band() -> None:
    with pytest.raises(ValueError, match="cuton_um"):
        QuantumEfficiency.parametric(peak=0.8, cuton_um=1.1, cutoff_um=0.4)


def test_parametric_rejects_nonpositive_rolloff() -> None:
    with pytest.raises(ValueError, match="rolloff_um"):
        QuantumEfficiency.parametric(peak=0.8, cuton_um=0.4, cutoff_um=1.1, rolloff_um=0.0)


def test_parametric_rejects_undersampled_grid() -> None:
    with pytest.raises(ValueError, match="n_samples"):
        QuantumEfficiency.parametric(peak=0.8, cuton_um=0.4, cutoff_um=1.1, n_samples=4)


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


def test_from_spectral_wraps_table() -> None:
    data = _sample_spectral()
    qe = QuantumEfficiency.from_spectral(data)
    out = qe.evaluate(np.array([0.5, 0.7, 1.0]))
    assert np.allclose(out, 0.6)


def test_evaluate_rejects_values_outside_unit_interval() -> None:
    lam = np.linspace(0.4, 1.1, 11)
    with pytest.raises(ValueError, match="out of"):
        QuantumEfficiency.from_spectral(_sample_spectral(lam, np.full_like(lam, 1.5)))
    with pytest.raises(ValueError, match="out of"):
        QuantumEfficiency.from_spectral(_sample_spectral(lam, np.full_like(lam, -0.1)))


def test_evaluate_out_of_range_raises() -> None:
    qe = QuantumEfficiency.from_spectral(_sample_spectral())
    with pytest.raises(ValueError, match="outside the QE table range"):
        qe.evaluate(np.array([0.3, 0.5]))  # below
    with pytest.raises(ValueError, match="outside the QE table range"):
        qe.evaluate(np.array([0.5, 1.5]))  # above


def test_evaluate_linear_interp() -> None:
    lam = np.array([0.4, 0.8, 1.2])
    vals = np.array([0.0, 0.8, 0.0])
    qe = QuantumEfficiency.from_spectral(_sample_spectral(lam, vals))
    mid = qe.evaluate(np.array([0.6]))[0]
    assert mid == pytest.approx(0.4, rel=1e-12)


def test_peak_qe_property() -> None:
    qe = QuantumEfficiency.parametric(peak=0.77, cuton_um=0.4, cutoff_um=1.1)
    # Bounded above by peak; reaches within ~0.3% at mid-band.
    assert qe.peak_qe <= 0.77 + 1e-12
    assert qe.peak_qe == pytest.approx(0.77, rel=3e-3)


def test_band_averaged_qe_flat_top() -> None:
    # Flat 0.5 over [0.4, 1.1] → band avg over [0.5, 1.0] is exactly 0.5.
    qe = QuantumEfficiency.from_spectral(
        _sample_spectral(np.linspace(0.4, 1.1, 101), np.full(101, 0.5))
    )
    assert qe.band_averaged_qe(0.5, 1.0) == pytest.approx(0.5, rel=1e-12)


def test_band_averaged_qe_rejects_inverted() -> None:
    qe = QuantumEfficiency.from_spectral(_sample_spectral())
    with pytest.raises(ValueError, match="lam_max_um"):
        qe.band_averaged_qe(1.0, 0.5)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_qe_round_trip() -> None:
    qe = QuantumEfficiency.parametric(
        peak=0.85, cuton_um=0.5, cutoff_um=1.0, n_samples=64, name="si_ccd"
    )
    d = qe.to_dict()
    restored = QuantumEfficiency.from_dict(d)
    assert restored.name == "si_ccd"
    assert restored.mode == "parametric"
    assert np.allclose(restored.table.values, qe.table.values)
    assert np.allclose(restored.table.wavelength_um, qe.table.wavelength_um)


# ---------------------------------------------------------------------------
# photon_energy_joules
# ---------------------------------------------------------------------------


def test_photon_energy_truth_anchor() -> None:
    # Truth anchor: at λ = 0.5 µm, E = hc/λ.
    lam = np.array([0.5])
    e = photon_energy_joules(lam)
    expected = h * c / (0.5e-6)
    assert e[0] == pytest.approx(expected, rel=1e-12)


def test_photon_energy_inverse_wavelength_scaling() -> None:
    lam = np.array([0.5, 1.0, 2.0])
    e = photon_energy_joules(lam)
    # E scales as 1/λ: ratios should be exact.
    assert e[0] / e[1] == pytest.approx(2.0, rel=1e-12)
    assert e[0] / e[2] == pytest.approx(4.0, rel=1e-12)


def test_photon_energy_rejects_nonpositive() -> None:
    with pytest.raises(ValueError, match="non-positive"):
        photon_energy_joules(np.array([0.0, 0.5]))
    with pytest.raises(ValueError, match="non-positive"):
        photon_energy_joules(np.array([-0.1, 0.5]))
