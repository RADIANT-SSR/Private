"""Integration: physics cross-checks over the real 2026-07-17 MODTRAN 6 run set.

These assert relationships *between* runs in the 39-run matrix
(`docs/plans/modtran_run_matrix.csv`) that no single-file parse test can
cover — the mutual consistency of the two altitude ladders, and the
airmass behaviour that confirms the Card-3 ANGLE convention (CU-065).

The runs live gitignored under ``modtran/real_runs/`` until the committed
fixture subset lands (plan §7.1), so every test here is ``skipif``-guarded
on their presence and is a no-op in CI. They are the real-data analogue of
the plan §4 "free integration test requiring no extra runs".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader

_REAL_RUNS = Path(__file__).resolve().parents[2] / "modtran" / "real_runs"

pytestmark = pytest.mark.skipif(
    not _REAL_RUNS.exists(),
    reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)


def _band_mean_transmittance(run: str, lo_um: float, hi_um: float) -> float:
    """Mean total transmittance of ``run`` over a wavelength window [µm]."""
    wl, trans, _, _ = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
    band = (wl >= lo_um) & (wl <= hi_um)
    return float(trans[band].mean())


@pytest.mark.level2
def test_cross_ladder_consistency_C_vs_G() -> None:
    """Plan §4 cross-ladder identity: transmittance is multiplicative along
    a nadir path, so τ(100→h) / τ(35→h) must be constant across target
    altitude h — namely τ(100→35 km), the shared upper column. Block C
    (midlat_summer, 35 km sensor) and Block G (same, 100 km sensor)
    therefore validate each other with no extra runs.
    """
    # (h_tgt km, Block-C run [35 km sensor], Block-G run [100 km sensor]).
    # h=0 uses A3 for the space ladder (the plan's designated G h_tgt=0 anchor).
    pairs = [
        (0, "C1", "A3"),
        (1, "C2", "G1"),
        (5, "C3", "G2"),
        (10, "C4", "G3"),
        (20, "C5", "G4"),
        (29, "C6", "G5"),
    ]
    ratios = []
    for _h, c_run, g_run in pairs:
        tau_c = _band_mean_transmittance(c_run, 10.0, 11.0)  # LWIR window
        tau_g = _band_mean_transmittance(g_run, 10.0, 11.0)
        ratios.append(tau_g / tau_c)
    ratios_arr = np.array(ratios)
    # The ratio is the 35→100 km column transmittance: near-unity in the
    # LWIR window (thin upper atmosphere) and, crucially, constant.
    assert ratios_arr.std() < 1.0e-3, (
        f"cross-ladder ratio not constant: {ratios_arr}"
    )
    assert np.all(ratios_arr < 1.0)  # extra column only attenuates
    assert ratios_arr.mean() == pytest.approx(0.998, abs=3.0e-3)


@pytest.mark.level2
def test_airmass_monotonicity_confirms_angle_convention() -> None:
    """CU-065 physics: the B-block zenith fan (us_standard full column at
    increasing off-nadir angle) must show transmittance *decreasing* with
    off-nadir angle — proving ANGLE=180 is the shortest (nadir) path, not
    grazing. An inverted convention would reverse the ordering.
    """
    # (run, off-nadir deg) — A1 nadir (ANGLE 180), B1/B2/B3 = 30/45/60 off.
    fan = [("A1", 0.0), ("B1", 30.0), ("B2", 45.0), ("B3", 60.0)]
    taus = [_band_mean_transmittance(run, 10.0, 12.0) for run, _ in fan]
    assert taus == sorted(taus, reverse=True), (
        f"transmittance not decreasing with off-nadir angle: {taus}"
    )
    # Beer's-law airmass cross-check at 45° off-nadir (airmass = √2):
    # τ(45°) ≈ τ_nadir**(1/cos45°) = τ_nadir**√2.
    tau_nadir, tau_45 = taus[0], taus[2]
    assert tau_45 == pytest.approx(tau_nadir**np.sqrt(2.0), rel=0.02)


@pytest.mark.level2
def test_c_ladder_pinned_constants_match_files() -> None:
    """The committed MODTRAN_C_LADDER_TAU goldens in test_table_c_cells.py
    must equal what the staged tape7s actually contain — guards the
    pinned constants against transcription drift (Gap 39)."""
    from tests.integration.test_table_c_cells import MODTRAN_C_LADDER_TAU

    run_by_h = {1000.0: "C2", 5000.0: "C3", 10000.0: "C4", 20000.0: "C5", 29000.0: "C6"}
    for h, run in run_by_h.items():
        wl, trans, _, _ = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
        band_813 = float(trans[(wl >= 8.0) & (wl <= 13.0)].mean())
        band_1012 = float(trans[(wl >= 10.0) & (wl <= 12.0)].mean())
        ref_813, ref_1012 = MODTRAN_C_LADDER_TAU[h]
        assert band_813 == pytest.approx(ref_813, abs=1e-5)
        assert band_1012 == pytest.approx(ref_1012, abs=1e-5)


# ---------------------------------------------------------------------------
# E_sky_thermal parity (MODTRAN_Run_Matrix_Plan §8 criterion #5)
# ---------------------------------------------------------------------------


def _band_integral(wl: np.ndarray, values: np.ndarray, lo_um: float, hi_um: float) -> float:
    """Band-integrated quantity [unit·µm] over [lo, hi] µm."""
    band = (wl >= lo_um) & (wl <= hi_um)
    return float(np.trapezoid(values[band], wl[band]))


def _modtran_esky_thermal(run: str) -> tuple[np.ndarray, np.ndarray]:
    """E_sky_thermal from an up-looking H-run: π·L_sky at the 48.2°
    diffusivity angle approximates the hemispheric downwelling flux."""
    reader = Tape7Reader(_REAL_RUNS / f"{run}.tp7")
    wl, _, l_path, _ = reader.to_radiant_units()
    return wl, np.pi * l_path


@pytest.mark.level2
def test_diffusivity_angle_matches_hemispheric_flux() -> None:
    """Methodology check: π·L_sky(48.2°) from the up-looking H2 run must
    agree with the true hemispheric DOWN flux from the E1 flux table
    (independent MODTRAN products, same us_standard profile) to within
    the textbook diffusivity-approximation error (~15%). This validates
    using H-runs as the E_sky_thermal reference at all.
    """
    from radiant.atmosphere.modtran import ModtranFluxReader

    wl_h, esky_h = _modtran_esky_thermal("H2")
    wl_f, _e_direct, e_diffuse = ModtranFluxReader(
        _REAL_RUNS / "E1_flux.csv"
    ).to_radiant_units()

    i_h = _band_integral(wl_h, esky_h, 8.0, 12.0)
    i_f = _band_integral(wl_f, e_diffuse, 8.0, 12.0)
    # Measured 2026-07-17: ratio = 0.849 (diffusivity angle slightly
    # under-weights the warm, opaque low-elevation sky).
    assert i_h / i_f == pytest.approx(0.85, abs=0.10)


@pytest.mark.level2
def test_esky_thermal_simple_vs_modtran_characterization() -> None:
    """Criterion #5: SimpleAtmosphere's graybody E_sky_thermal compared
    against real MODTRAN H-run downwelling (us_standard H2, tropical H4).

    RESULT (2026-07-17, CU-155): parity is NOT achieved — the simple
    backend underestimates downwelling sky irradiance by ~7× in the LWIR
    and ~25–50× in the MWIR for a space-sensor column. Two causes:
    (1) T_atm_eff evaluates at 0.5·h_sensor and clamps to the 216.65 K
    tropopause for h_sensor ≥ 22 km, while real downwelling is dominated
    by ~280 K near-surface air (the E1 flux DOWN at 14.4 µm ≈ π·B(283 K));
    (2) the 3-component simple model has no H₂O continuum, so the LWIR
    window is too transparent and the sky under-emits.

    This test pins BOTH sides of the characterization: the MODTRAN
    reference magnitudes (stable goldens for the H-runs) and the
    documented deficit band. If SimpleAtmosphere's downwelling model is
    ever improved (CU-155), the ratio assertions flip and force this
    characterization — and the CU — to be updated together.
    """
    import warnings as _warnings

    from radiant.api.session import RadiantSession
    from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere
    from radiant.core.los_geometry import LineOfSightGeometry

    # (run, profile, LWIR MODTRAN golden W/m², MWIR MODTRAN golden W/m²)
    cases = [
        ("H2", "us_standard", 20.87, 2.44),
        ("H4", "tropical", 66.76, 4.11),
    ]
    for run, profile, lwir_ref, mwir_ref in cases:
        wl, esky_mod = _modtran_esky_thermal(run)

        # MODTRAN reference magnitudes are stable goldens (2026-07-17 set).
        assert _band_integral(wl, esky_mod, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.02)
        assert _band_integral(wl, esky_mod, 3.0, 5.0) == pytest.approx(mwir_ref, rel=0.02)

        # Simple backend at the matching geometry: ground target, space
        # sensor (full column), matching profile + profile-coupled PWV.
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", profile)
        params.set("atmosphere.precipitable_water_cm", PROFILE_PWV_CM[profile])
        params.set("geometry.sensor_altitude_m", 100_000.0)
        params.set("optics.aperture_diameter_m", 0.08)
        params.set("optics.focal_length_m", 0.20)
        params.set("optics.transmission_scalar", 0.60)
        params.set("detector.pixel_pitch_x_um", 17.0)
        params.set("detector.pixel_pitch_y_um", 17.0)
        params.set("detector.qe_value", 0.55)
        params.set("detector.dark_rate_e_per_s", 1000.0)
        params.set("spectral_integration.filter_min_um", float(wl[0]))
        params.set("spectral_integration.filter_max_um", float(wl[-1]))
        params.set("spectral_integration.integration_time_s", 0.015)
        params.set("readout.read_noise_e_rms", 20.0)
        params.set("readout.gain_e_per_dn", 2.0)
        params.set("readout.adc_bits", 14)
        params.resolve()

        atm = SimpleAtmosphere(
            standard_atmosphere=profile,
            precipitable_water_cm=PROFILE_PWV_CM[profile],
        )
        los = LineOfSightGeometry(
            h_tgt=0.0, theta_o=0.0, h_atm_top=1.0e5, theta_s=None, delta_phi=None
        )
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            quantities = atm.evaluate(wl, los, params)

        lwir_simple = _band_integral(wl, quantities.E_sky_thermal, 8.0, 12.0)
        mwir_simple = _band_integral(wl, quantities.E_sky_thermal, 3.0, 5.0)

        # The characterized deficit (CU-155): simple/MODTRAN in
        # [0.03, 0.25] LWIR, [0.005, 0.10] MWIR for these profiles.
        assert 0.03 < lwir_simple / lwir_ref < 0.25, (
            f"{run}/{profile}: LWIR E_sky_thermal ratio "
            f"{lwir_simple / lwir_ref:.3f} outside the CU-155 characterized "
            "band — if the simple downwelling model was improved, update "
            "this characterization and the CU-155 record together."
        )
        assert 0.005 < mwir_simple / mwir_ref < 0.10, (
            f"{run}/{profile}: MWIR E_sky_thermal ratio "
            f"{mwir_simple / mwir_ref:.3f} outside the CU-155 characterized band."
        )
