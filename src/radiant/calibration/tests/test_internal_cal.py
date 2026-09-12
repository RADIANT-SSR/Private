"""Level 0 tests for the internal-cal path-mismatch split (Gap 122 item 4).

Key equation (written before the implementation, Rule 18):

    f_fore = ∫_band Σ_{i ∈ fore} E_i(λ) · λ dλ / ∫_band Σ_all E_i(λ) · λ dλ

— the photon-weighted (each W of in-band power carries λ/hc photons; hc
cancels in the ratio) fraction of the near-field FPA irradiance emitted by
elements in FRONT of the internal cal shutter. During an internal-shutter
cal the flag blocks the fore-optics, so the NUC never sees their emission;
in operation that emission returns as an uncorrected offset.

Hand anchors:
    A: flat spectra 1.0 vs 3.0 W/m²/µm — λ-weighting cancels → 0.25 exactly.
    B: A(λ) = 1/λ vs B(λ) = 1 on [4, 5] µm:
       ∫(1/λ)·λ dλ = 1.0;  ∫1·λ dλ = (25 − 16)/2 = 4.5 → f = 1/5.5.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.calibration.internal_cal import fore_optics_fraction
from radiant.core.spectral import SpectralData


def _sd(name: str, wl: np.ndarray, values: np.ndarray) -> SpectralData:
    return SpectralData(name=name, wavelength_um=wl, values=values, unit="W/m^2/um", source="test")


_WL = np.linspace(4.0, 5.0, 501)


class TestForeOpticsFraction:
    @pytest.mark.level0
    def test_flat_spectra_anchor(self) -> None:
        """Hand anchor A: flat 1.0 vs 3.0 — exactly 0.25."""
        per = {
            "primary": _sd("a", _WL, np.full_like(_WL, 1.0)),
            "relay": _sd("b", _WL, np.full_like(_WL, 3.0)),
        }
        f = fore_optics_fraction(
            per_element=per, fore_names=("primary",), lam_min_um=4.0, lam_max_um=5.0
        )
        assert f == pytest.approx(0.25, rel=1e-9)

    @pytest.mark.level0
    def test_spectral_anchor(self) -> None:
        """Hand anchor B: 1/λ vs flat → 1/5.5, photon weighting live."""
        per = {
            "primary": _sd("a", _WL, 1.0 / _WL),
            "relay": _sd("b", _WL, np.full_like(_WL, 1.0)),
        }
        f = fore_optics_fraction(
            per_element=per, fore_names=("primary",), lam_min_um=4.0, lam_max_um=5.0
        )
        assert f == pytest.approx(1.0 / 5.5, rel=1e-4)

    @pytest.mark.level0
    def test_band_mask_excludes_out_of_band_power(self) -> None:
        """Emission outside the sensing band cannot bias the split."""
        wl = np.linspace(3.0, 5.0, 1001)
        a = np.where(wl < 4.0, 10.0, 1.0)  # loud only out of band
        per = {
            "primary": _sd("a", wl, a),
            "relay": _sd("b", wl, np.full_like(wl, 1.0)),
        }
        f = fore_optics_fraction(
            per_element=per, fore_names=("primary",), lam_min_um=4.0, lam_max_um=5.0
        )
        assert f == pytest.approx(0.5, rel=1e-6)

    @pytest.mark.level0
    def test_all_fore_is_one_and_none_is_zero(self) -> None:
        per = {
            "primary": _sd("a", _WL, np.full_like(_WL, 2.0)),
            "relay": _sd("b", _WL, np.full_like(_WL, 1.0)),
        }
        kwargs: dict[str, object] = {"per_element": per, "lam_min_um": 4.0, "lam_max_um": 5.0}
        assert fore_optics_fraction(fore_names=("primary", "relay"), **kwargs) == 1.0
        assert fore_optics_fraction(fore_names=(), **kwargs) == 0.0

    @pytest.mark.level0
    def test_cold_fore_element_missing_from_map_contributes_zero(self) -> None:
        """A 0 K element never enters per_element — it emits nothing, so the
        name simply contributes zero rather than erroring."""
        per = {"relay": _sd("b", _WL, np.full_like(_WL, 1.0))}
        f = fore_optics_fraction(
            per_element=per,
            fore_names=("cold_primary",),
            lam_min_um=4.0,
            lam_max_um=5.0,
        )
        assert f == 0.0

    @pytest.mark.level0
    def test_zero_total_emission_is_zero_fraction(self) -> None:
        """No near-field emission at all → no mismatch, not a 0/0 NaN."""
        per = {"primary": _sd("a", _WL, np.zeros_like(_WL))}
        f = fore_optics_fraction(
            per_element=per, fore_names=("primary",), lam_min_um=4.0, lam_max_um=5.0
        )
        assert f == 0.0

    @pytest.mark.level0
    def test_empty_map_is_zero(self) -> None:
        f = fore_optics_fraction(
            per_element={}, fore_names=("primary",), lam_min_um=4.0, lam_max_um=5.0
        )
        assert f == 0.0
