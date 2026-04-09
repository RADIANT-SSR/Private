"""Tests for radiant.core.solar."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.constants import S_solar_W_per_m2
from radiant.core.solar import (
    toa_solar_equivalent_radiance,
    toa_solar_spectral_irradiance,
)


def test_integral_recovers_nominal_s0() -> None:
    """∫ E_sun dλ over the full spectrum = S_0 = 1361 W/m²."""
    lam = np.linspace(0.05, 50.0, 20_001)
    e = toa_solar_spectral_irradiance(lam)
    total = float(np.trapezoid(e, lam))
    # k_scale is calibrated on a 10001-point grid; the 20001-point
    # integral is essentially the same, so we expect < 1e-5 error.
    assert total == pytest.approx(S_solar_W_per_m2, rel=1e-5)


def test_visible_band_irradiance_within_10_percent_of_reference() -> None:
    """∫₀.₄^₀.₇ E_sun dλ ≈ 530 W/m² (ASTM E490 gives ~524 W/m²)."""
    lam = np.linspace(0.4, 0.7, 601)
    e = toa_solar_spectral_irradiance(lam)
    visible = float(np.trapezoid(e, lam))
    # 5778 K blackbody overestimates visible slightly; 10% is plenty
    # of margin for this smoke test.
    assert 470.0 < visible < 590.0


def test_peak_near_500_nm() -> None:
    """Wien displacement: λ_max ≈ 2897.8 / 5778 µm ≈ 0.5017 µm."""
    lam = np.linspace(0.3, 1.0, 2001)
    e = toa_solar_spectral_irradiance(lam)
    lam_peak = float(lam[int(np.argmax(e))])
    assert lam_peak == pytest.approx(0.5017, abs=5e-3)


def test_spectral_shape_matches_planck_curve() -> None:
    """E_sun(λ) should be proportional to B(λ, 5778 K) at every wavelength.

    Taking the ratio at multiple wavelengths should give a constant
    (the product π · dilution · k_scale) to machine precision.
    """
    from radiant.core.blackbody import planck_spectral_radiance

    lam = np.array([0.3, 0.5, 0.7, 1.0, 2.0, 5.0])
    e = toa_solar_spectral_irradiance(lam)
    b = planck_spectral_radiance(lam, 5778.0)
    ratio = e / b
    assert np.allclose(ratio, ratio[0], rtol=1e-12)


def test_equivalent_radiance_is_irradiance_over_pi() -> None:
    lam = np.linspace(0.4, 2.5, 201)
    e = toa_solar_spectral_irradiance(lam)
    radiance = toa_solar_equivalent_radiance(lam)
    assert np.allclose(radiance * np.pi, e, rtol=1e-14)


def test_scalar_input_returns_1d() -> None:
    e = toa_solar_spectral_irradiance(0.55)
    assert e.shape == (1,)
    assert e[0] > 0.0


def test_strictly_positive_over_reasonable_range() -> None:
    lam = np.linspace(0.2, 20.0, 501)
    e = toa_solar_spectral_irradiance(lam)
    assert np.all(e > 0.0)
    assert np.all(np.isfinite(e))


def test_rejects_unknown_model() -> None:
    with pytest.raises(ValueError, match="unknown model"):
        toa_solar_spectral_irradiance(np.array([0.5]), model="mystery_sun")  # type: ignore[arg-type]


def test_rejects_nonpositive_wavelength() -> None:
    # planck_spectral_radiance raises for non-positive wavelengths; the
    # solar wrapper should propagate that cleanly.
    with pytest.raises(ValueError, match="non-positive"):
        toa_solar_spectral_irradiance(np.array([0.0, 0.5]))
