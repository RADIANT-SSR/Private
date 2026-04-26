"""Tests for SpectralLibrary — detector QE curve loading and validation."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.data.library import SpectralLibrary


@pytest.fixture
def lib() -> SpectralLibrary:
    return SpectralLibrary()


@pytest.mark.level1
class TestDetectorsList:
    """Test listing available detectors."""

    def test_detectors_returns_list(self, lib: SpectralLibrary) -> None:
        detectors = lib.detectors()
        assert isinstance(detectors, list)
        assert len(detectors) >= 6

    def test_detectors_sorted(self, lib: SpectralLibrary) -> None:
        detectors = lib.detectors()
        assert detectors == sorted(detectors)

    def test_known_detectors_present(self, lib: SpectralLibrary) -> None:
        detectors = lib.detectors()
        for name in ["silicon", "ingaas", "hgcdte_mwir", "hgcdte_lwir"]:
            assert name in detectors


@pytest.mark.level1
class TestDetectorQELoading:
    """Test loading and validating detector QE spectra."""

    def test_load_silicon(self, lib: SpectralLibrary) -> None:
        sd = lib.detector_qe("silicon")
        assert sd.name == "qe_silicon"
        assert sd.unit == "dimensionless"
        assert len(sd.wavelength_um) >= 10

    def test_qe_range(self, lib: SpectralLibrary) -> None:
        """All QE values must be in [0, 1]."""
        for name in lib.detectors():
            sd = lib.detector_qe(name)
            assert np.all(sd.values >= 0.0), f"{name}: QE < 0"
            assert np.all(sd.values <= 1.0), f"{name}: QE > 1"

    def test_wavelength_ascending(self, lib: SpectralLibrary) -> None:
        """Wavelengths must be strictly ascending."""
        for name in lib.detectors():
            sd = lib.detector_qe(name)
            assert np.all(np.diff(sd.wavelength_um) > 0), f"{name}: not ascending"

    def test_peak_qe_reasonable(self, lib: SpectralLibrary) -> None:
        """Peak QE should be in a reasonable range (0.3–1.0)."""
        for name in lib.detectors():
            sd = lib.detector_qe(name)
            peak = float(np.max(sd.values))
            assert 0.3 <= peak <= 1.0, (
                f"{name}: peak QE {peak:.3f} outside reasonable range"
            )

    def test_cutoff_behavior(self, lib: SpectralLibrary) -> None:
        """QE at the long-wavelength end should drop (last value < peak)."""
        for name in lib.detectors():
            sd = lib.detector_qe(name)
            peak = float(np.max(sd.values))
            last = float(sd.values[-1])
            assert last < peak, (
                f"{name}: QE at longest wavelength ({last:.3f}) "
                f"should be below peak ({peak:.3f})"
            )

    def test_silicon_cutoff_near_1um(self, lib: SpectralLibrary) -> None:
        """Silicon QE should drop sharply beyond ~1.0 µm."""
        sd = lib.detector_qe("silicon")
        # QE at wavelengths > 1.0 µm should be small
        mask = sd.wavelength_um > 1.05
        if np.any(mask):
            assert float(np.max(sd.values[mask])) < 0.3

    def test_hgcdte_mwir_band(self, lib: SpectralLibrary) -> None:
        """HgCdTe MWIR should have reasonable QE in 3–5 µm."""
        sd = lib.detector_qe("hgcdte_mwir")
        mask = (sd.wavelength_um >= 3.0) & (sd.wavelength_um <= 5.0)
        assert np.any(mask)
        mean_qe = float(np.mean(sd.values[mask]))
        assert mean_qe > 0.4, f"HgCdTe MWIR mean QE in 3-5 µm: {mean_qe:.3f}"

    def test_unknown_detector_raises(self, lib: SpectralLibrary) -> None:
        with pytest.raises(KeyError, match="Unknown detector material"):
            lib.detector_qe("unobtainium_detector")
