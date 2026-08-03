"""Level-0 anchors for the height-resolved emission temperature (CU-321).

Every expectation here is a hand value or an analytic identity — none of it is
produced by another RADIANT physics module.  The Planck inversion is checked
against the longhand Planck law written from ``radiant.core.constants``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.emission_temperature import (
    EMISSION_LAYERS_PER_SPECIES,
    EmissionSpecies,
    emission_weighted_temperature,
    pressure_broadened_scale_height_m,
    segment_emission_temperature_K,
)
from radiant.core.constants import c, h, k_B
from radiant.core.parameters import ParameterBoundsError


def _planck_longhand(lam_um: np.ndarray, t_K: np.ndarray | float) -> np.ndarray:
    """B(λ, T) [W/m²/sr/µm] from first principles (Rule 18 independence)."""
    lam_m = np.asarray(lam_um, dtype=np.float64) * 1.0e-6
    return 2.0 * h * c**2 / lam_m**5 / np.expm1(h * c / (lam_m * k_B * np.asarray(t_K))) * 1.0e-6


def _lam() -> np.ndarray:
    return np.linspace(3.0, 12.0, 19)


# ---------------------------------------------------------------------------
# 1. The isothermal identity — exact, in both directions, at any opacity
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("escape", ["upper", "lower"])
@pytest.mark.parametrize("od_scale", [1.0e-9, 0.3, 3.0, 40.0])
def test_isothermal_atmosphere_returns_that_temperature_exactly(
    escape: str, od_scale: float
) -> None:
    """An isothermal segment emits at its own temperature — for every τ.

    This is the identity that lets the new form replace the old one without
    changing a level arm by a single bit: the weights are a partition of
    ``1 − τ`` whatever they are, so a constant ``B`` factors straight out.
    """
    lam = _lam()
    t_iso = 271.5
    result = emission_weighted_temperature(
        lam,
        h_low_m=0.0,
        h_high_m=2.0e4,
        species=(
            EmissionSpecies(8_000.0, np.full_like(lam, od_scale)),
            EmissionSpecies(2_000.0, np.full_like(lam, 0.5 * od_scale)),
        ),
        temperature_profile=lambda h: np.full_like(h, t_iso),
        escape=escape,  # type: ignore[arg-type]
    )
    np.testing.assert_allclose(result, t_iso, rtol=1e-12, atol=0.0)


@pytest.mark.level0
def test_zero_thickness_segment_is_the_level_isothermal_case() -> None:
    """``h_low == h_high`` returns the profile temperature there, exactly."""
    lam = _lam()
    result = emission_weighted_temperature(
        lam,
        h_low_m=3.0e3,
        h_high_m=3.0e3,
        species=(EmissionSpecies(8_000.0, np.full_like(lam, 0.7)),),
        temperature_profile=lambda h: 300.0 - 6.5e-3 * h,
        escape="lower",
    )
    np.testing.assert_allclose(result, 300.0 - 6.5e-3 * 3.0e3, rtol=1e-14, atol=0.0)


# ---------------------------------------------------------------------------
# 2. A two-layer toy atmosphere against the hand-computed formal solution
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("escape", ["upper", "lower"])
def test_two_slab_toy_atmosphere_matches_the_hand_formal_solution(escape: str) -> None:
    """Two equal-opacity slabs, hand-evaluated ``Σ B_i (1−e^{−δ}) e^{−c_i}``.

    The construction: one species and ``layers_per_species = 2``, which by
    definition cuts the segment into two slabs of exactly equal
    ``∫exp(−h/H) dh`` — so each carries ``δ = od_total/2`` — with a
    temperature profile that is piecewise constant across the cut, so each
    slab's temperature is unambiguous whatever altitude the layer midpoint
    lands on.  Everything on the right-hand side is then hand arithmetic:
    two weights, two Planck curves (written longhand from the constants) and
    one longhand Planck inversion.
    """
    lam = np.array([4.0, 10.0])
    scale_height = 5_000.0
    h_high = 2.0e4
    od_total = 1.6
    # layers_per_species = 2 ⇒ two slabs of equal ∫exp(−h/H)dh ⇒ δ = od/2 each.
    cut = -scale_height * math.log1p(-0.5 * -math.expm1(-h_high / scale_height))
    t_cold, t_warm = 230.0, 290.0

    def profile(altitudes: np.ndarray) -> np.ndarray:
        return np.where(altitudes < cut, t_warm, t_cold)

    result = emission_weighted_temperature(
        lam,
        h_low_m=0.0,
        h_high_m=h_high,
        species=(EmissionSpecies(scale_height, np.full_like(lam, od_total)),),
        temperature_profile=profile,
        escape=escape,  # type: ignore[arg-type]
        layers_per_species=2,
    )

    delta = 0.5 * od_total
    first, second = (t_warm, t_cold) if escape == "lower" else (t_cold, t_warm)
    w1 = -math.expm1(-delta)
    w2 = -math.expm1(-delta) * math.exp(-delta)
    b_eff = (w1 * _planck_longhand(lam, first) + w2 * _planck_longhand(lam, second)) / (w1 + w2)
    # Invert Planck by hand: T = hc / (λ k_B ln(1 + 2hc²/(λ⁵ L)))
    lam_m = lam * 1.0e-6
    expected = h * c / (lam_m * k_B * np.log1p(2.0 * h * c**2 / (lam_m**5 * b_eff * 1.0e6)))
    np.testing.assert_allclose(result, expected, rtol=1e-12, atol=0.0)
    # And the weights partition 1 − τ exactly.
    assert w1 + w2 == pytest.approx(-math.expm1(-od_total), rel=1e-14)


@pytest.mark.level0
def test_direction_reverses_which_slab_dominates() -> None:
    """The warm slab is at the bottom, so ``lower`` is warmer than ``upper``."""
    lam = np.array([4.0, 10.0])
    kwargs = {
        "h_low_m": 0.0,
        "h_high_m": 2.0e4,
        "species": (EmissionSpecies(5_000.0, np.full_like(lam, 1.6)),),
        "temperature_profile": lambda h: np.where(h < 4_000.0, 290.0, 230.0),
        "layers_per_species": 2,
    }
    warm = emission_weighted_temperature(lam, escape="lower", **kwargs)  # type: ignore[arg-type]
    cold = emission_weighted_temperature(lam, escape="upper", **kwargs)  # type: ignore[arg-type]
    assert np.all(warm > cold)
    assert np.all((cold >= 230.0 - 1e-9) & (warm <= 290.0 + 1e-9))


# ---------------------------------------------------------------------------
# 3. The pressure-broadening rule
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_pressure_broadened_scale_height_halves_a_well_mixed_absorber() -> None:
    """``α ∝ n·p`` ⇒ ``H/2`` for a well-mixed gas; harmonic sum in general."""
    assert pressure_broadened_scale_height_m(8_000.0, 8_000.0) == pytest.approx(4_000.0, rel=1e-14)
    assert pressure_broadened_scale_height_m(2_000.0, 8_000.0) == pytest.approx(1_600.0, rel=1e-14)
    # Harmonic combination is symmetric and always below both inputs.
    assert pressure_broadened_scale_height_m(1_200.0, 8_000.0) < 1_200.0


@pytest.mark.level0
@pytest.mark.parametrize("bad", [0.0, -1.0, float("inf"), float("nan")])
def test_pressure_broadened_scale_height_refuses_non_positive(bad: float) -> None:
    with pytest.raises(ParameterBoundsError):
        pressure_broadened_scale_height_m(bad, 8_000.0)
    with pytest.raises(ParameterBoundsError):
        pressure_broadened_scale_height_m(8_000.0, bad)


@pytest.mark.level0
def test_adapter_places_the_pressure_broadened_species_lower() -> None:
    """The adapter's gas floor emits from lower air than a density-profile one.

    Same total opacity, same geometry, escape at the top: putting the gas on
    4 km instead of 8 km moves its emission down into warmer air, so ``T_eff``
    must rise.
    """
    lam = _lam()
    zeros = np.zeros_like(lam)
    gas = np.full_like(lam, 2.0)

    def profile(altitudes: np.ndarray) -> np.ndarray:
        return np.maximum(288.15 - 6.5e-3 * np.clip(altitudes, 0.0, 11_000.0), 216.65)

    broadened = segment_emission_temperature_K(
        lam,
        h_low_m=0.0,
        h_high_m=3.0e4,
        od_slant_mol=zeros,
        od_slant_aer=zeros,
        od_slant_h2o=zeros,
        od_slant_gas=gas,
        scale_height_mol_m=8_000.0,
        scale_height_aer_m=1_200.0,
        scale_height_h2o_m=2_000.0,
        temperature_profile=profile,
        escape="upper",
    )
    unbroadened = emission_weighted_temperature(
        lam,
        h_low_m=0.0,
        h_high_m=3.0e4,
        species=(EmissionSpecies(8_000.0, gas),),
        temperature_profile=profile,
        escape="upper",
    )
    assert np.all(broadened > unbroadened + 1.0)


# ---------------------------------------------------------------------------
# 4. Failure modes and the vacuum limit
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_zero_opacity_returns_the_lower_endpoint_temperature_not_nan() -> None:
    """No absorber ⇒ nothing to weight; the value is finite and physical."""
    lam = _lam()
    result = emission_weighted_temperature(
        lam,
        h_low_m=1.0e3,
        h_high_m=2.0e4,
        species=(EmissionSpecies(8_000.0, np.zeros_like(lam)),),
        temperature_profile=lambda h: 300.0 - 6.5e-3 * h,
        escape="upper",
    )
    assert np.all(np.isfinite(result))
    assert np.all(result > 200.0)


@pytest.mark.level0
def test_a_species_whose_column_underflows_is_skipped_not_nan() -> None:
    """A 1.2 km aerosol profile 60 km up contributes no placeable opacity."""
    lam = _lam()
    result = emission_weighted_temperature(
        lam,
        h_low_m=6.0e4,
        h_high_m=8.0e4,
        species=(
            EmissionSpecies(1_200.0, np.full_like(lam, 0.1)),
            EmissionSpecies(8_000.0, np.full_like(lam, 0.4)),
        ),
        temperature_profile=lambda h: np.full_like(h, 216.65),
        escape="upper",
    )
    np.testing.assert_allclose(result, 216.65, rtol=1e-12, atol=0.0)


@pytest.mark.level0
def test_result_is_always_inside_the_layer_temperature_range() -> None:
    """A convex combination of Planck curves cannot leave the T range."""
    lam = np.linspace(3.0, 14.0, 45)
    result = emission_weighted_temperature(
        lam,
        h_low_m=0.0,
        h_high_m=1.0e5,
        species=(
            EmissionSpecies(8_000.0, np.linspace(0.05, 4.0, lam.size)),
            EmissionSpecies(1_600.0, np.linspace(4.0, 0.05, lam.size)),
        ),
        temperature_profile=lambda h: np.maximum(
            294.15 - 6.5e-3 * np.clip(h, 0.0, 11_000.0), 216.65
        ),
        escape="upper",
    )
    assert float(result.min()) >= 216.65 - 1e-9
    assert float(result.max()) <= 294.15 + 1e-9


@pytest.mark.level0
def test_invalid_inputs_raise_actionable_errors() -> None:
    lam = _lam()
    good = (EmissionSpecies(8_000.0, np.full_like(lam, 0.5)),)
    profile = lambda h: np.full_like(h, 280.0)  # noqa: E731

    with pytest.raises(ParameterBoundsError, match="escape"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=good,
            temperature_profile=profile,
            escape="sideways",  # type: ignore[arg-type]
        )
    with pytest.raises(ParameterBoundsError, match="ordered interval"):
        emission_weighted_temperature(
            lam,
            h_low_m=1.0e4,
            h_high_m=0.0,
            species=good,
            temperature_profile=profile,
            escape="upper",
        )
    with pytest.raises(ParameterBoundsError, match="no species"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=(),
            temperature_profile=profile,
            escape="upper",
        )
    with pytest.raises(ParameterBoundsError, match="does not match"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=(EmissionSpecies(8_000.0, np.zeros(3)),),
            temperature_profile=profile,
            escape="upper",
        )
    with pytest.raises(ParameterBoundsError, match="non-negative"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=(EmissionSpecies(8_000.0, np.full_like(lam, -0.1)),),
            temperature_profile=profile,
            escape="upper",
        )
    with pytest.raises(ParameterBoundsError, match="scale_height_m"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=(EmissionSpecies(0.0, np.full_like(lam, 0.1)),),
            temperature_profile=profile,
            escape="upper",
        )
    with pytest.raises(ParameterBoundsError, match="layers_per_species"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=good,
            temperature_profile=profile,
            escape="upper",
            layers_per_species=0,
        )
    with pytest.raises(ParameterBoundsError, match="temperature_profile"):
        emission_weighted_temperature(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e4,
            species=good,
            temperature_profile=lambda h: np.zeros_like(h),
            escape="upper",
        )


# ---------------------------------------------------------------------------
# 5. Quadrature convergence — the layer count is a numerical parameter
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_layer_quadrature_is_converged_at_the_shipped_resolution() -> None:
    """The shipped resolution is within 0.05 K of a 16× finer reference.

    The module's docstring claims the layer count is a converged quadrature,
    not a tuning knob.  This is that claim's teeth: if a future edit changes
    the layering scheme in a way that costs accuracy, it fails here rather
    than silently shifting every thermal path radiance.
    """
    lam = np.linspace(3.0, 12.0, 37)

    def profile(altitudes: np.ndarray) -> np.ndarray:
        return np.maximum(294.15 - 6.5e-3 * np.clip(altitudes, 0.0, 11_000.0), 216.65)

    def evaluate(n: int) -> np.ndarray:
        return segment_emission_temperature_K(
            lam,
            h_low_m=0.0,
            h_high_m=1.0e5,
            od_slant_mol=np.full_like(lam, 0.02),
            od_slant_aer=np.full_like(lam, 0.15),
            od_slant_h2o=np.linspace(2.5, 0.4, lam.size),
            od_slant_gas=np.linspace(0.1, 1.6, lam.size),
            scale_height_mol_m=8_000.0,
            scale_height_aer_m=1_200.0,
            scale_height_h2o_m=2_000.0,
            temperature_profile=profile,
            escape="upper",
            layers_per_species=n,
        )

    reference = evaluate(16 * EMISSION_LAYERS_PER_SPECIES)
    shipped = evaluate(EMISSION_LAYERS_PER_SPECIES)
    assert float(np.max(np.abs(shipped - reference))) < 0.05
    # …and the coarse end really is coarse, so the test is not vacuous.
    assert float(np.max(np.abs(evaluate(2) - reference))) > 0.5
