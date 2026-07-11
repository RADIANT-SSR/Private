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

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import (
    ModtranAtmosphere,
    ModtranConfig,
    ModtranUnavailableError,
    Tape7Import,
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

    Headerless (no "FREQ" column-header line) — exercises the CU-066
    positional-fallback path, which always warns.

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


def _write_realistic_tape7(path: Path, n_points: int = 20) -> dict[str, np.ndarray]:
    """Write a manual-faithful IEMSCT=2 tape7: numeric card echo, then a
    named 10-column header, then data (CU-066 regression fixture).

    THRML SCT and SURF EMIS are given DISTINCT, easily-distinguished
    values from SOL SCAT and GRNDRFLT so a positional (pre-CU-066)
    reader and a name-based reader disagree observably.

    Returns the per-column arrays (descending wavenumber) keyed by
    their RADIANT semantic field names, for the test to compare
    against ``ModtranNativeOutput``.
    """
    nu = np.linspace(5000, 2000, n_points)  # descending, MODTRAN convention
    tot_trans = np.full_like(nu, 0.80)
    pth_thrml = np.full_like(nu, 1.0e-6)
    thrml_sct = np.full_like(nu, 9.0e-6)  # decoy: must NOT land in path_scattered
    surf_emis = np.full_like(nu, 8.0e-6)  # decoy: must NOT land in ground_reflected
    sol_scat = np.full_like(nu, 2.0e-6)  # real path_scattered_radiance source
    sngl_scat = np.full_like(nu, 7.0e-6)
    grnd_rflt = np.full_like(nu, 3.0e-6)  # real ground_reflected_radiance source
    drct_rflt = np.full_like(nu, 6.0e-6)
    total_rad = pth_thrml + thrml_sct + surf_emis + sol_scat + grnd_rflt

    lines = [
        # Numeric card-echo lines: a headerless-scan reader (pre-CU-066)
        # would mistake these for spectral data since they start with
        # numbers; a header-anchored reader must skip them.
        "    1    5    0    6    0    2    2    1    0    0    0    1    0  0.000",
        "    1    0    0    0    0    0  0.000  0.000  0.000  0.000  0.000",
        "CARD 3    20.000     0.000     0.000     0.000     0.000     0    0.000",
        (
            "   FREQ   TOT TRANS   PTH THRML   THRML SCT   SURF EMIS   "
            "SOL SCAT   SNGL SCAT   GRND RFLT   DRCT RFLT   TOTAL RAD"
        ),
    ]
    for i in range(n_points):
        lines.append(
            f"{nu[i]:12.2f}{tot_trans[i]:12.6f}{pth_thrml[i]:12.4e}"
            f"{thrml_sct[i]:12.4e}{surf_emis[i]:12.4e}{sol_scat[i]:12.4e}"
            f"{sngl_scat[i]:12.4e}{grnd_rflt[i]:12.4e}{drct_rflt[i]:12.4e}"
            f"{total_rad[i]:12.4e}"
        )
    path.write_text("\n".join(lines))
    return {
        "wavenumber_cm1": nu,
        "total_transmittance": tot_trans,
        "path_thermal_radiance": pth_thrml,
        "path_scattered_radiance": sol_scat,
        "ground_reflected_radiance": grnd_rflt,
    }


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
        L_lam = L_nu[::-1] * nu_for_jac**2

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
        with pytest.warns(UserWarning, match="CU-066"):
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
        with pytest.warns(UserWarning, match="CU-066"):
            wl, trans, _, _ = reader.to_radiant_units()

        # Sorted to ascending wavelength: lam=3.33 (nu=3000), lam=5.0 (nu=2000)
        assert trans[0] == pytest.approx(0.75, abs=1e-10)  # nu=3000 -> lam=3.33
        assert trans[1] == pytest.approx(0.85, abs=1e-10)  # nu=2000 -> lam=5.0

    @pytest.mark.level1
    def test_ascending_wavelength_output(self, tmp_path: Path) -> None:
        """Output wavelength array must be strictly ascending."""
        _write_synthetic_tape7(tmp_path / "tape7")
        reader = Tape7Reader(tmp_path / "tape7")
        with pytest.warns(UserWarning, match="CU-066"):
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
        with pytest.warns(UserWarning, match="CU-066"):
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


class TestTape7ReaderNamedColumns:
    """CU-066: header-name-based column mapping on a manual-faithful tape7.

    Regression coverage for the two silent-misassignment defects found
    in the pre-fix positional reader: THRML SCT masquerading as
    path_scattered_radiance (real column: SOL SCAT) and SURF EMIS
    masquerading as ground_reflected_radiance (real column: GRND
    RFLT); plus the numeric-card-echo-as-data defect (data start was
    "first line with a numeric first field", which a real tape7's
    card echo satisfies before the header even appears).
    """

    @pytest.mark.level1
    def test_no_warning_with_named_header(self, tmp_path: Path) -> None:
        """A labeled header must NOT trigger the positional-fallback warning."""
        _write_realistic_tape7(tmp_path / "tape7")
        reader = Tape7Reader(tmp_path / "tape7")
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning fails the test
            native = reader.parse()
        assert native.wavenumber_cm1.shape[0] == 20

    @pytest.mark.level1
    def test_scattered_and_ground_reflected_not_swapped(self, tmp_path: Path) -> None:
        """path_scattered <- SOL SCAT and ground_reflected <- GRND RFLT,
        NOT the decoy THRML SCT / SURF EMIS columns (CU-066 defect)."""
        expected = _write_realistic_tape7(tmp_path / "tape7")
        native = Tape7Reader(tmp_path / "tape7").parse()

        np.testing.assert_allclose(
            native.path_scattered_radiance, expected["path_scattered_radiance"]
        )
        np.testing.assert_allclose(
            native.ground_reflected_radiance, expected["ground_reflected_radiance"]
        )
        # The decoy values (9e-6, 8e-6) must not appear in either field.
        assert not np.allclose(native.path_scattered_radiance, 9.0e-6)
        assert not np.allclose(native.ground_reflected_radiance, 8.0e-6)

    @pytest.mark.level1
    def test_card_echo_lines_excluded_from_data(self, tmp_path: Path) -> None:
        """Numeric card-echo lines preceding the header must not be
        parsed as spectral data rows."""
        expected = _write_realistic_tape7(tmp_path / "tape7")
        native = Tape7Reader(tmp_path / "tape7").parse()

        assert native.wavenumber_cm1.shape[0] == len(expected["wavenumber_cm1"])
        # rtol accounts for the fixture's %12.2f text round-trip, not the
        # reader under test.
        np.testing.assert_allclose(native.wavenumber_cm1, expected["wavenumber_cm1"], rtol=1e-5)
        np.testing.assert_allclose(native.total_transmittance, expected["total_transmittance"])

    @pytest.mark.level1
    def test_missing_required_label_raises(self, tmp_path: Path) -> None:
        """A named header lacking a required RADIANT field (here, no
        GRND RFLT column at all) raises rather than silently zeroing."""
        lines = [
            "   FREQ   TOT TRANS   PTH THRML   SOL SCAT",
            "5000.00     0.800000   1.0000e-06   2.0000e-06",
            "4000.00     0.800000   1.0000e-06   2.0000e-06",
        ]
        (tmp_path / "tape7").write_text("\n".join(lines))
        with pytest.raises(Tape7ParseError, match="missing required label"):
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
    def test_default_card1_card2_unchanged(self, default_geometry: AtmosphericGeometry) -> None:
        """CU-063/064 defaults must reproduce the pre-change deck exactly
        (visibility_km=None, iemsct=2) — no behavior change for existing
        callers."""
        tape5 = render_tape5(ModtranConfig(), default_geometry)
        lines = tape5.splitlines()
        assert lines[0] == "T    5    0    6    0    2    2    1    0    0    0    1    0  0.000"
        assert lines[2] == "    1    0    0    0    0    0  0.000  0.000  0.000  0.000  0.000"

    @pytest.mark.level1
    def test_visibility_km_in_card2(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig(visibility_km=8.5)
        tape5 = render_tape5(config, default_geometry)
        assert "8.500" in tape5.splitlines()[2]

    @pytest.mark.level1
    def test_visibility_km_none_keeps_zero(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig(visibility_km=None)
        tape5 = render_tape5(config, default_geometry)
        assert tape5.splitlines()[2].count("0.000") == 5

    @pytest.mark.level1
    def test_iemsct_solar_irradiance_mode(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig(iemsct=3)
        tape5 = render_tape5(config, default_geometry)
        card1 = tape5.splitlines()[0]
        assert card1 == "T    5    0    6    0    2    3    1    0    0    0    1    0  0.000"

    @pytest.mark.level1
    def test_itype_slant_to_space(self, default_geometry: AtmosphericGeometry) -> None:
        """CU-069: ITYPE=3 for solar-irradiance-mode runs looking to space."""
        config = ModtranConfig(itype=3, iemsct=3)
        tape5 = render_tape5(config, default_geometry)
        card1 = tape5.splitlines()[0]
        assert card1 == "T    5    0    6    0    3    3    1    0    0    0    1    0  0.000"

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
        self,
        default_geometry: AtmosphericGeometry,
        tmp_path: Path,
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
        self,
        default_geometry: AtmosphericGeometry,
        tmp_path: Path,
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
        self,
        default_geometry: AtmosphericGeometry,
        tmp_path: Path,
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

    @pytest.mark.level1
    def test_negative_visibility_km(self) -> None:
        with pytest.raises(ValueError, match="visibility_km"):
            ModtranConfig(visibility_km=-5.0)

    @pytest.mark.level1
    def test_zero_visibility_km(self) -> None:
        with pytest.raises(ValueError, match="visibility_km"):
            ModtranConfig(visibility_km=0.0)

    @pytest.mark.level1
    def test_invalid_iemsct(self) -> None:
        with pytest.raises(ValueError, match="iemsct"):
            ModtranConfig(iemsct=4)

    @pytest.mark.level1
    def test_invalid_itype(self) -> None:
        with pytest.raises(ValueError, match="itype"):
            ModtranConfig(itype=0)


# ---------------------------------------------------------------------------
# Tape7 file import (atmosphere.modtran.tape7_path)
# ---------------------------------------------------------------------------


class TestTape7Import:
    """First-class tape7 file import — no binary, no cache, no fallback."""

    @pytest.mark.level1
    def test_from_file_matches_reader(self, tmp_path: Path) -> None:
        """Tape7Import.from_file wraps Tape7Reader.to_radiant_units verbatim."""
        tape7 = tmp_path / "run.tp7"
        _write_realistic_tape7(tape7)

        imp = Tape7Import.from_file(tape7)
        wl, tau, lp, gr = Tape7Reader(tape7).to_radiant_units()

        np.testing.assert_array_equal(imp.wavelength_um, wl)
        np.testing.assert_array_equal(imp.transmittance, tau)
        np.testing.assert_array_equal(imp.path_radiance, lp)
        np.testing.assert_array_equal(imp.ground_reflected, gr)
        assert imp.source_path == str(tape7)
        assert len(imp.content_key) == 16
        assert all(c in "0123456789abcdef" for c in imp.content_key)

    @pytest.mark.level1
    def test_from_file_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="tape7"):
            Tape7Import.from_file(tmp_path / "nope.tp7")

    @pytest.mark.level1
    def test_build_state_from_file_needs_no_binary(
        self,
        default_geometry: AtmosphericGeometry,
        tmp_path: Path,
    ) -> None:
        """File import works with no binary, no cache, and fallback OFF."""
        tape7 = tmp_path / "run.tp7"
        _write_realistic_tape7(tape7)
        imp = Tape7Import.from_file(tape7)

        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=tmp_path / "cache",
            allow_fallback=False,
        )
        model = ModtranAtmosphere(config, tape7_import=imp)
        query_wl = np.linspace(2.5, 4.5, 40)
        state = model.build_state(query_wl, default_geometry)

        # Values are the imported arrays resampled to the query grid.
        expected_tau = np.interp(query_wl, imp.wavelength_um, imp.transmittance)
        np.testing.assert_allclose(state.transmittance.values, expected_tau, rtol=1e-12)
        assert any("tape7 import" in step for step in state.derivation_chain)
        assert imp.content_key in " ".join(state.derivation_chain)
        # No cache entry was created — the cache path is never consulted.
        assert not (tmp_path / "cache").exists()

    @pytest.mark.level1
    def test_file_wins_over_cache(
        self,
        default_geometry: AtmosphericGeometry,
        tmp_path: Path,
    ) -> None:
        """Precedence: tape7_path beats a pre-populated cache entry."""
        tape7 = tmp_path / "run.tp7"
        _write_realistic_tape7(tape7)  # TOT TRANS = 0.80 everywhere
        imp = Tape7Import.from_file(tape7)

        cache_dir = tmp_path / "cache"
        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=cache_dir,
            allow_fallback=False,
        )
        # Pre-populate the cache the binary path would hit.
        tape5 = render_tape5(config, default_geometry)
        wl_cached = np.linspace(2.0, 5.0, 50)
        _save_cache(
            cache_dir,
            _cache_key(tape5),
            wl_cached,
            np.full(50, 0.123),  # decoy transmittance != 0.80
            np.zeros(50),
            np.zeros(50),
        )

        model = ModtranAtmosphere(config, tape7_import=imp)
        state = model.build_state(np.linspace(2.5, 4.5, 20), default_geometry)
        np.testing.assert_allclose(state.transmittance.values, np.full(20, 0.80), rtol=0, atol=1e-6)

    @pytest.mark.level1
    def test_evaluate_single_file_warns_and_aliases_tau(self, tmp_path: Path) -> None:
        """One imported file still collapses the two-leg split — with the warning."""
        from radiant.api.session import RadiantSession
        from radiant.core.los_geometry import LineOfSightGeometry

        tape7 = tmp_path / "run.tp7"
        _write_realistic_tape7(tape7)
        imp = Tape7Import.from_file(tape7)
        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=tmp_path / "cache",
            allow_fallback=False,
        )
        model = ModtranAtmosphere(config, tape7_import=imp)

        wl = np.linspace(2.5, 4.5, 30)
        params = _resolved_params_for_evaluate(RadiantSession, wl)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=0.5, delta_phi=0.0)

        with pytest.warns(UserWarning, match="two-leg"):
            atm = model.evaluate(wl, los, params)
        np.testing.assert_array_equal(atm.tau_sun, atm.tau_up)
        np.testing.assert_array_equal(atm.tau_up, atm.tau_full_up)

    @pytest.mark.level1
    def test_evaluate_airborne_target_raises(self, tmp_path: Path) -> None:
        """File import is a single column — h_tgt > 0 must fail loud (Rule 17)."""
        from radiant.api.session import RadiantSession
        from radiant.core.los_geometry import LineOfSightGeometry

        tape7 = tmp_path / "run.tp7"
        _write_realistic_tape7(tape7)
        imp = Tape7Import.from_file(tape7)
        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            allow_fallback=False,
        )
        model = ModtranAtmosphere(config, tape7_import=imp)

        wl = np.linspace(2.5, 4.5, 30)
        params = _resolved_params_for_evaluate(RadiantSession, wl)
        los = LineOfSightGeometry(h_tgt=5000.0, theta_o=0.0)
        with pytest.raises(NotImplementedError, match="tape7 file-import"):
            model.evaluate(wl, los, params)


def _resolved_params_for_evaluate(session_cls: type, wavelength_um: np.ndarray) -> object:
    """Minimal resolved ParameterSet for ModtranAtmosphere.evaluate tests."""
    session = session_cls(wavelength_um=wavelength_um)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "modtran")
    params.set("geometry.sensor_altitude_m", 20_000.0)
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", float(wavelength_um[0]))
    params.set("spectral_integration.filter_max_um", float(wavelength_um[-1]))
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()
    return params


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
