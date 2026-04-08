"""Level 0 tests for radiant.core.units.

Verifies convert(), inverse_convert(), and the four physics helper functions:
wavelength_to_wavenumber, wavenumber_to_wavelength, photon_energy_J, photon_rate.
"""

import math

import pytest

from radiant.core.constants import c, h
from radiant.core.units import (
    convert,
    inverse_convert,
    photon_energy_J,
    photon_rate,
    wavelength_to_wavenumber,
    wavenumber_to_wavelength,
)

# ---------------------------------------------------------------------------
# convert() — basic registry tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_convert_identity_m() -> None:
    """convert m -> m returns the same value."""
    assert convert(1.0, "m", "m") == 1.0


@pytest.mark.level0
def test_convert_km_to_m() -> None:
    """1 km = 1000 m."""
    assert convert(1.0, "km", "m") == pytest.approx(1000.0, rel=1e-15)


@pytest.mark.level0
def test_convert_deg_to_rad() -> None:
    """1 deg = π/180 rad."""
    assert convert(1.0, "deg", "rad") == pytest.approx(math.pi / 180.0, rel=1e-15)


@pytest.mark.level0
def test_convert_W_cm2_sr_um_to_W_m2_sr_um() -> None:
    """1 W/cm²/sr/µm = 1e4 W/m²/sr/µm."""
    assert convert(1.0, "W/cm2/sr/um", "W/m2/sr/um") == pytest.approx(1e4, rel=1e-15)


@pytest.mark.level0
def test_convert_same_unit_skips_lookup() -> None:
    """convert with identical from/to returns value without registry lookup."""
    # "furlong" is not in the registry, but same-unit conversion always succeeds
    assert convert(42.0, "furlong", "furlong") == 42.0


@pytest.mark.level0
def test_convert_unregistered_raises_key_error() -> None:
    """convert raises KeyError for unregistered unit pairs."""
    with pytest.raises(KeyError, match="m.*kg"):
        convert(1.0, "m", "kg")


@pytest.mark.level0
def test_convert_urad_to_rad() -> None:
    """1 µrad = 1e-6 rad."""
    assert convert(1.0, "urad", "rad") == pytest.approx(1e-6, rel=1e-15)


@pytest.mark.level0
def test_convert_arcmin_to_rad() -> None:
    """1 arcmin = π/10800 rad."""
    assert convert(1.0, "arcmin", "rad") == pytest.approx(math.pi / 10800.0, rel=1e-15)


@pytest.mark.level0
def test_convert_arcsec_to_rad() -> None:
    """1 arcsec = π/648000 rad."""
    assert convert(1.0, "arcsec", "rad") == pytest.approx(math.pi / 648000.0, rel=1e-15)


# ---------------------------------------------------------------------------
# inverse_convert() — is the inverse of convert()
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_inverse_convert_km_m() -> None:
    """inverse_convert(1000.0, m, km) == 1.0."""
    assert inverse_convert(1000.0, "m", "km") == pytest.approx(1.0, rel=1e-15)


@pytest.mark.level0
def test_inverse_convert_deg_rad() -> None:
    """inverse_convert(π/180, rad, deg) == 1.0."""
    assert inverse_convert(math.pi / 180.0, "rad", "deg") == pytest.approx(1.0, rel=1e-14)


@pytest.mark.level0
def test_inverse_convert_W_cm2_sr_um() -> None:
    """inverse_convert(1e4, W/m2/sr/um, W/cm2/sr/um) == 1.0."""
    assert inverse_convert(1e4, "W/m2/sr/um", "W/cm2/sr/um") == pytest.approx(1.0, rel=1e-15)


@pytest.mark.level0
def test_inverse_convert_unregistered_raises_key_error() -> None:
    """inverse_convert raises KeyError for unregistered unit pairs."""
    with pytest.raises(KeyError):
        inverse_convert(1.0, "m", "kg")


# ---------------------------------------------------------------------------
# wavelength_to_wavenumber — known values and invertibility
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_wavelength_to_wavenumber_known() -> None:
    """λ = 10 µm → ν = 1000 cm⁻¹ exactly."""
    assert wavelength_to_wavenumber(10.0) == 1000.0


@pytest.mark.level0
def test_wavenumber_to_wavelength_known() -> None:
    """ν = 2000 cm⁻¹ → λ = 5.0 µm exactly."""
    assert wavenumber_to_wavelength(2000.0) == 5.0


@pytest.mark.level0
@pytest.mark.parametrize("nu", [100.0, 1000.0, 10000.0])
def test_wavenumber_wavelength_invertibility_from_nu(nu: float) -> None:
    """wavelength_to_wavenumber(wavenumber_to_wavelength(ν)) == ν."""
    assert wavelength_to_wavenumber(wavenumber_to_wavelength(nu)) == pytest.approx(
        nu, rel=1e-15
    )


@pytest.mark.level0
@pytest.mark.parametrize("lam", [0.5, 5.0, 12.0])
def test_wavenumber_wavelength_invertibility_from_lam(lam: float) -> None:
    """wavenumber_to_wavelength(wavelength_to_wavenumber(λ)) == λ."""
    assert wavenumber_to_wavelength(wavelength_to_wavenumber(lam)) == pytest.approx(
        lam, rel=1e-15
    )


# ---------------------------------------------------------------------------
# wavelength_to_wavenumber — edge cases and error handling
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_wavelength_to_wavenumber_zero_raises() -> None:
    """wavelength_to_wavenumber(0.0) raises ValueError."""
    with pytest.raises(ValueError, match="wavelength must be > 0"):
        wavelength_to_wavenumber(0.0)


@pytest.mark.level0
def test_wavelength_to_wavenumber_negative_raises() -> None:
    """wavelength_to_wavenumber(-1.0) raises ValueError."""
    with pytest.raises(ValueError, match="wavelength must be > 0"):
        wavelength_to_wavenumber(-1.0)


@pytest.mark.level0
def test_wavenumber_to_wavelength_zero_raises() -> None:
    """wavenumber_to_wavelength(0.0) raises ValueError."""
    with pytest.raises(ValueError, match="wavenumber must be > 0"):
        wavenumber_to_wavelength(0.0)


@pytest.mark.level0
def test_wavelength_to_wavenumber_tiny_does_not_raise() -> None:
    """wavelength_to_wavenumber(1e-6) is valid (tiny wavelength, large wavenumber)."""
    result = wavelength_to_wavenumber(1e-6)
    assert result == pytest.approx(1e10, rel=1e-15)
    assert math.isfinite(result)


# ---------------------------------------------------------------------------
# photon_energy_J — known values
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_photon_energy_1um() -> None:
    """E(λ=1 µm) = h*c / 1e-6 J."""
    expected = h * c / 1e-6
    assert photon_energy_J(1.0) == pytest.approx(expected, rel=1e-12)


@pytest.mark.level0
def test_photon_energy_10um() -> None:
    """E(λ=10 µm) = h*c / 10e-6 J."""
    expected = h * c / 10e-6
    assert photon_energy_J(10.0) == pytest.approx(expected, rel=1e-12)


@pytest.mark.level0
def test_photon_energy_zero_raises() -> None:
    """photon_energy_J(0.0) raises ValueError."""
    with pytest.raises(ValueError, match="wavelength must be > 0"):
        photon_energy_J(0.0)


@pytest.mark.level0
def test_photon_energy_negative_raises() -> None:
    """photon_energy_J(-1.0) raises ValueError."""
    with pytest.raises(ValueError, match="wavelength must be > 0"):
        photon_energy_J(-1.0)


# ---------------------------------------------------------------------------
# photon_rate — known values and edge cases
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_photon_rate_1W_1um() -> None:
    """photon_rate(1 W, 1 µm) == 1 / photon_energy_J(1.0)."""
    expected = 1.0 / photon_energy_J(1.0)
    assert photon_rate(1.0, 1.0) == pytest.approx(expected, rel=1e-12)


@pytest.mark.level0
def test_photon_rate_zero_power() -> None:
    """photon_rate(0 W, 1 µm) == 0.0: zero power yields zero photon rate."""
    assert photon_rate(0.0, 1.0) == pytest.approx(0.0, abs=1e-30)


@pytest.mark.level0
def test_photon_rate_invalid_wavelength_raises() -> None:
    """photon_rate with invalid wavelength propagates ValueError from photon_energy_J."""
    with pytest.raises(ValueError, match="wavelength must be > 0"):
        photon_rate(1.0, 0.0)
