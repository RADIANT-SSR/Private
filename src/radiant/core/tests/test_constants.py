"""Level 0 tests for radiant.core.constants.

Verifies CODATA 2018 exact values, derived quantities, and backward-compatibility
uppercase aliases.
"""

import math

import pytest
import scipy.constants as _sc  # type: ignore[import-untyped]

from radiant.core.constants import (
    C1,
    C2,
    K_B,  # noqa: N811
    SIGMA_SB,
    C,  # noqa: N811
    H,  # noqa: N811
    Q,  # noqa: N811
    c,
    h,
    hc,
    hc_over_kB,
    k_B,
    q,
    sigma_sb,
    two_hc2,
)

# ---------------------------------------------------------------------------
# CODATA 2018 exact values
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_c_codata_exact() -> None:
    """Speed of light is exact by SI definition: 2.99792458e8 m/s."""
    assert c == pytest.approx(2.99792458e8, rel=1e-10)


@pytest.mark.level0
def test_h_codata_exact() -> None:
    """Planck constant is exact by 2019 SI redefinition: 6.62607015e-34 J·s."""
    assert h == pytest.approx(6.62607015e-34, rel=1e-10)


@pytest.mark.level0
def test_k_B_codata_exact() -> None:
    """Boltzmann constant is exact by 2019 SI redefinition: 1.380649e-23 J/K."""
    assert k_B == pytest.approx(1.380649e-23, rel=1e-10)


@pytest.mark.level0
def test_q_codata_exact() -> None:
    """Elementary charge is exact by 2019 SI redefinition: 1.602176634e-19 C."""
    assert q == pytest.approx(1.602176634e-19, rel=1e-10)


@pytest.mark.level0
def test_sigma_sb_codata() -> None:
    """Stefan-Boltzmann constant matches CODATA: 5.670374419e-8 W/m²/K⁴."""
    assert sigma_sb == pytest.approx(5.670374419e-8, rel=1e-9)


# ---------------------------------------------------------------------------
# Derived quantities: computed from lowercase constants
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_hc_derived() -> None:
    """hc equals h * c exactly (floating-point identity)."""
    assert hc == h * c


@pytest.mark.level0
def test_two_hc2_derived() -> None:
    """two_hc2 equals 2 * h * c**2 exactly (floating-point identity)."""
    assert two_hc2 == 2.0 * h * c**2


@pytest.mark.level0
def test_hc_over_kB_derived() -> None:
    """hc_over_kB equals h * c / k_B exactly (floating-point identity)."""
    assert hc_over_kB == h * c / k_B


# ---------------------------------------------------------------------------
# Backward-compatibility uppercase aliases
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_alias_C() -> None:
    """Uppercase alias C equals lowercase c."""
    assert c == C


@pytest.mark.level0
def test_alias_H() -> None:
    """Uppercase alias H equals lowercase h."""
    assert h == H


@pytest.mark.level0
def test_alias_K_B() -> None:
    """Uppercase alias K_B equals lowercase k_B."""
    assert k_B == K_B


@pytest.mark.level0
def test_alias_Q() -> None:
    """Uppercase alias Q equals lowercase q."""
    assert q == Q


@pytest.mark.level0
def test_alias_SIGMA_SB() -> None:
    """Uppercase alias SIGMA_SB equals lowercase sigma_sb."""
    assert sigma_sb == SIGMA_SB


@pytest.mark.level0
def test_alias_C1() -> None:
    """Uppercase alias C1 equals two_hc2."""
    assert two_hc2 == C1


@pytest.mark.level0
def test_alias_C2() -> None:
    """Uppercase alias C2 equals hc_over_kB."""
    assert hc_over_kB == C2


# ---------------------------------------------------------------------------
# Verify sigma_sb derivation from first principles
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_sigma_sb_derivation() -> None:
    """Verify σ = 2π⁵k_B⁴/(15h³c²) matches scipy value within rel=1e-9.

    This is an independent check that our constants are mutually consistent
    with the Stefan-Boltzmann law derivation.
    """
    sigma_derived = (2.0 * math.pi**5 * k_B**4) / (15.0 * h**3 * c**2)
    assert sigma_derived == pytest.approx(_sc.sigma, rel=1e-9)


# ---------------------------------------------------------------------------
# Consistency with scipy.constants (source cross-check)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_c_matches_scipy() -> None:
    """c matches scipy.constants.c."""
    assert c == _sc.c


@pytest.mark.level0
def test_h_matches_scipy() -> None:
    """h matches scipy.constants.h."""
    assert h == _sc.h


@pytest.mark.level0
def test_k_B_matches_scipy() -> None:
    """k_B matches scipy.constants.k."""
    assert k_B == _sc.k


@pytest.mark.level0
def test_q_matches_scipy() -> None:
    """q matches scipy.constants.e."""
    assert q == _sc.e


@pytest.mark.level0
def test_sigma_sb_matches_scipy() -> None:
    """sigma_sb matches scipy.constants.sigma."""
    assert sigma_sb == _sc.sigma
