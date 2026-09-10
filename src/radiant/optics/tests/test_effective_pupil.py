"""Level 0 tests for the effective (cold-stop) pupil (Gap 128).

The load-bearing property is the **bit-identity** of the default: with
``u = 0`` and no cold-shield obscuration, the effective pupil must be the
primary pupil to the last bit, so every existing result is untouched.
"""

from __future__ import annotations

import math

import pytest

from radiant.optics.effective_pupil import MAX_UNDERSIZE_FRAC, resolve_effective_pupil
from radiant.optics.errors import OpticsValidationError


class TestDefaultBitIdentity:
    """u = 0, cold-shield obscuration = 0 ⇒ the primary pupil, exactly."""

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("d_m", "eps", "n"),
        [
            (0.3, 0.0, 6.0),
            (0.135, 0.35, 6.562962962962963),
            (1.7, 0.29, 12.3),
            (0.0254, 0.0, 1.4),
        ],
    )
    def test_exact_float_identity(self, d_m: float, eps: float, n: float) -> None:
        pupil = resolve_effective_pupil(d_m, eps, n, 0.0, 0.0)
        # Exact equality, not approx: (1 - 0.0) * D and max(eps, 0.0) are exact,
        # and N * (D / D) is N * 1.0 = N.
        assert pupil.diameter_m == d_m
        assert pupil.obscuration_ratio == eps
        assert pupil.f_number == n

    @pytest.mark.level0
    def test_f_number_not_rederived_from_f_and_d(self) -> None:
        """N_eff reuses the entered f/# rather than recomputing f/D.

        The {D, f, f/#} consistency group tolerates 1e-3 disagreement, so
        re-deriving would move results at u = 0. Feeding a deliberately
        off-by-0.05 % f/# must come back unchanged.
        """
        pupil = resolve_effective_pupil(0.135, 0.0, 6.5, 0.0, 0.0)
        assert pupil.f_number == 6.5


class TestUndersizing:
    """The arithmetic of a stop smaller than the primary."""

    @pytest.mark.level0
    def test_diameter_scales_linearly(self) -> None:
        """D_eff = (1 − u)·D: 5 % undersize on 0.3 m ⇒ 0.285 m."""
        pupil = resolve_effective_pupil(0.3, 0.0, 6.0, 0.05, 0.0)
        assert pupil.diameter_m == pytest.approx(0.285, rel=1e-15)

    @pytest.mark.level0
    def test_f_number_grows_as_pupil_shrinks(self) -> None:
        """N_eff = f/D_eff = N/(1 − u): f/6 at 5 % undersize ⇒ f/6.3158."""
        pupil = resolve_effective_pupil(0.3, 0.0, 6.0, 0.05, 0.0)
        assert pupil.f_number == pytest.approx(6.0 / 0.95, rel=1e-14)

    @pytest.mark.level0
    def test_collecting_area_scales_as_one_minus_u_squared(self) -> None:
        """Area ∝ D²: a 10 % undersized stop collects 81 % of the light."""
        pupil = resolve_effective_pupil(0.3, 0.0, 6.0, 0.10, 0.0)
        area_ratio = (pupil.diameter_m / 0.3) ** 2
        assert area_ratio == pytest.approx(0.81, rel=1e-14)

    @pytest.mark.level1
    def test_provenance_fields_retained(self) -> None:
        pupil = resolve_effective_pupil(0.3, 0.1, 6.0, 0.05, 0.0)
        assert pupil.primary_diameter_m == 0.3
        assert pupil.undersize_frac == 0.05


class TestEffectiveObscuration:
    """obs_eff = max(primary, cold shield) — the owner-ratified rule."""

    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("eps_primary", "eps_shield", "expected"),
        [(0.0, 0.0, 0.0), (0.35, 0.0, 0.35), (0.0, 0.2, 0.2), (0.35, 0.2, 0.35), (0.2, 0.4, 0.4)],
    )
    def test_larger_obscuration_governs(
        self, eps_primary: float, eps_shield: float, expected: float
    ) -> None:
        pupil = resolve_effective_pupil(0.3, eps_primary, 6.0, 0.0, eps_shield)
        assert pupil.obscuration_ratio == expected


class TestEtendueCeiling:
    """No configuration can outrun the Lagrange invariant."""

    @pytest.mark.level0
    def test_undersizing_always_shrinks_the_cone(self) -> None:
        """Undersizing raises N_eff, so Ω_cone can only fall — never rise."""
        from radiant.optics.etendue_cone import etendue_cone_solid_angle_sr

        base = etendue_cone_solid_angle_sr(
            resolve_effective_pupil(0.3, 0.0, 6.0, 0.0, 0.0).f_number
        )
        for u in (0.02, 0.05, 0.10, 0.25, 0.48):
            omega = etendue_cone_solid_angle_sr(
                resolve_effective_pupil(0.3, 0.0, 6.0, u, 0.0).f_number
            )
            assert 0.0 < omega < base

    @pytest.mark.level0
    def test_cone_stays_below_hemisphere_across_the_bound(self) -> None:
        """Even the fastest schema-legal system stays inside 2π sr."""
        from radiant.optics.etendue_cone import etendue_cone_solid_angle_sr

        pupil = resolve_effective_pupil(1.0, 0.0, 0.3, 0.0, 0.0)  # f/0.3, the schema floor
        assert etendue_cone_solid_angle_sr(pupil.f_number) < 2.0 * math.pi


class TestFailureModes:
    """Edge-of-domain and invalid inputs."""

    @pytest.mark.level1
    @pytest.mark.parametrize("bad", [0.0, -0.3, float("nan"), float("inf")])
    def test_invalid_diameter_raises(self, bad: float) -> None:
        with pytest.raises(OpticsValidationError, match="aperture_diameter_m"):
            resolve_effective_pupil(bad, 0.0, 6.0, 0.0, 0.0)

    @pytest.mark.level1
    @pytest.mark.parametrize("bad", [0.0, -6.0, float("nan")])
    def test_invalid_f_number_raises(self, bad: float) -> None:
        with pytest.raises(OpticsValidationError, match="f_number"):
            resolve_effective_pupil(0.3, 0.0, bad, 0.0, 0.0)

    @pytest.mark.level1
    @pytest.mark.parametrize("bad", [-0.01, MAX_UNDERSIZE_FRAC, 1.0, float("nan")])
    def test_undersize_out_of_range_raises(self, bad: float) -> None:
        with pytest.raises(OpticsValidationError, match="cold_stop_undersize_frac"):
            resolve_effective_pupil(0.3, 0.0, 6.0, bad, 0.0)

    @pytest.mark.level1
    @pytest.mark.parametrize("bad", [-0.01, 1.0, 1.5, float("nan")])
    def test_cold_stop_obscuration_out_of_range_raises(self, bad: float) -> None:
        with pytest.raises(OpticsValidationError, match="cold_stop_obscuration_ratio"):
            resolve_effective_pupil(0.3, 0.0, 6.0, 0.0, bad)

    @pytest.mark.level1
    def test_extreme_but_legal_undersize(self) -> None:
        """Just inside the bound: u = 0.489 ⇒ 26 % of the light, f/# doubled."""
        pupil = resolve_effective_pupil(0.3, 0.0, 6.0, 0.489, 0.0)
        assert pupil.diameter_m == pytest.approx(0.1533, rel=1e-9)
        assert pupil.f_number == pytest.approx(6.0 / 0.511, rel=1e-12)
