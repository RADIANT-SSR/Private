"""Tests for Zernike polynomial evaluation.

Validates:
- Noll indexing: Z1-Z15 match standard convention
- Normalization: integral of Z_j^2 over unit disk = pi
- Orthogonality: integral of Z_j * Z_k = 0 for j != k
- Z4 (defocus): radial profile is sqrt(3)*(2*rho^2 - 1)
- Z7 (coma): asymmetric PSF shape
- Obscured pupil: Zernike evaluated only inside annular aperture
- Annular warning: obscuration > 0.30 triggers UserWarning
- Edge cases: Noll index 0, very large coefficients
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.zernike import (
    evaluate_zernike_opd,
    noll_to_nm,
    zernike_polynomial,
    zernike_radial,
)


# ---------------------------------------------------------------------------
# Noll indexing
# ---------------------------------------------------------------------------


class TestNollIndexing:
    """Verify Noll-to-(n,m) mapping matches standard convention."""

    EXPECTED = {
        1: (0, 0),    # piston
        2: (1, 1),    # tilt x
        3: (1, -1),   # tilt y
        4: (2, 0),    # defocus
        5: (2, -2),   # astigmatism 45 deg
        6: (2, 2),    # astigmatism 0 deg
        7: (3, -1),   # coma y
        8: (3, 1),    # coma x
        9: (3, -3),   # trefoil y
        10: (3, 3),   # trefoil x
        11: (4, 0),   # spherical
        12: (4, 2),   # secondary astigmatism
        13: (4, -2),
        14: (4, 4),
        15: (4, -4),
    }

    @pytest.mark.parametrize("j,expected", list(EXPECTED.items()))
    def test_noll_known_values(self, j: int, expected: tuple[int, int]) -> None:
        assert noll_to_nm(j) == expected

    def test_noll_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="Noll index must be >= 1"):
            noll_to_nm(0)

    def test_noll_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="Noll index must be >= 1"):
            noll_to_nm(-3)

    def test_n_minus_m_abs_always_even(self) -> None:
        """For valid Zernike, n - |m| must be even."""
        for j in range(1, 37):
            n, m = noll_to_nm(j)
            assert (n - abs(m)) % 2 == 0, f"j={j}: n={n}, m={m}"


# ---------------------------------------------------------------------------
# Normalization: integral Z_j^2 dA = pi
# ---------------------------------------------------------------------------

NPIX_INTEG = 512  # high resolution for numerical integration


class TestNormalization:
    """Verify that each Zernike polynomial has unit-disk integral = pi."""

    @pytest.mark.parametrize("j", range(1, 16))
    def test_normalization_integral(self, j: int) -> None:
        r"""Verify integral Z_j^2 dA = pi over unit disk.

        Noll normalization: each polynomial satisfies
        integral from 0 to 1 of integral from 0 to 2*pi
        of Z_j^2(rho, theta) * rho d(rho) d(theta) = pi.
        """
        npix = NPIX_INTEG
        x = np.linspace(-1, 1, npix, endpoint=False) + 1.0 / npix
        xx, yy = np.meshgrid(x, x, indexing="xy")
        rho = np.sqrt(xx**2 + yy**2)
        theta = np.arctan2(yy, xx)
        mask = rho <= 1.0

        Z = zernike_polynomial(j, rho, theta)
        # Pixel area on the unit square [-1,1]x[-1,1]
        dx = 2.0 / npix
        integral = float(np.sum(Z[mask] ** 2)) * dx**2

        assert integral == pytest.approx(math.pi, rel=0.01)


# ---------------------------------------------------------------------------
# Orthogonality: integral Z_j * Z_k = 0 for j != k
# ---------------------------------------------------------------------------


class TestOrthogonality:
    """Verify pairwise orthogonality of first 15 Zernike polynomials."""

    def test_orthogonality_first_15(self) -> None:
        npix = NPIX_INTEG
        x = np.linspace(-1, 1, npix, endpoint=False) + 1.0 / npix
        xx, yy = np.meshgrid(x, x, indexing="xy")
        rho = np.sqrt(xx**2 + yy**2)
        theta = np.arctan2(yy, xx)
        mask = rho <= 1.0
        dx = 2.0 / npix

        n_zern = 15
        polys = []
        for j in range(1, n_zern + 1):
            Z = zernike_polynomial(j, rho, theta)
            polys.append(Z)

        for j in range(n_zern):
            for k in range(j + 1, n_zern):
                cross = float(np.sum(polys[j][mask] * polys[k][mask])) * dx**2
                assert abs(cross) < 0.05, (
                    f"Z{j+1} x Z{k+1} cross-integral = {cross:.4f}, "
                    f"expected ~0"
                )


# ---------------------------------------------------------------------------
# Z4 (defocus): profile check
# ---------------------------------------------------------------------------


class TestZ4Defocus:
    """Z4 = sqrt(3) * (2*rho^2 - 1)."""

    def test_z4_radial_profile(self) -> None:
        """Verify Z4 along the x-axis matches analytic formula."""
        rho = np.linspace(0, 1, 100)
        theta = np.zeros_like(rho)

        Z4 = zernike_polynomial(4, rho, theta)
        expected = math.sqrt(3) * (2.0 * rho**2 - 1.0)

        np.testing.assert_allclose(Z4, expected, atol=1e-12)

    def test_z4_center_value(self) -> None:
        """Z4(0, 0) = sqrt(3) * (-1) = -sqrt(3)."""
        rho = np.array([0.0])
        theta = np.array([0.0])
        Z4 = zernike_polynomial(4, rho, theta)
        assert float(Z4[0]) == pytest.approx(-math.sqrt(3), rel=1e-12)

    def test_z4_edge_value(self) -> None:
        """Z4(1, 0) = sqrt(3) * (2 - 1) = sqrt(3)."""
        rho = np.array([1.0])
        theta = np.array([0.0])
        Z4 = zernike_polynomial(4, rho, theta)
        assert float(Z4[0]) == pytest.approx(math.sqrt(3), rel=1e-12)


# ---------------------------------------------------------------------------
# Z7 (coma): asymmetry check
# ---------------------------------------------------------------------------


class TestZ7Coma:
    """Z7 (coma y) produces asymmetric OPD."""

    def test_z7_asymmetric_y(self) -> None:
        """Coma along y-axis: OPD at +y differs from -y."""
        npix = 128
        opd = evaluate_zernike_opd({7: 1.0}, npix, obscuration_ratio=0.0)

        c = npix // 2
        # Compare upper vs lower half
        upper = opd[:c, :].sum()
        lower = opd[c:, :].sum()
        assert upper != pytest.approx(lower, abs=1e-6)

    def test_z7_coma_formula(self) -> None:
        """Z7 = sqrt(8) * (3*rho^3 - 2*rho) * sin(theta)."""
        rho = np.array([0.5])
        theta = np.array([math.pi / 2.0])  # 90 deg

        Z7 = zernike_polynomial(7, rho, theta)
        # n=3, m=-1 -> sin(theta) term
        # R_3^1(0.5) = 3*(0.5)^3 - 2*(0.5) = 3*0.125 - 1.0 = -0.625
        # norm = sqrt(2*(3+1)) = sqrt(8)
        expected = math.sqrt(8) * (3 * 0.5**3 - 2 * 0.5) * math.sin(math.pi / 2)
        assert float(Z7[0]) == pytest.approx(expected, rel=1e-10)


# ---------------------------------------------------------------------------
# Radial polynomial
# ---------------------------------------------------------------------------


class TestRadialPolynomial:
    """Test zernike_radial for known cases."""

    def test_r00_is_one(self) -> None:
        """R_0^0(rho) = 1 everywhere."""
        rho = np.linspace(0, 1, 50)
        R = zernike_radial(0, 0, rho)
        np.testing.assert_allclose(R, 1.0, atol=1e-15)

    def test_r11_is_rho(self) -> None:
        """R_1^1(rho) = rho."""
        rho = np.linspace(0, 1, 50)
        R = zernike_radial(1, 1, rho)
        np.testing.assert_allclose(R, rho, atol=1e-15)

    def test_r20_defocus(self) -> None:
        """R_2^0(rho) = 2*rho^2 - 1."""
        rho = np.linspace(0, 1, 50)
        R = zernike_radial(2, 0, rho)
        expected = 2.0 * rho**2 - 1.0
        np.testing.assert_allclose(R, expected, atol=1e-14)

    def test_r22_astig(self) -> None:
        """R_2^2(rho) = rho^2."""
        rho = np.linspace(0, 1, 50)
        R = zernike_radial(2, 2, rho)
        np.testing.assert_allclose(R, rho**2, atol=1e-15)

    def test_r31_coma(self) -> None:
        """R_3^1(rho) = 3*rho^3 - 2*rho."""
        rho = np.linspace(0, 1, 50)
        R = zernike_radial(3, 1, rho)
        expected = 3.0 * rho**3 - 2.0 * rho
        np.testing.assert_allclose(R, expected, atol=1e-14)

    def test_r40_spherical(self) -> None:
        """R_4^0(rho) = 6*rho^4 - 6*rho^2 + 1."""
        rho = np.linspace(0, 1, 50)
        R = zernike_radial(4, 0, rho)
        expected = 6.0 * rho**4 - 6.0 * rho**2 + 1.0
        np.testing.assert_allclose(R, expected, atol=1e-13)

    def test_invalid_nm_returns_zero(self) -> None:
        """n - m_abs odd -> zero polynomial."""
        rho = np.linspace(0, 1, 10)
        R = zernike_radial(3, 0, rho)  # 3-0 = 3, odd
        np.testing.assert_array_equal(R, np.zeros_like(rho))


# ---------------------------------------------------------------------------
# evaluate_zernike_opd
# ---------------------------------------------------------------------------


class TestEvaluateZernikeOPD:
    """Test the full OPD evaluation function."""

    def test_piston_constant(self) -> None:
        """Z1 (piston) = constant over the pupil."""
        opd = evaluate_zernike_opd({1: 1.0}, npix=64, obscuration_ratio=0.0)
        mask = opd != 0.0
        values = opd[mask]
        # All non-zero values should be identical (piston = 1 * norm * 1)
        assert np.std(values) == pytest.approx(0.0, abs=1e-12)

    def test_zero_outside_pupil(self) -> None:
        """OPD should be zero outside the clear aperture."""
        opd = evaluate_zernike_opd({4: 1.0}, npix=64, obscuration_ratio=0.0)
        x = np.linspace(-0.5, 0.5, 64, endpoint=False) + 0.5 / 64
        xx, yy = np.meshgrid(x, x, indexing="xy")
        r = np.sqrt(xx**2 + yy**2)
        outside = r > 0.5
        np.testing.assert_array_equal(opd[outside], 0.0)

    def test_obscuration_zero_inside(self) -> None:
        """OPD should be zero inside the central obscuration."""
        opd = evaluate_zernike_opd({4: 1.0}, npix=128, obscuration_ratio=0.2)
        x = np.linspace(-0.5, 0.5, 128, endpoint=False) + 0.5 / 128
        xx, yy = np.meshgrid(x, x, indexing="xy")
        rho = 2.0 * np.sqrt(xx**2 + yy**2)
        inside_obs = rho < 0.2
        np.testing.assert_array_equal(opd[inside_obs], 0.0)

    def test_annular_warning(self) -> None:
        """Obscuration > 0.30 should trigger UserWarning."""
        with pytest.warns(UserWarning, match="NOT orthogonal"):
            evaluate_zernike_opd({4: 1.0}, npix=32, obscuration_ratio=0.35)

    def test_no_warning_small_obscuration(self) -> None:
        """Obscuration <= 0.30 should NOT warn."""
        # If no warning is raised, this passes; if one is raised, it fails.
        import warnings as _w

        with _w.catch_warnings():
            _w.simplefilter("error", UserWarning)
            evaluate_zernike_opd({4: 1.0}, npix=32, obscuration_ratio=0.20)

    def test_large_coeff_warning(self) -> None:
        """Coefficient > 10 waves should trigger UserWarning."""
        with pytest.warns(UserWarning, match="exceeds 10 waves"):
            evaluate_zernike_opd({4: 15.0}, npix=32, obscuration_ratio=0.0)

    def test_noll_zero_raises(self) -> None:
        """Noll index 0 should raise ValueError."""
        with pytest.raises(ValueError, match="Noll index must be >= 1"):
            evaluate_zernike_opd({0: 1.0}, npix=32, obscuration_ratio=0.0)

    def test_obscuration_ge_one_raises(self) -> None:
        with pytest.raises(ValueError, match="obscuration_ratio must be in"):
            evaluate_zernike_opd({4: 1.0}, npix=32, obscuration_ratio=1.0)

    def test_rms_of_z4_opd(self) -> None:
        """RMS of Z4 OPD with coeff c should be c/sqrt(3) over clear aperture.

        For the Noll-normalised Z4 with coefficient c:
        OPD = c * sqrt(3) * (2*rho^2 - 1)
        The RMS over the unit disk is c (by construction of normalisation).
        But RMS of Z4 polynomial itself = 1 (Noll normalisation), so
        RMS(c * Z4) = |c|.
        """
        c = 0.5
        npix = 256
        opd = evaluate_zernike_opd({4: c}, npix=npix, obscuration_ratio=0.0)
        x = np.linspace(-0.5, 0.5, npix, endpoint=False) + 0.5 / npix
        xx, yy = np.meshgrid(x, x, indexing="xy")
        rho = 2.0 * np.sqrt(xx**2 + yy**2)
        mask = rho <= 1.0

        rms = float(np.sqrt(np.mean(opd[mask] ** 2)))
        assert rms == pytest.approx(abs(c), rel=0.02)

    def test_sum_of_two_coefficients(self) -> None:
        """OPD from {4: a, 7: b} should equal sum of individual OPDs."""
        npix = 128
        a, b = 0.3, 0.2
        opd_both = evaluate_zernike_opd({4: a, 7: b}, npix)
        opd_4 = evaluate_zernike_opd({4: a}, npix)
        opd_7 = evaluate_zernike_opd({7: b}, npix)

        np.testing.assert_allclose(opd_both, opd_4 + opd_7, atol=1e-14)

    def test_empty_coeffs_is_zero(self) -> None:
        """No coefficients -> zero OPD everywhere."""
        opd = evaluate_zernike_opd({}, npix=32)
        np.testing.assert_array_equal(opd, np.zeros((32, 32)))

    def test_zero_coefficient_ignored(self) -> None:
        """A coefficient of 0.0 should produce zero OPD for that term."""
        opd = evaluate_zernike_opd({4: 0.0}, npix=32)
        np.testing.assert_array_equal(opd, np.zeros((32, 32)))
