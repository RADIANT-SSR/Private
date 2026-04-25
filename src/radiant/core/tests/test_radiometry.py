"""Tests for radiant.core.radiometry — RadiometricFrame and NoiseTerm.

All tests are Level 0: dataclass construction and validation contracts on a
single core module (XOR invariants, shape checks, finite-value rejection).
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.radiometry import NoiseTerm, RadiometricFrame

# ---------------------------------------------------------------------------
# RadiometricFrame
# ---------------------------------------------------------------------------


class TestRadiometricFrame:
    """Tests for RadiometricFrame construction and validation."""

    @pytest.fixture()
    def wl(self) -> np.ndarray:
        return np.linspace(3.0, 5.0, 50)

    @pytest.mark.level0
    def test_spectral_radiance_frame(self, wl: np.ndarray) -> None:
        L = np.ones_like(wl) * 1.0
        f = RadiometricFrame(name="test", wavelength_um=wl, spectral_radiance=L)
        assert f.name == "test"
        assert f.spectral_radiance is not None
        assert f.in_band_value is None

    @pytest.mark.level0
    def test_scalar_frame(self, wl: np.ndarray) -> None:
        f = RadiometricFrame(
            name="pe", wavelength_um=wl, in_band_value=1000.0, in_band_unit="e-",
        )
        assert f.in_band_value == pytest.approx(1000.0, rel=1e-12)
        assert f.spectral_radiance is None

    @pytest.mark.level0
    def test_xor_both_set_raises(self, wl: np.ndarray) -> None:
        with pytest.raises(ValueError, match="cannot hold both"):
            RadiometricFrame(
                name="bad",
                wavelength_um=wl,
                spectral_radiance=np.ones_like(wl),
                in_band_value=42.0,
            )

    @pytest.mark.level0
    def test_xor_neither_set_raises(self, wl: np.ndarray) -> None:
        with pytest.raises(ValueError, match="must set either"):
            RadiometricFrame(name="empty", wavelength_um=wl)

    @pytest.mark.level0
    def test_shape_mismatch_raises(self, wl: np.ndarray) -> None:
        with pytest.raises(ValueError, match="shape"):
            RadiometricFrame(
                name="bad",
                wavelength_um=wl,
                spectral_radiance=np.ones(10),  # wrong size
            )

    @pytest.mark.level0
    def test_wavelength_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            RadiometricFrame(
                name="bad",
                wavelength_um=np.array([3.0]),
                spectral_radiance=np.array([1.0]),
            )

    @pytest.mark.level0
    def test_non_finite_scalar_raises(self, wl: np.ndarray) -> None:
        with pytest.raises(ValueError, match="not finite"):
            RadiometricFrame(name="bad", wavelength_um=wl, in_band_value=float("inf"))


# ---------------------------------------------------------------------------
# NoiseTerm
# ---------------------------------------------------------------------------


class TestNoiseTerm:
    @pytest.mark.level0
    def test_valid_construction(self) -> None:
        nt = NoiseTerm(
            name="shot", value_e=100.0, origin_frame="photoelectrons",
            physical_basis="Poisson",
        )
        assert nt.value_e == pytest.approx(100.0, rel=1e-12)

    @pytest.mark.level0
    def test_zero_noise_ok(self) -> None:
        nt = NoiseTerm(
            name="zero", value_e=0.0, origin_frame="pe",
            physical_basis="Poisson",
        )
        assert nt.value_e == 0.0

    @pytest.mark.level0
    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            NoiseTerm(name="bad", value_e=-1.0, origin_frame="pe", physical_basis="x")

    @pytest.mark.level0
    def test_nan_raises(self) -> None:
        with pytest.raises(ValueError, match="not finite"):
            NoiseTerm(name="bad", value_e=float("nan"), origin_frame="pe", physical_basis="x")

    @pytest.mark.level0
    def test_empty_origin_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            NoiseTerm(name="bad", value_e=1.0, origin_frame="", physical_basis="x")

    @pytest.mark.level0
    def test_default_contributes_to(self) -> None:
        nt = NoiseTerm(name="t", value_e=1.0, origin_frame="pe", physical_basis="x")
        assert nt.contributes_to == ("total",)
