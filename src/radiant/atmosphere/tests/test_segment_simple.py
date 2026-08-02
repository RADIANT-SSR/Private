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
from radiant.atmosphere.segment_single_scatter import cos_scattering_angle
from radiant.atmosphere.segment_thermal import segment_thermal_emission
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import H_H2O_M, H_MOL_M, SimpleAtmosphere
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.solar import toa_solar_equivalent_radiance


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


# ---------------------------------------------------------------------------
# Species split at the lower endpoint (CU-260, adopted 2026-08-01)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_species_weights_are_taken_at_the_lower_endpoint() -> None:
    """The single-scatter species split is weighted at ``h_low``, not at the mean.

    Level 0: the ω₀ and P(Θ) weights are rebuilt here from the atmosphere's own
    per-species coefficients evaluated **at the segment's lower endpoint**, and
    the scattered radiance is reassembled from the documented closed form
    ``L = E_sun/(4π) · cos θ_s · ω₀ · P(Θ) · (1 − τ)``.  The evaluator must
    reproduce it exactly.

    Fails on the pre-CU-260 implementation, which weighted at
    ``0.5·(h_low + h_high)``: on this 0 → 60 km column the mean altitude is
    30 km, where the aerosol coefficient has underflowed to zero.
    """
    lam = _grid()
    atm = _atm()
    h_low, h_high = 0.0, 6.0e4
    theta_s = math.radians(30.0)
    spec = ColumnSegmentSpec(h_low_m=h_low, h_high_m=h_high, zeta_low_rad=0.0)
    q = evaluate_column_segment(atm, lam, spec, theta_s_rad=theta_s)

    _od, _am, lengths = column_segment_optical_depth(atm, lam, spec)
    tau = np.exp(-_od)
    col_mol = lengths["col_length_mol_km"]
    col_h2o = lengths["col_length_h2o_km"]
    sigma_mol = atm._rayleigh_extinction_km(lam, h_low)
    sigma_aer = atm._aerosol_extinction_km(lam, h_low)
    sigma_h2o = (atm._h2o_vertical_od(lam, col_h2o) / col_h2o) * math.exp(-h_low / H_H2O_M)
    sigma_gas = (atm._gas_floor_vertical_od(lam, col_mol) / col_mol) * math.exp(-h_low / H_MOL_M)
    omega0 = atm._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)
    cos_dn = cos_scattering_angle(0.0, theta_s, 0.0, "toward_lower")
    phase = atm._single_scatter_phase_function(cos_dn, sigma_mol, sigma_aer)
    expected_scatter = (
        toa_solar_equivalent_radiance(lam) * math.cos(theta_s) * omega0 * phase * (1.0 - tau) / 4.0
    )
    thermal = segment_thermal_emission(lam, tau, atm._downwelling_effective_temperature_K(h_low))
    np.testing.assert_allclose(q.L_toward_lower, thermal + expected_scatter, rtol=1e-12, atol=0.0)
    assert q.provenance["weight_altitude_m"] == pytest.approx(h_low, abs=0.0)


@pytest.mark.level0
def test_a_tall_ground_rooted_column_keeps_its_aerosol() -> None:
    """A 0 → 100 km column still scatters like a hazy atmosphere (CU-260).

    The defect this replaces: weighting at the 50 km arithmetic mean made every
    aerosol and water coefficient underflow, so ω₀ evaluated to exactly 1 (no
    absorption at all) and the phase function collapsed to the isotropic-Rayleigh
    forward value of 1.5 — the sky scattered as if ``visibility_km`` had never
    been set.  Weighted at the ground the Henyey-Greenstein forward peak survives.
    """
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e5, zeta_low_rad=0.0)
    q = evaluate_column_segment(atm, lam, spec, theta_s_rad=math.radians(30.0))
    sigma_mol = atm._rayleigh_extinction_km(lam, 0.0)
    sigma_aer = atm._aerosol_extinction_km(lam, 0.0)
    cos_dn = cos_scattering_angle(0.0, math.radians(30.0), 0.0, "toward_lower")
    phase = atm._single_scatter_phase_function(cos_dn, sigma_mol, sigma_aer)
    vis = lam < 0.7
    # Forward-peaked, i.e. well above the isotropic-Rayleigh 1.5 the collapsed
    # split produced.
    assert float(np.min(phase[vis])) > 3.0
    assert q.provenance["weight_altitude_m"] == 0.0


@pytest.mark.level0
def test_a_tall_column_keeps_its_forward_scattering_peak() -> None:
    """The aerosol forward peak survives on a tall ground-rooted column (CU-260).

    Isolates the *angular* half of the defect from the optical-depth half.  With
    ``ζ = 0`` the segment transmittance does not depend on the solar zenith, so

        L_scat(θ_s) / cos θ_s  ∝  P(cos Θ),   cos Θ_toward_lower = cos θ_s

    and the ratio between a forward geometry (θ_s = 0, cos Θ = 1) and an oblique
    one (θ_s = 60°, cos Θ = 0.5) is exactly ``P(1) / P(0.5)``.  For a pure
    Rayleigh scatterer that is ``1.5 / 0.9375 = 1.6``; with the ground aerosol
    alive (Henyey-Greenstein, g = 0.7) it is far larger.

    Under the arithmetic-mean split the 50 km weight altitude killed the aerosol
    outright, so this ratio collapsed onto the Rayleigh 1.6 whatever the user set
    ``visibility_km`` to.
    """
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=1.0e5, zeta_low_rad=0.0)
    dark = evaluate_column_segment(atm, lam, spec, theta_s_rad=None)
    fwd = evaluate_column_segment(atm, lam, spec, theta_s_rad=0.0)
    obl = evaluate_column_segment(atm, lam, spec, theta_s_rad=math.radians(60.0))
    vis = (lam > 0.45) & (lam < 0.7)
    scat_fwd = (fwd.L_toward_lower - dark.L_toward_lower)[vis] / 1.0
    scat_obl = (obl.L_toward_lower - dark.L_toward_lower)[vis] / math.cos(math.radians(60.0))
    ratio = float(np.median(scat_fwd / scat_obl))
    assert ratio > 3.0, f"phase ratio {ratio:.3f} is at the aerosol-free Rayleigh value"


# ---------------------------------------------------------------------------
# CU-320 — one linearisation reference column across all three evaluators
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_curve_of_growth_is_linearised_against_the_slant_column() -> None:
    """ω₀'s water and gas weights use the SLANT column, not the vertical one.

    The CU-161 water term is a curve of growth ``OD = k·w^b`` with ``b < 1`` in
    the saturated bands, so evaluating it at the vertical amount and at the
    traversed amount are different models — they differ by ``m_h2o^(b−1)`` in
    the effective weight and therefore in ω₀.  ``segment_grazing`` and
    ``level_whole_path`` have always used the slant column; ``segment_simple``
    used the vertical one until CU-320, which was the whole of the surviving
    80° hand-over step.

    Fails on the pre-CU-320 implementation: at ζ = 60° the air mass is ≈ 2, so
    the hand value below is built on twice the water the retired form used.
    """
    lam = _grid()
    atm = _atm()
    h_low, h_high = 0.0, 2.0e4
    zeta = math.radians(60.0)
    theta_s = math.radians(30.0)
    spec = ColumnSegmentSpec(h_low_m=h_low, h_high_m=h_high, zeta_low_rad=zeta)
    q = evaluate_column_segment(atm, lam, spec, theta_s_rad=theta_s)

    od, air_mass, lengths = column_segment_optical_depth(atm, lam, spec)
    tau = np.exp(-od)
    # Hand-built slant columns: one air mass serves every species inside 80°.
    s_mol = lengths["col_length_mol_km"] * air_mass
    s_h2o = lengths["col_length_h2o_km"] * air_mass
    assert lengths["slant_column_mol_km"] == pytest.approx(s_mol, rel=1e-12)
    assert lengths["slant_column_h2o_km"] == pytest.approx(s_h2o, rel=1e-12)
    assert air_mass > 1.9  # ζ = 60° really is ~2 air masses

    sigma_mol = atm._rayleigh_extinction_km(lam, h_low)
    sigma_aer = atm._aerosol_extinction_km(lam, h_low)
    sigma_h2o = (atm._h2o_vertical_od(lam, s_h2o) / s_h2o) * math.exp(-h_low / H_H2O_M)
    sigma_gas = (atm._gas_floor_vertical_od(lam, s_mol) / s_mol) * math.exp(-h_low / H_MOL_M)
    omega0 = atm._single_scattering_albedo(sigma_mol, sigma_aer, sigma_h2o, sigma_gas)
    cos_dn = cos_scattering_angle(zeta, theta_s, 0.0, "toward_lower")
    phase = atm._single_scatter_phase_function(cos_dn, sigma_mol, sigma_aer)
    expected_scatter = (
        toa_solar_equivalent_radiance(lam) * math.cos(theta_s) * omega0 * phase * (1.0 - tau) / 4.0
    )
    thermal = segment_thermal_emission(lam, tau, atm._downwelling_effective_temperature_K(h_low))
    np.testing.assert_allclose(q.L_toward_lower, thermal + expected_scatter, rtol=1e-12, atol=0.0)


@pytest.mark.level0
def test_vertical_column_is_untouched_by_the_slant_convention() -> None:
    """Zero drift at ζ = 0: air mass is exactly 1, so slant is the vertical column.

    This is what keeps the P4 K-ladder species-split anchors
    (``tests/integration/test_species_split_anchors.py``, every rung rendered at
    ζ = 0°) bit-identical across CU-320.
    """
    lam = _grid()
    atm = _atm()
    spec = ColumnSegmentSpec(h_low_m=0.0, h_high_m=2.0e4, zeta_low_rad=0.0)
    _od, air_mass, lengths = column_segment_optical_depth(atm, lam, spec)
    assert air_mass == pytest.approx(1.0, abs=0.0)
    for species in ("mol", "aer", "h2o"):
        assert lengths[f"slant_column_{species}_km"] == pytest.approx(
            lengths[f"col_length_{species}_km"], abs=0.0
        )


@pytest.mark.level0
def test_eighty_degree_handover_step_is_small_in_every_band() -> None:
    """The two evaluators agree at the hand-over to better than 1 % (CU-320).

    Band-mean grazing/column at ζ = 80°, ground to ``h_atm_top``, θ_s = 30°.
    Before CU-320 the step was 1.078 (VIS), 1.568 (NIR), 1.497 (SWIR), 1.024
    (MWIR) and 0.998 (LWIR) — a spectral artefact of two evaluators evaluating
    one sub-linear law at two different column amounts.  What is left is the
    plane-parallel air mass's own error where it is retired, and it is the same
    size in every band, which is the point.
    """
    from radiant.atmosphere.near_horizon_air_mass import tangent_radius_m
    from radiant.atmosphere.protocol import H_ATM_TOP_M
    from radiant.atmosphere.segment_grazing import evaluate_grazing_segment

    lam = np.concatenate([np.linspace(0.40, 2.60, 221), np.linspace(2.65, 14.20, 232)])
    atm = _atm()
    zeta = math.radians(80.0)
    theta_s = math.radians(30.0)
    col = evaluate_column_segment(
        atm,
        lam,
        ColumnSegmentSpec(h_low_m=0.0, h_high_m=H_ATM_TOP_M, zeta_low_rad=zeta),
        theta_s_rad=theta_s,
    )
    gra = evaluate_grazing_segment(
        atm,
        lam,
        r_tangent_m=tangent_radius_m(0.0, zeta),
        h_low_m=0.0,
        h_high_m=H_ATM_TOP_M,
        zeta_low_rad=zeta,
        theta_s_rad=theta_s,
    )

    def _band_mean(values: np.ndarray, lo: float, hi: float) -> float:
        mask = np.logical_and(lam >= lo, lam <= hi)
        return float(np.trapezoid(values[mask], lam[mask]) / (lam[mask][-1] - lam[mask][0]))

    bands = {
        "VIS": (0.45, 0.85),
        "NIR": (0.85, 1.40),
        "SWIR": (1.4, 2.5),
        "MWIR": (3.0, 5.0),
        "LWIR": (8.0, 13.0),
    }
    for name, (lo, hi) in bands.items():
        step = _band_mean(gra.L_toward_lower, lo, hi) / _band_mean(col.L_toward_lower, lo, hi)
        assert 0.99 < step < 1.01, f"{name} hand-over step {step:.4f} is outside 1 %"
