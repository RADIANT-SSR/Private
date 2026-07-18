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
    ModtranFluxReader,
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


def _write_realistic_tape7(
    path: Path, n_points: int = 20, tot_trans_value: float = 0.80
) -> dict[str, np.ndarray]:
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
    tot_trans = np.full_like(nu, tot_trans_value)
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


def _write_modtran6_tape7(
    path: Path, n_points: int = 20, tot_trans_value: float = 0.80
) -> dict[str, np.ndarray]:
    """Write a MODTRAN 6 (underscore-header) IEMSCT=2 tape7 (CU-154).

    MODTRAN 6 tape7 uses single-token underscore column labels and
    splits the classic combined ``SOL SCAT`` column into ``MULT_SCAT``
    (multiple) + ``SING_SCAT`` (single); the expected
    path_scattered_radiance is their sum. ``THRML_SCT`` / ``SURF_EMIS``
    / ``DRCT_RFLT`` carry distinct decoy values that must not leak into
    any consumed field. The block terminates with MODTRAN's ``-9999.``
    end-of-data sentinel — a lone float that must NOT be read as a data
    row.

    Returns the per-column expected arrays keyed by RADIANT semantic
    field name, in descending-wavenumber order.
    """
    nu = np.linspace(5000, 2000, n_points)  # descending, MODTRAN convention
    tot_trans = np.full_like(nu, tot_trans_value)
    thrml_em = np.full_like(nu, 1.0e-6)
    thrml_sct = np.full_like(nu, 9.0e-6)  # decoy: must NOT reach path_scattered
    surf_emis = np.full_like(nu, 8.0e-6)  # decoy: must NOT reach ground_reflected
    mult_scat = np.full_like(nu, 2.0e-6)  # real solar multiple scatter
    sing_scat = np.full_like(nu, 5.0e-7)  # real solar single scatter
    grnd_rflt = np.full_like(nu, 3.0e-6)  # real ground_reflected_radiance
    drct_rflt = np.full_like(nu, 6.0e-6)  # decoy
    total_rad = thrml_em + thrml_sct + surf_emis + mult_scat + sing_scat + grnd_rflt
    ref_sol = np.zeros_like(nu)
    sol_obs = np.zeros_like(nu)
    depth = np.full_like(nu, 30.0)
    dir_em = np.ones_like(nu)
    toa_sun = np.full_like(nu, 1.2e-7)
    bbody_t = np.full_like(nu, 250.0)

    lines = [
        # Numeric card-echo lines preceding the header (must be skipped).
        "    1    1    1    3    0    0  23.00000   0.00000   0.00000",
        "   361976 U S STANDARD",
        (
            "    FREQ  TOT_TRANS   THRML_EM  THRML_SCT  SURF_EMIS  "
            "MULT_SCAT  SING_SCAT  GRND_RFLT  DRCT_RFLT  TOTAL_RAD  "
            "REF_SOL  SOL@OBS   DEPTH DIR_EM    TOA_SUN BBODY_T[K]"
        ),
    ]
    for i in range(n_points):
        vals = [
            nu[i], tot_trans[i], thrml_em[i], thrml_sct[i], surf_emis[i],
            mult_scat[i], sing_scat[i], grnd_rflt[i], drct_rflt[i], total_rad[i],
            ref_sol[i], sol_obs[i], depth[i], dir_em[i], toa_sun[i], bbody_t[i],
        ]
        lines.append(" ".join(f"{v:.6e}" for v in vals))
    lines.append("  -9999.")  # MODTRAN end-of-block sentinel
    path.write_text("\n".join(lines))
    return {
        "wavenumber_cm1": nu,
        "total_transmittance": tot_trans,
        "path_thermal_radiance": thrml_em,
        "path_scattered_radiance": mult_scat + sing_scat,
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
        with pytest.raises(Tape7ParseError, match="missing required column"):
            Tape7Reader(tmp_path / "tape7").parse()


class TestTape7ReaderModtran6:
    """CU-154: MODTRAN 6 underscore-header tape7 variant.

    The first real MODTRAN run set (2026-07-17) is MODTRAN 6, whose
    tape7 uses underscore column labels ("TOT_TRANS", "THRML_EM") and
    splits the classic combined SOL SCAT column into MULT_SCAT +
    SING_SCAT. The pre-CU-154 reader recognised only the classic
    space-delimited vocabulary and rejected every real file. These
    verify the extended reader on the new vocabulary, the solar-scatter
    summation, and the "-9999." end-of-block sentinel.
    """

    @pytest.mark.level1
    def test_no_warning_with_underscore_header(self, tmp_path: Path) -> None:
        """A MODTRAN 6 labeled header must NOT trip the positional-fallback
        warning (it is a fully recognised named header)."""
        _write_modtran6_tape7(tmp_path / "tape7")
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning fails the test
            native = Tape7Reader(tmp_path / "tape7").parse()
        assert native.wavenumber_cm1.shape[0] == 20

    @pytest.mark.level1
    def test_scatter_is_mult_plus_sing(self, tmp_path: Path) -> None:
        """path_scattered_radiance <- MULT_SCAT + SING_SCAT, not either
        alone and not the THRML_SCT decoy."""
        expected = _write_modtran6_tape7(tmp_path / "tape7")
        native = Tape7Reader(tmp_path / "tape7").parse()
        np.testing.assert_allclose(
            native.path_scattered_radiance,
            expected["path_scattered_radiance"],
            rtol=1e-5,
        )
        # 2.0e-6 (MULT alone) and 9.0e-6 (THRML_SCT decoy) must not appear.
        assert not np.allclose(native.path_scattered_radiance, 2.0e-6)
        assert not np.allclose(native.path_scattered_radiance, 9.0e-6)

    @pytest.mark.level1
    def test_columns_mapped_correctly(self, tmp_path: Path) -> None:
        """TOT_TRANS / THRML_EM / GRND_RFLT land in the right fields; the
        SURF_EMIS (8e-6) and DRCT_RFLT (6e-6) decoys do not."""
        expected = _write_modtran6_tape7(tmp_path / "tape7")
        native = Tape7Reader(tmp_path / "tape7").parse()
        np.testing.assert_allclose(
            native.total_transmittance, expected["total_transmittance"], rtol=1e-5
        )
        np.testing.assert_allclose(
            native.path_thermal_radiance, expected["path_thermal_radiance"], rtol=1e-5
        )
        np.testing.assert_allclose(
            native.ground_reflected_radiance,
            expected["ground_reflected_radiance"],
            rtol=1e-5,
        )
        assert not np.allclose(native.ground_reflected_radiance, 8.0e-6)

    @pytest.mark.level1
    def test_sentinel_row_excluded(self, tmp_path: Path) -> None:
        """The lone "-9999." terminator is float-parseable but must be
        detected as a footer (column-count mismatch) and excluded."""
        _write_modtran6_tape7(tmp_path / "tape7", n_points=12)
        native = Tape7Reader(tmp_path / "tape7").parse()
        assert native.wavenumber_cm1.shape[0] == 12
        assert not np.any(native.wavenumber_cm1 == -9999.0)

    @pytest.mark.level1
    def test_missing_scatter_raises(self, tmp_path: Path) -> None:
        """MULT_SCAT present but no SING_SCAT and no SOL_SCAT: the solar
        scatter term is unavailable, so parsing raises (Rule 17), not
        silently zeros."""
        lines = [
            "    FREQ  TOT_TRANS   THRML_EM  GRND_RFLT  MULT_SCAT",
            "5000.0 0.80 1.0e-6 3.0e-6 2.0e-6",
            "4000.0 0.80 1.0e-6 3.0e-6 2.0e-6",
        ]
        (tmp_path / "tape7").write_text("\n".join(lines))
        with pytest.raises(Tape7ParseError, match="solar-scatter"):
            Tape7Reader(tmp_path / "tape7").parse()


# Real MODTRAN A1 tape7 — staged, gitignored, in modtran/real_runs/ until
# the fixture subset is committed (MODTRAN_Run_Matrix_Plan §7.1). The
# acceptance test below runs only where that file is present locally.
_REAL_A1_TAPE7 = (
    Path(__file__).resolve().parents[4] / "modtran" / "real_runs" / "A1.tp7"
)


@pytest.mark.skipif(
    not _REAL_A1_TAPE7.exists(),
    reason="real MODTRAN A1 tape7 not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)
class TestRealModtranA1:
    """Acceptance criterion #1 (MODTRAN_Run_Matrix_Plan §8): Tape7Reader
    round-trips >= 1 real tape7 (A1) with unit-conversion checks against
    hand-computed values at >= 3 wavelengths.

    This is the first real MODTRAN output ever exercised through the
    parser. Anchors span LWIR (thermal-dominated), MWIR, and VIS
    (solar-scatter-dominated) so the Jacobian and the scatter summation
    are both checked on real data.
    """

    def test_parses_without_fallback(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # no positional-fallback warning
            native = Tape7Reader(_REAL_A1_TAPE7).parse()
        assert native.wavenumber_cm1.size > 20_000
        assert np.all(np.isfinite(native.total_transmittance))
        assert np.all(native.total_transmittance >= 0.0)

    def test_ascending_ir_to_vis_range(self) -> None:
        wl, trans, l_path, l_ground = Tape7Reader(_REAL_A1_TAPE7).to_radiant_units()
        assert np.all(np.diff(wl) > 0.0)  # strictly ascending
        assert wl[0] == pytest.approx(0.3750, abs=1e-3)
        assert wl[-1] == pytest.approx(14.388, abs=1e-2)
        assert np.all(l_path >= 0.0)
        assert np.all((trans >= 0.0) & (trans <= 1.0))

    def test_unit_conversion_hand_anchors(self) -> None:
        """Hand-computed L(lambda) = L(nu) * nu^2 and tau passthrough at
        three wavenumbers, verified against to_radiant_units output.

        Anchor values were hand-computed offline from A1's native
        columns; they are literal truth anchors, not recomputations of
        the reader under test.
        """
        wl, trans, l_path, _ = Tape7Reader(_REAL_A1_TAPE7).to_radiant_units()
        # (wavelength_um, transmittance, path_radiance W/m2/sr/um)
        anchors = [
            (14.285714, 0.000000, 2.207695e00),  # nu=700  cm-1, LWIR, thermal
            (2.500000, 0.336426, 9.357310e-03),  # nu=4000 cm-1, MWIR
            (0.500000, 0.599329, 4.492120e01),  # nu=20000 cm-1, VIS, scatter
        ]
        for lam, tau_exp, l_exp in anchors:
            k = int(np.argmin(np.abs(wl - lam)))
            assert wl[k] == pytest.approx(lam, rel=1e-5)
            assert trans[k] == pytest.approx(tau_exp, abs=1e-5)
            assert l_path[k] == pytest.approx(l_exp, rel=1e-4)


# ---------------------------------------------------------------------------
# Flux table reader (MODTRAN spectral flux CSV — Block E irradiance runs)
# ---------------------------------------------------------------------------


def _write_modtran_flux_csv(
    path: Path, n_freq: int = 4, levels: tuple[float, ...] = (0.0, 1.0, 5.0)
) -> dict[str, np.ndarray]:
    """Write a MODTRAN 6 flux CSV fixture (case-brace block, num-freq /
    num-column metadata, UP/DOWN/SOLAR triple per level, closing brace).

    Each (level, kind) gets a distinct constant so column mapping is
    observable: UP = 1e-4·(j+1), DOWN = 2e-4·(j+1), SOLAR = 3e-4·(j+1)
    for level index j. UP is a decoy that must not reach either returned
    irradiance.
    """
    nu = np.linspace(5000.0, 2000.0, n_freq)  # descending, MODTRAN convention
    n_lev = len(levels)
    up = np.array([1.0e-4 * (j + 1) for j in range(n_lev)])
    down = np.array([2.0e-4 * (j + 1) for j in range(n_lev)])
    solar = np.array([3.0e-4 * (j + 1) for j in range(n_lev)])

    lines = [
        "case index 0 = {",
        f"num freq, {n_freq}",
        f"num column, {3 * n_lev}",
        ", ".join(["Freq"] + ["UP", "DOWN", "SOLAR"] * n_lev),
        ", ".join(["[cm-1]"] + [f"{a:g} KM" for a in levels for _ in range(3)]),
    ]
    for i in range(n_freq):
        vals = [nu[i]]
        for j in range(n_lev):
            vals += [up[j], down[j], solar[j]]
        lines.append(", ".join(f"{v:.6e}" for v in vals))
    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "wavenumber_cm1": nu,
        "altitude_km": np.asarray(levels, dtype=float),
        "flux_up": up,
        "flux_down": down,
        "flux_direct_solar": solar,
    }


class TestModtranFluxReader:
    """CU-154 follow-on: MODTRAN 6 spectral flux CSV reader (Block E).

    The E-block direct/diffuse solar irradiance lives in a separate
    ``*_flux.csv`` export (UP/DOWN/SOLAR per altitude level), a format
    the codebase had no reader for. These verify the structural parse,
    the level axis, the column mapping, and the ν² unit-conversion
    Jacobian (identical to the radiance case — no per-steradian factor).
    """

    @pytest.mark.level1
    def test_parse_shapes_and_levels(self, tmp_path: Path) -> None:
        _write_modtran_flux_csv(tmp_path / "flux.csv", n_freq=6)
        native = ModtranFluxReader(tmp_path / "flux.csv").parse()
        assert native.wavenumber_cm1.shape == (6,)
        assert native.flux_down.shape == (6, 3)
        np.testing.assert_allclose(native.altitude_km, [0.0, 1.0, 5.0])
        assert native.header["num_freq"] == 6
        assert native.header["num_column"] == 9

    @pytest.mark.level1
    def test_column_mapping_up_down_solar(self, tmp_path: Path) -> None:
        _write_modtran_flux_csv(tmp_path / "flux.csv")
        native = ModtranFluxReader(tmp_path / "flux.csv").parse()
        # Ground (level 0): UP=1e-4, DOWN=2e-4, SOLAR=3e-4.
        np.testing.assert_allclose(native.flux_up[:, 0], 1.0e-4, rtol=1e-6)
        np.testing.assert_allclose(native.flux_down[:, 0], 2.0e-4, rtol=1e-6)
        np.testing.assert_allclose(native.flux_direct_solar[:, 0], 3.0e-4, rtol=1e-6)
        # Level 2 (5 km) scales by (j+1)=3.
        np.testing.assert_allclose(native.flux_down[:, 2], 6.0e-4, rtol=1e-6)

    @pytest.mark.level1
    def test_to_radiant_units_ground_jacobian(self, tmp_path: Path) -> None:
        """E(λ) = E(ν)·ν² at ground; e_direct <- SOLAR, e_diffuse <- DOWN,
        never the UP decoy."""
        _write_modtran_flux_csv(tmp_path / "flux.csv")
        wl, e_direct, e_diffuse = ModtranFluxReader(tmp_path / "flux.csv").to_radiant_units()
        assert np.all(np.diff(wl) > 0.0)  # ascending
        nu = 10000.0 / wl
        np.testing.assert_allclose(e_direct, 3.0e-4 * nu * nu, rtol=1e-5)
        np.testing.assert_allclose(e_diffuse, 2.0e-4 * nu * nu, rtol=1e-5)
        # UP (1e-4) must not appear in either.
        assert not np.allclose(e_direct, 1.0e-4 * nu * nu)
        assert not np.allclose(e_diffuse, 1.0e-4 * nu * nu)

    @pytest.mark.level1
    def test_missing_level_header_raises(self, tmp_path: Path) -> None:
        lines = [
            "case index 0 = {",
            "num freq, 2",
            "num column, 3",
            "Freq, UP, DOWN, SOLAR",
            "5000.0, 1e-4, 2e-4, 3e-4",
            "}",
        ]
        (tmp_path / "flux.csv").write_text("\n".join(lines), encoding="utf-8")
        with pytest.raises(Tape7ParseError, match="level-label"):
            ModtranFluxReader(tmp_path / "flux.csv").parse()


# Real MODTRAN E1 flux CSV — staged, gitignored, in modtran/real_runs/.
_REAL_E1_FLUX = (
    Path(__file__).resolve().parents[4] / "modtran" / "real_runs" / "E1_flux.csv"
)


@pytest.mark.skipif(
    not _REAL_E1_FLUX.exists(),
    reason="real MODTRAN E1 flux CSV not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)
class TestRealModtranE1Flux:
    """Real-data validation of the flux reader on E1 (rural, θ_s=30°).

    Physical anchors: in the LWIR the direct solar beam is zero and the
    downwelling diffuse flux approaches π·B(T_near-surface); in the VIS
    the direct beam approximates TOA solar attenuated by transmittance
    and the solar-zenith cosine.
    """

    def test_parses_full_grid(self) -> None:
        native = ModtranFluxReader(_REAL_E1_FLUX).parse()
        assert native.wavenumber_cm1.size == 25_976
        assert native.altitude_km.shape == (36,)
        assert native.altitude_km[0] == 0.0
        assert native.altitude_km[-1] == 100.0

    def test_lwir_direct_zero_diffuse_thermal(self) -> None:
        wl, e_direct, e_diffuse = ModtranFluxReader(_REAL_E1_FLUX).to_radiant_units()
        # Longest wavelength (~14.4 µm, 695 cm-1): no direct sun.
        assert e_direct[-1] == 0.0
        # Downwelling diffuse ~ π·B near surface air temp: O(10) W/m²/µm.
        assert 12.0 < e_diffuse[-1] < 25.0

    def test_vis_direct_beam_magnitude(self) -> None:
        """Direct beam at 0.5 µm ≈ TOA(0.5µm)·τ·cos(30°) ~ 1e3 W/m²/µm."""
        wl, e_direct, e_diffuse = ModtranFluxReader(_REAL_E1_FLUX).to_radiant_units()
        k = int(np.argmin(np.abs(wl - 0.5)))
        assert e_direct[k] == pytest.approx(1020.9, rel=0.02)
        assert e_diffuse[k] > 0.0


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

    @pytest.mark.level0
    def test_card1_token_positions(self, default_geometry: AtmosphericGeometry) -> None:
        """CU-067: pin the Card 1 tokens RADIANT controls to their verified
        whitespace-split positions — [3]=MODEL, [5]=ITYPE, [6]=IEMSCT,
        [7]=IMULT — confirmed field-by-field against the real 2026-07-17
        MODTRAN 6 run set. Distinct values (6/2/3/1) make each position
        independently asserted, replacing the pre-fix stale comment that
        no test enforced (the original CU-067 defect)."""
        config = ModtranConfig(atmosphere_profile="us_standard", iemsct=3)  # itype default 2
        card1 = render_tape5(config, default_geometry).splitlines()[0].split()
        assert card1[3] == "6"  # MODEL: us_standard -> 6
        assert card1[5] == "2"  # ITYPE: default slant H1->H2
        assert card1[6] == "3"  # IEMSCT: irradiance mode
        assert card1[7] == "1"  # IMULT: multiple scattering (fixed)

    @pytest.mark.level1
    def test_geometry_in_card3(self, default_geometry: AtmosphericGeometry) -> None:
        config = ModtranConfig()
        tape5 = render_tape5(config, default_geometry)
        # H1 = 20 km, H2 = 0 km.
        assert "20.000" in tape5
        assert "0.000" in tape5

    @pytest.mark.level0
    def test_card3_angle_nadir_from_space_renders_180(self) -> None:
        """CU-065 Level 0: MODTRAN ANGLE is measured from zenith at H1 (the
        sensor) — a nadir-looking space sensor must render ANGLE = 180."""
        geometry = AtmosphericGeometry(
            sensor_altitude_m=100_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.0,  # nadir path: zenith 0 at the ground endpoint
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        tape5 = render_tape5(ModtranConfig(), geometry)
        card3 = tape5.splitlines()[4]
        h1, h2, angle = card3.split()[:3]
        assert float(h1) == pytest.approx(100.0, abs=1e-9)
        assert float(h2) == pytest.approx(0.0, abs=1e-9)
        assert float(angle) == pytest.approx(180.0, abs=1e-9)

    @pytest.mark.level0
    def test_card3_angle_downlooking_slant(self) -> None:
        """CU-065: 30 deg off-nadir from space -> ANGLE = 150 at H1 (run
        matrix row B1: path_zenith_deg_radiant=30, modtran_angle_at_h1_deg=150)."""
        import math

        geometry = AtmosphericGeometry(
            sensor_altitude_m=100_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(30.0),
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        tape5 = render_tape5(ModtranConfig(), geometry)
        angle = float(tape5.splitlines()[4].split()[2])
        assert angle == pytest.approx(150.0, abs=1e-9)

    @pytest.mark.level0
    def test_card3_angle_uplooking_unchanged(self) -> None:
        """CU-065: ground sensor looking up — the sensor IS the lower
        endpoint, so ANGLE = path zenith unchanged (run matrix row H2:
        zenith 48.2 -> ANGLE 48.2)."""
        import math

        geometry = AtmosphericGeometry(
            sensor_altitude_m=0.0,
            target_altitude_m=100_000.0,
            path_zenith_rad=math.radians(48.2),
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        tape5 = render_tape5(ModtranConfig(), geometry)
        angle = float(tape5.splitlines()[4].split()[2])
        assert angle == pytest.approx(48.2, abs=1e-9)

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


class TestTape7SunLegImport:
    """CU-011 (file flavor): tape7_sun_path supplies tau_sun independently."""

    @pytest.mark.level1
    def test_sun_file_splits_tau_and_kills_warning(self, tmp_path: Path) -> None:
        from radiant.api.session import RadiantSession
        from radiant.core.los_geometry import LineOfSightGeometry

        main = tmp_path / "up_leg.tp7"
        _write_realistic_tape7(main)  # TOT TRANS = 0.80
        sun = tmp_path / "sun_leg.tp7"
        _write_realistic_tape7(sun, tot_trans_value=0.55)

        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=tmp_path / "cache",
            allow_fallback=False,
        )
        model = ModtranAtmosphere(
            config,
            tape7_import=Tape7Import.from_file(main),
            tape7_sun_import=Tape7Import.from_file(sun),
        )

        wl = np.linspace(2.5, 4.5, 30)
        params = _resolved_params_for_evaluate(RadiantSession, wl)
        # Non-zero solar zenith: the sun leg is a genuinely different path.
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=np.deg2rad(30.0), delta_phi=0.0)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            atm = model.evaluate(wl, los, params)
        # The single-tau collapse warning (which the sun leg exists to kill)
        # must NOT fire. The Gap 81 downwelling-zeroed warning is expected and
        # tolerated — it is unrelated to the two-leg split.
        collapse = [w for w in caught if "tape7_sun_path" in str(w.message)]
        assert not collapse, [str(w.message) for w in collapse]

        # tau_sun comes from the sun-leg file; tau_up from the up-leg file.
        np.testing.assert_allclose(atm.tau_sun, np.full_like(wl, 0.55), rtol=0, atol=1e-6)
        np.testing.assert_allclose(atm.tau_up, np.full_like(wl, 0.80), rtol=0, atol=1e-6)
        assert not np.allclose(atm.tau_sun, atm.tau_up)
        # The up-leg pair still aliases (surface target).
        np.testing.assert_array_equal(atm.tau_up, atm.tau_full_up)

    @pytest.mark.level1
    def test_without_sun_file_warning_kept(self, tmp_path: Path) -> None:
        """Single-file import keeps the single-tau collapse warning."""
        from radiant.api.session import RadiantSession
        from radiant.core.los_geometry import LineOfSightGeometry

        main = tmp_path / "up_leg.tp7"
        _write_realistic_tape7(main)
        config = ModtranConfig(binary_path=tmp_path / "no_modtran", allow_fallback=False)
        model = ModtranAtmosphere(config, tape7_import=Tape7Import.from_file(main))

        wl = np.linspace(2.5, 4.5, 30)
        params = _resolved_params_for_evaluate(RadiantSession, wl)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=np.deg2rad(30.0), delta_phi=0.0)

        with pytest.warns(UserWarning, match="tape7_sun_path"):
            atm = model.evaluate(wl, los, params)
        np.testing.assert_array_equal(atm.tau_sun, atm.tau_up)

    @pytest.mark.level1
    def test_downwelling_zeroed_warns(self, tmp_path: Path) -> None:
        """Gap 81: a MODTRAN state warns that downwelling/scatter sky terms
        are zeroed rather than silently dropping them."""
        from radiant.core.los_geometry import LineOfSightGeometry

        main = tmp_path / "up_leg.tp7"
        _write_realistic_tape7(main)
        config = ModtranConfig(binary_path=tmp_path / "no_modtran", allow_fallback=False)
        model = ModtranAtmosphere(config, tape7_import=Tape7Import.from_file(main))
        wl = np.linspace(2.5, 4.5, 30)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0, theta_s=np.deg2rad(30.0), delta_phi=0.0)
        with pytest.warns(UserWarning, match="downwelling sky emission"):
            state = model.build_state(wl, los)
        assert np.all(state.atm_emission_down.values == 0.0)


class TestTape7UpLegImport:
    """Gap 94 (file flavor): tape7_up_path supplies the target→sensor leg."""

    @pytest.mark.level1
    def test_up_file_enables_airborne_target(self, tmp_path: Path) -> None:
        """With an up-leg file, h_tgt > 0 is accepted and the legs split:
        tau_up from the up-leg file, tau_full_up from the primary file."""
        from radiant.api.session import RadiantSession
        from radiant.core.los_geometry import LineOfSightGeometry

        full = tmp_path / "full_column.tp7"
        _write_realistic_tape7(full)  # TOT TRANS = 0.80 (ground→sensor)
        up = tmp_path / "up_leg.tp7"
        _write_realistic_tape7(up, tot_trans_value=0.95)  # target→sensor

        config = ModtranConfig(
            binary_path=tmp_path / "no_modtran",
            cache_dir=tmp_path / "cache",
            allow_fallback=False,
        )
        model = ModtranAtmosphere(
            config,
            tape7_import=Tape7Import.from_file(full),
            tape7_up_import=Tape7Import.from_file(up),
        )

        wl = np.linspace(2.5, 4.5, 30)
        params = _resolved_params_for_evaluate(RadiantSession, wl)
        los = LineOfSightGeometry(h_tgt=5_000.0, theta_o=0.0)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            atm = model.evaluate(wl, los, params)

        np.testing.assert_allclose(atm.tau_up, np.full_like(wl, 0.95), rtol=0, atol=1e-6)
        np.testing.assert_allclose(atm.tau_full_up, np.full_like(wl, 0.80), rtol=0, atol=1e-6)
        assert not np.allclose(atm.tau_up, atm.tau_full_up)
        # Without a sun-leg file, tau_sun aliases the up leg.
        np.testing.assert_array_equal(atm.tau_sun, atm.tau_up)

    @pytest.mark.level1
    def test_airborne_without_up_file_still_raises(self, tmp_path: Path) -> None:
        """The single-file restriction is unchanged when no up-leg file is given
        (same guard TestTape7FileImport.test_evaluate_airborne_target_raises pins);
        the error now names the tape7_up_path remedy."""
        from radiant.api.session import RadiantSession
        from radiant.core.los_geometry import LineOfSightGeometry

        full = tmp_path / "full_column.tp7"
        _write_realistic_tape7(full)
        config = ModtranConfig(binary_path=tmp_path / "no_modtran", allow_fallback=False)
        model = ModtranAtmosphere(config, tape7_import=Tape7Import.from_file(full))
        wl = np.linspace(2.5, 4.5, 30)
        params = _resolved_params_for_evaluate(RadiantSession, wl)
        los = LineOfSightGeometry(h_tgt=5_000.0, theta_o=0.0)
        with pytest.raises(NotImplementedError, match="tape7_up_path"):
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
