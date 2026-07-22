"""Integration: exo-altitude target over an atmospheric background (Gap 95).

The missile-defense driver scenario: a sub-pixel target above the
atmospheric column (h_tgt = 101 km) viewed from LEO (500 km) must run
end-to-end with an exact vacuum target leg — τ_up ≡ 1, L_path_up ≡ 0 —
while the ground→sensor full column (τ_full_up, L_path_full) survives to
the background/noise branch. Exercised on the shipped interpolated
ladder library (the axes-matched default) so the whole out-of-the-box
configuration path is covered.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession


def _params(session: RadiantSession, h_tgt_m: float):  # type: ignore[no-untyped-def]
    p = session.default_params()
    p.set("source.target.temperature", 700.0)  # hot booster body [K]
    p.set("source.target.emissivity", 0.9)
    p.set("geometry.target.shape", "sphere")
    p.set("geometry.target.shape_radius_m", 2.0)
    p.set("atmosphere.model", "interpolated")
    p.set("atmosphere.interpolation_axes", "sensor_altitude_m,target_altitude_m")
    p.set("geometry.sensor_altitude_m", 500_000.0)
    p.set("geometry.target_altitude_m", h_tgt_m)
    p.set("optics.aperture_diameter_m", 0.30)
    p.set("optics.focal_length_m", 0.75)
    p.set("optics.transmission_scalar", 0.60)
    p.set("detector.pixel_pitch_x_um", 17.0)
    p.set("detector.pixel_pitch_y_um", 17.0)
    p.set("detector.qe_value", 0.55)
    p.set("detector.dark_rate_e_per_s", 1000.0)
    p.set("spectral_integration.filter_min_um", 8.0)
    p.set("spectral_integration.filter_max_um", 13.0)
    p.set("spectral_integration.integration_time_s", 0.015)
    p.set("readout.read_noise_e_rms", 20.0)
    p.set("readout.gain_e_per_dn", 2.0)
    p.set("readout.adc_bits", 14)
    p.resolve()
    return p


@pytest.mark.level2
def test_exo_target_chain_runs_with_vacuum_leg_and_full_column_background() -> None:
    wl = np.linspace(8.0, 13.0, 251)
    session = RadiantSession(wavelength_um=wl)
    params = _params(session, h_tgt_m=101_000.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = session.run(params)

    q = result.stage_outputs["atmosphere"]["atm_quantities"]
    # Vacuum target leg — exact identities [dimensionless / W/m²/sr/µm].
    np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
    np.testing.assert_array_equal(q.tau_sun, np.ones_like(wl))
    np.testing.assert_array_equal(q.L_path_up, np.zeros_like(wl))
    # The background column is a real atmosphere, not vacuum.
    assert q.tau_full_up.min() < 1.0
    assert q.L_path_full.max() > 0.0
    # And the chain completes with a finite detection metric.
    assert np.isfinite(float(result.metrics["snr"]))
    assert float(result.metrics["snr"]) > 0.0


@pytest.mark.level2
def test_mid_boost_target_runs_with_real_partial_column() -> None:
    """Boost plan §5 chain smoke: a mid-boost target (h_tgt = 50 km, still
    inside the atmosphere) viewed from LEO runs on the shipped boost-ladder
    family with a REAL τ_up — between the 29 km rung and the vacuum limit,
    not the exo identity. Complements the h_tgt ≥ 100 km vacuum case."""
    from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

    boost_dir = _SHIPPED_ATMOSPHERES_DIR / "midlat_summer_boost_ladder"
    if not boost_dir.exists():
        pytest.skip("shipped boost-ladder family not present")

    wl = np.linspace(8.0, 13.0, 251)
    session = RadiantSession(wavelength_um=wl)
    p = _params(session, h_tgt_m=50_000.0)
    p.set("atmosphere.interpolated_data_dir", str(boost_dir))
    p.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = session.run(p)

    q = result.stage_outputs["atmosphere"]["atm_quantities"]
    # Real partial column: NOT the vacuum identity, NOT fully absorbed.
    tau_up_mean = float(q.tau_up.mean())
    assert 0.9 < tau_up_mean < 1.0  # 8–13 µm band τ_up(→50 km) ≈ 0.999
    assert np.any(q.tau_up < 1.0)  # not the exo identity
    # Full column stays more opaque than the partial (more absorber below).
    assert float(q.tau_full_up.mean()) < tau_up_mean
    assert np.isfinite(float(result.metrics["snr"]))
    assert float(result.metrics["snr"]) > 0.0


@pytest.mark.level2
def test_acceptance_sweep_target_altitude_through_endo_exo_boundary() -> None:
    """Boost plan §6 acceptance criterion 1: a single config sweeps
    geometry.target_altitude_m from ground to 300 km on the shipped
    off-nadir family (default for the 3-axis case) and produces monotone
    τ_up — rising through the endo band, exactly 1.0 above the 100 km
    handoff — with no errors and no CU-167 ignored-geometry warnings, at
    an off-nadir zenith (45°)."""
    from radiant.atmosphere.loaders import _SHIPPED_ATMOSPHERES_DIR

    if not (_SHIPPED_ATMOSPHERES_DIR / "midlat_summer_boost_offnadir").exists():
        pytest.skip("shipped off-nadir family not present")

    wl = np.linspace(8.0, 13.0, 121)
    session = RadiantSession(wavelength_um=wl)
    tau_up_means: list[float] = []
    for h_km in (0.0, 29.0, 50.0, 80.0, 100.0, 150.0, 300.0):
        p = _params(session, h_tgt_m=h_km * 1000.0)
        p.set(
            "atmosphere.interpolation_axes", "sensor_altitude_m,target_altitude_m,path_zenith_rad"
        )
        p.set("geometry.path_zenith_rad", float(np.radians(45.0)))
        p.resolve()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = session.run(p)
        # The acceptance criterion forbids CU-167 ignored-geometry warnings.
        geometry_warnings = [w for w in caught if "IGNORED" in str(w.message)]
        assert geometry_warnings == [], (
            f"CU-167 geometry warning at h_tgt={h_km} km: "
            f"{[str(w.message) for w in geometry_warnings]}"
        )
        q = result.stage_outputs["atmosphere"]["atm_quantities"]
        assert np.isfinite(float(result.metrics["snr"]))
        tau_up_means.append(float(q.tau_up.mean()))

    # Monotone non-decreasing τ_up, saturating to exactly 1.0 above 100 km.
    for a, b in zip(tau_up_means, tau_up_means[1:], strict=False):
        assert a <= b + 1e-9, f"τ_up not monotone across the sweep: {tau_up_means}"
    assert tau_up_means[-1] == pytest.approx(1.0, abs=1e-9)  # 300 km: vacuum
    assert tau_up_means[-3] == pytest.approx(1.0, abs=1e-9)  # 100 km: handoff


@pytest.mark.level2
def test_exo_background_column_matches_surface_target_run() -> None:
    """The exo run's background column equals a surface-target run's —
    the Gap 95 branch changes only the target leg."""
    wl = np.linspace(8.0, 13.0, 251)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        session_exo = RadiantSession(wavelength_um=wl)
        r_exo = session_exo.run(_params(session_exo, h_tgt_m=101_000.0))
        session_surf = RadiantSession(wavelength_um=wl)
        r_surf = session_surf.run(_params(session_surf, h_tgt_m=0.0))

    q_exo = r_exo.stage_outputs["atmosphere"]["atm_quantities"]
    q_surf = r_surf.stage_outputs["atmosphere"]["atm_quantities"]
    np.testing.assert_array_equal(q_exo.tau_full_up, q_surf.tau_full_up)
    np.testing.assert_array_equal(q_exo.L_path_full, q_surf.L_path_full)
