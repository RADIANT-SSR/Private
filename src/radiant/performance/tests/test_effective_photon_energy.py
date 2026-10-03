"""Level 0: the detected-photon-weighted mean photon energy (Gap 135)."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.constants import c, h
from radiant.performance.effective_photon_energy import effective_photon_energy
from radiant.performance.errors import PerformanceValidationError


def _E(lam_um: float) -> float:
    """Photon energy [J] at *lam_um*, by hand."""
    return h * c / (lam_um * 1e-6)


class TestAgainstHandCalculation:
    @pytest.mark.level0
    def test_a_monochromatic_band_is_its_own_photon_energy(self) -> None:
        wl = np.array([4.0])
        r = effective_photon_energy(wl, np.array([1.0]))
        assert r.energy_j == pytest.approx(_E(4.0), rel=1e-12)
        assert r.lambda_eff_um == pytest.approx(4.0, rel=1e-12)

    @pytest.mark.level0
    def test_a_narrow_flat_band_sits_at_its_centre(self) -> None:
        wl = np.linspace(3.999, 4.001, 64)
        r = effective_photon_energy(wl, np.ones_like(wl))
        assert r.lambda_eff_um == pytest.approx(4.0, rel=1e-6)

    @pytest.mark.level0
    def test_the_round_trip_is_exact(self) -> None:
        """lambda_eff is hc/E_eff back-solved, so it must invert exactly."""
        wl = np.linspace(3.5, 5.0, 256)
        r = effective_photon_energy(wl, np.ones_like(wl))
        assert _E(r.lambda_eff_um) == pytest.approx(r.energy_j, rel=1e-12)


class TestItIsAnEnergyAverageNotAWavelengthAverage:
    """The distinction the module exists to get right."""

    @pytest.mark.level0
    def test_energy_average_exceeds_the_energy_at_the_mean_wavelength(self) -> None:
        """Jensen: <hc/lambda> > hc/<lambda> for a non-degenerate band."""
        wl = np.linspace(3.5, 5.0, 512)
        r = effective_photon_energy(wl, np.ones_like(wl))
        mean_lambda = float(np.trapezoid(wl, wl)) / (wl[-1] - wl[0])
        assert r.energy_j > _E(mean_lambda)

    @pytest.mark.level0
    def test_so_lambda_eff_is_shorter_than_the_mean_wavelength(self) -> None:
        wl = np.linspace(3.5, 5.0, 512)
        r = effective_photon_energy(wl, np.ones_like(wl))
        mean_lambda = float(np.trapezoid(wl, wl)) / (wl[-1] - wl[0])
        assert r.lambda_eff_um < mean_lambda


class TestWeighting:
    @pytest.mark.level0
    def test_qe_shifts_the_average_toward_where_it_detects(self) -> None:
        """A QE favouring the blue end must raise the mean photon energy."""
        wl = np.linspace(3.5, 5.0, 512)
        flat = np.ones_like(wl)
        blue = np.linspace(1.0, 0.0, wl.size)  # falls off toward long lambda
        unweighted = effective_photon_energy(wl, flat)
        weighted = effective_photon_energy(wl, flat, qe=blue)
        assert weighted.energy_j > unweighted.energy_j
        assert weighted.lambda_eff_um < unweighted.lambda_eff_um

    @pytest.mark.level0
    def test_only_the_shape_of_the_flux_matters(self) -> None:
        """The weighting normalises, so scaling the flux changes nothing."""
        wl = np.linspace(3.5, 5.0, 128)
        flux = np.linspace(1.0, 2.0, 128)
        a = effective_photon_energy(wl, flux)
        b = effective_photon_energy(wl, flux * 1.0e9)
        assert a.energy_j == pytest.approx(b.energy_j, rel=1e-12)

    @pytest.mark.level0
    def test_a_flat_qe_changes_nothing(self) -> None:
        wl = np.linspace(3.5, 5.0, 128)
        flux = np.ones_like(wl)
        a = effective_photon_energy(wl, flux)
        b = effective_photon_energy(wl, flux, qe=np.full_like(wl, 0.7))
        assert a.energy_j == pytest.approx(b.energy_j, rel=1e-12)


class TestInvalidInput:
    @pytest.mark.level0
    def test_shape_mismatch_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="does not match"):
            effective_photon_energy(np.linspace(1, 2, 5), np.ones(4))

    @pytest.mark.level0
    def test_qe_shape_mismatch_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="qe shape"):
            effective_photon_energy(np.linspace(1, 2, 5), np.ones(5), qe=np.ones(4))

    @pytest.mark.level0
    def test_empty_band_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="empty"):
            effective_photon_energy(np.array([]), np.array([]))

    @pytest.mark.level0
    def test_non_positive_wavelength_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="strictly positive"):
            effective_photon_energy(np.array([0.0, 1.0]), np.ones(2))

    @pytest.mark.level0
    def test_negative_flux_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="non-negative"):
            effective_photon_energy(np.linspace(1, 2, 4), np.array([1.0, -1.0, 1.0, 1.0]))

    @pytest.mark.level0
    def test_zero_flux_is_undefined_not_zero(self) -> None:
        """No detected photons means no mean energy — say so, do not return 0."""
        wl = np.linspace(3.5, 5.0, 16)
        with pytest.raises(PerformanceValidationError, match="undefined"):
            effective_photon_energy(wl, np.zeros_like(wl))
