"""Level-0/1 tests for the column path segment (``segment_simple.py``).

The analytic anchors live here; the real-MODTRAN truth anchors live in
``tests/integration/test_segment_modtran_anchors.py`` (they need the staged
run set).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.segment_simple import (
    DEFAULT_H_ATM_TOP_M,
    column_segment_optical_depth,
    evaluate_column_segment,
)
from radiant.atmosphere.segment_thermal import segment_thermal_emission
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError


def _grid() -> np.ndarray:
    return np.linspace(0.4, 14.0, 301)


def _atm() -> SimpleAtmosphere:
    return SimpleAtmosphere()


# ---------------------------------------------------------------------------
# Vacuum limits — exact, not approximate
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_segment_above_h_atm_top_is_exact_vacuum() -> None:
    """A segment entirely above the modelled column: τ = 1, L = 0 exactly."""
    lam = _grid()
    spec = ColumnSegmentSpec(h_low_m=1.2e5, h_high_m=4.0e5, zeta_low_rad=0.4)
    q = evaluate_column_segment(_atm(), lam, spec, theta_s_rad=0.5)
    np.testing.assert_array_equal(q.tau, np.ones_like(lam))
    np.testing.assert_array_equal(q.L_toward_upper, np.zeros_like(lam))
    np.testing.assert_array_equal(q.L_toward_lower, np.zeros_like(lam))


@pytest.mark.level0
def test_segment_exactly_at_h_atm_top_is_exact_vacuum() -> None:
    """The boundary itself is vacuum (h_low >= h_atm_top, closed)."""
    lam = _grid()
    spec = ColumnSegmentSpec(h_low_m=DEFAULT_H_ATM_TOP_M, h_high_m=2.0e5, zeta_low_rad=0.0)
    q = evaluate_column_segment(_atm(), lam, spec)
    np.testing.assert_array_equal(q.tau, np.ones_like(lam))


@pytest.mark.level0
def test_zero_thickness_segment_is_exact_vacuum() -> None:
    """h_high == h_low: every column length is 0, so τ = exp(0) = 1 exactly."""
    lam = _grid()
    spec = ColumnSegmentSpec(h_low_m=3.0e3, h_high_m=3.0e3, zeta_low_rad=0.7)
    q = evaluate_column_segment(_atm(), lam, spec, theta_s_rad=0.4, delta_phi_rad=0.9)
    np.testing.assert_array_equal(q.tau, np.ones_like(lam))
    np.testing.assert_array_equal(q.L_toward_upper, np.zeros_like(lam))
    np.testing.assert_array_equal(q.L_toward_lower, np.zeros_like(lam))


# ---------------------------------------------------------------------------
# Reciprocity / lower-endpoint keying
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_tau_is_one_function_keyed_to_the_lower_endpoint() -> None:
    """Transmittance is reciprocal: one τ per segment, never flipped.

    Reading the same physical column with either travel direction returns
    the *same array object contents* — there is no per-direction τ to get
    out of sync, and the spec refuses an inverted endpoint pair, so no
    caller can accidentally key the airmass to the upper endpoint.
    """
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=1.0e3, h_high_m=1.2e4, zeta_low_rad=math.radians(35.0))
    q = evaluate_column_segment(atm, lam, spec, theta_s_rad=0.6, delta_phi_rad=1.1)
    # Both directional products are attenuated by the same single τ.
    assert q.tau.shape == lam.shape
    # Re-evaluating with the endpoints swapped is refused, not silently
    # re-keyed to the other endpoint.
    with pytest.raises(ParameterBoundsError):
        ColumnSegmentSpec(h_low_m=1.2e4, h_high_m=1.0e3, zeta_low_rad=math.radians(35.0))
    # τ from the direct optical-depth helper matches the evaluated field.
    od, air_mass, _lengths = column_segment_optical_depth(atm, lam, spec)
    np.testing.assert_array_equal(q.tau, np.exp(-od))
    assert air_mass == pytest.approx(1.0 / math.cos(math.radians(35.0)), rel=1e-9)


@pytest.mark.level0
def test_vertical_segment_airmass_is_exactly_one() -> None:
    lam = _grid()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=0.0)
    _od, air_mass, _lengths = column_segment_optical_depth(_atm(), lam, spec)
    assert air_mass == 1.0


# ---------------------------------------------------------------------------
# Consistency with the existing (untouched) down-looking model
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize(
    ("h_high_m", "zeta_deg"),
    [
        (DEFAULT_H_ATM_TOP_M, 0.0),  # ground → h_atm_top, vertical
        (1.0e4, 0.0),  # ground → 10 km, vertical (partial column)
        (7.0e5, 0.0),  # ground → LEO, vertical
        (1.0e4, 40.0),  # ground → 10 km, slant
    ],
)
def test_segment_tau_is_bit_identical_to_existing_evaluate(
    h_high_m: float, zeta_deg: float
) -> None:
    """The segment reuses the *same functions*, so τ matches bit for bit.

    This is the zero-drift proof for the shared machinery: if a future edit
    to ``simple.py`` changed the column integral, this equality — exact
    ``==``, not ``approx`` — breaks immediately.
    """
    lam = _grid()
    atm = _atm()
    zeta = math.radians(zeta_deg)
    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=h_high_m,
        theta_o=zeta,
        h_atm_top=DEFAULT_H_ATM_TOP_M,
        theta_s=0.5,
        delta_phi=0.2,
    )
    existing = atm.evaluate(lam, los, params=None)  # type: ignore[arg-type]
    segment = evaluate_column_segment(
        atm, lam, ColumnSegmentSpec(h_low_m=0.0, h_high_m=h_high_m, zeta_low_rad=zeta)
    )
    np.testing.assert_array_equal(segment.tau, existing.tau_up)


# ---------------------------------------------------------------------------
# Monotonicity
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_tau_decreases_with_zenith() -> None:
    lam = _grid()
    atm = _atm()
    previous: np.ndarray | None = None
    for zeta_deg in (0.0, 30.0, 60.0, 80.0, 89.0):
        spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=math.radians(zeta_deg))
        tau = evaluate_column_segment(atm, lam, spec).tau
        if previous is not None:
            assert np.all(tau <= previous + 1e-15)
            assert np.any(tau < previous)
        previous = tau


@pytest.mark.level0
def test_tau_decreases_with_segment_thickness() -> None:
    lam = _grid()
    atm = _atm()
    previous: np.ndarray | None = None
    for h_high in (1.0e3, 3.0e3, 1.0e4, 3.0e4):
        tau = evaluate_column_segment(
            atm, lam, ColumnSegmentSpec(h_low_m=0.0, h_high_m=h_high, zeta_low_rad=0.0)
        ).tau
        if previous is not None:
            assert np.all(tau <= previous + 1e-15)
            assert np.any(tau < previous)
        previous = tau


@pytest.mark.level0
def test_tau_decreases_with_path_water() -> None:
    lam = _grid()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=0.0)
    previous: np.ndarray | None = None
    for pwv in (0.5, 1.4, 3.0, 5.0):
        tau = evaluate_column_segment(SimpleAtmosphere(precipitable_water_cm=pwv), lam, spec).tau
        if previous is not None:
            assert np.all(tau <= previous + 1e-15)
            assert np.any(tau < previous)
        previous = tau


# ---------------------------------------------------------------------------
# Thermal and scattered composition
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_pure_thermal_segment_is_kirchhoff_graybody() -> None:
    """With no sun, both directional products are exactly (1 − τ)·B(T_eff).

    Emissivity is derived from the segment's own transmittance (Rule 5);
    there is no independent emissivity input anywhere in this path.
    """
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=math.radians(20.0))
    q = evaluate_column_segment(atm, lam, spec, theta_s_rad=None)
    t_eff = atm._downwelling_effective_temperature_K(0.0)
    expected = (1.0 - q.tau) * planck_spectral_radiance(lam, t_eff)
    np.testing.assert_array_equal(q.L_toward_upper, expected)
    np.testing.assert_array_equal(q.L_toward_lower, expected)
    assert q.provenance["t_eff_K"] == pytest.approx(t_eff, abs=0.0)


@pytest.mark.level0
def test_opaque_limit_saturates_at_the_planck_curve() -> None:
    """τ → 0 gives L → B(λ, T_eff) — the blackbody ceiling (Kirchhoff)."""
    lam = np.linspace(8.0, 12.0, 40)
    t_eff = 285.0
    tau = np.zeros_like(lam)
    np.testing.assert_array_equal(
        segment_thermal_emission(lam, tau, t_eff), planck_spectral_radiance(lam, t_eff)
    )


@pytest.mark.level0
def test_sun_below_horizon_gives_exactly_zero_scattered_term() -> None:
    """Night: the two directional products collapse onto the thermal one."""
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=0.3)
    night = evaluate_column_segment(atm, lam, spec, theta_s_rad=math.pi / 2.0)
    thermal_only = evaluate_column_segment(atm, lam, spec, theta_s_rad=None)
    np.testing.assert_array_equal(night.L_toward_upper, thermal_only.L_toward_upper)
    np.testing.assert_array_equal(night.L_toward_lower, thermal_only.L_toward_lower)


@pytest.mark.level0
def test_directional_products_differ_under_illumination() -> None:
    """Forward scatter one way is back scatter the other — a real difference.

    The thermal parts are identical by construction, so any difference here
    is entirely the scattering-angle flip.
    """
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=2.0e4, zeta_low_rad=math.radians(50.0))
    q = evaluate_column_segment(atm, lam, spec, theta_s_rad=math.radians(35.0), delta_phi_rad=0.0)
    assert q.provenance["cos_scatter_toward_lower"] == pytest.approx(
        -q.provenance["cos_scatter_toward_upper"], rel=1e-12
    )
    vis = lam < 0.8
    assert not np.allclose(q.L_toward_upper[vis], q.L_toward_lower[vis], rtol=1e-3)


@pytest.mark.level0
def test_illumination_only_adds_radiance() -> None:
    """The scattered term is a source, never a sink (non-negativity, Rule 17)."""
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e4, zeta_low_rad=0.3)
    lit = evaluate_column_segment(atm, lam, spec, theta_s_rad=0.5, delta_phi_rad=0.7)
    dark = evaluate_column_segment(atm, lam, spec, theta_s_rad=None)
    assert np.all(lit.L_toward_upper >= dark.L_toward_upper - 1e-15)
    assert np.all(lit.L_toward_lower >= dark.L_toward_lower - 1e-15)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("bad_top", [0.0, -1.0, float("nan")])
def test_rejects_bad_h_atm_top(bad_top: float) -> None:
    with pytest.raises(ParameterBoundsError, match="positive-finite"):
        evaluate_column_segment(
            _atm(),
            _grid(),
            ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=0.0),
            h_atm_top_m=bad_top,
        )


@pytest.mark.level0
def test_rejects_descending_wavelength_grid() -> None:
    with pytest.raises(ParameterBoundsError, match="strictly ascending"):
        evaluate_column_segment(
            _atm(),
            np.linspace(14.0, 0.4, 50),
            ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e3, zeta_low_rad=0.0),
        )


@pytest.mark.level1
def test_evaluation_is_deterministic() -> None:
    """Same inputs → identical outputs (traceability requirement)."""
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=500.0, h_high_m=1.5e4, zeta_low_rad=0.8)
    a = evaluate_column_segment(atm, lam, spec, theta_s_rad=0.4, delta_phi_rad=0.3)
    b = evaluate_column_segment(atm, lam, spec, theta_s_rad=0.4, delta_phi_rad=0.3)
    np.testing.assert_array_equal(a.tau, b.tau)
    np.testing.assert_array_equal(a.L_toward_upper, b.L_toward_upper)
    np.testing.assert_array_equal(a.L_toward_lower, b.L_toward_lower)
