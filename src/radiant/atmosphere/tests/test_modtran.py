"""Tests for radiant.atmosphere.modtran.

Category C validation for ModtranAtmosphere:
- Unit conversion correctness (Jacobian, cm-1 -> um, W/cm2 -> W/m2)
- Tape7 parsing with synthetic fixture data
- Card deck rendering (correct MODTRAN card values)
- Cache determinism and hit/miss behaviour
- Fallback to SimpleAtmosphere when binary unavailable
- Integral conservation (Jacobian correctness)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import (
    ModtranAtmosphere,
    ModtranConfig,
    ModtranUnavailableError,
    Tape7ParseError,
    Tape7Reader,
    _cache_key,
    _load_cache,
    _save_cache,
    render_tape5,
)
from radiant.atmosphere.protocol import (
    Atmosphere,
    AtmosphericGeometry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_geometry() -> AtmosphericGeometry:
    return AtmosphericGeometry(
        sensor_altitude_m=20_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=0.5,
        solar_azimuth_rad=0.0,
    )


@pytest.fixture()
def default_config(tmp_path: Path) -> ModtranConfig:
    return ModtranConfig(
        binary_path=tmp_path / "fake_modtran",
        cache_dir=tmp_path / "cache",
        allow_fallback=True,
    )


def _write_synthetic_tape7(path: Path, n_points: int = 50) -> np.ndarray:
    """Write a synthetic tape7-like file for testing.

    Returns the wavenumber grid [cm-1] in descending order.
    """
    # Descending wavenumber (MODTRAN convention).
    nu = np.linspace(5000, 2000, n_points)  # ~2-5 um range
    trans = np.exp(-0.1 * (nu / 3000.0))  # synthetic transmittance
    thermal = 1e-6 * (nu / 3000.0) ** 2  # synthetic thermal radiance [W/cm2/sr/cm-1]
    scattered = 0.5e-6 * np.ones_like(nu)  # synthetic scattered
    ground = 0.1e-6 * np.ones_like(nu)

    lines = ["MODTRAN Tape7 Header Line 1", "Column headers line 2"]
    for i in range(n_points):
        lines.append(
            f"{nu[i]:12.2f} {trans[i]:12.6f} {thermal[i]:14.6e} "
            f"{scattered[i]:14.6e} {ground[i]:14.6e}"
        )
    path.write_text("\n".join(lines))
    return nu


# ---------------------------------------------------------------------------
# Unit conversion tests (Level 0 — key equation)
# ---------------------------------------------------------------------------


class TestUnitConversion:
    """Verify the MODTRAN -> RADIANT unit conversion Jacobian."""

    @pytest.mark.level0
    def test_jacobian_preserves_integral(self, tmp_path: Path) -> None:
        """The integral of L(nu) d_nu must equal the integral of L(lambda) d_lambda.

        This is the fundamental correctness check for spectral axis
        conversion.  A flat L(nu) = C provides a simple analytic
        integral in both domains.
        """
        n = 500
        nu_asc = np.linspace(2000, 5000, n)  # cm-1, ascending
        L_nu = 1e-5 * np.ones_like(nu_asc)  # constant [W/cm2/sr/cm-1]

        # Integral in wavenumber space.
        integral_nu = np.trapezoid(L_nu, nu_asc)  # W/cm2/sr

        # Convert to wavelength space (ascending lambda).
        lam = 10000.0 / nu_asc[::-1]  # reverse nu descending -> lam ascending
        nu_for_jac = nu_asc[::-1]
        # Combined Jacobian: L_radiant(lam) [W/m2/sr/um] = L(nu) * nu^2
        L_lam = L_nu[::-1] * nu_for_jac ** 2

        integral_lam = np.trapezoid(L_lam, lam)  # W/m2/sr

        # The integral in wavenumber [W/cm2/sr] * 1e4 should equal
        # the integral in wavelength [W/m2/sr].
        assert integral_lam == pytest.approx(integral_nu * 1e4, rel=1e-3)

    @pytest.mark.level0
    def test_known_conversion_point(self, tmp_path: Path) -> None:
        """Hand-calculated conversion at a single wavenumber.

        At nu = 2500 cm-1 (lambda = 4.0 um):
        L(nu) = 1e-5 W/cm2/sr/cm-1
        L(lam) = L(nu) * nu^2 = 1e-5 * 2500^2 = 62.5 W/m2/sr/um
        """
        tape7 = tmp_path / "tape7"
        # Ascending wavenumber order (lower nu first).
        lines = [
            "Header line",
            "2000.00     0.900000   1.000000e-05   0.000000e+00   0.000000e+00",
            "2500.00     0.800000   1.000000e-05   0.000000e+00   0.000000e+00",
        ]
        tape7.write_text("\n".join(lines))

        reader = Tape7Reader(tape7)
        wl, trans, lp, _ = reader.to_radiant_units()

        # Ascending wavelength: [4.0, 5.0] um
        assert wl[0] == pytest.approx(4.0, abs=1e-10)
        assert wl[1] == pytest.approx(5.0, abs=1e-10)

        # At lambda=4.0 um (nu=2500): L = 1e-5 * 2500^2 = 62.5
        assert lp[0] == pytest.approx(62.5, rel=1e-6)

        # At lambda=5.0 um (nu=2000): L = 1e-5 * 2000^2 = 40.0
        assert lp[1] == pytest.approx(40.0, rel=1e-6)

    @pytest.mark.level0
    def test_transmittance_unchanged(self, tmp_path: Path) -> None:
        """Transmittance is dimensionless and should not be scaled."""
        tape7 = tmp_path / "tape7"
        lines = [
            "Header",
            "2000.00     0.850000   0.000000e+00   0.000000e+00   0.000000e+00",
            "3000.00     0.750000   0.000000e+00   0.000000e+00   0.000000e+00",
        ]
        tape7.write_text("\n".join(lines))

        reader = Tape7Reader(tape7)
        wl, trans, _, _ = reader.to_radiant_units()

        # Sorted to ascending wavelength: lam=3.33 (nu=3000), lam=5.0 (nu=2000)
        assert trans[0] == pytest.approx(0.75, abs=1e-10)  # nu=3000 -> lam=3.33
        assert trans[1] == pytest.approx(0.85, abs=1e-10)  # nu=2000 -> lam=5.0

    @pytest.mark.level1
    def test_ascending_wavelength_output(self, tmp_path: Path) -> None:
        """Output wavelength array must be strictly ascending."""
        _write_synthetic_tape7(tmp_path / "tape7")
        reader = Tape7Reader(tmp_path / "tape7")
        wl, _, _, _ = reader.to_radiant_units()

        assert np.all(np.diff(wl) > 0), "Wavelength must be ascending"


# ---------------------------------------------------------------------------
# Tape7 parsing
# ---------------------------------------------------------------------------


class TestTape7Reader:
    """Parse synthetic tape7 files."""

    @pytest.mark.level1
    def test_parse_synthetic(self, tmp_path: Path) -> None:
        nu = _write_synthetic_tape7(tmp_path / "tape7")
        reader = Tape7Reader(tmp_path / "tape7")
        native = reader.parse()

        assert native.wavenumber_cm1.shape[0] == len(nu)
        assert np.allclose(native.wavenumber_cm1, nu)

    @pytest.mark.level1
    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            Tape7Reader("/nonexistent/tape7")

    @pytest.mark.level1
    def test_empty_file(self, tmp_path: Path) -> None:
        (tmp_path / "tape7").write_text("")
        with pytest.raises(Tape7ParseError, match="no numeric data"):
            Tape7Reader(tmp_path / "tape7").parse()

    @pytest.mark.level1
    def test_header_only_file(self, tmp_path: Path) -> None:
        (tmp_path / "tape7").write_text("Header only\nNo data here\n")
        with pytest.raises(Tape7ParseError, match="no numeric data"):
            Tape7Reader(tmp_path / "tape7").parse()


# ---------------------------------------------------------------------------
# Card deck rendering
# ---------------------------------------------------------------------------


class TestCardDeck:
    """Verify the tape5 card deck is rendered correctly."""

    @pytest.mark.level1
    def test_model_code_mapping(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig(atmosphere_profile="tropical")
        tape5 = render_tape5(config, default_geometry)
        # MODEL=1 for tropical should appear in Card 1.
        assert "1" in tape5.splitlines()[0]

    @pytest.mark.level1
    def test_geometry_in_card3(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig()
        tape5 = render_tape5(config, default_geometry)
        # H1 = 20 km, H2 = 0 km.
        assert "20.000" in tape5
        assert "0.000" in tape5

    @pytest.mark.level1
    def test_spectral_range_in_card4(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig(v1_cm1=800.0, v2_cm1=5000.0)
        tape5 = render_tape5(config, default_geometry)
        assert "800.0" in tape5
        assert "5000.0" in tape5

    @pytest.mark.level1
    def test_deterministic_rendering(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig()
        t1 = render_tape5(config, default_geometry)
        t2 = render_tape5(config, default_geometry)
        assert t1 == t2


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    """Cache key determinism and round-trip."""

    @pytest.mark.level0
    def test_cache_key_deterministic(self) -> None:
        tape5 = "some card deck content\n"
        assert _cache_key(tape5) == _cache_key(tape5)

    @pytest.mark.level0
    def test_cache_key_differs_for_different_decks(self) -> None:
        assert _cache_key("deck_a\n") != _cache_key("deck_b\n")

    @pytest.mark.level1
    def test_cache_round_trip(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        key = "test_key_12345678"
        wl = np.linspace(3.0, 5.0, 10)
        tau = np.linspace(0.9, 0.5, 10)
        lp = np.linspace(0.01, 0.05, 10)
        gr = np.zeros(10)

        _save_cache(cache_dir, key, wl, tau, lp, gr)
        result = _load_cache(cache_dir, key)
        assert result is not None
        wl_r, tau_r, lp_r, gr_r = result

        np.testing.assert_array_equal(wl_r, wl)
        np.testing.assert_array_equal(tau_r, tau)
        np.testing.assert_array_equal(lp_r, lp)

    @pytest.mark.level1
    def test_cache_miss_returns_none(self, tmp_path: Path) -> None:
        result = _load_cache(tmp_path, "nonexistent_key")
        assert result is None


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


class TestFallback:
    """Fallback to SimpleAtmosphere when binary is unavailable."""

    @pytest.mark.level1
    def test_fallback_when_binary_missing(
        self, default_geometry: AtmosphericGeometry, tmp_path: Path,
    ) -> None:
        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=tmp_path / "cache",
            allow_fallback=True,
        )
        model = ModtranAtmosphere(config)
        wl = np.linspace(3.0, 5.0, 50)
        result = model.build_state(wl, default_geometry)

        # Should get a valid AtmosphericState from the fallback.
        assert result.transmittance.values.shape == wl.shape
        assert np.all(result.transmittance.values >= 0.0)
        assert np.all(result.transmittance.values <= 1.0)
        assert np.all(result.path_radiance.values >= 0.0)

    @pytest.mark.level1
    def test_error_when_no_fallback(
        self, default_geometry: AtmosphericGeometry, tmp_path: Path,
    ) -> None:
        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=tmp_path / "cache",
            allow_fallback=False,
        )
        model = ModtranAtmosphere(config)
        wl = np.linspace(3.0, 5.0, 50)
        with pytest.raises(ModtranUnavailableError, match="not found"):
            model.build_state(wl, default_geometry)

    @pytest.mark.level1
    def test_cache_hit_bypasses_binary(
        self, default_geometry: AtmosphericGeometry, tmp_path: Path,
    ) -> None:
        """Pre-populate cache; verify binary is never invoked."""
        cache_dir = tmp_path / "cache"
        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=cache_dir,
            allow_fallback=False,
        )

        # Render the tape5 and pre-populate cache.
        tape5 = render_tape5(config, default_geometry)
        key = _cache_key(tape5)
        wl_cached = np.linspace(3.0, 5.0, 100)
        tau_cached = np.linspace(0.9, 0.5, 100)
        lp_cached = np.linspace(0.01, 0.03, 100)
        gr_cached = np.zeros(100)
        _save_cache(cache_dir, key, wl_cached, tau_cached, lp_cached, gr_cached)

        model = ModtranAtmosphere(config)
        # Query on a sub-grid within the cached range.
        query_wl = np.linspace(3.5, 4.5, 20)
        result = model.build_state(query_wl, default_geometry)

        assert result.transmittance.values.shape == query_wl.shape
        assert np.all(result.transmittance.values >= 0.0)
        assert np.all(result.transmittance.values <= 1.0)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """ModtranConfig validates its parameters."""

    @pytest.mark.level1
    def test_invalid_profile(self) -> None:
        with pytest.raises(ValueError, match="atmosphere_profile"):
            ModtranConfig(atmosphere_profile="martian")

    @pytest.mark.level1
    def test_invalid_aerosol(self) -> None:
        with pytest.raises(ValueError, match="aerosol_model"):
            ModtranConfig(aerosol_model="volcanic")

    @pytest.mark.level1
    def test_negative_h2o_scale(self) -> None:
        with pytest.raises(ValueError, match="h2o_scale"):
            ModtranConfig(h2o_scale=-1.0)

    @pytest.mark.level1
    def test_bad_spectral_range(self) -> None:
        with pytest.raises(ValueError, match="v1_cm1"):
            ModtranConfig(v1_cm1=5000.0, v2_cm1=1000.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocol:
    """ModtranAtmosphere satisfies the Atmosphere protocol."""

    @pytest.mark.level1
    def test_isinstance_check(self, tmp_path: Path) -> None:
        config = ModtranConfig(
            binary_path=tmp_path / "fake",
            allow_fallback=True,
        )
        model = ModtranAtmosphere(config)
        assert isinstance(model, Atmosphere)
