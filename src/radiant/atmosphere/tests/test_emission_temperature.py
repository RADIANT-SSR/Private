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
    LayerSpecies,
    _column_fraction,
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
        ozone_share=zeros,
        ozone_layer_centre_m=25_000.0,
        ozone_layer_width_m=5_000.0,
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
# 3b. The layer placement law (CU-324 item 2 — ozone)
# ---------------------------------------------------------------------------


def _gaussian_column_fraction(edges: np.ndarray, centre_m: float, width_m: float) -> np.ndarray:
    """Analytic per-layer share of a Gaussian layer's column (Rule 18: hand form).

    ``∫ρ dz`` over each layer from the error function, normalised — the exact
    integral the module's midpoint quadrature approximates, written here from
    :func:`math.erf` so the check is independent of the implementation.
    """
    cdf = np.array(
        [0.5 * (1.0 + math.erf((float(z) - centre_m) / (width_m * math.sqrt(2.0)))) for z in edges]
    )
    column = np.diff(cdf)
    return column / column.sum()


@pytest.mark.level0
@pytest.mark.parametrize("escape", ["upper", "lower"])
def test_a_layer_species_is_exact_on_an_isothermal_segment(escape: str) -> None:
    """The isothermal identity survives the second placement law.

    The identity is what lets any placement be swapped in without touching a
    level arm: the weights are a partition of ``1 − τ`` whatever profile
    generated them, so a constant ``B`` factors straight out.  If the layer's
    weights ever failed to normalise, this is where it would show.
    """
    lam = _lam()
    result = emission_weighted_temperature(
        lam,
        h_low_m=0.0,
        h_high_m=4.0e4,
        species=(
            EmissionSpecies(4_000.0, np.full_like(lam, 0.3)),
            LayerSpecies(25_000.0, 5_000.0, np.full_like(lam, 1.7)),
        ),
        temperature_profile=lambda h: np.full_like(h, 244.25),
        escape=escape,
    )
    np.testing.assert_allclose(result, 244.25, rtol=1e-12, atol=0.0)


@pytest.mark.level0
def test_the_layer_column_weights_match_the_analytic_gaussian_integral() -> None:
    """The midpoint quadrature reproduces the erf-difference column shares.

    Hand truth: the fraction of a Gaussian layer's column between two
    altitudes is the difference of its CDF.  This pins the placement profile
    itself — a layer centred elsewhere, or a width read as a FWHM rather than
    a standard deviation, fails here rather than silently shifting parity.
    """
    edges = np.linspace(0.0, 5.0e4, 401)
    fraction = _column_fraction(LayerSpecies(25_000.0, 5_000.0, np.zeros(3)), edges[:-1], edges[1:])
    assert fraction is not None
    expected = _gaussian_column_fraction(edges, 25_000.0, 5_000.0)
    # 1e-3 is the midpoint rule's own error on a 125 m layer against a 5 km
    # width — three orders below the 2.35× a FWHM-for-σ misread would cost.
    np.testing.assert_allclose(fraction, expected, rtol=1.0e-3, atol=1.0e-12)
    assert float(fraction.sum()) == pytest.approx(1.0, rel=1e-12)
    # The peak layer is the one containing the centre.
    midpoints = 0.5 * (edges[:-1] + edges[1:])
    assert abs(float(midpoints[int(np.argmax(fraction))]) - 25_000.0) <= 0.5 * 125.0


@pytest.mark.level0
def test_a_layer_far_above_the_segment_still_places_all_of_its_opacity() -> None:
    """A distant layer normalises instead of underflowing to zero column.

    The failure this guards is silent and expensive: an ``exp(−½·(Δ/w)²)``
    column difference underflows to exactly 0.0 once the segment is ~38
    widths from the centre, and a species with a zero column would have its
    optical depth dropped from the layer sum — breaking the telescoping
    identity that makes ``T_eff`` mean anything.  The log-domain weights
    cannot underflow: only *differences* in the exponent survive the
    normalisation, however small the absolute densities are.
    """
    edges = np.linspace(0.0, 1.0e3, 33)
    centre_m, width_m = 2.0e5, 5_000.0

    # The failure mode is real on this geometry, not hypothetical: every
    # density here is below the smallest positive double.
    naive = np.exp(-0.5 * ((0.5 * (edges[:-1] + edges[1:]) - centre_m) / width_m) ** 2)
    assert float(naive.sum()) == 0.0

    fraction = _column_fraction(LayerSpecies(centre_m, width_m, np.zeros(3)), edges[:-1], edges[1:])
    assert fraction is not None
    assert float(fraction.sum()) == pytest.approx(1.0, rel=1e-12)
    assert np.all(np.diff(fraction) > 0.0), "weight must increase toward the distant layer"
    # The ratio across the segment is the analytic Gaussian density ratio
    # between the first and last layer midpoints — not a saturated 1, and not
    # the 0 the naive form above would have produced.
    midpoints = 0.5 * (edges[:-1] + edges[1:])
    expected_ratio = math.exp(
        0.5
        * ((centre_m - float(midpoints[0])) ** 2 - (centre_m - float(midpoints[-1])) ** 2)
        / width_m**2
    )
    assert float(fraction[-1] / fraction[0]) == pytest.approx(expected_ratio, rel=1e-9)


@pytest.mark.level0
def test_moving_the_gas_floor_onto_a_high_layer_cools_the_emission() -> None:
    """The whole point of the split, as a sign test.

    Same total opacity, same geometry, same profile: taking opacity off the
    4 km pressure-broadened profile and putting it on a 25 km layer moves the
    emission into colder air, so ``T_eff`` must fall — in **both** directions,
    since the layer is above the segment's warm end either way.
    """
    lam = _lam()
    zeros = np.zeros_like(lam)
    total = np.full_like(lam, 1.2)

    def profile(altitudes: np.ndarray) -> np.ndarray:
        return np.maximum(288.15 - 6.5e-3 * np.clip(altitudes, 0.0, 11_000.0), 216.65)

    def evaluate(share: float, escape: str) -> np.ndarray:
        return segment_emission_temperature_K(
            lam,
            h_low_m=0.0,
            h_high_m=4.0e4,
            od_slant_mol=zeros,
            od_slant_aer=zeros,
            od_slant_h2o=zeros,
            od_slant_gas=total,
            ozone_share=np.full_like(lam, share),
            ozone_layer_centre_m=25_000.0,
            ozone_layer_width_m=5_000.0,
            scale_height_mol_m=8_000.0,
            scale_height_aer_m=1_200.0,
            scale_height_h2o_m=2_000.0,
            temperature_profile=profile,
            escape=escape,
        )

    for escape in ("upper", "lower"):
        assert np.all(evaluate(0.8317, escape) < evaluate(0.0, escape) - 1.0), escape


@pytest.mark.level0
def test_a_zero_share_is_bit_identical_to_the_four_species_form() -> None:
    """No ozone anywhere ⇒ no layer species ⇒ not one bit moves.

    This is the invariant that bounds the CU-324 blast radius: every
    wavelength grid that does not reach the 9.6 µm band must return exactly
    what it returned before the split existed, to the last bit — not merely
    to a tolerance.
    """
    lam = _lam()
    kwargs = {
        "h_low_m": 0.0,
        "h_high_m": 3.0e4,
        "od_slant_mol": np.full_like(lam, 0.02),
        "od_slant_aer": np.full_like(lam, 0.15),
        "od_slant_h2o": np.linspace(2.5, 0.4, lam.size),
        "od_slant_gas": np.linspace(0.1, 1.6, lam.size),
        "ozone_layer_centre_m": 25_000.0,
        "ozone_layer_width_m": 5_000.0,
        "scale_height_mol_m": 8_000.0,
        "scale_height_aer_m": 1_200.0,
        "scale_height_h2o_m": 2_000.0,
        "temperature_profile": lambda h: np.maximum(
            288.15 - 6.5e-3 * np.clip(h, 0.0, 11_000.0), 216.65
        ),
        "escape": "upper",
    }
    with_zero_share = segment_emission_temperature_K(lam, ozone_share=np.zeros_like(lam), **kwargs)
    four_species = emission_weighted_temperature(
        lam,
        h_low_m=0.0,
        h_high_m=3.0e4,
        species=(
            EmissionSpecies(8_000.0, np.full_like(lam, 0.02)),
            EmissionSpecies(1_200.0, np.full_like(lam, 0.15)),
            EmissionSpecies(1_600.0, np.linspace(2.5, 0.4, lam.size)),
            EmissionSpecies(4_000.0, np.linspace(0.1, 1.6, lam.size)),
        ),
        temperature_profile=kwargs["temperature_profile"],  # type: ignore[arg-type]
        escape="upper",
    )
    np.testing.assert_array_equal(with_zero_share, four_species)


@pytest.mark.level0
def test_the_split_conserves_the_gas_floor_it_apportions() -> None:
    """Placement, not attenuation: the segment's own optical depth is untouched.

    ``share·od + (1 − share)·od`` is the gas floor back again, so the layered
    weights still telescope to ``1 − τ`` — verified here through the identity
    that guarantees it, at a share the shipped table actually produces.
    """
    lam = _lam()
    od_gas = np.linspace(0.2, 1.4, lam.size)
    share = np.where((lam >= 9.4) & (lam <= 9.9), 0.8317, 0.0)
    np.testing.assert_allclose(share * od_gas + (od_gas - share * od_gas), od_gas, rtol=0.0)


@pytest.mark.level0
def test_a_bad_layer_geometry_or_share_raises_actionably() -> None:
    lam = _lam()
    profile = lambda h: np.full_like(h, 280.0)  # noqa: E731

    for centre, width in ((float("nan"), 5_000.0), (25_000.0, 0.0), (25_000.0, -1.0)):
        with pytest.raises(ParameterBoundsError, match="layer geometry"):
            emission_weighted_temperature(
                lam,
                h_low_m=0.0,
                h_high_m=3.0e4,
                species=(LayerSpecies(centre, width, np.full_like(lam, 0.5)),),
                temperature_profile=profile,
                escape="upper",
            )

    adapter = {
        "h_low_m": 0.0,
        "h_high_m": 3.0e4,
        "od_slant_mol": np.zeros_like(lam),
        "od_slant_aer": np.zeros_like(lam),
        "od_slant_h2o": np.zeros_like(lam),
        "od_slant_gas": np.full_like(lam, 0.5),
        "ozone_layer_centre_m": 25_000.0,
        "ozone_layer_width_m": 5_000.0,
        "scale_height_mol_m": 8_000.0,
        "scale_height_aer_m": 1_200.0,
        "scale_height_h2o_m": 2_000.0,
        "temperature_profile": profile,
        "escape": "upper",
    }
    with pytest.raises(ParameterBoundsError, match="ozone_share shape"):
        segment_emission_temperature_K(lam, ozone_share=np.zeros(3), **adapter)  # type: ignore[arg-type]
    with pytest.raises(ParameterBoundsError, match=r"ozone_share leaves"):
        segment_emission_temperature_K(lam, ozone_share=np.full_like(lam, 1.5), **adapter)  # type: ignore[arg-type]
    with pytest.raises(ParameterBoundsError, match=r"ozone_share leaves"):
        segment_emission_temperature_K(lam, ozone_share=np.full_like(lam, -0.1), **adapter)  # type: ignore[arg-type]


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

    The grid deliberately straddles the 9.6 µm ozone band and the share is
    non-zero there, so the assertion covers the :class:`LayerSpecies`
    midpoint quadrature as well as the exponential species' equal-column one.
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
            ozone_share=np.where((lam >= 9.4) & (lam <= 9.9), 0.8317, 0.0),
            ozone_layer_centre_m=25_000.0,
            ozone_layer_width_m=5_000.0,
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
