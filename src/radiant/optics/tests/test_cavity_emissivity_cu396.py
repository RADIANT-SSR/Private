"""Level-0 tests for the CU-396 cavity-emissivity correction.

The defect: ``eps_eff`` carried an n^2 factor for the enhanced photon density of
states *inside* the dielectric, without the compensating 1/n^2 radiance
de-magnification on escape. Radiance is not invariant across a refracting surface
(L/n^2 is), and the two cancel exactly. Keeping one overstated emissivity by ~n^2 —
15.8x for germanium — and the result could exceed 1, which was being clipped.

These tests pin the correction from four independent directions: the n-independence
the cancellation implies, the energy-conservation identity, the physical bound, and
the asymmetric-coating case that distinguishes the right identity from the tempting
wrong one.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.cavity_model import CavityModel

_WL = np.array([10.6])


def _sd(value: float, name: str = "x"):
    from radiant.core.spectral import SpectralData

    return SpectralData(
        name=name, wavelength_um=_WL, values=np.full_like(_WL, value), unit="", source="test"
    )


def _cavity(*, r1: float, r2: float, alpha: float, d: float = 0.008) -> CavityModel:
    return CavityModel(
        R1=_sd(r1, "R1"),
        T1=_sd(1.0 - r1, "T1"),
        R2=_sd(r2, "R2"),
        T2=_sd(1.0 - r2, "T2"),
        alpha=_sd(alpha, "alpha"),
        thickness_m=d,
    )


class TestTheCancellation:
    @pytest.mark.level0
    def test_the_model_has_no_refractive_index_at_all(self) -> None:
        """CU-396 removed the n^2; CU-399 removed the index that fed it.

        This replaces a test that varied n and asserted eps did not move. That check
        became unconstructible — and it was always the weaker statement. An index the
        model accepts but ignores is a control an analyst can turn believing it
        matters; an index the model does not accept cannot mislead anyone.
        """
        assert "n_refr" not in CavityModel.__dataclass_fields__
        with pytest.raises(TypeError):
            CavityModel(  # type: ignore[call-arg]
                R1=_sd(0.01, "R1"),
                T1=_sd(0.99, "T1"),
                R2=_sd(0.01, "R2"),
                T2=_sd(0.99, "T2"),
                alpha=_sd(2.7, "alpha"),
                n_refr=_sd(4.0, "n"),
                thickness_m=0.008,
            )

    @pytest.mark.level0
    def test_germanium_is_no_longer_sixteen_times_too_high(self) -> None:
        """Regression anchor on the measured defect value.

        Hand value, first order (CU-398): beer = exp(-2.7*0.008) = 0.978631609, so
        eps = T2*(1-beer)*(1+R1*beer) = 0.99 * 0.021368391 * 1.009786316 = 0.021361733.
        It moved 0.02136378 -> 0.02136173 when the bounce series went, a factor
        1/denom = 1.0000958 at these AR coatings.
        """
        eps = _cavity(r1=0.01, r2=0.01, alpha=2.7).eps_eff.values[0]
        assert eps == pytest.approx(0.021361733, rel=1e-6)
        # What the n^2 expression used to give, for the record.
        assert 0.3385077 / eps == pytest.approx(15.8465, rel=1e-3)


class TestTheEnergyIdentity:
    @pytest.mark.level0
    def test_emissivity_is_the_side_two_absorptance(self) -> None:
        """eps = 1 - T_sys - R_side2, by energy conservation plus Kirchhoff."""
        rng = np.random.default_rng(3)
        worst = 0.0
        for _ in range(2000):
            r1, r2 = rng.uniform(0.0, 0.4, 2)
            alpha = rng.uniform(0.0, 400.0)
            c = _cavity(r1=float(r1), r2=float(r2), alpha=float(alpha))
            b = c.beer[0]
            # First order (CU-398): the side-swapped R_sys — one T2, no bounce series.
            r_side2 = r2 + (1.0 - r2) * r1 * b * b
            absorptance = 1.0 - c.T_sys.values[0] - r_side2
            worst = max(worst, abs(c.eps_eff.values[0] - absorptance))
        assert worst < 1e-14

    @pytest.mark.level0
    def test_the_side_one_shorthand_is_not_a_substitute(self) -> None:
        """`1 - T_sys - R_sys` is the SIDE-1 absorptance and differs when R1 != R2.

        This is pinned because the shorthand is tempting and correct for symmetric
        coatings, which is exactly what makes it a trap: entry and exit faces rarely
        carry the same AR stack. A "simplification" to R_sys would silently reintroduce
        an error on every asymmetric element.
        """
        c = _cavity(r1=0.30, r2=0.02, alpha=200.0)
        side_one = 1.0 - c.T_sys.values[0] - c.R_sys.values[0]
        assert c.eps_eff.values[0] != pytest.approx(side_one, rel=1e-3)

    @pytest.mark.level0
    def test_symmetric_coatings_make_the_two_agree(self) -> None:
        """...and this is why the trap is hard to see."""
        c = _cavity(r1=0.05, r2=0.05, alpha=200.0)
        side_one = 1.0 - c.T_sys.values[0] - c.R_sys.values[0]
        assert c.eps_eff.values[0] == pytest.approx(side_one, rel=1e-12)


class TestTheBound:
    @pytest.mark.level0
    def test_emissivity_never_exceeds_one(self) -> None:
        """No clip is needed because the corrected expression cannot exceed 1.

        A surface emitting more than a blackbody is a second-law violation; the old
        expression could, and was clipped, which concealed exactly that.
        """
        rng = np.random.default_rng(5)
        worst = 0.0
        for _ in range(4000):
            r1, r2 = rng.uniform(0.0, 0.95, 2)
            alpha = rng.uniform(0.0, 5000.0)
            eps = _cavity(r1=float(r1), r2=float(r2), alpha=float(alpha)).eps_eff.values[0]
            assert 0.0 <= eps <= 1.0
            worst = max(worst, eps)
        assert worst < 1.0

    @pytest.mark.level0
    def test_the_limit_is_a_blackbody_behind_a_lossless_window(self) -> None:
        """eps -> 1 only as R2 -> 0 and the slab becomes opaque."""
        eps = _cavity(r1=0.0, r2=0.0, alpha=1.0e6).eps_eff.values[0]
        assert eps == pytest.approx(1.0, abs=1e-9)


class TestTheZeroCasesStillHold:
    @pytest.mark.level0
    def test_no_absorption_means_no_emission(self) -> None:
        assert _cavity(r1=0.01, r2=0.01, alpha=0.0).eps_eff.values[0] == pytest.approx(
            0.0, abs=1e-15
        )

    @pytest.mark.level0
    def test_zero_thickness_means_no_emission(self) -> None:
        assert _cavity(r1=0.01, r2=0.01, alpha=2.7, d=0.0).eps_eff.values[0] == pytest.approx(
            0.0, abs=1e-15
        )
