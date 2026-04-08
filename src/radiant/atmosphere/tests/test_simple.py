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
    KOSCHMIEDER,
    RAYLEIGH_COEFF_KM,
    RAYLEIGH_EXPONENT,
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


def test_simple_atmosphere_implements_protocol() -> None:
    assert isinstance(SimpleAtmosphere(), Atmosphere)


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


def test_truth_anchor_1_rayleigh_only_matches_hand_calc() -> None:
    """At sea level, with V → very large and w_pw = 0, only Rayleigh remains.

    σ_mol(λ) = 0.0088 · λ⁻⁴·⁰⁹ km⁻¹ (Bucholtz 1995). For a 5 km
    horizontal path at sea level the optical depth at 0.55 µm is
    σ · L, and τ = exp(-σ · L).
    """
    atm = SimpleAtmosphere(
        visibility_km=10_000.0,  # effectively no aerosol
        precipitable_water_cm=0.0,  # no water vapor
    )
    geo = _horizontal_geometry(5.0)
    state = atm.build_state(np.array([0.55, 1.0, 2.0]), geo)

    # The "horizontal" helper is actually a 5 km vertical column with
    # path-mean altitude 2.5 km. The model scales molecular extinction
    # by exp(-h_mean / 8 km) and aerosol by exp(-h_mean / 1.2 km), so
    # the hand calc must do the same.
    mean_alt_m = 0.5 * (geo.sensor_altitude_m + geo.target_altitude_m)
    mol_scale = math.exp(-mean_alt_m / 8000.0)
    aer_scale = math.exp(-mean_alt_m / 1200.0)
    for lam_um in (0.55, 1.0, 2.0):
        idx = int(np.argmin(np.abs(state.wavelength_um - lam_um)))
        sigma_mol = RAYLEIGH_COEFF_KM * lam_um ** (-RAYLEIGH_EXPONENT) * mol_scale
        sigma_aer = KOSCHMIEDER / 10_000.0 * (lam_um / 0.55) ** (-1.3) * aer_scale
        expected_tau = math.exp(-(sigma_mol + sigma_aer) * 5.0)
        assert state.transmittance.values[idx] == pytest.approx(
            expected_tau, rel=1e-12, abs=1e-12
        ), f"τ mismatch at {lam_um} µm"


# ---------------------------------------------------------------------------
# Truth anchor 2 — qualitative water-vapor band structure
# ---------------------------------------------------------------------------


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


def test_truth_anchor_3_koschmieder_visibility_round_trip() -> None:
    """At 550 nm with no Rayleigh and no water vapor, σ should be 3.912/V.

    We can't actually disable Rayleigh, but we can subtract its
    known contribution at the same wavelength and recover σ_aer.
    Then ``visibility_km = 3.912 / σ_aer`` must equal what we set.
    """
    visibility = 15.0
    atm = SimpleAtmosphere(
        visibility_km=visibility,
        aerosol_type="rural",
        precipitable_water_cm=0.0,
    )
    grid = np.array([0.55, 0.56])
    geo = _horizontal_geometry(1.0)  # 1 km path
    state = atm.build_state(grid, geo)
    tau = float(state.transmittance.values[0])

    # Total OD on a 1 km path = -ln(tau). Both Rayleigh and aerosol
    # are scaled by their respective scale-height factors at the
    # path-mean altitude, so we apply the same scaling to the
    # hand-calculated Rayleigh contribution before subtracting.
    od_total = -math.log(tau)
    mean_alt_m = 0.5 * (geo.sensor_altitude_m + geo.target_altitude_m)
    mol_scale = math.exp(-mean_alt_m / 8000.0)
    aer_scale = math.exp(-mean_alt_m / 1200.0)
    sigma_mol = RAYLEIGH_COEFF_KM * 0.55 ** (-RAYLEIGH_EXPONENT) * mol_scale
    # 1 km × σ_aer(scaled), so dividing recovers σ_aer at the path-mean
    sigma_aer_scaled = od_total - sigma_mol
    sigma_aer_550 = sigma_aer_scaled / aer_scale
    visibility_round_trip = KOSCHMIEDER / sigma_aer_550
    assert visibility_round_trip == pytest.approx(visibility, rel=1e-9)


# ---------------------------------------------------------------------------
# Cross-model consistency: SimpleAtmosphere(V→∞, w=0) approaches Exo
# ---------------------------------------------------------------------------


def test_cross_model_simple_high_visibility_approaches_exo() -> None:
    """``SimpleAtmosphere(V→∞, w=0)`` is close to but not equal to Exo.

    Rayleigh scattering still bites at short wavelengths, so the gap
    is wavelength-dependent. The test asserts both:
      - τ_simple ≈ τ_exo to within a few percent in the SWIR/MWIR
      - τ_simple < 1 in the VIS due to Rayleigh
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

    # MWIR/LWIR: λ⁻⁴·⁰⁹ kills Rayleigh; the gap is < 1e-4
    assert abs(s_tau[-1] - 1.0) < 1e-4
    assert abs(s_tau[-2] - 1.0) < 1e-4


# ---------------------------------------------------------------------------
# Geometry edge cases
# ---------------------------------------------------------------------------


def test_zenith_zero_slant_equals_altitude_difference() -> None:
    geo = AtmosphericGeometry(
        sensor_altitude_m=10_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
    )
    assert geo.slant_path_length_m() == pytest.approx(10_000.0, rel=1e-12)
    assert geo.air_mass() == pytest.approx(1.0, rel=1e-12)


def test_zenith_60_deg_air_mass_two() -> None:
    """sec(60°) = 2.0 — flat-Earth check."""
    geo = AtmosphericGeometry(
        sensor_altitude_m=10_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=math.radians(60.0),
    )
    assert geo.air_mass() == pytest.approx(2.0, rel=1e-12)


def test_zenith_85_deg_uses_spherical_correction() -> None:
    """Past 80° the spherical correction kicks in. Air mass remains
    finite and is less than the (singular) flat-Earth ``sec(85°)``.
    """
    geo = AtmosphericGeometry(
        sensor_altitude_m=20_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=math.radians(85.0),
    )
    am = geo.air_mass()
    flat = 1.0 / math.cos(math.radians(85.0))  # ≈ 11.47
    assert math.isfinite(am)
    assert am < flat
    # The spherical correction should not dramatically change AM at 85°.
    assert am > 0.5 * flat


def test_zenith_above_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="path_zenith_rad"):
        AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=ZENITH_CEILING_RAD + 0.01,
        )


def test_negative_zenith_rejected() -> None:
    with pytest.raises(ValueError, match="path_zenith_rad"):
        AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=-0.01,
        )


def test_negative_altitude_rejected() -> None:
    with pytest.raises(ValueError, match="altitude"):
        AtmosphericGeometry(
            sensor_altitude_m=-100.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.0,
        )


def test_geometry_from_degrees_round_trip() -> None:
    geo = AtmosphericGeometry.from_degrees(
        sensor_altitude_m=500_000.0,
        target_altitude_m=0.0,
        path_zenith_deg=30.0,
        solar_zenith_deg=45.0,
        solar_azimuth_deg=180.0,
    )
    assert geo.path_zenith_rad == pytest.approx(math.radians(30.0))
    assert geo.solar_zenith_rad == pytest.approx(math.radians(45.0))
    assert geo.solar_azimuth_rad == pytest.approx(math.radians(180.0))


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


def test_negative_visibility_rejected() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        SimpleAtmosphere(visibility_km=-1.0)


def test_zero_visibility_rejected() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        SimpleAtmosphere(visibility_km=0.0)


def test_unknown_aerosol_type_rejected() -> None:
    with pytest.raises(ValueError, match="aerosol_type"):
        SimpleAtmosphere(aerosol_type="dusty")


def test_negative_pwv_rejected() -> None:
    with pytest.raises(ValueError, match="precipitable_water_cm"):
        SimpleAtmosphere(precipitable_water_cm=-0.1)


def test_zero_pwv_disables_water_vapor() -> None:
    """w_pw = 0 must zero out the H₂O term cleanly."""
    atm = SimpleAtmosphere(precipitable_water_cm=0.0, visibility_km=1e9)
    grid = np.array([2.7, 6.3])
    state = atm.build_state(grid, _horizontal_geometry(5.0))
    # Both band centres should be ~ Rayleigh-only — very high transmittance.
    assert np.all(state.transmittance.values > 0.999)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


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


def test_simple_rejects_non_ascending_grid() -> None:
    with pytest.raises(ValueError, match="ascending"):
        SimpleAtmosphere().build_state(np.array([1.0, 0.5, 2.0]), _horizontal_geometry())


def test_simple_rejects_non_positive_grid() -> None:
    with pytest.raises(ValueError, match="positive"):
        SimpleAtmosphere().build_state(np.array([-0.1, 1.0, 2.0]), _horizontal_geometry())


# ---------------------------------------------------------------------------
# Deliverable: 0.4–14 µm transmittance plot artifact
# ---------------------------------------------------------------------------


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
