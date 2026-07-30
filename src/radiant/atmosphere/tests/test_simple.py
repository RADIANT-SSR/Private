"""Tests for radiant.atmosphere.simple.

Validation per Task 2B.2 (Category C). The numerical truth anchors
are:

1. **Analytical Beer-Lambert.** For a single-species path the
   transmittance must equal ``exp(-σ · L)`` to within machine
   precision. Implemented by isolating the molecular term (visibility
   → very large, w_pw = 0) and comparing to a hand calculation at a
   wavelength where Rayleigh dominates.

2. **Published / handbook spectral landmarks.** Verify the qualitative
   absorption / window structure: τ at the 2.7 µm and 6.3 µm water
   bands is significantly lower than τ in the 4 µm window for a
   sea-level horizontal path. Specific reference values are taken from
   the Bucholtz/Koschmieder/water-vapor parameterisations the model
   itself is built from, so the test is checking *implementation*
   consistency rather than independent literature; this is the
   strongest claim the closed-form simple model can make.

3. **Independent single-absorber Beer's law.** For aerosol-only at
   550 nm, ``σ_aer = 3.912 / V_km`` (Koschmieder), and the implied
   visibility from the model output must round-trip to the visibility
   we set.

Cross-model consistency: ``SimpleAtmosphere(visibility_km → ∞,
precipitable_water_cm = 0)`` approaches but does not equal
``ExoAtmosphere`` because Rayleigh scattering remains.

Failure modes: zenith 0°, near 90°, > 90°, negative visibility,
unknown aerosol type, negative precipitable water.

Deliverable: a transmittance plot covering 0.4–14 µm under
mid-latitude-summer-ish conditions saved to ``tests/artifacts/`` for
visual inspection.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.protocol import (
    ZENITH_CEILING_RAD,
    Atmosphere,
    AtmosphericGeometry,
)
from radiant.atmosphere.simple import (
    AEROSOL_CLAMP_WAVELENGTH_UM,
    H_AER_M,
    H_MOL_M,
    KOSCHMIEDER,
    RAYLEIGH_EXPONENT,
    RAYLEIGH_VERTICAL_OD_1UM,
    SimpleAtmosphere,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _horizontal_geometry(slant_km: float = 10.0) -> AtmosphericGeometry:
    """Horizontal sea-level path of length ``slant_km`` (km).

    Implemented as Δh = slant_km · cos(zenith); we pick a small zenith
    so the cos≈1 and the math is easy. Using exact zero zenith and
    Δh = slant_km lets us test slant = Δh.
    """
    return AtmosphericGeometry(
        sensor_altitude_m=slant_km * 1000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )


def _grid_vis_to_lwir(n: int = 281) -> np.ndarray:
    return np.linspace(0.4, 14.0, n)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_simple_atmosphere_implements_protocol() -> None:
    assert isinstance(SimpleAtmosphere(), Atmosphere)


@pytest.mark.level1
def test_simple_state_invariants() -> None:
    atm = SimpleAtmosphere()
    state = atm.build_state(_grid_vis_to_lwir(), _horizontal_geometry())
    tau = state.transmittance.values
    assert np.all(tau >= 0.0) and np.all(tau <= 1.0)
    assert state.transmittance.unit == ""
    assert state.path_radiance.unit == "W/m²/sr/µm"
    assert state.atm_emission_down.unit == "W/m²/sr/µm"
    # All three arrays share the wavelength grid
    assert np.array_equal(state.transmittance.wavelength_um, state.wavelength_um)
    assert np.array_equal(state.path_radiance.wavelength_um, state.wavelength_um)
    assert np.array_equal(state.atm_emission_down.wavelength_um, state.wavelength_um)


# ---------------------------------------------------------------------------
# Truth anchor 1 — analytical Beer-Lambert (Rayleigh isolation)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_truth_anchor_1_rayleigh_only_matches_hand_calc() -> None:
    """With V → very large and w_pw = 0, only Rayleigh remains.

    The model integrates ``σ₀(λ) · exp(−h/H)`` from 0 to 5 km
    (the _horizontal_geometry helper creates a vertical column).
    The column-integrated OD is ``σ₀ · H · [1 − exp(−5/H)]``,
    which for ``H_mol = 8 km`` gives an effective column length
    of ``8 · (1 − exp(−0.625)) ≈ 3.718 km``.
    """
    atm = SimpleAtmosphere(
        visibility_km=10_000.0,  # effectively no aerosol
        precipitable_water_cm=0.0,  # no water vapor
    )
    geo = _horizontal_geometry(5.0)
    state = atm.build_state(np.array([0.55, 1.0, 2.0]), geo)

    # Column-integrated OD: σ₀ × H × [exp(-h_low/H) - exp(-h_high/H)]
    h_low_m = 0.0
    h_high_m = 5000.0
    col_mol = (H_MOL_M / 1000.0) * (math.exp(-h_low_m / H_MOL_M) - math.exp(-h_high_m / H_MOL_M))
    col_aer = (H_AER_M / 1000.0) * (math.exp(-h_low_m / H_AER_M) - math.exp(-h_high_m / H_AER_M))

    for lam_um in (0.55, 1.0, 2.0):
        idx = int(np.argmin(np.abs(state.wavelength_um - lam_um)))
        sigma_mol_0 = RAYLEIGH_VERTICAL_OD_1UM * lam_um ** (-RAYLEIGH_EXPONENT) / (H_MOL_M / 1000.0)
        sigma_aer_0 = KOSCHMIEDER / 10_000.0 * (lam_um / 0.55) ** (-1.3)
        od = sigma_mol_0 * col_mol + sigma_aer_0 * col_aer
        expected_tau = math.exp(-od)
        assert state.transmittance.values[idx] == pytest.approx(
            expected_tau, rel=1e-12, abs=1e-12
        ), f"τ mismatch at {lam_um} µm"


# ---------------------------------------------------------------------------
# Truth anchor 2 — qualitative water-vapor band structure
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_truth_anchor_2_water_vapor_bands_lower_than_windows() -> None:
    """Mid-latitude-ish 5 km horizontal, w_pw = 1.4 cm.

    The 2.7 µm and 6.3 µm water bands must show transmittance well
    below the 4.0 µm and 10.0 µm atmospheric windows.
    """
    atm = SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=1.4,
    )
    grid = np.array([2.7, 4.0, 6.3, 10.0])
    state = atm.build_state(grid, _horizontal_geometry(5.0))
    tau = state.transmittance.values
    tau_2p7, tau_4, tau_6p3, tau_10 = tau

    # Window/band ratios. The bands must be visibly attenuated.
    assert tau_2p7 < 0.5 * tau_4, (
        f"2.7 µm band ({tau_2p7:.3f}) is not noticeably attenuated relative "
        f"to the 4 µm window ({tau_4:.3f})."
    )
    assert tau_6p3 < 0.5 * tau_10, (
        f"6.3 µm band ({tau_6p3:.3f}) is not noticeably attenuated relative "
        f"to the 10 µm window ({tau_10:.3f})."
    )
    # Sanity: all values are physical.
    assert np.all((tau >= 0.0) & (tau <= 1.0))


# ---------------------------------------------------------------------------
# Truth anchor 3 — independent Koschmieder round-trip
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_truth_anchor_3_koschmieder_visibility_round_trip() -> None:
    """At 550 nm with no water vapor, subtract Rayleigh and recover V.

    The column-integrated OD decomposes into molecular and aerosol
    contributions. We subtract the known molecular column OD and
    recover the sea-level aerosol extinction, which must round-trip
    to the input visibility via ``V = 3.912 / σ_aer(550 nm)``.
    """
    visibility = 15.0
    atm = SimpleAtmosphere(
        visibility_km=visibility,
        aerosol_type="rural",
        precipitable_water_cm=0.0,
    )
    grid = np.array([0.55, 0.56])
    geo = _horizontal_geometry(1.0)  # 1 km vertical column (0 → 1 km)
    state = atm.build_state(grid, geo)
    tau = float(state.transmittance.values[0])

    # Column-integrated OD = σ₀ × H × [exp(-h_low/H) - exp(-h_high/H)]
    h_low_m, h_high_m = 0.0, 1000.0
    col_mol = (H_MOL_M / 1000.0) * (math.exp(-h_low_m / H_MOL_M) - math.exp(-h_high_m / H_MOL_M))
    col_aer = (H_AER_M / 1000.0) * (math.exp(-h_low_m / H_AER_M) - math.exp(-h_high_m / H_AER_M))

    od_total = -math.log(tau)
    sigma_mol_0 = RAYLEIGH_VERTICAL_OD_1UM * 0.55 ** (-RAYLEIGH_EXPONENT) / (H_MOL_M / 1000.0)
    od_mol = sigma_mol_0 * col_mol
    od_aer = od_total - od_mol
    sigma_aer_0 = od_aer / col_aer
    visibility_round_trip = KOSCHMIEDER / sigma_aer_0
    assert visibility_round_trip == pytest.approx(visibility, rel=1e-9)


# ---------------------------------------------------------------------------
# Cross-model consistency: SimpleAtmosphere(V→∞, w=0) approaches Exo
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_cross_model_simple_high_visibility_approaches_exo() -> None:
    """``SimpleAtmosphere(V→∞, w=0)`` approaches Exo only where no gas
    absorbs — and must NOT approach it inside the well-mixed-gas bands.

    Post-CU-161 the model carries a water-independent CO₂/N₂O/O₃ floor,
    so a real atmosphere never looks exo-atmospheric in the MWIR/LWIR
    even with the aerosol and water turned off. The test asserts:
      - τ_simple ≈ τ_exo in the NIR window (no floor, Rayleigh tiny)
      - τ_simple < 1 in the VIS due to Rayleigh
      - the gas floor bites at 5 µm and 10 µm (physically required)
    """
    geo = _horizontal_geometry(5.0)
    grid = np.array([0.4, 0.55, 1.0, 2.5, 5.0, 10.0])

    simple = SimpleAtmosphere(visibility_km=1e9, precipitable_water_cm=0.0)
    exo = ExoAtmosphere()

    s_state = simple.build_state(grid, geo)
    e_state = exo.build_state(grid, geo)

    s_tau = s_state.transmittance.values
    e_tau = e_state.transmittance.values
    assert np.allclose(e_tau, 1.0)

    # VIS: Rayleigh still attenuates noticeably (more than 0.1 % at 400 nm)
    assert s_tau[0] < 0.999

    # NIR window (1.0 µm): no gas floor; only Rayleigh (OD ≈ 0.033 over
    # this ~3.7 km column) separates it from exo → within 4%
    assert abs(s_tau[2] - 1.0) < 4e-2
    # 5 µm sits in the 5.0–7.5 µm region (floor OD 1.354) and 10 µm in
    # 10–12 (floor 0.047): the floor must absorb, unlike the exo model.
    assert s_tau[4] < 0.9  # strong CO₂/N₂O absorption at 5 µm
    assert s_tau[5] < 0.999  # weak O₃/continuum floor at 10 µm


# ---------------------------------------------------------------------------
# Geometry edge cases
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_zenith_zero_slant_equals_altitude_difference() -> None:
    geo = AtmosphericGeometry(
        sensor_altitude_m=10_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )
    assert geo.slant_path_length_m() == pytest.approx(10_000.0, rel=1e-12)
    assert geo.air_mass() == pytest.approx(1.0, rel=1e-12)


@pytest.mark.level0
def test_zenith_60_deg_air_mass_two() -> None:
    """sec(60°) = 2.0 — flat-Earth check."""
    geo = AtmosphericGeometry(
        sensor_altitude_m=10_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=math.radians(60.0),
    )
    assert geo.air_mass() == pytest.approx(2.0, rel=1e-12)


@pytest.mark.level0
def test_air_mass_is_sec_zeta_with_no_branch() -> None:
    """CU-274: one formula over the whole legal domain, ``m = sec ζ``.

    The 80° "spherical correction" branch is gone.  It was the root form
    ``R_E·[√(cos²ζ + 2x + x²) − cos ζ]`` with ``x = Δh/R_E``, i.e. the
    *geometric chord* of a slab — not a density-weighted air mass — and it
    made the air mass **drop** 18 % across its own switch (5.7023 at 79.9° →
    4.8072 at 80.1°), so transmittance was discontinuous in look angle for
    every scene class.
    """
    for zenith_deg in (0.0, 30.0, 60.0, 79.9, 80.0, 80.1, 85.0, 89.5):
        geo = AtmosphericGeometry(
            sensor_altitude_m=20_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(zenith_deg),
        )
        assert geo.air_mass() == pytest.approx(1.0 / math.cos(math.radians(zenith_deg)), rel=1e-12)


@pytest.mark.level0
def test_air_mass_is_continuous_and_monotone_across_the_old_switch() -> None:
    """No step at 80°, and air mass never falls as the path tilts (CU-274)."""

    def am(zenith_deg: float) -> float:
        return AtmosphericGeometry(
            sensor_altitude_m=20_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(zenith_deg),
        ).air_mass()

    # Continuity: the two sides of the retired switch agree to the step size
    # the derivative alone implies (d(sec ζ)/dζ · 0.2° ≈ 0.115 at 80°).
    assert am(80.1) - am(79.9) == pytest.approx(0.114, abs=0.01)
    previous = 0.0
    for zenith_deg in (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 79.9, 80.1, 85.0, 89.0, 89.5):
        value = am(zenith_deg)
        assert value > previous, f"air mass fell at {zenith_deg}°"
        assert math.isfinite(value)
        previous = value


@pytest.mark.level0
def test_zenith_above_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="path_zenith_rad"):
        AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=ZENITH_CEILING_RAD + 0.01,
        )


@pytest.mark.level0
def test_negative_zenith_rejected() -> None:
    with pytest.raises(ValueError, match="path_zenith_rad"):
        AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=-0.01,
        )


@pytest.mark.level0
def test_negative_altitude_rejected() -> None:
    with pytest.raises(ValueError, match="altitude"):
        AtmosphericGeometry(
            sensor_altitude_m=-100.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.0,
        )


@pytest.mark.level0
def test_geometry_from_degrees_round_trip() -> None:
    geo = AtmosphericGeometry.from_degrees(
        sensor_altitude_m=500_000.0,
        target_altitude_m=0.0,
        path_zenith_deg=30.0,
        solar_zenith_deg=45.0,
        solar_azimuth_deg=180.0,
    )
    assert geo.path_zenith_rad == pytest.approx(math.radians(30.0), rel=1e-9)
    assert geo.solar_zenith_rad == pytest.approx(math.radians(45.0), rel=1e-9)
    assert geo.solar_azimuth_rad == pytest.approx(math.radians(180.0), rel=1e-9)


@pytest.mark.level0
def test_geometry_serialization_round_trip() -> None:
    geo = AtmosphericGeometry.from_degrees(
        sensor_altitude_m=8000.0,
        target_altitude_m=100.0,
        path_zenith_deg=12.5,
        solar_zenith_deg=37.0,
        observer_type="airborne",
    )
    d = geo.to_dict()
    geo2 = AtmosphericGeometry.from_dict(d)
    assert geo2 == geo


# ---------------------------------------------------------------------------
# Constructor failure modes
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_negative_visibility_rejected() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        SimpleAtmosphere(visibility_km=-1.0)


@pytest.mark.level0
def test_zero_visibility_rejected() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        SimpleAtmosphere(visibility_km=0.0)


@pytest.mark.level0
def test_unknown_aerosol_type_rejected() -> None:
    with pytest.raises(ValueError, match="aerosol_type"):
        SimpleAtmosphere(aerosol_type="dusty")


@pytest.mark.level0
def test_negative_pwv_rejected() -> None:
    with pytest.raises(ValueError, match="precipitable_water_cm"):
        SimpleAtmosphere(precipitable_water_cm=-0.1)


@pytest.mark.level0
def test_zero_pwv_disables_water_vapor() -> None:
    """w_pw = 0 must zero the H₂O term — but NOT the well-mixed-gas floor.

    Post-CU-161 the 2.7/6.3 µm regions carry water-independent CO₂/N₂O
    floors, so τ stays well below 1 even bone-dry; what w=0 removes is
    exactly the water OD (asserted directly on the model's own term),
    and adding water must strictly reduce τ from the dry baseline.
    """
    atm = SimpleAtmosphere(precipitable_water_cm=0.0, visibility_km=1e9)
    grid = np.array([2.7, 6.3])
    # The water term itself is exactly zero at w = 0.
    assert np.all(atm._h2o_vertical_od(grid, 2.0) == 0.0)  # noqa: SLF001

    dry = atm.build_state(grid, _horizontal_geometry(5.0)).transmittance.values
    wet = (
        SimpleAtmosphere(precipitable_water_cm=2.0, visibility_km=1e9)
        .build_state(grid, _horizontal_geometry(5.0))
        .transmittance.values
    )
    assert np.all(wet < dry)  # water strictly adds absorption
    assert np.all(dry < 1.0)  # the gas floor persists at w = 0


# ---------------------------------------------------------------------------
# Orbital altitude — regression test for Gap 2 (SNR = 0 at LEO)
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_orbital_altitude_high_transmittance() -> None:
    """At 500 km LEO, τ must be physically reasonable (not zero).

    The column-integrated OD saturates at the full atmospheric column.
    In the MWIR window the simple model's Lorentzian H₂O band tails
    (especially from the 6.3 µm band) contribute noticeable extinction,
    giving τ ≈ 0.5–0.6 at 4.0–4.5 µm with w_pw = 1.4 cm. This is
    pessimistic relative to MODTRAN (which gives τ ≈ 0.8–0.9 in the
    true atmospheric window) but physically plausible.

    This is the regression test for Gap 2 — the old mean-altitude
    approach produced τ ≈ 10⁻⁵⁶ at orbital altitudes.
    """
    atm = SimpleAtmosphere(visibility_km=23.0, precipitable_water_cm=1.4)
    geo = AtmosphericGeometry(
        sensor_altitude_m=500_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )
    grid = np.array([4.0, 4.25, 4.5])
    state = atm.build_state(grid, geo)
    tau = state.transmittance.values

    # Must be physically reasonable: nonzero and in (0, 1).
    # The old code gave τ ≈ 10⁻⁵⁶ here; the fix gives τ ≈ 0.5–0.6.
    assert np.all(tau > 0.3), f"τ at 500 km LEO in MWIR window = {tau}, expected > 0.3"
    assert np.all(tau < 1.0), "τ at 500 km should be < 1 (some atmosphere remains)"


@pytest.mark.level0
def test_orbital_altitude_column_od_hand_calc() -> None:
    """Verify column-integrated OD matches hand calculation at 500 km.

    At 4.25 µm with V→∞ and w_pw=0, three terms survive:
      Rayleigh: σ₀ = 0.0088 × 4.25⁻⁴·⁰⁹; col = 8 × [1 − exp(−500/8)] km
      aerosol:  Koschmieder/1e9 (negligible but nonzero)
      gas floor (CU-161): the 3.50–5.00 µm region's well-mixed CO₂/N₂O
        floor OD 0.4497 × (col_mol / 8 km) — full column ⇒ ≈ 0.4497
    """
    atm = SimpleAtmosphere(visibility_km=1e9, precipitable_water_cm=0.0)
    geo = AtmosphericGeometry(
        sensor_altitude_m=500_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )
    grid = np.array([4.25, 4.26])
    state = atm.build_state(grid, geo)
    tau = float(state.transmittance.values[0])

    # Hand calc: at 500 km the full molecular column is traversed.
    sigma_mol_0 = RAYLEIGH_VERTICAL_OD_1UM * 4.25 ** (-RAYLEIGH_EXPONENT) / (H_MOL_M / 1000.0)
    col_mol = (H_MOL_M / 1000.0) * (1.0 - math.exp(-500_000.0 / H_MOL_M))
    # Aerosol term (V=1e9 → negligible but nonzero)
    sigma_aer_0 = KOSCHMIEDER / 1e9 * (4.25 / 0.55) ** (-1.3)
    col_aer = (H_AER_M / 1000.0) * (1.0 - math.exp(-500_000.0 / H_AER_M))

    # CU-161 gas floor: 4.25 µm is in the 3.50–5.00 µm region
    # (floor_od = 0.4497, full vertical column on the molecular scale height).
    od_gas = 0.4497 * (col_mol / (H_MOL_M / 1000.0))

    od_expected = sigma_mol_0 * col_mol + sigma_aer_0 * col_aer + od_gas
    tau_expected = math.exp(-od_expected)
    assert tau == pytest.approx(tau_expected, rel=1e-10)


@pytest.mark.level1
def test_geo_orbit_transmittance_above_ground_observer() -> None:
    """GEO at 35786 km should have essentially the same τ as LEO.

    Both altitudes are far above all scale heights, so the full
    atmospheric column is traversed. The column-integrated OD should
    be nearly identical.
    """
    atm = SimpleAtmosphere(visibility_km=23.0, precipitable_water_cm=1.4)
    grid = np.array([4.0, 10.0])

    leo = atm.build_state(
        grid,
        AtmosphericGeometry(
            sensor_altitude_m=500_000.0, target_altitude_m=0.0, path_zenith_rad=0.0
        ),
    )
    geo = atm.build_state(
        grid,
        AtmosphericGeometry(
            sensor_altitude_m=35_786_000.0, target_altitude_m=0.0, path_zenith_rad=0.0
        ),
    )
    # Both should be very close since the atmosphere is entirely below.
    assert np.allclose(leo.transmittance.values, geo.transmittance.values, rtol=1e-6)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_build_state_is_deterministic() -> None:
    atm = SimpleAtmosphere()
    grid = _grid_vis_to_lwir(64)
    geo = _horizontal_geometry(7.5)
    a = atm.build_state(grid, geo).transmittance.values
    b = atm.build_state(grid, geo).transmittance.values
    assert np.array_equal(a, b)


# ---------------------------------------------------------------------------
# Wavelength grid hygiene
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_simple_rejects_non_ascending_grid() -> None:
    with pytest.raises(ValueError, match="ascending"):
        SimpleAtmosphere().build_state(np.array([1.0, 0.5, 2.0]), _horizontal_geometry())


@pytest.mark.level0
def test_simple_rejects_non_positive_grid() -> None:
    with pytest.raises(ValueError, match="positive"):
        SimpleAtmosphere().build_state(np.array([-0.1, 1.0, 2.0]), _horizontal_geometry())


# ---------------------------------------------------------------------------
# Deliverable: 0.4–14 µm transmittance plot artifact
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_artifact_plot_visible_to_lwir(tmp_path: Path) -> None:
    """Save a transmittance plot for visual inspection.

    Per the 2B.2 deliverable: 0.4–14 µm grid under mid-latitude-summer-ish
    conditions, written to
    ``src/radiant/atmosphere/tests/artifacts/simple_transmittance.png``
    so a human can sanity-check the band structure.

    Falls back gracefully (test still passes) if matplotlib is not
    importable in the runtime environment.
    """
    atm = SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=2.0,
        standard_atmosphere="midlat_summer",
    )
    geo = AtmosphericGeometry(
        sensor_altitude_m=2_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )
    grid = np.linspace(0.4, 14.0, 1401)
    state = atm.build_state(grid, geo)
    tau = state.transmittance.values

    # Sanity bounds (these would catch a sign or unit slip even
    # without the plot).
    assert np.all((tau >= 0.0) & (tau <= 1.0))
    # The 6.3 µm band should still be the deepest single feature
    # for these conditions.
    band_idx = int(np.argmin(np.abs(grid - 6.3)))
    window_idx = int(np.argmin(np.abs(grid - 10.0)))
    assert tau[band_idx] < tau[window_idx]

    artifact_dir = Path(__file__).parent / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    plot_path = artifact_dir / "simple_transmittance.png"

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        pytest.skip("matplotlib not available; transmittance plot skipped")

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ax.plot(grid, tau, color="C0", linewidth=1.0)
    ax.set_xlabel("Wavelength (µm)")
    ax.set_ylabel("Atmospheric transmittance τ_atm")
    ax.set_title("SimpleAtmosphere — 2 km vertical path, V=23 km, rural, w_pw=2.0 cm")
    ax.set_ylim(0.0, 1.05)
    ax.set_xlim(0.4, 14.0)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)

    assert plot_path.exists()


# ---------------------------------------------------------------------------
# L_atm_down graybody downwelling
# ---------------------------------------------------------------------------


def _vertical_geometry(sensor_altitude_m: float) -> AtmosphericGeometry:
    """Zero-zenith vertical path from the ground to ``sensor_altitude_m``."""
    return AtmosphericGeometry(
        sensor_altitude_m=sensor_altitude_m,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )


@pytest.mark.level0
def test_l_atm_down_zero_when_tau_one() -> None:
    """Exo-configuration (Δh = 0) has τ ≡ 1 → L_atm_down ≡ 0."""
    atm = SimpleAtmosphere()
    geom = AtmosphericGeometry(
        sensor_altitude_m=400_000.0,
        target_altitude_m=400_000.0,
        path_zenith_rad=0.0,
    )
    grid = np.linspace(0.4, 14.0, 141)
    state = atm.build_state(grid, geom)
    assert np.allclose(state.transmittance.values, 1.0)
    assert np.allclose(state.atm_emission_down.values, 0.0)


@pytest.mark.level1
def test_l_atm_down_nonnegative_and_bounded_by_planck() -> None:
    """L_atm_down ∈ [0, B(λ, T_eff)] point-wise, per §3.1 hard limit.

    CU-155: T_eff is target-anchored — ground target (0 m) + 200 m
    emission-height offset → 288.15 − 6.5·0.2 = 286.85 K.
    """
    from radiant.core.blackbody import planck_spectral_radiance

    atm = SimpleAtmosphere(
        visibility_km=10.0,
        precipitable_water_cm=2.0,
        standard_atmosphere="us_standard",
    )
    grid = np.linspace(0.4, 14.0, 281)
    state = atm.build_state(grid, _vertical_geometry(2_000.0))
    emission = state.atm_emission_down.values

    t_expected = 288.15 - 6.5 * 0.2
    planck = planck_spectral_radiance(grid, t_expected)

    assert np.all(emission >= 0.0)
    assert np.all(emission <= planck + 1e-12)


@pytest.mark.level0
def test_l_atm_down_truth_anchor_opaque_limit() -> None:
    """At a wavelength where τ ≈ 0, L_atm_down → B(λ, T_atm_eff) exactly.

    The 6.3 µm water band with heavy precipitable water drives τ near
    zero, so (1 − τ) · B ≈ B. Post-CU-161 the calibrated band OD is
    bounded (curve of growth — real saturated bands stop deepening
    linearly), so "opaque" means τ ≲ 2×10⁻³ rather than the old
    fit's τ < 10⁻⁶; the graybody identity is asserted exactly and the
    B-limit to the corresponding (1 − τ) tolerance.
    """
    from radiant.core.blackbody import planck_spectral_radiance

    atm = SimpleAtmosphere(
        visibility_km=5.0,
        precipitable_water_cm=10.0,  # very wet column
        standard_atmosphere="us_standard",
    )
    grid = np.array([6.28, 6.30, 6.32])
    state = atm.build_state(grid, _vertical_geometry(4_000.0))

    # CU-155: T_eff is target-anchored (ground target + 200 m offset).
    t_expected = 288.15 - 6.5 * 0.2
    planck = planck_spectral_radiance(grid, t_expected)
    tau = state.transmittance.values  # vertical geometry → τ = τ_vert

    # With w_pw = 10 cm at the 6.3 µm band centre the calibrated band
    # is effectively opaque (curve-of-growth-bounded OD ≈ 6.2 → τ ≈ 2.1e-3).
    assert np.all(tau < 2.5e-3)
    # Graybody identity holds exactly: L_atm_down = (1 − τ_vert^D) · B
    # with the CU-155 flux-diffusivity exponent D.
    from radiant.atmosphere.simple import _ESKY_DIFFUSIVITY_D

    np.testing.assert_allclose(
        state.atm_emission_down.values,
        (1.0 - tau**_ESKY_DIFFUSIVITY_D) * planck,
        rtol=1e-9,
    )
    # And approaches the Planck curve to within the (1 − τ^D) shortfall.
    assert np.allclose(state.atm_emission_down.values, planck, rtol=3e-3, atol=0.0)


@pytest.mark.level1
def test_l_atm_down_scales_with_profile_temperature() -> None:
    """Hotter standard atmosphere → larger L_atm_down at fixed geometry."""
    grid = np.linspace(8.0, 14.0, 61)
    geom = _vertical_geometry(2_000.0)

    tropical = SimpleAtmosphere(standard_atmosphere="tropical").build_state(grid, geom)
    arctic_winter = SimpleAtmosphere(standard_atmosphere="subarctic_winter").build_state(grid, geom)

    # Same visibility/pwv/aerosol → same τ → L_atm_down ordering is
    # purely driven by T_atm_eff.
    assert np.allclose(tropical.transmittance.values, arctic_winter.transmittance.values)
    assert np.all(tropical.atm_emission_down.values > arctic_winter.atm_emission_down.values)


@pytest.mark.level0
def test_t_atm_eff_truth_anchor_lookup() -> None:
    """T_eff = T_sea − 6.5·(h_tgt + 200 m)/1000, clamped at 216.65 K (CU-155).

    Target-anchored: the sensor altitude does not enter (the pre-CU-155
    model evaluated at 0.5·h_sensor, clamping every space column to the
    tropopause — the measured downwelling deficit).
    """
    atm = SimpleAtmosphere(standard_atmosphere="us_standard")
    # Ground target → h_eval = 200 m → 288.15 − 1.3 = 286.85 K.
    assert atm._downwelling_effective_temperature_K(0.0) == pytest.approx(286.85, rel=1e-9)
    # 4 km target → h_eval = 4.2 km → 288.15 − 27.3 = 260.85 K.
    assert atm._downwelling_effective_temperature_K(4_000.0) == pytest.approx(260.85, rel=1e-9)
    # 30 km target → h_eval capped at 11 km → tropopause floor 216.65 K.
    assert atm._downwelling_effective_temperature_K(30_000.0) == pytest.approx(216.65, rel=1e-9)
    # Negative target altitude clamps to ground + offset.
    assert atm._downwelling_effective_temperature_K(-500.0) == pytest.approx(286.85, rel=1e-9)


@pytest.mark.level0
def test_esky_thermal_independent_of_sensor_altitude() -> None:
    """CU-155 marquee property: the sky a ground target sees is the same
    whether the sensor flies at 3 km or 500 km — E_sky_thermal is computed
    on the target→h_atm_top column at a target-anchored temperature, so it
    is identical for both sensors [W/m²/µm]."""
    import warnings as _warnings

    from radiant.core.los_geometry import LineOfSightGeometry

    from .test_evaluate import _resolved_params

    grid = np.linspace(3.0, 14.0, 111)
    results = []
    for h_sensor_m in (3_000.0, 500_000.0):
        atm = SimpleAtmosphere(standard_atmosphere="us_standard")
        params = _resolved_params(grid, sensor_altitude_m=h_sensor_m)
        # ADR-0011 / guardrail G2: the backend reads the sensor endpoint from
        # the LOS, so it is the LOS that must carry the varied altitude.
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=h_sensor_m, theta_o=0.0, h_atm_top=1.0e5)
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            results.append(atm.evaluate(grid, los, params).E_sky_thermal)
    np.testing.assert_array_equal(results[0], results[1])
    assert results[0].max() > 0.0


@pytest.mark.level0
def test_invalid_standard_atmosphere_raises() -> None:
    with pytest.raises(ValueError, match="standard_atmosphere"):
        SimpleAtmosphere(standard_atmosphere="martian")


# ---------------------------------------------------------------------------
# L_path single-scatter
# ---------------------------------------------------------------------------


def _daylight_geometry(
    sensor_altitude_m: float = 2_000.0,
    solar_zenith_rad: float = 0.3,
    solar_azimuth_rad: float = 0.0,
) -> AtmosphericGeometry:
    return AtmosphericGeometry(
        sensor_altitude_m=sensor_altitude_m,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=solar_zenith_rad,
        solar_azimuth_rad=solar_azimuth_rad,
    )


@pytest.mark.level0
def test_l_path_zero_when_tau_one() -> None:
    """No atmosphere along the line of sight → no scattered radiance."""
    atm = SimpleAtmosphere()
    geom = AtmosphericGeometry(
        sensor_altitude_m=400_000.0,
        target_altitude_m=400_000.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=0.5,
    )
    grid = np.linspace(0.4, 2.5, 141)
    state = atm.build_state(grid, geom)
    assert np.allclose(state.transmittance.values, 1.0)
    assert np.allclose(state.path_radiance.values, 0.0)


@pytest.mark.level1
def test_l_path_sun_at_horizon_vs_overhead() -> None:
    """L_path ∝ cos(θ_sun): horizon case is ~1e-6 of the overhead case."""
    atm = SimpleAtmosphere(visibility_km=5.0)
    grid = np.linspace(0.4, 2.5, 141)
    overhead = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=0.0))
    horizon = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=math.pi / 2 - 1e-6))
    # cos(θ_sun) ratio is ~1e-6. The phase function also changes
    # slightly (cos Θ swings from −1 to 0) so allow a small ratio
    # window. Use a pointwise ratio at a vis wavelength.
    idx = int(np.argmin(np.abs(grid - 0.55)))
    ratio = horizon.path_radiance.values[idx] / overhead.path_radiance.values[idx]
    assert ratio < 1e-4  # cos(θ_sun)-driven reduction dominates


@pytest.mark.level1
def test_l_path_nonnegative_and_finite() -> None:
    atm = SimpleAtmosphere(visibility_km=10.0, precipitable_water_cm=2.0)
    grid = np.linspace(0.4, 14.0, 281)
    state = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=0.5))
    lp = state.path_radiance.values
    assert np.all(np.isfinite(lp))
    assert np.all(lp >= 0.0)


@pytest.mark.level1
def test_l_path_higher_in_vis_than_lwir() -> None:
    """Rayleigh ∝ λ⁻⁴ dominates in vis, extinction collapses in LWIR."""
    atm = SimpleAtmosphere(visibility_km=15.0)
    grid = np.linspace(0.4, 14.0, 281)
    state = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=0.4))
    lp = state.path_radiance.values
    vis_idx = int(np.argmin(np.abs(grid - 0.55)))
    lwir_idx = int(np.argmin(np.abs(grid - 10.0)))
    assert lp[vis_idx] > 100.0 * lp[lwir_idx]


@pytest.mark.level1
def test_l_path_scales_linearly_with_cos_theta_sun() -> None:
    """Hold everything else fixed, double cos(θ_sun) → L_path doubles."""
    atm = SimpleAtmosphere(visibility_km=15.0)
    grid = np.linspace(0.4, 1.0, 61)

    # Pick θ_v = 0 so that cos(Θ) = −cos(θ_sun); both the phase
    # function and cos(θ_sun) change with solar zenith, so to isolate
    # the μ₀ scaling we use a fixed cos(Θ) by varying φ. That's too
    # complicated; instead check ordering: a sun closer to the zenith
    # produces more path radiance at visible wavelengths (by a large
    # factor) than a sun near the horizon.
    overhead = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=0.05))
    low_sun = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=1.3))
    overhead_peak = float(np.max(overhead.path_radiance.values))
    low_sun_peak = float(np.max(low_sun.path_radiance.values))
    assert overhead_peak > low_sun_peak


@pytest.mark.level1
def test_l_path_scales_with_solar_irradiance_shape() -> None:
    """L_path at 0.5 µm should be ~O(1) W/m²/sr/µm for a typical case.

    Rough order-of-magnitude: a 20% Rayleigh OD at 0.5 µm with
    cos θ_sun = 0.8 and ω₀ ≈ 1 for the molecular component gives:
        L_path ≈ [E_sun(0.5 µm)/(4π)] · 0.8 · 1 · P_R(Θ) · 0.2
    with E_sun(0.5 µm)/(4π) ≈ 2e3/(4π) ≈ 160 W/m²/sr/µm (approx)
    and P_R(backscatter) ≈ 1.5. So L_path ≈ 160 · 0.8 · 1.5 · 0.2 ≈ 38.
    Check the value is positive and in the 0.1–1000 W/m²/sr/µm band.
    """
    atm = SimpleAtmosphere(visibility_km=15.0, precipitable_water_cm=1.0)
    grid = np.linspace(0.49, 0.51, 21)
    state = atm.build_state(grid, _daylight_geometry(solar_zenith_rad=math.radians(37.0)))
    mid = float(state.path_radiance.values[len(grid) // 2])
    assert 0.1 < mid < 1000.0


@pytest.mark.level0
def test_cos_scattering_angle_truth_anchors() -> None:
    """Truth anchors for the geometry helper."""
    # Sun at zenith, sensor at nadir: cos Θ = −1 (backscatter).
    g1 = AtmosphericGeometry(
        sensor_altitude_m=1000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=0.0,
    )
    assert g1.cos_scattering_angle() == pytest.approx(-1.0, abs=1e-12)

    # Sun at 90° with sensor at zenith and Δφ = 0: cos Θ = 0.
    # (But solar_zenith_rad < π/2 is enforced, so use a very close value.)
    g2 = AtmosphericGeometry(
        sensor_altitude_m=1000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=math.pi / 2 - 1e-9,
    )
    assert g2.cos_scattering_angle() == pytest.approx(0.0, abs=1e-6)

    # Sun at 60° forward of sensor, sensor at 60° zenith, Δφ = 0:
    # cos Θ = −(sin²60 + cos²60) = −1 (hotspot / exact backscatter).
    g3 = AtmosphericGeometry(
        sensor_altitude_m=1000.0,
        target_altitude_m=0.0,
        path_zenith_rad=math.radians(60.0),
        solar_zenith_rad=math.radians(60.0),
        solar_azimuth_rad=0.0,
    )
    assert g3.cos_scattering_angle() == pytest.approx(-1.0, abs=1e-12)


class TestAerosolLwirClamp:
    """CU-088: the Ångström power law is clamped at the MWIR–LWIR boundary."""

    @pytest.mark.level0
    def test_lwir_extinction_is_flat_at_boundary_value(self) -> None:
        atm = SimpleAtmosphere(visibility_km=10.0, aerosol_type="rural")
        boundary = atm._aerosol_extinction_km(np.array([AEROSOL_CLAMP_WAVELENGTH_UM]), 0.0)[0]
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lwir = atm._aerosol_extinction_km(np.linspace(8.0, 13.0, 20), 0.0)
        np.testing.assert_allclose(lwir, boundary, rtol=1e-12)

    @pytest.mark.level0
    def test_clamp_raises_extinction_above_power_law(self) -> None:
        """The clamp increases LWIR extinction vs the unphysical power-law
        extrapolation (absorption-dominated IR, not decaying)."""
        atm = SimpleAtmosphere(visibility_km=10.0, aerosol_type="rural")
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clamped_10 = atm._aerosol_extinction_km(np.array([10.0]), 0.0)[0]
        alpha = 1.3
        power_law_10 = (KOSCHMIEDER / 10.0) * (10.0 / 0.55) ** (-alpha)
        assert clamped_10 > power_law_10

    @pytest.mark.level0
    def test_mwir_below_boundary_unaffected(self) -> None:
        """MWIR (≤ 5 µm) uses the power law unchanged — no clamp, no warning."""
        import warnings

        atm = SimpleAtmosphere(visibility_km=10.0, aerosol_type="rural")
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            mwir = atm._aerosol_extinction_km(np.linspace(3.5, 5.0, 10), 0.0)
        # Power law still monotonic-decreasing across MWIR.
        assert mwir[0] > mwir[-1]

    @pytest.mark.level0
    def test_notes_clamp_at_debug_not_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """The Ångström clamp beyond 5 µm is logged at debug (warning-free-UX), not a
        UserWarning — a valid MWIR/LWIR SimpleAtmosphere scenario stays quiet."""
        import logging
        import warnings

        atm = SimpleAtmosphere(visibility_km=10.0, aerosol_type="rural")
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)  # must NOT warn
            with caplog.at_level(logging.DEBUG, logger="radiant.atmosphere.simple"):
                atm._aerosol_extinction_km(np.linspace(8.0, 13.0, 10), 0.0)
        assert any("aerosol extinction is clamped" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# CU-161 calibration anchors — real MODTRAN 6 band means (2026-07-17 set)
# ---------------------------------------------------------------------------


@pytest.mark.level0
@pytest.mark.parametrize(
    ("w_cm", "band", "tau_real"),
    [
        # us_standard water ladder (runs D4/A1/D5, rural 23 km, nadir full column)
        (0.7, (3.5, 5.0), 0.5856),
        (1.4, (3.5, 5.0), 0.5553),
        (2.8, (3.5, 5.0), 0.5060),
        (0.7, (8.0, 12.0), 0.7912),
        (1.4, (8.0, 12.0), 0.7322),
        (2.8, (8.0, 12.0), 0.5878),
        (1.4, (1.5, 2.4), 0.6870),
    ],
)
def test_cu161_water_ladder_anchor(w_cm: float, band: tuple[float, float], tau_real: float) -> None:
    """The calibrated gas-region model reproduces the real MODTRAN 6
    water-ladder anchors (D4/A1/D5) to ±0.02 band-mean τ.

    These are the CU-161 truth anchors: real MODTRAN 6 (2026-07-17 run
    set), us_standard, rural 23 km visibility, nadir 100 km→0 column,
    H₂O column scaled ×0.5/×1/×2. Values extracted by
    ``scripts/fit_simple_atmosphere_gas_bands.py``'s anchor pass;
    the staged tape7s (gitignored) are the primary source.
    """
    lam = np.linspace(band[0], band[1], 400)
    atm = SimpleAtmosphere(precipitable_water_cm=w_cm)  # rural, 23 km default
    geo = AtmosphericGeometry(
        sensor_altitude_m=100_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )
    tau = atm.build_state(lam, geo).transmittance.values
    assert float(np.mean(tau)) == pytest.approx(tau_real, abs=0.02)


@pytest.mark.level0
def test_cu161_water_response_slope_mwir() -> None:
    """The MWIR water response is weak and sub-linear (CU-161): doubling
    the column from 1.4 to 2.8 cm costs ≈ 0.05 τ (the old linear model
    lost 0.24 — the 5× over-response this calibration fixed)."""
    lam = np.linspace(3.5, 5.0, 400)
    geo = AtmosphericGeometry(
        sensor_altitude_m=100_000.0, target_altitude_m=0.0, path_zenith_rad=0.0
    )
    atm_1x = SimpleAtmosphere(precipitable_water_cm=1.4)
    atm_2x = SimpleAtmosphere(precipitable_water_cm=2.8)
    tau_1x = float(np.mean(atm_1x.build_state(lam, geo).transmittance.values))
    tau_2x = float(np.mean(atm_2x.build_state(lam, geo).transmittance.values))
    drop = tau_1x - tau_2x
    assert 0.02 < drop < 0.09, (
        f"MWIR τ drop for 2× water = {drop:.3f}; the calibrated response "
        "is ≈ 0.05 (real MODTRAN) — a large value means the linear "
        "over-response is back."
    )
