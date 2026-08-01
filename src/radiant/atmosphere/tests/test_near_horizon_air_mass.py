"""Level-0 tests for the near-horizon per-species air mass (CU-224 / ex-CU-275).

The analytic anchors for the underlying spherical slant integral live in
``test_grazing_column.py``; what is pinned here is the *air-mass* layer built on
it — that it reduces to the plane-parallel primitive where that primitive is
valid, that it diverges from it where the plane-parallel description expires,
and that the divergence is species dependent (which is why one scalar cannot
serve).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.atmosphere.near_horizon_air_mass import (
    SpeciesAirMass,
    apply_species_air_mass,
    is_near_horizon,
    near_horizon_species_air_mass,
    tangent_radius_m,
)
from radiant.atmosphere.protocol import SPHERICAL_SWITCH_RAD, AtmosphericGeometry
from radiant.atmosphere.simple import H_AER_M, H_H2O_M, H_MOL_M, SimpleAtmosphere
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

_H_TOP_M = 100_000.0


def _masses(zenith_deg: float, h_low_m: float = 0.0, h_high_m: float = _H_TOP_M) -> SpeciesAirMass:
    zeta = math.radians(zenith_deg)
    col = SimpleAtmosphere._column_length_km
    return near_horizon_species_air_mass(
        tangent_radius_m(h_low_m, zeta),
        h_low_m,
        h_high_m,
        col_mol_km=col(h_low_m, h_high_m, H_MOL_M),
        col_aer_km=col(h_low_m, h_high_m, H_AER_M),
        col_h2o_km=col(h_low_m, h_high_m, H_H2O_M),
        scale_height_mol_m=H_MOL_M,
        scale_height_aer_m=H_AER_M,
        scale_height_h2o_m=H_H2O_M,
    )


def _plane_parallel(zenith_deg: float, h_low_m: float = 0.0) -> float:
    return AtmosphericGeometry(
        sensor_altitude_m=_H_TOP_M,
        target_altitude_m=h_low_m,
        path_zenith_rad=math.radians(zenith_deg),
    ).air_mass()


# ---------------------------------------------------------------------------
# Reduction to the plane-parallel primitive
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("zenith_deg", [0.0, 30.0, 60.0, 75.0])
def test_reduces_to_the_plane_parallel_air_mass_inside_the_flat_band(zenith_deg: float) -> None:
    """Cross-model check: where ``sec ζ`` is valid, every species agrees with it.

    Model A: exact spherical slant column / vertical column, per species.
    Model B: ``AtmosphericGeometry.air_mass()`` — one plane-parallel scalar.
    Tolerance: 2 % at 75°, the loosest point inside the band; the measured
    disagreements are 0.000 % at 0°, 0.042 % at 30°, 0.373 % at 60° and 1.687 %
    at 75° for the molecular profile.
    """
    m = _masses(zenith_deg)
    pp = _plane_parallel(zenith_deg)
    for value in (m.m_mol, m.m_aer, m.m_h2o):
        assert value == pytest.approx(pp, rel=0.02)


@pytest.mark.level0
def test_vertical_path_has_unit_air_mass_for_every_species() -> None:
    """ζ = 0: the slant column *is* the vertical column, exactly."""
    m = _masses(0.0)
    for value in (m.m_mol, m.m_aer, m.m_h2o):
        assert value == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# Divergence near the horizon — the reason this module exists
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize(
    "zenith_deg,expected_overstatement",
    [(80.0, 0.03752), (85.0, 0.1315), (89.4, 2.365)],
)
def test_sec_zeta_overstates_the_molecular_air_mass_by_the_measured_amount(
    zenith_deg: float, expected_overstatement: float
) -> None:
    """``sec ζ`` is high by 3.8 % at 80°, 13 % at 85° and 237 % at 89.4°.

    These are the CU-275 numbers, re-measured; they are the quantitative
    statement of why the hand-over exists and of how big the error was before it.
    """
    m = _masses(zenith_deg)
    overstatement = _plane_parallel(zenith_deg) / m.m_mol - 1.0
    assert overstatement == pytest.approx(expected_overstatement, rel=0.02)


@pytest.mark.level0
def test_the_divergence_is_species_dependent() -> None:
    """Water vapour and molecular air diverge from ``sec ζ`` by ~2.3× at 89.4°.

    A shallow (2 km) profile hugs the tangent point far harder than a deep
    (8 km) one, so a single scalar effective air mass cannot serve both — the
    finding that forced the per-species form rather than one corrected scalar.
    """
    m = _masses(89.4)
    pp = _plane_parallel(89.4)
    err_mol = pp / m.m_mol - 1.0
    err_h2o = pp / m.m_h2o - 1.0
    assert err_mol / err_h2o == pytest.approx(2.27, rel=0.05)


@pytest.mark.level0
@pytest.mark.parametrize("zenith_deg", [80.0, 85.0, 89.4])
def test_the_spherical_air_mass_is_always_the_smaller_one(zenith_deg: float) -> None:
    """The correction removes air; it never adds any.

    Direction matters for the SNR story: the plane-parallel form was
    *pessimistic* near the horizon (too much air ⇒ too little signal), so the
    fix moves transmittance and SNR **up**, never down.
    """
    m = _masses(zenith_deg)
    pp = _plane_parallel(zenith_deg)
    assert m.m_mol < pp
    assert m.m_aer < pp
    assert m.m_h2o < pp


# ---------------------------------------------------------------------------
# The hand-over predicate and the weighted sum
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_hand_over_predicate_is_the_eighty_degree_switch() -> None:
    assert not is_near_horizon(SPHERICAL_SWITCH_RAD)
    assert not is_near_horizon(math.radians(79.999))
    assert is_near_horizon(math.radians(80.001))
    assert is_near_horizon(math.radians(89.5))


@pytest.mark.level0
def test_tangent_radius_is_r_sin_zeta() -> None:
    assert tangent_radius_m(0.0, math.pi / 2.0) == pytest.approx(R_EARTH_M, rel=1e-15)
    assert tangent_radius_m(10_000.0, 0.0) == pytest.approx(0.0, abs=1e-9)
    assert tangent_radius_m(10_000.0, math.radians(60.0)) == pytest.approx(
        (R_EARTH_M + 10_000.0) * math.sin(math.radians(60.0)), rel=1e-15
    )


@pytest.mark.level0
def test_the_gas_floor_rides_on_the_molecular_air_mass() -> None:
    """CU-161 defines the well-mixed-gas floor as a fraction of the molecular
    column, so it must carry the molecular curvature, not its own."""
    masses = SpeciesAirMass(
        m_mol=2.0,
        m_aer=3.0,
        m_h2o=5.0,
        r_tangent_m=R_EARTH_M,
        slant_column_mol_km=0.0,
        slant_column_aer_km=0.0,
        slant_column_h2o_km=0.0,
    )
    ones = np.ones(4)
    od = apply_species_air_mass(
        masses,
        od_vert_mol=ones,
        od_vert_aer=np.zeros(4),
        od_vert_h2o=np.zeros(4),
        od_vert_gas=ones,
    )
    np.testing.assert_allclose(od, np.full(4, 4.0), rtol=0.0, atol=0.0)


@pytest.mark.level0
def test_a_zero_length_column_gives_unit_air_masses() -> None:
    """Δh = 0: no species contributes optical depth, so the factor is 1 by
    convention rather than 0/0."""
    m = _masses(85.0, h_low_m=5_000.0, h_high_m=5_000.0)
    assert (m.m_mol, m.m_aer, m.m_h2o) == (1.0, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_rejects_a_non_finite_tangent_radius(bad: float) -> None:
    with pytest.raises(ParameterBoundsError, match="not finite"):
        near_horizon_species_air_mass(
            bad,
            0.0,
            _H_TOP_M,
            col_mol_km=1.0,
            col_aer_km=1.0,
            col_h2o_km=1.0,
            scale_height_mol_m=H_MOL_M,
            scale_height_aer_m=H_AER_M,
            scale_height_h2o_m=H_H2O_M,
        )


@pytest.mark.level0
def test_rejects_a_perigee_above_the_near_end() -> None:
    """A ray whose perigee sits above the arc's near end never reaches it."""
    with pytest.raises(ParameterBoundsError, match="exceeds the near-end radius"):
        near_horizon_species_air_mass(
            R_EARTH_M + 20_000.0,
            0.0,
            _H_TOP_M,
            col_mol_km=1.0,
            col_aer_km=1.0,
            col_h2o_km=1.0,
            scale_height_mol_m=H_MOL_M,
            scale_height_aer_m=H_AER_M,
            scale_height_h2o_m=H_H2O_M,
        )


@pytest.mark.level0
def test_is_deterministic() -> None:
    a = _masses(85.0)
    b = _masses(85.0)
    assert (a.m_mol, a.m_aer, a.m_h2o) == (b.m_mol, b.m_aer, b.m_h2o)
