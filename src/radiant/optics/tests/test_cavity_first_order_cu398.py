"""The cavity is a FIRST-ORDER model: one interaction per surface (CU-398).

Until 2026-10-04 every cavity quantity was divided by the Airy denominator
``1 - R1*R2*beer^2``, the closed form of the infinite internal-bounce series. Summing
that series is a higher-order term, so it does not belong in a first-order model.

The justification is the **order of the model, not the geometry of the element** (owner
ruling). Whether a lens is curved, wedged or plane-parallel, and at what ray angles, is
detailed ray tracing RADIANT neither performs nor represents, so it cannot be what
selects the formula — and there is therefore no plane-parallel opt-in to test for.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.optics.cavity_model import CavityModel

_WL = np.array([4.0])
rng = np.random.default_rng(398)


def _sd(value: float, name: str) -> SpectralData:
    return SpectralData(
        name=name, wavelength_um=_WL.copy(), values=np.array([value]), unit="", source="test"
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


class TestNoBounceSeries:
    @pytest.mark.level0
    def test_transmittance_is_one_pass(self) -> None:
        """T_sys = T1 * beer * T2, with nothing divided out.

        Hand value: beer = exp(-120 * 0.008) = exp(-0.96) = 0.382892886...
        T_sys = 0.7 * 0.382892886 * 0.6 = 0.160815012...
        """
        c = _cavity(r1=0.3, r2=0.4, alpha=120.0)
        beer = math.exp(-0.96)
        assert c.T_sys.values[0] == pytest.approx(0.7 * beer * 0.6, rel=1e-14)
        assert c.T_sys.values[0] == pytest.approx(0.160815012, rel=1e-8)

    @pytest.mark.level0
    def test_side_one_reflectance_carries_a_single_T1(self) -> None:
        """R_sys = R1 + T1*R2*beer^2 — one T1, not two.

        With no second bounce the ghost off surface 2 exits surface 1 in full. Keeping
        ``T1^2`` here while dropping the series would lose R1*T1*R2*beer^2 of the
        incident power, and the energy identity below would not close.
        """
        c = _cavity(r1=0.3, r2=0.4, alpha=120.0)
        beer = math.exp(-0.96)
        assert c.R_sys.values[0] == pytest.approx(0.3 + 0.7 * 0.4 * beer**2, rel=1e-14)
        # The two-T1 form is materially different — this is not a rounding distinction.
        two_t1 = 0.3 + 0.7**2 * 0.4 * beer**2
        assert c.R_sys.values[0] != pytest.approx(two_t1, rel=1e-3)

    @pytest.mark.level0
    def test_emissivity_has_no_denominator(self) -> None:
        """eps = T2*(1-beer)*(1+R1*beer), exactly the old numerator."""
        c = _cavity(r1=0.3, r2=0.4, alpha=120.0)
        beer = math.exp(-0.96)
        assert c.eps_eff.values[0] == pytest.approx(0.6 * (1 - beer) * (1 + 0.3 * beer), rel=1e-14)

    @pytest.mark.level0
    def test_the_old_model_was_exactly_one_over_denom_higher(self) -> None:
        """Pins the size of the correction, for anyone auditing a moved result."""
        c = _cavity(r1=0.3, r2=0.4, alpha=120.0)
        beer = math.exp(-0.96)
        denom = 1.0 - 0.3 * 0.4 * beer**2
        etalon = 0.6 * (1 - beer) * (1 + 0.3 * beer) / denom
        assert etalon / c.eps_eff.values[0] == pytest.approx(1.0 / denom, rel=1e-14)
        assert c.denom[0] == pytest.approx(denom, rel=1e-14)  # kept as a diagnostic


class TestEnergyClosesExactly:
    @pytest.mark.level0
    def test_identity_holds_over_random_coatings(self) -> None:
        """T_sys + R_side2 + eps = 1, with R_side2 the side-swapped R_sys.

        Exact, not approximate: the truncation was chosen so that it closes. A form
        that merely *nearly* closes is a form that is losing or inventing power.
        """
        worst = 0.0
        for _ in range(3000):
            r1, r2 = rng.uniform(0.0, 0.5, 2)
            alpha = rng.uniform(0.0, 400.0)
            c = _cavity(r1=float(r1), r2=float(r2), alpha=float(alpha))
            beer = c.beer[0]
            r_side2 = r2 + (1.0 - r2) * r1 * beer * beer
            total = c.T_sys.values[0] + r_side2 + c.eps_eff.values[0]
            worst = max(worst, abs(total - 1.0))
        assert worst < 1e-15, worst

    @pytest.mark.level0
    def test_uncoated_glass_closes_exactly_where_the_old_form_could_not(self) -> None:
        """R=0.04 per face, no absorption: 0.9216 + 0.0784 + 0 = 1 exactly.

        The summed-bounce form gave 0.92288 + 0.07693 = 0.99981 here — a 1.9e-4
        shortfall that had to be absorbed by an atol.
        """
        c = _cavity(r1=0.04, r2=0.04, alpha=0.0, d=0.003)
        total = c.T_sys.values[0] + c.R_sys.values[0] + c.eps_eff.values[0]
        assert c.T_sys.values[0] == pytest.approx(0.9216, rel=1e-15)
        assert c.R_sys.values[0] == pytest.approx(0.0784, rel=1e-15)
        assert total == pytest.approx(1.0, abs=1e-15)


class TestTheBoundSurvives:
    @pytest.mark.level0
    def test_emissivity_stays_within_zero_and_one(self) -> None:
        for _ in range(3000):
            r1, r2 = rng.uniform(0.0, 1.0, 2)
            eps = _cavity(r1=float(r1), r2=float(r2), alpha=float(rng.uniform(0.0, 5000.0))).eps_eff
            assert 0.0 <= eps.values[0] <= 1.0

    @pytest.mark.level0
    def test_opaque_slab_behind_a_lossless_window_emits_as_a_blackbody(self) -> None:
        assert _cavity(r1=0.0, r2=0.0, alpha=1.0e6).eps_eff.values[0] == pytest.approx(
            1.0, abs=1e-12
        )

    @pytest.mark.level0
    def test_no_absorption_means_no_emission(self) -> None:
        assert _cavity(r1=0.3, r2=0.4, alpha=0.0).eps_eff.values[0] == pytest.approx(0.0, abs=1e-15)
