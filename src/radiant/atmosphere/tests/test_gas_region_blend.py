"""Level-0 tests for the CU-267 gas-region coefficient blend.

The calibrated gas-band table ``_CALIBRATED_GAS_REGIONS`` is
piecewise-constant in ``(floor_od, k_h2o, b_h2o)``. Read literally it
makes ``τ(λ)`` step discontinuously at all fourteen interior region
edges (measured: −90 % at 2.40 µm, +821 % relative at 8.00 µm), which
in turn makes any band-mean τ that straddles an edge depend on the
sampling grid. CU-267 replaces the step with a C¹ smoothstep ramp of
half-width ``GAS_REGION_BLEND_HALF_WIDTH_UM`` on each edge.

The blend is defined analytically, so these are Level-0 tests against
hand-derived values rather than against other RADIANT code:

    u(λ) = clip(0.5 + (λ − λ_edge) / (2·hw), 0, 1)
    S(u) = u²·(3 − 2u)                    # C¹ smoothstep
    c(λ) = c_lo + (c_hi − c_lo)·S(u)

with ``S(0) = 0``, ``S(1) = 1``, ``S(0.5) = 0.5``, ``S'(0) = S'(1) = 0``
and ``S'(u) = 6u(1 − u)``.

Coverage:

(a) continuity and C¹ smoothness across a region edge — the coefficient
    is continuous at the edge and its derivative matches the analytic
    smoothstep derivative everywhere in the ramp (including vanishing
    at both ramp ends, which is what makes it C¹ rather than a kinked
    linear interpolation);
(b) interior invariance — any λ at or beyond ``hw`` from every edge
    keeps the *bit-identical* unblended table coefficients, so bands
    that cross no edge (3.7–4.8 µm, 10.6–11.2 µm) are untouched;
(c) hand-computed anchor at an edge — at λ = λ_edge exactly the blended
    coefficient is the arithmetic mean of the two regions' values,
    because S(0.5) = 0.5 exactly;
(d) the no-overlap invariant — every region is wider than the full
    blend width, so no two ramps can ever overlap. This is the guard
    that stops a future table edit from silently breaking the blend.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere.simple import (
    _CALIBRATED_GAS_REGIONS,
    GAS_REGION_BLEND_HALF_WIDTH_UM,
    AtmosphericGeometry,
    SimpleAtmosphere,
    _GasRegion,
)

HW: float = GAS_REGION_BLEND_HALF_WIDTH_UM

# Interior region edges [µm]: every ``lo_um`` after the first region.
EDGES: tuple[float, ...] = tuple(r.lo_um for r in _CALIBRATED_GAS_REGIONS[1:])

# Coefficient index in the ``_region_params`` return tuple.
_COEFF_NAMES = ("floor_od", "k_h2o", "b_h2o")


def _coeffs(lam: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Blended (floor_od, k_h2o, b_h2o) on the given wavelength grid."""
    return SimpleAtmosphere._region_params(np.asarray(lam, dtype=np.float64))  # noqa: SLF001


def _region_pair(edge_um: float) -> tuple[_GasRegion, _GasRegion]:
    """The (below, above) regions meeting at ``edge_um``."""
    for lo, hi in zip(_CALIBRATED_GAS_REGIONS[:-1], _CALIBRATED_GAS_REGIONS[1:], strict=True):
        if hi.lo_um == edge_um:
            return lo, hi
    raise AssertionError(f"{edge_um} is not a region edge")


# ----------------------------------------------------------------------
# (d) No-overlap invariant — checked first: everything else assumes it.
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_blend_ramps_never_overlap() -> None:
    """Every region is wider than the full blend width 2·hw.

    A ramp occupies ``[λ_edge − hw, λ_edge + hw]``. Region *i* carries
    the ramps of both of its edges, so non-overlap requires
    ``hi_um − lo_um > 2·hw`` — i.e. a strip of un-blended, exactly
    calibrated coefficients survives inside every region. The narrowest
    shipped region is 1.30–1.50 µm at 0.20 µm, five times the 0.04 µm
    full width.
    """
    full_width = 2.0 * HW
    for region in _CALIBRATED_GAS_REGIONS:
        width = region.hi_um - region.lo_um
        assert width > full_width, (
            f"region {region.lo_um}–{region.hi_um} µm is {width} µm wide, "
            f"not wider than the {full_width} µm blend width: the blend ramps "
            f"of its two edges would overlap and the region's calibrated "
            f"coefficients would never be reached"
        )


# ----------------------------------------------------------------------
# (a) Continuity and C¹ smoothness
# ----------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", EDGES)
def test_coefficients_continuous_at_every_edge(edge_um: float) -> None:
    """No coefficient steps across a region edge.

    Evaluated ±1e-9 µm either side of each edge — the same probe the
    CU-267 measurement used. Unblended, ``k_h2o`` alone steps by up to
    1.09 here (1.30 µm edge).
    """
    eps = 1.0e-9
    below = _coeffs(np.array([edge_um - eps]))
    above = _coeffs(np.array([edge_um + eps]))
    for name, lo_val, hi_val in zip(_COEFF_NAMES, below, above, strict=True):
        jump = abs(float(hi_val[0]) - float(lo_val[0]))
        assert jump < 1.0e-6, f"{name} steps by {jump} across the {edge_um} µm edge"


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", [0.70, 3.50, 8.00])
def test_coefficient_derivative_matches_analytic_smoothstep(edge_um: float) -> None:
    """dc/dλ across a ramp equals the analytic smoothstep derivative.

    ``S'(u) = 6u(1 − u)`` and ``du/dλ = 1/(2·hw)``, so

        dc/dλ = (c_hi − c_lo) · 6u(1 − u) / (2·hw)

    This is the C¹ statement in its strongest form: it pins the
    derivative to a *continuous* function that vanishes at both ramp
    ends (u = 0 and u = 1), where the ramp meets the flat calibrated
    regions. A linear ramp — continuous but not C¹ — would give a
    constant, non-vanishing derivative and fail here; a step gives an
    unbounded one.
    """
    lo_region, hi_region = _region_pair(edge_um)
    lam = np.linspace(edge_um - 0.999 * HW, edge_um + 0.999 * HW, 2001)
    d_lam = float(lam[1] - lam[0])
    u = 0.5 + (lam - edge_um) / (2.0 * HW)

    for name, values, lo_val, hi_val in zip(
        _COEFF_NAMES,
        _coeffs(lam),
        (lo_region.floor_od, lo_region.k_h2o, lo_region.b_h2o),
        (hi_region.floor_od, hi_region.k_h2o, hi_region.b_h2o),
        strict=True,
    ):
        delta = hi_val - lo_val
        if delta == 0.0:
            assert np.all(values == lo_val), f"{name} moved though the two regions agree"
            continue
        # Central differences only: np.gradient's one-sided endpoints
        # carry a first-order truncation error that has nothing to say
        # about the blend.
        numeric = np.gradient(values, d_lam)[1:-1]
        analytic = (delta * 6.0 * u * (1.0 - u) / (2.0 * HW))[1:-1]
        scale = 1.5 * abs(delta) / (2.0 * HW)  # peak analytic slope, at u = 0.5
        # A linear (C⁰-only) ramp would sit 0.67·scale away at the ramp
        # ends; a step is unbounded. 1e-4·scale is the central-difference
        # truncation floor, and is two orders sharper than either.
        assert np.max(np.abs(numeric - analytic)) < 1.0e-4 * scale, (
            f"{name} derivative across the {edge_um} µm edge is not the "
            f"analytic smoothstep derivative"
        )


@pytest.mark.level0
def test_transmittance_continuous_across_edge() -> None:
    """τ(λ) itself is continuous across the 0.70 µm edge.

    The CU-267 symptom in the form a reader reproduces it: a vertical
    ground → 700 km midlat-summer column stepped 0.824 → 0.680 across
    one grid point at 0.70 µm (−17.5 %). The blended model must move by
    far less than that across the same probe, and the whole traverse of
    the ramp must be monotone-bounded by the smoothstep's Lipschitz
    constant rather than jumping.
    """
    atm = SimpleAtmosphere(standard_atmosphere="midlat_summer", precipitable_water_cm=2.92)
    geo = AtmosphericGeometry(
        sensor_altitude_m=700_000.0, target_altitude_m=0.0, path_zenith_rad=0.0
    )
    eps = 1.0e-9
    lam = np.array([0.70 - eps, 0.70 + eps])
    tau = atm.build_state(lam, geo).transmittance.values
    assert abs(float(tau[1] - tau[0])) < 1.0e-6, (
        f"τ steps {float(tau[0])} → {float(tau[1])} across the 0.70 µm edge"
    )


# ----------------------------------------------------------------------
# (b) Interior invariance — bit-identical to the unblended table
# ----------------------------------------------------------------------


@pytest.mark.level0
def test_interior_wavelengths_keep_exact_table_coefficients() -> None:
    """Points ≥ hw from every edge carry the exact calibrated values.

    Bit-identical, not approximately equal: the blend must not perturb
    the interior of a region at all, or every existing calibration
    anchor and golden baseline would move.
    """
    for region in _CALIBRATED_GAS_REGIONS:
        lam = np.linspace(region.lo_um + HW, region.hi_um - HW, 37)
        floor, k, b = _coeffs(lam)
        assert np.all(floor == region.floor_od), f"floor_od moved inside {region}"
        assert np.all(k == region.k_h2o), f"k_h2o moved inside {region}"
        assert np.all(b == region.b_h2o), f"b_h2o moved inside {region}"


@pytest.mark.level0
@pytest.mark.parametrize(
    ("band", "expected"),
    [
        ((3.7, 4.8), (0.4498, 0.0944, 0.808)),  # interior of 3.50–5.00 µm
        ((10.6, 11.2), (0.0471, 0.0602, 1.750)),  # interior of 10.00–12.00 µm
    ],
)
def test_interior_control_bands_are_untouched(
    band: tuple[float, float], expected: tuple[float, float, float]
) -> None:
    """The two shipped bands that cross no edge see the raw table.

    3.7–4.8 µm and 10.6–11.2 µm are CU-267's interior controls: their
    band-mean τ must be bit-identical before and after the blend, which
    holds iff every coefficient on the band is the unblended value.
    """
    lam = np.linspace(band[0], band[1], 401)
    for name, values, want in zip(_COEFF_NAMES, _coeffs(lam), expected, strict=True):
        assert np.all(values == want), f"{name} is not exactly {want} across {band} µm"


@pytest.mark.level0
def test_clamped_ends_keep_edge_region_coefficients() -> None:
    """Outside the 0.30–14.29 µm table the edge regions still clamp."""
    first, last = _CALIBRATED_GAS_REGIONS[0], _CALIBRATED_GAS_REGIONS[-1]
    floor, k, b = _coeffs(np.array([0.05, 0.20, 20.0, 100.0]))
    assert float(floor[0]) == first.floor_od
    assert float(k[1]) == first.k_h2o
    assert float(b[1]) == first.b_h2o
    assert float(floor[2]) == last.floor_od
    assert float(k[3]) == last.k_h2o
    assert float(b[3]) == last.b_h2o


# ----------------------------------------------------------------------
# (c) Hand-computed anchor at an edge midpoint
# ----------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("edge_um", EDGES)
def test_edge_value_is_the_mean_of_the_two_regions(edge_um: float) -> None:
    """At λ = λ_edge the blended coefficient is the two regions' mean.

    Hand derivation: the ramp is centred on the edge, so u(λ_edge) = 0.5
    and S(0.5) = 0.5²·(3 − 2·0.5) = 0.25 · 2 = 0.5 exactly. Hence
    c(λ_edge) = c_lo + (c_hi − c_lo)·0.5 = (c_lo + c_hi)/2.

    Worked example at the 0.70 µm edge: k_h2o = (0.0025 + 0.1245)/2
    = 0.0635 per cm^b; floor_od = (0.1597 + 0.0517)/2 = 0.1057 (both
    rows shipped at 0.0000 until the CU-335 re-fit); b_h2o
    = (0.874 + 0.434)/2 = 0.654.
    """
    lo_region, hi_region = _region_pair(edge_um)
    got = _coeffs(np.array([edge_um]))
    wants = (
        0.5 * (lo_region.floor_od + hi_region.floor_od),
        0.5 * (lo_region.k_h2o + hi_region.k_h2o),
        0.5 * (lo_region.b_h2o + hi_region.b_h2o),
    )
    for name, values, want in zip(_COEFF_NAMES, got, wants, strict=True):
        assert float(values[0]) == pytest.approx(want, rel=1e-14, abs=1e-15), (
            f"{name} at the {edge_um} µm edge is not the mean of the two regions"
        )


@pytest.mark.level0
def test_edge_midpoint_hand_value_at_0p70_um() -> None:
    """The 0.70 µm anchor written out longhand (no table lookup).

    ``floor_od`` here was 0.0 until CU-335 (2026-08-30): both the
    0.45–0.70 and 0.70–1.30 µm rows shipped at the zero clamp, because
    CU-161 calibrated them against a Rayleigh optical depth ~8× too
    large.  The re-fit lifts them to 0.1597 and 0.0517, so the edge now
    carries their mean, 0.1057.
    """
    floor, k, b = _coeffs(np.array([0.70]))
    assert float(floor[0]) == pytest.approx(0.1057, rel=1e-14, abs=1e-15)
    assert float(k[0]) == pytest.approx(0.0635, rel=1e-14)
    assert float(b[0]) == pytest.approx(0.654, rel=1e-14)


@pytest.mark.level0
def test_ramp_ends_reach_the_region_values_exactly() -> None:
    """S(0) = 0 and S(1) = 1: the ramp ends land on the table values."""
    for edge_um in EDGES:
        lo_region, hi_region = _region_pair(edge_um)
        floor_lo, k_lo, b_lo = _coeffs(np.array([edge_um - HW]))
        floor_hi, k_hi, b_hi = _coeffs(np.array([edge_um + HW]))
        assert float(k_lo[0]) == lo_region.k_h2o
        assert float(floor_lo[0]) == lo_region.floor_od
        assert float(b_lo[0]) == lo_region.b_h2o
        assert float(k_hi[0]) == hi_region.k_h2o
        assert float(floor_hi[0]) == hi_region.floor_od
        assert float(b_hi[0]) == hi_region.b_h2o


@pytest.mark.level0
def test_blend_is_monotone_between_the_two_region_values() -> None:
    """Inside a ramp every coefficient stays between its two endpoints.

    The smoothstep has no overshoot, so the blend can never invent an
    optical depth outside the calibrated bracket.
    """
    for edge_um in EDGES:
        lo_region, hi_region = _region_pair(edge_um)
        lam = np.linspace(edge_um - HW, edge_um + HW, 101)
        for values, lo_val, hi_val in zip(
            _coeffs(lam),
            (lo_region.floor_od, lo_region.k_h2o, lo_region.b_h2o),
            (hi_region.floor_od, hi_region.k_h2o, hi_region.b_h2o),
            strict=True,
        ):
            low, high = min(lo_val, hi_val), max(lo_val, hi_val)
            assert np.all(values >= low - 1e-15)
            assert np.all(values <= high + 1e-15)
